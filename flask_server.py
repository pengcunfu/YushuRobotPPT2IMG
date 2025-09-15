#!/usr/bin/env python3
"""
Flask HTTP服务器 - PPT转图片服务
支持上传PPT文件并流式返回转换后的图片
"""

import os
import uuid
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Generator
from pathlib import Path

from flask import Flask, request, jsonify, Response, send_file, stream_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
from loguru import logger

from pptx_to_images import pptx_to_images, PPTConversionResult, ImageInfo


class PPTService:
    """PPT转换服务类"""
    
    def __init__(self, upload_dir: str = "uploads", output_dir: str = "outputs"):
        self.upload_dir = Path(upload_dir)
        self.output_dir = Path(output_dir)
        self.sessions: Dict[str, Dict] = {}  # 存储会话信息
        
        # 确保目录存在
        self.upload_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        # 启动清理线程
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """启动清理线程，定期清理过期文件"""
        def cleanup():
            while True:
                try:
                    self._cleanup_expired_files()
                    time.sleep(3600)  # 每小时清理一次
                except Exception as e:
                    logger.error(f"清理线程出错: {e}")
                    time.sleep(3600)
        
        cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        cleanup_thread.start()
        logger.info("文件清理线程已启动")
    
    def _cleanup_expired_files(self):
        """清理过期文件（超过24小时）"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        cleaned_count = 0
        
        # 清理上传文件
        for file_path in self.upload_dir.glob("*.pptx"):
            if datetime.fromtimestamp(file_path.stat().st_mtime) < cutoff_time:
                try:
                    file_path.unlink()
                    cleaned_count += 1
                except Exception as e:
                    logger.error(f"删除文件失败 {file_path}: {e}")
        
        # 清理输出目录
        for session_dir in self.output_dir.iterdir():
            if session_dir.is_dir() and datetime.fromtimestamp(session_dir.stat().st_mtime) < cutoff_time:
                try:
                    import shutil
                    shutil.rmtree(session_dir)
                    cleaned_count += 1
                except Exception as e:
                    logger.error(f"删除目录失败 {session_dir}: {e}")
        
        if cleaned_count > 0:
            logger.info(f"清理了 {cleaned_count} 个过期文件/目录")
    
    def upload_ppt(self, file) -> Dict:
        """上传PPT文件"""
        if not file or not file.filename:
            raise ValueError("没有选择文件")
        
        # 检查文件扩展名
        if not file.filename.lower().endswith(('.ppt', '.pptx')):
            raise ValueError("只支持PPT和PPTX文件")
        
        # 生成唯一文件名
        session_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        file_path = self.upload_dir / f"{session_id}_{filename}"
        
        # 保存文件
        file.save(str(file_path))
        
        # 记录会话信息
        self.sessions[session_id] = {
            'upload_time': datetime.now(),
            'filename': filename,
            'file_path': str(file_path),
            'status': 'uploaded',
            'conversion_result': None
        }
        
        logger.info(f"文件上传成功: {filename} -> {file_path}")
        
        return {
            'session_id': session_id,
            'filename': filename,
            'message': '文件上传成功'
        }
    
    def convert_ppt(self, session_id: str, width: int = 1920, height: int = 1080) -> Dict:
        """转换PPT为图片"""
        if session_id not in self.sessions:
            raise ValueError("会话不存在")
        
        session = self.sessions[session_id]
        if session['status'] != 'uploaded':
            raise ValueError("文件状态不正确")
        
        try:
            # 更新状态
            session['status'] = 'converting'
            
            # 创建输出目录
            output_dir = self.output_dir / session_id
            output_dir.mkdir(exist_ok=True)
            
            # 转换PPT
            logger.info(f"开始转换PPT: {session['file_path']}")
            result = pptx_to_images(
                pptx_path=session['file_path'],
                output_dir=str(output_dir),
                width=width,
                height=height
            )
            
            # 更新会话信息
            session['status'] = 'completed'
            session['conversion_result'] = result.to_dict()
            session['output_dir'] = str(output_dir)
            
            logger.info(f"PPT转换完成: {result.converted_slides}/{result.total_slides} 张图片")
            
            return {
                'session_id': session_id,
                'status': 'completed',
                'total_slides': result.total_slides,
                'converted_slides': result.converted_slides,
                'images': [
                    {
                        'slide_number': img.slide_number,
                        'filename': img.filename,
                        'download_url': f"/download/{session_id}/{img.filename}"
                    }
                    for img in result.image_info_list
                ]
            }
            
        except Exception as e:
            session['status'] = 'failed'
            session['error'] = str(e)
            logger.error(f"PPT转换失败: {e}")
            raise
    
    def get_session_status(self, session_id: str) -> Dict:
        """获取会话状态"""
        if session_id not in self.sessions:
            raise ValueError("会话不存在")
        
        session = self.sessions[session_id]
        result = {
            'session_id': session_id,
            'status': session['status'],
            'filename': session['filename'],
            'upload_time': session['upload_time'].isoformat()
        }
        
        if session['status'] == 'completed' and session['conversion_result']:
            result['conversion_result'] = session['conversion_result']
        elif session['status'] == 'failed':
            result['error'] = session.get('error', '未知错误')
        
        return result
    
    def get_image_stream(self, session_id: str, filename: str) -> Generator[bytes, None, None]:
        """流式返回图片数据"""
        if session_id not in self.sessions:
            raise ValueError("会话不存在")
        
        session = self.sessions[session_id]
        if session['status'] != 'completed':
            raise ValueError("转换未完成")
        
        image_path = self.output_dir / session_id / filename
        if not image_path.exists():
            raise ValueError("图片文件不存在")
        
        # 流式读取文件
        with open(image_path, 'rb') as f:
            while True:
                chunk = f.read(8192)  # 8KB chunks
                if not chunk:
                    break
                yield chunk
    
    def get_image_info(self, session_id: str, filename: str) -> Dict:
        """获取图片文件信息"""
        if session_id not in self.sessions:
            raise ValueError("会话不存在")
        
        session = self.sessions[session_id]
        if session['status'] != 'completed':
            raise ValueError("转换未完成")
        
        image_path = self.output_dir / session_id / filename
        if not image_path.exists():
            raise ValueError("图片文件不存在")
        
        stat = image_path.stat()
        return {
            'filename': filename,
            'size': stat.st_size,
            'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat()
        }


# 创建Flask应用
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# 添加CORS支持
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# 创建PPT服务实例
ppt_service = PPTService()


@app.route('/')
def index():
    """首页"""
    return jsonify({
        'service': 'PPT转图片服务',
        'version': '1.0.0',
        'endpoints': {
            'upload': 'POST /upload - 上传PPT文件',
            'convert': 'POST /convert/<session_id> - 转换PPT为图片',
            'status': 'GET /status/<session_id> - 获取转换状态',
            'download': 'GET /download/<session_id>/<filename> - 下载图片',
            'stream': 'GET /stream/<session_id>/<filename> - 流式下载图片',
            'info': 'GET /info/<session_id>/<filename> - 获取图片信息'
        }
    })


@app.route('/upload', methods=['POST'])
def upload_ppt():
    """上传PPT文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有选择文件'}), 400
        
        file = request.files['file']
        result = ppt_service.upload_ppt(file)
        
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"上传文件失败: {e}")
        return jsonify({'error': '上传失败'}), 500


