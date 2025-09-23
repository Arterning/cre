import os
import zipfile
from datetime import datetime
import requests
import json
import typing
import base64
from urllib.parse import quote
from database import insert_task_detail, update_task_detail
import traceback

class UserSession:
    usertoken: str
    anchormailbox: str
    def __init__(self, *, usertoken: str, anchormailbox: str):
        self.usertoken = usertoken
        self.anchormailbox = anchormailbox

class Folder:
    folder_class: typing.Optional[str] = None
    display_name: str
    total_count: int
    unread_count: int
    folder_id: str
    distinguished_folder_id: typing.Optional[str]
    def __init__(self, *, folder_class: typing.Optional[str] = None, display_name: str, total_count: int, unread_count: int, folder_id: str, distinguished_folder_id: typing.Optional[str]):
        self.folder_class = folder_class
        self.display_name = display_name
        self.total_count = total_count
        self.unread_count = unread_count
        self.folder_id = folder_id
        self.distinguished_folder_id = distinguished_folder_id
    def __repr__(self):
        return f"Folder(id={self.folder_id}, name=\"{self.distinguished_folder_id}\", total={self.total_count}, unread={self.unread_count})"

class Conversation:
    conversation_id: str
    item_ids: typing.List[str]
    global_item_ids: typing.List[str]
    preview: str

    def __init__(self, *, conversation_id: str, item_ids: typing.List[str], global_item_ids: typing.List[str], preview: str):
        self.conversation_id = conversation_id
        self.item_ids = item_ids
        self.global_item_ids = global_item_ids
        self.preview = preview

    def __repr__(self):
        return f"Conversation(id={self.conversation_id}, preview=\"{self.preview[:30]}\")"

class Eml:
    eml_data: str
    def __init__(self, *, eml_data: str):
        self.eml_data = eml_data
    def __repr__(self):
        return f"Eml(data_length={len(self.eml_data)})"
    def __str__(self):
        return self.eml_data

def fetch_folders(*, user: UserSession) -> typing.List[Folder]:
    resp = requests.post(
        url="https://outlook.live.com/owa/0/startupdata.ashx?app=Mail",
        headers={
            "authorization": f'MSAuth1.0 usertoken="{user.usertoken}", type="MSACT"',
            "x-anchormailbox": user.anchormailbox,
            "action": "StartupData",
        }
    )
    results: typing.List[Folder] = []
    for folder in resp.json()["findFolders"]["Body"]["ResponseMessages"]["Items"][0]["RootFolder"]["Folders"]:
        folder_class = folder.get("FolderClass", None)
        display_name = folder["DisplayName"]
        total_count = folder.get("TotalCount", 0)
        unread_count = folder.get("UnreadCount", 0)
        folder_id = folder["FolderId"]["Id"]
        distinguished_folder_id = folder.get("DistinguishedFolderId", None)
        results.append(Folder(
            folder_class=folder_class,
            display_name=display_name,
            total_count=total_count,
            unread_count=unread_count,
            folder_id=folder_id,
            distinguished_folder_id=distinguished_folder_id,
        ))
    return results

def fetch_conversations(*, user: UserSession, folder: Folder, offset: int, page_size: int) -> typing.List[Conversation]:
    payload: typing.Dict[str, typing.Any] = {
        "__type": "FindConversationJsonRequest:#Exchange",
        "Header": {
            "__type": "JsonRequestHeaders:#Exchange",
            "RequestServerVersion": "V2018_01_08",
            "TimeZoneContext": {
                "__type": "TimeZoneContext:#Exchange",
                "TimeZoneDefinition": {
                    "__type": "TimeZoneDefinitionType:#Exchange",
                    "Id": "China Standard Time"
                }
            }
        },
        "Body": {
            "ParentFolderId": {
                "__type": "TargetFolderId:#Exchange",
                "BaseFolderId": {
                    "__type": "FolderId:#Exchange",
                    "Id": folder.folder_id
                }
            },
            "ConversationShape": {
                "__type": "ConversationResponseShape:#Exchange",
                "BaseShape": "IdOnly"
            },
            "ShapeName": "ReactConversationListView",
            "Paging": {
                "__type": "IndexedPageView:#Exchange",
                "BasePoint": "Beginning",
                "Offset": offset,
                "MaxEntriesReturned": page_size,
            },
            "ViewFilter": "All",
            "SortOrder": [{
                "__type": "SortResults:#Exchange",
                "Order": "Descending",
                "Path": {
                    "__type": "PropertyUri:#Exchange",
                    "FieldURI": "ConversationLastDeliveryOrRenewTime"
                }
            }, {
                "__type": "SortResults:#Exchange",
                "Order": "Descending",
                "Path": {
                    "__type": "PropertyUri:#Exchange",
                    "FieldURI": "ConversationLastDeliveryTime"
                }
            }],
            "FocusedViewFilter": 0,
        }
    }
    data = quote(json.dumps(payload))
    resp = requests.post(
        url="https://outlook.live.com/owa/0/service.svc?action=FindConversation&app=Mail",
        headers={
            "authorization": f'MSAuth1.0 usertoken="{user.usertoken}", type="MSACT"',
            "x-anchormailbox": user.anchormailbox,
            "action": "FindConversation",
            "x-owa-urlpostdata": data,
            "content-type": "application/json; charset=utf-8",
        }
    )
    results: typing.List[Conversation] = []
    for conversation in resp.json()["Body"]["Conversations"]:
        conversation_id = conversation["ConversationId"]["Id"]
        preview = conversation["Preview"]
        item_ids = [item["Id"] for item in conversation["ItemIds"]]
        global_item_ids = [item["Id"] for item in conversation["GlobalItemIds"]]
        results.append(Conversation(
            conversation_id=conversation_id,
            preview=preview,
            item_ids=item_ids,
            global_item_ids=global_item_ids
        ))
    return results

