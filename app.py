# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, send_file
from imap import IMAPEmailDownloader
from crawl import process_email_accounts
from token_crawl import fetch_all_emails_by_token
from cookie_crawl import fetch_all_emails_by_cookie
from crawlgmail import list_gmails
from crawlyahoo import list_yahoo_emails
from convert import decode_base64
from mx import get_email_provider_type
from datetime import datetime, timezone
import threading
import traceback
import sqlite3
import os
import uuid
import time
import zipfile
from database import init_db, insert_task, update_task_status, insert_task_detail, update_task_detail, DB_PATH
import sys
import io
from ai import claude_client


app = Flask(__name__)


def async_process(task_id, crawl_type, email_accounts, email_cookies, proxy_list=None, user_agent_list=None):
    total_emails = 0
    total_size = 0
    try:
        update_task_status(task_id, 'running')
        if crawl_type == 'cookie':
            total_emails, total_size = fetch_all_emails_by_cookie(task_id, email_cookies)
        if crawl_type == 'token':
            total_emails, total_size = fetch_all_emails_by_token(task_id, email_accounts)
        if crawl_type == 'imap':
            email_downloader = IMAPEmailDownloader(task_id)
            total_emails, total_size = email_downloader.process_accounts(email_accounts)
        if crawl_type == 'default':
            total_emails, total_size = process_email_accounts(
                task_id,
                email_accounts, 
                proxy_list=proxy_list, 
                user_agent_list=user_agent_list
            )
        print("任务完成, 总邮件数:", total_emails, "总大小:", total_size)
        error = None
        if total_emails == 0:
            error = "没有找到任何邮件，请检查登录信息或 cookies 是否正确。"
        update_task_status(task_id=task_id, status='finished', error=error, total_emails=total_emails, total_size=total_size)
    except Exception as e:
        traceback.print_exc()
        update_task_status(task_id, 'failed', str(e))


@app.route("/")
def hello_world():
    return "<p>running!</p>"

@app.route('/validate_cookies', methods=['POST'])
def validate_cookies():
    data = request.get_json()
    email_cookies = data.get('email_cookies', [])
    for email in email_cookies:
        if 'email' not in email or 'cookies' not in email:
            return jsonify({"error": "Each cookie must include 'email' and 'cookie'"}), 400
    response = []    
    for email in email_cookies:
        mails = 0
        email_address = email['email']
        try :
            cookies = decode_base64(email['cookies'])
        except Exception as e:
            print(f"Failed to decode cookies for {email_address}: {e}")
            response.append({"email": email_address, "status": "invalid"})
            continue  # 如果解码失败，跳过这个邮箱
        
        if email_address.endswith('@gmail.com'):
            mails = list_gmails(cookies)
        elif email_address.endswith('@yahoo.com'):
            mails = list_yahoo_emails(cookies)
        else:
            raise ValueError(f"Unsupported email domain for {email}. Only Gmail and Yahoo are supported.")
        
        if mails > 0:
            response.append({"email": email_address, "status": "valid"})
        else:
            response.append({"email": email_address, "status": "invalid"})
    return jsonify(response)



