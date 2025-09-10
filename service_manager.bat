@echo off
chcp 65001
echo PPT处理服务管理脚本
echo =====================

:menu
echo.
echo 请选择操作:
echo 1. 安装服务
echo 2. 启动服务
echo 3. 停止服务
echo 4. 重启服务
echo 5. 卸载服务
echo 6. 查看服务状态
echo 7. 设置定时任务
echo 8. 删除定时任务
echo 9. 退出
echo.
set /p choice=请输入选项 (1-9): 

if "%choice%"=="1" goto install
if "%choice%"=="2" goto start
if "%choice%"=="3" goto stop
if "%choice%"=="4" goto restart
if "%choice%"=="5" goto uninstall
if "%choice%"=="6" goto status
if "%choice%"=="7" goto create_task
if "%choice%"=="8" goto delete_task
if "%choice%"=="9" goto exit
echo 无效选项，请重新选择
goto menu

:install
echo 正在安装PPT处理服务...
python windows_service.py install
if errorlevel 1 (
    echo 服务安装失败！请检查是否以管理员身份运行
) else (
    echo 服务安装成功！
)
pause
goto menu

:start
echo 正在启动PPT处理服务...
python windows_service.py start
if errorlevel 1 (
    echo 服务启动失败！
) else (
    echo 服务启动成功！
)
pause
goto menu

:stop
echo 正在停止PPT处理服务...
python windows_service.py stop
if errorlevel 1 (
    echo 服务停止失败！
) else (
    echo 服务停止成功！
)
pause
goto menu

:restart
echo 正在重启PPT处理服务...
python windows_service.py restart
if errorlevel 1 (
    echo 服务重启失败！
) else (
    echo 服务重启成功！
)
pause
goto menu

:uninstall
echo 正在卸载PPT处理服务...
python windows_service.py remove
if errorlevel 1 (
    echo 服务卸载失败！
) else (
    echo 服务卸载成功！
)
pause
goto menu

:status
echo 查看服务状态...
sc query PPTProcessingService
pause
goto menu

:create_task
echo 正在创建定时清理任务...
schtasks /create /tn "PPT文件清理任务" /tr "python \"%~dp0cleanup_script.py\"" /sc daily /st 02:00 /f
if errorlevel 1 (
    echo 定时任务创建失败！请检查是否以管理员身份运行
) else (
    echo 定时任务创建成功！每天凌晨2点执行清理
)
pause
goto menu

:delete_task
echo 正在删除定时清理任务...
schtasks /delete /tn "PPT文件清理任务" /f
if errorlevel 1 (
    echo 定时任务删除失败！
) else (
    echo 定时任务删除成功！
)
pause
goto menu

:exit
echo 退出管理脚本
exit /b 0
