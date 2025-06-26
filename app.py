from flask import Flask, request, jsonify, send_file
from imap import IMAPEmailDownloader
from crawl import process_email_accounts
import threading
import traceback
import sqlite3
import os
import uuid
import time

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


def async_process(task_id, crawl_type, email_accounts):
    total_emails = 0
    total_size = 0
    try:
        update_task_status(task_id, 'running')
        if crawl_type == 'imap':
            email_downloader = IMAPEmailDownloader()
            total_emails, total_size = email_downloader.process_accounts(email_accounts)
        else:
            total_emails, total_size = process_email_accounts(email_accounts)
            print("任务完成, 总邮件数:", total_emails, "总大小:", total_size)
        update_task_status(task_id=task_id, status='finished', error=None, total_emails=total_emails, total_size=total_size)
    except Exception as e:
        traceback.print_exc()
        update_task_status(task_id, 'failed', str(e))


@app.route("/")
def hello_world():
    return "<p>running!</p>"


@app.route('/submit_emails', methods=['POST'])
def submit_emails():
    data = request.get_json()

    if not data or 'email_accounts' not in data:
        return jsonify({"error": "Missing 'email_accounts' parameter"}), 400

    email_accounts = data['email_accounts']
    crawl_type = data.get('crawl_type', 'default')

    for account in email_accounts:
        if 'email' not in account or 'password' not in account:
            return jsonify({"error": "Each account must include 'email' and 'password'"}), 400

    # 创建任务记录并获取任务 ID
    task_id = insert_task(crawl_type)

    # 启动后台线程处理任务
    thread = threading.Thread(target=async_process, args=(task_id, crawl_type, email_accounts))
    thread.start()

    return jsonify({"status": "submitted", "task_id": task_id})


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

    if not email:
        return {"error": "缺少 email 参数"}, 400

    output_dir="/tmp/outlook_emails/"
    account_name = email.split('@')[0]
    account_dir = os.path.join(output_dir, account_name)
    file_path = os.path.join(output_dir, f"{email.replace('@', '_')}.zip")

    # 拼接文件路径
    #safe_email = email.replace("/", dd"_")  # 简单防止路径注入
    #file_path = f"/tmp/outlook_emails/{safe_email}.zip"

    print("file_path", file_path)

    if not os.path.exists(file_path):
        return {"error": "文件不存在"}, 404

    # 返回文件流供用户下载
    return send_file(file_path, as_attachment=True)



if __name__ == '__main__':
    app.run(debug=True)


# 启动前初始化数据库
init_db()
