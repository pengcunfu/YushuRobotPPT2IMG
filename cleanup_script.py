import os
import shutil
import logging
from datetime import datetime
from pathlib import Path

# 配置日志
log_file = f"cleanup_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def cleanup_directory(directory_path):
    """清空指定目录"""
    try:
        if not os.path.exists(directory_path):
            logger.warning(f"目录不存在: {directory_path}")
            return False
        
        logger.info(f"开始清理目录: {directory_path}")
        
        # 统计清理前的文件和目录数量
        files_count = 0
        dirs_count = 0
        total_size = 0
        
        for root, dirs, files in os.walk(directory_path):
            files_count += len(files)
            dirs_count += len(dirs)
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    total_size += os.path.getsize(file_path)
                except:
                    pass
        
        logger.info(f"清理前统计 - 文件: {files_count}个, 目录: {dirs_count}个, 总大小: {total_size / (1024*1024):.2f}MB")
        
        # 清理目录内容
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                    logger.debug(f"删除文件: {item_path}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    logger.debug(f"删除目录: {item_path}")
            except Exception as e:
                logger.error(f"删除失败 {item_path}: {e}")
                return False
        
        logger.info(f"目录清理完成: {directory_path}")
        return True
        
    except Exception as e:
        logger.error(f"清理目录时出错 {directory_path}: {e}")
        return False

def main():
    """主清理函数"""
    logger.info("=" * 60)
    logger.info("开始执行定时清理任务")
    logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取当前脚本目录
    current_dir = Path(__file__).parent.absolute()
    
    # 定义要清理的目录
    directories_to_clean = [
        current_dir / "uploads",
        current_dir / "results"
    ]
    
    success_count = 0
    total_count = len(directories_to_clean)
    
    for directory in directories_to_clean:
        logger.info(f"处理目录: {directory}")
        if cleanup_directory(str(directory)):
            success_count += 1
        else:
            logger.error(f"清理失败: {directory}")
    
    logger.info(f"清理任务完成: {success_count}/{total_count} 个目录清理成功")
    
    if success_count == total_count:
        logger.info("所有目录清理成功！")
    else:
        logger.warning(f"有 {total_count - success_count} 个目录清理失败")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
