#!/usr/bin/env python3

# -*- coding: utf-8 -*-
"""
邮箱下载模板脚本
生成时间: 2025-09-03 00:38:35
原始邮箱: a-markelov-53576138@rambler.ru
邮箱域名: rambler.ru

使用方法:
1. 修改下面的邮箱配置信息
2. 运行脚本: python email_downloader_rambler.ru_template.py

注意: 请将下面的占位符替换为实际的邮箱凭据
"""

# -*- coding: utf-8 -*-

import imaplib
import email
import os
import re
from datetime import datetime
from email.header import decode_header
import ssl

def clean_filename(filename):
    """清理文件名，移除非法字符"""
    # 移除或替换非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 限制文件名长度
    if len(filename) > 100:
        filename = filename[:100]
    return filename.strip()

def decode_mime_words(s):
    """解码MIME编码的字符串"""
    if not s:
        return "无标题"
    
    try:
        decoded_parts = decode_header(s)
        decoded_string = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    decoded_string += part.decode(encoding)
                else:
                    # 尝试常见编码
                    for enc in ['utf-8', 'gb2312', 'gbk', 'big5']:
                        try:
                            decoded_string += part.decode(enc)
                            break
                        except:
                            continue
                    else:
                        decoded_string += part.decode('utf-8', errors='ignore')
            else:
                decoded_string += str(part)
        return decoded_string
    except:
        return str(s)

def get_imap_config(domain):
    """根据域名获取IMAP配置"""
    imap_configs = {
        'gmail.com': ('imap.gmail.com', 993),
        'outlook.com': ('outlook.office365.com', 993),
        'hotmail.com': ('outlook.office365.com', 993),
        'live.com': ('outlook.office365.com', 993),
        'yahoo.com': ('imap.mail.yahoo.com', 993),
        '163.com': ('imap.163.com', 993),
        'qq.com': ('imap.qq.com', 993),
        'rambler.ru': ('imap.rambler.ru', 993),
    }
    
    return imap_configs.get(domain, (f'imap.{domain}', 993))

def is_oauth_domain(domain):
    """判断域名是否需要使用授权码"""
    oauth_domains = ['gmail.com', 'outlook.com', 'hotmail.com', 'live.com', 'yahoo.com', '163.com', 'qq.com']
    return domain in oauth_domains

def download_emails():
    # 邮箱配置
    email_address = "your_email@example.com"  # 直接使用提供的用户名
    password = "your_password"  # 直接使用提供的密码
    
    # 解析域名
    domain = email_address.split('@')[1]
    username = email_address.split('@')[0]
    
    # 获取IMAP配置
    imap_server, imap_port = get_imap_config(domain)
    
    # 创建保存目录
    current_date = datetime.now().strftime('%Y%m%d')
    save_dir = os.path.join('email', domain, username, current_date)
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"开始连接邮箱: {email_address}")
    print(f"IMAP服务器: {imap_server}:{imap_port}")
    print(f"认证方式: {'授权码' if is_oauth_domain(domain) else '密码'}")
    print(f"邮件保存路径: {save_dir}")
    print("-" * 50)
    
    try:
        # 连接到IMAP服务器
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(imap_server, imap_port, ssl_context=context)
        
        # 登录
        print("正在登录...")
        mail.login(email_address, password)
        print("登录成功！")
        
        # 选择收件箱
        mail.select('INBOX')
        
        # 搜索所有邮件
        print("正在搜索邮件...")
        status, messages = mail.search(None, 'ALL')
        
        if status != 'OK':
            print("搜索邮件失败")
            return
        
        email_ids = messages[0].split()
        total_emails = len(email_ids)
        
        print(f"找到 {total_emails} 封邮件，开始下载...")
        print("-" * 50)
        
        downloaded_count = 0
        
        for i, email_id in enumerate(email_ids, 1):
            try:
                # 获取邮件
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                
                if status != 'OK':
                    print(f"获取邮件 {i} 失败")
                    continue
                
                # 解析邮件
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # 获取邮件主题
                subject = email_message.get('Subject', '无标题')
                subject = decode_mime_words(subject)
                subject = clean_filename(subject)
                
                # 如果主题为空或过短，使用邮件ID
                if not subject or len(subject.strip()) < 1:
                    subject = f"邮件_{email_id.decode()}"
                
                # 构建文件名
                filename = f"{subject}.eml"
                filepath = os.path.join(save_dir, filename)
                
                # 如果文件已存在，添加序号
                counter = 1
                original_filepath = filepath
                while os.path.exists(filepath):
                    name, ext = os.path.splitext(original_filepath)
                    filepath = f"{name}_{counter}{ext}"
                    counter += 1
                
                # 保存邮件
                with open(filepath, 'wb') as f:
                    f.write(raw_email)
                
                downloaded_count += 1
                
                # 显示进度
                progress = (i / total_emails) * 100
                print(f"进度: {i}/{total_emails} ({progress:.1f}%) - 已保存: {filename}")
                
            except Exception as e:
                print(f"处理邮件 {i} 时出错: {str(e)}")
                continue
        
        print("-" * 50)
        print(f"下载完成！")
        print(f"总邮件数: {total_emails}")
        print(f"成功下载: {downloaded_count}")
        print(f"保存路径: {save_dir}")
        
        # 关闭连接
        mail.close()
        mail.logout()
        
    except imaplib.IMAP4.error as e:
        print(f"IMAP错误: {str(e)}")
        if "authentication failed" in str(e).lower():
            print("认证失败，请检查用户名和密码/授权码")
    except Exception as e:
        print(f"连接失败: {str(e)}")

if __name__ == "__main__":
    download_emails()