package main

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"time"

	"github.com/sirupsen/logrus"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"ppt-to-images-service/proto"
)

// PPTClient PPT转换客户端
type PPTClient struct {
	conn   *grpc.ClientConn
	client proto.PPTToImagesServiceClient
	logger *logrus.Logger
}

// NewPPTClient 创建新的PPT客户端
func NewPPTClient(serverAddr string, logger *logrus.Logger) (*PPTClient, error) {
	conn, err := grpc.Dial(serverAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("连接服务器失败: %v", err)
	}

	client := proto.NewPPTToImagesServiceClient(conn)

	return &PPTClient{
		conn:   conn,
		client: client,
		logger: logger,
	}, nil
}

// Close 关闭客户端连接
func (c *PPTClient) Close() error {
	return c.conn.Close()
}

// ConvertPPT 转换PPT文件
func (c *PPTClient) ConvertPPT(pptPath string, outputDir string, width, height int32) error {
	// 读取PPT文件
	pptData, err := os.ReadFile(pptPath)
	if err != nil {
		return fmt.Errorf("读取PPT文件失败: %v", err)
	}

	filename := filepath.Base(pptPath)
	c.logger.Infof("开始转换PPT文件: %s", filename)

	// 创建转换请求
	req := &proto.ConvertPPTRequest{
		Filename:     filename,
		PptData:      pptData,
		Width:        width,
		Height:       height,
		OutputFormat: "PNG",
	}

	// 调用转换服务
	stream, err := c.client.ConvertPPT(context.Background(), req)
	if err != nil {
		return fmt.Errorf("调用转换服务失败: %v", err)
	}

	// 处理流式响应
	var images []*proto.ImageInfo
	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("接收响应失败: %v", err)
		}

		switch response := resp.Response.(type) {
		case *proto.ConvertPPTResponse_Status:
			// 处理状态更新
			status := response.Status
			c.logger.Infof("[%s] %s (%d%%) - %d/%d", 
				status.Status, 
				status.Message, 
				status.Progress,
				status.ProcessedSlides,
				status.TotalSlides)

		case *proto.ConvertPPTResponse_ImageInfo:
			// 收集图片信息
			images = append(images, response.ImageInfo)
			c.logger.Infof("图片信息: 幻灯片 %d - %s (大小: %d 字节)", 
				response.ImageInfo.SlideNumber,
				response.ImageInfo.Filename,
				response.ImageInfo.FileSize)

		case *proto.ConvertPPTResponse_Result:
			// 处理最终结果
			result := response.Result
			if result.Success {
				c.logger.Infof("转换成功: %s", result.Message)
				c.logger.Infof("总共转换了 %d/%d 张幻灯片", result.ConvertedSlides, result.TotalSlides)
				
				// 下载所有图片
				if err := c.downloadAllImages(images, outputDir); err != nil {
					c.logger.Errorf("下载图片失败: %v", err)
					return err
				}
			} else {
				return fmt.Errorf("转换失败: %s", result.Error)
			}
		}
	}

	return nil
}

// downloadAllImages 下载所有图片
func (c *PPTClient) downloadAllImages(images []*proto.ImageInfo, outputDir string) error {
	// 确保输出目录存在
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return fmt.Errorf("创建输出目录失败: %v", err)
	}

	c.logger.Infof("开始下载 %d 张图片到目录: %s", len(images), outputDir)

	for i, image := range images {
		c.logger.Infof("下载图片 %d/%d: %s", i+1, len(images), image.Filename)
		
		if err := c.downloadImage(image.DownloadId, filepath.Join(outputDir, image.Filename)); err != nil {
			c.logger.Errorf("下载图片失败 %s: %v", image.Filename, err)
			continue
		}
	}

	c.logger.Infof("所有图片下载完成")
	return nil
}

// downloadImage 下载单张图片
func (c *PPTClient) downloadImage(downloadID, outputPath string) error {
	req := &proto.DownloadRequest{
		DownloadId: downloadID,
	}

	stream, err := c.client.DownloadImage(context.Background(), req)
	if err != nil {
		return fmt.Errorf("调用下载服务失败: %v", err)
	}

	// 创建输出文件
	file, err := os.Create(outputPath)
	if err != nil {
		return fmt.Errorf("创建输出文件失败: %v", err)
	}
	defer file.Close()

	var fileSize int64
	var filename string

	// 处理流式响应
	for {
		resp, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("接收下载响应失败: %v", err)
		}

		switch response := resp.Response.(type) {
		case *proto.DownloadResponse_Info:
			// 文件信息
			info := response.Info
			fileSize = info.FileSize
			filename = info.Filename
			c.logger.Debugf("下载文件信息: %s (大小: %d 字节, 类型: %s)", 
				info.Filename, info.FileSize, info.ContentType)

		case *proto.DownloadResponse_Chunk:
			// 数据块
			if _, err := file.Write(response.Chunk); err != nil {
				return fmt.Errorf("写入文件失败: %v", err)
			}
		}
	}

	c.logger.Infof("图片下载完成: %s (大小: %d 字节)", filename, fileSize)
	return nil
}

// GetConversionStatus 获取转换状态
func (c *PPTClient) GetConversionStatus(conversionID string) (*proto.StatusResponse, error) {
	req := &proto.StatusRequest{
		ConversionId: conversionID,
	}

	resp, err := c.client.GetConversionStatus(context.Background(), req)
	if err != nil {
		return nil, fmt.Errorf("获取转换状态失败: %v", err)
	}

	return resp, nil
}

func main() {
	// 设置日志
	logger := logrus.New()
	logger.SetLevel(logrus.InfoLevel)
	logger.SetFormatter(&logrus.TextFormatter{
		FullTimestamp: true,
	})

	// 检查命令行参数
	if len(os.Args) < 2 {
		fmt.Println("用法: go run main.go <ppt文件路径> [输出目录] [宽度] [高度]")
		fmt.Println("示例: go run main.go example.pptx ./output 1920 1080")
		os.Exit(1)
	}

	pptPath := os.Args[1]
	outputDir := "./output"
	width := int32(1920)
	height := int32(1080)

	if len(os.Args) > 2 {
		outputDir = os.Args[2]
	}
	if len(os.Args) > 3 {
		if w, err := fmt.Sscanf(os.Args[3], "%d", &width); err != nil || w != 1 {
			logger.Warnf("无效的宽度参数，使用默认值: %d", width)
		}
	}
	if len(os.Args) > 4 {
		if h, err := fmt.Sscanf(os.Args[4], "%d", &height); err != nil || h != 1 {
			logger.Warnf("无效的高度参数，使用默认值: %d", height)
		}
	}

	// 检查PPT文件是否存在
	if _, err := os.Stat(pptPath); os.IsNotExist(err) {
		logger.Fatalf("PPT文件不存在: %s", pptPath)
	}

	logger.Infof("PPT转换客户端启动")
	logger.Infof("服务器地址: localhost:50051")
	logger.Infof("PPT文件: %s", pptPath)
	logger.Infof("输出目录: %s", outputDir)
	logger.Infof("输出尺寸: %dx%d", width, height)

	// 创建客户端
	client, err := NewPPTClient("localhost:50051", logger)
	if err != nil {
		logger.Fatalf("创建客户端失败: %v", err)
	}
	defer client.Close()

	// 执行转换
	startTime := time.Now()
	if err := client.ConvertPPT(pptPath, outputDir, width, height); err != nil {
		logger.Fatalf("转换失败: %v", err)
	}

	duration := time.Since(startTime)
	logger.Infof("转换完成，耗时: %v", duration)
}
