import base64
import json
import tempfile
import gnupg
import typing
import requests
from urllib.parse import urlencode
from Crypto.Cipher import AES
import os
from utils import zip_email_files


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
        header = message.get("Header", "")
        body = message.get("Body", "")
        if not header and not body:
            continue
        messages.append(Message(header=header, body=body))
    return messages



def download_emails(email_address: str = "demo@proton.com", page_size: int = 50):
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

    account_name = email_address.replace('@', '_')
    output_dir = f"/tmp/exportmail/{account_name}/"

    total_emails = 0
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
                    
                    eml_content = f"{message.header}\n\n{message.body}"
                    output_file = f"{output_dir}/output_{id}.eml"
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(eml_content)
                        total_emails += 1
                    print(f"Saved message to {output_file}")
    
    # 创建压缩包
    zip_output_dir = f"/tmp/exportmail/"
    total_size = zip_email_files(email_address, zip_output_dir)
    return total_size, total_emails



if __name__ == "__main__":
    email = "demo@proton.com"
    page_size = 1
    total_size, total_emails = download_emails(email, page_size)
    print(f"Total size: {total_size} bytes")
    print(f"Total emails: {total_emails}")