import base64
import json
import tempfile
import gnupg
import typing
import requests
from urllib.parse import urlencode
from Crypto.Cipher import AES


class Message:
    header: str
    body: str
    def __init__(self, header: str, body: str):
        self.header = header
        self.body = body
    
    def __repr__(self):
        return self.header + "\n" + self.body

def get_key_password(client_key: str, blob: str) -> str:
    client_key = base64.b64decode(client_key)
    blob = base64.b64decode(blob)
    iv, blob = blob[:16], blob[16:]
    cipher = AES.new(client_key, AES.MODE_GCM, iv)
    decrypted_data = cipher.decrypt(blob)
    for length in range(2, len(decrypted_data) + 1):
        try:
            data = decrypted_data[:length]
            return json.loads(data)["keyPassword"]
        except:
            continue
    raise ValueError("Key password not found in decrypted data")

def get_client_key(headers: typing.Dict[str, str]) -> str:
    resp = requests.get("https://mail.proton.me/api/auth/v4/sessions/local/key", headers=headers)
    return resp.json()["ClientKey"]

def get_user_private_key(headers: typing.Dict[str, str]) -> str:
    resp = requests.get("https://mail.proton.me/api/core/v4/users", headers=headers)
    for key in resp.json()["User"]["Keys"]:
        if key["Primary"] == 1:
            return key["PrivateKey"]
    raise ValueError("Primary private key not found in user keys")

def get_address(headers: typing.Dict[str, str]) -> typing.Tuple[str, str]:
    resp = requests.get("https://mail.proton.me/api/core/v4/addresses?Page=0&PageSize=50", headers=headers)
    results: typing.List[typing.Tuple[str, str]] = []
    for addr in resp.json()["Addresses"]:
        for key in addr["Keys"]:
            if key["Token"] and key["PrivateKey"]:
                return key["Token"], key["PrivateKey"]
    if not results:
        raise ValueError("No address keys found in response")
    return results

def get_conversations(*, label_id: int, headers: typing.Dict[str, str], page: int, page_size: int) -> typing.List[str]:
    url = "https://mail.proton.me/api/mail/v4/conversations?" + urlencode({
        "LabelID": label_id,
        "Page": page,
        "PageSize": page_size,
        "Desc": "1",
    })
    resp = requests.get(url, headers=headers)
    ids: typing.List[str] = []
    for conversation in resp.json()["Conversations"]:
        ids.append(conversation["ID"])
    return ids

def get_label_id(headers: typing.Dict[str, str]) -> typing.Tuple[int, int]:
    url = "https://mail.proton.me/api/mail/v4/conversations/count"
    resp = requests.get(url, headers=headers)
    label = max(resp.json()["Counts"], key=lambda x: x["Total"])
    return (label["LabelID"], label["Total"])

def get_messages(*, headers: typing.Dict[str, str], conversation_id: str) -> typing.List[Message]:
    url = f"https://mail.proton.me/api/mail/v4/conversations/{conversation_id}"
    resp = requests.get(url, headers=headers)
    messages: typing.List[Message] = []
    for message in resp.json()["Messages"]:
        header = message["Header"]
        body = message["Body"]
        messages.append(Message(header=header, body=body))
    return messages



def download_emails():
    BLOB = "..."
    X_PM_UID = "..."
    COOKIE = "..."

    blob = BLOB
    headers = {
        "x-pm-uid": X_PM_UID,
        "x-pm-appversion": "web-mail@5.0.72.6",
        "cookie": COOKIE
    }
    (label_id, total) = get_label_id(headers=headers)

    print(f"Label ID: {label_id}, Total Conversations: {total}")


    client_key = get_client_key(headers)
    print(f"Client Key: {client_key}")
    user_private_key = get_user_private_key(headers)
    print(f"User Private Key: {user_private_key[:30]}... (truncated)")
    address_token_message, address_private_key = get_address(headers)

    key_password = get_key_password(client_key=client_key, blob=blob)
    print(f"Key Password: {key_password}")

    page_size = 50

    with tempfile.TemporaryDirectory() as tempdir:
        gpg = gnupg.GPG(gnupghome=tempdir)
        gpg.import_keys(user_private_key)
        gpg.import_keys(address_private_key)
        address_key_password = gpg.decrypt(address_token_message, passphrase=key_password)
        address_key_password = address_key_password.data.decode("utf-8")

        for page in range(0, (total + page_size - 1) // page_size):
            print(f"Fetching conversations for page {page + 1} of {total // page_size + 1}")
            ids = get_conversations(headers=headers, label_id=label_id, page=page, page_size=page_size)
            for id in ids:
                print(f"Conversation ID: {id}")
                messages = get_messages(headers=headers, conversation_id=id)
                for message in messages:
                    body = gpg.decrypt(message.body, passphrase=address_key_password)
                    body = body.data.decode("utf-8")
                    message.body = body
                    print(message)