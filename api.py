import os
import uuid
import time
import json
import threading
import requests
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
from pptx_to_images import pptx_to_images
from loguru import logger

# 配置loguru日志 - 使用默认控制台输出
# loguru默认已经配置了控制台输出，无需额外配置

app = Flask(__name__)


def load_existing_tasks():
    """启动时加载已存在的任务结果"""
    if not os.path.exists(app.config['RESULT_FOLDER']):
        return
    
    logger.info("正在加载已存在的任务结果...")
    
    for task_dir in os.listdir(app.config['RESULT_FOLDER']):
        task_path = os.path.join(app.config['RESULT_FOLDER'], task_dir)
        if os.path.isdir(task_path):
            try:
                # 检查是否有图片文件
                image_files = [f for f in os.listdir(task_path) if f.endswith('.png')]
                if image_files:
                    # 尝试找到对应的原始文件
                    upload_file = None
                    for ext in ['.ppt', '.pptx']:
                        potential_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_dir}{ext}")
                        if os.path.exists(potential_file):
                            upload_file = potential_file
                            break
                    
                    # 构建图片路径列表
                    image_paths = []
                    for img_file in sorted(image_files):
                        image_paths.append(os.path.join(task_path, img_file))
                    
                    # 重建任务记录
                    tasks[task_dir] = {
                        'id': task_dir,
                        'original_filename': f"recovered_{task_dir}.pptx",
                        'filename': f"{task_dir}.pptx",
                        'ppt_path': upload_file or '',
                        'output_dir': task_path,
                        'status': 'completed',
                        'created_at': int(os.path.getctime(task_path)),
                        'width': 1920,
                        'height': 1080,
                        'callback_url': '',
                        'image_paths': image_paths,
                        'completed_at': int(os.path.getmtime(task_path))
                    }
                    
                    logger.info(f"恢复任务 {task_dir}，包含 {len(image_paths)} 张图片")
            except Exception as e:
                logger.warning(f"恢复任务 {task_dir} 失败: {str(e)}")
    
    logger.info(f"已恢复 {len(tasks)} 个任务")

# 配置
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULT_FOLDER'] = 'results'
app.config['ALLOWED_EXTENSIONS'] = {'ppt', 'pptx'}
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 限制上传文件大小为100MB

# 确保目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

# 任务状态存储
tasks = {}

# 启动时加载已有任务
load_existing_tasks()

# 回调重试配置
MAX_CALLBACK_RETRIES = 3
CALLBACK_RETRY_DELAY = 5  # 秒


