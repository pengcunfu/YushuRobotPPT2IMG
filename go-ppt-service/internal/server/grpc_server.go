package server

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"sync"
	"time"

	"github.com/sirupsen/logrus"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"ppt-to-images-service/internal/converter"
	"ppt-to-images-service/proto"
)

// GRPCServer gRPC服务器
type GRPCServer struct {
	proto.UnimplementedPPTToImagesServiceServer
	converter    *converter.PPTConverter
	logger       *logrus.Logger
	conversions  map[string]*ConversionSession
	conversionsMutex sync.RWMutex
	outputDir    string
	tempDir      string
}

// ConversionSession 转换会话
type ConversionSession struct {
	ID        string
	Status    converter.ConversionStatus
	Result    *converter.ConversionResult
	StartTime time.Time
	EndTime   *time.Time
	Mutex     sync.RWMutex
}

// NewGRPCServer 创建新的gRPC服务器
func NewGRPCServer(outputDir, tempDir string, logger *logrus.Logger) *GRPCServer {
	// 确保目录存在
	os.MkdirAll(outputDir, 0755)
	os.MkdirAll(tempDir, 0755)

	var pptConverter *converter.PPTConverter
	
	// 根据操作系统选择转换器
	if runtime.GOOS == "windows" {
		pptConverter = converter.NewWindowsPPTConverter(
			outputDir,
			tempDir,
			1920,  // 默认宽度
			1080,  // 默认高度
			"PNG", // 默认格式
			logger,
		)
	} else {
		// 非Windows平台使用基础转换器
		pptConverter = converter.NewPPTConverter(
			outputDir,
			tempDir,
			1920,  // 默认宽度
			1080,  // 默认高度
			"PNG", // 默认格式
			logger,
		)
	}

	return &GRPCServer{
		converter:   pptConverter,
		logger:      logger,
		conversions: make(map[string]*ConversionSession),
		outputDir:   outputDir,
		tempDir:     tempDir,
	}
}

// ConvertPPT 转换PPT文件 (流式响应)
func (s *GRPCServer) ConvertPPT(req *proto.ConvertPPTRequest, stream proto.PPTToImagesService_ConvertPPTServer) error {
	// 生成转换ID
	conversionID := generateConversionID()
	
	s.logger.Infof("开始处理转换请求: %s (ID: %s)", req.Filename, conversionID)

	// 创建转换会话
	session := &ConversionSession{
		ID:        conversionID,
		StartTime: time.Now(),
		Status: converter.ConversionStatus{
			Status:  "processing",
			Progress: 0,
			Message: "开始处理...",
		},
	}

	s.conversionsMutex.Lock()
	s.conversions[conversionID] = session
	s.conversionsMutex.Unlock()

	// 清理函数
	defer func() {
		s.conversionsMutex.Lock()
		delete(s.conversions, conversionID)
		s.conversionsMutex.Unlock()
	}()

	// 发送初始状态
	if err := s.sendStatusUpdate(stream, session); err != nil {
		return err
	}

	// 创建进度回调
	progressCallback := func(status converter.ConversionStatus) {
		session.Mutex.Lock()
		session.Status = status
		session.Mutex.Unlock()

		// 发送状态更新
		if err := s.sendStatusUpdate(stream, session); err != nil {
			s.logger.Errorf("发送状态更新失败: %v", err)
		}
	}

	// 执行转换
	result, err := s.converter.ConvertPPT(
		req.PptData,
		req.Filename,
		progressCallback,
	)

	// 更新会话结果
	session.Mutex.Lock()
	if err != nil {
		session.Status = converter.ConversionStatus{
			Status:  "failed",
			Progress: 100,
			Message: fmt.Sprintf("转换失败: %v", err),
		}
		session.Result = &converter.ConversionResult{
			Success: false,
			Error:   err.Error(),
		}
	} else {
		session.Status = converter.ConversionStatus{
			Status:  "completed",
			Progress: 100,
			Message: result.Message,
		}
		session.Result = result
	}
	now := time.Now()
	session.EndTime = &now
	session.Mutex.Unlock()

	// 发送最终结果
	if err := s.sendFinalResult(stream, session); err != nil {
		return err
	}

	s.logger.Infof("转换完成: %s (ID: %s)", req.Filename, conversionID)
	return nil
}

// GetConversionStatus 获取转换状态
func (s *GRPCServer) GetConversionStatus(ctx context.Context, req *proto.StatusRequest) (*proto.StatusResponse, error) {
	s.conversionsMutex.RLock()
	session, exists := s.conversions[req.ConversionId]
	s.conversionsMutex.RUnlock()

	if !exists {
		return nil, status.Errorf(codes.NotFound, "转换会话不存在: %s", req.ConversionId)
	}

	session.Mutex.RLock()
	defer session.Mutex.RUnlock()

	response := &proto.StatusResponse{
		Status: s.convertStatusToProto(session.Status),
	}

	if session.Result != nil {
		response.Result = s.convertResultToProto(session.Result)
	}

	return response, nil
}

