import os
import time
import zipfile
import shutil
import requests
from urllib.parse import urlparse, parse_qs
from imapclient import IMAPClient
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException


class IMAPEmailDownloader:
    def __init__(self):
        # OAuth 配置
        self.client_id = "000000004C12142B"
        self.client_secret = "enA0CwXg0B9olTrXGnm6ucdqWv7WkdXc"
        self.redirect_uri = "https://readdle.com/"

        # Selenium 配置
        self.driver = None
        self.setup_selenium()

        # 输出目录
        #self.base_output_dir = os.path.join(os.getcwd(), "emails")
        self.base_output_dir = "/tmp/outlook_emails/"
        os.makedirs(self.base_output_dir, exist_ok=True)

    def setup_selenium(self):
        """强化WebDriver配置"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 开发时可先注释掉，方便调试
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

        # 添加用户代理
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 30)
        print("Selenium WebDriver 已成功初始化")

    def _save_debug_screenshot(self, email, step_name):
        """保存调试截图"""
        debug_dir = os.path.join(os.getcwd(), "debug_screenshots")
        os.makedirs(debug_dir, exist_ok=True)
        filename = f"{email.split('@')[0]}_{int(time.time())}_{step_name}.png"
        filepath = os.path.join(debug_dir, filename)
        self.driver.save_screenshot(filepath)
        print(f"已保存调试截图: {filepath}")

    def get_authorization_code(self, email, password):
        """增强版授权码获取，处理多种登录场景"""
        try:
            print(f"\n[授权流程] 开始处理账号: {email}")

            # 构建授权URL
            auth_url = f"https://login.live.com/oauth20_authorize.srf?client_id={self.client_id}" \
                       f"&redirect_uri={self.redirect_uri}&response_type=code" \
                       f"&scope=wl.imap&login_hint={email}"

            # 访问授权页面
            self.driver.get(auth_url)
            self._save_debug_screenshot(email, "1_init_page")

            # 立即检查URL是否已包含code（已授权账户可能直接跳转）
            current_url = self.driver.current_url
            if "code=" in current_url:
                print("检测到已授权账户直接跳转")
                return self._extract_code_from_url(current_url)

            # 处理密码输入页面的多种可能情况
            try:
                # 尝试多种可能的密码输入框定位方式
                password_selectors = [
                    "input[type='password']",
                    "input#passwordInput",
                    "input#i0118",
                    "input[name='passwd']"
                ]

                password_field = None
                for selector in password_selectors:
                    try:
                        password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue

                if password_field is None:
                    raise Exception("找不到密码输入框")

                password_field.send_keys(password)
                self._save_debug_screenshot(email, "2_password_entered")

                # 尝试多种可能的登录按钮定位方式
                login_button_selectors = [
                    "input[type='submit'][value='登录']",
                    "button[data-testid='primaryButton']",
                    "input#idSIButton9",
                    "button#btnSubmit"
                ]

                login_button = None
                for selector in login_button_selectors:
                    try:
                        login_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue

                if login_button is None:
                    raise Exception("找不到登录按钮")

                login_button.click()
                self._save_debug_screenshot(email, "3_after_login_click")
                time.sleep(3)  # 等待页面跳转

                # 再次检查是否直接跳转到授权码页面（已授权账户）
                current_url = self.driver.current_url
                if "code=" in current_url:
                    print("密码验证后直接跳转到授权页面")
                    return self._extract_code_from_url(current_url)

                # 处理保持登录提示（如存在）
                try:
                    no_button = self.driver.find_element(By.ID, "idBtn_Back")
                    no_button.click()
                    time.sleep(2)
                    self._save_debug_screenshot(email, "4_after_keep_login")
                except NoSuchElementException:
                    pass

                # 处理保持登录按钮，如果存在
                try:
                    consent_button = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='secondaryButton']"))
                    )
                    consent_button.click()
                    time.sleep(2)
                    self._save_debug_screenshot(email, "5_after_consent")
                except (NoSuchElementException, TimeoutException):
                    pass
                # 处理同意授权按钮，如果存在
                try:
                    consent_button = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='appConsentPrimaryButton']"))
                    )
                    consent_button.click()
                    time.sleep(2)
                    self._save_debug_screenshot(email, "aa_after_consent")
                except (NoSuchElementException, TimeoutException):
                    pass

                # 最终获取授权码
                current_url = self.driver.current_url
                if "code=" not in current_url:
                    raise Exception("未成功跳转到授权码页面，可能是此账户未启用IMAP协议")

                return self._extract_code_from_url(current_url)

            except Exception as e:
                self._save_debug_screenshot(email, "error_during_auth")
                raise Exception(f"授权过程中出错: {str(e)}")

        except Exception as e:
            print(f"[授权失败] {email}: {str(e)}")
            raise

    def _extract_code_from_url(self, url):
        """从URL中安全提取授权码"""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if "code" not in params:
                raise ValueError("授权码未在URL中找到")
            return params["code"][0]
        except Exception as e:
            raise ValueError(f"解析授权码失败: {str(e)}")

    def get_access_token(self, code, max_retries=3):
        """获取访问令牌，增加重试机制"""
        for attempt in range(max_retries):
            try:
                print(f"尝试获取访问令牌 (尝试 {attempt + 1}/{max_retries})...")
                response = requests.post(
                    "https://login.live.com/oauth20_token.srf",
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": self.redirect_uri,
                    },
                    timeout=30
                )
                response.raise_for_status()
                json_response = response.json()

                if "access_token" not in json_response:
                    raise ValueError("响应中未包含访问令牌")

                print("访问令牌获取成功")
                return json_response["access_token"]

            except Exception as e:
                if attempt == max_retries - 1:
                    raise Exception(f"获取访问令牌失败: {str(e)}")
                time.sleep(2 * (attempt + 1))  # 指数退避

    def check_imap_availability(self, email, access_token):
        """检查IMAP服务是否可用"""
        try:
            print(f"正在检查 {email} 的IMAP服务可用性...")
            with IMAPClient(host="outlook.office365.com", ssl=True, port=993) as client:
                client.oauth2_login(email, access_token)
                client.select_folder('INBOX', readonly=True)
                print("IMAP服务可用")
                return True
        except Exception as e:
            error_msg = str(e).lower()
            if "imap access is disabled" in error_msg:
                print("IMAP服务未启用")
                return False
            # 其他连接问题也视为IMAP不可用
            print(f"IMAP检查出错: {str(e)}")
            return False

    def download_emails(self, email, password):
        """增强版邮件下载方法，处理IMAP未启用情况"""
        try:
            print(f"\n[开始下载] 处理邮箱: {email}")

            # 1. 获取授权码
            try:
                code = self.get_authorization_code(email, password)
            except Exception as e:
                if "IMAP" in str(e):  # 明确提示IMAP未启用
                    print(f"账户 {email} 未启用IMAP协议，跳过处理")
                    return 0
                raise

            # 2. 获取访问令牌
            access_token = self.get_access_token(code)

            # 3. 检查IMAP可用性
            if not self.check_imap_availability(email, access_token):
                print(f"[IMAP不可用] 跳过 {email} 的邮件下载")
                return 0

            # 4. 创建邮箱专属目录
            email_folder = os.path.join(self.base_output_dir, email.replace("@", "_"))
            os.makedirs(email_folder, exist_ok=True)

            # 5. 连接IMAP服务器并下载邮件
            download_count = 0
            with IMAPClient(host="outlook.office365.com", ssl=True, port=993) as client:
                client.oauth2_login(email, access_token)
                client.select_folder('INBOX')

                # 获取所有未删除邮件
                messages = client.search(['NOT', 'DELETED'])

                if not messages:
                    print(f"{email} 收件箱中没有未删除邮件")
                    return 0

                print(f"{email} 发现 {len(messages)} 封未删除邮件")

                # 分批获取邮件内容，避免内存问题
                batch_size = 50
                for i in range(0, len(messages), batch_size):
                    batch = messages[i:i + batch_size]
                    response = client.fetch(batch, ['RFC822'])

                    for msg_id, data in response.items():
                        try:
                            filename = f"email_{time.strftime('%Y%m%d_%H%M%S')}_{msg_id}.eml"
                            filepath = os.path.join(email_folder, filename)

                            with open(filepath, 'wb') as f:
                                f.write(data[b'RFC822'])

                            download_count += 1
                            if download_count % 10 == 0:
                                print(f"已下载 {download_count}/{len(messages)} 封邮件")
                        except Exception as e:
                            print(f"下载邮件 {msg_id} 时出错: {str(e)}")
                            continue

            print(f"成功下载 {download_count}/{len(messages)} 封邮件")
            return download_count

        except Exception as e:
            print(f"[下载失败] {email}: {str(e)}")
            return 0

    def zip_email_folder(self, email):
        """将邮箱目录打包为ZIP文件，增强错误处理"""
        try:
            print(f"\n[开始打包] 处理邮箱: {email}")

            email_folder_name = email.replace("@", "_")
            email_folder = os.path.join(self.base_output_dir, email_folder_name)
            zip_filename = os.path.join(self.base_output_dir, f"{email_folder_name}.zip")

            # 检查目录是否存在
            if not os.path.exists(email_folder):
                print(f"邮件目录不存在: {email_folder}")
                return False

            # 检查目录是否为空
            if not os.listdir(email_folder):
                print(f"邮件目录为空: {email_folder}")
                return False

            print(f"开始打包 {email} 的邮件...")

            # 创建ZIP文件
            with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(email_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, email_folder)
                        zipf.write(file_path, arcname)

            # 验证ZIP文件
            if not os.path.exists(zip_filename):
                raise Exception("ZIP文件创建失败")

            # 删除原始文件夹
            shutil.rmtree(email_folder)

            print(f"邮件已打包到 {zip_filename}")
            return True

        except Exception as e:
            print(f"[打包失败] {email}: {str(e)}")
            return False

    def process_accounts(self, accounts):
        """处理多个邮箱账号，增加进度报告"""
        success_count = 0
        failed_accounts = []

        print(f"\n开始批量处理 {len(accounts)} 个邮箱账号")

        for index, account in enumerate(accounts, start=1):
            email = account['email']
            password = account['password']

            print(f"\n[{index}/{len(accounts)}] 正在处理 {email}")

            try:
                downloaded = self.download_emails(email, password)

                if downloaded > 0:
                    self.zip_email_folder(email)
                    success_count += 1
                    print(f"[成功] {email} 处理完成，下载 {downloaded} 封邮件")
                else:
                    print(f"[跳过] {email} 没有可下载的邮件或IMAP未启用")

            except Exception as e:
                failed_accounts.append((email, str(e)))
                print(f"[失败] {email} 处理出错: {str(e)}")

        # 输出汇总报告
        print("\n" + "=" * 50)
        print("处理完成".center(50))
        print("=" * 50)
        print(f"成功处理: {success_count}/{len(accounts)} 个账号")
        if failed_accounts:
            print("\n失败账号列表:")
            for email, error in failed_accounts:
                print(f"- {email}: {error}")
        print("=" * 50)

        return success_count

    def close(self):
        """安全关闭资源"""
        print("\n正在清理资源...")
        try:
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
                print("浏览器已关闭")
        except Exception as e:
            print(f"关闭浏览器时出错: {str(e)}")


if __name__ == "__main__":
    # 测试账号 - 替换为真实账号
    TEST_ACCOUNTS = [
        {"email": "asmasaailgcba@outlook.com", "password": "1qaz@WSX..123"},
        {"email": "coco67493@outlook.com", "password": "g0NLnGtK2skxgEsG"}
    ]

    downloader = IMAPEmailDownloader()
    try:
        downloader.process_accounts(TEST_ACCOUNTS)
    except KeyboardInterrupt:
        print("\n用户中断操作")
    except Exception as e:
        print(f"主程序出错: {str(e)}")
    finally:
        downloader.close()
