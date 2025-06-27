from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
import traceback
import shutil
import zipfile
import argparse
from datetime import datetime


def create_directory(path):
    """创建目录，如果目录不存在"""
    if not os.path.exists(path):
        os.makedirs(path)


def process_email_account(email, password, output_dir, proxy=None, user_agent=None):
    """处理单个邮箱账号的邮件下载"""
    account_name = email.split('@')[0]
    account_dir = os.path.join(output_dir, account_name)
    create_directory(account_dir)

    # 配置 Chrome 选项
    chrome_options = Options()
    chrome_options.add_argument("--lang=zh-CN")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # 设置用户代理
    if user_agent:
        chrome_options.add_argument(f"user-agent={user_agent}")
    else:
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/137.0.0.0 Safari/537.36"
        )

    # 设置代理
    if proxy:
        if proxy.startswith('socks5://'):
            # 处理带认证的socks5代理
            if '@' in proxy:
                # 格式: socks5://username:password@host:port
                proxy_parts = proxy.split('@')
                auth_part = proxy_parts[0].replace('socks5://', '')
                username, password_proxy = auth_part.split(':')
                host_port = proxy_parts[1]
                chrome_options.add_argument(f'--proxy-server=socks5://{host_port}')
                chrome_options.add_argument(f'--proxy-auth={username}:{password_proxy}')
            else:
                # 格式: socks5://host:port
                host_port = proxy.replace('socks5://', '')
                chrome_options.add_argument(f'--proxy-server=socks5://{host_port}')
        else:
            # 处理http/https代理
            chrome_options.add_argument(f'--proxy-server={proxy}')
            
            # 运行时修改代理
            os.environ['HTTP_PROXY'] = f'http://{proxy}'
            os.environ['HTTPS_PROXY'] = f'http://{proxy}'


    # 设置下载参数
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": account_dir,
        "download.prompt_for_download": False,
        "safebrowsing.enabled": True,
        "safebrowsing.disable_download_protection": False,
        "intl.accept_languages": "zh-CN,zh"
    })

    # 启动 Chrome 浏览器
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        print(f"正在处理邮箱账号: {email}")
        driver.get("https://outlook.office.com/mail/")

        # 登录流程
        email_field = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input#i0116"))
        )
        email_field.clear()
        email_field.send_keys(email)

        next_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input#idSIButton9"))
        )
        time.sleep(2)
        next_button.click()

        password_field = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input#passwordEntry"))
        )
        password_field.clear()
        password_field.send_keys(password)
        time.sleep(1)

        sign_in_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='primaryButton']"))
        )
        sign_in_button.click()

        # 处理"是否保持登录"弹窗
        try:
            no_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='secondaryButton']"))
            )
            no_button.click()
        except:
            print("'保持登录'提示未出现")

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main']")))
        print(f"成功登录邮箱: {email}")

        # 尝试开始新会话
        try:
            new_session = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div#newSessionLink"))
            )
            new_session.click()
            print("新会话已开始")
        except:
            print("未找到新会话链接")

        time.sleep(3)
        print("开始邮件下载流程...")

        # 检查收件箱是否有邮件
        try:
            wait.until(EC.presence_of_element_located((By.XPATH,
                                                       "//div[contains(@aria-checked, 'false')]/ancestor::div[contains(@style, 'top') and contains(@style, 'height')]"
                                                       )))
            print("收件箱中找到了邮件")
        except:
            print("收件箱中没有邮件")
            return 0

        # 开始处理邮件
        first_email = wait.until(
            EC.presence_of_element_located((By.XPATH,
                                            "//div[contains(@aria-checked, 'false')]/ancestor::div[contains(@style, 'top') and contains(@style, 'height')]"
                                            ))
        )
        current_style = first_email.get_attribute("style")
        print(f"First email style: {current_style}")
        email_count = 0

        while True:
            try:
                # 点击打开邮件
                try:
                    email_div = driver.find_element(
                        By.XPATH,
                        f"//div[contains(@style, '{current_style}')]//div[contains(@class, 'IjzWp XG5Jd gy2aJ Ejrkd lME98')]"
                    )
                    email_div.click()
                    time.sleep(1)
                except Exception as e:
                    print(f"无法点击邮件: {str(e)}")
                    break

                # 点击更多选项
                try:
                    more_options = wait.until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, ".ms-Button.ms-Button--commandBar.ms-Button--hasMenu"))
                    )
                    more_options.click()
                    time.sleep(0.5)
                except:
                    print("未找到更多选项按钮")
                    break

                # 点击下载按钮
                try:
                    download_button = wait.until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, "button[aria-label='下载'], button[aria-label='download']"))
                    )
                    download_button.click()
                    time.sleep(1)
                except:
                    print("未找到下载按钮")
                    break

                # 选择EML格式下载
                try:
                    eml_button = wait.until(
                        EC.element_to_be_clickable((By.XPATH,
                                                    "//button[(contains(translate(@aria-label, 'DOWNLOAD下载', 'download下载'), '下载') or "
                                                    "contains(translate(@aria-label, 'DOWNLOAD下载', 'download下载'), 'download')) and "
                                                    "(contains(translate(@aria-label, 'EML', 'eml'), 'eml'))]"
                                                    ))
                    )
                    eml_button.click()
                    print("正在下载邮件为EML格式...")
                    time.sleep(2)
                    email_count += 1
                except:
                    print("未找到EML下载选项")
                    break

                # 关闭邮件视图
                try:
                    close_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Close']")
                    close_button.click()
                    time.sleep(1)
                except:
                    pass

                # 转到下一封邮件
                try:
                    print("处理下一封邮件")
                    next_email = driver.find_element(
                        By.XPATH, f"//div[contains(@style, '{current_style}')]/following-sibling::div[1]"
                    )
                    current_style = next_email.get_attribute("style")
                    print(f"Next email style: {current_style}")
                    time.sleep(1)
                except:
                    print("没有更多邮件需要下载")
                    break

            except Exception as e:
                print(f"处理邮件时出错: {str(e)}")
                break

        print(f"邮箱 {email} 共下载了 {email_count} 封邮件")
        return email_count

    except Exception as e:
        print(f"处理邮箱 {email} 时出错: {str(e)}")
        traceback.print_exc()
        return 0
    finally:
        driver.quit()


