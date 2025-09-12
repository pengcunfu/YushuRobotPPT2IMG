"""
WebSocket客户端V2 - 测试PPT处理服务
用于测试基于URL的PPT处理功能
使用Flask-SocketIO实现，解决代理问题
使用模型类进行数据封装
"""
import socketio
import time
import uuid
from loguru import logger

from websocket_models import PPTProcessingRequest

# 配置日志
logger.add("test_client_v2.log", rotation="1 MB", level="DEBUG")


class PPTProcessingClient:
    """PPT处理客户端"""

    def __init__(self, server_url="http://localhost:8020"):
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
            print(f"   错误: {data['error']}")
            print(f"   消息: {data['message']}")

        @self.sio.event
        def error(data):
            logger.error(f"服务器错误: {data}")
            print(f"❌ 服务器错误: {data['message']}")

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
        # 使用模型类创建请求
        request = PPTProcessingRequest(
            ppt_url=ppt_url,
            ppt_name=ppt_name,
            width=width,
            height=height
        )

        logger.info(f"发送处理请求: {request.to_dict()}")
        print(f"🚀 发送PPT处理请求:")
        print(f"   URL: {ppt_url}")
        print(f"   名称: {ppt_name}")
        print(f"   尺寸: {width}x{height}")
        print(f"   存储桶: images (服务器端固定)")

        self.sio.emit('start_ppt_processing', request.to_dict())


def main():
    """主函数"""
    print("🚀 PPT处理服务测试客户端V2")
    print("=" * 50)
    print("📋 功能说明:")
    print("   - 连接到WebSocket服务器")
    print("   - 发送PPT URL和名称")
    print("   - 接收处理进度更新")
    print("   - 获取图片下载链接")
    print("   - 使用模型类进行数据封装")
    print("=" * 50)

    # 创建客户端
    client = PPTProcessingClient()

    # 连接到服务器
    if not client.connect():
        print("❌ 无法连接到服务器，请确保服务器正在运行")
        return

    try:
        # 使用测试数据（参考pptx_to_images_minio.py的测试函数）
        test_url = "http://8.153.175.16:9001/api/v1/download-shared-object/aHR0cDovLzEyNy4wLjAuMTo5MDAwL2RvY3VtZW50cy8lRTQlQjklOUQlRTQlQjglODklRTklOTglODUlRTUlODUlQjUtQUklRTYlQUQlQTYlRTUlOTklQTgucHB0eD9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPTVMRTc3UzdGOUZEVkdEMzRYTzg5JTJGMjAyNTA5MTIlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjUwOTEyVDAyNTc0N1omWC1BbXotRXhwaXJlcz00MzIwMCZYLUFtei1TZWN1cml0eS1Ub2tlbj1leUpoYkdjaU9pSklVelV4TWlJc0luUjVjQ0k2SWtwWFZDSjkuZXlKaFkyTmxjM05MWlhraU9pSTFURVUzTjFNM1JqbEdSRlpIUkRNMFdFODRPU0lzSW1WNGNDSTZNVGMxTnpZNE5qVTJPU3dpY0dGeVpXNTBJam9pYldsdWFXOWhaRzFwYmlKOS4xY1JmWEJTSWJnT3dmdUI4OXRlczB3MFlQanFRLXFBeW1mMk5CS0lwWWhCbnd2TUtsUUl2d25JLVdNSGUxOXNDSWJ2aGY4bDhtVG5aZ25NWmNuckdMUSZYLUFtei1TaWduZWRIZWFkZXJzPWhvc3QmdmVyc2lvbklkPW51bGwmWC1BbXotU2lnbmF0dXJlPTcxY2E5YzViMTU5N2Y1OGZkMjc5NzkzN2MyNWUwNzY5ZmQ1ZTUxZjEyNmQ1Njk3N2I1MmY3MmE5Mzg3OWI0ZTA"
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
        print("\n⏳ 等待处理完成... (按Ctrl+C中断)")
        try:
            while True:
                time.sleep(1)
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
