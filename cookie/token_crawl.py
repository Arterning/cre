from database import insert_task_detail, update_task_detail
from .proton import download_emails
from .outlook import fetch_emails
import traceback


def fetch_all_emails_by_token(task_id, email_accounts):
    total_emails = 0
    total_size = 0
    for account in email_accounts:
        email = account['email']
        unique_code = account.get('unique_code')
        params = account.get('params', {})
        detail_id = insert_task_detail(task_id, email, unique_code)
        try:
            if 'outlook.com' in email:
                emails_count, size = fetch_emails(email, params)
                total_emails += emails_count
                total_size += size
            if 'proton' in email:
                emails_count, size = download_emails(email, params, 50)
                total_emails += emails_count
                total_size += size
            update_task_detail(detail_id, 'finished', emails_count, size)
        except Exception as e:
            traceback.print_exc()
            update_task_detail(detail_id, 'failed', error=str(e))
    return total_emails, total_size