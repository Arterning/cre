# -*- coding: utf-8 -*-

from flask import request, jsonify
import threading
from convert import decode_base64
from mx import get_email_provider_type
from cookie.crawlgmail import list_gmails
from cookie.crawlyahoo import list_yahoo_emails
from database import insert_task


def async_process(task_id, crawl_type, email_accounts, email_cookies, proxy_list=None, user_agent_list=None):
    from cookie import cookie_crawl, token_crawl
    from imap import IMAPEmailDownloader
    from crawl import process_email_accounts
    import traceback
    from database import update_task_status
    
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
            mails = 1
        else:
            raise ValueError(f"Unsupported email domain for {email}. Only Gmail and Yahoo are supported.")
        
        if mails > 0:
            response.append({"email": email_address, "status": "valid"})
        else:
            response.append({"email": email_address, "status": "invalid", "error_message": "cookie 验证不通过"})

    return jsonify({"status": "submitted", "task_id": task_id, "emails": response})