from flask import Flask, request, render_template, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
CORS(app)

# 配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov', 'webm', 'mkv', 'flv'}
GROUPS_FILE = 'groups.json'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 最大 500MB

# 确保上传文件夹存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 默认账号
DEFAULT_USER = {
    'username': 'xkz666',
    'password': 'xkz666'
}

# 初始化 groups.json
def init_groups_file():
    if not os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'groups': []}, f, ensure_ascii=False, indent=2)

def load_groups():
    init_groups_file()
    with open(GROUPS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_groups(data):
    with open(GROUPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    image_exts = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp']
    video_exts = ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv', 'webm']
    
    if ext in image_exts:
        return 'image'
    elif ext in video_exts:
        return 'video'
    return 'other'

def get_next_file_number(group_name, group_folder):
    """
    获取该文件夹下一个可用的序号
    命名规则：文件夹名_序号.扩展名
    例如：奥奇_1.jpg, 奥奇_2.jpg
    """
    import re
    
    max_number = 0
    # 匹配规则：文件夹名_数字.扩展名
    pattern = re.compile(rf'^{re.escape(group_name)}_(\d+)\.\w+$')
    
    if os.path.exists(group_folder):
        for filename in os.listdir(group_folder):
            match = pattern.match(filename)
            if match:
                number = int(match.group(1))
                if number > max_number:
                    max_number = number
    
    return max_number + 1

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'success': False, 'error': '请先登录', 'code': 'AUTH_REQUIRED'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ============ 账号相关接口 ============

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if username == DEFAULT_USER['username'] and password == DEFAULT_USER['password']:
        session['logged_in'] = True
        session['username'] = username
        return jsonify({'success': True, 'message': '登录成功', 'username': username})
    else:
        return jsonify({'success': False, 'error': '用户名或密码错误'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': '已退出登录'})

@app.route('/api/auth/status', methods=['GET'])
def check_auth():
    if session.get('logged_in'):
        return jsonify({
            'success': True,
            'isLoggedIn': True,
            'username': session.get('username')
        })
    else:
        return jsonify({
            'success': True,
            'isLoggedIn': False
        })

# ============ 页面路由 ============

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

# ============ 分组管理接口 ============

# 获取所有分组（公开接口，不需要登录）
@app.route('/api/groups', methods=['GET'])
def get_groups():
    groups_data = load_groups()
    return jsonify({'success': True, 'groups': groups_data['groups']})

# 创建分组（需要登录）
@app.route('/api/groups', methods=['POST'])
@login_required
def create_group():
    data = request.get_json()
    name = data.get('name', '').strip()
    
    if not name:
        return jsonify({'success': False, 'error': '分组名称不能为空'}), 400
    
    # 检查是否已存在
    groups_data = load_groups()
    existing_names = [g['name'] for g in groups_data['groups']]
    
    if name in existing_names:
        return jsonify({'success': False, 'error': '分组名称已存在'}), 400
    
    # 创建文件夹
    group_folder = os.path.join(UPLOAD_FOLDER, name)
    os.makedirs(group_folder, exist_ok=True)
    
    # 保存分组信息
    group_info = {
        'id': str(int(datetime.now().timestamp() * 1000)),
        'name': name,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'folder': group_folder
    }
    groups_data['groups'].append(group_info)
    save_groups(groups_data)
    
    return jsonify({'success': True, 'group': group_info})

# 删除分组（需要登录）
@app.route('/api/groups/<group_name>', methods=['DELETE'])
@login_required
def delete_group(group_name):
    groups_data = load_groups()
    
    # 找到并移除分组
    group = None
    for g in groups_data['groups']:
        if g['name'] == group_name:
            group = g
            break
    
    if not group:
        return jsonify({'success': False, 'error': '分组不存在'}), 404
    
    # 删除文件夹
    group_folder = os.path.join(UPLOAD_FOLDER, group_name)
    if os.path.exists(group_folder):
        import shutil
        shutil.rmtree(group_folder)
    
    # 从列表中移除
    groups_data['groups'] = [g for g in groups_data['groups'] if g['name'] != group_name]
    save_groups(groups_data)
    
    return jsonify({'success': True, 'message': f'分组 "{group_name}" 已删除'})

# ============ 文件管理接口 ============

# 获取分组内的文件列表（公开接口）
@app.route('/api/files/<group_name>', methods=['GET'])
def get_group_files(group_name):
    group_folder = os.path.join(UPLOAD_FOLDER, group_name)
    
    if not os.path.exists(group_folder):
        return jsonify({'success': False, 'error': '分组不存在'}), 404
    
    files = []
    for filename in os.listdir(group_folder):
        filepath = os.path.join(group_folder, filename)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            files.append({
                'name': filename,
                'type': get_file_type(filename),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'url': f'/uploads/{group_name}/{filename}'
            })
    
    # 按时间倒序排列
    files.sort(key=lambda x: x['modified'], reverse=True)
    
    return jsonify({'success': True, 'files': files})

# 上传文件到指定分组（需要登录）
@app.route('/api/upload/<group_name>', methods=['POST'])
@login_required
def upload_file(group_name):
    # 检查分组是否存在
    groups_data = load_groups()
    group_names = [g['name'] for g in groups_data['groups']]
    
    if group_name not in group_names:
        return jsonify({'success': False, 'error': '分组不存在'}), 404
    
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': '没有选择文件'}), 400
    
    files = request.files.getlist('files')
    uploaded_files = []
    errors = []
    
    group_folder = os.path.join(UPLOAD_FOLDER, group_name)
    os.makedirs(group_folder, exist_ok=True)
    
    for file in files:
        if file.filename == '':
            continue
            
        if file and allowed_file(file.filename):
            # 获取文件扩展名（从原始文件名，不使用 secure_filename）
            original_filename = file.filename
            # 提取扩展名
            if '.' in original_filename:
                ext_part = original_filename.rsplit('.', 1)[1].lower()
                # 确保扩展名以点开头
                if not ext_part.startswith('.'):
                    ext_part = '.' + ext_part
            else:
                ext_part = ''
            
            # 获取下一个序号
            next_number = get_next_file_number(group_name, group_folder)
            
            # 新命名规则：文件夹名_序号.扩展名
            filename = f"{group_name}_{next_number}{ext_part}"
            
            # 如果文件名已存在（理论上不应该），继续递增
            filepath = os.path.join(group_folder, filename)
            while os.path.exists(filepath):
                next_number += 1
                filename = f"{group_name}_{next_number}{ext_part}"
                filepath = os.path.join(group_folder, filename)
            
            # 保存文件
            file.save(filepath)
            
            file_info = {
                'name': filename,
                'original_name': original_filename,
                'type': get_file_type(filename),
                'size': os.path.getsize(filepath)
            }
            uploaded_files.append(file_info)
        else:
            errors.append(f"{file.filename} - 不支持的文件类型")
    
    if uploaded_files:
        return jsonify({
            'success': True,
            'message': f'成功上传 {len(uploaded_files)} 个文件',
            'files': uploaded_files,
            'errors': errors
        })
    else:
        return jsonify({
            'success': False,
            'error': '没有文件被上传',
            'errors': errors
        }), 400

# 删除文件（需要登录）
@app.route('/api/files/<group_name>/<path:filename>', methods=['DELETE'])
@login_required
def delete_file(group_name, filename):
    filepath = os.path.join(UPLOAD_FOLDER, group_name, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    
    try:
        os.remove(filepath)
        return jsonify({'success': True, 'message': '文件已删除'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# 提供文件访问（用于预览）
@app.route('/uploads/<path:filename>')
def serve_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# 下载文件（公开接口，所有人可用）
@app.route('/api/download/<group_name>/<path:filename>', methods=['GET'])
def download_file(group_name, filename):
    filepath = os.path.join(UPLOAD_FOLDER, group_name, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    
    try:
        # 直接使用当前文件名作为下载名
        # 新格式：文件夹名_序号.扩展名（如：奥奇_1.jpg）
        return send_from_directory(
            os.path.join(UPLOAD_FOLDER, group_name),
            filename,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
