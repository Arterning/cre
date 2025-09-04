# GMX邮箱自动下载工具

```
uv run .\claude_client.py --username china_ningning@outlook.com --password xldkdfj --max_attempts 2  --auto_query_imap --key_file .\key.txt
```

这是一个使用Python编写的GMX邮箱自动下载工具，可以通过IMAP协议连接到GMX邮箱，自动获取所有邮件并保存到本地。

## 功能特点

- ✅ 自动连接GMX IMAP服务器
- ✅ 支持SSL安全连接
- ✅ 获取所有邮箱文件夹
- ✅ 下载所有邮件到本地
- ✅ 支持邮件数量限制
- ✅ 自动创建文件夹结构
- ✅ 保存邮件元数据（JSON格式）
- ✅ 完整的日志记录
- ✅ 错误处理和重试机制
- ✅ 进度显示

## 系统要求

- Python 3.6 或更高版本
- 网络连接
- GMX邮箱账户

## 安装和使用

### 1. 下载脚本

将以下文件下载到你的本地目录：
- `gmx_email_downloader.py` - 主程序文件
- `requirements.txt` - 依赖文件（可选）

### 2. 运行程序

```bash
python gmx_email_downloader.py
```

### 3. 输入信息

程序会提示你输入：
- GMX邮箱用户名（完整邮箱地址）
- GMX邮箱密码
- 每个文件夹最大下载邮件数量（可选，直接回车下载全部）

## 输出文件结构

下载的邮件会保存在 `emails` 目录下，结构如下：

```
emails/
├── INBOX/                    # 收件箱邮件
│   ├── email_1_20231201_143022.eml
│   ├── email_1_20231201_143022_metadata.json
│   ├── email_2_20231201_143025.eml
│   └── email_2_20231201_143025_metadata.json
├── Sent/                     # 已发送邮件
│   ├── email_3_20231201_143030.eml
│   └── email_3_20231201_143030_metadata.json
└── Drafts/                   # 草稿邮件
    └── ...
```

## 文件说明

### .eml 文件
- 原始邮件文件，包含完整的邮件内容
- 可以用任何邮件客户端打开查看

### _metadata.json 文件
- 邮件元数据，包含以下信息：
  - `email_id`: 邮件ID
  - `subject`: 邮件主题
  - `from`: 发件人
  - `to`: 收件人
  - `date`: 邮件日期
  - `folder`: 所在文件夹
  - `filename`: 文件名
  - `download_time`: 下载时间

## 日志文件

程序运行时会生成 `gmx_downloader.log` 日志文件，记录：
- 连接状态
- 下载进度
- 错误信息
- 操作历史

## 使用示例

### 基本使用
```bash
python gmx_email_downloader.py
```

输入：
```
请输入GMX邮箱用户名: your_email@gmx.com
请输入GMX邮箱密码: your_password
请输入每个文件夹最大下载邮件数量（直接回车表示下载全部）: 100
```

### 程序化使用
```python
from gmx_email_downloader import GMXEmailDownloader

# 创建下载器
downloader = GMXEmailDownloader("your_email@gmx.com", "your_password")

# 下载所有邮件
success = downloader.run()

# 或者限制每个文件夹最多下载50封邮件
success = downloader.run(max_emails_per_folder=50)
```

## 注意事项

1. **安全性**：
   - 密码会以明文形式输入，请确保在安全环境中使用
   - 建议使用应用专用密码而不是主密码

2. **网络连接**：
   - 需要稳定的网络连接
   - 大量邮件下载可能需要较长时间

3. **存储空间**：
   - 确保有足够的磁盘空间存储邮件
   - 邮件文件会占用相应空间

4. **服务器限制**：
   - GMX可能有连接频率限制
   - 程序已添加延迟机制避免触发限制

5. **邮件格式**：
   - 下载的是原始邮件格式(.eml)
   - 可以用Outlook、Thunderbird等邮件客户端打开

## 故障排除

### 连接失败
- 检查网络连接
- 确认用户名和密码正确
- 检查GMX账户是否启用了IMAP访问

### 下载中断
- 查看日志文件了解具体错误
- 重新运行程序，已下载的邮件不会重复下载

### 权限问题
- 确保有写入权限到当前目录
- 检查防火墙设置

## 技术细节

- **IMAP服务器**: imap.gmx.com:993 (SSL)
- **协议**: IMAP4 over SSL
- **编码**: UTF-8
- **邮件格式**: RFC822

## 许可证

本工具仅供学习和个人使用，请遵守相关法律法规和GMX服务条款。

## 更新日志

- v1.0.0: 初始版本，支持基本的邮件下载功能
