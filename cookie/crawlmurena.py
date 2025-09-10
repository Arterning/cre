import subprocess
import re
import time
import sys
import os
import json
import base64
from datetime import datetime, timedelta
from convert import convert_to_netscape, convert_cookies_to_netscape
from utils import zip_email_files

# 示例 1：执行简单命令并获取输出
def run_command(command):
    try:
        # 执行命令，捕获输出
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }
    except subprocess.SubprocessError as e:
        print(f"命令执行失败：{e}")



def fetch_murena_emails(email, cookies, proxy):
    """
    使用 curl 命令获取 Murena 邮件。
    cookies: Netscape 格式的 cookies 字符串。
    proxy: 代理地址，例如 'http://
    """
    valid_proxy = ""
    result = {
        "stdout": "",
        "stderr": "",
        "returncode": 0
    }
    regex1 = r'"accountHash":"([a-f0-9]{40})"'
    regex2 = r'"token":"([a-f0-9-]{42})"'
    cookiedata = f"__Host-nc_sameSiteCookielax=true; __Host-nc_sameSiteCookiestrict=true;"
    if "✓" in cookies:
        print("Cookies 不是 Netscape 格式，正在转换...")
        convert_cookies_to_netscape(cookies)
    else:
        print("Cookies 已经是 Netscape 格式，无需转换。")
        # save cookies to netscape-cookies.txt
        with open('netscape-cookies.txt', 'w') as f:
            f.write(cookies)

    if proxy:
        if isinstance(proxy, str):
            cmd = f"curl --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/AppData/' --cookie '{cookiedata}' --proxy {proxy}"
            result = run_command(cmd)  # 使用管道的命令
            valid_proxy = proxy
            print("使用代理", proxy)
        if isinstance(proxy, list):
            for p in proxy:
                print("尝试使用代理", p)
                cmd = f"curl --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/AppData/' --cookie '{cookiedata}' --proxy {p}"
                result = run_command(cmd)
                regex1 = r'"accountHash":"([a-f0-9]{40})"'
                regex2 = r'"token":"([a-f0-9-]{42})"'
                accountHash = re.findall(regex1, result["stdout"])
                token = re.findall(regex2, result["stdout"])[0]
                if len(accountHash) == 0 or len(token) == 0:
                    print("代理不可用，尝试下一个代理", p)
                    continue
                else:
                    print("代理可用，使用代理", p)
                    valid_proxy = p
                    break
                
    else:
        result = run_command(f"curl --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/AppData/' --cookie '{cookiedata}'")


    accountHash = re.findall(regex1, result["stdout"])
    token = re.findall(regex2, result["stdout"])[0]
    accountHashlist = list(set(accountHash))
    #tokenlist = list(set(token))
    print("获取到账户hash{}".format(accountHash))

    print("获取到账户token{}".format(token))
    data = {
        "folder": "INBOX",
        "offset": 0,
        "limit": 999,
        "uidNext": 0,
        "sort": "",
        "search": "",
        "threadUid": 0,
        "Action": "MessageList"
    }
    postdata = json.dumps(data)
    token = f"X-SM-Token: {token}"
    contenttype = "Content-Type: application/json"
    if valid_proxy == "":
        cmd = f"curl -X POST --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/Json/&q[]=/0/' --cookie '{cookiedata}' -H '{token}' -H '{contenttype}' -d '{postdata}'"
    else:
        cmd = f"curl -X POST --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/Json/&q[]=/0/' --cookie '{cookiedata}' --proxy {valid_proxy} -H '{token}' -H '{contenttype}' -d '{postdata}'"
    result = run_command(cmd)  # 使用管道的命令
    regex3 = r'"uid":(\d+)'
    match = re.search(regex3, result["stdout"])
    uid = match.group(1)
    print("获取到{}封邮件".format(uid))

    account_name = email.replace('@', '_')
    output_dir = f"/tmp/exportmail/{account_name}/"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print("输出目录为：", output_dir)
    for i in range(int(uid)):
        print("正在收取第{}封邮件".format(i+1))
        output_file = f"{output_dir}/output_{i+1}.eml"
        json_data = {"folder":"INBOX","uid":0,"mimeType":"message/rfc822","fileName":"","accountHash":""}
        json_data["accountHash"] = accountHash[0]
        json_data["uid"] = i+1
        json_data = json.dumps(json_data, separators=(',', ':'))
        #print(json_data)
        encoded_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
        encoded_data = encoded_data.rstrip("=")
        #print(encoded_data)
        cmd=f"curl --proxy {valid_proxy}  -o {output_file} --cookie '{cookiedata}' --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/Raw/&q[]=/0/Download/&q[]=/{encoded_data}'"
        result =run_command(cmd)
        print(result["stdout"])
        time.sleep(10)

    # 创建压缩包
    zip_output_dir = f"/tmp/exportmail/"
    total_size = zip_email_files(email, zip_output_dir)
    total_emails = len(range(int(uid)))
    print(f"已导出 {total_emails} 封邮件，压缩包大小为 {total_size} 字节。")
    return total_size, total_emails



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python convert_cookies.py <file-with-cookies-copy-pasted-from-Chrome.txt> > netscape-cookies.txt", file=sys.stderr)
        print("\n确保将 <file-with-cookies-copy-pasted-from-Chrome.txt> 替换为从 Chrome 的 Application -> Storage -> Cookies 复制的 cookies 文件名。", file=sys.stderr)
        print("\n然后，将 'netscape-cookies.txt' 文件传递给 'curl' 或 'youtube-dl' 或其他支持 Netscape cookies 格式的工具。", file=sys.stderr)
        sys.exit(1)

    filename = sys.argv[1]
    convert_to_netscape(filename)
    cookiedata = f"__Host-nc_sameSiteCookielax=true; __Host-nc_sameSiteCookiestrict=true;"
    cmd = f"curl --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/AppData/' --cookie '{cookiedata}' --proxy http://172.17.120.142:7890"
    result = run_command(cmd)  # 使用管道的命令
    regex1 = r'"accountHash":"([a-f0-9]{40})"'
    regex2 = r'"token":"([a-f0-9-]{42})"'
    accountHash = re.findall(regex1, result["stdout"])
    token = re.findall(regex2, result["stdout"])[0]
    accountHashlist = list(set(accountHash))
    #tokenlist = list(set(token))
    print("获取到账户hash{}".format(accountHash))

    print("获取到账户token{}".format(token))

    data = {
    "folder": "INBOX",
    "offset": 0,
    "limit": 999,
    "uidNext": 0,
    "sort": "",
    "search": "",
    "threadUid": 0,
    "Action": "MessageList"
    }
    postdata = json.dumps(data)
    token = f"X-SM-Token: {token}"
    contenttype = "Content-Type: application/json"
    cmd = f"curl -X POST --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/Json/&q[]=/0/' --cookie '{cookiedata}' --proxy http://172.17.120.142:7890 -H '{token}' -H '{contenttype}' -d '{postdata}'"
    result = run_command(cmd)  # 使用管道的命令
    regex3 = r'"uid":(\d+)'
    match = re.search(regex3, result["stdout"])
    uid = match.group(1)
    print("获取到{}封邮件".format(uid))

    for i in range(int(uid)):
        print("正在收取第{}封邮件".format(i+1))
        output_file = f"./exportmail/output_{i+1}.eml"
        json_data = {"folder":"INBOX","uid":0,"mimeType":"message/rfc822","fileName":"","accountHash":""}
        json_data["accountHash"] = accountHash[0]
        json_data["uid"] = i+1
        json_data = json.dumps(json_data, separators=(',', ':'))
        #print(json_data)
        encoded_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
        encoded_data = encoded_data.rstrip("=")
        #print(encoded_data)
        cmd=f"curl --proxy http://172.17.120.142:7890  -o {output_file} --cookie '{cookiedata}' --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/Raw/&q[]=/0/Download/&q[]=/{encoded_data}'"
        result =run_command(cmd)
        print(result["stdout"])

        time.sleep(10)