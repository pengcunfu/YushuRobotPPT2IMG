"""
启动WebSocket服务器V2
"""
import os
import sys
from loguru import logger

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 配置日志
logger.add("websocket_server_v2.log", rotation="10 MB", level="DEBUG")

if __name__ == "__main__":
    try:
        from websocket_server_v2 import start_flask_server
        
        # 启动服务器
        start_flask_server()
        
    except KeyboardInterrupt:
        logger.info("⏹️ 服务器已停止")
        print("\n⏹️ 服务器已停止")
    except Exception as e:
        logger.error(f"❌ 启动失败: {e}")
        print(f"❌ 启动失败: {e}")
        sys.exit(1)
