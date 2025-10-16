# -*- coding: utf-8 -*-

import os
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request
from functools import wraps
from database import get_templates, get_template_by_name, insert_template, update_template, delete_template
import json
from ai.claude_client import one_shot_call, extract_text_from_body, load_api_key
import argparse

# 创建蓝图
template_bp = Blueprint('templates', __name__)


def extract_template_fields_with_ai(template_code):
    """使用Claude AI自动提取模板代码中的字段信息"""
    try:
        # 获取API Key
        args = argparse.Namespace(key_file=None)
        api_key = load_api_key(args)

        # 构建提示词
        prompt = f"""请分析以下Python模板代码，提取其中的配置信息。

代码：
```python
{template_code}
```

请严格按照以下JSON格式返回结果（只返回JSON，不要包含任何其他文字）：
{{
    "server_address": "服务器地址（如：imap.gmail.com, outlook.office365.com等，如果找不到则为空字符串）",
    "protocol_type": "协议类型（如：imap, smtp, pop3, web等，如果找不到则为空字符串）",
    "port": 端口号（如：993, 587, 443等，如果找不到则为null）,
    "type": "模板类型（根据代码判断是email, cookie, web还是api，默认为default）",
    "api_address": "API地址（如果代码中有API调用，提取URL，否则为空字符串）",
    "login_address": "登录页面地址（如果是web类型，提取登录URL，否则为空字符串）",
    "redirect_address": "重定向地址（如果代码中有重定向逻辑，提取URL，否则为空字符串）"
}}

注意：
1. 如果是IMAP邮件下载脚本，协议类型应该是"imap"
2. 如果是Web自动化脚本（使用selenium），协议类型应该是"web"
3. 如果是Cookie下载脚本，协议类型应该是"cookie"
4. 端口号必须是整数或null
5. 所有字符串字段如果找不到对应信息，应该返回空字符串""而不是null
6. 只返回JSON，不要包含任何解释性文字"""

        # 调用Claude API
        response = one_shot_call(
            api_key=api_key,
            prompt=prompt,
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=None,
            api_url="https://api.anthropic.com/v1/messages",
            timeout=30.0,
            retries=2
        )

        if response.get("error"):
            return None, f"API调用失败: {response.get('body', {}).get('message', 'Unknown error')}"

        # 提取文本内容
        body = response.get("body", {})
        text = extract_text_from_body(body)

        # 解析JSON
        # 移除可能的markdown代码块标记
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            result = json.loads(text)
            return result, None
        except json.JSONDecodeError as e:
            return None, f"解析JSON失败: {str(e)}, 原始内容: {text[:200]}"

    except Exception as e:
        return None, f"提取字段时出错: {str(e)}"


def init_templates_from_filesystem():
    """初始化函数：将文件系统中的模板导入到数据库中（如果数据库中不存在）"""
    try:
        templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')

        # 如果模板目录不存在，创建它
        if not os.path.exists(templates_dir):
            os.makedirs(templates_dir, exist_ok=True)
            return

        # 遍历模板目录中的所有.py文件
        for filename in os.listdir(templates_dir):
            if filename.endswith('.py'):
                # 从文件名中提取模板名称（去掉.py后缀）
                template_name = filename.replace('.py', '')

                # 检查数据库中是否已存在该模板
                if not get_template_by_name(template_name) and not get_template_by_name(filename):
                    # 如果不存在，插入到数据库中
                    # 注意：这里我们使用文件名作为path，而将去掉.py后缀的作为name
                    # 同时设置默认的服务器地址、协议类型和端口
                    insert_template(
                        name=template_name,
                        path=filename,
                        server_address='',
                        protocol_type='',
                        port=None,
                        type='default',
                        api_address='',
                        login_address='',
                        redirect_address='',
                        web_dom=''
                    )

    except Exception as e:
        print(f"初始化模板数据时出错: {str(e)}")


