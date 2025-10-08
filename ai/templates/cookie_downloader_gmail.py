import subprocess
import re
import time
import os
from utils import run_command, zip_email_files

# 从crawlgmail.py抽取的邮件下载核心方法
def download_gmail_emails(email, cookies, proxy, limit=5):
    regex = r"msg-f:\d{19}"
    valid_proxy = ""
    if "✓" in cookies:
        print("Cookies 不是 Netscape 格式，正在转换...")
        # 注意：convert_cookies_to_netscape函数需要从原文件中导入
        from convert import convert_cookies_to_netscape
        convert_cookies_to_netscape(cookies)
    else:
        print("Cookies 已经是 Netscape 格式，无需转换。")
        # save cookies to netscape-cookies.txt
        with open('netscape-cookies.txt', 'w') as f:
            f.write(cookies)
    if proxy:
        if isinstance(proxy, str):
            result = run_command(f"curl --cookie netscape-cookies.txt 'https://mail.google.com/mail/u/0/' --proxy {proxy}")  # 使用管道的命令
            valid_proxy = proxy
            print("使用代理", proxy)
        if isinstance(proxy, list):
            for p in proxy:
                print("尝试使用代理", p)
                result = run_command(f"curl --cookie netscape-cookies.txt 'https://mail.google.com/mail/u/0/' --proxy {p}")
                matches = re.findall(regex, result["stdout"])
                if len(matches) > 0:
                    print("代理可用，使用代理", p)
                    valid_proxy = p
                    break
    else:
        result = run_command("curl --cookie netscape-cookies.txt 'https://mail.google.com/mail/u/0/'")
    
    # print("Result:", result)
    
    matches = re.findall(regex, result["stdout"])
    print("获取到{}封邮件".format(len(matches)))
    
    # Apply limit to the number of emails to process
    if limit > 0:
        matches = matches[:limit]
        print(f"限制处理数量为 {limit} 封邮件")
    
    account_name = email.replace('@', '_')
    
    result_file = f'{account_name}_result.txt'
    with open(result_file, 'w') as f:
        f.write(result["stdout"])
    print(f"结果已保存到 {result_file}")

    output_dir = f"/tmp/exportmail/{account_name}/"

    if not matches:
        print("没有找到邮件")
        return 0, 0

    for msg in matches:
        print(msg)
        url = f"https://mail.google.com/mail/u/0/?view=att&permmsgid={msg}&disp=comp&safe=1"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_file = f"{output_dir}/output_{msg}.eml"
        if valid_proxy:
            cmd=f"curl --proxy {valid_proxy}  -L  -J -o {output_file} --cookie netscape-cookies.txt 'https://mail.google.com/mail/u/0/?view=att&permmsgid={msg}&disp=comp&safe=1'"
        else:
            cmd=f"curl -L  -J -o {output_file} --cookie netscape-cookies.txt 'https://mail.google.com/mail/u/0/?view=att&permmsgid={msg}&disp=comp&safe=1'"
        result =run_command(cmd)
        print(result)
        time.sleep(10)

    
    # 创建压缩包
    total_size = zip_email_files(email)
    total_emails = len(matches)
    return total_size, total_emails