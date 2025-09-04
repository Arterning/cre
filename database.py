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
            unique_code TEXT,
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

def insert_task_detail(task_id, email, unique_code=None):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    start_time = time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute('INSERT INTO task_details (task_id, email, start_time, status, unique_code) VALUES (?, ?, ?, ?, ?)',
              (task_id, email, start_time, 'running', unique_code))
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
        SELECT id, unique_code, crawl_type, status, total_emails, total_size, created_at, error
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
            'error': row[7]
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
    
    c.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('completed',))
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
        SELECT id, email, start_time, end_time, status, email_count, total_size, error
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
            'error': row[7]
        })
    
    conn.close()
    return details
