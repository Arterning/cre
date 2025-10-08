# -*- coding: utf-8 -*-

from flask import request, jsonify
import threading
from convert import decode_base64
from mx import get_email_provider_type
from cookie.crawlgmail import list_gmails
from cookie.crawlyahoo import list_yahoo_emails
from database import insert_task, capture_task_logs
from imap import process_accounts, process_single_account
from web.login import process_email_accounts, process_email_account
from cookie import cookie_crawl
from api import token_crawl
import traceback
from database import update_task_status


def async_process(task_id, crawl_type, email_accounts, email_cookies, proxy_list=None, user_agent_list=None):
    with capture_task_logs(task_id):
        total_emails = 0
        total_size = 0
        try:
            print(f"开始执行任务 {task_id}，类型: {crawl_type}")
            update_task_status(task_id, 'running')

            if crawl_type == 'cookie':
                print("使用Cookie模式爬取邮件")
                total_emails, total_size = cookie_crawl.fetch_all_emails_by_cookie(task_id, email_accounts)
            if crawl_type == 'token':
                print("使用Token模式爬取邮件")
                total_emails, total_size = token_crawl.fetch_all_emails_by_token(task_id, email_accounts)
            if crawl_type == 'protocol':
                print("使用协议模式爬取邮件")
                total_emails, total_size = async_claude_process(task_id, email_accounts, 2)
            if crawl_type == 'default':
                print("使用默认模式爬取邮件")
                total_emails, total_size = process_email_accounts(
                    task_id,
                    email_accounts,
                    proxy_list=proxy_list,
                    user_agent_list=user_agent_list
                )
            if crawl_type == 'auto' or crawl_type is None:
                print("使用自动模式爬取邮件")
                # 先尝试协议模式
                for account in email_accounts:
                    print(f"自动模式: 尝试协议模式爬取 {account['email']}")
                    is_success, account_email_count, account_total_size = process_single_account(task_id, account, 2)
                    if is_success:
                        total_emails += account_email_count
                        total_size += account_total_size
                    else:
                        print(f"自动模式: 协议模式失败 ({str(e)}), 切换到默认模式")
                        process_email_account(task_id, account, proxy_list, user_agent_list)
               
            print("任务完成, 总邮件数:", total_emails, "总大小:", total_size)
            error = None
            if total_emails == 0:
                error = "没有找到任何邮件，请检查登录信息或 cookies 是否正确。"
                print("警告: 未找到任何邮件")
            update_task_status(task_id=task_id, status='finished', error=error, total_emails=total_emails, total_size=total_size)
            print(f"任务 {task_id} 执行完成")
        except Exception as e:
            print(f"任务 {task_id} 执行失败: {str(e)}")
            traceback.print_exc()
            update_task_status(task_id, 'failed', str(e))


