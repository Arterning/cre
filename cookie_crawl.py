
from crawlgmail import fetch_gmail_emails
from crawlyahoo import fetch_yahoo_emails
from crawlmurena import fetch_murena_emails
from convert import decode_base64

def fetch_all_emails_by_cookie(email_cookies):
    total_emails = 0
    total_size = 0
    for account in email_cookies:
        cookies_base64 = account['cookies']
        cookies = decode_base64(cookies_base64)
        # print(f"Decoded cookies for {account['email']}: {cookies}")
        email = account['email']
        proxy = account.get('proxy', None)
        
        # if gmail
        if email.endswith('@gmail.com'):
            size, emails = fetch_gmail_emails(email, cookies, proxy)
        # if yahoo
        elif email.endswith('@yahoo.com') or email.endswith('@ymail.com') or email.endswith('@rocketmail.com') or email.endswith('@yahoo.com.cn') or email.endswith('@yahoo.cn'):
            size, emails = fetch_yahoo_emails(email, cookies, proxy)

        elif email.endswith('@murena.io'):
            size, emails = fetch_murena_emails(email, cookies, proxy)
        else:
            raise ValueError(f"Unsupported email domain for {email}. Only Gmail and Yahoo are supported.")

        total_emails += emails
        total_size += size

    return total_emails, total_size
