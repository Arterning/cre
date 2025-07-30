import sqlite3
import uuid
import time

DB_PATH = 'tasks.db'

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
            error TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS task_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            email TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            status TEXT,
            email_count INTEGER DEFAULT 0,
            total_size INTEGER DEFAULT 0,
            error TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks (id)
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

def insert_task_detail(task_id, email):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    start_time = time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute('INSERT INTO task_details (task_id, email, start_time, status) VALUES (?, ?, ?, ?)',
              (task_id, email, start_time, 'running'))
    detail_id = c.lastrowid
    conn.commit()
    conn.close()
    return detail_id

def update_task_detail(detail_id, status, email_count=0, total_size=0, error=None):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    end_time = time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute('UPDATE task_details SET status = ?, email_count = ?, total_size = ?, error = ?, end_time = ? WHERE id = ?',
              (status, email_count, total_size, error, end_time, detail_id))
    conn.commit()
    conn.close()
