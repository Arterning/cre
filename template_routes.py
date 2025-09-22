# -*- coding: utf-8 -*-

import os
from datetime import datetime
from flask import Blueprint, render_template, jsonify, request
from functools import wraps

# 创建蓝图
template_bp = Blueprint('templates', __name__)


def register_template_routes(app, login_required, api_key_or_login_required):
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
            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            templates = []

            if os.path.exists(templates_dir):
                for filename in os.listdir(templates_dir):
                    if filename.endswith('.py'):
                        filepath = os.path.join(templates_dir, filename)
                        stat = os.stat(filepath)

                        templates.append({
                            'name': filename,
                            'path': filename,
                            'size': stat.st_size,
                            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })

            templates.sort(key=lambda x: x['name'])
            return jsonify({'success': True, 'templates': templates})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/templates/<template_name>', methods=['GET'])
    @api_key_or_login_required
    def api_get_template(template_name):
        """获取单个模板内容"""
        try:
            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            filepath = os.path.join(templates_dir, template_name)

            if not os.path.exists(filepath) or not template_name.endswith('.py'):
                return jsonify({'success': False, 'error': '模板文件不存在'}), 404

            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            return jsonify({'success': True, 'content': content, 'name': template_name})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/templates/<template_name>', methods=['PUT'])
    @api_key_or_login_required
    def api_update_template(template_name):
        """更新模板内容"""
        try:
            data = request.get_json()
            if not data or 'content' not in data:
                return jsonify({'success': False, 'error': '缺少模板内容'}), 400

            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            filepath = os.path.join(templates_dir, template_name)

            if not template_name.endswith('.py'):
                return jsonify({'success': False, 'error': '模板文件名必须以.py结尾'}), 400

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(data['content'])

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
            if not template_name.endswith('.py'):
                template_name += '.py'

            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            os.makedirs(templates_dir, exist_ok=True)
            filepath = os.path.join(templates_dir, template_name)

            if os.path.exists(filepath):
                return jsonify({'success': False, 'error': '模板文件已存在'}), 400

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(data['content'])

            return jsonify({'success': True, 'message': '模板创建成功', 'name': template_name})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/templates/<template_name>/copy', methods=['POST'])
    @api_key_or_login_required
    def api_copy_template(template_name):
        """复制模板"""
        try:
            data = request.get_json()
            new_name = data.get('new_name') if data else None

            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            source_path = os.path.join(templates_dir, template_name)

            if not os.path.exists(source_path):
                return jsonify({'success': False, 'error': '源模板文件不存在'}), 404

            # 生成新文件名
            if not new_name:
                base_name = template_name.replace('.py', '')
                new_name = f"{base_name}_copy.py"
                counter = 1
                while os.path.exists(os.path.join(templates_dir, new_name)):
                    new_name = f"{base_name}_copy{counter}.py"
                    counter += 1
            elif not new_name.endswith('.py'):
                new_name += '.py'

            dest_path = os.path.join(templates_dir, new_name)

            if os.path.exists(dest_path):
                return jsonify({'success': False, 'error': '目标文件已存在'}), 400

            with open(source_path, 'r', encoding='utf-8') as src:
                content = src.read()

            with open(dest_path, 'w', encoding='utf-8') as dest:
                dest.write(content)

            return jsonify({'success': True, 'message': '模板复制成功', 'new_name': new_name})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


    @app.route('/api/templates/<template_name>', methods=['DELETE'])
    @api_key_or_login_required
    def api_delete_template(template_name):
        """删除模板"""
        try:
            templates_dir = os.path.join(os.getcwd(), 'ai', 'templates')
            filepath = os.path.join(templates_dir, template_name)

            if not os.path.exists(filepath):
                return jsonify({'success': False, 'error': '模板文件不存在'}), 404

            os.remove(filepath)
            return jsonify({'success': True, 'message': '模板删除成功'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500