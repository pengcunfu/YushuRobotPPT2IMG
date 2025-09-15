"""
WebSocket客户端V2 - 测试PPT处理服务
用于测试基于URL的PPT处理功能
使用Flask-SocketIO实现，解决代理问题
"""
import socketio
import time
import uuid
from loguru import logger


class PPTProcessingClient:
    """PPT处理客户端"""

    def __init__(self, server_url="http://8.149.241.205:8020"):
        self.server_url = server_url
        self.sio = socketio.Client()
        self.current_task = None
        self.setup_events()

    def setup_events(self):
        """设置WebSocket事件处理"""

        @self.sio.event
        def connect():
            logger.info("✅ 已连接到服务器")
            print("✅ 已连接到PPT处理服务器V2")

        @self.sio.event
        def disconnect():
            logger.info("❌ 与服务器断开连接")
            print("❌ 与服务器断开连接")

        @self.sio.event
        def connected(data):
            logger.info(f"服务器响应: {data}")
            print(f"📡 服务器响应: {data['message']}")

        @self.sio.event
        def task_created(data):
            logger.info(f"任务已创建: {data}")
            print(f"📋 任务已创建:")
            print(f"   UUID: {data['uuid']}")
            print(f"   PPT名称: {data['ppt_name']}")
            print(f"   消息: {data['message']}")
            self.current_task = data['uuid']

        @self.sio.event
        def progress_update(data):
            logger.info(f"进度更新: {data}")
            print(f"🔄 处理进度: {data['message']}")
            if data.get('total_slides', 0) > 0:
                progress = (data.get('processed_slides', 0) / data['total_slides']) * 100
                print(f"   进度: {progress:.1f}% ({data.get('processed_slides', 0)}/{data['total_slides']})")

        @self.sio.event
        def task_complete(data):
            logger.info(f"任务完成: {data}")
            print(f"\n🎉 PPT处理完成!")
            print(f"   PPT名称: {data['ppt_name']}")
            print(f"   总幻灯片数: {data['total_slides']}")
            print(f"   成功处理: {data['processed_slides']}")
            print(f"   下载URL数量: {len(data['download_urls'])}")

            # 显示所有下载URL
            print(f"\n📥 所有下载URLs:")
            for i, url in enumerate(data['download_urls']):
                print(f"   {i + 1:2d}. {url}")

            print(f"\n✅ 测试完成！共获得 {len(data['download_urls'])} 个图片下载链接")

        @self.sio.event
        def task_error(data):
            logger.error(f"任务失败: {data}")
            print(f"❌ 任务失败:")
            print(f"   UUID: {data['uuid']}")
            if 'ppt_name' in data:
                print(f"   PPT名称: {data['ppt_name']}")
            print(f"   状态: {data['status']}")
            print(f"   错误: {data['error']}")
            print(f"   消息: {data['message']}")

        @self.sio.event
        def error(data):
            logger.error(f"服务器错误: {data}")
            print(f"❌ 服务器错误: {data['message']}")

        @self.sio.event
        def task_status(data):
            """处理任务状态查询响应"""
            logger.info(f"任务状态: {data}")
            print(f"📊 任务状态:")
            print(f"   UUID: {data['uuid']}")
            print(f"   PPT名称: {data['ppt_name']}")
            print(f"   状态: {data['status']}")
            print(f"   进度: {data.get('progress', 0)}%")
            if data.get('total_slides', 0) > 0:
                print(f"   幻灯片: {data.get('processed_slides', 0)}/{data['total_slides']}")
            if data.get('download_urls'):
                print(f"   下载链接数量: {len(data['download_urls'])}")
            if data.get('error'):
                print(f"   错误: {data['error']}")
            print(f"   消息: {data['message']}")

    def connect(self):
        """连接到服务器"""
        try:
            self.sio.connect(self.server_url)
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            print(f"❌ 连接失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        self.sio.disconnect()

    def start_ppt_processing(self, ppt_url, ppt_name, width=1920, height=1080):
        """启动PPT处理任务"""
        task_data = {
            "ppt_url": ppt_url,
            "ppt_name": ppt_name,
            "width": width,
            "height": height
        }

        logger.info(f"发送处理请求: {task_data}")
        print(f"🚀 发送PPT处理请求:")
        print(f"   URL: {ppt_url}")
        print(f"   名称: {ppt_name}")
        print(f"   尺寸: {width}x{height}")
        print(f"   存储桶: images (服务器固定设置)")

        self.sio.emit('start_ppt_processing', task_data)

    def join_task(self, task_uuid):
        """加入现有任务的房间"""
        task_data = {
            "uuid": task_uuid
        }

        logger.info(f"加入任务: {task_data}")
        print(f"🔗 加入任务: {task_uuid}")

        self.sio.emit('join_task', task_data)

    def get_task_status(self, task_uuid):
        """获取任务状态"""
        task_data = {
            "uuid": task_uuid
        }

        logger.info(f"查询任务状态: {task_data}")
        print(f"📊 查询任务状态: {task_uuid}")

        self.sio.emit('get_task_status', task_data)


def main():
    """主函数"""
    print("🚀 PPT处理服务测试客户端V2")
    print("=" * 50)
    print("📋 功能说明:")
    print("   - 连接到WebSocket服务器")
    print("   - 发送PPT URL和名称")
    print("   - 接收处理进度更新")
    print("   - 获取图片下载链接")
    print("   - 支持任务状态查询")
    print("   - 支持加入现有任务")
    print("=" * 50)

    # 创建客户端
    client = PPTProcessingClient()

    # 连接到服务器
    if not client.connect():
        print("❌ 无法连接到服务器，请确保服务器正在运行")
        return

    try:
        # 使用测试数据（参考pptx_to_images_minio.py的测试函数）
        test_url = "http://8.153.175.16:9001/api/v1/download-shared-object/aHR0cDovLzEyNy4wLjAuMTo5MDAwL2RhdGEvJUU0JUI5JTlEJUU0JUI4JTg5JUU5JTk4JTg1JUU1JTg1JUI1LUFJJUU2JUFEJUE2JUU1JTk5JUE4LnBwdHg_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1TSTJQV1c4V1dBM1A1U0tUQUlXWCUyRjIwMjUwOTEyJTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI1MDkxMlQxNjQwNDNaJlgtQW16LUV4cGlyZXM9NDMxOTkmWC1BbXotU2VjdXJpdHktVG9rZW49ZXlKaGJHY2lPaUpJVXpVeE1pSXNJblI1Y0NJNklrcFhWQ0o5LmV5SmhZMk5sYzNOTFpYa2lPaUpUU1RKUVYxYzRWMWRCTTFBMVUwdFVRVWxYV0NJc0ltVjRjQ0k2TVRjMU56Y3pPRFF6TWl3aWNHRnlaVzUwSWpvaWJXbHVhVzloWkcxcGJpSjkuMDVaZFlKS3hEa2pjMGdVeFltTDdPeldjRnVkS01QVGE3d2hhSVFTaWhJdnZLMG5HcF9EYVRieW5QS2NBS0ZvMjdxZ3FqWWdxX0JvU0VwWnBoU3hkaVEmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0JnZlcnNpb25JZD1udWxsJlgtQW16LVNpZ25hdHVyZT0xZDMxNTQ2OTMyMzdmZjgzNzgyNTdkYWJjMDljMDc5ZjYyZGJlMzQyMzM2NDA3MGRiOTU3M2VhOTUwZmViNzU0"
        test_name = str(uuid.uuid4())  # 使用UUID作为PPT名称

        print(f"\n🚀 使用测试数据:")
        print(f"   URL: {test_url[:100]}...")
        print(f"   名称: {test_name}")

        # 启动处理任务
        client.start_ppt_processing(
            ppt_url=test_url,
            ppt_name=test_name,
            width=1920,
            height=1080
        )

        # 等待处理完成
        print("\n⏳ 等待处理完成...")
        print("💡 提示: 按Ctrl+C中断，或输入命令:")
        print("   - 'status <uuid>' 查询任务状态")
        print("   - 'join <uuid>' 加入现有任务")
        print("   - 'quit' 退出程序")

        try:
            while True:
                user_input = input("\n> ").strip()
                if user_input.lower() == 'quit':
                    break
                elif user_input.startswith('status '):
                    task_uuid = user_input[7:].strip()
                    if task_uuid:
                        client.get_task_status(task_uuid)
                    else:
                        print("❌ 请提供任务UUID")
                elif user_input.startswith('join '):
                    task_uuid = user_input[5:].strip()
                    if task_uuid:
                        client.join_task(task_uuid)
                    else:
                        print("❌ 请提供任务UUID")
                elif user_input:
                    print("❌ 未知命令，请输入 'status <uuid>', 'join <uuid>' 或 'quit'")
        except KeyboardInterrupt:
            print("\n⏹️ 用户中断")

    except Exception as e:
        logger.error(f"测试异常: {e}")
        print(f"❌ 测试异常: {e}")
    finally:
        client.disconnect()
        print("🔌 已断开连接")
        print("✅ 测试完成")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ 程序被中断")
    except Exception as e:
        logger.error(f"程序异常: {e}")
        print(f"❌ 程序异常: {e}")
