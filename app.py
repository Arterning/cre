# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for, session, flash
from imap import IMAPEmailDownloader
from crawl import process_email_accounts

from cookie import cookie_crawl, token_crawl
from cookie.crawlgmail import list_gmails
from cookie.crawlyahoo import list_yahoo_emails
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
from database import init_db, insert_task, update_task_status, insert_task_detail, update_task_detail, get_tasks_paginated, get_task_statistics, get_task_details, DB_PATH
import sys
import io
from ai import claude_client
from utils import zip_email_files
from dotenv import load_dotenv
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def async_process(task_id, crawl_type, email_accounts, email_cookies, proxy_list=None, user_agent_list=None):
    total_emails = 0
    total_size = 0
    try:
        update_task_status(task_id, 'running')
        if crawl_type == 'cookie':
            total_emails, total_size = cookie_crawl.fetch_all_emails_by_cookie(task_id, email_cookies)
        if crawl_type == 'token':
            total_emails, total_size = token_crawl.fetch_all_emails_by_token(task_id, email_accounts)
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
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get paginated tasks
    pagination_data = get_tasks_paginated(page=page, per_page=per_page)
    
    # Get statistics
    stats = get_task_statistics()
    
    # Create pagination object for template
    class Pagination:
        def __init__(self, data):
            for key, value in data.items():
                setattr(self, key, value)
        
        def iter_pages(self):
            # Simple pagination logic - show up to 10 pages
            start = max(1, self.page - 5)
            end = min(self.pages + 1, self.page + 6)
            
            pages = []
            if start > 1:
                pages.extend([1, None])  # None represents ellipsis
            
            for page_num in range(start, end):
                pages.append(page_num)
            
            if end <= self.pages:
                pages.extend([None, self.pages])
            
            return pages
    
    pagination = Pagination(pagination_data)
    
    return render_template('index.html', 
                         tasks=pagination_data['tasks'], 
                         pagination=pagination, 
                         stats=stats)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        admin_user = os.environ.get('ADMIN_USER')
        admin_auth = os.environ.get('ADMIN_AUTH')
        
        if username == admin_user and password == admin_auth:
            session['logged_in'] = True
            session['username'] = username
            flash('登录成功!', 'success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('已成功退出登录', 'success')
    return redirect(url_for('login'))


@app.route('/create_task')
@login_required
def create_task():
    return render_template('create_task.html')

@app.route('/batch_create_task')
@login_required
def batch_create_task():
    return render_template('batch_create_task.html')

@app.route('/api/task-details/<task_id>')
@login_required
def api_task_details(task_id):
    try:
        details = get_task_details(task_id)
        return jsonify({
            'success': True,
            'details': details
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
    total_all_emails = 0
    total_all_size = 0
    
    try:
        update_task_status(task_id, 'running')
        
        for account in accounts:
            username = account['username']
            password = account['password']
            
            # Create task detail record for this account
            detail_id = insert_task_detail(task_id, username)
            
            account_email_count = 0
            account_total_size = 0
            
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
                
                # After successful email download, zip the email files and calculate size
                try:
                    # Get the AI client path where emails are saved
                    ai_client_path = os.path.dirname(os.path.abspath(claude_client.__file__))
                    email_base_dir = os.path.join(ai_client_path, "email")
                    
                    # Create export directory if it doesn't exist
                    export_dir = "/tmp/exportmail/"
                    os.makedirs(export_dir, exist_ok=True)
                    
                    # Check if emails were saved for this user
                    if os.path.exists(email_base_dir):
                        domain = username.split('@')[1] if '@' in username else 'unknown'
                        user_part = username.split('@')[0] if '@' in username else username
                        user_email_dir = os.path.join(email_base_dir, domain, user_part)
                        
                        if os.path.exists(user_email_dir):
                            # Count emails and calculate directory size before zipping
                            email_count = 0
                            dir_size = 0
                            
                            for root, dirs, files in os.walk(user_email_dir):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    if os.path.exists(file_path):
                                        dir_size += os.path.getsize(file_path)
                                        if file.endswith('.eml') or file.endswith('.msg'):
                                            email_count += 1
                            
                            # Copy user emails to temp directory with expected structure
                            account_name = username.replace('@', '_')
                            temp_account_dir = os.path.join(export_dir, account_name)
                            os.makedirs(temp_account_dir, exist_ok=True)
                            
                            # Copy the user's email directory to temp location
                            import shutil
                            shutil.copytree(user_email_dir, temp_account_dir, dirs_exist_ok=True)
                            
                            # Zip the email files
                            zip_size = zip_email_files(username, export_dir)
                            
                            # Clean up temp directory
                            if os.path.exists(temp_account_dir):
                                shutil.rmtree(temp_account_dir)
                            
                            # Use the zip file size as the account total size
                            account_email_count = email_count
                            account_total_size = zip_size if zip_size > 0 else dir_size
                            
                            print(f"已为用户 {username} 创建邮件压缩包，邮件数: {account_email_count}，大小: {account_total_size} 字节")
                            
                        else:
                            print(f"未找到用户 {username} 的邮件目录")
                            account_email_count = 0
                            account_total_size = 0
                    else:
                        print(f"邮件基础目录不存在: {email_base_dir}")
                        account_email_count = 0
                        account_total_size = 0
                        
                except Exception as zip_error:
                    print(f"压缩邮件文件时出错: {zip_error}")
                    traceback.print_exc()
                    account_email_count = 0
                    account_total_size = 0
                
                # Update task detail with actual email count and size
                update_task_detail(detail_id, 'finished', account_email_count, account_total_size, None)
                total_success += 1
                total_all_emails += account_email_count
                total_all_size += account_total_size
                    
            except Exception as e:
                traceback.print_exc()
                update_task_detail(detail_id, 'failed', 0, 0, str(e))
            
            total_processed += 1
        
        # Update main task status with total email count and size
        if total_success == len(accounts):
            update_task_status(task_id, 'finished', None, total_all_emails, total_all_size)
        elif total_success > 0:
            update_task_status(task_id, 'finished', f"Processed {total_success}/{len(accounts)} accounts successfully", total_all_emails, total_all_size)
        else:
            update_task_status(task_id, 'failed', 'All accounts failed to process')
            
    except Exception as e:
        traceback.print_exc()
        update_task_status(task_id, 'failed', str(e))


@app.route('/imap_email', methods=['POST'])
@login_required
def imap_email():
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
    task_id = insert_task('imap_email')
    
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


@app.route('/submit_imap_task', methods=['POST'])
def submit_imap_task():
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
    task_id = insert_task('imap_email')
    
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

    email_domain = email.split('@')[-1].lower() if '@' in email else ''

    # Check if email domain is supported
    # supported_domains = {
    #     'outlook.com', 'gmail.com', 'tutamail.com', 
    #     'murena.io', 'proton.me', 'yahoo.com',
    #     'ymail.com', 'rocketmail.com', 'yahoo.com.cn', 'yahoo.cn',
    # }

    # if email:

    #     if email_domain not in supported_domains:
    #         provider = get_email_provider_type(email)  # 调用函数获取邮箱类型
    #         if "未知" in provider:
    #             return {"error": "不支持的邮箱类型"}, 400


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
