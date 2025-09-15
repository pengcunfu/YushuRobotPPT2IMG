@echo off
echo 生成protobuf代码...

REM 检查protoc是否安装
where protoc >nul 2>nul
if %errorlevel% neq 0 (
    echo 错误: protoc 未安装
    echo 请安装 Protocol Buffers 编译器:
    echo   从 https://github.com/protocolbuffers/protobuf/releases 下载
    pause
    exit /b 1
)

REM 检查protoc-gen-go是否安装
where protoc-gen-go >nul 2>nul
if %errorlevel% neq 0 (
    echo 安装 protoc-gen-go...
    go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
)

REM 检查protoc-gen-go-grpc是否安装
where protoc-gen-go-grpc >nul 2>nul
if %errorlevel% neq 0 (
    echo 安装 protoc-gen-go-grpc...
    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
)

REM 创建输出目录
if not exist proto mkdir proto

REM 生成Go代码
echo 生成Go代码...
protoc ^
    --go_out=proto ^
    --go_opt=paths=source_relative ^
    --go-grpc_out=proto ^
    --go-grpc_opt=paths=source_relative ^
    proto/ppt_service.proto

if %errorlevel% neq 0 (
    echo protobuf代码生成失败
    pause
    exit /b 1
)

echo protobuf代码生成完成!
echo 生成的文件:
echo   - proto/ppt_service.pb.go
echo   - proto/ppt_service_grpc.pb.go
pause
