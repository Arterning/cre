
from crawlgmail import fetch_gmail_emails
from crawlyahoo import fetch_yahoo_emails
from crawlmurena import fetch_murena_emails
from convert import decode_base64
from mx import get_email_provider_type

def fetch_all_emails_by_cookie(email_cookies):
    total_emails = 0
    total_size = 0
    for account in email_cookies:
        cookies_base64 = account['cookies']
        cookies = decode_base64(cookies_base64)
        # print(f"Decoded cookies for {account['email']}: {cookies}")
        email = account['email']
        proxy = account.get('proxy', None)

        provider = get_email_provider_type(email)
        
        # if gmail
        if "Google Mail" in provider or "Gmail" in provider:
            size, emails = fetch_gmail_emails(email, cookies, proxy)
        # if yahoo
        elif "Yahoo Mail" in provider or "Yahoo" in provider:
            size, emails = fetch_yahoo_emails(email, cookies, proxy)
        # if murena
        elif "Murena Mail" in provider or "Murena" in provider:
            size, emails = fetch_murena_emails(email, cookies, proxy)
        else:
            raise ValueError(f"Unsupported email domain for {email}. Only Gmail and Yahoo are supported.")

        total_emails += emails
        total_size += size

    return total_emails, total_size
