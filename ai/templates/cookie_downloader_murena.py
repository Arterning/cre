import re
import os
import time
import json
import base64
import subprocess
from convert import convert_cookies_to_netscape
from utils import zip_email_files, run_command, create_account_dir


def download_murena_emails(email, cookies, proxy=None, limit=0):
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

    # Apply limit to the number of emails to process
    max_emails = int(uid)
    if limit > 0 and limit < max_emails:
        max_emails = limit
        print(f"限制处理数量为 {limit} 封邮件")

    output_dir = create_account_dir(email)
    print("输出目录为：", output_dir)
    for i in range(max_emails):
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
        if valid_proxy == "":
            cmd=f"curl -o {output_file} --cookie '{cookiedata}' --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/Raw/&q[]=/0/Download/&q[]=/{encoded_data}'"
        else:
            cmd=f"curl --proxy {valid_proxy}  -o {output_file} --cookie '{cookiedata}' --cookie netscape-cookies.txt 'https://murena.io/apps/snappymail/?/Raw/&q[]=/0/Download/&q[]=/{encoded_data}'"
        result =run_command(cmd)
        print(result["stdout"])
        time.sleep(10)

    # 创建压缩包
    total_size = zip_email_files(email)
    total_emails = max_emails
    print(f"已导出 {total_emails} 封邮件，压缩包大小为 {total_size} 字节。")
    return total_size, total_emails