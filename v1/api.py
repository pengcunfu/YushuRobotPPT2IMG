import os
import uuid
import time
from flask import Flask, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
import websocket_server

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 16MB max file size

# 初始化SocketIO
socketio = websocket_server.init_socketio(app)

# 创建必要的文件夹
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

# 允许的文件扩展名 - 仅支持PPT格式
ALLOWED_EXTENSIONS = {'ppt', 'pptx'}


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['POST'])
def upload_file():
    """文件上传接口"""
    if 'file' not in request.files:
        return jsonify({'error': '没有找到文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400

    if file and allowed_file(file.filename):
        # 生成唯一的UUID
        file_uuid = str(uuid.uuid4())

        # 保存原始文件名信息
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()

        # 使用UUID作为文件名
        filename = f"{file_uuid}.{file_extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # 保存文件
        file.save(filepath)

        # 获取可选的图片尺寸参数
        width = int(request.form.get('width', 1920))
        height = int(request.form.get('height', 1080))

        # 初始化任务状态
        task_data = {
            'uuid': file_uuid,
            'original_filename': original_filename,
            'status': 'uploaded',
            'progress': 0,
            'total_images': 0,
            'processed_images': 0,
            'created_at': time.time(),
            'file_path': filepath,
            'width': width,
            'height': height
        }
        websocket_server.add_task(task_data)

        return jsonify({
            'uuid': file_uuid,
            'filename': original_filename,
            'message': '文件上传成功'
        }), 200

    return jsonify({'error': '不支持的文件类型'}), 400


@app.route('/download/<file_uuid>/<int:image_index>')
def download_image(file_uuid, image_index):
    """下载处理后的图片"""
    task = websocket_server.get_task(file_uuid)
    if not task:
        abort(404)

    # 构造处理后的图片路径
    processed_dir = os.path.join(app.config['PROCESSED_FOLDER'], file_uuid)
    image_filename = f"image_{image_index:03d}.png"
    image_path = os.path.join(processed_dir, image_filename)

    if not os.path.exists(image_path):
        abort(404)

    return send_file(image_path, as_attachment=True, download_name=image_filename)


@app.route('/status/<file_uuid>')
def get_task_status(file_uuid):
    """获取任务状态"""
    task = websocket_server.get_task(file_uuid)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify({
        'uuid': file_uuid,
        'status': task['status'],
        'progress': task['progress'],
        'total_images': task['total_images'],
        'processed_images': task['processed_images']
    })


@app.route('/server/stats')
def get_server_stats():
    """获取服务器统计信息"""
    stats = websocket_server.get_server_stats()
    return jsonify(stats)


@app.route('/')
def index():
    """主页"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>图片处理服务</title>
        <meta charset="utf-8">
    </head>
    <body>
        <h1>图片处理服务API</h1>
        <h2>可用接口：</h2>
        <ul>
            <li>POST /upload - 上传文件</li>
            <li>GET /download/&lt;uuid&gt;/&lt;image_index&gt; - 下载处理后的图片</li>
            <li>GET /status/&lt;uuid&gt; - 获取任务状态</li>
            <li>WebSocket连接用于实时任务处理</li>
        </ul>
    </body>
    </html>
    '''


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=False)
