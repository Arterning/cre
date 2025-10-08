import os
import zipfile
import shutil
import subprocess
import time
import sys

def create_directory(path):
    """创建目录，如果目录不存在"""
    if not os.path.exists(path):
        os.makedirs(path)


# 示例 1：执行简单命令并获取输出
def run_command(command):
    try:
        # 执行命令，捕获输出
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }
    except subprocess.SubprocessError as e:
        print(f"命令执行失败：{e}")


def zip_email_files(email):
    """将下载的eml文件按邮箱名称打包为zip，并返回打包前文件的总大小（字节）"""
    output_dir = "/tmp/exportmail"
    account_name = email.replace('@', '_')
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