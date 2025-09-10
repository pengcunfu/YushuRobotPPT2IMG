import os
import uuid
import time
import json
import asyncio
import threading
import base64
from pathlib import Path
import websockets
from loguru import logger
from pptx_to_images import pptx_to_images

# 配置
WEBSOCKET_HOST = "0.0.0.0"
WEBSOCKET_PORT = 8020
UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
ALLOWED_EXTENSIONS = {'.ppt', '.pptx'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# 确保目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

# 全局变量
connected_clients = {}  # {task_id: websocket}
tasks = {}  # 任务状态存储


class WebSocketPPTServer:
    def __init__(self):
        self.load_existing_tasks()

    def load_existing_tasks(self):
        """启动时加载已存在的任务结果"""
        if not os.path.exists(RESULT_FOLDER):
            return

        logger.info("正在加载已存在的任务结果...")

        for task_dir in os.listdir(RESULT_FOLDER):
            task_path = os.path.join(RESULT_FOLDER, task_dir)
            if os.path.isdir(task_path):
                try:
                    # 检查是否有图片文件
                    image_files = [f for f in os.listdir(task_path) if f.endswith('.png')]
                    if image_files:
                        # 尝试找到对应的原始文件
                        upload_file = None
                        for ext in ['.ppt', '.pptx']:
                            potential_file = os.path.join(UPLOAD_FOLDER, f"{task_dir}{ext}")
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
                            'image_paths': image_paths,
                            'completed_at': int(os.path.getmtime(task_path))
                        }

                        logger.info(f"恢复任务 {task_dir}，包含 {len(image_paths)} 张图片")
                except Exception as e:
                    logger.warning(f"恢复任务 {task_dir} 失败: {str(e)}")

        logger.info(f"已恢复 {len(tasks)} 个任务")

    async def handle_client(self, websocket):
        """处理WebSocket客户端连接"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"新客户端连接: {client_id}")

        try:
            # 发送欢迎消息
            await self.send_message(websocket, {
                "type": "welcome",
                "message": "PPT WebSocket服务器已连接",
                "server_info": {
                    "version": "2.0.0",
                    "max_file_size": MAX_FILE_SIZE,
                    "allowed_extensions": list(ALLOWED_EXTENSIONS)
                }
            })

            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(websocket, data)
                except json.JSONDecodeError:
                    await self.send_error(websocket, "Invalid JSON format")
                except Exception as e:
                    logger.error(f"处理消息时发生错误: {str(e)}")
                    await self.send_error(websocket, f"处理消息失败: {str(e)}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端断开连接: {client_id}")
        except Exception as e:
            logger.error(f"WebSocket连接错误: {str(e)}")
        finally:
            # 清理客户端连接
            for task_id, ws in list(connected_clients.items()):
                if ws == websocket:
                    del connected_clients[task_id]
                    logger.info(f"清理任务 {task_id} 的客户端连接")

    async def handle_message(self, websocket, data: dict):
        """处理WebSocket消息"""
        message_type = data.get("type")

        if message_type == "upload_ppt":
            await self.handle_upload(websocket, data)
        elif message_type == "get_task_status":
            await self.handle_get_task_status(websocket, data)
        elif message_type == "list_tasks":
            await self.handle_list_tasks(websocket)
        elif message_type == "get_task_images":
            await self.handle_get_task_images(websocket, data)
        elif message_type == "download_image":
            await self.handle_download_image(websocket, data)
        elif message_type == "ping":
            await self.send_message(websocket, {"type": "pong", "timestamp": time.time()})
        else:
            await self.send_error(websocket, f"未知的消息类型: {message_type}")

    async def handle_upload(self, websocket, data: dict):
        """处理PPT文件上传"""
        try:
            # 验证必需字段
            required_fields = ["filename", "file_data"]
            for field in required_fields:
                if field not in data:
                    await self.send_error(websocket, f"缺少必需字段: {field}")
                    return

            filename = data["filename"]
            file_data_b64 = data["file_data"]
            width = data.get("width", 1920)
            height = data.get("height", 1080)

            # 验证文件扩展名
            file_ext = Path(filename).suffix.lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                await self.send_error(websocket, f"不支持的文件类型: {file_ext}")
                return

            # 解码base64文件数据
            try:
                file_data = base64.b64decode(file_data_b64)
            except Exception as e:
                await self.send_error(websocket, f"文件数据解码失败: {str(e)}")
                return

            # 检查文件大小
            if len(file_data) > MAX_FILE_SIZE:
                await self.send_error(websocket, f"文件过大，最大允许 {MAX_FILE_SIZE // (1024 * 1024)}MB")
                return

            # 生成任务ID和保存文件
            task_id = str(uuid.uuid4())
            saved_filename = f"{task_id}{file_ext}"
            ppt_path = os.path.join(UPLOAD_FOLDER, saved_filename)

            # 保存文件
            with open(ppt_path, 'wb') as f:
                f.write(file_data)

            # 创建结果目录
            task_result_dir = os.path.join(RESULT_FOLDER, task_id)
            os.makedirs(task_result_dir, exist_ok=True)

            # 创建任务记录
            tasks[task_id] = {
                'id': task_id,
                'original_filename': filename,
                'filename': saved_filename,
                'ppt_path': ppt_path,
                'output_dir': task_result_dir,
                'status': 'pending',
                'created_at': time.time(),
                'width': width,
                'height': height
            }

            # 注册客户端连接
            connected_clients[task_id] = websocket

            # 发送任务创建确认
            await self.send_message(websocket, {
                "type": "task_created",
                "task_id": task_id,
                "status": "pending",
                "message": "PPT文件上传成功，开始处理..."
            })

            # 启动后台处理
            threading.Thread(
                target=self.process_ppt_task,
                args=(task_id, ppt_path, task_result_dir, width, height),
                daemon=True
            ).start()

            logger.info(f"任务 {task_id} 创建成功，文件: {filename}")

        except Exception as e:
            logger.error(f"处理上传时发生错误: {str(e)}")
            await self.send_error(websocket, f"上传处理失败: {str(e)}")

    async def handle_get_task_status(self, websocket, data: dict):
        """获取任务状态"""
        task_id = data.get("task_id")
        if not task_id:
            await self.send_error(websocket, "缺少task_id参数")
            return

        if task_id not in tasks:
            await self.send_error(websocket, "任务不存在")
            return

        task = tasks[task_id]
        response_data = {
            "type": "task_status",
            "task_id": task_id,
            "status": task["status"],
            "original_filename": task["original_filename"],
            "created_at": task["created_at"]
        }

        if task["status"] == "completed":
            # 构建图片信息
            image_files = []
            for i, path in enumerate(task.get("image_paths", [])):
                filename = os.path.basename(path)
                image_files.append({
                    "slide": i + 1,
                    "filename": filename,
                    "path": path
                })

            response_data.update({
                "image_count": len(task.get("image_paths", [])),
                "images": image_files,
                "completed_at": task.get("completed_at")
            })
        elif task["status"] == "failed":
            response_data["error"] = task.get("error", "未知错误")

        await self.send_message(websocket, response_data)

    async def handle_list_tasks(self, websocket):
        """列出所有任务"""
        task_list = []
        for task_id, task in tasks.items():
            task_info = {
                "task_id": task_id,
                "status": task["status"],
                "original_filename": task["original_filename"],
                "created_at": task["created_at"]
            }

            if task["status"] == "completed":
                task_info["image_count"] = len(task.get("image_paths", []))
                task_info["completed_at"] = task.get("completed_at")
            elif task["status"] == "failed":
                task_info["error"] = task.get("error", "未知错误")

            task_list.append(task_info)

        # 按创建时间倒序排列
        task_list.sort(key=lambda x: x["created_at"], reverse=True)

        await self.send_message(websocket, {
            "type": "task_list",
            "total": len(task_list),
            "tasks": task_list
        })

    async def handle_get_task_images(self, websocket, data: dict):
        """获取任务的所有图片信息"""
        task_id = data.get("task_id")
        if not task_id:
            await self.send_error(websocket, "缺少task_id参数")
            return

        if task_id not in tasks:
            await self.send_error(websocket, "任务不存在")
            return

        task = tasks[task_id]
        if task["status"] != "completed":
            await self.send_error(websocket, "任务尚未完成")
            return

        image_files = []
        for i, path in enumerate(task.get("image_paths", [])):
            filename = os.path.basename(path)
            image_files.append({
                "slide": i + 1,
                "filename": filename,
                "path": path
            })

        await self.send_message(websocket, {
            "type": "task_images",
            "task_id": task_id,
            "image_count": len(image_files),
            "images": image_files
        })

    async def handle_download_image(self, websocket, data: dict):
        """下载图片文件"""
        task_id = data.get("task_id")
        filename = data.get("filename")

        if not task_id or not filename:
            await self.send_error(websocket, "缺少task_id或filename参数")
            return

        if task_id not in tasks:
            await self.send_error(websocket, "任务不存在")
            return

        task = tasks[task_id]
        image_path = os.path.join(task["output_dir"], filename)

        if not os.path.exists(image_path):
            await self.send_error(websocket, "图片文件不存在")
            return

        try:
            # 读取图片文件并编码为base64
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            await self.send_message(websocket, {
                "type": "image_data",
                "task_id": task_id,
                "filename": filename,
                "image_data": image_data,
                "content_type": "image/png"
            })

        except Exception as e:
            logger.error(f"读取图片文件失败: {str(e)}")
            await self.send_error(websocket, f"读取图片失败: {str(e)}")

    def process_ppt_task(self, task_id: str, ppt_path: str, output_dir: str, width: int, height: int):
        """后台处理PPT转图片任务"""
        try:
            logger.info(f"开始处理任务 {task_id}: {ppt_path}")
            tasks[task_id]['status'] = 'processing'

            # 发送处理开始通知
            asyncio.run(self.notify_client(task_id, {
                "type": "task_update",
                "task_id": task_id,
                "status": "processing",
                "message": "正在处理PPT文件..."
            }))

            # 调用转换函数
            image_paths = pptx_to_images(ppt_path, output_dir, width, height)

            # 更新任务状态
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['image_paths'] = image_paths
            tasks[task_id]['completed_at'] = time.time()

            logger.info(f"任务 {task_id} 完成，生成了 {len(image_paths)} 张图片")

            # 发送完成通知
            asyncio.run(self.notify_client(task_id, {
                "type": "task_completed",
                "task_id": task_id,
                "status": "completed",
                "message": f"PPT转换完成，生成了 {len(image_paths)} 张图片",
                "image_count": len(image_paths),
                "images": [
                    {
                        "slide": i + 1,
                        "filename": os.path.basename(path),
                        "path": path
                    }
                    for i, path in enumerate(image_paths)
                ]
            }))

        except Exception as e:
            logger.error(f"任务 {task_id} 处理失败: {str(e)}")
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)

            # 发送失败通知
            asyncio.run(self.notify_client(task_id, {
                "type": "task_failed",
                "task_id": task_id,
                "status": "failed",
                "message": "PPT转换失败",
                "error": str(e)
            }))

    async def notify_client(self, task_id: str, message: dict):
        """通知特定任务的客户端"""
        if task_id in connected_clients:
            websocket = connected_clients[task_id]
            try:
                await self.send_message(websocket, message)
            except Exception as e:
                logger.error(f"发送通知到客户端失败: {str(e)}")
                # 移除无效连接
                if task_id in connected_clients:
                    del connected_clients[task_id]

    async def send_message(self, websocket, message: dict):
        """发送消息到WebSocket客户端"""
        try:
            await websocket.send(json.dumps(message, ensure_ascii=False))
        except websockets.exceptions.ConnectionClosed:
            logger.warning("尝试向已关闭的连接发送消息")
        except Exception as e:
            logger.error(f"发送WebSocket消息失败: {str(e)}")
            raise

    async def send_error(self, websocket, error_message: str):
        """发送错误消息"""
        await self.send_message(websocket, {
            "type": "error",
            "message": error_message,
            "timestamp": time.time()
        })

    async def start_server(self):
        """启动WebSocket服务器"""
        logger.info(f"启动WebSocket PPT服务器在 {WEBSOCKET_HOST}:{WEBSOCKET_PORT}")

        async with websockets.serve(
                self.handle_client,
                WEBSOCKET_HOST,
                WEBSOCKET_PORT,
                max_size=MAX_FILE_SIZE + 1024 * 1024,  # 给base64编码留出空间
                ping_interval=30,
                ping_timeout=10
        ):
            logger.info("WebSocket服务器启动成功，等待客户端连接...")
            await asyncio.Future()  # 永久运行


def main():
    """主函数"""
    try:
        server = WebSocketPPTServer()
        asyncio.run(server.start_server())
    except KeyboardInterrupt:
        logger.info("服务器被用户中断")
    except Exception as e:
        logger.error(f"服务器启动失败: {str(e)}")
        raise


if __name__ == "__main__":
    main()
