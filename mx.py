import dns.resolver
from typing import Optional, List

def get_mx_records(domain: str) -> Optional[List[str]]:
    """
    获取指定域名的MX记录
    
    :param domain: 邮箱域名部分（如gmail.com）
    :return: MX记录列表或None（如果查询失败）
    """
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        return [str(mx.exchange).rstrip('.') for mx in mx_records]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return None

def get_email_provider_type(email: str) -> str:
    """
    根据邮箱地址判断其服务提供商类型
    
    :param email: 邮箱地址
    :return: 服务商类型字符串
    """
    if '@' not in email:
        return "无效的邮箱地址"
    
    domain = email.split('@')[-1].lower()
    
    # 常见邮箱服务商直接判断
    common_providers = {
        'gmail.com': 'Google Mail',
        'outlook.com': 'Microsoft Outlook',
        'hotmail.com': 'Microsoft Hotmail',
        'yahoo.com': 'Yahoo Mail',
        'qq.com': 'QQ Mail',
        '163.com': '163 Mail',
        '126.com': '126 Mail',
        'sina.com': 'Sina Mail',
        'icloud.com': 'Apple iCloud Mail',
        'aol.com': 'AOL Mail',
        'protonmail.com': 'ProtonMail',
        'zoho.com': 'Zoho Mail'
    }
    
    if domain in common_providers:
        return common_providers[domain]
    
    # 获取MX记录进行判断
    mx_records = get_mx_records(domain)
    if not mx_records:
        return "未知邮箱服务商 (无MX记录)"
    
    # 根据MX记录判断服务商
    mx_str = ' '.join(mx_records).lower()
    
    if 'google' in mx_str or 'gmail' in mx_str:
        return 'Google Mail (自定义域名)'
    elif 'outlook' in mx_str or 'microsoft' in mx_str or 'hotmail' in mx_str:
        return 'Microsoft Exchange/Outlook (自定义域名)'
    elif 'yahoo' in mx_str:
        return 'Yahoo Mail (自定义域名)'
    elif 'qq' in mx_str:
        return 'QQ Mail (自定义域名)'
    elif '163' in mx_str or '126' in mx_str or 'netease' in mx_str:
        return '网易系列邮箱 (自定义域名)'
    elif 'zimbra' in mx_str:
        return 'Zimbra邮件服务器'
    elif 'mxbiz' in mx_str or 'exmail' in mx_str:
        return '腾讯企业邮箱'
    elif 'qiye.163' in mx_str:
        return '网易企业邮箱'
    elif 'mailcontrol' in mx_str:
        return 'Amazon WorkMail'
    elif 'protection.outlook' in mx_str:
        return 'Microsoft 365/Exchange Online'
    elif 'mail.ecloud' in mx_str:
        return 'Murena Mail (eCloud Mail)'
    else:
        return f"未知邮箱服务商 (MX: {', '.join(mx_records)})"


# 示例使用
if __name__ == '__main__':
    emails = [
        'user@gmail.com',
        'user@yahoo.com',
        'user@ymail.com',
        'user@rocketmail.com',
        'user@yahoo.com.cn',
        'user@yahoo.cn',
        'user@outlook.com',
        'user@qq.com',
        'user@protonmail.com',
        'user@@murena.io',
        'user@company.com',  # 假设这是使用Google Workspace的自定义域名
        'user@example.org',  # 假设这是未知的邮箱服务
        'invalid-email'
    ]
    
    for email in emails:
        provider = get_email_provider_type(email)
        print(f"{email}: {provider}")