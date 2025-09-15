# PPT转图片服务 (Go + gRPC)

这是一个基于Go语言和gRPC的PPT转图片服务，专门为Windows平台设计，使用PowerPoint COM接口进行转换。

## 功能特性

- 🚀 基于gRPC的高性能服务
- 📊 实时进度更新
- 🖼️ 支持多种图片格式 (PNG, JPEG)
- 📱 流式文件传输
- 🔄 异步处理
- 📝 详细的日志记录

## 系统要求

- Windows 10/11
- Go 1.21+
- Microsoft PowerPoint (用于COM接口)
- Protocol Buffers 编译器 (protoc)

## 安装依赖

### 1. 安装Protocol Buffers编译器

从 [Protocol Buffers Releases](https://github.com/protocolbuffers/protobuf/releases) 下载并安装protoc。

### 2. 安装Go依赖

```bash
go mod tidy
```

### 3. 生成protobuf代码

运行批处理文件生成protobuf代码：

```bash
scripts\generate_proto.bat
```

或者手动运行：

```bash
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
protoc --go_out=proto --go_opt=paths=source_relative --go-grpc_out=proto --go-grpc_opt=paths=source_relative proto/ppt_service.proto
```

## 运行服务

### 1. 启动服务器

```bash
go run cmd/server/main.go
```

可选参数：
- `-port`: gRPC服务端口 (默认: 50051)
- `-output`: 输出目录 (默认: ./output)
- `-temp`: 临时目录 (默认: ./temp)
- `-log-level`: 日志级别 (默认: info)

示例：
```bash
go run cmd/server/main.go -port 50051 -output ./output -temp ./temp -log-level debug
```

### 2. 运行客户端

```bash
go run cmd/client/main.go <ppt文件路径> [输出目录] [宽度] [高度]
```

示例：
```bash
go run cmd/client/main.go example.pptx ./output 1920 1080
```

## 项目结构

```
go-ppt-service/
├── cmd/
│   ├── server/          # 服务器主程序
│   └── client/          # 客户端主程序
├── internal/
│   ├── converter/       # PPT转换器
│   └── server/          # gRPC服务器
├── proto/               # protobuf定义
├── scripts/             # 构建脚本
├── go.mod
└── README.md
```

## API接口

### ConvertPPT (流式)

转换PPT文件为图片，支持实时进度更新。

**请求:**
```protobuf
message ConvertPPTRequest {
    string filename = 1;           // 文件名
    bytes ppt_data = 2;            // PPT文件数据
    int32 width = 3;               // 输出图片宽度
    int32 height = 4;              // 输出图片高度
    string output_format = 5;      // 输出格式 (PNG, JPEG)
}
```

**响应 (流式):**
```protobuf
message ConvertPPTResponse {
    oneof response {
        ConversionStatus status = 1;    // 状态信息
        ImageInfo image_info = 2;       // 图片信息
        ConversionResult result = 3;    // 最终结果
    }
}
```

### GetConversionStatus

获取转换状态。

### DownloadImage (流式)

下载转换后的图片。

## 工作原理

1. **客户端上传**: 客户端通过gRPC流式上传PPT文件
2. **PowerShell转换**: 服务器使用PowerShell脚本调用PowerPoint COM接口
3. **进度更新**: 实时发送转换进度给客户端
4. **图片下载**: 转换完成后，客户端可以下载生成的图片

## 注意事项

- 需要安装Microsoft PowerPoint
- 确保PowerPoint可以正常启动
- 转换过程中PowerPoint会以不可见模式运行
- 转换完成后会自动关闭PowerPoint进程

## 故障排除

### 1. PowerPoint无法启动

确保：
- PowerPoint已正确安装
- 没有其他PowerPoint实例在运行
- 有足够的系统权限

### 2. COM接口错误

检查：
- PowerPoint版本是否支持COM接口
- 系统是否启用了COM组件

### 3. 转换失败

检查：
- PPT文件是否损坏
- 文件路径是否包含特殊字符
- 输出目录是否有写入权限

## 开发

### 添加新功能

1. 修改 `proto/ppt_service.proto`
2. 重新生成protobuf代码
3. 更新服务器和客户端实现

### 测试

```bash
# 运行服务器
go run cmd/server/main.go

# 在另一个终端运行客户端
go run cmd/client/main.go test.pptx
```

## 许可证

MIT License
