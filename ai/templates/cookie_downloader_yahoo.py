import re
import os
import time
import subprocess
from convert import convert_cookies_to_netscape
from utils import zip_email_files

# 执行命令并获取输出
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

def download_yahoo_emails(email, cookies, proxy=None, limit=0):
    regex = r'"id":\s*"([A-Za-z0-9_-]{27})"'
    valid_proxy = ""
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
            result = run_command(f"curl --cookie netscape-cookies.txt 'https://mail.yahoo.com/d/folders/1?reason=onboarded' --proxy {proxy}")  # 使用管道的命令
            valid_proxy = proxy
            print("使用代理", proxy)
        if isinstance(proxy, list):
            for p in proxy:
                print("尝试使用代理", p)
                result = run_command(f"curl --cookie netscape-cookies.txt 'https://mail.yahoo.com/d/folders/1?reason=onboarded' --proxy {p}")
                matches = re.findall(regex, result["stdout"])
                if len(matches) > 0:
                    print("代理可用，使用代理", p)
                    valid_proxy = p
                    break
    else:
        result = run_command("curl --cookie netscape-cookies.txt 'https://mail.yahoo.com/d/folders/1?reason=onboarded'")
    # print("Result:", result)
    # save result to file
    
    
    matches = re.findall(regex, result["stdout"])
    matches = list(set(matches))
    print("获取到{}封邮件".format(len(matches)))
    
    # Apply limit to the number of emails to process
    if limit > 0:
        matches = matches[:limit]
        print(f"限制处理数量为 {limit} 封邮件")
    
    account_name = email.replace('@', '_')
    output_dir = f"/tmp/exportmail/{account_name}/"
    total_emails = len(matches)

    result_file = f'{account_name}_result.txt'
    with open(result_file, 'w') as f:
        f.write(result["stdout"])
    print(f"结果已保存到 {result_file}")

    if total_emails == 0:
        print("没有找到邮件")
        return 0, 0

    for msg in matches:
        print(msg)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_file = f"{output_dir}/output_{msg}.eml"
        if valid_proxy:
            cmd=f"curl --proxy {valid_proxy}  -o {output_file} --cookie netscape-cookies.txt 'https://mail.yahoo.com/ws/v3/mailboxes/@/messages/@.id=={msg}/content/rawplaintext'"
        else:
            cmd=f"curl -o {output_file} --cookie netscape-cookies.txt 'https://mail.yahoo.com/ws/v3/mailboxes/@/messages/@.id=={msg}/content/rawplaintext'"
        result =run_command(cmd)
        print(result)
        time.sleep(10)
    
    # 创建压缩包
    zip_output_dir = f"/tmp/exportmail/"
    total_size = zip_email_files(email, zip_output_dir)
    return total_size, total_emails