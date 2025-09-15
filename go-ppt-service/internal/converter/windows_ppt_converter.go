//go:build windows
// +build windows

package converter

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// WindowsPPTConverter Windows平台PPT转换器
type WindowsPPTConverter struct {
	*PPTConverter
}

// NewWindowsPPTConverter 创建Windows PPT转换器
func NewWindowsPPTConverter(outputDir, tempDir string, width, height int, outputFormat string, logger *logrus.Logger) *WindowsPPTConverter {
	baseConverter := NewPPTConverter(outputDir, tempDir, width, height, outputFormat, logger)
	return &WindowsPPTConverter{
		PPTConverter: baseConverter,
	}
}

// ConvertPPT 使用PowerShell和Office COM接口转换PPT
func (c *WindowsPPTConverter) ConvertPPT(pptData []byte, filename string, progressCallback ProgressCallback) (*ConversionResult, error) {
	c.logger.Info("开始转换PPT文件 (Windows): ", filename)
	
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

	// 使用PowerShell脚本转换PPT
	outputPath := filepath.Join(c.outputDir, generateSessionID())
	if err := os.MkdirAll(outputPath, 0755); err != nil {
		return nil, fmt.Errorf("创建输出目录失败: %v", err)
	}

	// 创建PowerShell脚本
	psScript := c.createPowerShellScript(tempFile, outputPath, c.width, c.height)
	scriptFile := filepath.Join(c.tempDir, fmt.Sprintf("convert_%d.ps1", time.Now().UnixNano()))
	
	if err := os.WriteFile(scriptFile, []byte(psScript), 0644); err != nil {
		return nil, fmt.Errorf("创建PowerShell脚本失败: %v", err)
	}
	defer os.Remove(scriptFile)

	// 发送解析完成状态
	if progressCallback != nil {
		progressCallback(ConversionStatus{
			Status:  "processing",
			Progress: 20,
			Message: "正在使用PowerPoint转换PPT...",
		})
	}

	// 执行PowerShell脚本
	cmd := exec.Command("powershell", "-ExecutionPolicy", "Bypass", "-File", scriptFile)
	output, err := cmd.CombinedOutput()
	if err != nil {
		c.logger.Errorf("PowerShell脚本执行失败: %v", err)
		c.logger.Errorf("输出: %s", string(output))
		return nil, fmt.Errorf("PowerShell脚本执行失败: %v", err)
	}

	c.logger.Debugf("PowerShell脚本输出: %s", string(output))

	// 扫描输出目录获取转换结果
	images, err := c.scanOutputDirectory(outputPath)
	if err != nil {
		return nil, fmt.Errorf("扫描输出目录失败: %v", err)
	}

	totalSlides := len(images)
	convertedCount := len(images)

	// 发送完成状态
	if progressCallback != nil {
		progressCallback(ConversionStatus{
			Status:          "completed",
			Progress:        100,
			Message:         fmt.Sprintf("转换完成，成功转换 %d 张幻灯片", convertedCount),
			TotalSlides:     totalSlides,
			ProcessedSlides: convertedCount,
		})
	}

	result := &ConversionResult{
		Success:         convertedCount > 0,
		Message:         fmt.Sprintf("成功转换 %d 张幻灯片", convertedCount),
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

// createPowerShellScript 创建PowerShell转换脚本
func (c *WindowsPPTConverter) createPowerShellScript(inputFile, outputDir string, width, height int) string {
	script := fmt.Sprintf(`
# PowerPoint转换脚本
try {
    # 创建PowerPoint应用程序对象
    $ppt = New-Object -ComObject PowerPoint.Application
    $ppt.Visible = $false
    
    # 打开演示文稿
    $presentation = $ppt.Presentations.Open("%s", $false, $false, $false)
    
    Write-Host "演示文稿包含 $($presentation.Slides.Count) 张幻灯片"
    
    # 遍历每张幻灯片
    for ($i = 1; $i -le $presentation.Slides.Count; $i++) {
        $slide = $presentation.Slides($i)
        $outputFile = "%s\\slide_%03d.png"
        $outputFile = $outputFile -f $i
        
        Write-Host "正在导出第 $i 张幻灯片到: $outputFile"
        
        # 导出幻灯片为PNG
        $slide.Export($outputFile, "PNG", %d, %d)
        
        Write-Host "第 $i 张幻灯片导出完成"
    }
    
    # 关闭演示文稿
    $presentation.Close()
    
    # 退出PowerPoint
    $ppt.Quit()
    
    # 释放COM对象
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($presentation) | Out-Null
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($ppt) | Out-Null
    
    Write-Host "转换完成"
}
catch {
    Write-Error "转换过程中发生错误: $($_.Exception.Message)"
    exit 1
}
finally {
    # 确保PowerPoint进程被关闭
    Get-Process -Name "POWERPNT" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
`, 
		strings.ReplaceAll(inputFile, "\\", "\\\\"),
		strings.ReplaceAll(outputDir, "\\", "\\\\"),
		width,
		height,
	)
	
	return script
}

// scanOutputDirectory 扫描输出目录获取图片文件
func (c *WindowsPPTConverter) scanOutputDirectory(outputDir string) ([]ImageInfo, error) {
	var images []ImageInfo
	
	// 扫描PNG文件
	pattern := filepath.Join(outputDir, "slide_*.png")
	matches, err := filepath.Glob(pattern)
	if err != nil {
		return nil, err
	}
	
	for _, match := range matches {
		filename := filepath.Base(match)
		
		// 从文件名提取幻灯片编号
		slideNumber := c.extractSlideNumber(filename)
		
		// 获取文件信息
		fileInfo, err := os.Stat(match)
		if err != nil {
			c.logger.Warnf("获取文件信息失败: %s", match)
			continue
		}
		
		imageInfo := ImageInfo{
			SlideNumber: slideNumber,
			Filename:    filename,
			FilePath:    match,
			FileSize:    fileInfo.Size(),
			DownloadID:  generateDownloadID(),
		}
		
		images = append(images, imageInfo)
	}
	
	return images, nil
}

// extractSlideNumber 从文件名提取幻灯片编号
func (c *WindowsPPTConverter) extractSlideNumber(filename string) int {
	// 文件名格式: slide_001.png
	parts := strings.Split(filename, "_")
	if len(parts) >= 2 {
		slidePart := strings.Split(parts[1], ".")[0]
		if num, err := strconv.Atoi(slidePart); err == nil {
			return num
		}
	}
	return 1
}
