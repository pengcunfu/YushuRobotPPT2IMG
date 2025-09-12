"""
WebSocket客户端V2 - 测试PPT处理服务
用于测试基于URL的PPT处理功能
使用Flask-SocketIO实现，解决代理问题
"""
import socketio
import time
from loguru import logger

# 配置日志
logger.add("test_client_v2.log", rotation="1 MB", level="DEBUG")

class PPTProcessingClient:
    """PPT处理客户端"""
    
    def __init__(self, server_url="http://localhost:5000"):
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
            print(f"🎉 PPT处理完成!")
            print(f"   PPT名称: {data['ppt_name']}")
            print(f"   总幻灯片数: {data['total_slides']}")
            print(f"   成功处理: {data['processed_slides']}")
            print(f"   下载URL数量: {len(data['download_urls'])}")
            
            # 显示前几个下载URL
            print(f"   📥 下载URLs:")
            for i, url in enumerate(data['download_urls'][:3]):
                print(f"     {i+1}. {url}")
            if len(data['download_urls']) > 3:
                print(f"     ... 还有 {len(data['download_urls']) - 3} 个URL")
        
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
    
    def start_ppt_processing(self, ppt_url, ppt_name, width=1920, height=1080, bucket_name="images"):
        """启动PPT处理任务"""
        task_data = {
            "ppt_url": ppt_url,
            "ppt_name": ppt_name,
            "width": width,
            "height": height,
            "bucket_name": bucket_name
        }
        
        logger.info(f"发送处理请求: {task_data}")
        print(f"🚀 发送PPT处理请求:")
        print(f"   URL: {ppt_url}")
        print(f"   名称: {ppt_name}")
        print(f"   尺寸: {width}x{height}")
        print(f"   存储桶: {bucket_name}")
        
        self.sio.emit('start_ppt_processing', task_data)


def main():
    """主函数"""
    print("🚀 PPT处理服务测试客户端V2")
    print("=" * 50)
    
    # 创建客户端
    client = PPTProcessingClient()
    
    # 连接到服务器
    if not client.connect():
        print("❌ 无法连接到服务器，请确保服务器正在运行")
        return
    
    try:
        # 获取用户输入
        print("\n请输入PPT处理参数:")
        ppt_url = input("PPT URL: ").strip()
        ppt_name = input("PPT名称: ").strip()
        
        if not ppt_url or not ppt_name:
            print("❌ URL和名称不能为空")
            return
        
        # 启动处理任务
        client.start_ppt_processing(
            ppt_url=ppt_url,
            ppt_name=ppt_name,
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