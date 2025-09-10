import os
import pythoncom
import win32com.client
from PIL import Image

def pptx_to_images(pptx_path:str, output_dir:str, width=1920, height=1080):
    """
    使用PowerPoint COM接口直接将PPT导出为图片
    
    Args:
        pptx_path: PPT文件路径，将被转换为绝对路径
        output_dir: 输出图片目录，将被转换为绝对路径
        width: 导出图片宽度（像素）
        height: 导出图片高度（像素），设为0时根据宽度按比例自动计算
    """
    # 转换为绝对路径
    pptx_path = os.path.abspath(pptx_path)
    output_dir = os.path.abspath(output_dir)
    print(f"开始将PPT转换为图片...")
    print(f"PPT文件: {pptx_path}")
    print(f"输出目录: {output_dir}")
    
    # 验证PPT文件路径
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(f"PPT文件不存在: {pptx_path}")
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 初始化COM
    pythoncom.CoInitialize()
    ppt_app = win32com.client.Dispatch("PowerPoint.Application")
    
    image_paths = []
    
    presentation = None
    try:
        # 打开PPT文件
        print(f"打开PPT文件...")
        presentation = ppt_app.Presentations.Open(pptx_path, WithWindow=False)
        
        # 获取PPT的原始尺寸和宽高比
        slide_width = presentation.PageSetup.SlideWidth
        slide_height = presentation.PageSetup.SlideHeight
        aspect_ratio = slide_height / slide_width
        print(f"PPT原始尺寸: {slide_width} x {slide_height}, 宽高比: {aspect_ratio:.3f}")
        
        # 如果高度为0，根据宽度和原始比例计算
        if height == 0:
            height = int(width * aspect_ratio)
            print(f"根据宽度自动计算高度: {height}px")
        
        print(f"将导出为图片尺寸: {width}x{height}px")
        print(f"幻灯片总数: {presentation.Slides.Count}")
        
        # 遍历所有幻灯片并导出
        for i in range(1, presentation.Slides.Count + 1):
            img_path = os.path.join(output_dir, f"slide_{i}.png")
            print(f"导出幻灯片 {i}/{presentation.Slides.Count} 到 {img_path}")
            
            slide = presentation.Slides(i)
            
            try:
                # 尝试直接以指定尺寸导出
                slide.Export(img_path, "PNG", width, height)
            except Exception as e:
                print(f"警告: 使用指定尺寸导出失败 ({str(e)})，改用默认尺寸导出后再调整")
                
                # 使用默认尺寸导出
                temp_path = os.path.join(output_dir, f"temp_{i}.png")
                slide.Export(temp_path, "PNG")
                
                # 使用PIL调整尺寸
                try:
                    with Image.open(temp_path) as img:
                        img_resized = img.resize((width, height), Image.LANCZOS)
                        img_resized.save(img_path)
                    os.remove(temp_path)
                except Exception as resize_error:
                    print(f"调整大小失败: {str(resize_error)}")
                    if os.path.exists(temp_path):
                        # 如果调整大小失败，至少保留原始导出的图片
                        os.rename(temp_path, img_path)
            
            image_paths.append(img_path)
        
        print("所有幻灯片导出完成!")
        
    except Exception as e:
        print(f"错误: {str(e)}")
        raise
    finally:
        # 确保关闭演示文稿
        if presentation is not None:
            try:
                presentation.Close()
                print("演示文稿已关闭")
            except Exception as e:
                print(f"关闭演示文稿时出错: {str(e)}")
        
        # 退出PowerPoint并释放COM
        try:
            ppt_app.Quit()
            print("PowerPoint应用程序已退出")
        except Exception as e:
            print(f"退出PowerPoint时出错: {str(e)}")
        
        try:
            pythoncom.CoUninitialize()
            print("COM组件已释放")
        except Exception as e:
            print(f"释放COM组件时出错: {str(e)}")
    
    return image_paths

# 使用示例
if __name__ == "__main__":

    # 直接调用转换函数
    image_paths = pptx_to_images(
        pptx_path="1.pptx",
        output_dir="output_images",
        width=1920,    # 宽度1920像素
        height=1080    # 高度1080像素，设为0可按原始比例自动计算
    )
    
    print(f"成功导出 {len(image_paths)} 张图片到 {output_dir}")
    for path in image_paths:
        print(f" - {path}")