import os
import time
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import request
from pptx_to_images import pptx_to_images

# 存储任务状态和连接信息 - 使用线程安全的数据结构
tasks = {}
active_connections = {}
tasks_lock = threading.RLock()  # 可重入锁
connections_lock = threading.RLock()

# 任务队列和线程池
task_queue = queue.Queue()
MAX_CONCURRENT_TASKS = 10  # 最大并发任务数
task_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TASKS, thread_name_prefix="PPT_Worker")


def init_socketio(app):
    """初始化SocketIO"""
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

    @socketio.on('connect')
    def handle_connect():
        """WebSocket连接处理"""
        print(f'客户端已连接: {request.sid}')
        emit('connected', {'message': '已连接到服务器'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """WebSocket断开连接处理"""
        print(f'客户端已断开连接: {request.sid}')
        with connections_lock:
            if request.sid in active_connections:
                connection_info = active_connections[request.sid]
                del active_connections[request.sid]
                print(f'已清理客户端 {request.sid} 的连接信息')

    @socketio.on('start_task')
    def handle_start_task(data):
        """启动图片处理任务"""
        file_uuid = data.get('uuid')

        with tasks_lock:
            if not file_uuid or file_uuid not in tasks:
                emit('error', {'message': '无效的任务UUID'})
                return

            task = tasks[file_uuid]
            if task['status'] != 'uploaded':
                emit('error', {'message': '任务状态无效，无法启动'})
                return

            # 检查并发任务数量
            active_tasks = sum(1 for t in tasks.values() if t['status'] == 'processing')
            if active_tasks >= MAX_CONCURRENT_TASKS:
                emit('error', {'message': f'服务器繁忙，当前有 {active_tasks} 个任务在处理中，请稍后重试'})
                return

            # 将任务状态设置为排队中
            task['status'] = 'queued'
            task['queued_at'] = time.time()

        # 将客户端加入到特定的房间（以UUID命名）
        room_id = f"task_{file_uuid}"
        join_room(room_id)

        with connections_lock:
            active_connections[request.sid] = {'room': room_id, 'uuid': file_uuid}

        emit('task_started', {
            'uuid': file_uuid,
            'message': '任务已加入处理队列，等待处理...'
        })

        # 将任务提交到线程池
        future = task_executor.submit(process_images_task, file_uuid, room_id, socketio)

        # 可选：添加回调来处理任务完成或异常
        def task_done_callback(future):
            try:
                future.result()  # 获取结果，如果有异常会抛出
            except Exception as e:
                print(f"任务 {file_uuid} 执行异常: {e}")
                with tasks_lock:
                    if file_uuid in tasks:
                        tasks[file_uuid]['status'] = 'failed'
                        tasks[file_uuid]['error'] = str(e)

                socketio.emit('task_error', {
                    'uuid': file_uuid,
                    'status': 'failed',
                    'error': str(e),
                    'message': f'任务执行异常: {str(e)}'
                }, room=room_id)

        future.add_done_callback(task_done_callback)

    @socketio.on('join_task')
    def handle_join_task(data):
        """加入现有任务的房间"""
        file_uuid = data.get('uuid')

        with tasks_lock:
            if not file_uuid or file_uuid not in tasks:
                emit('error', {'message': '无效的任务UUID'})
                return

            task = tasks[file_uuid]

        room_id = f"task_{file_uuid}"
        join_room(room_id)

        with connections_lock:
            active_connections[request.sid] = {'room': room_id, 'uuid': file_uuid}

        # 发送当前任务状态
        emit('task_status', {
            'uuid': file_uuid,
            'status': task['status'],
            'progress': task['progress'],
            'total_images': task['total_images'],
            'processed_images': task['processed_images']
        })

    return socketio


def process_images_task(file_uuid, room_id, socketio):
    """处理PPT转图片的后台任务"""
    try:
        with tasks_lock:
            task = tasks[file_uuid]
            task['status'] = 'processing'
            task['started_at'] = time.time()

        # 创建处理后图片的目录
        processed_folder = 'processed'
        processed_dir = os.path.join(processed_folder, file_uuid)
        os.makedirs(processed_dir, exist_ok=True)

        # 获取PPT文件路径
        ppt_file_path = task['file_path']

        # 发送开始处理消息
        socketio.emit('progress_update', {
            'uuid': file_uuid,
            'status': 'processing',
            'progress': 0,
            'total_images': 0,
            'processed_images': 0,
            'current_image': -1,
            'message': '正在分析PPT文件...'
        }, room=room_id)

        # 使用现有的pptx_to_images函数进行转换
        # 设置默认尺寸，也可以从任务参数中获取
        width = task.get('width', 1920)
        height = task.get('height', 1080)

        # 调用PPT转换函数
        image_paths = pptx_to_images(
            pptx_path=ppt_file_path,
            output_dir=processed_dir,
            width=width,
            height=height
        )

        # 更新任务信息
        total_images = len(image_paths)
        with tasks_lock:
            task['total_images'] = total_images
            task['processed_images'] = total_images
            task['progress'] = 100

        # 重命名文件以匹配下载接口的格式 (image_000.png, image_001.png, ...)
        renamed_paths = []
        for i, old_path in enumerate(image_paths):
            new_filename = f"image_{i:03d}.png"
            new_path = os.path.join(processed_dir, new_filename)

            # 如果文件名不同，则重命名
            if old_path != new_path:
                os.rename(old_path, new_path)
            renamed_paths.append(new_path)

        # 任务完成
        with tasks_lock:
            task['status'] = 'completed'
            task['image_paths'] = renamed_paths
            task['completed_at'] = time.time()

        socketio.emit('task_complete', {
            'uuid': file_uuid,
            'status': 'completed',
            'progress': 100,
            'total_images': total_images,
            'processed_images': total_images,
            'message': f'PPT转换完成！生成了 {total_images} 张图片'
        }, room=room_id)

    except Exception as e:
        # 任务失败
        with tasks_lock:
            if file_uuid in tasks:
                tasks[file_uuid]['status'] = 'failed'
                tasks[file_uuid]['error'] = str(e)

        socketio.emit('task_error', {
            'uuid': file_uuid,
            'status': 'failed',
            'error': str(e),
            'message': f'PPT转换失败: {str(e)}'
        }, room=room_id)


def add_task(task_data):
    """添加任务到全局任务字典"""
    with tasks_lock:
        tasks[task_data['uuid']] = task_data


def get_task(file_uuid):
    """获取任务信息"""
    with tasks_lock:
        return tasks.get(file_uuid)


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
