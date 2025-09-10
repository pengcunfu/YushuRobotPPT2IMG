import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import time
import subprocess
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ppt_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PPTProcessingService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PPTProcessingService"
    _svc_display_name_ = "PPT Processing API Service"
    _svc_description_ = "PPT文件处理API服务，自动重启防止崩溃"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_alive = True
        self.process = None

    def SvcStop(self):
        logger.info("停止PPT处理服务...")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.is_alive = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
                logger.info("API进程已正常停止")
            except Exception as e:
                logger.error(f"停止API进程时出错: {e}")
                try:
                    self.process.kill()
                except:
                    pass
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        logger.info("启动PPT处理服务...")
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                            servicemanager.PYS_SERVICE_STARTED,
                            (self._svc_name_, ''))
        self.main()

    def main(self):
        # 获取当前脚本目录
        current_dir = Path(__file__).parent.absolute()
        api_script = current_dir / "api.py"
        
        logger.info(f"服务工作目录: {current_dir}")
        logger.info(f"API脚本路径: {api_script}")
        
        while self.is_alive:
            try:
                logger.info("启动API进程...")
                
                # 启动API进程
                self.process = subprocess.Popen([
                    sys.executable, str(api_script)
                ], 
                cwd=str(current_dir),
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
                )
                
                logger.info(f"API进程已启动，PID: {self.process.pid}")
                
                # 监控进程状态
                while self.is_alive:
                    if self.process.poll() is not None:
                        # 进程已退出
                        stdout, stderr = self.process.communicate()
                        logger.error(f"API进程异常退出，退出码: {self.process.returncode}")
                        if stdout:
                            logger.info(f"标准输出: {stdout}")
                        if stderr:
                            logger.error(f"错误输出: {stderr}")
                        break
                    
                    # 检查服务停止信号
                    if win32event.WaitForSingleObject(self.hWaitStop, 5000) == win32event.WAIT_OBJECT_0:
                        logger.info("收到停止信号")
                        break
                    
                if not self.is_alive:
                    break
                
                # 如果进程异常退出且服务仍在运行，等待5秒后重启
                logger.info("等待5秒后重启API进程...")
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"服务运行出错: {e}")
                if self.is_alive:
                    logger.info("等待10秒后重试...")
                    time.sleep(10)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PPTProcessingService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PPTProcessingService)
