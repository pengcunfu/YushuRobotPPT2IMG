"""
WebSocket服务器V2 - 基于URL的PPT处理服务
客户端提供PPT URL和文件名，服务器处理并返回图片下载URL
基于Flask-SocketIO实现，解决代理问题
"""
import os
import time
import threading
import queue
import re
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from loguru import logger

from pptx_to_images_minio import pptx_url_to_minio_images
from websocket_models import (
    PPTProcessingRequest, TaskJoinRequest, TaskStatusRequest,
    ConnectedResponse, TaskCreatedResponse, ProgressUpdateResponse,
    TaskCompleteResponse, TaskErrorResponse, TaskStatusResponse,
    ErrorResponse, TaskData, ConnectionInfo, ServerStats
)

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
        response = ConnectedResponse(message='已连接到PPT处理服务器V2')
        emit('connected', response.to_dict())

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
        try:
            # 解析请求数据
            ppt_request = PPTProcessingRequest.from_dict(data)
        except Exception as e:
            error_response = ErrorResponse(message=f'请求数据格式错误: {str(e)}')
            emit('error', error_response.to_dict())
            return

        # 验证必需参数
        if not ppt_request.ppt_url or not ppt_request.ppt_name:
            error_response = ErrorResponse(message='缺少必需参数: ppt_url 和 ppt_name')
            emit('error', error_response.to_dict())
            return

        # 创建任务数据（bucket_name在服务器端固定设置）
        task_data = TaskData.create_new(
            ppt_url=ppt_request.ppt_url,
            ppt_name=ppt_request.ppt_name,
            width=ppt_request.width,
            height=ppt_request.height,
            bucket_name="images"  # 固定使用images存储桶
        )

        # 检查并发任务数量
        with tasks_lock:
            active_tasks = sum(1 for t in tasks.values() if t.status in ['queued', 'processing'])
            if active_tasks >= MAX_CONCURRENT_TASKS:
                error_response = ErrorResponse(message=f'服务器繁忙，当前有 {active_tasks} 个任务在处理中，请稍后重试')
                emit('error', error_response.to_dict())
                return

            # 添加任务
            task_data.status = 'queued'
            task_data.queued_at = time.time()
            tasks[task_data.uuid] = task_data

        # 将客户端加入到特定的房间（以UUID命名）
        room_id = f"task_{task_data.uuid}"
        join_room(room_id)

        with connections_lock:
            connection_info = ConnectionInfo(room=room_id, uuid=task_data.uuid)
            active_connections[request.sid] = connection_info

        logger.info(f'任务 {task_data.uuid} 已创建: {task_data.ppt_name}')

        response = TaskCreatedResponse(
            uuid=task_data.uuid,
            ppt_name=task_data.ppt_name,
            message='任务已创建并加入处理队列'
        )
        emit('task_created', response.to_dict())

        # 将任务提交到线程池
        future = task_executor.submit(process_ppt_task, task_data.uuid, room_id, socketio)

        # 添加回调来处理任务完成或异常
        def task_done_callback(future):
            try:
                future.result()  # 获取结果，如果有异常会抛出
            except Exception as e:
                logger.error(f"任务 {task_data.uuid} 执行异常: {e}")
                with tasks_lock:
                    if task_data.uuid in tasks:
                        tasks[task_data.uuid].status = 'failed'
                        tasks[task_data.uuid].error = str(e)

                error_response = TaskErrorResponse(
                    uuid=task_data.uuid,
                    status='failed',
                    error=str(e),
                    message=f'任务执行异常: {str(e)}'
                )
                socketio.emit('task_error', error_response.to_dict(), room=room_id)

        future.add_done_callback(task_done_callback)

    @socketio.on('join_task')
    def handle_join_task(data):
        """加入现有任务的房间"""
        try:
            # 解析请求数据
            join_request = TaskJoinRequest.from_dict(data)
        except Exception as e:
            error_response = ErrorResponse(message=f'请求数据格式错误: {str(e)}')
            emit('error', error_response.to_dict())
            return

        with tasks_lock:
            if not join_request.uuid or join_request.uuid not in tasks:
                error_response = ErrorResponse(message='无效的任务UUID')
                emit('error', error_response.to_dict())
                return

            task = tasks[join_request.uuid]

        room_id = f"task_{join_request.uuid}"
        join_room(room_id)

        with connections_lock:
            connection_info = ConnectionInfo(room=room_id, uuid=join_request.uuid)
            active_connections[request.sid] = connection_info

        # 发送当前任务状态
        response = TaskStatusResponse(
            uuid=task.uuid,
            ppt_name=task.ppt_name,
            status=task.status,
            progress=task.progress,
            total_slides=task.total_slides,
            processed_slides=task.processed_slides,
            download_urls=task.download_urls,
            message='任务状态'
        )
        emit('task_status', response.to_dict())

    @socketio.on('get_task_status')
    def handle_get_task_status(data):
        """获取任务状态"""
        try:
            # 解析请求数据
            status_request = TaskStatusRequest.from_dict(data)
        except Exception as e:
            error_response = ErrorResponse(message=f'请求数据格式错误: {str(e)}')
            emit('error', error_response.to_dict())
            return

        with tasks_lock:
            if not status_request.uuid or status_request.uuid not in tasks:
                error_response = ErrorResponse(message='无效的任务UUID')
                emit('error', error_response.to_dict())
                return

            task = tasks[status_request.uuid]

        response = TaskStatusResponse(
            uuid=task.uuid,
            ppt_name=task.ppt_name,
            status=task.status,
            progress=task.progress,
            total_slides=task.total_slides,
            processed_slides=task.processed_slides,
            download_urls=task.download_urls,
            error=task.error,
            message='任务状态'
        )
        emit('task_status', response.to_dict())


