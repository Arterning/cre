from flask import Flask, request, jsonify, send_file
from imap import IMAPEmailDownloader
from crawl import process_email_accounts
import traceback
import os

app = Flask(__name__)


@app.route("/")
def hello_world():
    return "<p>running!</p>"


@app.route('/submit_emails', methods=['POST'])
def submit_emails():
    data = request.get_json()

    # 校验是否提供了 email_accounts 字段
    if not data or 'email_accounts' not in data:
        return jsonify({"error": "Missing 'email_accounts' parameter"}), 400

    email_accounts = data['email_accounts']
    crawl_type = data.get('crawl_type')  

    # 简单校验每个邮箱条目是否包含 email 和 password 字段
    for account in email_accounts:
        if 'email' not in account or 'password' not in account:
            return jsonify({"error": "Each account must include 'email' and 'password'"}), 400

    # 打印/处理接收到的数据（此处只是打印）
    print("Received email accounts:", email_accounts)

    try:
        if crawl_type == 'imap':
            email_downloader = IMAPEmailDownloader()
            email_downloader.process_accounts(email_accounts)
        else:
            process_email_accounts(email_accounts)
    except Exception as e:
        traceback.print_exc()  # 打印完整堆栈信息
        return jsonify({"status":"error", "msg":"download email error"}), 500


    return jsonify({"status": "success", "received": email_accounts})



@app.route('/download', methods=['GET'])
def download_file():
    email = request.args.get('email')

    if not email:
        return {"error": "缺少 email 参数"}, 400

    output_dir="/tmp/outlook_emails/"
    account_name = email.split('@')[0]
    account_dir = os.path.join(output_dir, account_name)
    file_path = os.path.join(output_dir, f"{email.replace('@', '_')}.zip")

    # 拼接文件路径
    #safe_email = email.replace("/", dd"_")  # 简单防止路径注入
    #file_path = f"/tmp/outlook_emails/{safe_email}.zip"

    print("file_path", file_path)

    if not os.path.exists(file_path):
        return {"error": "文件不存在"}, 404

    # 返回文件流供用户下载
    return send_file(file_path, as_attachment=True)



if __name__ == '__main__':
    app.run(debug=True)

