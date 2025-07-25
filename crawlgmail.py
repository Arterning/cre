import subprocess
import re
import time
import sys
import os
from datetime import datetime, timedelta
from convert import convert_cookies_to_netscape, convert_to_netscape
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


def fetch_emails(email, cookies, proxy):
    """
    使用 curl 命令获取 Gmail 邮件。
    cookie_file: Netscape 格式的 cookies 文件路径。
    """
    convert_cookies_to_netscape(cookies)
    result = run_command(f"curl --cookie netscape-cookies.txt 'https://mail.google.com/mail/u/0/' --proxy {proxy}")  # 使用管道的命令
    regex = r"msg-f:\d{19}"
    matches = re.findall(regex, result["stdout"])
    print("获取到{}封邮件".format(len(matches)))
    account_name = email.replace('@', '_')
    output_dir = f"/tmp/exportmail/{account_name}/"
    for msg in matches:
        print(msg)
        url = f"https://mail.google.com/mail/u/0/?view=att&permmsgid={msg}&disp=comp&safe=1"
        output_dir = f"./exportmail/{email}"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_file = f"{output_dir}/output_{msg}.eml"
        if proxy:
            cmd=f"curl --proxy {proxy}  -L  -J -o {output_file} --cookie netscape-cookies.txt 'https://mail.google.com/mail/u/0/?view=att&permmsgid={msg}&disp=comp&safe=1'"
        else:
            cmd=f"curl -L  -J -o {output_file} --cookie netscape-cookies.txt 'https://mail.google.com/mail/u/0/?view=att&permmsgid={msg}&disp=comp&safe=1'"
        result =run_command(cmd)
        print(result)
        time.sleep(10)

    # 创建压缩包
    zip_output_dir = f"/tmp/exportmail/"
    total_size = zip_email_files(email, zip_output_dir)
    return total_size


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python convert_cookies.py <file-with-cookies-copy-pasted-from-Chrome.txt> > netscape-cookies.txt", file=sys.stderr)
        print("\n确保将 <file-with-cookies-copy-pasted-from-Chrome.txt> 替换为从 Chrome 的 Application -> Storage -> Cookies 复制的 cookies 文件名。", file=sys.stderr)
        print("\n然后，将 'netscape-cookies.txt' 文件传递给 'curl' 或 'youtube-dl' 或其他支持 Netscape cookies 格式的工具。", file=sys.stderr)
        sys.exit(1)

    filename = sys.argv[1]
    convert_to_netscape(filename)
    proxy="http://172.17.120.142:7890"
    result = run_command("curl --cookie netscape-cookies.txt 'https://mail.google.com/mail/u/0/' --proxy {proxy}")  # 使用管道的命令
    regex = r"msg-f:\d{19}"
    matches = re.findall(regex, result["stdout"])

    print(matches)
    for msg in matches:
        print(msg)
        url = f"https://mail.google.com/mail/u/0/?view=att&permmsgid={msg}&disp=comp&safe=1"
        output_file = f"./exportmail/output_{msg}.eml"
        cmd=f"curl --proxy {proxy}  -L  -J -o {output_file} --cookie netscape-cookies.txt 'https://mail.google.com/mail/u/0/?view=att&permmsgid={msg}&disp=comp&safe=1'"
        result =run_command(cmd)
        #regex_file = r"curl: Saved to filename '([^']+)'"
        print(result)
        #matches_file = re.findall(regex_file, result["stdout"])
        #print(matches_file)
        time.sleep(10)
