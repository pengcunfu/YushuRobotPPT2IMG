from loguru import logger

from websocket_server import init_socketio_events, socketio, app


def start_flask_server(host='0.0.0.0', port=8020, debug=False):
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
