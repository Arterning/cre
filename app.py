from flask import Flask, request, jsonify, send_file
from imap import IMAPEmailDownloader
from crawl import process_email_accounts
from token_crawl import fetch_all_emails
from cookie_crawl import fetch_all_emails_by_cookie
from crawlgmail import list_gmails
from crawlyahoo import list_yahoo_emails
from convert import decode_base64
import threading
import traceback
import sqlite3
import os
import uuid
import time
import zipfile


app = Flask(__name__)
DB_PATH = 'tasks.db'


# 初始化数据库（只执行一次）
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            crawl_type TEXT,
            status TEXT,
            total_emails INTEGER DEFAULT 0,
            total_size INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            error TEXT
        )
    ''')
    conn.commit()
    conn.close()


# 插入任务记录
def insert_task(crawl_type):
    task_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO tasks (id, crawl_type, status) VALUES (?, ?, ?)', (task_id, crawl_type, 'pending'))
    conn.commit()
    conn.close()
    return task_id


# 更新任务状态
def update_task_status(task_id, status, error=None, total_emails=0, total_size=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE tasks SET status = ?, error = ?, total_emails = ?, total_size = ? WHERE id = ?', (status, error, total_emails, total_size, task_id))
    conn.commit()
    conn.close()


def async_process(task_id, crawl_type, email_accounts, email_cookies, proxy_list=None, user_agent_list=None):
    total_emails = 0
    total_size = 0
    try:
        update_task_status(task_id, 'running')
        if crawl_type == 'cookie':
            total_emails, total_size = fetch_all_emails_by_cookie(email_cookies)
        if crawl_type == 'token':
            total_emails, total_size = fetch_all_emails(email_accounts)
        if crawl_type == 'imap':
            email_downloader = IMAPEmailDownloader()
            total_emails, total_size = email_downloader.process_accounts(email_accounts)
        if crawl_type == 'default':
            total_emails, total_size = process_email_accounts(
                email_accounts, 
                proxy_list=proxy_list, 
                user_agent_list=user_agent_list
            )
            print("任务完成, 总邮件数:", total_emails, "总大小:", total_size)
        update_task_status(task_id=task_id, status='finished', error=None, total_emails=total_emails, total_size=total_size)
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
    for email in email_cookies:
        mails = 0
        email_address = email['email']
        try :
            cookies = decode_base64(email['cookies'])
        except Exception as e:
            print(f"Failed to decode cookies for {email_address}: {e}")
            response.append({"email": email_address, "status": "invalid", "error_message": "cookie 验证不通过"})
            continue  # 如果解码失败，跳过这个邮箱
        
        if email_address.endswith('@gmail.com'):
            mails = list_gmails(cookies)
        elif email_address.endswith('@yahoo.com'):
            mails = list_yahoo_emails(cookies)
        elif email_address.endswith('@murena.io'):
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
    c.execute('SELECT id, crawl_type, status, total_emails, total_size, created_at, error FROM tasks WHERE id = ?', (task_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return jsonify({
            "task_id": row[0],
            "crawl_type": row[1],
            "status": row[2],
            "total_emails": row[3],
            "total_size": row[4],
            "created_at": row[5],
            "error": row[6]
        })
    else:
        return jsonify({"error": "Task not found"}), 404


@app.route('/download', methods=['GET'])
def download_file():

    email = request.args.get('email')
    anchormailbox = request.args.get('anchormailbox')

    # Check if email domain is supported
    supported_domains = {
        'outlook.com', 'gmail.com', 'tutamail.com', 
        'murena.io', 'proton.me', 'yahoo.com',
    }

    if email:
        email_domain = email.split('@')[-1].lower() if '@' in email else ''

        if email_domain not in supported_domains:
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
