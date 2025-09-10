import time
from flask import Flask, request, jsonify

# 回调服务器配置
CALLBACK_SERVER_HOST = "localhost"
CALLBACK_SERVER_PORT = 8021
CALLBACK_ENDPOINT = "/callback"

# 创建回调服务器
app = Flask(__name__)

# 存储收到的回调
callbacks = []


@app.route(CALLBACK_ENDPOINT, methods=['POST'])
def callback_handler():
    """接收API服务器的回调通知"""
    data = request.json
    print(f"\n收到回调通知: {data}\n")
    print("=" * 60)
    print(f"任务ID: {data.get('task_id')}")
    print(f"状态: {data.get('status')}")
    print(f"原始文件名: {data.get('original_filename')}")
    print(f"UUID文件名: {data.get('filename')}")
    print(f"创建时间: {data.get('created_at')}")
    
    if data.get('status') == 'completed':
        print(f"生成的图片数量: {data.get('image_count', 0)}")
        for img in data.get('images', []):
            print(f" - 幻灯片 {img['slide']}: {img['path']}")
        print(f"完成时间: {data.get('completed_at')}")
    elif data.get('status') == 'failed':
        print(f"错误: {data.get('error', '未知错误')}")
    
    print("=" * 60)
    
    callbacks.append(data)
    return jsonify({"status": "success", "message": "回调接收成功"})


@app.route('/status', methods=['GET'])
def get_status():
    """获取回调状态"""
    return jsonify({
        "callback_count": len(callbacks),
        "callbacks": callbacks
    })


if __name__ == "__main__":
    print(f"回调服务器启动在 http://{CALLBACK_SERVER_HOST}:{CALLBACK_SERVER_PORT}")
    print(f"回调接口: {CALLBACK_ENDPOINT}")
    print(f"状态查询: /status")
    print("等待回调通知...")
    app.run(host='0.0.0.0', port=CALLBACK_SERVER_PORT, debug=False)
