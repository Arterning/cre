
from .crawlgmail import fetch_gmail_emails
from .crawlyahoo import fetch_yahoo_emails
from .crawlmurena import fetch_murena_emails
from convert import decode_base64
from mx import get_email_provider_type
from database import insert_task_detail, update_task_detail
import traceback

def fetch_all_emails_by_cookie(task_id, email_accounts):
    total_emails = 0
    total_size = 0
    for account in email_accounts:
        email = account['email']
        unique_code = account.get('unique_code')
        limit = account.get('limit', 50)
        detail_id = insert_task_detail(task_id, email, unique_code)
        try:
            params = account.get('params', {})
            cookies_base64 = params.get('cookie', '')
            cookies = decode_base64(cookies_base64)
            # print(f"Decoded cookies for {account['email']}: {cookies}")
            proxy = account.get('proxy', None)

            provider = get_email_provider_type(email)
            
            # if gmail
            if "Google Mail" in provider or "Gmail" in provider:
                size, emails = fetch_gmail_emails(email, cookies, proxy, limit)
            # if yahoo
            elif "Yahoo Mail" in provider or "Yahoo" in provider:
                size, emails = fetch_yahoo_emails(email, cookies, proxy, limit)
            # if murena
            elif "Murena Mail" in provider or "Murena" in provider:
                size, emails = fetch_murena_emails(email, cookies, proxy, limit)
            else:
                raise ValueError(f"Unsupported email domain for {email}. Only Gmail and Yahoo are supported.")

            total_emails += emails
            total_size += size
            update_task_detail(detail_id, 'finished', emails, size)
        except Exception as e:
            traceback.print_exc()
            update_task_detail(detail_id, 'failed', error=str(e))

    return total_emails, total_size
