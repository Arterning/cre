import subprocess
import re
import time
import sys
import os
from datetime import datetime, timedelta
from convert import convert_cookies_to_netscape, convert_to_netscape
from utils import zip_email_files


def list_yahoo_emails(cookies):
    convert_cookies_to_netscape(cookies)
    result = run_command("curl --cookie netscape-cookies.txt 'https://mail.yahoo.com/d/folders/1?reason=onboarded'")
    # print("Result:", result)
    regex = r'"id":\s*"([A-Za-z0-9_-]{27})"'
    matches = re.findall(regex, result["stdout"])
    if matches == 0:
        print("没有找到邮件")
        return 0
    return len(matches)

def fetch_yahoo_emails(email, cookies, proxy):
    """
    使用 curl 命令获取 Yahoo 邮箱中的邮件 ID。
    需要提供 Netscape 格式的 cookies 文件。
    """
    convert_cookies_to_netscape(cookies)
    if proxy:
        result = run_command(f"curl --cookie netscape-cookies.txt 'https://mail.yahoo.com/d/folders/1?reason=onboarded' --proxy {proxy}")  # 使用管道的命令
    else:
        result = run_command("curl --cookie netscape-cookies.txt 'https://mail.yahoo.com/d/folders/1?reason=onboarded'")
    # print("Result:", result)
    regex = r'"id":\s*"([A-Za-z0-9_-]{27})"'
    matches = re.findall(regex, result["stdout"])
    matches = list(set(matches))
    print("获取到{}封邮件".format(len(matches)))
    account_name = email.replace('@', '_')
    output_dir = f"/tmp/exportmail/{account_name}/"
    total_emails = len(matches)
    for msg in matches:
        print(msg)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_file = f"{output_dir}/output_{msg}.eml"
        if proxy:
            cmd=f"curl --proxy {proxy}  -o {output_file} --cookie netscape-cookies.txt 'https://mail.yahoo.com/ws/v3/mailboxes/@/messages/@.id=={msg}/content/rawplaintext'"
        else:
            cmd=f"curl -o {output_file} --cookie netscape-cookies.txt 'https://mail.yahoo.com/ws/v3/mailboxes/@/messages/@.id=={msg}/content/rawplaintext'"
        result =run_command(cmd)
        print(result)
        time.sleep(10)
    
    # 创建压缩包
    zip_output_dir = f"/tmp/exportmail/"
    total_size = zip_email_files(email, zip_output_dir)
    return total_size, total_emails





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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python convert_cookies.py <file-with-cookies-copy-pasted-from-Chrome.txt> > netscape-cookies.txt", file=sys.stderr)
        print("\n确保将 <file-with-cookies-copy-pasted-from-Chrome.txt> 替换为从 Chrome 的 Application -> Storage -> Cookies 复制的 cookies 文件名。", file=sys.stderr)
        print("\n然后，将 'netscape-cookies.txt' 文件传递给 'curl' 或 'youtube-dl' 或其他支持 Netscape cookies 格式的工具。", file=sys.stderr)
        sys.exit(1)

    filename = sys.argv[1]
    convert_to_netscape(filename)
    result = run_command("curl --cookie netscape-cookies.txt 'https://mail.yahoo.com/d/folders/1?reason=onboarded' --proxy http://172.17.120.142:7890")  # 使用管道的命令
    print("Result:", result)
    regex = r'"id":\s*"([A-Za-z0-9_-]{27})"'
    matches = re.findall(regex, result["stdout"])
    matches = list(set(matches))
    print("获取到{}封邮件".format(len(matches)))
    #print(matches)
    for msg in matches:
        print(msg)
        #url = f"https://mail.yahoo.com/ws/v3/mailboxes/@/messages/@.id=={msg}/content/rawplaintext"
        output_file = f"/tmp/exportmail/output_{msg}.eml"
        cmd=f"curl --proxy http://172.17.120.142:7890  -o {output_file} --cookie netscape-cookies.txt 'https://mail.yahoo.com/ws/v3/mailboxes/@/messages/@.id=={msg}/content/rawplaintext'"
        result =run_command(cmd)
        #regex_file = r"curl: Saved to filename '([^']+)'"
        print(result)
        #matches_file = re.findall(regex_file, result["stdout"])
        #print(matches_file)
        time.sleep(10)
