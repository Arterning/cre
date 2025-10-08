from selenium import webdriver
import sys
import os

# 添加项目根目录到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import traceback
import shutil
import zipfile
import argparse
from datetime import datetime
import random
from database import insert_task_detail, update_task_detail
from ai.templates.web_downloader_outlook import process_outlook_email_account
from utils import zip_email_files, create_directory


# 处理单个账号
def process_email_account(task_id, email_account, output_dir, proxy_list=None, user_agent_list=None):
    """处理单个邮箱账号"""
    email = email_account['email']
    password = email_account['password']
    unique_code = email_account.get('unique_code')
    detail_id = insert_task_detail(task_id, email, unique_code)
    
    # 获取账号特定的代理和用户代理设置，如果没有则使用全局设置
    account_proxy_list = email_account.get('proxy', proxy_list)
    account_user_agent_list = email_account.get('ua', user_agent_list)

    # 如果是outlook邮箱，使用outlook的下载器
    if email.endswith('@outlook.com'):
        downloaded = process_outlook_email_account(email, password, output_dir, account_proxy_list, account_user_agent_list)
    else:
        # 暂不支持其他邮箱类型
        downloaded = 0
    
    if downloaded > 0:
        size = zip_email_files(email, output_dir)
        update_task_detail(detail_id, 'finished', downloaded, size, None, 'default', 'success')
    else:
        update_task_detail(detail_id, 'finished', downloaded, size, None, 'default', 'failed')
        
    except Exception as e:
        traceback.print_exc()
        update_task_detail(detail_id, 'failed', error=str(e), crawl_type='outlook', crawl_status='failed')
    return downloaded, size
    

def process_email_accounts(task_id, email_accounts, output_dir="/tmp/exportmail", proxy_list=None, user_agent_list=None):
    """处理多个邮箱账号"""
    create_directory(output_dir)
    total_emails = 0
    total_size = 0

    for account in email_accounts:
        try:
            downloaded, size = process_email_account(task_id, account, output_dir, proxy_list, user_agent_list)
            total_emails += downloaded
            total_size += size

    print(f"\n所有邮箱账号处理完成，共下载 {total_emails} 封邮件， 总大小：{total_size} 字节")
    return total_emails, total_size


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Outlook邮件下载工具')
    parser.add_argument('--email', help='邮箱地址', required=True)
    parser.add_argument('--password', help='邮箱密码', required=True)
    parser.add_argument('--output', help='输出目录', default='/outlook_emails')
    parser.add_argument('--proxy',
                        help='代理设置，支持多个代理用逗号分隔，会逐个尝试直到成功。格式: socks5://127.0.0.1:1005:username:password 或 socks5://127.0.0.1:1005')
    parser.add_argument('--ua', help='自定义User-Agent头，支持多个UA用逗号分隔，会随机选择一个')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # 配置要处理的邮箱账号
    email_accounts = [
        {"email": args.email, "password": args.password}
    ]

    # 执行邮件下载和打包
    total_emails, total_size = process_email_accounts(
        1,
        email_accounts,
        output_dir=args.output,
        proxy_list=args.proxy.split(',') if args.proxy else None,
        user_agent_list=args.ua.split(',') if args.ua else None
    )

    print(f"所有邮箱账号处理完成，共下载 {total_emails} 封邮件， 总大小：{total_size} 字节")