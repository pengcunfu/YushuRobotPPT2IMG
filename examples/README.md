# PPT处理API客户端示例

这个目录包含用于测试PPT处理API的客户端示例，分为两个独立的组件：

## 回调服务器 (server.py)

用于接收API处理完成后的回调通知。

### 启动回调服务器

```bash
python server.py
```

服务器将启动在 `http://localhost:8021`，提供以下接口：
- `POST /callback` - 接收回调通知
- `GET /status` - 查看回调状态

### 功能特点

- 自动接收并显示回调通知
- 格式化显示任务状态、文件信息、处理结果
- 记录所有收到的回调数据
- 提供状态查询接口

## 上传客户端 (upload.py)

用于上传PPT文件到API服务器进行处理。

### 使用方法

```bash
python upload.py <PPT文件路径> <回调URL> [宽度] [高度]
```

### 参数说明

- `PPT文件路径`: 要处理的PPT文件路径
- `回调URL`: 处理完成后的回调通知地址
- `宽度`: 输出图片宽度（可选，默认1280）
- `高度`: 输出图片高度（可选，默认720）

### 示例

```bash
# 基本用法
python upload.py ../1.pptx http://localhost:8021/callback

# 指定图片尺寸
python upload.py ../1.pptx http://localhost:8021/callback 1920 1080
```

## 完整使用流程

1. **启动API服务器**（在项目根目录）：
   ```bash
   python api.py
   ```

2. **启动回调服务器**：
   ```bash
   cd examples
   python server.py
   ```

3. **上传PPT文件**（在新的终端）：
   ```bash
   cd examples
   python upload.py ../1.pptx http://localhost:8021/callback
   ```

4. **查看结果**：
   - 上传成功后，回调服务器会自动接收并显示处理结果
   - 可以访问 `http://localhost:8021/status` 查看所有回调记录

## 配置说明

### API服务器配置
- 默认地址: `http://localhost:8020`
- 可在 `upload.py` 中修改 `api_server` 参数

### 回调服务器配置
- 默认地址: `http://localhost:8021`
- 可在 `server.py` 中修改相关配置

## 测试客户端 (test_client.py)

原始的完整测试客户端，包含上传和回调功能，现在主要用作参考。