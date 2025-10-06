import sqlite3
import uuid
import time
import sys
import io
from contextlib import contextmanager

DB_PATH = 'tasks.db'

class TaskLogCapture:
    def __init__(self, task_id):
        self.task_id = task_id
        self.previous_stdout = None

    def write(self, text):
        # 1. 先传递给下一级（可能是LogCapture或原始stdout）
        if self.previous_stdout:
            self.previous_stdout.write(text)

        # 2. 处理自己的逻辑（写入数据库）
        if text.strip():
            append_task_log(self.task_id, text.rstrip())

    def flush(self):
        if self.previous_stdout and hasattr(self.previous_stdout, 'flush'):
            self.previous_stdout.flush()

    def start_capture(self):
        self.previous_stdout = sys.stdout
        sys.stdout = self

    def stop_capture(self):
        if self.previous_stdout:
            sys.stdout = self.previous_stdout

    def __enter__(self):
        self.start_capture()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_capture()

@contextmanager
def capture_task_logs(task_id):
    capture = TaskLogCapture(task_id)
    try:
        capture.start_capture()
        yield capture
    finally:
        capture.stop_capture()

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            unique_code TEXT,
            crawl_type TEXT,
            status TEXT,
            total_emails INTEGER DEFAULT 0,
            total_size INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            error TEXT,
            logs TEXT DEFAULT ''
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS task_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            unique_code TEXT,
            email TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            status TEXT,
            email_count INTEGER DEFAULT 0,
            total_size INTEGER DEFAULT 0,
            error TEXT,
            crawl_type TEXT,
            crawl_status TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            server_address TEXT,
            protocol_type TEXT,
            port INTEGER,
            type TEXT DEFAULT 'default',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            api_address TEXT,
            login_address TEXT,
            redirect_address TEXT,
            web_dom TEXT,
            UNIQUE (name)
        )
    ''')
    conn.commit()
    conn.close()

def insert_task(crawl_type, unique_code=None):
    task_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('INSERT INTO tasks (id, crawl_type, status, unique_code) VALUES (?, ?, ?, ?)', (task_id, crawl_type, 'pending', unique_code))
    conn.commit()
    conn.close()
    return task_id

def update_task_status(task_id, status, error=None, total_emails=0, total_size=0):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('UPDATE tasks SET status = ?, error = ?, total_emails = ?, total_size = ? WHERE id = ?', (status, error, total_emails, total_size, task_id))
    conn.commit()
    conn.close()

def append_task_log(task_id, log_content):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()

    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    formatted_log = f"[{timestamp}] {log_content}"

    c.execute('SELECT logs FROM tasks WHERE id = ?', (task_id,))
    result = c.fetchone()

    if result:
        existing_logs = result[0] or ''
        new_logs = existing_logs + '\n' + formatted_log if existing_logs else formatted_log
        c.execute('UPDATE tasks SET logs = ? WHERE id = ?', (new_logs, task_id))
        conn.commit()

    conn.close()

def insert_task_detail(task_id, email, unique_code=None, crawl_type=None):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    start_time = time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute('INSERT INTO task_details (task_id, email, start_time, status, unique_code, crawl_type) VALUES (?, ?, ?, ?, ?, ?)',
              (task_id, email, start_time, 'running', unique_code, crawl_type))
    detail_id = c.lastrowid
    conn.commit()
    conn.close()
    return detail_id

def update_task_detail(detail_id, status, email_count=0, total_size=0, error=None, crawl_type=None, crawl_status=None):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    end_time = time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute('UPDATE task_details SET status = ?, email_count = ?, total_size = ?, error = ?, end_time = ?, crawl_type = ?, crawl_status = ? WHERE id = ?',
              (status, email_count, total_size, error, end_time, crawl_type, crawl_status, detail_id))
    conn.commit()
    conn.close()


def get_tasks_paginated(page=1, per_page=10):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    # Get total count
    c.execute('SELECT COUNT(*) FROM tasks')
    total = c.fetchone()[0]
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    # Get tasks with pagination
    c.execute('''
        SELECT id, unique_code, crawl_type, status, total_emails, total_size, created_at, error, logs
        FROM tasks
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    ''', (per_page, offset))
    
    tasks = []
    for row in c.fetchall():
        tasks.append({
            'id': row[0],
            'unique_code': row[1],
            'crawl_type': row[2],
            'status': row[3],
            'total_emails': row[4],
            'total_size': row[5],
            'created_at': row[6],
            'error': row[7],
            'logs': row[8]
        })
    
    conn.close()
    
    return {
        'tasks': tasks,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
        'has_prev': page > 1,
        'has_next': page * per_page < total,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page * per_page < total else None
    }


def get_task_statistics():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM tasks')
    total_tasks = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('finished',))
    completed_tasks = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('running',))
    running_tasks = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('failed',))
    failed_tasks = c.fetchone()[0]
    
    conn.close()
    
    return {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'running_tasks': running_tasks,
        'failed_tasks': failed_tasks
    }


def get_task_details(task_id):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''
        SELECT id, email, start_time, end_time, status, email_count, total_size, error,
        crawl_type, crawl_status
        FROM task_details 
        WHERE task_id = ? 
        ORDER BY start_time DESC
    ''', (task_id,))
    
    details = []
    for row in c.fetchall():
        details.append({
            'id': row[0],
            'email': row[1],
            'start_time': row[2],
            'end_time': row[3],
            'status': row[4],
            'email_count': row[5],
            'total_size': row[6],
            'error': row[7],
            'crawl_type': row[8],
            'crawl_status': row[9]
        })
    
    conn.close()
    return details


