import os
import sys
import requests


def upload_ppt(file_path, callback_url, api_server="http://localhost:8020", width=1280, height=720):
    """上传PPT文件到API服务器"""
    if not os.path.exists(file_path):
        print(f"错误: 文件不存在 - {file_path}")
        return None

    url = f"{api_server}/api/upload"

    # 准备表单数据
    data = {
        'width': width,
        'height': height,
        'callback_url': callback_url
    }

    # 准备文件
    files = {
        'file': (os.path.basename(file_path), open(file_path, 'rb'),
                 'application/vnd.openxmlformats-officedocument.presentationml.presentation')
    }

    try:
        print(f"上传文件: {file_path}")
        print(f"请求URL: {url}")
        print(f"回调URL: {callback_url}")
        print(f"图片尺寸: {width}x{height}")

        # 发送请求
        response = requests.post(url, data=data, files=files)

        # 检查响应
        if response.status_code == 200:
            result = response.json()
            print(f"上传成功: {result}")
            return result
        else:
            print(f"上传失败: HTTP状态码 {response.status_code}")
            print(response.text)
            return None

    except Exception as e:
        print(f"上传过程中发生错误: {str(e)}")
        return None
    finally:
        # 关闭文件
        files['file'][1].close()


def main():
    """主函数"""
    if len(sys.argv) < 3:
        print("用法: python upload.py <PPT文件路径> <回调URL> [宽度] [高度]")
        print("示例: python upload.py 1.pptx http://localhost:8021/callback 1920 1080")
        return

    # 获取命令行参数
    ppt_path = sys.argv[1]
    callback_url = sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
    height = int(sys.argv[4]) if len(sys.argv) > 4 else 720

    # 上传文件
    result = upload_ppt(ppt_path, callback_url, width=width, height=height)

    if result:
        print(f"\n任务已提交，任务ID: {result.get('task_id')}")
        print("请等待回调通知...")
    else:
        print("上传失败")


if __name__ == "__main__":
    main()