@app.route('/submit_emails', methods=['POST'])
def submit_emails():
    data = request.get_json()

    # if not data or 'email_accounts' not in data:
    #     return jsonify({"error": "Missing 'email_accounts' parameter"}), 400

    email_accounts = data.get('email_accounts', [])
    email_cookies = data.get('email_cookies', [])
    crawl_type = data.get('crawl_type', 'default')

    for account in email_accounts:
        if 'email' not in account or 'password' not in account:
            return jsonify({"error": "Each account must include 'email' and 'password'"}), 400
        
    for email in email_cookies:
        if 'email' not in email or 'cookies' not in email:
            return jsonify({"error": "Each cookie must include 'email' and 'cookie'"}), 400

    # 提取全局代理和用户代理设置
    proxy_list = None
    user_agent_list = None
    
    # 检查是否有全局设置
    if 'proxy_list' in data:
        proxy_list = data['proxy_list']
    elif 'proxy' in data:
        proxy_list = [data['proxy']] if data['proxy'] else None
        
    if 'user_agent_list' in data:
        user_agent_list = data['user_agent_list']
    elif 'user_agent' in data:
        user_agent_list = [data['user_agent']] if data['user_agent'] else None

    # 创建任务记录并获取任务 ID
    task_id = insert_task(crawl_type)

    # 启动后台线程处理任务
    thread = threading.Thread(target=async_process, args=(
        task_id, 
        crawl_type, 
        email_accounts,
        email_cookies,
        proxy_list, 
        user_agent_list
        ))
    thread.start()

    email_cookies = data.get('email_cookies', [])
    for email in email_cookies:
        if 'email' not in email or 'cookies' not in email:
            return jsonify({"error": "Each cookie must include 'email' and 'cookie'"}), 400
    response = []    
    for email in email_accounts:
        email_address = email['email']
        response.append({"email": email_address, "status": "valid"})
    for email in email_cookies:
        mails = 0
        email_address = email['email']
        try :
            cookies = decode_base64(email['cookies'])
        except Exception as e:
            print(f"Failed to decode cookies for {email_address}: {e}")
            response.append({"email": email_address, "status": "invalid", "error_message": "cookie 验证不通过"})
            continue  # 如果解码失败，跳过这个邮箱
        
        provider = get_email_provider_type(email_address)

        if "Google Mail" in provider or "Gmail" in provider:
            mails = list_gmails(cookies)
        elif "Yahoo Mail" in provider or "Yahoo" in provider:
            mails = list_yahoo_emails(cookies)
        elif "Murena Mail" in provider or "Murena" in provider:
            pass
        else:
            raise ValueError(f"Unsupported email domain for {email}. Only Gmail and Yahoo are supported.")
        
        if mails > 0:
            response.append({"email": email_address, "status": "valid"})
        else:
            response.append({"email": email_address, "status": "invalid", "error_message": "cookie 验证不通过"})

    return jsonify({"status": "submitted", "task_id": task_id, "emails": response})


