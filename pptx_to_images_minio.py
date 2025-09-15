"""
PPT转图片并上传到MinIO服务
支持从远程URL下载PPT，转换为图片后直接上传到MinIO
"""
import os
import asyncio
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
from loguru import logger

from pptx_to_images import pptx_to_images
from minio_service import minio_service
from minio_download import download_file


@dataclass
class UploadResult:
    """单个图片上传结果"""
    slide_number: int
    filename: str
    object_name: str
    size: int = None
    download_url: str = None
    error: str = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UploadResult':
        """从字典创建实例"""
        return cls(**data)


@dataclass
class PPTMinioResult:
    """PPT转图片并上传到MinIO的结果模型"""
    ppt_url: str
    ppt_name: str
    bucket_name: str
    total_slides: int
    successful_uploads: int
    failed_uploads: int
    upload_results: List[UploadResult]
    download_urls: List[str]
    temp_dir: str = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result_dict = asdict(self)
        # 将UploadResult对象转换为字典
        result_dict['upload_results'] = [result.to_dict() for result in self.upload_results]
        return result_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PPTMinioResult':
        """从字典创建实例"""
        # 将字典列表转换为UploadResult对象列表
        upload_results = [UploadResult.from_dict(result_dict) for result_dict in data['upload_results']]
        data['upload_results'] = upload_results
        return cls(**data)


async def pptx_url_to_minio_images(
        ppt_url: str,
        ppt_name: str,
        bucket_name: str = "images",
        width: int = 1920,
        height: int = 1080,
        temp_dir: str = None,
        progress_callback=None
) -> PPTMinioResult:
    """
    从远程URL下载PPT，转换为图片并上传到MinIO
    
    Args:
        ppt_url: PPT文件的远程URL
        ppt_name: PPT文件名（用于创建目录结构）
        bucket_name: MinIO存储桶名称
        width: 导出图片宽度（像素）
        height: 导出图片高度（像素）
        temp_dir: 临时目录，如果为None则使用系统临时目录
        progress_callback: 进度回调函数，接收 (stage, message, progress) 参数
        
    Returns:
        PPTMinioResult: 包含上传结果的对象
        
    Raises:
        Exception: 当下载、转换或上传过程中出现错误时
    """
    temp_pptx_path = None
    temp_output_dir = None

    try:
        # 创建临时目录（使用Windows系统临时目录下的子目录）
        if temp_dir is None:
            # 在系统临时目录下创建一个子目录
            base_temp_dir = tempfile.gettempdir()
            temp_dir = tempfile.mkdtemp(prefix="ppt_minio_", dir=base_temp_dir)
            auto_cleanup = True
        else:
            os.makedirs(temp_dir, exist_ok=True)
            auto_cleanup = False

        logger.info(f"🚀 开始处理PPT: {ppt_url}")
        logger.info(f"📝 PPT名称: {ppt_name}")
        logger.info(f"📁 临时目录: {temp_dir}")

        # 1. 下载PPT文件
        logger.info("📥 正在下载PPT文件...")
        if progress_callback:
            progress_callback("download", "正在下载PPT文件...", 10)
        
        ppt_filename = "presentation.pptx"
        temp_pptx_path = os.path.join(temp_dir, ppt_filename)

        download_result = await download_file(ppt_url, temp_pptx_path)
        if not download_result["success"]:
            raise Exception(f"下载PPT失败: {download_result['error']}")

        logger.info(f"✅ PPT下载成功: {download_result['size']} 字节")
        if progress_callback:
            progress_callback("download", f"PPT下载完成 ({download_result['size']} 字节)", 30)

        # 2. 转换为图片
        logger.info("🖼️ 正在将PPT转换为图片...")
        if progress_callback:
            progress_callback("convert", "正在将PPT转换为图片...", 40)
        
        temp_output_dir = os.path.join(temp_dir, "images")

        conversion_result = pptx_to_images(
            pptx_path=temp_pptx_path,
            output_dir=temp_output_dir,
            width=width,
            height=height
        )

        image_info_list = conversion_result.image_info_list
        logger.info(f"✅ 转换完成，生成 {len(image_info_list)} 张图片")
        if progress_callback:
            progress_callback("convert", f"PPT转换完成，生成 {len(image_info_list)} 张图片", 60)

        # 3. 上传图片到MinIO
        logger.info("📤 正在上传图片到MinIO...")
        if progress_callback:
            progress_callback("upload", "正在上传图片到MinIO...", 70)
        
        upload_results = []
        download_urls = []

        for i, image_info in enumerate(image_info_list):
            # 使用PPT名称和UUID文件名作为对象名称
            object_name = f"/{ppt_name}/{image_info.filename}"

            # 读取图片文件
            with open(image_info.filepath, "rb") as f:
                image_data = f.read()

            # 上传到MinIO
            result = await minio_service.upload_image(
                file=image_data,
                object_name=object_name,
                bucket_name=bucket_name
            )

            if result.success:
                upload_result = UploadResult(
                    slide_number=image_info.slide_number,
                    filename=image_info.filename,
                    object_name=object_name,
                    size=result.size,
                    download_url=result.download_url
                )
                upload_results.append(upload_result)
                download_urls.append(result.download_url)

                logger.info(f"✅ 幻灯片 {image_info.slide_number} 上传成功: {object_name}")
            else:
                logger.error(f"❌ 幻灯片 {image_info.slide_number} 上传失败: {result.error}")
                upload_result = UploadResult(
                    slide_number=image_info.slide_number,
                    filename=image_info.filename,
                    object_name=object_name,
                    error=result.error
                )
                upload_results.append(upload_result)
            
            # 更新上传进度
            if progress_callback:
                upload_progress = 70 + int((i + 1) / len(image_info_list) * 25)  # 70-95%
                progress_callback("upload", f"正在上传图片 ({i + 1}/{len(image_info_list)})", upload_progress)

        # 4. 统计结果
        successful_uploads = [r for r in upload_results if r.download_url is not None]
        failed_uploads = [r for r in upload_results if r.error is not None]

        logger.info(f"🎉 处理完成! 成功: {len(successful_uploads)}, 失败: {len(failed_uploads)}")
        if progress_callback:
            progress_callback("complete", f"处理完成! 成功: {len(successful_uploads)}, 失败: {len(failed_uploads)}", 100)

        return PPTMinioResult(
            ppt_url=ppt_url,
            ppt_name=ppt_name,
            bucket_name=bucket_name,
            total_slides=len(image_info_list),
            successful_uploads=len(successful_uploads),
            failed_uploads=len(failed_uploads),
            upload_results=upload_results,
            download_urls=download_urls,
            temp_dir=temp_dir
        )

    except Exception as e:
        logger.error(f"❌ 处理失败: {e}")
        # 直接抛出异常
        raise

    finally:
        # 清理临时文件（直接删除我们创建的临时目录）
        try:
            if auto_cleanup and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
                logger.info("🗑️ 临时目录已完全删除")
            elif temp_dir and not auto_cleanup:
                # 如果使用自定义目录，只删除我们创建的文件
                if temp_pptx_path and os.path.exists(temp_pptx_path):
                    os.remove(temp_pptx_path)
                    logger.info("🗑️ 临时PPT文件已删除")

                if temp_output_dir and os.path.exists(temp_output_dir):
                    import shutil
                    shutil.rmtree(temp_output_dir)
                    logger.info("🗑️ 临时图片目录已删除")

        except Exception as e:
            logger.warning(f"⚠️ 清理临时文件时出错: {e}")


