"""
WebSocket消息模型定义
用于封装请求和响应数据结构
"""
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import uuid


@dataclass
class PPTProcessingRequest:
    """PPT处理请求"""
    ppt_url: str
    ppt_name: str
    width: int = 1920
    height: int = 1080
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PPTProcessingRequest':
        """从字典创建实例"""
        return cls(**data)


@dataclass
class TaskJoinRequest:
    """加入任务请求"""
    uuid: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskJoinRequest':
        """从字典创建实例"""
        return cls(**data)


@dataclass
class TaskStatusRequest:
    """获取任务状态请求"""
    uuid: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskStatusRequest':
        """从字典创建实例"""
        return cls(**data)


@dataclass
class BaseResponse:
    """基础响应类"""
    message: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class ConnectedResponse(BaseResponse):
    """连接响应"""
    pass


@dataclass
class TaskCreatedResponse(BaseResponse):
    """任务创建响应"""
    uuid: str
    ppt_name: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class ProgressUpdateResponse(BaseResponse):
    """进度更新响应"""
    uuid: str
    status: str
    progress: int
    total_slides: int
    processed_slides: int
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class TaskCompleteResponse(BaseResponse):
    """任务完成响应"""
    uuid: str
    ppt_name: str
    status: str
    progress: int
    total_slides: int
    processed_slides: int
    download_urls: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class TaskErrorResponse(BaseResponse):
    """任务错误响应"""
    uuid: str
    status: str
    error: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class TaskStatusResponse(BaseResponse):
    """任务状态响应"""
    uuid: str
    ppt_name: str
    status: str
    progress: int
    total_slides: int
    processed_slides: int
    download_urls: List[str]
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class ErrorResponse(BaseResponse):
    """错误响应"""
    pass


@dataclass
class TaskData:
    """任务数据模型"""
    uuid: str
    ppt_url: str
    ppt_name: str
    width: int
    height: int
    bucket_name: str
    status: str
    created_at: float
    progress: int
    total_slides: int
    processed_slides: int
    download_urls: List[str]
    error: Optional[str] = None
    queued_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    @classmethod
    def create_new(cls, ppt_url: str, ppt_name: str, width: int = 1920, 
                   height: int = 1080, bucket_name: str = "images") -> 'TaskData':
        """创建新任务"""
        import time
        return cls(
            uuid=str(uuid.uuid4()),
            ppt_url=ppt_url,
            ppt_name=ppt_name,
            width=width,
            height=height,
            bucket_name=bucket_name,
            status='created',
            created_at=time.time(),
            progress=0,
            total_slides=0,
            processed_slides=0,
            download_urls=[]
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskData':
        """从字典创建实例"""
        return cls(**data)


@dataclass
class ConnectionInfo:
    """连接信息模型"""
    room: str
    uuid: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConnectionInfo':
        """从字典创建实例"""
        return cls(**data)


@dataclass
class ServerStats:
    """服务器统计信息"""
    total_tasks: int
    active_tasks: int
    queued_tasks: int
    completed_tasks: int
    failed_tasks: int
    active_connections: int
    max_concurrent_tasks: int
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
