#!/usr/bin/env python3
"""
Flask PPT转图片服务启动脚本
"""

import os
import sys
from pathlib import Path

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import flask
        import loguru
        import win32com.client
        import pythoncom
        from PIL import Image
        print("✅ 所有依赖已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False

def check_directories():
    """检查并创建必要的目录"""
    directories = ['uploads', 'outputs']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ 目录已准备: {directory}")

def check_example_file():
    """检查示例文件"""
    example_file = Path("examples/1.pptx")
    if example_file.exists():
        print(f"✅ 示例文件存在: {example_file}")
    else:
        print(f"⚠️  示例文件不存在: {example_file}")
        print("   您可以上传自己的PPT文件进行测试")

def main():
    """主函数"""
    print("🚀 启动PPT转图片Flask服务...")
    print("=" * 50)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查目录
    check_directories()
    
    # 检查示例文件
    check_example_file()
    
    print("=" * 50)
    print("📋 服务信息:")
    print("   - 服务地址: http://localhost:5000")
    print("   - 上传目录: uploads/")
    print("   - 输出目录: outputs/")
    print("   - 测试页面: test_page.html")
    print("   - 测试客户端: python test_client.py")
    print("=" * 50)
    
    # 启动Flask服务
    try:
        from flask_server import app
        print("🎯 服务启动中...")
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,  # 生产环境建议设为False
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 服务启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