@app.route('/convert/<session_id>', methods=['POST'])
def convert_ppt(session_id: str):
    """转换PPT为图片"""
    try:
        # 获取参数
        data = request.get_json() or {}
        width = data.get('width', 1920)
        height = data.get('height', 1080)
        
        result = ppt_service.convert_ppt(session_id, width, height)
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"转换PPT失败: {e}")
        return jsonify({'error': '转换失败'}), 500


@app.route('/status/<session_id>')
def get_status(session_id: str):
    """获取转换状态"""
    try:
        result = ppt_service.get_session_status(session_id)
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        return jsonify({'error': '获取状态失败'}), 500


@app.route('/download/<session_id>/<filename>')
def download_image(session_id: str, filename: str):
    """下载图片文件"""
    try:
        if session_id not in ppt_service.sessions:
            return jsonify({'error': '会话不存在'}), 404
        
        session = ppt_service.sessions[session_id]
        if session['status'] != 'completed':
            return jsonify({'error': '转换未完成'}), 400
        
        image_path = ppt_service.output_dir / session_id / filename
        if not image_path.exists():
            return jsonify({'error': '图片文件不存在'}), 404
        
        return send_file(
            str(image_path),
            as_attachment=True,
            download_name=filename,
            mimetype='image/png'
        )
        
    except Exception as e:
        logger.error(f"下载图片失败: {e}")
        return jsonify({'error': '下载失败'}), 500


@app.route('/stream/<session_id>/<filename>')
def stream_image(session_id: str, filename: str):
    """流式返回图片数据"""
    try:
        def generate():
            for chunk in ppt_service.get_image_stream(session_id, filename):
                yield chunk
        
        return Response(
            generate(),
            mimetype='image/png',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Cache-Control': 'no-cache'
            }
        )
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"流式下载失败: {e}")
        return jsonify({'error': '流式下载失败'}), 500


@app.route('/info/<session_id>/<filename>')
def get_image_info(session_id: str, filename: str):
    """获取图片信息"""
    try:
        result = ppt_service.get_image_info(session_id, filename)
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"获取图片信息失败: {e}")
        return jsonify({'error': '获取图片信息失败'}), 500


@app.errorhandler(413)
def too_large(e):
    """文件过大错误处理"""
    return jsonify({'error': '文件过大，最大支持100MB'}), 413


@app.errorhandler(404)
def not_found(e):
    """404错误处理"""
    return jsonify({'error': '接口不存在'}), 404


@app.errorhandler(500)
def internal_error(e):
    """500错误处理"""
    return jsonify({'error': '服务器内部错误'}), 500


if __name__ == '__main__':
    logger.info("启动PPT转图片Flask服务...")
    logger.info("服务地址: http://localhost:5000")
    logger.info("上传目录: uploads/")
    logger.info("输出目录: outputs/")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
