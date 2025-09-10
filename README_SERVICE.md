# PPT处理服务部署指南

本项目提供了Windows服务和定时清理功能，确保API服务稳定运行并自动清理临时文件。

## 功能特性

### Windows服务功能
- **自动重启**: 当API程序崩溃时自动重启
- **服务监控**: 持续监控API进程状态
- **日志记录**: 详细的服务运行日志
- **系统集成**: 作为Windows系统服务运行

### 定时清理功能
- **每日清理**: 每天凌晨2点自动清理
- **清理目录**: `uploads/` 和 `results/` 目录
- **日志记录**: 清理过程和结果日志
- **统计信息**: 清理前后的文件统计

## 安装步骤

### 1. 安装依赖

**方法一：使用批处理脚本（推荐）**
```cmd
# 以管理员身份运行
install_dependencies.bat
```

**方法二：手动安装**
```cmd
pip install -r requirements.txt
pip install pywin32
python -m pip install --upgrade pywin32
```

### 2. 安装和管理服务

使用服务管理脚本：
```cmd
# 以管理员身份运行
service_manager.bat
```

或手动执行：
```cmd
# 安装服务
python windows_service.py install

# 启动服务
python windows_service.py start

# 停止服务
python windows_service.py stop

# 卸载服务
python windows_service.py remove
```

### 3. 设置定时清理任务

**使用管理脚本**：
- 运行 `service_manager.bat`
- 选择选项 7 创建定时任务

**手动创建**：
```cmd
schtasks /create /tn "PPT文件清理任务" /tr "python C:\path\to\cleanup_script.py" /sc daily /st 02:00 /f
```

## 文件说明

### 核心文件
- `api.py` - 主API服务
- `windows_service.py` - Windows服务包装器
- `cleanup_script.py` - 定时清理脚本

### 管理工具
- `service_manager.bat` - 服务管理界面
- `install_dependencies.bat` - 依赖安装脚本
- `README_SERVICE.md` - 本说明文档

### 日志文件
- `ppt_service.log` - 服务运行日志
- `cleanup_YYYYMMDD.log` - 清理任务日志

## 使用说明

### 服务管理

1. **查看服务状态**:
   ```cmd
   sc query PPTProcessingService
   ```

2. **查看服务日志**:
   - 服务日志: `ppt_service.log`
   - Windows事件日志: 应用程序日志中查找 "PPTProcessingService"

3. **重启服务**:
   ```cmd
   python windows_service.py restart
   ```

### 手动清理

如需手动执行清理：
```cmd
python cleanup_script.py
```

### 定时任务管理

查看已创建的定时任务：
```cmd
schtasks /query /tn "PPT文件清理任务"
```

删除定时任务：
```cmd
schtasks /delete /tn "PPT文件清理任务" /f
```

## 监控和维护

### 日志监控
- 定期检查 `ppt_service.log` 了解服务状态
- 查看清理日志确认定时任务执行情况

### 性能监控
- 监控CPU和内存使用情况
- 检查磁盘空间（特别是uploads和results目录）

### 故障排除

**服务无法启动**:
1. 检查是否以管理员身份安装
2. 确认Python环境和依赖完整
3. 查看服务日志和事件日志

**API连接失败**:
1. 检查端口8020是否被占用
2. 确认防火墙设置
3. 查看API服务日志

**清理任务未执行**:
1. 检查定时任务是否创建成功
2. 确认任务计划程序服务运行正常
3. 查看清理日志

## 安全注意事项

1. **管理员权限**: 安装和管理服务需要管理员权限
2. **文件权限**: 确保服务账户对工作目录有读写权限
3. **网络安全**: 根据需要配置防火墙规则
4. **备份策略**: 重要数据应在清理前备份

## 卸载说明

1. 停止并卸载服务：
   ```cmd
   python windows_service.py stop
   python windows_service.py remove
   ```

2. 删除定时任务：
   ```cmd
   schtasks /delete /tn "PPT文件清理任务" /f
   ```

3. 清理文件（可选）：
   - 删除日志文件
   - 清理临时目录
