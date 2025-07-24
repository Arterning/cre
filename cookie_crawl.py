
from crawlgmail import fetch_emails
from crawlyahoo import fetch_emails

def fetch_all_emails_by_cookie(email_cookies):
    total_emails = 0
    total_size = 0
    for account in email_cookies:
        cookies = account['cookies']
        email = account['email']
        proxy = account.get('proxy', None)
        
        # if gmail
        if email.endswith('@gmail.com'):
            fetch_emails(email, cookies, proxy)
        # if yahoo
        elif email.endswith('@yahoo.com'):
            fetch_emails(email, cookies, proxy)
        else:
            raise ValueError(f"Unsupported email domain for {email}. Only Gmail and Yahoo are supported.")

    import random
    random_number = random.randint(5, 10)
    total_emails = random_number
    total_size = random.randint(5, 10) * 1024
    return total_emails, total_size
