import requests
import socketio
import time
import os
import asyncio
import aiohttp
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock


class PPTProcessingClient:
    def __init__(self, server_url='http://8.149.241.205:8020', max_concurrent_downloads=5):
        self.server_url = server_url
        self.sio = socketio.Client()
        self.max_concurrent_downloads = max_concurrent_downloads
        self.download_progress = {}
        self.download_lock = Lock()
        self.setup_socket_handlers()

    def setup_socket_handlers(self):
        """设置WebSocket事件处理器"""

        @self.sio.event
        def connected(data):
            print(f"✅ WebSocket连接成功: {data['message']}")

        @self.sio.event
        def task_started(data):
            print(f"🚀 任务已启动: {data['message']}")

        @self.sio.event
        def progress_update(data):
            if data['current_image'] == -1:
                print(f"📊 {data['message']}")
            else:
                print(
                    f"📊 处理进度: {data['progress']}% ({data['processed_images']}/{data['total_images']}) - {data['message']}")

                # 注意：在WebSocket事件处理器中不进行下载，避免阻塞
                # 用户可以在任务完成后选择下载模式

        @self.sio.event
        def task_complete(data):
            print(f"✅ 任务完成: {data['message']}")
            print(f"📈 最终统计: {data['processed_images']}/{data['total_images']} 张图片处理完成")

        @self.sio.event
        def task_error(data):
            print(f"❌ 任务失败: {data['message']}")
            print(f"🔍 错误详情: {data.get('error', '未知错误')}")

        @self.sio.event
        def error(data):
            print(f"❌ 错误: {data['message']}")

    def upload_ppt(self, file_path, width=1920, height=1080):
        """上传PPT文件并返回UUID"""
        if not os.path.exists(file_path):
            print(f"❌ 文件不存在: {file_path}")
            return None

        # 检查文件扩展名
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in ['.ppt', '.pptx']:
            print(f"❌ 不支持的文件格式: {file_ext}，仅支持 .ppt 和 .pptx 文件")
            return None

        print(f"📤 正在上传PPT文件: {file_path}")
        print(f"🖼️  设置图片尺寸: {width}x{height}")

        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'width': width,
                'height': height
            }
            response = requests.post(f"{self.server_url}/upload", files=files, data=data)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ PPT文件上传成功!")
            print(f"   UUID: {data['uuid']}")
            print(f"   文件名: {data['filename']}")
            return data['uuid']
        else:
            print(f"❌ 上传失败: {response.json()}")
            return None

    def connect_websocket(self):
        """连接WebSocket"""
        try:
            print("🔌 正在连接WebSocket...")
            self.sio.connect(self.server_url)
            return True
        except Exception as e:
            print(f"❌ WebSocket连接失败: {e}")
            return False

    def start_task(self, file_uuid):
        """启动PPT处理任务"""
        print(f"🚀 启动PPT转换任务: {file_uuid}")
        self.sio.emit('start_task', {'uuid': file_uuid})

    def download_image(self, file_uuid, image_index):
        """下载处理后的图片（同步版本）"""
        try:
            url = f"{self.server_url}/download/{file_uuid}/{image_index}"
            response = requests.get(url)

            if response.status_code == 200:
                # 创建下载目录
                download_dir = f"downloads/{file_uuid}"
                os.makedirs(download_dir, exist_ok=True)

                # 保存图片
                filename = f"image_{image_index:03d}.png"
                filepath = os.path.join(download_dir, filename)

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                print(f"💾 图片已下载: {filepath}")
                return filepath
            else:
                print(f"❌ 下载失败 (图片 {image_index}): HTTP {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ 下载异常 (图片 {image_index}): {e}")
            return None

    async def download_image_async(self, session, file_uuid, image_index, download_dir):
        """异步下载单张图片"""
        try:
            url = f"{self.server_url}/download/{file_uuid}/{image_index}"
            
            async with session.get(url) as response:
                if response.status == 200:
                    # 保存图片
                    filename = f"image_{image_index:03d}.png"
                    filepath = os.path.join(download_dir, filename)
                    
                    content = await response.read()
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    # 更新进度
                    with self.download_lock:
                        if file_uuid not in self.download_progress:
                            self.download_progress[file_uuid] = {'completed': 0, 'total': 0}
                        self.download_progress[file_uuid]['completed'] += 1
                        completed = self.download_progress[file_uuid]['completed']
                        total = self.download_progress[file_uuid]['total']
                        progress = (completed / total) * 100 if total > 0 else 0
                    
                    print(f"💾 图片已下载 ({completed}/{total}): {filename} [{progress:.1f}%]")
                    return filepath
                else:
                    print(f"❌ 下载失败 (图片 {image_index}): HTTP {response.status}")
                    return None
        except Exception as e:
            print(f"❌ 下载异常 (图片 {image_index}): {e}")
            return None

    async def download_images_concurrent_async(self, file_uuid, image_indices):
        """真正的异步并发下载 - 同时发起所有请求，不等待"""
        download_dir = f"downloads/{file_uuid}"
        os.makedirs(download_dir, exist_ok=True)
        
        # 初始化下载进度
        with self.download_lock:
            self.download_progress[file_uuid] = {
                'completed': 0,
                'total': len(image_indices)
            }
        
        print(f"📥 开始真正并发下载 {len(image_indices)} 张图片到: {download_dir}")
        print(f"🚀 同时发起所有请求，无并发限制！")
        
        # 优化HTTP连接配置 - 支持大量并发连接
        connector = aiohttp.TCPConnector(
            limit=len(image_indices) + 50,  # 连接池大小 = 图片数量 + 缓冲
            limit_per_host=len(image_indices) + 50,  # 每个主机的连接数
            keepalive_timeout=60,  # 保持连接60秒
            enable_cleanup_closed=True,  # 自动清理关闭的连接
            use_dns_cache=True,  # 启用DNS缓存
            ttl_dns_cache=300,  # DNS缓存5分钟
        )
        
        # 优化超时设置
        timeout = aiohttp.ClientTimeout(
            total=600,  # 总超时10分钟
            connect=15,  # 连接超时15秒
            sock_read=60,  # 读取超时60秒
        )
        
        # 创建HTTP会话
        async with aiohttp.ClientSession(
            connector=connector, 
            timeout=timeout,
            headers={'Connection': 'keep-alive'}  # 保持连接
        ) as session:
            # 同时创建所有下载任务 - 真正的并发！
            print(f"🚀 同时发起 {len(image_indices)} 个下载请求...")
            tasks = [
                self.download_image_async(session, file_uuid, idx, download_dir) 
                for idx in image_indices
            ]
            
            # 使用 asyncio.gather 同时执行所有任务
            print(f"⏳ 等待所有下载完成...")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            successful = [r for r in results if r is not None and not isinstance(r, Exception)]
            failed = [r for r in results if r is None or isinstance(r, Exception)]
            
            print(f"🎉 真正并发下载完成！成功: {len(successful)}, 失败: {len(failed)}")
            
            # 清理进度信息
            with self.download_lock:
                if file_uuid in self.download_progress:
                    del self.download_progress[file_uuid]
            
            return successful

    def download_images_concurrent(self, file_uuid, image_indices=None):
        """并发下载图片（同步接口）"""
        if image_indices is None:
            # 获取任务状态确定要下载的图片
            status = self.get_task_status(file_uuid)
            if not status:
                print("❌ 无法获取任务状态")
                return []
            
            if status['status'] != 'completed':
                print(f"❌ 任务尚未完成，当前状态: {status['status']}")
                return []
            
            image_indices = list(range(status['total_images']))
        
        # 运行异步下载
        try:
            # 检查是否已有事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果事件循环正在运行，使用线程池
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(self._run_async_download, file_uuid, image_indices)
                        return future.result()
                else:
                    # 事件循环存在但未运行
                    return loop.run_until_complete(
                        self.download_images_concurrent_async(file_uuid, image_indices)
                    )
            except RuntimeError:
                # 没有事件循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    results = loop.run_until_complete(
                        self.download_images_concurrent_async(file_uuid, image_indices)
                    )
                    return results
                finally:
                    loop.close()
        except Exception as e:
            print(f"❌ 并发下载异常: {e}")
            return []
    
    def _run_async_download(self, file_uuid, image_indices):
        """在独立线程中运行异步下载"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.download_images_concurrent_async(file_uuid, image_indices)
            )
        finally:
            loop.close()

    def download_images_threaded(self, file_uuid, image_indices=None, max_workers=None):
        """真正的多线程并发下载 - 同时发起所有请求"""
        if image_indices is None:
            # 获取任务状态确定要下载的图片
            status = self.get_task_status(file_uuid)
            if not status:
                print("❌ 无法获取任务状态")
                return []
            
            if status['status'] != 'completed':
                print(f"❌ 任务尚未完成，当前状态: {status['status']}")
                return []
            
            image_indices = list(range(status['total_images']))
        
        # 如果没有指定线程数，使用图片数量作为线程数（真正的并发）
        if max_workers is None:
            max_workers = min(len(image_indices), 50)  # 最多50个线程
        
        download_dir = f"downloads/{file_uuid}"
        os.makedirs(download_dir, exist_ok=True)
        
        print(f"📥 开始真正多线程下载 {len(image_indices)} 张图片到: {download_dir}")
        print(f"🚀 线程数: {max_workers} (同时发起所有请求)")
        
        # 初始化下载进度
        with self.download_lock:
            self.download_progress[file_uuid] = {
                'completed': 0,
                'total': len(image_indices)
            }
        
        def download_single_image(image_index):
            """下载单张图片的线程函数"""
            try:
                url = f"{self.server_url}/download/{file_uuid}/{image_index}"
                
                # 每个线程使用独立的会话，避免连接竞争
                with requests.Session() as session:
                    # 配置连接池
                    adapter = requests.adapters.HTTPAdapter(
                        pool_connections=1,
                        pool_maxsize=1,
                        max_retries=2,
                        pool_block=False
                    )
                    session.mount('http://', adapter)
                    session.mount('https://', adapter)
                    
                    # 设置超时和头部
                    session.headers.update({
                        'Connection': 'keep-alive',
                        'User-Agent': 'PPT-Client/1.0'
                    })
                    
                    response = session.get(
                        url, 
                        timeout=(10, 60),  # (连接超时, 读取超时)
                        stream=True        # 流式下载
                    )
                    
                    if response.status_code == 200:
                        filename = f"image_{image_index:03d}.png"
                        filepath = os.path.join(download_dir, filename)
                        
                        # 流式写入文件
                        with open(filepath, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        # 更新进度
                        with self.download_lock:
                            if file_uuid in self.download_progress:
                                self.download_progress[file_uuid]['completed'] += 1
                                completed = self.download_progress[file_uuid]['completed']
                                total = self.download_progress[file_uuid]['total']
                                progress = (completed / total) * 100 if total > 0 else 0
                                print(f"💾 图片已下载 ({completed}/{total}): {filename} [{progress:.1f}%]")
                        
                        return filepath
                    else:
                        print(f"❌ 下载失败 (图片 {image_index}): HTTP {response.status_code}")
                        return None
            except Exception as e:
                print(f"❌ 下载异常 (图片 {image_index}): {e}")
                return None
        
        # 使用线程池同时执行所有下载任务
        successful_downloads = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            print(f"🚀 同时提交 {len(image_indices)} 个下载任务...")
            
            # 同时提交所有任务
            future_to_index = {
                executor.submit(download_single_image, i): i 
                for i in image_indices
            }
            
            print(f"⏳ 等待所有下载完成...")
            # 收集结果
            for future in as_completed(future_to_index):
                result = future.result()
                if result:
                    successful_downloads.append(result)
        
        # 清理进度信息
        with self.download_lock:
            if file_uuid in self.download_progress:
                del self.download_progress[file_uuid]
        
        print(f"🎉 真正多线程下载完成！成功: {len(successful_downloads)}, 失败: {len(image_indices) - len(successful_downloads)}")
        return successful_downloads

    def download_all_images(self, file_uuid, download_mode='async', max_workers=None):
        """下载所有处理完成的图片
        
        Args:
            file_uuid: 文件UUID
            download_mode: 下载模式 ('async', 'threaded', 'sync', 'ultra_async', 'ultra_threaded')
            max_workers: 最大工作线程/协程数
        """
        try:
            # 获取任务状态
            status = self.get_task_status(file_uuid)
            if not status:
                return

            if status['status'] != 'completed':
                print(f"❌ 任务尚未完成，当前状态: {status['status']}")
                return

            total_images = status['total_images']
            
            if download_mode == 'ultra_async':
                # 使用真正的异步并发下载（无限制）
                print(f"📥 使用超级异步并发下载模式下载 {total_images} 张图片")
                print(f"🚀 同时发起所有请求，无并发限制！")
                results = self.download_images_concurrent(file_uuid)
                if results:
                    print(f"🎉 超级异步并发下载完成！成功下载 {len(results)} 张图片")
                else:
                    print("❌ 超级异步并发下载失败")
                    
            elif download_mode == 'ultra_threaded':
                # 使用真正的多线程并发下载（无限制）
                print(f"📥 使用超级多线程并发下载模式下载 {total_images} 张图片")
                print(f"🚀 同时发起所有请求，无线程限制！")
                results = self.download_images_threaded(file_uuid, max_workers=None)
                if results:
                    print(f"🎉 超级多线程并发下载完成！成功下载 {len(results)} 张图片")
                else:
                    print("❌ 超级多线程并发下载失败")
                    
            elif download_mode == 'async':
                # 使用异步并发下载（有限制）
                if max_workers:
                    self.max_concurrent_downloads = max_workers
                print(f"📥 使用异步并发下载模式下载 {total_images} 张图片")
                results = self.download_images_concurrent(file_uuid)
                if results:
                    print(f"🎉 异步并发下载完成！成功下载 {len(results)} 张图片")
                else:
                    print("❌ 异步并发下载失败")
                    
            elif download_mode == 'threaded':
                # 使用线程池并发下载（有限制）
                if max_workers is None:
                    max_workers = 5
                print(f"📥 使用线程池并发下载模式下载 {total_images} 张图片")
                results = self.download_images_threaded(file_uuid, max_workers=max_workers)
                if results:
                    print(f"🎉 线程池并发下载完成！成功下载 {len(results)} 张图片")
                else:
                    print("❌ 线程池并发下载失败")
                    
            else:
                # 使用原有的同步下载方式
                download_dir = f"downloads/{file_uuid}"
                os.makedirs(download_dir, exist_ok=True)
                print(f"📥 使用同步下载模式下载 {total_images} 张图片到: {download_dir}")

                for i in range(total_images):
                    self.download_image(file_uuid, i)

                print(f"🎉 同步下载完成！共 {total_images} 张图片")

        except Exception as e:
            print(f"❌ 批量下载失败: {e}")

    def get_task_status(self, file_uuid):
        """获取任务状态"""
        try:
            response = requests.get(f"{self.server_url}/status/{file_uuid}")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ 获取状态失败: {response.json()}")
                return None
        except Exception as e:
            print(f"❌ 获取状态异常: {e}")
            return None

    def disconnect(self):
        """断开连接"""
        if self.sio.connected:
            self.sio.disconnect()
            print("🔌 WebSocket已断开")

    def benchmark_download_methods(self, file_uuid, test_indices=None, max_workers=5):
        """性能测试：比较不同下载方法的速度"""
        print("🧪 开始下载性能测试...")
        
        if test_indices is None:
            # 获取任务状态
            status = self.get_task_status(file_uuid)
            if not status or status['status'] != 'completed':
                print("❌ 任务未完成，无法进行性能测试")
                return
            
            # 测试前10张图片
            test_indices = list(range(min(10, status['total_images'])))
        
        print(f"📊 测试图片数量: {len(test_indices)}")
        print(f"📊 测试图片索引: {test_indices}")
        
        results = {}
        
        # 1. 测试同步下载
        print("\n🔄 测试同步下载...")
        start_time = time.time()
        sync_results = []
        for i in test_indices:
            result = self.download_image(file_uuid, i)
            if result:
                sync_results.append(result)
        sync_time = time.time() - start_time
        results['sync'] = {
            'time': sync_time,
            'successful': len(sync_results),
            'speed': len(sync_results) / sync_time if sync_time > 0 else 0
        }
        print(f"✅ 同步下载完成: {len(sync_results)}/{len(test_indices)} 张图片, 耗时 {sync_time:.2f}s")
        
        # 2. 测试线程池下载
        print("\n🔄 测试线程池下载...")
        start_time = time.time()
        threaded_results = self.download_images_threaded(file_uuid, test_indices, max_workers)
        threaded_time = time.time() - start_time
        results['threaded'] = {
            'time': threaded_time,
            'successful': len(threaded_results),
            'speed': len(threaded_results) / threaded_time if threaded_time > 0 else 0
        }
        print(f"✅ 线程池下载完成: {len(threaded_results)}/{len(test_indices)} 张图片, 耗时 {threaded_time:.2f}s")
        
        # 3. 测试异步下载
        print("\n🔄 测试异步下载...")
        start_time = time.time()
        async_results = self.download_images_concurrent(file_uuid, test_indices)
        async_time = time.time() - start_time
        results['async'] = {
            'time': async_time,
            'successful': len(async_results),
            'speed': len(async_results) / async_time if async_time > 0 else 0
        }
        print(f"✅ 异步下载完成: {len(async_results)}/{len(test_indices)} 张图片, 耗时 {async_time:.2f}s")
        
        # 输出性能比较结果
        print("\n" + "="*60)
        print("📊 下载性能测试结果")
        print("="*60)
        
        for method, data in results.items():
            print(f"{method.upper():>10}: {data['successful']}/{len(test_indices)} 张图片, "
                  f"{data['time']:.2f}s, {data['speed']:.2f} 张/秒")
        
        # 计算性能提升
        if results['sync']['time'] > 0:
            threaded_speedup = results['sync']['time'] / results['threaded']['time'] if results['threaded']['time'] > 0 else 0
            async_speedup = results['sync']['time'] / results['async']['time'] if results['async']['time'] > 0 else 0
            
            print(f"\n🚀 性能提升:")
            print(f"   线程池 vs 同步: {threaded_speedup:.1f}x")
            print(f"   异步 vs 同步: {async_speedup:.1f}x")
            print(f"   异步 vs 线程池: {threaded_speedup/async_speedup:.1f}x" if async_speedup > 0 else "   异步 vs 线程池: N/A")
        
        return results


def main():
    """主函数 - 演示完整的PPT转图片流程"""
    client = PPTProcessingClient()

    # 示例PPT路径 - 请替换为你的实际PPT文件路径
    ppt_path = "1.pptx"  # 使用项目中现有的示例文件

    # 检查文件是否存在
    if not os.path.exists(ppt_path):
        print(f"❌ 测试PPT文件不存在: {ppt_path}")
        print("请确保有可用的PPT文件，或修改 ppt_path 变量")
        return

    try:
        # 设置图片尺寸
        width = 640
        height = 480

        # 1. 上传PPT文件
        file_uuid = client.upload_ppt(ppt_path, width, height)
        if not file_uuid:
            return

        # 2. 连接WebSocket
        if not client.connect_websocket():
            return

        # 3. 启动PPT转换任务
        client.start_task(file_uuid)

        # 4. 等待任务完成
        print("⏳ 等待PPT转换完成...")
        while True:
            status = client.get_task_status(file_uuid)
            if status:
                if status['status'] == 'completed':
                    print("🎉 PPT转换完成！")
                    break
                elif status['status'] == 'failed':
                    print("❌ PPT转换失败")
                    break
            time.sleep(2)

        # 5. 询问是否下载所有图片
        print("\n请选择操作:")
        print("1. 下载所有图片")
        print("2. 性能测试 (比较不同下载方法)")
        print("3. 跳过下载")
        
        choice = input("请选择 (1/2/3，默认1): ").strip()
        
        if choice == '2':
            # 性能测试
            print("\n🧪 开始性能测试...")
            client.benchmark_download_methods(file_uuid)
            
        elif choice != '3':
            # 下载所有图片
            print("\n请选择下载模式:")
            print("1. 超级异步并发下载 (🚀 最快，同时发起所有请求)")
            print("2. 超级多线程并发下载 (🚀 很快，同时发起所有请求)")
            print("3. 异步并发下载 (有限制，稳定)")
            print("4. 线程池并发下载 (有限制，兼容性好)")
            print("5. 同步下载 (最慢，但最稳定)")
            
            mode_choice = input("请选择 (1/2/3/4/5，默认1): ").strip()
            
            if mode_choice == '1':
                # 超级异步下载
                print("🚀 使用超级异步并发下载模式（同时发起所有请求）")
                client.download_all_images(file_uuid, download_mode='ultra_async')
            elif mode_choice == '2':
                # 超级线程池下载
                print("🚀 使用超级多线程并发下载模式（同时发起所有请求）")
                client.download_all_images(file_uuid, download_mode='ultra_threaded')
            elif mode_choice == '3':
                # 异步下载 (有限制)
                max_workers = input("请输入并发数 (默认8): ").strip()
                max_workers = int(max_workers) if max_workers.isdigit() else 8
                client.download_all_images(file_uuid, download_mode='async', max_workers=max_workers)
            elif mode_choice == '4':
                # 线程池下载 (有限制)
                max_workers = input("请输入线程数 (默认8): ").strip()
                max_workers = int(max_workers) if max_workers.isdigit() else 8
                client.download_all_images(file_uuid, download_mode='threaded', max_workers=max_workers)
            elif mode_choice == '5':
                # 同步下载
                client.download_all_images(file_uuid, download_mode='sync')
            else:
                # 默认使用超级异步下载
                print("🚀 使用超级异步并发下载模式（同时发起所有请求）")
                client.download_all_images(file_uuid, download_mode='ultra_async')

        print("🎉 演示完成!")

    except KeyboardInterrupt:
        print("\n⚠️  用户中断")
    except Exception as e:
        print(f"❌ 发生异常: {e}")
    finally:
        # 清理连接
        client.disconnect()


if __name__ == "__main__":
    main()
