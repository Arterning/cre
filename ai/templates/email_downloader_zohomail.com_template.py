#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮箱下载模板脚本
生成时间: 2025-09-03 00:26:46
原始邮箱: hgdbtd@zohomail.com
邮箱域名: zohomail.com

使用方法:
1. 修改下面的邮箱配置信息
2. 运行脚本: python email_downloader_zohomail.com_template.py

注意: 请将下面的占位符替换为实际的邮箱凭据
"""

import imaplib
import email
import os
import re
from datetime import datetime
import ssl

def sanitize_filename(filename):
    """清理文件名，移除不合法字符"""
    # 移除或替换不合法的文件名字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # 限制文件名长度
    if len(filename) > 100:
        filename = filename[:100]
    return filename.strip()

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
        'zohomail.com': ('imap.zoho.com', 993),
        'zoho.com': ('imap.zoho.com', 993),
    }
    
    if domain in imap_configs:
        return imap_configs[domain]
    else:
        # 对于其他域名，尝试标准格式
        return (f'imap.{domain}', 993)

def is_auth_code_required(domain):
    """判断是否需要授权码"""
    auth_code_domains = [
        'gmail.com', 'outlook.com', 'hotmail.com', 'live.com',
        'yahoo.com', 'yahoo.cn', '163.com', '126.com', 'qq.com'
    ]
    return domain in auth_code_domains

def download_emails():
    # 邮箱配置
    email_address = "your_email@example.com"  # 已自动替换为提供的凭据
    password = "your_password"  # 请替换为实际密码
    
    # 提取域名和用户名
    username = email_address.split('@')[0]
    domain = email_address.split('@')[1]
    
    # 获取IMAP配置
    imap_server, imap_port = get_imap_config(domain)
    
    # 创建保存目录
    current_date = datetime.now().strftime('%Y%m%d')
    save_dir = f'email/{domain}/{username}/{current_date}'
    os.makedirs(save_dir, exist_ok=True)
    
    print(f"开始连接邮箱: {email_address}")
    print(f"IMAP服务器: {imap_server}:{imap_port}")
    print(f"保存路径: {save_dir}")
    
    auth_method = "授权码" if is_auth_code_required(domain) else "密码"
    print(f"认证方式: {auth_method}")
    
    try:
        # 连接IMAP服务器
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(imap_server, imap_port, ssl_context=context)
        
        # 登录
        print("正在登录...")
        mail.login(email_address, password)
        print("登录成功!")
        
        # 选择收件箱
        mail.select('INBOX')
        
        # 搜索所有邮件
        print("正在搜索邮件...")
        status, messages = mail.search(None, 'ALL')
        
        if status != 'OK':
            print("搜索邮件失败")
            return
        
        # 获取邮件ID列表
        email_ids = messages[0].split()
        total_emails = len(email_ids)
        
        print(f"找到 {total_emails} 封邮件，开始下载...")
        
        downloaded_count = 0
        
        for i, email_id in enumerate(email_ids, 1):
            try:
                # 获取邮件
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                
                if status != 'OK':
                    print(f"获取第 {i} 封邮件失败")
                    continue
                
                # 解析邮件
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # 获取邮件主题
                subject = email_message.get('Subject', f'No_Subject_{email_id.decode()}')
                if subject:
                    # 解码主题
                    subject = email.header.decode_header(subject)[0][0]
                    if isinstance(subject, bytes):
                        subject = subject.decode('utf-8', errors='ignore')
                else:
                    subject = f'No_Subject_{email_id.decode()}'
                
                # 清理文件名
                filename = sanitize_filename(subject)
                if not filename:
                    filename = f'Email_{email_id.decode()}'
                
                # 保存邮件
                file_path = os.path.join(save_dir, f'{filename}.eml')
                
                # 如果文件名重复，添加序号
                counter = 1
                original_file_path = file_path
                while os.path.exists(file_path):
                    name, ext = os.path.splitext(original_file_path)
                    file_path = f'{name}_{counter}{ext}'
                    counter += 1
                
                with open(file_path, 'wb') as f:
                    f.write(raw_email)
                
                downloaded_count += 1
                
                # 显示进度
                progress = (i / total_emails) * 100
                print(f"进度: {i}/{total_emails} ({progress:.1f}%) - 已下载: {filename[:50]}...")
                
            except Exception as e:
                print(f"处理第 {i} 封邮件时出错: {str(e)}")
                continue
        
        # 关闭连接
        mail.close()
        mail.logout()
        
        print(f"\n下载完成!")
        print(f"总邮件数: {total_emails}")
        print(f"成功下载: {downloaded_count}")
        print(f"保存路径: {save_dir}")
        
        if downloaded_count < total_emails:
            print(f"跳过邮件: {total_emails - downloaded_count}")
        
    except imaplib.IMAP4.error as e:
        print(f"IMAP错误: {str(e)}")
        print("可能的原因:")
        print("1. 用户名或密码错误")
        print("2. 需要启用IMAP功能")
        print("3. 需要使用应用专用密码而非普通密码")
        
    except Exception as e:
        print(f"执行失败: {str(e)}")

if __name__ == "__main__":
    download_emails()