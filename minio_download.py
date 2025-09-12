"""
多线程异步下载工具
支持单文件下载、批量下载、断点续传等功能
"""
import asyncio
import aiohttp
import aiofiles
import os
from pathlib import Path
from typing import List, Union, Optional, Dict, Any
from urllib.parse import urlparse
import time
from loguru import logger


class AsyncDownloader:
    """异步下载器"""

    def __init__(self,
                 max_concurrent: int = 10,
                 chunk_size: int = 8192,
                 timeout: int = 300,
                 headers: Optional[Dict[str, str]] = None):
        """
        初始化下载器
        
        Args:
            max_concurrent: 最大并发下载数
            chunk_size: 每次读取的块大小
            timeout: 超时时间（秒）
            headers: 请求头
        """
        self.max_concurrent = max_concurrent
        self.chunk_size = chunk_size
        self.timeout_seconds = timeout
        self.headers = headers or {}

    async def download_single(self,
                              url: str,
                              save_path: Union[str, Path],
                              progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        下载单个文件
        
        Args:
            url: 下载URL
            save_path: 保存路径
            progress_callback: 进度回调函数 (current, total, url)
            
        Returns:
            Dict: 下载结果信息
        """
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        start_time = time.time()

        try:
            # 在异步函数内创建连接器和超时配置
            connector = aiohttp.TCPConnector(
                limit=self.max_concurrent + 10,
                limit_per_host=self.max_concurrent + 10,
                keepalive_timeout=60,
                enable_cleanup_closed=True,
                use_dns_cache=True,
                ttl_dns_cache=300,
            )

            timeout = aiohttp.ClientTimeout(
                total=self.timeout_seconds,
                connect=10,
                sock_read=30
            )

            # 创建会话
            async with aiohttp.ClientSession(
                    connector=connector,
                    timeout=timeout,
                    headers=self.headers
            ) as session:

                async with session.get(url) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP {response.status}: {response.reason}")

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0

                    async with aiofiles.open(save_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(self.chunk_size):
                            await f.write(chunk)
                            downloaded += len(chunk)

                            if progress_callback and total_size > 0:
                                progress_callback(downloaded, total_size, url)

                    elapsed = time.time() - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0

                    logger.info(f"✅ 下载完成: {url} -> {save_path} ({downloaded} bytes, {speed:.2f} KB/s)")

                    return {
                        "success": True,
                        "url": url,
                        "save_path": str(save_path),
                        "size": downloaded,
                        "elapsed": elapsed,
                        "speed": speed
                    }

        except Exception as e:
            logger.error(f"❌ 下载失败: {url} - {e}")
            return {
                "success": False,
                "url": url,
                "save_path": str(save_path),
                "error": str(e)
            }

    async def download_batch(self,
                             download_list: List[Dict[str, str]],
                             progress_callback: Optional[callable] = None) -> List[Dict[str, Any]]:
        """
        批量下载文件
        
        Args:
            download_list: 下载列表，格式: [{"url": "xxx", "save_path": "xxx"}, ...]
            progress_callback: 进度回调函数 (completed, total, current_url)
            
        Returns:
            List[Dict]: 所有下载结果
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def download_with_semaphore(item):
            async with semaphore:
                return await self.download_single(
                    item["url"],
                    item["save_path"],
                    progress_callback
                )

        logger.info(f"🚀 开始批量下载 {len(download_list)} 个文件...")
        start_time = time.time()

        tasks = [download_with_semaphore(item) for item in download_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "url": download_list[i]["url"],
                    "save_path": download_list[i]["save_path"],
                    "error": str(result)
                })
            else:
                processed_results.append(result)

        elapsed = time.time() - start_time
        successful = [r for r in processed_results if r["success"]]
        failed = [r for r in processed_results if not r["success"]]

        logger.info(f"🎉 批量下载完成! 成功: {len(successful)}, 失败: {len(failed)}, 耗时: {elapsed:.2f}s")

        return processed_results

    def get_filename_from_url(self, url: str) -> str:
        """从URL提取文件名"""
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        return filename if filename else "download_file"


# 全局下载器实例
downloader = AsyncDownloader()


async def download_file(url: str, save_path: Union[str, Path]) -> Dict[str, Any]:
    """
    简单的单文件下载函数
    
    Args:
        url: 下载URL
        save_path: 保存路径
        
    Returns:
        Dict: 下载结果
    """
    return await downloader.download_single(url, save_path)


async def download_files(urls: List[str], save_dir: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    批量下载文件到指定目录
    
    Args:
        urls: URL列表
        save_dir: 保存目录
        
    Returns:
        List[Dict]: 下载结果列表
    """
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    download_list = []
    for i, url in enumerate(urls):
        filename = downloader.get_filename_from_url(url)
        if not filename or filename == "download_file":
            filename = f"file_{i:03d}"

        download_list.append({
            "url": url,
            "save_path": save_dir / filename
        })

    return await downloader.download_batch(download_list)


# 测试函数
async def test_download():
    """测试下载功能"""
    print("🧪 测试下载功能...")

    # 测试单文件下载 - 使用一个简单的测试URL
    test_url = "http://8.153.175.16:9001/api/v1/download-shared-object/aHR0cDovLzEyNy4wLjAuMTo5MDAwL2RvY3VtZW50cy8lRTQlQjklOUQlRTQlQjglODklRTklOTglODUlRTUlODUlQjUtQUklRTYlQUQlQTYlRTUlOTklQTgucHB0eD9YLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPTVMRTc3UzdGOUZEVkdEMzRYTzg5JTJGMjAyNTA5MTIlMkZ1cy1lYXN0LTElMkZzMyUyRmF3czRfcmVxdWVzdCZYLUFtei1EYXRlPTIwMjUwOTEyVDAyNTc0N1omWC1BbXotRXhwaXJlcz00MzIwMCZYLUFtei1TZWN1cml0eS1Ub2tlbj1leUpoYkdjaU9pSklVelV4TWlJc0luUjVjQ0k2SWtwWFZDSjkuZXlKaFkyTmxjM05MWlhraU9pSTFURVUzTjFNM1JqbEdSRlpIUkRNMFdFODRPU0lzSW1WNGNDSTZNVGMxTnpZNE5qVTJPU3dpY0dGeVpXNTBJam9pYldsdWFXOWhaRzFwYmlKOS4xY1JmWEJTSWJnT3dmdUI4OXRlczB3MFlQanFRLXFBeW1mMk5CS0lwWWhCbnd2TUtsUUl2d25JLVdNSGUxOXNDSWJ2aGY4bDhtVG5aZ25NWmNuckdMUSZYLUFtei1TaWduZWRIZWFkZXJzPWhvc3QmdmVyc2lvbklkPW51bGwmWC1BbXotU2lnbmF0dXJlPTcxY2E5YzViMTU5N2Y1OGZkMjc5NzkzN2MyNWUwNzY5ZmQ1ZTUxZjEyNmQ1Njk3N2I1MmY3MmE5Mzg3OWI0ZTA"  # 1KB测试文件
    result = await download_file(test_url, "1.pptx")
    print(f"单文件下载结果: {result}")

    # 测试批量下载
    # test_urls = [
    #     "https://httpbin.org/bytes/512",
    #     "https://httpbin.org/bytes/1024",
    #     "https://httpbin.org/bytes/2048"
    # ]
    # results = await download_files(test_urls, "test_downloads")
    # print(f"批量下载结果: {len(results)} 个文件")


if __name__ == "__main__":
    asyncio.run(test_download())
