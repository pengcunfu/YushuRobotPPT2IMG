package converter

import (
	"bytes"
	"fmt"
	"image"
	"image/jpeg"
	"image/png"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/disintegration/imaging"
	"github.com/sirupsen/logrus"
)

// ImageInfo 图片信息
type ImageInfo struct {
	SlideNumber int    `json:"slide_number"`
	Filename    string `json:"filename"`
	FilePath    string `json:"file_path"`
	FileSize    int64  `json:"file_size"`
	DownloadID  string `json:"download_id"`
}

// ConversionResult 转换结果
type ConversionResult struct {
	Success         bool        `json:"success"`
	Message         string      `json:"message"`
	TotalSlides     int         `json:"total_slides"`
	ConvertedSlides int         `json:"converted_slides"`
	Images          []ImageInfo `json:"images"`
	Error           string      `json:"error,omitempty"`
}

// ConversionStatus 转换状态
type ConversionStatus struct {
	Status          string `json:"status"`
	Progress        int    `json:"progress"`
	Message         string `json:"message"`
	TotalSlides     int    `json:"total_slides"`
	ProcessedSlides int    `json:"processed_slides"`
}

// ProgressCallback 进度回调函数
type ProgressCallback func(status ConversionStatus)

// PPTConverter PPT转换器
type PPTConverter struct {
	outputDir    string
	tempDir      string
	width        int
	height       int
	outputFormat string
	logger       *logrus.Logger
}

// NewPPTConverter 创建新的PPT转换器
func NewPPTConverter(outputDir, tempDir string, width, height int, outputFormat string, logger *logrus.Logger) *PPTConverter {
	return &PPTConverter{
		outputDir:    outputDir,
		tempDir:      tempDir,
		width:        width,
		height:       height,
		outputFormat: strings.ToUpper(outputFormat),
		logger:       logger,
	}
}

// ConvertPPT 转换PPT文件
func (c *PPTConverter) ConvertPPT(pptData []byte, filename string, progressCallback ProgressCallback) (*ConversionResult, error) {
	c.logger.Info("开始转换PPT文件: ", filename)
	
	// 创建临时文件
	tempFile, err := c.createTempFile(pptData, filename)
	if err != nil {
		return nil, fmt.Errorf("创建临时文件失败: %v", err)
	}
	defer os.Remove(tempFile)

	// 发送开始处理状态
	if progressCallback != nil {
		progressCallback(ConversionStatus{
			Status:  "processing",
			Progress: 10,
			Message: "正在解析PPT文件...",
		})
	}

	// 打开PPT文件
	pres, err := presentation.Open(tempFile)
	if err != nil {
		return nil, fmt.Errorf("打开PPT文件失败: %v", err)
	}
	defer pres.Close()

	totalSlides := len(pres.Slides())
	c.logger.Infof("PPT文件包含 %d 张幻灯片", totalSlides)

	// 发送解析完成状态
	if progressCallback != nil {
		progressCallback(ConversionStatus{
			Status:      "processing",
			Progress:    20,
			Message:     fmt.Sprintf("PPT解析完成，共 %d 张幻灯片", totalSlides),
			TotalSlides: totalSlides,
		})
	}

	// 创建输出目录
	outputPath := filepath.Join(c.outputDir, generateSessionID())
	if err := os.MkdirAll(outputPath, 0755); err != nil {
		return nil, fmt.Errorf("创建输出目录失败: %v", err)
	}

	var images []ImageInfo
	convertedCount := 0

	// 转换每张幻灯片
	for i, slide := range pres.Slides() {
		slideNumber := i + 1
		
		// 发送当前处理状态
		if progressCallback != nil {
			progress := 20 + int(float64(slideNumber)/float64(totalSlides)*70)
			progressCallback(ConversionStatus{
				Status:          "processing",
				Progress:        progress,
				Message:         fmt.Sprintf("正在转换第 %d/%d 张幻灯片", slideNumber, totalSlides),
				TotalSlides:     totalSlides,
				ProcessedSlides: slideNumber - 1,
			})
		}

		// 转换幻灯片为图片
		imageInfo, err := c.convertSlide(slide, slideNumber, outputPath)
		if err != nil {
			c.logger.Errorf("转换第 %d 张幻灯片失败: %v", slideNumber, err)
			continue
		}

		images = append(images, *imageInfo)
		convertedCount++

		c.logger.Infof("成功转换第 %d 张幻灯片: %s", slideNumber, imageInfo.Filename)
	}

	// 发送完成状态
	if progressCallback != nil {
		progressCallback(ConversionStatus{
			Status:          "completed",
			Progress:        100,
			Message:         fmt.Sprintf("转换完成，成功转换 %d/%d 张幻灯片", convertedCount, totalSlides),
			TotalSlides:     totalSlides,
			ProcessedSlides: convertedCount,
		})
	}

	result := &ConversionResult{
		Success:         convertedCount > 0,
		Message:         fmt.Sprintf("成功转换 %d/%d 张幻灯片", convertedCount, totalSlides),
		TotalSlides:     totalSlides,
		ConvertedSlides: convertedCount,
		Images:          images,
	}

	if convertedCount == 0 {
		result.Error = "没有成功转换任何幻灯片"
		result.Success = false
	}

	c.logger.Infof("PPT转换完成: %s", result.Message)
	return result, nil
}

