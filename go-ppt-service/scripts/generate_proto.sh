#!/bin/bash

# 生成protobuf代码的脚本

set -e

echo "生成protobuf代码..."

# 检查protoc是否安装
if ! command -v protoc &> /dev/null; then
    echo "错误: protoc 未安装"
    echo "请安装 Protocol Buffers 编译器:"
    echo "  - Ubuntu/Debian: sudo apt-get install protobuf-compiler"
    echo "  - macOS: brew install protobuf"
    echo "  - Windows: 从 https://github.com/protocolbuffers/protobuf/releases 下载"
    exit 1
fi

# 检查protoc-gen-go是否安装
if ! command -v protoc-gen-go &> /dev/null; then
    echo "安装 protoc-gen-go..."
    go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
fi

# 检查protoc-gen-go-grpc是否安装
if ! command -v protoc-gen-go-grpc &> /dev/null; then
    echo "安装 protoc-gen-go-grpc..."
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
fi

# 创建输出目录
mkdir -p proto

# 生成Go代码
echo "生成Go代码..."
protoc \
    --go_out=proto \
    --go_opt=paths=source_relative \
    --go-grpc_out=proto \
    --go-grpc_opt=paths=source_relative \
    proto/ppt_service.proto

echo "protobuf代码生成完成!"
echo "生成的文件:"
echo "  - proto/ppt_service.pb.go"
echo "  - proto/ppt_service_grpc.pb.go"
