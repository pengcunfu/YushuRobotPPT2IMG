import os
import uuid
import pythoncom
import win32com.client
from PIL import Image
from dataclasses import dataclass, asdict
from typing import List, Dict, Any


@dataclass
class ImageInfo:
    """图片信息模型"""
    slide_number: int
    filename: str
    filepath: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageInfo':
        """从字典创建实例"""
        return cls(**data)


@dataclass
class PPTConversionResult:
    """PPT转换结果模型"""
    success: bool
    total_slides: int
    converted_slides: int
    image_info_list: List[ImageInfo]
    pptx_path: str
    output_dir: str
    width: int
    height: int
    error: str = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result_dict = asdict(self)
        # 将ImageInfo对象转换为字典
        result_dict['image_info_list'] = [info.to_dict() for info in self.image_info_list]
        return result_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PPTConversionResult':
        """从字典创建实例"""
        # 将字典列表转换为ImageInfo对象列表
        image_info_list = [ImageInfo.from_dict(info_dict) for info_dict in data['image_info_list']]
        data['image_info_list'] = image_info_list
        return cls(**data)


def pptx_to_images(pptx_path: str, output_dir: str, width=1920, height=1080) -> PPTConversionResult:
    """
    使用PowerPoint COM接口直接将PPT导出为图片
    
    Args:
        pptx_path: PPT文件路径，将被转换为绝对路径
        output_dir: 输出图片目录，将被转换为绝对路径
        width: 导出图片宽度（像素）
        height: 导出图片高度（像素），设为0时根据宽度按比例自动计算
        
    Returns:
        PPTConversionResult: 转换结果对象，包含：
            - success: 是否成功
            - total_slides: 总幻灯片数
            - converted_slides: 成功转换的幻灯片数
            - image_info_list: 图片信息列表
            - error: 错误信息（如果有）
    """
    # 转换为绝对路径
    pptx_path = os.path.abspath(pptx_path)
    output_dir = os.path.abspath(output_dir)
    print(f"开始将PPT转换为图片...")
    print(f"PPT文件: {pptx_path}")
    print(f"输出目录: {output_dir}")

    # 验证PPT文件路径
    if not os.path.exists(pptx_path):
        return PPTConversionResult(
            success=False,
            total_slides=0,
            converted_slides=0,
            image_info_list=[],
            pptx_path=pptx_path,
            output_dir=output_dir,
            width=width,
            height=height,
            error=f"PPT文件不存在: {pptx_path}"
        )

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 初始化COM
    pythoncom.CoInitialize()
    ppt_app = win32com.client.Dispatch("PowerPoint.Application")

    image_info_list = []
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
            # 生成UUID文件名
            file_uuid = str(uuid.uuid4())
            filename = f"{file_uuid}.png"
            img_path = os.path.join(output_dir, filename)

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

            # 添加到图片信息列表
            image_info = ImageInfo(
                slide_number=i,
                filename=filename,
                filepath=img_path
            )
            image_info_list.append(image_info)

        print("所有幻灯片导出完成!")
        
        # 返回成功结果
        return PPTConversionResult(
            success=True,
            total_slides=presentation.Slides.Count,
            converted_slides=len(image_info_list),
            image_info_list=image_info_list,
            pptx_path=pptx_path,
            output_dir=output_dir,
            width=width,
            height=height
        )

    except Exception as e:
        print(f"错误: {str(e)}")
        # 返回失败结果
        return PPTConversionResult(
            success=False,
            total_slides=presentation.Slides.Count if presentation else 0,
            converted_slides=len(image_info_list),
            image_info_list=image_info_list,
            pptx_path=pptx_path,
            output_dir=output_dir,
            width=width,
            height=height,
            error=str(e)
        )
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


# 使用示例
if __name__ == "__main__":
    output_dir = "out/" + str(uuid.uuid4())
    # 直接调用转换函数
    result = pptx_to_images(
        pptx_path="examples/1.pptx",
        output_dir=output_dir,
        width=1920,  # 宽度1920像素
        height=1080  # 高度1080像素，设为0可按原始比例自动计算
    )

    if result.success:
        print(f"✅ 成功导出 {result.converted_slides}/{result.total_slides} 张图片到 {result.output_dir}")
        print("按顺序排列的图片信息:")
        for info in result.image_info_list:
            print(f"  幻灯片 {info.slide_number}: {info.filename} -> {info.filepath}")
    else:
        print(f"❌ 转换失败: {result.error}")
        print(f"已转换: {result.converted_slides}/{result.total_slides} 张图片")
