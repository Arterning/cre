# -*- coding: utf-8 -*-

from flask import request, jsonify
import threading
import traceback
import os
import shutil
from ai import claude_client
from utils import zip_email_files
from database import insert_task, update_task_status, insert_task_detail, update_task_detail

def process_single_account(task_id, account, max_attempts):
    username = account.get('username', account.get('email'))
    password = account['password']
    unique_code = account.get('unique_code')
    
    # Create task detail record for this account
    detail_id = insert_task_detail(task_id, username, unique_code, 'imap')
    
    account_email_count = 0
    account_total_size = 0
    is_success = False
    
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
        update_task_detail(detail_id, 'finished', account_email_count, account_total_size, None, 'imap', 'success')
        is_success = True
            
    except Exception as e:
        traceback.print_exc()
        update_task_detail(detail_id, 'failed', 0, 0, str(e), 'imap', 'failed')
    
    return is_success, account_email_count, account_total_size


def process_accounts(task_id, accounts, max_attempts):
    total_processed = 0
    total_success = 0
    total_all_emails = 0
    total_all_size = 0
    
    try:
        update_task_status(task_id, 'running')
        
        for account in accounts:
            # 调用处理单个账号的方法
            is_success, email_count, size = process_single_account(task_id, account, max_attempts)
            
            if is_success:
                total_success += 1
                total_all_emails += email_count
                total_all_size += size
                
            total_processed += 1
        
        # Update main task status with total email count and size
        if total_success == len(accounts):
            update_task_status(task_id, 'finished', None, total_all_emails, total_all_size)
        elif total_success > 0:
            update_task_status(task_id, 'finished', f"Processed {total_success}/{len(accounts)} accounts successfully", total_all_emails, total_all_size)
        else:
            update_task_status(task_id, 'failed', 'All accounts failed to process')
        
        return total_all_emails, total_all_size
            
    except Exception as e:
        traceback.print_exc()
        update_task_status(task_id, 'failed', str(e))
        return 0, 0


