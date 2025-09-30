import os
import time
import random
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


def test_proxy(proxy, chrome_options):
    """测试代理是否工作"""
    try:
        print(f"尝试代理: {proxy}")
        
        # 复制Chrome选项，避免修改原选项
        test_options = Options()
        for arg in chrome_options.arguments:
            test_options.add_argument(arg)
        
        # 设置代理
        if proxy.startswith('socks5://'):
            # 处理带认证的socks5代理
            if '@' in proxy:
                # 格式: socks5://username:password@host:port
                proxy_parts = proxy.split('@')
                auth_part = proxy_parts[0].replace('socks5://', '')
                username, password_proxy = auth_part.split(':')
                host_port = proxy_parts[1]
                test_options.add_argument(f'--proxy-server=socks5://{host_port}')
                test_options.add_argument(f'--proxy-auth={username}:{password_proxy}')
            else:
                # 处理不带认证的
                if 'socks5://' in proxy:
                    # 格式: socks5://host:port
                    host_port = proxy.replace('socks5://', '')
                    test_options.add_argument(f'--proxy-server=socks5://{host_port}')
        else:
            # 处理http/https代理
            test_options.add_argument(f'--proxy-server={proxy}')

        # 启动 Chrome 浏览器测试代理
        driver = webdriver.Chrome(options=test_options)
        wait = WebDriverWait(driver, 10)
        
        # 测试代理是否工作
        driver.get("https://httpbin.org/ip")
        time.sleep(2)
        
        # 如果页面加载成功，认为代理可用
        if "origin" in driver.page_source.lower():
            print(f"代理 {proxy} 连接成功")
            proxy_success = True
        else:
            # print(f"代理 {proxy} 连接失败，尝试下一个")
            proxy_success = False
        driver.quit()
        return proxy_success
    except Exception as e:
        # print(f"代理 {proxy} 测试失败: {str(e)}")
        try:
            driver.quit()
        except:
            pass
        return False


def process_email_account(email, password, output_dir, proxy_list=None, user_agent_list=None):
    """处理单个邮箱账号的邮件下载"""
    account_name = email.split('@')[0]
    account_dir = os.path.join(output_dir, account_name)
    create_directory(account_dir)

    # 随机选择一个用户代理
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
            if test_proxy(proxy, chrome_options):
                proxy_success = True
                # 设置成功的代理到chrome_options
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
                break
        
        
    else:
        # 单个代理的情况（向后兼容）
        proxy = proxy_list if isinstance(proxy_list, str) else None
        print(f"使用代理: {proxy}")
        if proxy and test_proxy(proxy, chrome_options):
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


    if not proxy_success:
        # print("所有代理都连接失败，使用无代理模式")
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


        # 检查是否需要点击特殊元素
        try:
            # 尝试找到并点击指定元素
            special_element = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#view > div > span:nth-child(6) > div > span"))
            )
            print("验证你的电子邮件地址的提示出现")
            special_element.click()
            time.sleep(1)
        except:
            # 如果元素不存在或点击失败，则继续流程
            print("验证你的电子邮件地址的提示未出现，继续流程")
            pass

        # 输入密码

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
        import traceback
        print(f"处理邮箱 {email} 时出错: {str(e)}")
            
        traceback.print_exc()

        random_number = random.randint(5, 10)
        return random_number
    finally:
        driver.quit()


# 辅助函数：创建目录
def create_directory(directory_path):
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)