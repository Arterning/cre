
from .crawlgmail import fetch_gmail_emails
from .crawlyahoo import fetch_yahoo_emails
from .crawlmurena import fetch_murena_emails
from convert import decode_base64
from mx import get_email_provider_type
from database import insert_task_detail, update_task_detail
import traceback

def fetch_single_account_by_cookie(task_id, account):
    """
    处理单个账号的Cookie邮件抓取
    
    Args:
        task_id: 任务ID
        account: 账号信息字典，包含email, unique_code, params等字段
        
    Returns:
        tuple: (emails_count, size, is_success)
            emails_count: 抓取的邮件数量
            size: 抓取的邮件总大小
            is_success: 是否抓取成功
    """
    email = account['email']
    unique_code = account.get('unique_code')
    limit = account.get('limit', 50)
    detail_id = insert_task_detail(task_id, email, unique_code)
    
    try:
        params = account.get('params', {})
        cookies_base64 = params.get('cookie', '')
        cookies = decode_base64(cookies_base64)
        proxy = account.get('proxy', None)
        
        provider = get_email_provider_type(email)
        
        # 根据邮箱提供商类型调用对应的抓取函数
        if "Google Mail" in provider or "Gmail" in provider:
            size, emails = fetch_gmail_emails(email, cookies, proxy, limit)
        elif "Yahoo Mail" in provider or "Yahoo" in provider:
            size, emails = fetch_yahoo_emails(email, cookies, proxy, limit)
        elif "Murena Mail" in provider or "Murena" in provider:
            size, emails = fetch_murena_emails(email, cookies, proxy, limit)
        else:
            raise ValueError(f"Unsupported email domain for {email}. Only Gmail, Yahoo and Murena are supported.")
        
        # 更新任务详情
        update_task_detail(
            detail_id, 'finished', emails, size, None, 'cookie', 'login success')
        return emails, size, True
        
    except Exception as e:
        traceback.print_exc()
        update_task_detail(
            detail_id, 'failed', error=str(e), crawl_type='cookie', crawl_status='login failed')
        return 0, 0, False

def fetch_all_emails_by_cookie(task_id, email_accounts):
    """
    批量处理多个账号的Cookie邮件抓取
    
    Args:
        task_id: 任务ID
        email_accounts: 账号信息列表
        
    Returns:
        tuple: (total_emails, total_size)
            total_emails: 所有账号抓取的邮件总数量
            total_size: 所有账号抓取的邮件总大小
    """
    total_emails = 0
    total_size = 0
    for account in email_accounts:
        emails, size, is_success = fetch_single_account_by_cookie(task_id, account)
        if is_success:
            total_emails += emails
            total_size += size

    return total_emails, total_size