def init_socketio():
    """初始化SocketIO"""
    init_socketio_events()
    return socketio


def process_ppt_task(task_uuid, room_id, socketio):
    """处理PPT转图片的后台任务"""
    try:
        with tasks_lock:
            task = tasks[task_uuid]
            task.status = 'processing'
            task.started_at = time.time()

        logger.info(f'开始处理任务 {task_uuid}: {task.ppt_name}')

        # 发送开始处理消息
        progress_response = ProgressUpdateResponse(
            uuid=task_uuid,
            status='processing',
            progress=0,
            total_slides=0,
            processed_slides=0,
            message='正在下载PPT文件...'
        )
        socketio.emit('progress_update', progress_response.to_dict(), room=room_id)

        # 定义进度回调函数
        def progress_callback(stage, message, progress):
            """进度回调函数"""
            # 根据阶段更新任务信息
            with tasks_lock:
                if task_uuid in tasks:
                    current_task = tasks[task_uuid]
                    current_task.progress = progress
                    
                    # 如果是转换完成阶段，更新幻灯片数量
                    if stage == "convert" and "生成" in message:
                        # 从消息中提取幻灯片数量
                        match = re.search(r'生成 (\d+) 张图片', message)
                        if match:
                            current_task.total_slides = int(match.group(1))
                    
                    # 如果是上传阶段，更新已处理数量
                    elif stage == "upload" and "正在上传图片" in message:
                        # 从消息中提取当前上传进度
                        match = re.search(r'正在上传图片 \((\d+)/(\d+)\)', message)
                        if match:
                            current_task.processed_slides = int(match.group(1))
                            if current_task.total_slides == 0:
                                current_task.total_slides = int(match.group(2))
            
            progress_response = ProgressUpdateResponse(
                uuid=task_uuid,
                status='processing',
                progress=progress,
                total_slides=task.total_slides,
                processed_slides=task.processed_slides,
                message=f"[{stage.upper()}] {message}"
            )
            socketio.emit('progress_update', progress_response.to_dict(), room=room_id)

        # 调用PPT转图片并上传到MinIO的函数
        import asyncio
        result = asyncio.run(pptx_url_to_minio_images(
            ppt_url=task.ppt_url,
            ppt_name=task.ppt_name,
            bucket_name=task.bucket_name,
            width=task.width,
            height=task.height,
            progress_callback=progress_callback
        ))

        # 处理成功（如果函数正常返回，说明没有异常）
        with tasks_lock:
            task.status = 'completed'
            task.total_slides = result.total_slides
            task.processed_slides = result.successful_uploads
            task.progress = 100
            task.download_urls = result.download_urls
            task.completed_at = time.time()

        logger.info(f'任务 {task_uuid} 完成: 成功处理 {result.successful_uploads} 张图片')

        complete_response = TaskCompleteResponse(
            uuid=task_uuid,
            ppt_name=task.ppt_name,
            status='completed',
            progress=100,
            total_slides=result.total_slides,
            processed_slides=result.successful_uploads,
            download_urls=result.download_urls,
            message=f'PPT处理完成！生成了 {result.successful_uploads} 张图片'
        )
        socketio.emit('task_complete', complete_response.to_dict(), room=room_id)

    except Exception as e:
        # 任务异常
        with tasks_lock:
            if task_uuid in tasks:
                tasks[task_uuid].status = 'failed'
                tasks[task_uuid].error = str(e)

        logger.error(f'任务 {task_uuid} 异常: {e}')

        error_response = TaskErrorResponse(
            uuid=task_uuid,
            status='failed',
            error=str(e),
            message=f'PPT处理异常: {str(e)}'
        )
        socketio.emit('task_error', error_response.to_dict(), room=room_id)


def add_task(task_data: TaskData):
    """添加任务到全局任务字典"""
    with tasks_lock:
        tasks[task_data.uuid] = task_data


def get_task(task_uuid: str) -> TaskData:
    """获取任务信息"""
    with tasks_lock:
        return tasks.get(task_uuid)


def get_all_tasks() -> dict:
    """获取所有任务"""
    with tasks_lock:
        return tasks.copy()


def get_server_stats() -> ServerStats:
    """获取服务器统计信息"""
    with tasks_lock:
        total_tasks = len(tasks)
        active_tasks = sum(1 for t in tasks.values() if t.status == 'processing')
        queued_tasks = sum(1 for t in tasks.values() if t.status == 'queued')
        completed_tasks = sum(1 for t in tasks.values() if t.status == 'completed')
        failed_tasks = sum(1 for t in tasks.values() if t.status == 'failed')

    with connections_lock:
        active_connections_count = len(active_connections)

    return ServerStats(
        total_tasks=total_tasks,
        active_tasks=active_tasks,
        queued_tasks=queued_tasks,
        completed_tasks=completed_tasks,
        failed_tasks=failed_tasks,
        active_connections=active_connections_count,
        max_concurrent_tasks=MAX_CONCURRENT_TASKS
    )
