#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮箱下载模板脚本
生成时间: 2025-09-03 00:36:26
原始邮箱: boulebraedy@gmx.com
邮箱域名: gmx.com

使用方法:
1. 修改下面的邮箱配置信息
2. 运行脚本: python email_downloader_gmx.com_template.py

注意: 请将下面的占位符替换为实际的邮箱凭据
"""

import imaplib
import email
import os
import re
from datetime import datetime
from email.header import decode_header
import sys

def clean_filename(filename):
    """清理文件名，移除不合法字符"""
    # 移除或替换不合法的文件名字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 限制文件名长度
    if len(filename) > 100:
        filename = filename[:100]
    return filename.strip()

def decode_mime_words(s):
    """解码MIME编码的字符串"""
    if s is None:
        return "No Subject"
    
    try:
        decoded_fragments = decode_header(s)
        decoded_string = ''
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                if encoding:
                    try:
                        decoded_string += fragment.decode(encoding)
                    except:
                        decoded_string += fragment.decode('utf-8', errors='ignore')
                else:
                    decoded_string += fragment.decode('utf-8', errors='ignore')
            else:
                decoded_string += fragment
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
        'yahoo.cn': ('imap.mail.yahoo.com', 993),
        '163.com': ('imap.163.com', 993),
        '126.com': ('imap.126.com', 993),
        'qq.com': ('imap.qq.com', 993),
        'foxmail.com': ('imap.qq.com', 993),
        'gmx.com': ('imap.gmx.com', 993),
        'rambler.ru': ('imap.rambler.ru', 993),
    }
    
    if domain in imap_configs:
        return imap_configs[domain]
    else:
        # 自动推断IMAP服务器
        return (f'imap.{domain}', 993)

def is_oauth_required(domain):
    """判断是否需要使用授权码"""
    oauth_domains = ['gmail.com', 'outlook.com', 'hotmail.com', 'live.com', 'yahoo.com', 'yahoo.cn', '163.com', '126.com', 'qq.com', 'foxmail.com']
    return domain in oauth_domains

def download_emails():
    # 邮箱配置信息
    email_address = "your_email@example.com"  # 直接使用提供的用户名
    password = "your_password"  # 直接使用提供的密码
    
    # 从邮箱地址中提取域名和用户名
    username = email_address.split('@')[0]
    domain = email_address.split('@')[1]
    
    # 获取IMAP配置
    imap_server, imap_port = get_imap_config(domain)
    
    # 创建保存目录
    current_date = datetime.now().strftime('%Y%m%d')
    save_dir = os.path.join('email', domain, username, current_date)
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"邮箱地址: {email_address}")
    print(f"IMAP服务器: {imap_server}:{imap_port}")
    print(f"保存目录: {save_dir}")
    print(f"认证方式: {'授权码' if is_oauth_required(domain) else '密码'}")
    print("-" * 50)
    
    try:
        # 连接到IMAP服务器
        print("正在连接到邮件服务器...")
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        
        # 登录
        print("正在登录...")
        mail.login(email_address, password)
        print("登录成功！")
        
        # 选择收件箱
        mail.select('inbox')
        
        # 搜索所有邮件
        print("正在搜索邮件...")
        status, messages = mail.search(None, 'ALL')
        
        if status != 'OK':
            print("搜索邮件失败！")
            return
            
        email_ids = messages[0].split()
        total_emails = len(email_ids)
        
        if total_emails == 0:
            print("未找到任何邮件。")
            return
            
        print(f"找到 {total_emails} 封邮件，开始下载...")
        print("-" * 50)
        
        downloaded_count = 0
        
        # 下载每封邮件
        for i, email_id in enumerate(email_ids, 1):
            try:
                # 获取邮件
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                
                if status != 'OK':
                    print(f"获取邮件 {i}/{total_emails} 失败")
                    continue
                    
                # 解析邮件
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # 获取邮件主题
                subject = decode_mime_words(email_message['subject']) or f"邮件_{i}"
                subject = clean_filename(subject)
                
                # 保存邮件
                filename = f"{subject}.eml"
                filepath = os.path.join(save_dir, filename)
                
                # 如果文件名重复，添加序号
                counter = 1
                original_filepath = filepath
                while os.path.exists(filepath):
                    name, ext = os.path.splitext(original_filepath)
                    filepath = f"{name}_{counter}{ext}"
                    counter += 1
                
                with open(filepath, 'wb') as f:
                    f.write(email_body)
                
                downloaded_count += 1
                
                # 显示进度
                progress = (i / total_emails) * 100
                print(f"进度: {i}/{total_emails} ({progress:.1f}%) - 已保存: {subject[:50]}{'...' if len(subject) > 50 else ''}")
                
            except Exception as e:
                print(f"下载邮件 {i}/{total_emails} 时出错: {str(e)}")
                continue
        
        # 关闭连接
        mail.close()
        mail.logout()
        
        print("-" * 50)
        print(f"下载完成！")
        print(f"总邮件数: {total_emails}")
        print(f"成功下载: {downloaded_count}")
        print(f"保存位置: {save_dir}")
        
    except imaplib.IMAP4.error as e:
        print(f"IMAP错误: {str(e)}")
        if "authentication failed" in str(e).lower():
            if is_oauth_required(domain):
                print("提示: 该邮箱可能需要使用授权码而不是密码进行登录")
            else:
                print("提示: 请检查用户名和密码是否正确")
        sys.exit(1)
        
    except Exception as e:
        print(f"发生错误: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    download_emails()