def allowed_file(filename):
    """检查文件扩展名是否允许上传"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def process_ppt_task(task_id, ppt_path, output_dir, width, height, callback_url=None):
    """后台处理PPT转图片任务"""
    try:
        logger.info(f"开始处理任务 {task_id}: {ppt_path}")
        tasks[task_id]['status'] = 'processing'

        # 调用转换函数
        image_paths = pptx_to_images(ppt_path, output_dir, width, height)

        # 更新任务状态
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['image_paths'] = image_paths
        tasks[task_id]['completed_at'] = time.time()

        logger.info(f"任务 {task_id} 完成，生成了 {len(image_paths)} 张图片")

    except Exception as e:
        logger.error(f"任务 {task_id} 处理失败: {str(e)}")
        tasks[task_id]['status'] = 'failed'
        tasks[task_id]['error'] = str(e)

    finally:
        # 发送回调通知
        if callback_url:
            send_callback(task_id, callback_url)


@app.route('/', methods=['GET'])
def index():
    """API首页和文档"""
    return jsonify({
        'service': 'PPT to Images Converter API',
        'version': '1.0.0',
        'status': 'running',
        'endpoints': {
            'upload': 'POST /api/upload - 上传PPT文件进行转换',
            'task_status': 'GET /api/tasks/<task_id>/status - 获取任务状态',
            'task_images': 'GET /api/tasks/<task_id>/images - 列出任务的所有图片',
            'task_image': 'GET /api/tasks/<task_id>/images/<filename> - 获取特定图片',
            'download_original': 'GET /api/tasks/<task_id>/download - 下载原始PPT文件',
            'list_tasks': 'GET /api/tasks - 列出所有任务',
            'health': 'GET /api/health - 健康检查'
        },
        'current_tasks': len(tasks),
        'completed_tasks': len([t for t in tasks.values() if t['status'] == 'completed'])
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': int(time.time()),
        'uptime': int(time.time()),  # 简化的运行时间
        'tasks': {
            'total': len(tasks),
            'pending': len([t for t in tasks.values() if t['status'] == 'pending']),
            'processing': len([t for t in tasks.values() if t['status'] == 'processing']),
            'completed': len([t for t in tasks.values() if t['status'] == 'completed']),
            'failed': len([t for t in tasks.values() if t['status'] == 'failed'])
        },
        'storage': {
            'upload_folder': app.config['UPLOAD_FOLDER'],
            'result_folder': app.config['RESULT_FOLDER']
        }
    })


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """上传PPT文件API接口"""
    # 检查是否有文件
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']

    # 检查文件名
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # 检查文件类型
    if not allowed_file(file.filename):
        return jsonify(
            {'error': f'File type not allowed. Allowed types: {", ".join(app.config["ALLOWED_EXTENSIONS"])}'}), 400

    # 生成唯一ID和文件名
    task_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1].lower()  # 获取文件扩展名
    filename = f"{task_id}{file_extension}"  # 使用UUID作为文件名
    timestamp = int(time.time())

    # 创建结果专属目录
    task_result_dir = os.path.join(app.config['RESULT_FOLDER'], task_id)
    os.makedirs(task_result_dir, exist_ok=True)

    # 保存上传的文件到uploads目录下
    ppt_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(ppt_path)

    # 获取转换参数和回调URL
    width = int(request.form.get('width', 1920))
    height = int(request.form.get('height', 1080))
    callback_url = request.form.get('callback_url')

    # 验证必须提供回调URL
    if not callback_url:
        return jsonify({'error': 'callback_url is required'}), 400

    # 创建任务记录
    tasks[task_id] = {
        'id': task_id,
        'original_filename': file.filename,  # 保存原始文件名
        'filename': filename,  # UUID文件名
        'ppt_path': ppt_path,
        'output_dir': task_result_dir,
        'status': 'pending',
        'created_at': timestamp,
        'width': width,
        'height': height,
        'callback_url': callback_url
    }

    # 启动后台线程处理转换任务
    thread = threading.Thread(
        target=process_ppt_task,
        args=(task_id, ppt_path, task_result_dir, width, height, callback_url)
    )
    thread.daemon = True
    thread.start()

    # 返回任务ID
    return jsonify({
        'task_id': task_id,
        'status': 'pending',
        'message': 'PPT conversion started, result will be sent to callback URL'
    })


@app.route('/api/tasks/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """获取任务状态"""
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = tasks[task_id]
    response_data = {
        'task_id': task_id,
        'status': task['status'],
        'original_filename': task['original_filename'],
        'created_at': task['created_at']
    }
    
    if task['status'] == 'completed':
        # 构建图片信息
        image_files = []
        for i, path in enumerate(task.get('image_paths', [])):
            filename = os.path.basename(path)
            image_files.append({
                'slide': i + 1,
                'filename': filename,
                'path': f"/api/tasks/{task_id}/images/{filename}"
            })
        
        response_data.update({
            'image_count': len(task.get('image_paths', [])),
            'images': image_files,
            'completed_at': task.get('completed_at')
        })
    elif task['status'] == 'failed':
        response_data['error'] = task.get('error', 'Unknown error')
    
    return jsonify(response_data)


@app.route('/api/tasks/<task_id>/images/<filename>', methods=['GET'])
def get_task_image(task_id, filename):
    """获取任务生成的图片"""
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = tasks[task_id]
    image_path = os.path.join(task['output_dir'], filename)
    
    if not os.path.exists(image_path):
        return jsonify({'error': 'Image not found'}), 404
    
    return send_file(image_path, mimetype='image/png')


@app.route('/api/tasks/<task_id>/images', methods=['GET'])
def list_task_images(task_id):
    """列出任务的所有图片"""
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = tasks[task_id]
    if task['status'] != 'completed':
        return jsonify({'error': 'Task not completed yet'}), 400
    
    image_files = []
    for i, path in enumerate(task.get('image_paths', [])):
        filename = os.path.basename(path)
        image_files.append({
            'slide': i + 1,
            'filename': filename,
            'path': f"/api/tasks/{task_id}/images/{filename}",
            'url': f"http://{request.host}/api/tasks/{task_id}/images/{filename}"
        })
    
    return jsonify({
        'task_id': task_id,
        'image_count': len(image_files),
        'images': image_files
    })


@app.route('/api/tasks/<task_id>/download', methods=['GET'])
def download_original_file(task_id):
    """下载原始PPT文件"""
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404
    
    task = tasks[task_id]
    ppt_path = task['ppt_path']
    
    if not os.path.exists(ppt_path):
        return jsonify({'error': 'Original file not found'}), 404
    
    return send_file(ppt_path, 
                    as_attachment=True, 
                    download_name=task['original_filename'])


@app.route('/api/tasks', methods=['GET'])
def list_all_tasks():
    """列出所有任务"""
    task_list = []
    for task_id, task in tasks.items():
        task_info = {
            'task_id': task_id,
            'status': task['status'],
            'original_filename': task['original_filename'],
            'created_at': task['created_at']
        }
        
        if task['status'] == 'completed':
            task_info['image_count'] = len(task.get('image_paths', []))
            task_info['completed_at'] = task.get('completed_at')
        elif task['status'] == 'failed':
            task_info['error'] = task.get('error', 'Unknown error')
        
        task_list.append(task_info)
    
    # 按创建时间倒序排列
    task_list.sort(key=lambda x: x['created_at'], reverse=True)
    
    return jsonify({
        'total': len(task_list),
        'tasks': task_list
    })


def send_callback(task_id, callback_url, retry_count=0):
    """
    发送回调通知到客户提供的URL
    """
    if not callback_url:
        logger.warning(f"任务 {task_id} 没有提供回调URL，跳过回调")
        return

    try:
        task = tasks[task_id]

        # 准备回调数据
        callback_data = {
            'task_id': task_id,
            'status': task['status'],
            'original_filename': task['original_filename'],
            'filename': task['filename'],
            'created_at': task['created_at']
        }

        # 根据任务状态添加不同的数据
        if task['status'] == 'completed':
            # 构建图片信息
            image_files = []
            for i, path in enumerate(task.get('image_paths', [])):
                filename = os.path.basename(path)
                image_files.append({
                    'slide': i + 1,
                    'filename': filename,
                    'path': f"/api/tasks/{task_id}/images/{filename}"
                })

            callback_data.update({
                'image_count': len(task.get('image_paths', [])),
                'images': image_files,
                'completed_at': task.get('completed_at')
            })
        elif task['status'] == 'failed':
            callback_data['error'] = task.get('error', 'Unknown error')

        # 发送回调请求
        logger.info(f"发送回调通知到 {callback_url} (尝试 {retry_count + 1}/{MAX_CALLBACK_RETRIES + 1})")
        response = requests.post(
            callback_url,
            json=callback_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

        # 检查响应状态
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"回调成功: {response.status_code}")
            return True
        else:
            logger.warning(f"回调失败: HTTP状态码 {response.status_code}")
            # 如果回调失败且未达到最大重试次数，则重试
            if retry_count < MAX_CALLBACK_RETRIES:
                logger.info(f"将在 {CALLBACK_RETRY_DELAY} 秒后重试回调")
                time.sleep(CALLBACK_RETRY_DELAY)
                return send_callback(task_id, callback_url, retry_count + 1)
            else:
                logger.error(f"回调失败，已达到最大重试次数: {MAX_CALLBACK_RETRIES}")
                return False

    except Exception as e:
        logger.error(f"回调过程中发生错误: {str(e)}")
        # 如果发生异常且未达到最大重试次数，则重试
        if retry_count < MAX_CALLBACK_RETRIES:
            logger.info(f"将在 {CALLBACK_RETRY_DELAY} 秒后重试回调")
            time.sleep(CALLBACK_RETRY_DELAY)
            return send_callback(task_id, callback_url, retry_count + 1)
        else:
            logger.error(f"回调失败，已达到最大重试次数: {MAX_CALLBACK_RETRIES}")
            return False


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8020)