def register_template_routes(app, login_required, api_key_or_login_required):
    # 初始化模板数据
    init_templates_from_filesystem()
    # 这里使用传入的装饰器
    
    @app.route('/templates')
    @login_required
    def templates():
        """模板管理主页面"""
        return render_template('templates.html')


    @app.route('/api/templates', methods=['GET'])
    @api_key_or_login_required
    def api_get_templates():
        """获取所有模板列表"""
        try:
            # 从数据库获取模板列表
            db_templates = get_templates()
            templates = []
            
            for template in db_templates:
                # 根据模板路径获取文件信息
                templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
                filepath = os.path.join(templates_dir, template['path'])
                
                if os.path.exists(filepath):
                    stat = os.stat(filepath)
                    # 确保 web_dom 是字符串类型
                    web_dom_str = template.get('web_dom', '{}')
                    if web_dom_str is None:
                        web_dom_str = '{}'
                    try:
                        web_dom_json = json.loads(web_dom_str)
                    except (json.JSONDecodeError, TypeError):
                        web_dom_json = {}
                    template_info = {
                        'name': template['name'],
                        'path': template['path'],
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'server_address': template['server_address'],
                        'protocol_type': template['protocol_type'],
                        'port': template['port'],
                        'type': template.get('type', 'default'),
                        'api_address': template.get('api_address'),
                        'login_address': template.get('login_address'),
                        'redirect_address': template.get('redirect_address'),
                        'web_dom': web_dom_json,
                        'created_at': template['created_at'],
                        'updated_at': template['updated_at']
                    }
                    templates.append(template_info)
            
            templates.sort(key=lambda x: x['name'])
            return jsonify({'success': True, 'templates': templates})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/templates/<template_name>', methods=['GET'])
    @api_key_or_login_required
    def api_get_template(template_name):
        """获取单个模板内容"""
        try:
            # 从数据库获取模板信息
            template = get_template_by_name(template_name)
            
            if not template:
                return jsonify({'success': False, 'error': '模板不存在'}), 404
            
            # 根据模板路径读取文件内容
            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            filepath = os.path.join(templates_dir, template['path'])
            
            if not os.path.exists(filepath):
                return jsonify({'success': False, 'error': '模板文件不存在'}), 404
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # 确保 web_dom 是字符串类型
            web_dom_str = template.get('web_dom', '{}')
            if web_dom_str is None:
                web_dom_str = '{}'
            try:
                web_dom_json = json.loads(web_dom_str)
            except (json.JSONDecodeError, TypeError):
                web_dom_json = {}
            
            # 返回模板内容和数据库中的模板信息
            return jsonify({
                'success': True, 
                'content': content, 
                'name': template['name'],
                'path': template['path'],
                'server_address': template['server_address'],
                'protocol_type': template['protocol_type'],
                'port': template['port'],
                'type': template.get('type', 'default'),
                'api_address': template.get('api_address'),
                'login_address': template.get('login_address'),
                'redirect_address': template.get('redirect_address'),
                'web_dom': web_dom_json,
                'created_at': template['created_at'],
                'updated_at': template['updated_at']
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/templates/<template_name>', methods=['PUT'])
    @api_key_or_login_required
    def api_update_template(template_name):
        """更新模板内容"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': '缺少更新数据'}), 400
            
            # 检查模板是否存在
            template = get_template_by_name(template_name)
            if not template:
                return jsonify({'success': False, 'error': '模板不存在'}), 404
            
            # 更新文件内容（如果提供了）
            if 'content' in data:
                templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
                filepath = os.path.join(templates_dir, template['path'])
                
                if not os.path.exists(filepath):
                    return jsonify({'success': False, 'error': '模板文件不存在'}), 404
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(data['content'])
            
            # 验证web_dom字段是否为有效的JSON格式（如果提供了）
            web_dom = data.get('web_dom')
            if web_dom:
                import json
                try:
                    web_dom_json = json.loads(web_dom)
                    # 检查是否包含必要的字段
                    if not isinstance(web_dom_json, dict):
                        return jsonify({'success': False, 'error': 'web_dom必须是JSON对象格式'}), 400
                    
                    # 重新格式化JSON字符串，确保格式统一
                    web_dom = json.dumps(web_dom_json, ensure_ascii=False)
                except json.JSONDecodeError:
                    return jsonify({'success': False, 'error': 'web_dom不是有效的JSON格式'}), 400
            
            # 更新数据库记录
            update_template(
                template_name,
                path=data.get('path'),
                server_address=data.get('server_address'),
                protocol_type=data.get('protocol_type'),
                port=data.get('port'),
                type=data.get('type'),
                api_address=data.get('api_address'),
                login_address=data.get('login_address'),
                redirect_address=data.get('redirect_address'),
                web_dom=web_dom
            )
            
            return jsonify({'success': True, 'message': '模板更新成功'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/templates', methods=['POST'])
    @api_key_or_login_required
    def api_create_template():
        """创建新模板"""
        try:
            data = request.get_json()
            if not data or 'name' not in data or 'content' not in data:
                return jsonify({'success': False, 'error': '缺少模板名称或内容'}), 400
            
            template_name = data['name']
            content = data['content']
            server_address = data.get('server_address')
            protocol_type = data.get('protocol_type')
            port = data.get('port')
            type = data.get('type', 'default')
            api_address = data.get('api_address')
            login_address = data.get('login_address')
            redirect_address = data.get('redirect_address')
            web_dom = data.get('web_dom')
            
            # 验证web_dom字段是否为有效的JSON格式
            if web_dom:
                import json
                try:
                    web_dom_json = json.loads(web_dom)
                    # 检查是否包含必要的字段
                    if not isinstance(web_dom_json, dict):
                        return jsonify({'success': False, 'error': 'web_dom必须是JSON对象格式'}), 400
                    
                    # 重新格式化JSON字符串，确保格式统一
                    web_dom = json.dumps(web_dom_json, ensure_ascii=False)
                except json.JSONDecodeError:
                    return jsonify({'success': False, 'error': 'web_dom不是有效的JSON格式'}), 400
            
            # 默认path为模板名称，确保以.py结尾
            path = template_name
            if not path.endswith('.py'):
                path += '.py'
            
            # 保存文件
            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            os.makedirs(templates_dir, exist_ok=True)
            filepath = os.path.join(templates_dir, path)
            
            if os.path.exists(filepath):
                return jsonify({'success': False, 'error': '模板文件已存在'}), 400
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 插入数据库记录
            success = insert_template(template_name, path, server_address, protocol_type, port, type, api_address, login_address, redirect_address, web_dom)
            if not success:
                # 如果数据库插入失败，删除已创建的文件
                os.remove(filepath)
                return jsonify({'success': False, 'error': '模板名称已存在'}), 400
            
            return jsonify({
                'success': True, 
                'message': '模板创建成功', 
                'name': template_name,
                'path': path,
                'server_address': server_address,
                'protocol_type': protocol_type,
                'port': port,
                'type': type,
                'api_address': api_address,
                'login_address': login_address,
                'redirect_address': redirect_address,
                'web_dom': web_dom
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/templates/<template_name>/copy', methods=['POST'])
    @api_key_or_login_required
    def api_copy_template(template_name):
        """复制模板"""
        try:
            data = request.get_json()
            new_name = data.get('new_name')
            
            # 获取源模板信息
            source_template = get_template_by_name(template_name)
            
            if not source_template:
                return jsonify({'success': False, 'error': '源模板不存在'}), 404
            
            # 生成新文件名和路径
            if not new_name:
                base_name = template_name.replace('.py', '')
                new_name = f"{base_name}_copy"
                counter = 1
                # 检查新名称是否已存在
                while get_template_by_name(new_name) or get_template_by_name(f"{new_name}.py"):
                    new_name = f"{base_name}_copy{counter}"
                    counter += 1
            
            new_path = new_name
            if not new_path.endswith('.py'):
                new_path += '.py'
            
            # 复制文件
            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            source_filepath = os.path.join(templates_dir, source_template['path'])
            dest_filepath = os.path.join(templates_dir, new_path)
            
            if not os.path.exists(source_filepath):
                return jsonify({'success': False, 'error': '源模板文件不存在'}), 404
            
            if os.path.exists(dest_filepath):
                return jsonify({'success': False, 'error': '目标文件已存在'}), 400
            
            with open(source_filepath, 'r', encoding='utf-8') as src:
                content = src.read()
            
            with open(dest_filepath, 'w', encoding='utf-8') as dest:
                dest.write(content)
            
            # 验证并处理web_dom字段
            web_dom = source_template.get('web_dom')
            if web_dom:
                import json
                try:
                    web_dom_json = json.loads(web_dom)
                    # 检查是否包含必要的字段
                    if not isinstance(web_dom_json, dict):
                        web_dom = ''  # 如果不是有效的JSON对象，设置为空字符串
                    elif 'email_input' not in web_dom_json or 'password_input' not in web_dom_json:
                        # 如果缺少必要的字段，补充默认值
                        web_dom_json.setdefault('email_input', '')
                        web_dom_json.setdefault('password_input', '')
                        web_dom = json.dumps(web_dom_json, ensure_ascii=False)
                except json.JSONDecodeError:
                    web_dom = ''  # 如果不是有效的JSON格式，设置为空字符串
            
            # 插入新模板到数据库
            success = insert_template(
                new_name, 
                new_path, 
                source_template['server_address'], 
                source_template['protocol_type'], 
                source_template['port'], 
                source_template.get('type', 'default'),
                source_template.get('api_address'),
                source_template.get('login_address'),
                source_template.get('redirect_address'),
                web_dom
            )
            if not success:
                # 如果数据库插入失败，删除已创建的文件
                os.remove(dest_filepath)
                return jsonify({'success': False, 'error': '模板名称已存在'}), 400
            
            return jsonify({
                'success': True, 
                'message': '模板复制成功', 
                'new_name': new_name, 
                'new_path': new_path,
                'server_address': source_template['server_address'],
                'protocol_type': source_template['protocol_type'],
                'port': source_template['port'],
                'type': source_template.get('type', 'default'),
                'api_address': source_template.get('api_address'),
                'login_address': source_template.get('login_address'),
                'redirect_address': source_template.get('redirect_address'),
                'web_dom': web_dom
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/templates/<template_name>', methods=['DELETE'])
    @api_key_or_login_required
    def api_delete_template(template_name):
        """删除模板"""
        try:
            # 检查模板是否存在
            template = get_template_by_name(template_name)
            if not template:
                return jsonify({'success': False, 'error': '模板不存在'}), 404

            # 删除文件
            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            filepath = os.path.join(templates_dir, template['path'])

            if os.path.exists(filepath):
                os.remove(filepath)

            # 删除数据库记录
            deleted = delete_template(template_name)
            if not deleted:
                return jsonify({'success': False, 'error': '删除模板记录失败'}), 500

            return jsonify({'success': True, 'message': '模板删除成功'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/templates/<template_name>/extract-fields', methods=['POST'])
    @api_key_or_login_required
    def api_extract_template_fields(template_name):
        """使用AI自动提取模板代码中的字段信息并更新到数据库"""
        try:
            # 检查模板是否存在
            template = get_template_by_name(template_name)
            if not template:
                return jsonify({'success': False, 'error': '模板不存在'}), 404

            # 读取模板文件内容
            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            filepath = os.path.join(templates_dir, template['path'])

            if not os.path.exists(filepath):
                return jsonify({'success': False, 'error': '模板文件不存在'}), 404

            with open(filepath, 'r', encoding='utf-8') as f:
                template_code = f.read()

            # 使用AI提取字段
            extracted_fields, error = extract_template_fields_with_ai(template_code)

            if error:
                return jsonify({'success': False, 'error': error}), 500

            if not extracted_fields:
                return jsonify({'success': False, 'error': 'AI未能提取到有效字段'}), 500

            # 更新数据库
            update_template(
                template_name,
                server_address=extracted_fields.get('server_address'),
                protocol_type=extracted_fields.get('protocol_type'),
                port=extracted_fields.get('port'),
                type=extracted_fields.get('type', 'default'),
                api_address=extracted_fields.get('api_address'),
                login_address=extracted_fields.get('login_address'),
                redirect_address=extracted_fields.get('redirect_address')
            )

            return jsonify({
                'success': True,
                'message': '字段提取成功',
                'extracted_fields': extracted_fields
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500