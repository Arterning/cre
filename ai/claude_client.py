#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claude Messages API 简易客户端

功能：
- 交互式对话（多轮），JSON输入/JSON输出
- 单次调用（从stdin读取JSON或命令行参数）

环境变量：
- ANTHROPIC_API_KEY：Claude API Key（必需）

依赖：仅使用Python标准库
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from typing import Any, Dict, List, Tuple
import time
import socket
import re
import subprocess
from datetime import datetime


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-20250514"


def http_post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout: float = 30.0, retries: int = 1) -> Dict[str, Any]:
    data = json.dumps(payload).encode('utf-8')
    last_error: Dict[str, Any] | None = None
    attempts = max(1, int(retries))
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode('utf-8')
                return {
                    "status": resp.getcode(),
                    "headers": dict(resp.headers),
                    "body": json.loads(body) if body else None,
                }
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='ignore')
            try:
                err_json = json.loads(err_body)
            except Exception:
                err_json = {"raw": err_body}
            return {"status": e.code, "error": True, "body": err_json}
        except (urllib.error.URLError, socket.timeout) as e:
            last_error = {"status": 0, "error": True, "body": {"message": str(e), "attempt": attempt}}
            if attempt < attempts:
                time.sleep(min(2 ** (attempt - 1), 5))
            else:
                break
    return last_error or {"status": 0, "error": True, "body": {"message": "request failed"}}


def build_headers(api_key: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }


def one_shot_call(api_key: str, prompt: str, model: str, max_tokens: int, system: str = None, api_url: str = ANTHROPIC_API_URL, timeout: float = 30.0, retries: int = 1) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "user", "content": prompt}
        ],
    }
    if system:
        payload["system"] = system
    return http_post_json(api_url, payload, build_headers(api_key), timeout=timeout, retries=retries)


def conversation_loop(api_key: str, model: str, max_tokens: int, system: str = None, api_url: str = ANTHROPIC_API_URL, timeout: float = 30.0, retries: int = 1) -> None:
    print(json.dumps({"type": "info", "message": "Enter 'exit' to quit"}, ensure_ascii=False))
    history: List[Dict[str, str]] = []
    while True:
        try:
            user_input = input().strip()
        except EOFError:
            break
        if user_input.lower() in {"exit", "quit", ":q", ":q!"}:
            break
        if not user_input:
            continue

        history.append({"role": "user", "content": user_input})

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": history[-20:],  # 保留近20轮，避免上下文过长
        }
        if system:
            payload["system"] = system

        resp = http_post_json(api_url, payload, build_headers(api_key), timeout=timeout, retries=retries)
        if resp.get("error"):
            print(json.dumps({"type": "error", "data": resp}, ensure_ascii=False))
            continue

        body = resp.get("body", {})
        # Claude messages API 返回结构：{"content":[{"type":"text","text":"..."}], ...}
        answer = ""
        try:
            parts = body.get("content", [])
            for p in parts:
                if isinstance(p, dict) and p.get("type") == "text":
                    answer += p.get("text", "")
        except Exception:
            pass

        history.append({"role": "assistant", "content": answer})
        print(json.dumps({"type": "message", "answer": answer, "raw": body}, ensure_ascii=False))


def read_stdin_json() -> Dict[str, Any]:
    raw = sys.stdin.read()
    return json.loads(raw) if raw.strip() else {}


def extract_text_from_body(body: Dict[str, Any]) -> str:
    parts = body.get("content", [])
    text_chunks: List[str] = []
    for p in parts:
        if isinstance(p, dict) and p.get("type") == "text":
            text_chunks.append(p.get("text", ""))
    return "".join(text_chunks)


def extract_code_blocks(text: str, preferred_language: str = "python") -> List[Tuple[str, str]]:
    # 提取三引号代码块，兼容 Windows 行结尾与可选语言标注
    code_blocks: List[Tuple[str, str]] = []
    patterns = [
        re.compile(r"```[ \t]*([a-zA-Z0-9_+\-]*)\r?\n([\s\S]*?)```", re.MULTILINE),
        re.compile(r"```\r?\n([\s\S]*?)```", re.MULTILINE),
    ]
    for pat in patterns:
        for match in pat.finditer(text):
            if match.lastindex == 2:
                lang = match.group(1).strip().lower()
                code = match.group(2)
            else:
                lang = ""
                code = match.group(1)
            code_blocks.append((lang or "", code))
        if code_blocks:
            break

    # Fallback：整段文本看似包含围栏但未匹配时，尝试粗暴去掉首尾围栏行
    if not code_blocks and text.strip().lstrip().startswith("```"):
        lines = text.splitlines()
        # 去掉第一行 ```lang
        if lines:
            lines = lines[1:]
        # 去掉末尾第一次出现的 ```
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                lines = lines[:i]
                break
        code_blocks.append(("", "\n".join(lines)))

    # 若仍没有，则将全文作为代码（避免把 ``` 内容原样写入 .py）
    if not code_blocks and text.strip():
        cleaned = text
        # 移除任何行内仅包含 ``` 的行
        cleaned = "\n".join([ln for ln in cleaned.splitlines() if ln.strip() != "```"])
        # 移除开头的 ```lang 标记行
        if cleaned.lstrip().startswith("```"):
            cleaned = "\n".join(cleaned.splitlines()[1:])
        code_blocks.append(("", cleaned))

    # 规范化：去掉BOM与首尾空白
    norm_blocks: List[Tuple[str, str]] = []
    for lang, code in code_blocks:
        if code.startswith("\ufeff"):
            code = code.lstrip("\ufeff")
        code = code.strip("\n\r")
        norm_blocks.append((lang, code))

    # 将首选语言放前
    if preferred_language:
        norm_blocks.sort(key=lambda t: 0 if t[0] == preferred_language.lower() else 1)
    return norm_blocks