// DownloadImage 下载图片 (流式响应)
func (s *GRPCServer) DownloadImage(req *proto.DownloadRequest, stream proto.PPTToImagesService_DownloadImageServer) error {
	// 查找对应的图片文件
	imagePath, err := s.findImageByDownloadID(req.DownloadId)
	if err != nil {
		return status.Errorf(codes.NotFound, "图片文件不存在: %s", req.DownloadId)
	}

	// 打开文件
	file, err := os.Open(imagePath)
	if err != nil {
		return status.Errorf(codes.Internal, "无法打开文件: %v", err)
	}
	defer file.Close()

	// 获取文件信息
	fileInfo, err := file.Stat()
	if err != nil {
		return status.Errorf(codes.Internal, "无法获取文件信息: %v", err)
	}

	// 发送文件信息
	info := &proto.DownloadInfo{
		Filename:    fileInfo.Name(),
		FileSize:    fileInfo.Size(),
		ContentType: s.getContentType(filepath.Ext(imagePath)),
	}

	if err := stream.Send(&proto.DownloadResponse{
		Response: &proto.DownloadResponse_Info{Info: info},
	}); err != nil {
		return err
	}

	// 分块发送文件数据
	buffer := make([]byte, 64*1024) // 64KB 缓冲区
	for {
		n, err := file.Read(buffer)
		if err == io.EOF {
			break
		}
		if err != nil {
			return status.Errorf(codes.Internal, "读取文件失败: %v", err)
		}

		if err := stream.Send(&proto.DownloadResponse{
			Response: &proto.DownloadResponse_Chunk{Chunk: buffer[:n]},
		}); err != nil {
			return err
		}
	}

	return nil
}

// sendStatusUpdate 发送状态更新
func (s *GRPCServer) sendStatusUpdate(stream proto.PPTToImagesService_ConvertPPTServer, session *ConversionSession) error {
	session.Mutex.RLock()
	status := session.Status
	session.Mutex.RUnlock()

	return stream.Send(&proto.ConvertPPTResponse{
		Response: &proto.ConvertPPTResponse_Status{
			Status: s.convertStatusToProto(status),
		},
	})
}

// sendFinalResult 发送最终结果
func (s *GRPCServer) sendFinalResult(stream proto.PPTToImagesService_ConvertPPTServer, session *ConversionSession) error {
	session.Mutex.RLock()
	result := session.Result
	session.Mutex.RUnlock()

	if result == nil {
		return fmt.Errorf("转换结果为空")
	}

	// 发送每个图片信息
	for _, image := range result.Images {
		if err := stream.Send(&proto.ConvertPPTResponse{
			Response: &proto.ConvertPPTResponse_ImageInfo{
				ImageInfo: s.convertImageInfoToProto(image),
			},
		}); err != nil {
			return err
		}
	}

	// 发送最终结果
	return stream.Send(&proto.ConvertPPTResponse{
		Response: &proto.ConvertPPTResponse_Result{
			Result: s.convertResultToProto(result),
		},
	})
}

// convertStatusToProto 转换状态到protobuf
func (s *GRPCServer) convertStatusToProto(status converter.ConversionStatus) *proto.ConversionStatus {
	return &proto.ConversionStatus{
		Status:          status.Status,
		Progress:        int32(status.Progress),
		Message:         status.Message,
		TotalSlides:     int32(status.TotalSlides),
		ProcessedSlides: int32(status.ProcessedSlides),
	}
}

// convertResultToProto 转换结果到protobuf
func (s *GRPCServer) convertResultToProto(result *converter.ConversionResult) *proto.ConversionResult {
	protoResult := &proto.ConversionResult{
		Success:         result.Success,
		Message:         result.Message,
		TotalSlides:     int32(result.TotalSlides),
		ConvertedSlides: int32(result.ConvertedSlides),
		Error:           result.Error,
	}

	for _, image := range result.Images {
		protoResult.Images = append(protoResult.Images, s.convertImageInfoToProto(image))
	}

	return protoResult
}

// convertImageInfoToProto 转换图片信息到protobuf
func (s *GRPCServer) convertImageInfoToProto(image converter.ImageInfo) *proto.ImageInfo {
	return &proto.ImageInfo{
		SlideNumber: int32(image.SlideNumber),
		Filename:    image.Filename,
		FileSize:    image.FileSize,
		DownloadId:  image.DownloadID,
	}
}

// findImageByDownloadID 根据下载ID查找图片文件
func (s *GRPCServer) findImageByDownloadID(downloadID string) (string, error) {
	// 在实际实现中，这里应该维护一个下载ID到文件路径的映射
	// 为了简化，我们遍历输出目录查找文件
	return filepath.Glob(filepath.Join(s.outputDir, "**", "*"))
}

// getContentType 根据文件扩展名获取内容类型
func (s *GRPCServer) getContentType(ext string) string {
	switch ext {
	case ".png":
		return "image/png"
	case ".jpg", ".jpeg":
		return "image/jpeg"
	case ".gif":
		return "image/gif"
	case ".webp":
		return "image/webp"
	default:
		return "application/octet-stream"
	}
}

// generateConversionID 生成转换ID
func generateConversionID() string {
	return fmt.Sprintf("conv_%d", time.Now().UnixNano())
}
