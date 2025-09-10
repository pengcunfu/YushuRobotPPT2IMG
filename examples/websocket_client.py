import asyncio
import websockets
import json
import base64
import sys
import os


class WebSocketPPTClient:
    def __init__(self, server_url="ws://localhost:8020"):
        self.server_url = server_url
        self.websocket = None
        self.task_id = None

    async def connect(self):
        try:
            # 绕过代理设置，直接连接
            self.websocket = await websockets.connect(
                self.server_url,
                ping_interval=None,  # 禁用ping避免代理干扰
                close_timeout=5,
            )
            print(f"已连接到服务器: {self.server_url}")
            return True
        except Exception as e:
            print(f"连接失败: {str(e)}")
            print("提示: 如果使用了代理，请尝试临时禁用代理")
            return False

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            print("已断开连接")

    async def send_message(self, message):
        if not self.websocket:
            raise Exception("未连接到服务器")
        await self.websocket.send(json.dumps(message, ensure_ascii=False))

    async def receive_message(self):
        if not self.websocket:
            raise Exception("未连接到服务器")
        message = await self.websocket.recv()
        return json.loads(message)

    async def upload_ppt(self, file_path, width=1920, height=1080):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(file_path, 'rb') as f:
            file_data = f.read()

        file_data_b64 = base64.b64encode(file_data).decode('utf-8')
        filename = os.path.basename(file_path)

        print(f"上传文件: {filename} ({len(file_data)} bytes)")

        upload_message = {
            "type": "upload_ppt",
            "filename": filename,
            "file_data": file_data_b64,
            "width": width,
            "height": height
        }

        await self.send_message(upload_message)
        response = await self.receive_message()

        if response.get("type") == "task_created":
            self.task_id = response["task_id"]
            print(f"任务创建成功: {self.task_id}")
            return self.task_id
        elif response.get("type") == "error":
            raise Exception(f"上传失败: {response['message']}")
        else:
            raise Exception(f"意外响应: {response}")

    async def wait_for_completion(self):
        if not self.task_id:
            raise Exception("没有活动任务")

        print("等待任务完成...")

        while True:
            try:
                message = await self.receive_message()
                message_type = message.get("type")

                if message_type == "task_update":
                    print(f"任务更新: {message['status']} - {message.get('message', '')}")

                elif message_type == "task_completed":
                    print(f"✅ 任务完成!")
                    print(f"生成图片数量: {message['image_count']}")

                    images = message.get("images", [])
                    for img in images:
                        print(f"  - 幻灯片 {img['slide']}: {img['filename']}")

                    return message

                elif message_type == "task_failed":
                    print(f"❌ 任务失败: {message.get('error', '未知错误')}")
                    return message

                elif message_type == "error":
                    print(f"服务器错误: {message['message']}")
                    return message

            except websockets.exceptions.ConnectionClosed:
                print("连接已断开")
                break
            except Exception as e:
                print(f"接收消息时发生错误: {str(e)}")
                break

    async def download_image(self, task_id, filename):
        await self.send_message({
            "type": "download_image",
            "task_id": task_id,
            "filename": filename
        })

        response = await self.receive_message()

        if response.get("type") == "image_data":
            image_data = base64.b64decode(response["image_data"])
            return image_data
        elif response.get("type") == "error":
            raise Exception(f"下载失败: {response['message']}")
        else:
            raise Exception(f"意外响应: {response}")

    async def download_all_images(self, task_id, output_dir="downloads"):
        await self.send_message({
            "type": "get_task_status",
            "task_id": task_id
        })

        status_response = await self.receive_message()

        if status_response.get("status") != "completed":
            raise Exception("任务尚未完成")

        images = status_response.get("images", [])
        if not images:
            print("没有找到图片")
            return

        os.makedirs(output_dir, exist_ok=True)
        print(f"开始下载 {len(images)} 张图片到 {output_dir}/")

        for img in images:
            filename = img["filename"]
            print(f"下载: {filename}")

            try:
                image_data = await self.download_image(task_id, filename)
                output_path = os.path.join(output_dir, filename)
                with open(output_path, 'wb') as f:
                    f.write(image_data)
                print(f"  ✅ 已保存: {output_path}")
            except Exception as e:
                print(f"  ❌ 下载失败: {str(e)}")

        print("所有图片下载完成!")


async def main():
    if len(sys.argv) < 2:
        print("用法: python websocket_client.py <PPT文件路径> [宽度] [高度]")
        return

    file_path = sys.argv[1]
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1920
    height = int(sys.argv[3]) if len(sys.argv) > 3 else 1080

    client = WebSocketPPTClient()

    try:
        if not await client.connect():
            return

        welcome = await client.receive_message()
        if welcome.get("type") == "welcome":
            print(f"服务器版本: {welcome.get('server_info', {}).get('version')}")

        task_id = await client.upload_ppt(file_path, width, height)
        result = await client.wait_for_completion()

        if result.get("type") == "task_completed":
            print("\n🎉 转换完成！")
            download = input("是否下载生成的图片？(y/N): ").strip().lower()
            if download in ['y', 'yes', '是']:
                output_dir = input("请输入下载目录 (默认: downloads): ").strip() or "downloads"
                await client.download_all_images(task_id, output_dir)

    except KeyboardInterrupt:
        print("\n操作被用户中断")
    except Exception as e:
        print(f"发生错误: {str(e)}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
