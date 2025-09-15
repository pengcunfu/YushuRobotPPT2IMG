# PPT转图片Flask服务

基于Flask的纯HTTP方案，支持上传PPT文件并流式返回转换后的图片。

## 功能特性

- ✅ **文件上传**: 支持PPT/PPTX文件上传到本地uploads目录
- ✅ **PPT转换**: 使用Windows COM接口将PPT转换为高质量图片
- ✅ **流式返回**: 支持流式下载图片，节省内存
- ✅ **会话管理**: 每个上传文件都有唯一的会话ID
- ✅ **自动清理**: 自动清理超过24小时的过期文件
- ✅ **错误处理**: 完善的错误处理和状态反馈
- ✅ **RESTful API**: 标准的HTTP API接口

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python flask_server.py
```

服务将在 `http://localhost:5000` 启动

### 3. 测试服务

#### 方法1: 使用测试页面（推荐）
在浏览器中打开 `test_page.html` 文件，通过Web界面测试所有功能。

#### 方法2: 使用Python客户端
```bash
python test_client.py
```

#### 方法3: 使用curl命令
```bash
# 上传文件
curl -X POST -F "file=@examples/1.pptx" http://localhost:5000/upload

# 转换PPT（替换SESSION_ID）
curl -X POST -H "Content-Type: application/json" \
  -d '{"width":1920,"height":1080}' \
  http://localhost:5000/convert/SESSION_ID

# 下载图片
curl -O http://localhost:5000/download/SESSION_ID/filename.png
```

## API接口文档

### 1. 上传PPT文件
```http
POST /upload
Content-Type: multipart/form-data

参数:
- file: PPT文件 (必需)

响应:
{
  "session_id": "uuid",
  "filename": "example.pptx",
  "message": "文件上传成功"
}
```

### 2. 转换PPT为图片
```http
POST /convert/{session_id}
Content-Type: application/json

参数:
{
  "width": 1920,    // 图片宽度 (可选，默认1920)
  "height": 1080    // 图片高度 (可选，默认1080)
}

响应:
{
  "session_id": "uuid",
  "status": "completed",
  "total_slides": 10,
  "converted_slides": 10,
  "images": [
    {
      "slide_number": 1,
      "filename": "uuid.png",
      "download_url": "/download/session_id/filename.png"
    }
  ]
}
```

### 3. 获取转换状态
```http
GET /status/{session_id}

响应:
{
  "session_id": "uuid",
  "status": "completed",
  "filename": "example.pptx",
  "upload_time": "2024-01-01T12:00:00",
  "conversion_result": { ... }
}
```

### 4. 下载图片文件
```http
GET /download/{session_id}/{filename}

响应: 图片文件 (二进制数据)
```

### 5. 流式下载图片
```http
GET /stream/{session_id}/{filename}

响应: 图片文件流 (二进制数据)
```

### 6. 获取图片信息
```http
GET /info/{session_id}/{filename}

响应:
{
  "filename": "uuid.png",
  "size": 123456,
  "modified_time": "2024-01-01T12:00:00"
}
```

## 目录结构

```
项目根目录/
├── flask_server.py          # Flask服务器主文件
├── test_client.py           # Python测试客户端
├── test_page.html           # Web测试页面
├── pptx_to_images.py        # PPT转换核心模块
├── uploads/                 # 上传文件存储目录
├── outputs/                 # 转换结果存储目录
└── examples/                # 示例PPT文件
```

## 配置说明

### 服务器配置
- **端口**: 5000 (可在flask_server.py中修改)
- **最大文件大小**: 100MB
- **上传目录**: uploads/
- **输出目录**: outputs/
- **文件清理**: 自动清理24小时前的文件

### 转换参数
- **默认尺寸**: 1920x1080
- **输出格式**: PNG
- **质量**: 高质量输出

## 错误处理

服务提供完善的错误处理机制：

- **400 Bad Request**: 请求参数错误
- **404 Not Found**: 会话或文件不存在
- **413 Payload Too Large**: 文件过大
- **500 Internal Server Error**: 服务器内部错误

所有错误都会返回JSON格式的错误信息：
```json
{
  "error": "错误描述"
}
```

## 性能优化

1. **流式传输**: 大文件使用流式传输，节省内存
2. **自动清理**: 定期清理过期文件，节省磁盘空间
3. **多线程**: 支持并发请求处理
4. **会话管理**: 高效的会话状态管理

## 安全考虑

1. **文件类型检查**: 只允许上传PPT/PPTX文件
2. **文件名安全**: 使用secure_filename处理文件名
3. **路径安全**: 防止路径遍历攻击
4. **文件大小限制**: 限制上传文件大小

## 故障排除

### 常见问题

1. **PowerPoint COM错误**
   - 确保系统安装了Microsoft PowerPoint
   - 检查PowerPoint是否被其他程序占用

2. **文件上传失败**
   - 检查文件大小是否超过100MB
   - 确认文件格式为PPT或PPTX

3. **转换失败**
   - 检查PPT文件是否损坏
   - 确认有足够的磁盘空间

4. **服务无法启动**
   - 检查端口5000是否被占用
   - 确认所有依赖已正确安装

### 日志查看

服务使用loguru进行日志记录，可以在控制台查看详细的运行日志。

## 扩展功能

可以基于现有代码扩展以下功能：

1. **批量处理**: 支持批量上传和转换
2. **格式转换**: 支持更多输出格式（JPG、PDF等）
3. **压缩选项**: 添加图片压缩选项
4. **用户认证**: 添加用户认证和权限管理
5. **数据库存储**: 使用数据库存储会话信息
6. **分布式部署**: 支持多实例部署

## 许可证

本项目基于MIT许可证开源。