def get_templates():
    """获取所有模板列表"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        SELECT name, path, server_address, protocol_type, port, type, created_at, updated_at, api_address, login_address, redirect_address, web_dom
        FROM templates
        ORDER BY name
    ''')
    
    templates = []
    for row in c.fetchall():
        templates.append({
            'name': row[0],
            'path': row[1],
            'server_address': row[2],
            'protocol_type': row[3],
            'port': row[4],
            'type': row[5],
            'created_at': row[6],
            'updated_at': row[7],
            'api_address': row[8],
            'login_address': row[9],
            'redirect_address': row[10],
            'web_dom': row[11]
        })
    
    conn.close()
    return templates


def get_template_by_name(name):
    """根据名称获取模板"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        SELECT name, path, server_address, protocol_type, port, type, created_at, updated_at, api_address, login_address, redirect_address, web_dom
        FROM templates
        WHERE name = ?
    ''', (name,))
    
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            'name': row[0],
            'path': row[1],
            'server_address': row[2],
            'protocol_type': row[3],
            'port': row[4],
            'type': row[5],
            'created_at': row[6],
            'updated_at': row[7],
            'api_address': row[8],
            'login_address': row[9],
            'redirect_address': row[10],
            'web_dom': row[11]
        }
    return None


def insert_template(name, path, server_address=None, protocol_type=None, port=None, type=None, api_address=None, login_address=None, redirect_address=None, web_dom=None):
    """插入新模板"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute(
            'INSERT INTO templates (name, path, server_address, protocol_type, port, type, api_address, login_address, redirect_address, web_dom) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (name, path, server_address, protocol_type, port, type, api_address, login_address, redirect_address, web_dom)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # 处理名称重复的情况
        return False
    finally:
        conn.close()


def update_template(name, path=None, server_address=None, protocol_type=None, port=None, type=None, api_address=None, login_address=None, redirect_address=None, web_dom=None):
    """更新模板信息"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    
    # 构建更新语句
    fields = []
    params = []
    
    if path is not None:
        fields.append('path = ?')
        params.append(path)
    if server_address is not None:
        fields.append('server_address = ?')
        params.append(server_address)
    if protocol_type is not None:
        fields.append('protocol_type = ?')
        params.append(protocol_type)
    if port is not None:
        fields.append('port = ?')
        params.append(port)
    if type is not None:
        fields.append('type = ?')
        params.append(type)
    if api_address is not None:
        fields.append('api_address = ?')
        params.append(api_address)
    if login_address is not None:
        fields.append('login_address = ?')
        params.append(login_address)
    if redirect_address is not None:
        fields.append('redirect_address = ?')
        params.append(redirect_address)
    if web_dom is not None:
        fields.append('web_dom = ?')
        params.append(web_dom)
    
    # 总是更新更新时间
    fields.append('updated_at = CURRENT_TIMESTAMP')
    params.append(name)
    
    if fields:
        sql = f'UPDATE templates SET {', '.join(fields)} WHERE name = ?'
        c.execute(sql, params)
        conn.commit()
    
    conn.close()


def delete_template(name):
    """删除模板"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('DELETE FROM templates WHERE name = ?', (name,))
    affected_rows = c.rowcount
    conn.commit()
    conn.close()
    return affected_rows > 0
