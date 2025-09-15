#!/usr/bin/env python3
"""
Flask PPT转图片服务测试客户端
演示如何使用HTTP API上传PPT并获取图片
"""

import requests
import json
import time
from pathlib import Path


class PPTClient:
    """PPT转图片服务客户端"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
    
    def upload_ppt(self, ppt_file_path: str) -> dict:
        """上传PPT文件"""
        if not Path(ppt_file_path).exists():
            raise FileNotFoundError(f"文件不存在: {ppt_file_path}")
        
        with open(ppt_file_path, 'rb') as f:
            files = {'file': (Path(ppt_file_path).name, f, 'application/vnd.openxmlformats-officedocument.presentationml.presentation')}
            response = requests.post(f"{self.base_url}/upload", files=files)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"上传失败: {response.json()}")
    
    def convert_ppt(self, session_id: str, width: int = 1920, height: int = 1080) -> dict:
        """转换PPT为图片"""
        data = {'width': width, 'height': height}
        response = requests.post(
            f"{self.base_url}/convert/{session_id}",
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"转换失败: {response.json()}")
    
    def get_status(self, session_id: str) -> dict:
        """获取转换状态"""
        response = requests.get(f"{self.base_url}/status/{session_id}")
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"获取状态失败: {response.json()}")
    
    def download_image(self, session_id: str, filename: str, save_path: str = None) -> str:
        """下载图片"""
        if save_path is None:
            save_path = filename
        
        response = requests.get(f"{self.base_url}/download/{session_id}/{filename}")
        
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return save_path
        else:
            raise Exception(f"下载失败: {response.json()}")
    
    def stream_download_image(self, session_id: str, filename: str, save_path: str = None) -> str:
        """流式下载图片"""
        if save_path is None:
            save_path = filename
        
        response = requests.get(f"{self.base_url}/stream/{session_id}/{filename}", stream=True)
        
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return save_path
        else:
            raise Exception(f"流式下载失败: {response.json()}")
    
    def get_image_info(self, session_id: str, filename: str) -> dict:
        """获取图片信息"""
        response = requests.get(f"{self.base_url}/info/{session_id}/{filename}")
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"获取图片信息失败: {response.json()}")


def main():
    """主函数 - 演示完整流程"""
    print("=== PPT转图片服务测试客户端 ===\n")
    
    # 创建客户端
    client = PPTClient()
    
    try:
        # 1. 检查服务状态
        print("1. 检查服务状态...")
        response = requests.get(f"{client.base_url}/")
        if response.status_code == 200:
            print("✅ 服务运行正常")
            print(f"服务信息: {json.dumps(response.json(), indent=2, ensure_ascii=False)}\n")
        else:
            print("❌ 服务不可用")
            return
        
        # 2. 上传PPT文件
        print("2. 上传PPT文件...")
        ppt_file = "examples/1.pptx"  # 使用示例文件
        
        if not Path(ppt_file).exists():
            print(f"❌ 示例文件不存在: {ppt_file}")
            print("请确保examples/1.pptx文件存在")
            return
        
        upload_result = client.upload_ppt(ppt_file)
        session_id = upload_result['session_id']
        print(f"✅ 上传成功")
        print(f"会话ID: {session_id}")
        print(f"文件名: {upload_result['filename']}\n")
        
        # 3. 转换PPT
        print("3. 转换PPT为图片...")
        convert_result = client.convert_ppt(session_id, width=1920, height=1080)
        print(f"✅ 转换完成")
        print(f"总幻灯片数: {convert_result['total_slides']}")
        print(f"成功转换: {convert_result['converted_slides']}")
        print(f"图片列表:")
        for img in convert_result['images']:
            print(f"  - 幻灯片 {img['slide_number']}: {img['filename']}")
        print()
        
        # 4. 下载第一张图片
        if convert_result['images']:
            print("4. 下载第一张图片...")
            first_image = convert_result['images'][0]
            filename = first_image['filename']
            
            # 普通下载
            download_path = f"downloaded_{filename}"
            client.download_image(session_id, filename, download_path)
            print(f"✅ 普通下载完成: {download_path}")
            
            # 流式下载
            stream_path = f"streamed_{filename}"
            client.stream_download_image(session_id, filename, stream_path)
            print(f"✅ 流式下载完成: {stream_path}")
            
            # 获取图片信息
            info = client.get_image_info(session_id, filename)
            print(f"图片信息: {json.dumps(info, indent=2, ensure_ascii=False)}")
            print()
        
        # 5. 获取会话状态
        print("5. 获取会话状态...")
        status = client.get_status(session_id)
        print(f"✅ 状态获取成功")
        print(f"状态信息: {json.dumps(status, indent=2, ensure_ascii=False)}\n")
        
        print("🎉 测试完成！所有功能正常工作。")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    main()
