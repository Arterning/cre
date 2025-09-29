from selenium import webdriver
import sys
import os
import time

# 添加项目根目录到sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


chrome_options = Options()
chrome_options.add_argument("--lang=zh-CN")
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)
# proxy = "http://127.0.0.1:7890"
# chrome_options.add_argument(f'--proxy-server={proxy}')

# 启动 Chrome 浏览器测试代理
driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, 10)
print("浏览器启动成功")

# 测试代理是否工作
driver.get("https://httpbin.org/ip")
time.sleep(2)

print(driver.page_source)
# 如果页面加载成功，认为代理可用
if "origin" in driver.page_source.lower():
    print(f"连接成功")