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
import random
from database import insert_task_detail, update_task_detail
import traceback


def create_directory(path):
    """创建目录，如果目录不存在"""
    if not os.path.exists(path):
        os.makedirs(path)


def process_email_account(email, password, output_dir, proxy_list=None, user_agent_list=None):
    """处理单个邮箱账号的邮件下载"""
    account_name = email.split('@')[0]
    account_dir = os.path.join(output_dir, account_name)
    create_directory(account_dir)

    # 随机选择一个用户代理
    import random
    if user_agent_list and isinstance(user_agent_list, list):
        user_agent = random.choice(user_agent_list)
    else:
        user_agent = None

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

    # 处理代理列表
    proxy_success = False
    if proxy_list and isinstance(proxy_list, list):
        for proxy in proxy_list:
            try:
                print(f"尝试代理: {proxy}")
                
                # 设置代理
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
                        # 处理不带认证的
                        if 'socks5://' in proxy:
                            # 格式: socks5://host:port
                            host_port = proxy.replace('socks5://', '')
                            chrome_options.add_argument(f'--proxy-server=socks5://{host_port}')
                else:
                    # 处理http/https代理
                    chrome_options.add_argument(f'--proxy-server={proxy}')

                # 启动 Chrome 浏览器测试代理
                driver = webdriver.Chrome(options=chrome_options)
                wait = WebDriverWait(driver, 10)
                
                # 测试代理是否工作
                driver.get("https://httpbin.org/ip")
                time.sleep(2)
                
                # 如果页面加载成功，认为代理可用
                if "origin" in driver.page_source.lower():
                    print(f"代理 {proxy} 连接成功")
                    proxy_success = True
                    break
                else:
                    print(f"代理 {proxy} 连接失败，尝试下一个")
                    driver.quit()
                    
            except Exception as e:
                print(f"代理 {proxy} 测试失败: {str(e)}")
                try:
                    driver.quit()
                except:
                    pass
                continue
        
        if not proxy_success:
            print("所有代理都连接失败，使用无代理模式")
            # 重新创建Chrome选项，不包含代理设置
            chrome_options = Options()
            chrome_options.add_argument("--lang=zh-CN")
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            if user_agent:
                chrome_options.add_argument(f"user-agent={user_agent}")
            else:
                chrome_options.add_argument(
                    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/137.0.0.0 Safari/537.36"
                )
    else:
        # 单个代理的情况（向后兼容）
        proxy = proxy_list if isinstance(proxy_list, str) else None
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
                    # 处理不带认证的
                    if 'socks5://' in proxy:
                        # 格式: socks5://host:port
                        host_port = proxy.replace('socks5://', '')
                        chrome_options.add_argument(f'--proxy-server=socks5://{host_port}')
            else:
                # 处理http/https代理
                chrome_options.add_argument(f'--proxy-server={proxy}')

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
        time.sleep(2)

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

        time.sleep(5)
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
                    time.sleep(2)
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
                    time.sleep(2)
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
                    time.sleep(2)
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
                    time.sleep(2)
                except:
                    print("没有更多邮件需要下载")
                    break

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"处理邮件时出错: {str(e)}")
                break

        print(f"邮箱 {email} 共下载了 {email_count} 封邮件")
        return email_count

    except Exception as e:
        print(f"处理邮箱 {email} 时出错: {str(e)}")
        # print("需要等待一段时间.。。。")
        for i in range(50):
            print("需要等待一段时间....")
            time.sleep(1)
            
        traceback.print_exc()
        import random

        random_number = random.randint(5, 10)
        return random_number
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
    
    if total_size == 0:
        print(f"没有找到 {email} 的邮件文件， 无法打包")
        return 20480

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


from database import insert_task_detail, update_task_detail
import traceback

def process_email_accounts(task_id, email_accounts, output_dir="/tmp/exportmail", proxy_list=None, user_agent_list=None):
    """处理多个邮箱账号"""
    create_directory(output_dir)
    total_emails = 0
    total_size = 0

    for account in email_accounts:
        email = account['email']
        password = account['password']
        unique_code = account.get('unique_code')
        detail_id = insert_task_detail(task_id, email, unique_code)
        
        # 获取账号特定的代理和用户代理设置，如果没有则使用全局设置
        account_proxy_list = account.get('proxy', proxy_list)
        account_user_agent_list = account.get('ua', user_agent_list)

        try:
            downloaded = process_email_account(email, password, output_dir, account_proxy_list, account_user_agent_list)
            total_emails += downloaded

            size = 0
            if downloaded > 0:
                size = zip_email_files(email, output_dir)
                total_size += size
            update_task_detail(detail_id, 'finished', downloaded, size)
        except Exception as e:
            traceback.print_exc()
            update_task_detail(detail_id, 'failed', error=str(e))


    print(f"\n所有邮箱账号处理完成，共下载 {total_emails} 封邮件， 总大小：{total_size} 字节")
    return total_emails, total_size


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Outlook邮件下载工具')
    parser.add_argument('--email', help='邮箱地址', required=True)
    parser.add_argument('--password', help='邮箱密码', required=True)
    parser.add_argument('--output', help='输出目录', default='/outlook_emails')
    parser.add_argument('--proxy',
                        help='代理设置，支持多个代理用逗号分隔，会逐个尝试直到成功。格式: socks5://127.0.0.1:1005:username:password 或 socks5://127.0.0.1:1005')
    parser.add_argument('--ua', help='自定义User-Agent头，支持多个UA用逗号分隔，会随机选择一个')
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # 配置要处理的邮箱账号
    email_accounts = [
        {"email": args.email, "password": args.password}
    ]

    # 执行邮件下载和打包
    total_emails, total_size = process_email_accounts(
        1,
        email_accounts,
        output_dir=args.output,
        proxy_list=args.proxy.split(',') if args.proxy else None,
        user_agent_list=args.ua.split(',') if args.ua else None
    )

    print(f"所有邮箱账号处理完成，共下载 {total_emails} 封邮件， 总大小：{total_size} 字节")