def zip_email_files(email, output_dir):
    """将下载的eml文件按邮箱名称打包为zip，并返回打包前文件的总大小（字节）"""
    account_name = email.split('@')[0]
    account_dir = os.path.join(output_dir, account_name)
    zip_filename = os.path.join(output_dir, f"{email.replace('@', '_')}.zip")

    if not os.path.exists(account_dir):
        print(f"没有找到 {email} 的邮件目录")
        return 0

    # 计算打包前所有文件的总大小（单位：字节）
    total_size = 0
    for root, _, files in os.walk(account_dir):
        for file in files:
            file_path = os.path.join(root, file)
            total_size += os.path.getsize(file_path)

    print(f"正在将 {email} 的邮件打包为 zip 文件...")

    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(account_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, account_dir)
                zipf.write(file_path, arcname)

    # 清理临时目录
    shutil.rmtree(account_dir)
    print(f"已完成 {email} 的邮件打包: {zip_filename}，原始大小: {total_size} 字节")

    return total_size


def process_email_accounts(email_accounts, output_dir="/tmp/outlook_emails", proxy=None, user_agent=None):
    """处理多个邮箱账号"""
    create_directory(output_dir)
    total_emails = 0
    total_size = 0

    for account in email_accounts:
        email = account['email']
        password = account['password']
        proxy = account['proxy']
        user_agent = account['user_agent']

        downloaded = process_email_account(email, password, output_dir, proxy, user_agent)
        total_emails += downloaded

        if downloaded > 0:
            size = zip_email_files(email, output_dir)
            total_size += size

    print(f"\n所有邮箱账号处理完成，共下载 {total_emails} 封邮件， 总大小：{total_size} 字节")
    return total_emails, total_size


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Outlook邮件下载工具')
    parser.add_argument('--email', help='邮箱地址', required=True)
    parser.add_argument('--password', help='邮箱密码', required=True)
    parser.add_argument('--output', help='输出目录', default='/outlook_emails')
    parser.add_argument('--proxy',
                        help='代理设置，支持socks5/http/https，格式: socks5://127.0.0.1:1005:username:password 或 socks5://127.0.0.1:1005')
    parser.add_argument('--ua', help='自定义User-Agent头')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # 配置要处理的邮箱账号
    email_accounts = [
        {"email": args.email, "password": args.password}
    ]

    # 执行邮件下载和打包
    total_emails, total_size = process_email_accounts(
        email_accounts,
        output_dir=args.output,
        proxy=args.proxy,
        user_agent=args.ua
    )

    print(f"所有邮箱账号处理完成，共下载 {total_emails} 封邮件， 总大小：{total_size} 字节")