# 测试函数
async def test_pptx_to_minio():
    """测试PPT转图片并上传到MinIO功能"""
    logger.info("🧪 测试PPT转图片并上传到MinIO...")

    # 测试URL（使用你提供的URL）
    test_url = "http://8.153.175.16:9001/api/v1/download-shared-object/aHR0cDovLzEyNy4wLjAuMTo5MDAwL2RvY3VtZW50cy8lRTQlQjklOUQlRTQlQjglODklRTklOTglODUlRTUlODUlQjUtQUklRTYlQUQlQTYlRTUlOTklQTgucHB0eD9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPTVMRTc3UzdGOUZEVkdEMzRYTzg5JTJGMjAyNTA5MTIlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjUwOTEyVDAyNTc0N1omWC1BbXotRXhwaXJlcz00MzIwMCZYLUFtei1TZWN1cml0eS1Ub2tlbj1leUpoYkdjaU9pSklVelV4TWlJc0luUjVjQ0k2SWtwWFZDSjkuZXlKaFkyTmxjM05MWlhraU9pSTFURVUzTjFNM1JqbEdSRlpIUkRNMFdFODRPU0lzSW1WNGNDSTZNVGMxTnpZNE5qVTJPU3dpY0dGeVpXNTBJam9pYldsdWFXOWhaRzFwYmlKOS4xY1JmWEJTSWJnT3dmdUI4OXRlczB3MFlQanFRLXFBeW1mMk5CS0lwWWhCbnd2TUtsUUl2d25JLVdNSGUxOXNDSWJ2aGY4bDhtVG5aZ25NWmNuckdMUSZYLUFtei1TaWduZWRIZWFkZXJzPWhvc3QmdmVyc2lvbklkPW51bGwmWC1BbXotU2lnbmF0dXJlPTcxY2E5YzViMTU5N2Y1OGZkMjc5NzkzN2MyNWUwNzY5ZmQ1ZTUxZjEyNmQ1Njk3N2I1MmY3MmE5Mzg3OWI0ZTA"

    try:
        result = await pptx_url_to_minio_images(
            ppt_url=test_url,
            ppt_name="九三阅兵-AI武器",
            bucket_name="images",
            width=1920,
            height=1080
        )

        logger.success("✅ 处理成功!")
        logger.info(f"📊 总幻灯片数: {result.total_slides}")
        logger.info(f"📤 成功上传: {result.successful_uploads}")
        logger.info(f"❌ 失败上传: {result.failed_uploads}")
        logger.info(f"🔗 下载链接数量: {len(result.download_urls)}")

        # 显示前几个下载链接
        for i, url in enumerate(result.download_urls[:3]):
            logger.info(f"  {i + 1}. {url}")
            
    except Exception as e:
        logger.error(f"❌ 处理失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_pptx_to_minio())
