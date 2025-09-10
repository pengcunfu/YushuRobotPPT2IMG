@echo off
chcp 65001
echo 安装PPT处理服务依赖
echo ===================

echo 正在安装Python依赖包...
pip install pywin32

echo.
echo 正在安装Windows服务相关依赖...
python -m pip install --upgrade pywin32
python "%PYTHON%\Scripts\pywin32_postinstall.py" -install

echo.
echo 依赖安装完成！
echo.
echo 注意事项：
echo 1. 请确保以管理员身份运行此脚本
echo 2. 安装完成后可以运行 service_manager.bat 来管理服务
echo 3. 服务将自动重启API程序，防止崩溃
echo 4. 定时任务将每天凌晨2点清理uploads和results目录

pause