def language_to_extension(lang: str) -> str:
    mapping = {
        "python": "py",
        "py": "py",
        "bash": "sh",
        "sh": "sh",
        "javascript": "js",
        "js": "js",
        "typescript": "ts",
        "ts": "ts",
        "json": "json",
        "yaml": "yml",
        "yml": "yml",
        "": "txt",
    }
    return mapping.get(lang.lower(), "txt")


def replace_hardcoded_credentials(code: str, username: str = None, password: str = None) -> str:
    """替换代码中的硬编码用户名和密码"""
    if not username and not password:
        return code
    
    import re
    lines = code.split('\n')
    modified_lines = []
    
    for line in lines:
        original_line = line
        
        # 检查是否包含硬编码的用户名
        if username:
            # 匹配各种用户名变量赋值模式
            patterns = [
                (r'email_address\s*=\s*["\'][^"\']*["\']', f'email_address = "{username}"'),
                (r'username\s*=\s*["\'][^"\']*["\']', f'username = "{username}"'),
                (r'user\s*=\s*["\'][^"\']*["\']', f'user = "{username}"'),
                (r'email\s*=\s*["\'][^"\']*["\']', f'email = "{username}"'),
                (r'account\s*=\s*["\'][^"\']*["\']', f'account = "{username}"'),
            ]
            
            for pattern, replacement in patterns:
                if re.search(pattern, line):
                    line = re.sub(pattern, replacement, line)
                    break
        
        # 检查是否包含硬编码的密码
        if password:
            # 匹配各种密码变量赋值模式
            patterns = [
                (r'password\s*=\s*["\'][^"\']*["\']', f'password = "{password}"'),
                (r'passwd\s*=\s*["\'][^"\']*["\']', f'passwd = "{password}"'),
                (r'auth_code\s*=\s*["\'][^"\']*["\']', f'auth_code = "{password}"'),
                (r'token\s*=\s*["\'][^"\']*["\']', f'token = "{password}"'),
                (r'key\s*=\s*["\'][^"\']*["\']', f'key = "{password}"'),
            ]
            
            for pattern, replacement in patterns:
                if re.search(pattern, line):
                    line = re.sub(pattern, replacement, line)
                    break
        
        # 如果行被修改了，添加注释说明
        if line != original_line and (username or password):
            # 检查是否已经有注释
            if '#' not in line:
                line += '  # 已自动替换为提供的凭据'
        
        modified_lines.append(line)
    
    return '\n'.join(modified_lines)


