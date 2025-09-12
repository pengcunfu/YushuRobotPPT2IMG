#!/usr/bin/env python3
"""
配置文件读取模块
支持从YAML文件读取配置，提供简单的get方法
"""

import yaml
import os
from typing import Any, Optional
from loguru import logger


class Config:
    """配置管理类"""

    _instance = None
    _config_data = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config_data is None:
            self._load_config()

    def _load_config(self):
        """加载配置文件"""
        config_file = "config.yaml"

        # 检查配置文件是否存在
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件 {config_file} 不存在")

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self._config_data = yaml.safe_load(f)
            logger.info(f"✅ 配置文件 {config_file} 加载成功")
        except Exception as e:
            logger.error(f"❌ 加载配置文件失败: {e}")
            raise

    def get(self, key: str) -> Any:
        """
        获取配置值
        
        Args:
            key: 配置键，支持点号分隔的嵌套键，如 "llm.douyin.api_key"
            
        Returns:
            Any: 配置值
            
        Raises:
            KeyError: 当配置键不存在时
        """
        if self._config_data is None:
            raise RuntimeError("配置未初始化")

        # 按点号分割键
        keys = key.split('.')
        value = self._config_data

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError) as e:
            raise KeyError(f"配置键 '{key}' 不存在") from e

    def get_with_default(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，如果不存在则返回默认值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            Any: 配置值或默认值
        """
        try:
            return self.get(key)
        except KeyError:
            return default

    def has_key(self, key: str) -> bool:
        """
        检查配置键是否存在
        
        Args:
            key: 配置键
            
        Returns:
            bool: 键是否存在
        """
        try:
            self.get(key)
            return True
        except KeyError:
            return False

    def reload(self):
        """重新加载配置文件"""
        self._config_data = None
        self._load_config()
        logger.info("🔄 配置文件已重新加载")


# 创建全局配置实例
config = Config()


# 便捷函数
def get_config(key: str) -> Any:
    """
    获取配置值的便捷函数
    
    Args:
        key: 配置键
        
    Returns:
        Any: 配置值
    """
    return config.get(key)


def get_config_with_default(key: str, default: Any = None) -> Any:
    """
    获取配置值的便捷函数（带默认值）
    
    Args:
        key: 配置键
        default: 默认值
        
    Returns:
        Any: 配置值或默认值
    """
    return config.get_with_default(key, default)


# 示例用法
if __name__ == "__main__":
    # 测试配置读取
    try:
        # 测试TTS配置
        access_token = get_config("douyin_tts.access_token")
        app_id = get_config("douyin_tts.app_id")
        print(f"TTS Access Token: {access_token}")
        print(f"TTS App ID: {app_id}")

        # 测试LLM配置
        api_key = get_config("douyin_llm.api_key")
        model = get_config("douyin_llm.model")
        print(f"LLM API Key: {api_key}")
        print(f"LLM Model: {model}")

        # 测试嵌套配置
        voice_type = get_config("douyin_tts.voice_type")
        print(f"Voice Type: {voice_type}")

    except KeyError as e:
        print(f"配置键不存在: {e}")
    except Exception as e:
        print(f"配置读取失败: {e}")
