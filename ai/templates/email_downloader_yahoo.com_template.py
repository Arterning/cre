#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮箱下载模板脚本
生成时间: 2025-09-02 23:48:08
原始邮箱: clarkfranze725649@yahoo.com
邮箱域名: yahoo.com

使用方法:
1. 修改下面的邮箱配置信息
2. 运行脚本: python email_downloader_yahoo.com_template.py

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
    """解码邮件头部信息"""
    if s is None:
        return "无主题"
    decoded_parts = decode_header(s)
    decoded_string = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            if encoding:
                try:
                    decoded_string += part.decode(encoding)
                except:
                    try:
                        decoded_string += part.decode('utf-8')
                    except:
                        decoded_string += part.decode('utf-8', errors='ignore')
            else:
                try:
                    decoded_string += part.decode('utf-8')
                except:
                    decoded_string += part.decode('utf-8', errors='ignore')
        else:
            decoded_string += str(part)
    return decoded_string

def get_imap_config(domain):
    """根据域名获取IMAP配置"""
    imap_configs = {
        'gmail.com': ('imap.gmail.com', 993),
        'outlook.com': ('outlook.office365.com', 993),
        'hotmail.com': ('outlook.office365.com', 993),
        'live.com': ('outlook.office365.com', 993),
        'yahoo.com': ('imap.mail.yahoo.com', 993),
        '163.com': ('imap.163.com', 993),
        '126.com': ('imap.126.com', 993),
        'qq.com': ('imap.qq.com', 993),
        'sina.com': ('imap.sina.com', 993),
    }
    
    if domain in imap_configs:
        return imap_configs[domain]
    else:
        # 对于其他域名，尝试通用格式
        return (f'imap.{domain}', 993)

def is_oauth_required(domain):
    """判断是否需要使用授权码"""
    oauth_domains = ['gmail.com', 'outlook.com', 'hotmail.com', 'live.com', 'yahoo.com', '163.com', '126.com', 'qq.com']
    return domain in oauth_domains

def connect_to_imap(email_address, password):
    """连接到IMAP服务器"""
    domain = email_address.split('@')[1]
    imap_server, imap_port = get_imap_config(domain)
    
    print(f"正在连接到 {imap_server}:{imap_port}...")
    
    try:
        # 连接到IMAP服务器
        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        
        # 登录
        print("正在登录...")
        mail.login(email_address, password)
        print("登录成功!")
        
        return mail, domain
    except Exception as e:
        print(f"连接或登录失败: {e}")
        return None, None

def download_emails(mail, email_address, domain):
    """下载所有邮件"""
    try:
        # 选择收件箱
        mail.select('INBOX')
        
        # 搜索所有邮件
        print("正在搜索邮件...")
        status, messages = mail.search(None, 'ALL')
        
        if status != 'OK':
            print("搜索邮件失败")
            return 0
        
        email_ids = messages[0].split()
        total_emails = len(email_ids)
        
        if total_emails == 0:
            print("没有找到邮件")
            return 0
        
        print(f"找到 {total_emails} 封邮件，开始下载...")
        
        # 创建保存目录
        username = email_address.split('@')[0]
        today = datetime.now().strftime('%Y%m%d')
        save_dir = os.path.join('email', domain, username, today)
        os.makedirs(save_dir, exist_ok=True)
        
        downloaded_count = 0
        
        for i, email_id in enumerate(email_ids, 1):
            try:
                # 获取邮件
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                
                if status != 'OK':
                    print(f"获取邮件 {i}/{total_emails} 失败")
                    continue
                
                # 解析邮件
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # 获取邮件主题
                subject = decode_mime_words(email_message.get('Subject', '无主题'))
                subject = clean_filename(subject)
                
                # 如果主题为空或只有空格，使用默认名称
                if not subject or subject.strip() == '':
                    subject = f'邮件_{i}'
                
                # 保存邮件
                filename = f"{subject}.eml"
                filepath = os.path.join(save_dir, filename)
                
                # 如果文件已存在，添加序号
                counter = 1
                original_filepath = filepath
                while os.path.exists(filepath):
                    name, ext = os.path.splitext(original_filepath)
                    filepath = f"{name}_{counter}{ext}"
                    counter += 1
                
                with open(filepath, 'wb') as f:
                    f.write(raw_email)
                
                downloaded_count += 1
                
                # 显示进度
                print(f"下载进度: {i}/{total_emails} ({(i/total_emails)*100:.1f}%) - {subject}")
                
            except Exception as e:
                print(f"下载邮件 {i}/{total_emails} 时出错: {e}")
                continue
        
        print(f"\n下载完成! 成功下载 {downloaded_count} 封邮件到: {save_dir}")
        return downloaded_count
        
    except Exception as e:
        print(f"下载邮件时出错: {e}")
        return 0

def main():
    """主函数"""
    # 邮箱配置
    email_address = "your_email@example.com"  # 已自动替换为提供的凭据
    password = "your_password"  # 请替换为实际的授权码
    
    print("=== 邮件下载工具 ===")
    print(f"邮箱地址: {email_address}")
    
    # 连接到IMAP服务器
    mail, domain = connect_to_imap(email_address, password)
    
    if mail is None:
        print("连接失败，程序退出")
        sys.exit(1)
    
    try:
        # 下载邮件
        downloaded_count = download_emails(mail, email_address, domain)
        
        if downloaded_count > 0:
            print(f"\n✓ 任务完成! 总共成功下载 {downloaded_count} 封邮件")
        else:
            print("\n✗ 没有下载任何邮件")
        
    finally:
        # 关闭连接
        try:
            mail.close()
            mail.logout()
            print("已断开邮箱连接")
        except:
            pass

if __name__ == "__main__":
    main()