def save_code_template(root_dir: str, attempt_dir: str, code_blocks: List[Tuple[str, str]], preferred_language: str, entry_filename: str, username: str = None, password: str = None) -> Dict[str, Any]:
    os.makedirs(attempt_dir, exist_ok=True)
    saved_files: List[str] = []
    primary_path: str | None = None
    python_blocks = [(i, b) for i, b in enumerate(code_blocks) if b[0] in {preferred_language.lower(), ""}]
    for idx, (lang, code) in enumerate(code_blocks):
        # 替换硬编码的凭据
        modified_code = replace_hardcoded_credentials(code, username, password)
        
        # 如果代码被修改了，输出调试信息
        if modified_code != code and (username or password):
            print(f"已自动替换硬编码凭据: {username or 'N/A'} / {password or 'N/A'}")
        
        # 如果首选语言是python且未标注语言，则默认保存为.py
        if (not lang) and preferred_language.lower() == "python":
            ext = "py"
        else:
            ext = language_to_extension(lang)
        # 不强制 main.py。优先生成通用文件名 code_*.ext；仅当显式提供 entry_filename 时，首个匹配语言的块使用该文件名。
        filename = f"code_{idx + 1}.{ext}"
        if entry_filename and lang == preferred_language.lower() and primary_path is None and modified_code.strip():
            filename = entry_filename
        file_path = os.path.join(attempt_dir, filename)
        import codecs
        with codecs.open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_code)
        saved_files.append(file_path)
        if filename == entry_filename and primary_path is None:
            primary_path = file_path
    # 若未指定或未命中入口文件，则自动选择第一个 .py 文件作为入口；若不存在 .py，则选择第一个保存的文件
    if primary_path is None:
        py_files = [p for p in saved_files if p.lower().endswith('.py')]
        primary_path = py_files[0] if py_files else (saved_files[0] if saved_files else None)
    meta = {
        "root_dir": root_dir,
        "attempt_dir": attempt_dir,
        "files": saved_files,
        "entry": primary_path,
    }
    with open(os.path.join(attempt_dir, 'files.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


def run_python_file(file_path: str, cwd: str | None = None, timeout: float = 120.0) -> Dict[str, Any]:
    entry_dir = cwd or os.path.dirname(os.path.abspath(file_path))
    entry_name = os.path.basename(file_path)
    
    # 运行脚本并实时显示输出
    print(f"\n=== 执行脚本: {entry_name} ===")
    
    try:
        # 设置环境变量确保UTF-8编码和无缓冲
        env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1'}
        
        # 使用subprocess.Popen实现实时输出
        process = subprocess.Popen(
            [sys.executable, entry_name],
            cwd=entry_dir,
            text=True,
            encoding='utf-8',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            bufsize=0,  # 无缓冲
            universal_newlines=True
        )
        
        stdout_lines = []
        
        # 实时读取并显示输出
        while True:
            # 检查进程是否结束
            if process.poll() is not None:
                # 读取剩余输出
                remaining = process.stdout.read()
                if remaining:
                    print(remaining, end='', flush=True)
                    stdout_lines.append(remaining)
                break
            
            # 读取一行输出
            line = process.stdout.readline()
            if line:
                print(line, end='', flush=True)  # 立即显示
                stdout_lines.append(line)
            else:
                # 短暂等待避免CPU占用过高
                import time
                time.sleep(0.01)
        
        # 获取返回码
        returncode = process.wait()
        
        return {
            "returncode": returncode,
            "stdout": "".join(stdout_lines),
            "stderr": ""
        }
        
    except subprocess.TimeoutExpired:
        process.kill()
        print(f"\n脚本执行超时 ({timeout}s)")
        return {"returncode": -1, "stdout": "", "stderr": f"Timeout after {timeout}s"}
    except Exception as e:
        print(f"\n脚本执行出错: {e}")
        return {"returncode": -1, "stdout": "", "stderr": str(e)}


def check_script_success(run_result: Dict[str, Any], attempt_dir: str, entry: str) -> bool:
    """检查脚本是否真正成功：不仅没有语法错误，还要检查是否成功下载了邮件"""
    # 1. 首先检查是否有语法错误
    if run_result.get('returncode', 0) != 0:
        print(f"❌ 脚本执行失败，返回码: {run_result.get('returncode', 0)}")
        return False
    
    # 2. 检查stdout中是否有成功下载邮件的标志
    stdout = run_result.get('stdout', '').lower()
    stderr = run_result.get('stderr', '').lower()
    
    # 成功标志：包含邮件下载成功的提示
    success_indicators = [
        '邮件下载完成',
        '下载完成',
        'download complete',
        'successfully downloaded',
        '邮件保存成功',
        'emails saved',
        '下载了',
        'downloaded',
        '保存到',
        'saved to',
        '成功下载邮件数量',
        '成功下载',
        '邮件数量',
        '任务完成',
        '总共成功下载'
    ]
    
    # 失败标志：登录失败、密码错误、下载失败等
    failure_indicators = [
        '登录失败',
        'login failed',
        'authentication failed',
        '密码错误',
        'password error',
        '用户名错误',
        'username error',
        '下载失败',
        'download failed',
        '连接失败',
        'connection failed',
        'imap error',
        '无法连接',
        'cannot connect',
        '授权码错误',
        'authorization code error'
    ]
    
    # 检查是否有失败标志
    for indicator in failure_indicators:
        if indicator in stdout or indicator in stderr:
            return False
    
    # 检查是否有成功标志
    for indicator in success_indicators:
        if indicator in stdout:
            print(f"✅ 检测到成功标志: '{indicator}'")
            return True
    
    # 调试信息：显示stdout的前200个字符
    print(f"🔍 调试信息 - stdout前200字符: {stdout[:200]}")
    
    # 3. 检查是否创建了邮件文件（检查新的邮件保存路径结构）
    try:
        # 获取脚本所在目录的父目录（client同路径）
        script_dir = os.path.dirname(entry)
        parent_dir = os.path.dirname(script_dir) if script_dir else os.getcwd()
        
        # 检查新的邮件保存路径结构：email/域名/用户名/日期/
        email_base_dir = os.path.join(parent_dir, "email")
        if os.path.exists(email_base_dir):
            # 遍历域名目录
            for domain_dir in os.listdir(email_base_dir):
                domain_path = os.path.join(email_base_dir, domain_dir)
                if os.path.isdir(domain_path):
                    # 遍历用户名目录
                    for user_dir in os.listdir(domain_path):
                        user_path = os.path.join(domain_path, user_dir)
                        if os.path.isdir(user_path):
                            # 遍历日期目录
                            for date_dir in os.listdir(user_path):
                                date_path = os.path.join(user_path, date_dir)
                                if os.path.isdir(date_path):
                                    # 检查是否有邮件文件
                                    try:
                                        files = os.listdir(date_path)
                                        if any(ext in f.lower() for f in files for ext in ['.eml', '.msg']):
                                            print(f"✅ 检测到邮件文件目录: email/{domain_dir}/{user_dir}/{date_dir}")
                                            return True
                                    except Exception:
                                        continue
    except Exception:
        pass
    
    # 兼容旧的邮件保存格式
    try:
        # 获取脚本所在目录的父目录（client同路径）
        script_dir = os.path.dirname(entry)
        parent_dir = os.path.dirname(script_dir) if script_dir else os.getcwd()
        
        # 查找邮件目录（支持多种格式）
        if os.path.exists(parent_dir):
            files = os.listdir(parent_dir)
            # 查找邮件目录（格式：emails_username_YYYYMMDD_HHMMSS 或 username_YYYYMMDD_HHMMSS）
            email_dirs = []
            for f in files:
                if os.path.isdir(os.path.join(parent_dir, f)):
                    # 检查是否包含邮件相关的关键词
                    if any(keyword in f.lower() for keyword in ['email', 'mail', 'emails']) or '_' in f:
                        email_dirs.append(f)
            
            for email_dir in email_dirs:
                email_dir_path = os.path.join(parent_dir, email_dir)
                try:
                    subfiles = os.listdir(email_dir_path)
                    if any(ext in f.lower() for f in subfiles for ext in ['.eml', '.msg', 'email', 'mail']):
                        print(f"✅ 检测到邮件文件目录: {email_dir}")
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    
    # 4. 如果stdout不为空且没有明显的失败标志，认为可能成功
    if stdout.strip() and not any(indicator in stdout for indicator in failure_indicators):
        print(f"✅ 脚本执行完成且无失败标志，认为成功")
        return True
    
    print(f"❌ 未检测到成功标志，stdout: {stdout[:200]}...")
    return False


def copy_successful_script(entry: str, templates_dir: str, attempt_dir: str, username: str = None, password: str = None, domain: str = None) -> str:
    """将成功的脚本复制到templates目录作为模板"""
    import shutil
    from datetime import datetime
    
    # 生成通用模板文件名
    if domain:
        safe_domain = "".join(c for c in domain if c.isalnum() or c in ('_', '-', '.')).strip()
        template_filename = f"email_downloader_{safe_domain}_template.py"
    else:
        template_filename = "email_downloader_template.py"
    
    template_path = os.path.join(templates_dir, template_filename)
    
    # 读取原始脚本内容
    with open(entry, 'r', encoding='utf-8') as f:
        script_content = f.read()
    
    # 替换脚本中的硬编码凭据为占位符，使其成为通用模板
    template_content = script_content
    if username:
        # 替换用户名
        import re
        template_content = re.sub(r'email_address\s*=\s*["\'][^"\']*["\']', 'email_address = "your_email@example.com"', template_content)
        template_content = re.sub(r'username\s*=\s*["\'][^"\']*["\']', 'username = "your_username"', template_content)
        template_content = re.sub(r'user\s*=\s*["\'][^"\']*["\']', 'user = "your_username"', template_content)
    
    if password:
        # 替换密码
        template_content = re.sub(r'password\s*=\s*["\'][^"\']*["\']', 'password = "your_password"', template_content)
        template_content = re.sub(r'passwd\s*=\s*["\'][^"\']*["\']', 'passwd = "your_password"', template_content)
        template_content = re.sub(r'auth_code\s*=\s*["\'][^"\']*["\']', 'auth_code = "your_auth_code"', template_content)
    
    # 在脚本开头添加模板说明
    template_header = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮箱下载模板脚本
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
原始邮箱: {username if username else '未知'}
邮箱域名: {domain if domain else '未知'}

使用方法:
1. 修改下面的邮箱配置信息
2. 运行脚本: python {template_filename}

注意: 请将下面的占位符替换为实际的邮箱凭据
"""

'''
    
    # 将模板说明添加到脚本开头
    if not template_content.startswith('#!/usr/bin/env python3'):
        template_content = template_header + template_content
    else:
        # 如果已有shebang，在它后面添加说明
        lines = template_content.split('\n')
        if len(lines) > 1:
            lines.insert(1, '')
            lines.insert(2, '# -*- coding: utf-8 -*-')
            lines.insert(3, '"""')
            lines.insert(4, f'邮箱下载模板脚本')
            lines.insert(5, f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            lines.insert(6, f'原始邮箱: {username if username else "未知"}')
            lines.insert(7, f'邮箱域名: {domain if domain else "未知"}')
            lines.insert(8, '')
            lines.insert(9, '使用方法:')
            lines.insert(10, '1. 修改下面的邮箱配置信息')
            lines.insert(11, f'2. 运行脚本: python {template_filename}')
            lines.insert(12, '')
            lines.insert(13, '注意: 请将下面的占位符替换为实际的邮箱凭据')
            lines.insert(14, '"""')
            lines.insert(15, '')
            template_content = '\n'.join(lines)
    
    # 保存模板文件
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write(template_content)
    
    return template_path


def extract_domain_from_email(email: str) -> str:
    """从邮箱地址中提取域名"""
    if not email or '@' not in email:
        return None
    
    domain = email.split('@')[1].strip().lower()
    return domain


def validate_email_address(email: str) -> bool:
    """验证邮箱地址格式"""
    if not email:
        return False
    
    import re
    # 简单的邮箱格式验证
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def generate_email_path_example(username: str, domain: str) -> str:
    """生成邮件保存路径示例"""
    if not username or not domain:
        return "email/域名/用户名/日期/邮件标题.eml"
    
    # 提取用户名部分（@之前的部分）
    user_part = username.split('@')[0] if '@' in username else username
    
    # 生成示例路径
    example_path = f"email/{domain}/{user_part}/20250902/邮件标题.eml"
    return example_path


def move_emails_to_client_path(attempt_dir: str, client_path: str, username: str = None) -> bool:
    """将邮件文件从attempt目录移动到claude_client.py同路径下"""
    import shutil
    from datetime import datetime
    
    try:
        # 查找attempt目录下的email文件夹
        email_source_dir = os.path.join(attempt_dir, "email")
        if not os.path.exists(email_source_dir):
            return False
        
        # 目标路径：claude_client.py同路径下的email目录
        email_target_dir = os.path.join(client_path, "email")
        
        # 如果提供了用户名，检查是否已存在该用户的邮件目录
        if username and os.path.exists(email_target_dir):
            domain = username.split('@')[1] if '@' in username else 'unknown'
            user_part = username.split('@')[0] if '@' in username else username
            
            # 检查是否已存在该用户的目录
            user_dir = os.path.join(email_target_dir, domain, user_part)
            if os.path.exists(user_dir):
                # 合并邮件目录，而不是备份整个email目录
                merge_user_emails(email_source_dir, email_target_dir, domain, user_part)
                print(f"📧 邮件已合并到: {user_dir}")
                return True
        
        # 如果目标目录已存在且没有用户名信息，先备份
        if os.path.exists(email_target_dir) and not username:
            backup_dir = f"{email_target_dir}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.move(email_target_dir, backup_dir)
            print(f"📁 已备份现有email目录到: {backup_dir}")
        
        # 移动整个email目录
        shutil.move(email_source_dir, email_target_dir)
        print(f"📧 邮件已移动到: {email_target_dir}")
        return True
        
    except Exception as e:
        print(f"❌ 移动邮件文件失败: {e}")
        return False


def handle_template_email_merge(client_path: str, username: str) -> bool:
    """处理模板执行后的邮件合并（脚本直接在client_path下执行）"""
    try:
        if not username:
            return True
            
        domain = username.split('@')[1] if '@' in username else 'unknown'
        user_part = username.split('@')[0] if '@' in username else username
        
        email_target_dir = os.path.join(client_path, "email")
        user_dir = os.path.join(email_target_dir, domain, user_part)
        
        if os.path.exists(user_dir):
            print(f"📧 邮件已保存到: {user_dir}")
        else:
            print(f"📧 邮件已保存到: {email_target_dir}")
        
        return True
        
    except Exception as e:
        print(f"❌ 处理邮件目录失败: {e}")
        return False


def merge_user_emails(source_dir: str, target_dir: str, domain: str, user_part: str) -> None:
    """合并用户邮件目录"""
    import shutil
    
    try:
        # 源用户目录
        source_user_dir = os.path.join(source_dir, domain, user_part)
        if not os.path.exists(source_user_dir):
            return
        
        # 目标用户目录
        target_user_dir = os.path.join(target_dir, domain, user_part)
        os.makedirs(target_user_dir, exist_ok=True)
        
        # 遍历源目录中的所有日期目录
        for date_dir in os.listdir(source_user_dir):
            source_date_dir = os.path.join(source_user_dir, date_dir)
            if os.path.isdir(source_date_dir):
                target_date_dir = os.path.join(target_user_dir, date_dir)
                
                # 如果目标日期目录已存在，合并文件
                if os.path.exists(target_date_dir):
                    for file in os.listdir(source_date_dir):
                        source_file = os.path.join(source_date_dir, file)
                        target_file = os.path.join(target_date_dir, file)
                        
                        # 如果目标文件已存在，重命名源文件
                        if os.path.exists(target_file):
                            name, ext = os.path.splitext(file)
                            counter = 1
                            while os.path.exists(target_file):
                                new_name = f"{name}_{counter}{ext}"
                                target_file = os.path.join(target_date_dir, new_name)
                                counter += 1
                        
                        shutil.move(source_file, target_file)
                else:
                    # 直接移动整个日期目录
                    shutil.move(source_date_dir, target_date_dir)
        
        # 清理空的源目录
        try:
            shutil.rmtree(source_dir)
        except Exception:
            pass
            
    except Exception as e:
        print(f"❌ 合并邮件目录失败: {e}")


def find_existing_template(domain: str = None) -> str:
    """查找已存在的模板文件"""
    templates_dir = "templates"
    if not os.path.exists(templates_dir):
        return None
    
    if domain:
        safe_domain = "".join(c for c in domain if c.isalnum() or c in ('_', '-', '.')).strip()
        template_filename = f"email_downloader_{safe_domain}_template.py"
    else:
        template_filename = "email_downloader_template.py"
    
    template_path = os.path.join(templates_dir, template_filename)
    print(f"🔍 检查模板文件: {template_path}")
    if os.path.exists(template_path):
        print(f"✅ 模板文件已存在: {template_path}")
        return template_path
    print(f"❌ 模板文件不存在: {template_path}")
    return None


def generate_email_prompt(base_prompt: str, username: str = None, password: str = None, 
                         domain: str = None, imap_server: str = None, imap_port: int = None) -> str:
    """根据命令行参数生成增强的邮箱下载提示"""
    
    # 基础提示
    enhanced_prompt = base_prompt
    
    # 添加邮箱参数信息
    email_params = []
    
    if domain:
        email_params.append(f"邮箱域名: {domain}")
        # 如果提供了域名但没有提供IMAP服务器，让AI自动推断
        if not imap_server:
            email_params.append("请根据域名自动推断IMAP服务器地址和端口")
    
    if imap_server:
        email_params.append(f"IMAP服务器: {imap_server}")
    
    if imap_port:
        email_params.append(f"IMAP端口: {imap_port}")
    
    if username:
        email_params.append(f"用户名: {username}")
        enhanced_prompt += f"\n\n重要：用户名已提供为 '{username}'，脚本必须直接使用此用户名，不要硬编码或提示用户输入。"
        enhanced_prompt += f"\n示例：email_address = '{username}'  # 直接使用提供的用户名"
    
    if password:
        # 根据域名判断认证方式
        auth_type = "授权码" if domain and any(d in domain.lower() for d in ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', '163.com', 'qq.com']) else "密码"
        email_params.append(f"{auth_type}: [已提供]")
        enhanced_prompt += f"\n\n重要：{auth_type}已提供，脚本必须直接使用此{auth_type}，不要硬编码或提示用户输入。"
        enhanced_prompt += f"\n示例：password = 'your_actual_password'  # 直接使用提供的{auth_type}"
    
    # 如果有任何邮箱参数，添加到提示中
    if email_params:
        enhanced_prompt += f"\n\n邮箱配置信息：\n" + "\n".join(f"- {param}" for param in email_params)
    
    # 添加脚本要求
    enhanced_prompt += "\n\n脚本要求："
    enhanced_prompt += "\n1. 如果提供了用户名和密码/授权码，必须直接使用，绝对不要硬编码或提示用户输入"
    enhanced_prompt += "\n2. 如果提供了IMAP服务器和端口，必须直接使用"
    enhanced_prompt += "\n3. 如果没有提供IMAP信息，请根据域名自动推断（如 rambler.ru -> imap.rambler.ru:993）"
    enhanced_prompt += "\n4. 认证方式判断：Gmail、Outlook、Yahoo、163、QQ等主流邮箱使用授权码，其他邮箱使用密码"
    enhanced_prompt += "\n5. 脚本执行后应显示明确的成功或失败信息"
    enhanced_prompt += "\n6. 成功下载邮件后应显示下载的邮件数量"
    enhanced_prompt += "\n7. 脚本中不要包含任何硬编码的用户名、密码或邮箱地址"
    enhanced_prompt += "\n8. 所有配置信息都应该从提供的参数中获取"
    # 生成具体的邮件保存路径示例
    if username and domain:
        path_example = generate_email_path_example(username, domain)
        enhanced_prompt += f"\n9. 邮件保存路径结构：{path_example}，保存到脚本同目录下"
        enhanced_prompt += f"\n10. 重要：一次执行脚本使用一个日期，所有邮件都保存在同一个日期目录下，不要每封邮件创建不同的日期目录"
    else:
        enhanced_prompt += "\n9. 邮件保存路径结构：email/域名/用户名/执行日期/邮件标题.eml，保存到脚本同目录下"
        enhanced_prompt += f"\n10. 重要：一次执行脚本使用一个日期，所有邮件都保存在同一个日期目录下"
    
    return enhanced_prompt


def query_imap_server(api_key: str, domain: str, model: str, max_tokens: int, system: str | None,
                      api_url: str, timeout: float, retries: int) -> tuple[str, int]:
    """查询指定域名的真实IMAP服务器地址和端口"""
    query_prompt = f"""请查询域名 {domain} 的真实IMAP服务器地址和端口。

请按以下格式返回结果：
IMAP_SERVER: [真实的IMAP服务器地址]
IMAP_PORT: [端口号，通常是993]

例如：
IMAP_SERVER: imap.gmail.com
IMAP_PORT: 993

注意：
1. 不要包含任何其他文字，只返回上述格式
2. 如果域名是 zohomail.com，真实IMAP地址可能是 zoho.com
3. 如果域名是 outlook.com，真实IMAP地址可能是 outlook.office365.com
4. 端口通常是993（SSL）或143（非SSL），优先使用993"""
    
    resp = one_shot_call(api_key, query_prompt, model, max_tokens, system, api_url=api_url, timeout=timeout, retries=retries)
    
    if resp.get("error"):
        print(f"查询IMAP服务器失败: {resp}")
        return domain, 993  # 返回默认值
    
    body = resp.get("body", {})
    text = extract_text_from_body(body)
    
    # 解析返回的IMAP服务器信息
    imap_server = domain  # 默认值
    imap_port = 993       # 默认值
    
    try:
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('IMAP_SERVER:'):
                imap_server = line.split(':', 1)[1].strip()
            elif line.startswith('IMAP_PORT:'):
                imap_port = int(line.split(':', 1)[1].strip())
    except Exception as e:
        print(f"解析IMAP服务器信息失败: {e}")
    
    print(f"查询到 {domain} 的IMAP服务器: {imap_server}:{imap_port}")
    return imap_server, imap_port


def auto_codegen_pipeline(api_key: str, base_prompt: str, model: str, max_tokens: int, system: str | None,
                          templates_root: str, preferred_language: str, entry_filename: str,
                          api_url: str, timeout: float, retries: int, max_attempts: int,
                          username: str = None, password: str = None, domain: str = None, 
                          imap_server: str = None, imap_port: int = None, auto_query_imap: bool = False) -> None:
    
    # 首先检查是否有现有的模板可以使用
    existing_template = find_existing_template(domain)
    if existing_template:
        print(f"🎯 发现现有模板: {existing_template}")
        print("📝 使用现有模板，跳过AI生成...")
        
        # 创建templates目录
        templates_dir = "templates"
        os.makedirs(templates_dir, exist_ok=True)
        
        # 读取模板内容并替换凭据
        with open(existing_template, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # 替换凭据
        modified_content = replace_hardcoded_credentials(template_content, username, password)
        
        # 执行脚本（在client同路径下执行，避免路径问题）
        client_path = os.path.dirname(os.path.abspath(__file__))
        
        # 创建临时脚本文件在client_path下，确保UTF-8编码
        temp_script_path = os.path.join(client_path, f"temp_{os.path.basename(existing_template)}")
        import codecs
        with codecs.open(temp_script_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        print(f"🚀 执行模板脚本: {existing_template}")
        run_result = run_python_file(temp_script_path, cwd=client_path)
        
        # 检查是否成功
        success = check_script_success(run_result, client_path, temp_script_path)
        
        if success:
            # 处理邮件目录（脚本直接在client_path下执行，无需移动）
            handle_template_email_merge(client_path, username)
            
            # 清理临时文件
            try:
                os.remove(temp_script_path)
            except Exception:
                pass
            
            print(f"\n🎉 模板脚本执行成功！")
            print(f"📁 使用模板: {existing_template}")
            print(f"📧 目标邮箱: {username if username else '未知'}")
            print(f"🌐 邮箱域名: {domain if domain else '未知'}")
            print(json.dumps({"type": "template_success", "template": existing_template, "username": username, "domain": domain}, ensure_ascii=False))
            return  # 成功执行模板，直接返回
        else:
            print(f"\n❌ 模板脚本执行失败，将使用AI重新生成...")
            # 继续执行AI生成流程
    
    # 如果没有现有模板或模板执行失败，使用AI生成
    if not existing_template:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        root_dir = os.path.join(templates_root, f"gen_{ts}")
        os.makedirs(root_dir, exist_ok=True)
        
        # 如果启用了自动查询IMAP且提供了域名但没有提供IMAP服务器信息，先查询真实的IMAP地址
        if domain and not imap_server and auto_query_imap:
            print(f"正在查询 {domain} 的真实IMAP服务器地址...")
            imap_server, imap_port = query_imap_server(api_key, domain, model, max_tokens, system, api_url, timeout, retries)
        
        # 生成增强的提示（仅在第一次尝试时添加邮箱参数）
        current_prompt = generate_email_prompt(base_prompt, username, password, domain, imap_server, imap_port)
        
        for attempt in range(1, max(1, max_attempts) + 1):
            attempt_dir = os.path.join(root_dir, f"attempt_{attempt}")
            os.makedirs(attempt_dir, exist_ok=True)
            resp = one_shot_call(api_key, current_prompt, model, max_tokens, system, api_url=api_url, timeout=timeout, retries=retries)
            with open(os.path.join(attempt_dir, 'response.json'), 'w', encoding='utf-8') as f:
                json.dump(resp, f, ensure_ascii=False, indent=2)
            if resp.get("error"):
                with open(os.path.join(attempt_dir, 'error.json'), 'w', encoding='utf-8') as f:
                    json.dump(resp, f, ensure_ascii=False, indent=2)
                print(json.dumps({"type": "auto_codegen", "attempt": attempt, "status": "api_error", "dir": attempt_dir}, ensure_ascii=False))
                break
            body = resp.get("body", {})
            text = extract_text_from_body(body)
            with open(os.path.join(attempt_dir, 'answer.txt'), 'w', encoding='utf-8') as f:
                f.write(text)
            code_blocks = extract_code_blocks(text, preferred_language=preferred_language)
            meta = save_code_template(root_dir, attempt_dir, code_blocks, preferred_language, entry_filename, username, password)
            entry = meta.get("entry")
            if not entry or not os.path.isfile(entry):
                print(json.dumps({"type": "auto_codegen", "attempt": attempt, "status": "no_entry", "dir": attempt_dir}, ensure_ascii=False))
                current_prompt = base_prompt + f"\n\n请仅返回```{preferred_language}```代码块，并包含完整可运行的代码。不要包含任何解释文字，只输出代码。"
                continue
            # 在client_path下执行脚本，避免嵌套email目录
            client_path = os.path.dirname(os.path.abspath(__file__))
            
            # 将脚本复制到client_path下执行
            script_name = os.path.basename(entry)
            temp_script_path = os.path.join(client_path, f"temp_{script_name}")
            
            # 读取脚本内容并复制
            with open(entry, 'r', encoding='utf-8') as f:
                script_content = f.read()
            
            # 替换硬编码凭据
            modified_content = replace_hardcoded_credentials(script_content, username, password)
            
            # 保存到client_path下
            import codecs
            with codecs.open(temp_script_path, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            # 执行脚本
            run_result = run_python_file(temp_script_path, cwd=client_path)
            
            # 清理临时文件
            try:
                os.remove(temp_script_path)
            except Exception:
                pass
            with open(os.path.join(attempt_dir, 'stdout.txt'), 'w', encoding='utf-8') as f:
                f.write(run_result.get('stdout', ''))
            with open(os.path.join(attempt_dir, 'stderr.txt'), 'w', encoding='utf-8') as f:
                f.write(run_result.get('stderr', ''))
            with open(os.path.join(attempt_dir, 'exit_code.txt'), 'w', encoding='utf-8') as f:
                f.write(str(run_result.get('returncode', 0)))
            
            # 保存当前脚本内容到文件，方便调试
            if entry and os.path.exists(entry):
                try:
                    with open(entry, 'r', encoding='utf-8') as f:
                        script_content = f.read()
                    import codecs
                    with codecs.open(os.path.join(attempt_dir, 'current_script.py'), 'w', encoding='utf-8') as f:
                        f.write(script_content)
                except Exception:
                    pass
            # 检查是否真正成功：不仅没有语法错误，还要检查是否成功下载了邮件
            success = check_script_success(run_result, client_path, entry)
            
            if success:
                # 处理邮件目录（脚本直接在client_path下执行，无需移动）
                handle_template_email_merge(client_path, username)
                
                # 成功时，将脚本复制到templates目录作为模板
                templates_dir = "templates"
                os.makedirs(templates_dir, exist_ok=True)
                template_script_path = copy_successful_script(entry, templates_dir, attempt_dir, username, password, domain)
                
                print(f"\n🎉 脚本生成成功！")
                print(f"📁 模板脚本已保存到: {template_script_path}")
                print(f"📧 目标邮箱: {username if username else '未知'}")
                print(f"🌐 邮箱域名: {domain if domain else '未知'}")
                print(f"📝 尝试次数: {attempt}")
                print(json.dumps({"type": "auto_codegen", "attempt": attempt, "status": "success", "dir": attempt_dir, "entry": entry, "template_script": template_script_path}, ensure_ascii=False))
                break
            # 收集错误信息：包括stderr和stdout（可能包含登录失败等信息）
            err = run_result.get('stderr', '')
            out = run_result.get('stdout', '')
            
            # 读取上次生成的脚本内容
            last_script_content = ""
            try:
                if entry and os.path.exists(entry):
                    with open(entry, 'r', encoding='utf-8') as f:
                        last_script_content = f.read()
            except Exception:
                pass
            
            # 合并错误信息，优先显示stderr，然后显示stdout中的错误信息
            error_info = ""
            if err.strip():
                error_info += f"错误输出:\n{err}\n\n"
            if out.strip():
                error_info += f"程序输出:\n{out}\n\n"
            
            # 如果没有任何输出，说明可能是静默失败
            if not error_info.strip():
                error_info = "脚本执行完成但没有明显的成功标志，请检查登录和下载逻辑。"
            
            # 构建包含上次脚本和错误信息的提示
            retry_prompt = f"""上次生成的脚本执行失败，请基于以下脚本进行修复：

=== 上次生成的脚本 ===
```python
{last_script_content}
```

=== 执行结果 ===
{error_info}

请修复上述脚本中的问题，返回完整可运行的```{preferred_language}```代码。注意：
1. 保持脚本的基本结构和逻辑
2. 只修复导致错误的部分
3. 不要完全重写脚本
4. 确保修复后的脚本能够成功下载邮件
5. 重要：如果提供了用户名和密码/授权码，必须直接使用，不要硬编码或提示用户输入
6. 脚本中不要包含任何硬编码的用户名、密码或邮箱地址"""
            
            # 限制提示长度，避免超过API限制
            if len(retry_prompt) > 8000:
                # 如果太长，截取关键部分
                script_preview = last_script_content[:2000] + "\n... (脚本内容过长，已截取)" if len(last_script_content) > 2000 else last_script_content
                error_preview = error_info[-2000:] if len(error_info) > 2000 else error_info
                retry_prompt = f"""上次生成的脚本执行失败，请基于以下脚本进行修复：

=== 上次生成的脚本（部分） ===
```python
{script_preview}
```

=== 执行结果 ===
{error_preview}

请修复上述脚本中的问题，返回完整可运行的```{preferred_language}```代码。注意：如果提供了用户名和密码/授权码，必须直接使用，不要硬编码或提示用户输入。"""
            
            current_prompt = retry_prompt
            print(json.dumps({"type": "auto_codegen", "attempt": attempt, "status": "retry", "dir": attempt_dir}, ensure_ascii=False))

def load_api_key(args) -> str:
        # 1) 显式指定 --key_file
        if args.key_file:
            if os.path.isfile(args.key_file):
                try:
                    with open(args.key_file, 'r', encoding='utf-8') as f:
                        return f.read().strip()
                except Exception:
                    pass
            print(json.dumps({"type": "error", "message": f"指定的key文件不存在或不可读: {args.key_file}"}, ensure_ascii=False))
            sys.exit(1)

        # 2) 当前目录默认文件名 'key'
        cwd_key = os.path.join(os.getcwd(), 'key')
        if os.path.isfile(cwd_key):
            try:
                with open(cwd_key, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception:
                pass

        # 3) 环境变量回退
        env_key = os.environ.get("ANTHROPIC_API_KEY")
        if env_key:
            return env_key.strip()

        print(json.dumps({"type": "error", "message": "未找到API Key。请设置环境变量ANTHROPIC_API_KEY或在当前目录创建'key'文件，或使用--key_file指定"}, ensure_ascii=False))
        sys.exit(1)

def download_emails(args):
    api_key = load_api_key(args)
    
    # 验证邮箱地址格式
    if args.username and not validate_email_address(args.username):
        print(json.dumps({"type": "error", "message": f"无效的邮箱地址格式: {args.username}"}, ensure_ascii=False))
        sys.exit(1)
    
    # 如果没有提供域名，从用户名中自动提取
    if not args.domain and args.username:
        extracted_domain = extract_domain_from_email(args.username)
        if extracted_domain:
            args.domain = extracted_domain
            print(f"🔍 从邮箱地址自动提取域名: {args.domain}")
        else:
            print(json.dumps({"type": "error", "message": f"无法从邮箱地址提取域名: {args.username}"}, ensure_ascii=False))
            sys.exit(1)
    
    # 如果没有提供prompt，使用默认的邮箱下载提示
    if not args.prompt and not args.stdin_json:
        args.prompt = "你现在是专业的代码开发人员，帮我实现一个可以自动以imap协议登录邮箱的python脚本，并可以实现自动获取全部邮件，并保存到本地。脚本需要：1）根据邮箱域名智能判断认证方式：Gmail、Outlook、Yahoo等主流邮箱使用授权码，其他邮箱可能使用密码；2）使用IMAP协议连接邮箱服务器；3）获取所有邮件并保存到本地，邮件保存路径结构为：email/域名/用户名/执行日期/邮件标题.eml（如：email/yahoo.com/suttonandrew40700/20250902/邮件标题.eml），注意：一次执行脚本使用一个日期，所有邮件都保存在同一个日期目录下；4）显示执行进度和结果。只要python脚本的代码，其他什么回答都不需要"



    if args.stdin_json:
        try:
            cfg = read_stdin_json()
        except Exception as e:
            print(json.dumps({"type": "error", "message": f"读取stdin JSON失败: {e}"}, ensure_ascii=False))
            sys.exit(1)
        prompt = cfg.get("prompt")
        model = cfg.get("model", args.model)
        max_tokens = int(cfg.get("max_tokens", args.max_tokens))
        system = cfg.get("system", args.system)
        if not prompt:
            print(json.dumps({"type": "error", "message": "stdin JSON缺少prompt"}, ensure_ascii=False))
            sys.exit(1)
        resp = one_shot_call(api_key, prompt, model, max_tokens, system, api_url=args.api_url, timeout=args.timeout, retries=max(1, args.retries))
        print(json.dumps(resp, ensure_ascii=False))
        return

    if args.prompt is not None:
        if args.auto_codegen:
            auto_codegen_pipeline(api_key, args.prompt, args.model, args.max_tokens, args.system, args.templates_root, args.code_lang, args.entry_filename, args.api_url, args.timeout, max(1, args.retries), max(1, args.max_attempts), args.username, args.password, args.domain, args.imap_server, args.imap_port, args.auto_query_imap)
        else:
            resp = one_shot_call(api_key, args.prompt, args.model, args.max_tokens, args.system, api_url=args.api_url, timeout=args.timeout, retries=max(1, args.retries))
            print(json.dumps(resp, ensure_ascii=False))
        return

    # 交互模式
    conversation_loop(api_key, args.model, args.max_tokens, args.system, api_url=args.api_url, timeout=args.timeout, retries=max(1, args.retries))


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Messages API JSON客户端")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="模型名称")
    parser.add_argument("--max_tokens", type=int, default=50000, help="回答最大tokens")
    parser.add_argument("--system", default=None, help="System提示词")
    parser.add_argument("--prompt", default=None, help="单次调用的用户问题。如果省略则进入交互模式或从stdin读取JSON")
    parser.add_argument("--stdin_json", action="store_true", help="从stdin读取JSON：{prompt, model, max_tokens, system}")

    parser.add_argument("--key_file", default=None, help="从本地文件读取API Key（默认优先读取当前目录下的key文件）")
    parser.add_argument("--api_url", default=ANTHROPIC_API_URL, help="自定义API URL（默认 https://api.anthropic.com/v1/messages）")
    parser.add_argument("--timeout", type=float, default=30.0, help="请求超时时间（秒）")
    parser.add_argument("--retries", type=int, default=2, help="网络错误时重试次数")
    parser.add_argument("--auto_codegen", action="store_true", help="启用自动代码生成与运行，错误将反馈给AI重试")
    parser.add_argument("--templates_root", default="log", help="日志输出根目录")
    parser.add_argument("--code_lang", default="python", help="首选代码语言（默认python）")
    parser.add_argument("--entry_filename", default="", help="主入口文件名（留空则自动选择第一个保存的 .py 文件）")
    parser.add_argument("--max_attempts", type=int, default=2, help="自动重试最大次数")

    # 邮箱相关参数
    parser.add_argument("--username", default=None, help="邮箱地址（如 user@example.com，如果提供，脚本将自动使用此邮箱）")
    parser.add_argument("--password", default=None, help="邮箱密码/授权码（如果提供，脚本将自动使用此密码）")
    parser.add_argument("--domain", default=None, help="邮箱域名（可选，如 rambler.ru, gmail.com 等，留空则从用户名自动提取）")
    parser.add_argument("--imap_server", default=None, help="IMAP服务器地址（如 imap.rambler.ru，留空则AI自动推断）")
    parser.add_argument("--imap_port", type=int, default=None, help="IMAP端口（如 993，留空则AI自动推断）")
    parser.add_argument("--auto_query_imap", action="store_true", help="自动查询域名的真实IMAP服务器地址（推荐）")

    args = parser.parse_args()

    download_emails(args)


    

if __name__ == "__main__":
    main()


