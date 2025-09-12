"""
MinIO对象存储服务实现
提供图片上传和预签名URL生成功能
"""
import asyncio
import os
import io
from datetime import timedelta
from typing import Optional, BinaryIO, Union, Tuple
from minio import Minio
from minio.error import S3Error
from fastapi import UploadFile, HTTPException
from loguru import logger

from config import get_config


class MinioService:
    """MinIO对象存储服务"""

    def __init__(self):
        """初始化MinIO客户端"""
        self.client = None
        self._init_client()

    def _init_client(self):
        """初始化MinIO客户端"""
        try:
            # 从配置文件获取MinIO配置
            endpoint = get_config("endpoint")
            access_key = get_config("access_key")
            secret_key = get_config("secret_key")
            secure = get_config("secure")
            region = get_config("region")

            # 创建客户端
            self.client = Minio(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
                region=region if region else None
            )
            logger.info(f"MinIO客户端初始化成功: {endpoint}")
        except Exception as e:
            logger.error(f"MinIO客户端初始化失败: {e}")
            raise

    async def upload_image(
            self,
            file: Union[UploadFile, BinaryIO, bytes],
            object_name: str,
            bucket_name: str = "images"
    ) -> dict:
        """
        上传图片到MinIO
        
        Args:
            file: 图片文件对象，可以是FastAPI的UploadFile、文件对象或字节数据
            object_name: 对象名称/路径
            bucket_name: 存储桶名称，默认为"images"
            
        Returns:
            dict: 上传结果信息
        """
        try:
            # 确保存储桶存在
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"创建存储桶成功: {bucket_name}")

            # 处理不同类型的文件输入
            file_data, file_size = self._prepare_file_data(file)

            # 根据文件名推断内容类型
            content_type = self._guess_image_content_type(object_name)

            # 上传文件
            etag = self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=content_type
            )

            logger.info(f"图片上传成功: {bucket_name}/{object_name}")

            # 生成预签名URL用于直接下载
            download_url = self._generate_presigned_url(object_name, bucket_name)

            return {
                "success": True,
                "bucket_name": bucket_name,
                "object_name": object_name,
                "etag": etag,
                "size": file_size,
                "content_type": content_type,
                "download_url": download_url
            }

        except S3Error as e:
            logger.error(f"上传图片失败: {e}")
            raise HTTPException(status_code=500, detail=f"上传图片失败: {e}")

    def _prepare_file_data(self, file: Union[UploadFile, BinaryIO, bytes]) -> Tuple[BinaryIO, int]:
        """
        准备文件数据
        
        Args:
            file: 文件对象，可以是FastAPI的UploadFile、文件对象或字节数据
            
        Returns:
            Tuple[BinaryIO, int]: 文件数据流和文件大小
        """
        if isinstance(file, UploadFile):
            # FastAPI的UploadFile
            content = file.file.read()
            file_data = io.BytesIO(content)
            file_size = len(content)
        elif isinstance(file, bytes):
            # 字节数据
            file_data = io.BytesIO(file)
            file_size = len(file)
        else:
            # 假设是文件对象
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            file_data = file

        return file_data, file_size

    def _generate_presigned_url(self, object_name: str, bucket_name: str, expires_in: int = 3600) -> str:
        """
        内部方法：生成预签名URL
        
        Args:
            object_name: 对象名称/路径
            bucket_name: 存储桶名称
            expires_in: URL过期时间（秒），默认1小时
            
        Returns:
            str: 预签名URL
        """
        try:
            # 检查对象是否存在
            if not self.client.bucket_exists(bucket_name):
                logger.error(f"存储桶不存在: {bucket_name}")
                raise HTTPException(status_code=404, detail=f"存储桶不存在: {bucket_name}")

            # 检查对象是否存在
            try:
                self.client.stat_object(bucket_name, object_name)
                logger.info(f"对象存在: {bucket_name}/{object_name}")
            except S3Error as e:
                logger.error(f"对象不存在: {bucket_name}/{object_name} - {e}")
                raise HTTPException(status_code=404, detail=f"对象不存在: {bucket_name}/{object_name}")

            # 将秒数转换为timedelta对象
            expires = timedelta(seconds=expires_in)
            url = self.client.presigned_get_object(
                bucket_name=bucket_name,
                object_name=object_name,
                expires=expires
            )
            logger.info(f"生成预签名URL成功: {bucket_name}/{object_name}")
            logger.info(f"预签名URL: {url}")
            return url
        except S3Error as e:
            logger.error(f"生成预签名URL失败: {e}")
            raise HTTPException(status_code=500, detail=f"生成预签名URL失败: {e}")
        except Exception as e:
            logger.error(f"生成预签名URL时发生未知错误: {e}")
            raise HTTPException(status_code=500, detail=f"生成预签名URL时发生未知错误: {e}")

    def _guess_image_content_type(self, filename: str) -> str:
        """
        根据文件名推断图片内容类型
        
        Args:
            filename: 文件名
            
        Returns:
            str: 图片内容类型
        """
        ext = filename.lower().split('.')[-1] if '.' in filename else ''

        image_content_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'bmp': 'image/bmp',
            'webp': 'image/webp',
            'svg': 'image/svg+xml',
            'tiff': 'image/tiff',
            'ico': 'image/x-icon'
        }

        return image_content_types.get(ext, 'image/jpeg')


# 全局MinIO服务实例
minio_service = MinioService()


async def test_server():
    """测试MinIO服务功能"""
    print("🧪 测试MinIO服务...")

    # 读取真实的PNG图片文件
    try:
        with open("out/slide_1.png", "rb") as f:
            real_image_data = f.read()
        print(f"📤 正在上传真实图片文件 (大小: {len(real_image_data)} 字节)...")

        result = await minio_service.upload_image(
            file=real_image_data,
            object_name="real_slide_1.png",
            bucket_name="images"
        )
        print(f"✅ 真实图片上传成功: {result}")

        # 测试预签名URL（从上传结果中获取）
        print("🔗 上传结果中的预签名URL:")
        print(f"✅ 预签名URL: {result['download_url']}")
    except FileNotFoundError:
        print("❌ 找不到文件 out/slide_1.png")
        print("💡 请确保文件存在，或者使用其他图片文件进行测试")
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")

    print("\n🎉 MinIO服务测试完成!")


if __name__ == '__main__':
    asyncio.run(test_server())
