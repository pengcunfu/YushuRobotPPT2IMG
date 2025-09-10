# PPT处理API系统

🚀 一个高效稳定的PowerPoint文件转图片处理系统，支持异步处理、自动重启和定时清理。

## ✨ 特性

- 🔄 **异步处理**: 基于回调机制的异步PPT转图片处理
- 🛡️ **自动重启**: Windows服务确保程序崩溃后自动恢复
- 🧹 **定时清理**: 每日自动清理临时文件，节省磁盘空间
- 📊 **详细日志**: 完整的操作日志和错误追踪
- 🎯 **高可用性**: 多重保障确保服务稳定运行
- 🔧 **易于管理**: 图形化服务管理和一键部署

## 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   客户端应用     │───▶│   PPT API服务   │───▶│   PowerPoint    │
│  (上传PPT文件)   │    │  (Flask服务)    │    │   COM组件       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         ▲                       │                       │
         │                       ▼                       ▼
         │              ┌─────────────────┐    ┌─────────────────┐
         │              │   文件存储       │    │   图片生成       │
         │              │ uploads/results │    │   (PNG格式)     │
         │              └─────────────────┘    └─────────────────┘
         │                       │
         └───────────────────────┘
              回调通知结果
```

## 🚀 快速开始

### 1️⃣ 环境要求

- ✅ Windows 10/11 或 Windows Server
- ✅ Python 3.7+
- ✅ Microsoft PowerPoint
- ✅ 管理员权限

### 2️⃣ 一键安装

```cmd
# 1. 下载项目到本地
git clone <项目地址>
cd ppt

# 2. 安装依赖（以管理员身份运行）
install_dependencies.bat

# 3. 启动服务管理器
service_manager.bat
```

### 3️⃣ 服务配置

在服务管理器中依次操作：
1. 选择 `1` - 安装服务
2. 选择 `2` - 启动服务  
3. 选择 `7` - 设置定时清理任务

### 4️⃣ 测试使用

```cmd
# 启动测试回调服务器
cd examples
python server.py

# 新开命令行窗口，上传测试文件
cd examples
python upload.py ../test.pptx http://localhost:8021/callback
```

## 📚 目录结构

```
ppt/
├── 📄 api.py                    # 主API服务
├── 🔧 windows_service.py        # Windows服务包装器
├── 🧹 cleanup_script.py         # 定时清理脚本
├── ⚙️ pptx_to_images.py         # PPT转图片核心模块
├── 📋 requirements.txt          # Python依赖
├── 🚀 service_manager.bat       # 服务管理界面
├── 📦 install_dependencies.bat  # 依赖安装脚本
├── 📖 README.md                 # 项目说明（本文件）
├── 📘 使用说明.md               # 详细使用文档
├── 🔧 README_SERVICE.md         # 服务部署指南
├── 📁 examples/                 # 客户端示例
│   ├── 🖥️ server.py            # 回调服务器
│   ├── 📤 upload.py             # 上传客户端
│   └── 📖 README.md             # 示例说明
├── 📁 uploads/                  # 上传文件目录
└── 📁 results/                  # 处理结果目录
```

## 🔌 API接口

### 上传文件接口

**接口**: `POST /api/upload`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | ✅ | PPT文件(.ppt/.pptx) |
| callback_url | String | ✅ | 回调通知地址 |
| width | Integer | ❌ | 图片宽度(默认1920) |
| height | Integer | ❌ | 图片高度(默认1080) |

**响应示例**:
```json
{
  "task_id": "uuid-string",
  "status": "pending", 
  "message": "PPT conversion started, result will be sent to callback URL"
}
```

### 回调通知

处理完成后会向回调URL发送POST请求：

```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "original_filename": "example.pptx",
  "image_count": 10,
  "images": [
    {
      "slide": 1,
      "filename": "slide_1.png", 
      "path": "/api/tasks/uuid/images/slide_1.png"
    }
  ]
}
```

## 🛠️ 开发集成

### Python示例

```python
import requests

def upload_ppt(file_path, callback_url):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'callback_url': callback_url,
            'width': 1920,
            'height': 1080
        }
        response = requests.post(
            'http://localhost:8020/api/upload',
            files=files, 
            data=data
        )
        return response.json()

# 使用示例
result = upload_ppt('presentation.pptx', 'http://your-server.com/callback')
print(f"任务ID: {result['task_id']}")
```

### cURL示例

```bash
curl -X POST http://localhost:8020/api/upload \
  -F "file=@presentation.pptx" \
  -F "callback_url=http://your-server.com/callback" \
  -F "width=1920" \
  -F "height=1080"
```

## 📊 监控管理

### 服务状态监控

```cmd
# 查看服务状态
sc query PPTProcessingService

# 查看服务日志
type ppt_service.log

# 重启服务
python windows_service.py restart
```

### 清理任务监控

```cmd
# 查看定时任务
schtasks /query /tn "PPT文件清理任务"

# 手动执行清理
python cleanup_script.py

# 查看清理日志
type cleanup_20240101.log
```

## 🔧 配置说明

### 服务配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 服务端口 | 8020 | API服务监听端口 |
| 文件大小限制 | 100MB | 单个文件最大大小 |
| 回调重试次数 | 3 | 回调失败重试次数 |
| 回调超时 | 10秒 | 回调请求超时时间 |

### 清理配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 清理时间 | 每日2:00 | 定时清理执行时间 |
| 清理目录 | uploads/, results/ | 清理的目录列表 |

## 🚨 故障排除

### 常见问题

<details>
<summary>❗ 服务无法启动</summary>

**可能原因**:
- 未以管理员身份运行
- Python环境问题
- 端口被占用

**解决方法**:
1. 确保以管理员身份运行命令提示符
2. 检查Python版本和环境变量
3. 检查端口8020是否被占用: `netstat -an | findstr 8020`
4. 查看服务日志: `type ppt_service.log`
</details>

<details>
<summary>❗ PPT处理失败</summary>

**可能原因**:
- PowerPoint未安装或版本不兼容
- PPT文件损坏
- 权限问题

**解决方法**:
1. 确认PowerPoint已安装并可正常使用
2. 尝试手动打开PPT文件确认文件完整性
3. 检查服务账户权限
4. 查看详细错误日志
</details>

<details>
<summary>❗ 回调未收到</summary>

**可能原因**:
- 回调URL不可访问
- 网络连接问题
- 回调服务器故障

**解决方法**:
1. 确认回调URL可从服务器访问
2. 检查防火墙和网络设置
3. 验证回调服务器是否正常运行
4. 查看回调重试日志
</details>

## 📞 技术支持

- 📖 [详细使用说明](使用说明.md)
- 🔧 [服务部署指南](README_SERVICE.md)  
- 💡 [客户端示例](examples/README.md)

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🤝 贡献

欢迎提交问题和功能请求！

---

⭐ 如果这个项目对您有帮助，请给个星标支持！
