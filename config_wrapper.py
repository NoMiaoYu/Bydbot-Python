"""
配置包装器
为新配置结构提供统一的访问接口，支持向后兼容
"""
import json
import os
from typing import Dict, Any, Optional


class ConfigWrapper:
    """配置包装器，支持新旧配置格式"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self._raw_config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._raw_config = json.load(f)
        except FileNotFoundError:
            print(f"配置文件不存在: {self.config_path}")
            self._raw_config = {}
        except json.JSONDecodeError as e:
            print(f"配置文件解析失败: {e}")
            self._raw_config = {}

    def reload(self):
        """重新加载配置"""
        self._load_config()

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持新旧配置格式
        支持的点分隔路径：新格式 "napcat.http_url" 或 旧格式 "napcat_http_url"
        """
        # 尝试新格式（点分隔路径）
        if '.' in key:
            keys = key.split('.')
            value = self._raw_config
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    # 新格式未找到，尝试旧格式
                    return self._get_old_style(key, default)
            return value if value is not None else default

        # 尝试旧格式（扁平结构）
        if key in self._raw_config:
            return self._raw_config[key]

        # 尝试从新格式结构中查找
        return self._get_old_style(key, default)

    def _get_old_style(self, key: str, default: Any = None) -> Any:
        """从旧格式配置中获取值"""
        # NapCat 配置
        if key == 'napcat_http_url':
            return self._raw_config.get('napcat', {}).get('http_url', default)
        if key == 'napcat_token':
            return self._raw_config.get('napcat', {}).get('token', default)
        if key == 'ws_port':
            return self._raw_config.get('napcat', {}).get('ws_port', default)

        # 基础配置
        if key == 'log_file':
            return self._raw_config.get('basic', {}).get('log_file', default)
        if key == 'enable_command_listener':
            return self._raw_config.get('basic', {}).get('enable_command_listener', default)
        if key == 'test_command':
            return self._raw_config.get('basic', {}).get('test_command', default)
        if key == 'test_groups_only':
            return self._raw_config.get('basic', {}).get('test_groups_only', default)
        if key == 'owner_id':
            return self._raw_config.get('basic', {}).get('owner_id', default)

        # 地震配置
        if key == 'sources':
            return self._raw_config.get('earthquake', {}).get('sources', default)
        if key == 'source_rules':
            return self._raw_config.get('earthquake', {}).get('source_rules', default)
        if key == 'draw_sources':
            return self._raw_config.get('earthquake', {}).get('drawing', {}).get('sources', default)
        if key == 'draw_timeout':
            return self._raw_config.get('earthquake', {}).get('drawing', {}).get('timeout', default)

        # 天气API配置
        if key == 'weather_api_enabled':
            return self._raw_config.get('qweather', {}).get('enabled', default)
        if key == 'weather_api_daily_limit':
            return self._raw_config.get('qweather', {}).get('daily_limit', default)

        # UAPI配置
        if key == 'uapi':
            return self._raw_config.get('uapi', default)
        if key == 'uapi_rate_limit':
            return self._raw_config.get('uapi_rate_limit', default)

        # 消息模板
        if key == 'message_templates':
            return self._raw_config.get('earthquake_templates', default)
        if key == 'weather_templates':
            return self._raw_config.get('weather_templates', default)

        # 帮助配置
        if key == 'help':
            return self._raw_config.get('help', default)

        # 字段规则
        if key == 'field_rules':
            return self._raw_config.get('field_rules', default)

        return default

    def __getitem__(self, key: str) -> Any:
        """支持字典式访问"""
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        """支持 in 操作符"""
        return self.get(key) is not None

    def keys(self):
        """返回所有配置键"""
        # 合并新旧格式的键
        keys = set(self._raw_config.keys())
        
        # 添加新格式的点分隔键
        def add_nested_keys(prefix, obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    full_key = f"{prefix}.{k}" if prefix else k
                    keys.add(full_key)
                    add_nested_keys(full_key, v)
        
        add_nested_keys('', self._raw_config)
        return keys


# 全局配置实例
_config_wrapper: Optional[ConfigWrapper] = None


def get_config() -> ConfigWrapper:
    """获取全局配置实例"""
    global _config_wrapper
    if _config_wrapper is None:
        _config_wrapper = ConfigWrapper()
    return _config_wrapper


def load_config(config_path: str = "config.json") -> ConfigWrapper:
    """加载配置文件"""
    global _config_wrapper
    _config_wrapper = ConfigWrapper(config_path)
    return _config_wrapper