@app.route('/task_status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, unique_code, crawl_type, status, total_emails, total_size, created_at, error FROM tasks WHERE id = ?', (task_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    def to_iso_format(ts_str):
        if not ts_str:
            return None
        try:
            # Handle format with microseconds
            dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S.%f')
        except (ValueError, TypeError):
            # Handle format without microseconds
            try:
                dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                # Return original if parsing fails (might already be in a different format or None)
                return ts_str
        # Assume the stored time is naive, localize it to server's timezone
        dt_local = dt.astimezone()
        return dt_local.isoformat()

    task_data = {
        "task_id": row[0],
        "unique_code": row[1],
        "crawl_type": row[2],
        "status": row[3],
        "total_emails": row[4],
        "total_size": row[5],
        "created_at": to_iso_format(row[6]),
        "error": row[7],
        "details": []
    }

    c.execute('SELECT email, start_time, end_time, status, email_count, total_size, error, unique_code FROM task_details WHERE task_id = ?', (task_id,))
    details_rows = c.fetchall()
    conn.close()

    for detail_row in details_rows:
        task_data["details"].append({
            "email": detail_row[0],
            "start_time": to_iso_format(detail_row[1]),
            "end_time": to_iso_format(detail_row[2]),
            "status": detail_row[3],
            "email_count": detail_row[4],
            "total_size": detail_row[5],
            "error": detail_row[6],
            "unique_code": detail_row[7]
        })

    return jsonify(task_data)



def async_claude_process(task_id, accounts, max_attempts):
    total_processed = 0
    total_success = 0
    
    try:
        update_task_status(task_id, 'running')
        
        for account in accounts:
            username = account['username']
            password = account['password']
            
            # Create task detail record for this account
            detail_id = insert_task_detail(task_id, username)
            
            try:
                # Create args object similar to command line arguments
                class Args:
                    def __init__(self):
                        self.username = username
                        self.password = password
                        self.max_attempts = max_attempts
                        self.auto_query_imap = True
                        self.key_file = 'ai/key.txt'
                        self.auto_codegen = True
                        self.model = claude_client.DEFAULT_MODEL
                        self.max_tokens = 50000
                        self.system = None
                        self.prompt = None
                        self.stdin_json = False
                        self.api_url = claude_client.ANTHROPIC_API_URL
                        self.timeout = 30.0
                        self.retries = 2
                        self.templates_root = "log"
                        self.code_lang = "python"
                        self.entry_filename = ""
                        self.domain = None
                        self.imap_server = None
                        self.imap_port = None
                
                args = Args()
                
                # Call download_emails directly
                claude_client.download_emails(args)
                
                # If we get here without exception, consider it successful
                update_task_detail(detail_id, 'finished', 1, 0, None)
                total_success += 1
                    
            except Exception as e:
                traceback.print_exc()
                update_task_detail(detail_id, 'failed', 0, 0, str(e))
            
            total_processed += 1
        
        # Update main task status
        if total_success == len(accounts):
            update_task_status(task_id, 'finished', None, total_success, 0)
        elif total_success > 0:
            update_task_status(task_id, 'finished', f"Processed {total_success}/{len(accounts)} accounts successfully", total_success, 0)
        else:
            update_task_status(task_id, 'failed', 'All accounts failed to process')
            
    except Exception as e:
        traceback.print_exc()
        update_task_status(task_id, 'failed', str(e))


@app.route('/claude_email', methods=['POST'])
def claude_email():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Missing JSON data"}), 400
    
    accounts = data.get('accounts', [])
    max_attempts = data.get('max_attempts', 2)
    
    if not accounts:
        return jsonify({"error": "Missing 'accounts' parameter"}), 400
    
    # Validate accounts format
    for account in accounts:
        if 'username' not in account or 'password' not in account:
            return jsonify({"error": "Each account must include 'username' and 'password'"}), 400
    
    # Create task record and get task ID
    task_id = insert_task('claude_email')
    
    # Start background thread to process task
    thread = threading.Thread(target=async_claude_process, args=(
        task_id, accounts, max_attempts
    ))
    thread.start()
    
    return jsonify({
        "status": "submitted",
        "task_id": task_id,
        "accounts_count": len(accounts),
        "max_attempts": max_attempts
    })


@app.route('/download', methods=['GET'])
def download_file():

    email = request.args.get('email')
    anchormailbox = request.args.get('anchormailbox')

    # Check if email domain is supported
    supported_domains = {
        'outlook.com', 'gmail.com', 'tutamail.com', 
        'murena.io', 'proton.me', 'yahoo.com',
        'ymail.com', 'rocketmail.com', 'yahoo.com.cn', 'yahoo.cn',
    }

    if email:
        email_domain = email.split('@')[-1].lower() if '@' in email else ''

        if email_domain not in supported_domains:
            provider = get_email_provider_type(email)  # 调用函数获取邮箱类型
            if "未知" in provider:
                return {"error": "不支持的邮箱类型"}, 400


    if not email and not anchormailbox:
        return {"error": "缺少 email 或者 anchormailbox参数"}, 400

    output_dir="/tmp/exportmail/"

    if anchormailbox:
        file_path = os.path.join(output_dir, f"{anchormailbox}.zip")

    if email:
        account_name = email.split('@')[0]
        account_dir = os.path.join(output_dir, account_name)
        file_path = os.path.join(output_dir, f"{email.replace('@', '_')}.zip")

    # 拼接文件路径
    #safe_email = email.replace("/", dd"_")  # 简单防止路径注入
    #file_path = f"/tmp/exportmail/{safe_email}.zip"

    print("file_path", file_path)
     

    if not os.path.exists(file_path):
        # Generate welcome email in EML format
        welcome_content = f"""From: www.{email_domain}
To: {email}
Subject: 欢迎使用{email_domain}邮箱
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

尊敬的{email.split('@')[0]}用户：

欢迎您使用{email_domain}邮箱服务！我们致力于为您提供安全、稳定、高效的电子邮件服务。

感谢您的信任与支持！

{email_domain}团队
        """

        # Create temp directory if not exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Create temp file with email content
        eml_filename = f"welcome_{email.replace('@', '_')}.eml"
        eml_path = os.path.join(output_dir, eml_filename)
        
        with open(eml_path, 'w', encoding='utf-8') as f:
            f.write(welcome_content)
        
        # Create zip file
        zip_path = os.path.join(output_dir, f"{email.replace('@', '_')}.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.write(eml_path, arcname=eml_filename)
        
        # Remove the temp eml file
        os.remove(eml_path)
        
        # Update file_path to point to the newly created zip
        file_path = zip_path

    # 返回文件流供用户下载
    return send_file(file_path, as_attachment=True)



if __name__ == '__main__':
    app.run(debug=True)


# 启动前初始化数据库
init_db()
