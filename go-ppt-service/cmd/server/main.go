package main

import (
	"flag"
	"fmt"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/sirupsen/logrus"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"

	"ppt-to-images-service/internal/server"
	"ppt-to-images-service/proto"
)

func main() {
	// 命令行参数
	var (
		port      = flag.String("port", "50051", "gRPC服务端口")
		outputDir = flag.String("output", "./output", "输出目录")
		tempDir   = flag.String("temp", "./temp", "临时目录")
		logLevel  = flag.String("log-level", "info", "日志级别 (debug, info, warn, error)")
	)
	flag.Parse()

	// 设置日志
	logger := logrus.New()
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
	})

	// 设置日志级别
	switch *logLevel {
	case "debug":
		logger.SetLevel(logrus.DebugLevel)
	case "info":
		logger.SetLevel(logrus.InfoLevel)
	case "warn":
		logger.SetLevel(logrus.WarnLevel)
	case "error":
		logger.SetLevel(logrus.ErrorLevel)
	default:
		logger.SetLevel(logrus.InfoLevel)
	}

	logger.Infof("PPT转图片服务启动")
	logger.Infof("端口: %s", *port)
	logger.Infof("输出目录: %s", *outputDir)
	logger.Infof("临时目录: %s", *tempDir)
	logger.Infof("日志级别: %s", *logLevel)

	// 创建gRPC服务器
	grpcServer := grpc.NewServer()
	
	// 创建PPT服务
	pptService := server.NewGRPCServer(*outputDir, *tempDir, logger)
	proto.RegisterPPTToImagesServiceServer(grpcServer, pptService)
	
	// 启用gRPC反射 (用于调试和测试)
	reflection.Register(grpcServer)

	// 启动服务器
	listener, err := net.Listen("tcp", ":"+*port)
	if err != nil {
		logger.Fatalf("监听端口失败: %v", err)
	}

	logger.Infof("gRPC服务器启动在端口 %s", *port)

	// 启动服务器协程
	go func() {
		if err := grpcServer.Serve(listener); err != nil {
			logger.Fatalf("gRPC服务器启动失败: %v", err)
		}
	}()

	// 等待中断信号
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	logger.Info("收到停止信号，正在关闭服务器...")

	// 优雅关闭
	grpcServer.GracefulStop()
	logger.Info("服务器已关闭")
}
