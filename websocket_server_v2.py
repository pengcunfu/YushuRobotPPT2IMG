"""
WebSocket服务器V2 - 基于URL的PPT处理服务
客户端提供PPT URL和文件名，服务器处理并返回图片下载URL
基于Flask-SocketIO实现，解决代理问题
"""
import os
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from loguru import logger

from pptx_to_images_minio import pptx_url_to_minio_images

# 存储任务状态和连接信息 - 使用线程安全的数据结构
tasks = {}
active_connections = {}
tasks_lock = threading.RLock()  # 可重入锁
connections_lock = threading.RLock()

# 任务队列和线程池
task_queue = queue.Queue()
MAX_CONCURRENT_TASKS = 5  # 最大并发任务数（PPT处理比较耗时，减少并发数）
task_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TASKS, thread_name_prefix="PPT_MinIO_Worker")

# 创建Flask应用和SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'ppt_processing_secret_key_v2'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


def init_socketio_events():
    """初始化SocketIO事件处理"""
    
    @socketio.on('connect')
    def handle_connect():
        """WebSocket连接处理"""
        logger.info(f'客户端已连接: {request.sid}')
        emit('connected', {'message': '已连接到PPT处理服务器V2'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """WebSocket断开连接处理"""
        logger.info(f'客户端已断开连接: {request.sid}')
        with connections_lock:
            if request.sid in active_connections:
                connection_info = active_connections[request.sid]
                del active_connections[request.sid]
                logger.info(f'已清理客户端 {request.sid} 的连接信息')

    @socketio.on('start_ppt_processing')
    def handle_start_ppt_processing(data):
        """启动PPT处理任务"""
        ppt_url = data.get('ppt_url')
        ppt_name = data.get('ppt_name')
        width = data.get('width', 1920)
        height = data.get('height', 1080)
        bucket_name = data.get('bucket_name', 'images')

        # 验证必需参数
        if not ppt_url or not ppt_name:
            emit('error', {'message': '缺少必需参数: ppt_url 和 ppt_name'})
            return

        # 生成任务UUID
        import uuid
        task_uuid = str(uuid.uuid4())

        # 创建任务数据
        task_data = {
            'uuid': task_uuid,
            'ppt_url': ppt_url,
            'ppt_name': ppt_name,
            'width': width,
            'height': height,
            'bucket_name': bucket_name,
            'status': 'created',
            'created_at': time.time(),
            'progress': 0,
            'total_slides': 0,
            'processed_slides': 0,
            'download_urls': [],
            'error': None
        }

        # 检查并发任务数量
        with tasks_lock:
            active_tasks = sum(1 for t in tasks.values() if t['status'] in ['queued', 'processing'])
            if active_tasks >= MAX_CONCURRENT_TASKS:
                emit('error', {'message': f'服务器繁忙，当前有 {active_tasks} 个任务在处理中，请稍后重试'})
                return

            # 添加任务
            tasks[task_uuid] = task_data
            task_data['status'] = 'queued'
            task_data['queued_at'] = time.time()

        # 将客户端加入到特定的房间（以UUID命名）
        room_id = f"task_{task_uuid}"
        join_room(room_id)

        with connections_lock:
            active_connections[request.sid] = {'room': room_id, 'uuid': task_uuid}

        logger.info(f'任务 {task_uuid} 已创建: {ppt_name}')

        emit('task_created', {
            'uuid': task_uuid,
            'ppt_name': ppt_name,
            'message': '任务已创建并加入处理队列'
        })

        # 将任务提交到线程池
        future = task_executor.submit(process_ppt_task, task_uuid, room_id, socketio)

        # 添加回调来处理任务完成或异常
        def task_done_callback(future):
            try:
                future.result()  # 获取结果，如果有异常会抛出
            except Exception as e:
                logger.error(f"任务 {task_uuid} 执行异常: {e}")
                with tasks_lock:
                    if task_uuid in tasks:
                        tasks[task_uuid]['status'] = 'failed'
                        tasks[task_uuid]['error'] = str(e)

                socketio.emit('task_error', {
                    'uuid': task_uuid,
                    'status': 'failed',
                    'error': str(e),
                    'message': f'任务执行异常: {str(e)}'
                }, room=room_id)

        future.add_done_callback(task_done_callback)

    @socketio.on('join_task')
    def handle_join_task(data):
        """加入现有任务的房间"""
        task_uuid = data.get('uuid')

        with tasks_lock:
            if not task_uuid or task_uuid not in tasks:
                emit('error', {'message': '无效的任务UUID'})
                return

            task = tasks[task_uuid]

        room_id = f"task_{task_uuid}"
        join_room(room_id)

        with connections_lock:
            active_connections[request.sid] = {'room': room_id, 'uuid': task_uuid}

        # 发送当前任务状态
        emit('task_status', {
            'uuid': task_uuid,
            'ppt_name': task['ppt_name'],
            'status': task['status'],
            'progress': task['progress'],
            'total_slides': task['total_slides'],
            'processed_slides': task['processed_slides'],
            'download_urls': task['download_urls']
        })

    @socketio.on('get_task_status')
    def handle_get_task_status(data):
        """获取任务状态"""
        task_uuid = data.get('uuid')

        with tasks_lock:
            if not task_uuid or task_uuid not in tasks:
                emit('error', {'message': '无效的任务UUID'})
                return

            task = tasks[task_uuid]

        emit('task_status', {
            'uuid': task_uuid,
            'ppt_name': task['ppt_name'],
            'status': task['status'],
            'progress': task['progress'],
            'total_slides': task['total_slides'],
            'processed_slides': task['processed_slides'],
            'download_urls': task['download_urls'],
            'error': task.get('error')
        })


def init_socketio():
    """初始化SocketIO"""
    init_socketio_events()
    return socketio


def process_ppt_task(task_uuid, room_id, socketio):
    """处理PPT转图片的后台任务"""
    try:
        with tasks_lock:
            task = tasks[task_uuid]
            task['status'] = 'processing'
            task['started_at'] = time.time()

        logger.info(f'开始处理任务 {task_uuid}: {task["ppt_name"]}')

        # 发送开始处理消息
        socketio.emit('progress_update', {
            'uuid': task_uuid,
            'status': 'processing',
            'progress': 0,
            'total_slides': 0,
            'processed_slides': 0,
            'message': '正在下载PPT文件...'
        }, room=room_id)

        # 调用PPT转图片并上传到MinIO的函数
        import asyncio
        result = asyncio.run(pptx_url_to_minio_images(
            ppt_url=task['ppt_url'],
            ppt_name=task['ppt_name'],
            bucket_name=task['bucket_name'],
            width=task['width'],
            height=task['height']
        ))

        if result['success']:
            # 处理成功
            with tasks_lock:
                task['status'] = 'completed'
                task['total_slides'] = result['total_slides']
                task['processed_slides'] = result['successful_uploads']
                task['progress'] = 100
                task['download_urls'] = result['download_urls']
                task['completed_at'] = time.time()

            logger.info(f'任务 {task_uuid} 完成: 成功处理 {result["successful_uploads"]} 张图片')

            socketio.emit('task_complete', {
                'uuid': task_uuid,
                'ppt_name': task['ppt_name'],
                'status': 'completed',
                'progress': 100,
                'total_slides': result['total_slides'],
                'processed_slides': result['successful_uploads'],
                'download_urls': result['download_urls'],
                'message': f'PPT处理完成！生成了 {result["successful_uploads"]} 张图片'
            }, room=room_id)

        else:
            # 处理失败
            with tasks_lock:
                task['status'] = 'failed'
                task['error'] = result['error']

            logger.error(f'任务 {task_uuid} 失败: {result["error"]}')

            socketio.emit('task_error', {
                'uuid': task_uuid,
                'ppt_name': task['ppt_name'],
                'status': 'failed',
                'error': result['error'],
                'message': f'PPT处理失败: {result["error"]}'
            }, room=room_id)

    except Exception as e:
        # 任务异常
        with tasks_lock:
            if task_uuid in tasks:
                tasks[task_uuid]['status'] = 'failed'
                tasks[task_uuid]['error'] = str(e)

        logger.error(f'任务 {task_uuid} 异常: {e}')

        socketio.emit('task_error', {
            'uuid': task_uuid,
            'status': 'failed',
            'error': str(e),
            'message': f'PPT处理异常: {str(e)}'
        }, room=room_id)


def add_task(task_data):
    """添加任务到全局任务字典"""
    with tasks_lock:
        tasks[task_data['uuid']] = task_data


def get_task(task_uuid):
    """获取任务信息"""
    with tasks_lock:
        return tasks.get(task_uuid)


def get_all_tasks():
    """获取所有任务"""
    with tasks_lock:
        return tasks.copy()


def get_server_stats():
    """获取服务器统计信息"""
    with tasks_lock:
        total_tasks = len(tasks)
        active_tasks = sum(1 for t in tasks.values() if t['status'] == 'processing')
        queued_tasks = sum(1 for t in tasks.values() if t['status'] == 'queued')
        completed_tasks = sum(1 for t in tasks.values() if t['status'] == 'completed')
        failed_tasks = sum(1 for t in tasks.values() if t['status'] == 'failed')

    with connections_lock:
        active_connections_count = len(active_connections)

    return {
        'total_tasks': total_tasks,
        'active_tasks': active_tasks,
        'queued_tasks': queued_tasks,
        'completed_tasks': completed_tasks,
        'failed_tasks': failed_tasks,
        'active_connections': active_connections_count,
        'max_concurrent_tasks': MAX_CONCURRENT_TASKS
    }


def start_flask_server(host='0.0.0.0', port=8082, debug=False):
    """启动Flask-SocketIO服务器"""
    logger.info(f"🚀 启动Flask-SocketIO服务器: http://{host}:{port}")
    print(f"🚀 启动Flask-SocketIO服务器: http://{host}:{port}")
    print("📋 支持的功能:")
    print("   - 基于URL的PPT处理")
    print("   - 实时进度更新")
    print("   - 自动上传到MinIO")
    print("   - 返回下载链接")
    print("   - 支持代理环境")
    print("=" * 50)
    
    # 初始化SocketIO事件
    init_socketio_events()
    
    # 启动服务器
    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        allow_unsafe_werkzeug=True
    )


if __name__ == "__main__":
    try:
        start_flask_server()
    except KeyboardInterrupt:
        logger.info("⏹️ 服务器已停止")
        print("\n⏹️ 服务器已停止")
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        print(f"❌ 启动失败: {e}")
