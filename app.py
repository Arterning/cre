# -*- coding: utf-8 -*-

import sys
import io
import threading
import traceback
import sqlite3
import os
import uuid
import time
import zipfile
from collections import deque
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_file, render_template, redirect, url_for, session, flash
from crawl import process_email_accounts

from cookie import cookie_crawl, token_crawl
from cookie.crawlgmail import list_gmails
from cookie.crawlyahoo import list_yahoo_emails
from convert import decode_base64
from mx import get_email_provider_type
from database import init_db, insert_task, update_task_status, insert_task_detail, update_task_detail, get_tasks_paginated, get_task_statistics, get_task_details, DB_PATH
from ai import claude_client
from utils import zip_email_files
from dotenv import load_dotenv
from functools import wraps
from submit_emails_api import submit_emails
from submit_emails_api import async_process
from template_routes import register_template_routes

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# 日志捕获系统
class LogCapture:
    def __init__(self, max_lines=1000):
        self.max_lines = max_lines
        self.logs = deque(maxlen=max_lines)
        self.original_stdout = sys.stdout

    def write(self, message):
        # 写入原始输出
        self.original_stdout.write(message)
        self.original_stdout.flush()

        # 捕获非空行
        message = message.strip()
        if message:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.logs.append(f"[{timestamp}] {message}")

    def flush(self):
        self.original_stdout.flush()

    def get_logs(self):
        return list(self.logs)

# 初始化日志捕获
log_capture = LogCapture()
sys.stdout = log_capture


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def api_key_or_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in (web interface)
        if 'logged_in' in session:
            return f(*args, **kwargs)

        # Check API key (third-party access)
        api_key = request.headers.get('X-API-Key')
        expected_key = os.environ.get('API_KEY')

        if api_key and expected_key and api_key == expected_key:
            return f(*args, **kwargs)

        # Neither login nor valid API key
        return jsonify({
            'success': False,
            'error': 'Invalid API key'
        }), 401

    return decorated_function




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

        # Get task info including logs
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT logs FROM tasks WHERE id = ?', (task_id,))
        result = c.fetchone()
        conn.close()

        task_info = {
            'logs': result[0] if result and result[0] else None
        }

        return jsonify({
            'success': True,
            'details': details,
            'task_info': task_info
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
def submit_emails_route():
    return submit_emails()


@app.route('/task_status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, unique_code, crawl_type, status, total_emails, total_size, created_at, error, logs FROM tasks WHERE id = ?', (task_id,))
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
        "logs": row[8],
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




@app.route('/imap_email', methods=['POST'])
@login_required
def imap_email_route():
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
    thread = threading.Thread(target=async_process, args=(
        task_id,
        'imap',
        accounts, 
        None,
        None,
        None
    ))
    thread.start()
    
    return jsonify({
        "status": "submitted",
        "task_id": task_id,
        "accounts_count": len(accounts),
        "max_attempts": max_attempts
    })



    
# 注册模板路由
register_template_routes(app, login_required, api_key_or_login_required)


@app.route('/api/logs', methods=['GET'])
@login_required
def api_get_logs():
    """获取运行日志"""
    try:
        logs = log_capture.get_logs()
        return jsonify({
            'success': True,
            'logs': logs,
            'count': len(logs)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/logs')
@login_required
def logs():
    """运行日志页面"""
    return render_template('logs.html')


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