def fetch_item(*, user: UserSession, item_id: str) -> Eml:
    payload: typing.Dict[str, typing.Any] = {
        "__type": "GetItemJsonRequest:#Exchange",
        "Header": {
            "__type": "JsonRequestHeaders:#Exchange",
            "RequestServerVersion": "V2016_06_24",
            "TimeZoneContext": {
                "__type": "TimeZoneContext:#Exchange",
                "TimeZoneDefinition": {
                    "__type": "TimeZoneDefinitionType:#Exchange",
                    "Id": "China Standard Time"
                }
            }
        },
        "Body": {
            "__type": "GetItemRequest:#Exchange",
            "ItemShape": {
                "__type": "ItemResponseShape:#Exchange",
                "BaseShape": "IdOnly",
                "IncludeMimeContent": True,
            },
            "ItemIds": [{
                "__type": "ItemId:#Exchange",
                "Id": item_id,
            }]
        }
    }
    data = quote(json.dumps(payload))
    resp = requests.post(
        url="https://outlook.live.com/owa/0/service.svc?action=GetItem&app=Mail",
        headers={
            "authorization": f'MSAuth1.0 usertoken="{user.usertoken}", type="MSACT"',
            "x-anchormailbox": user.anchormailbox,
            "action": "GetItem",
            "x-owa-urlpostdata": data,
            "content-type": "application/json; charset=utf-8",
        }
    )
    data = resp.json()["Body"]["ResponseMessages"]["Items"][0]["Items"][0]["MimeContent"]["Value"]
    data = base64.b64decode(data.encode("utf-8")).decode("utf-8")
    return Eml(eml_data=data)
    # print(resp.json())

def fetch_emails(usertoken, authenticate):
    anchormailbox = authenticate.get('anchormailbox', "")
    user = UserSession(
        usertoken=usertoken,
        anchormailbox=anchormailbox
    )
    folders = fetch_folders(user=user)
    all_emails = []
    total_size = 0
    for folder in folders:
        if not all([
            folder.total_count > 0,
            folder.folder_class == "IPF.Note"
        ]):
            continue
        print("Folder", folder)
        conversations = fetch_conversations(
            user=user,
            folder=folder,
            offset=0,
            page_size=2000,
        )
        for conversation in conversations:
            for item in conversation.item_ids:
                print(f"Conversation: {conversation.conversation_id}, Item ID: {item}")
                eml = fetch_item(user=user, item_id=item)
                eml_filename = f"conv_{conversation.conversation_id}_item_{item}.eml"
                eml_content = str(eml)
                all_emails.append((eml_filename, eml_content))
                total_size += len(eml_content)

    output_dir = "/tmp/exportmail/"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = os.path.join(output_dir, f"{anchormailbox}.zip")
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for eml_filename, eml_content in all_emails:
            zipf.writestr(eml_filename, eml_content)
    print(f"All EML files have been saved to {zip_filename}")
    return len(all_emails), total_size



if __name__ == "__main__":
    usertoken=""
    anchormailbox=""
    fetch_emails(usertoken=usertoken, authenticate={'anchormailbox': anchormailbox})