// convertSlide 转换单张幻灯片
func (c *PPTConverter) convertSlide(slide *presentation.Slide, slideNumber int, outputPath string) (*ImageInfo, error) {
	// 生成文件名
	filename := fmt.Sprintf("slide_%03d.%s", slideNumber, strings.ToLower(c.outputFormat))
	filePath := filepath.Join(outputPath, filename)

	// 将幻灯片转换为图片
	// 注意: unioffice库可能不直接支持幻灯片转图片
	// 这里我们使用一个简化的方法，实际项目中可能需要使用其他库或工具
	
	// 创建一个占位图片 (实际实现中需要真正的幻灯片转图片逻辑)
	img, err := c.createPlaceholderImage(slideNumber)
	if err != nil {
		return nil, fmt.Errorf("创建图片失败: %v", err)
	}

	// 调整图片尺寸
	if c.width > 0 && c.height > 0 {
		img = imaging.Resize(img, c.width, c.height, imaging.Lanczos)
	}

	// 保存图片
	if err := c.saveImage(img, filePath); err != nil {
		return nil, fmt.Errorf("保存图片失败: %v", err)
	}

	// 获取文件信息
	fileInfo, err := os.Stat(filePath)
	if err != nil {
		return nil, fmt.Errorf("获取文件信息失败: %v", err)
	}

	return &ImageInfo{
		SlideNumber: slideNumber,
		Filename:    filename,
		FilePath:    filePath,
		FileSize:    fileInfo.Size(),
		DownloadID:  generateDownloadID(),
	}, nil
}

// createPlaceholderImage 创建占位图片 (实际项目中需要实现真正的幻灯片转图片)
func (c *PPTConverter) createPlaceholderImage(slideNumber int) (image.Image, error) {
	// 创建一个简单的占位图片
	// 实际实现中，这里应该使用真正的PPT转图片逻辑
	// 可能需要调用外部工具如LibreOffice或使用其他Go库
	
	width := c.width
	height := c.height
	if width <= 0 {
		width = 1920
	}
	if height <= 0 {
		height = 1080
	}

	// 创建一个简单的彩色图片作为占位符
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	
	// 填充背景色 (根据幻灯片编号使用不同颜色)
	colors := []struct{ r, g, b, a uint8 }{
		{255, 200, 200, 255}, // 浅红色
		{200, 255, 200, 255}, // 浅绿色
		{200, 200, 255, 255}, // 浅蓝色
		{255, 255, 200, 255}, // 浅黄色
		{255, 200, 255, 255}, // 浅紫色
	}
	
	color := colors[slideNumber%len(colors)]
	for y := 0; y < height; y++ {
		for x := 0; x < width; x++ {
			img.Set(x, y, color)
		}
	}

	return img, nil
}

// saveImage 保存图片到文件
func (c *PPTConverter) saveImage(img image.Image, filePath string) error {
	file, err := os.Create(filePath)
	if err != nil {
		return err
	}
	defer file.Close()

	switch c.outputFormat {
	case "PNG":
		return png.Encode(file, img)
	case "JPEG", "JPG":
		return jpeg.Encode(file, img, &jpeg.Options{Quality: 90})
	default:
		return png.Encode(file, img)
	}
}

// createTempFile 创建临时文件
func (c *PPTConverter) createTempFile(data []byte, filename string) (string, error) {
	// 确保临时目录存在
	if err := os.MkdirAll(c.tempDir, 0755); err != nil {
		return "", err
	}

	// 创建临时文件
	tempFile := filepath.Join(c.tempDir, fmt.Sprintf("temp_%d_%s", time.Now().UnixNano(), filename))
	
	file, err := os.Create(tempFile)
	if err != nil {
		return "", err
	}
	defer file.Close()

	_, err = io.Copy(file, bytes.NewReader(data))
	return tempFile, err
}

// generateSessionID 生成会话ID
func generateSessionID() string {
	return fmt.Sprintf("session_%d", time.Now().UnixNano())
}

// generateDownloadID 生成下载ID
func generateDownloadID() string {
	return fmt.Sprintf("download_%d", time.Now().UnixNano())
}
