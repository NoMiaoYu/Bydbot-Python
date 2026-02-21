"""
配置适配器
将新的配置结构转换为旧格式，保持向后兼容
"""
import json
import os
from typing import Dict, Any, Optional


class ConfigAdapter:
    """配置适配器，支持新旧配置格式"""

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
        
        支持的点分隔路径：
        - 新格式: "napcat.http_url"
        - 旧格式: "napcat_http_url"
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
                    return self._raw_config.get(key, default)
            return value if value is not None else default

        # 尝试旧格式（扁平结构）
        if key in self._raw_config:
            return self._raw_config[key]

        # 尝试从新格式结构中查找
        # napcat 配置
        napcat_mapping = {
            'napcat_http_url': 'napcat.http_url',
            'napcat_token': 'napcat.token',
            'ws_port': 'napcat.ws_port',
        }
        if key in napcat_mapping:
            return self._get_nested(napcat_mapping[key], default)

        # basic 配置
        basic_mapping = {
            'log_file': 'basic.log_file',
            'enable_command_listener': 'basic.enable_command_listener',
            'test_command': 'basic.test_command',
            'test_groups_only': 'basic.test_groups_only',
            'owner_id': 'basic.owner_id',
        }
        if key in basic_mapping:
            return self._get_nested(basic_mapping[key], default)

        # earthquake 配置
        earthquake_mapping = {
            'sources': 'earthquake.sources',
            'source_rules': 'earthquake.source_rules',
            'draw_sources': 'earthquake.drawing.sources',
            'draw_timeout': 'earthquake.drawing.timeout',
        }
        if key in earthquake_mapping:
            return self._get_nested(earthquake_mapping[key], default)

        # qweather 配置
        qweather_mapping = {
            'weather_api_enabled': 'qweather.enabled',
            'weather_api_daily_limit': 'qweather.daily_limit',
        }
        if key in qweather_mapping:
            return self._get_nested(qweather_mapping[key], default)

        # 默认返回
        return default

    def _get_nested(self, path: str, default: Any = None) -> Any:
        """获取嵌套配置值"""
        keys = path.split('.')
        value = self._raw_config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_napcat_config(self) -> Dict[str, Any]:
        """获取NapCat配置"""
        return {
            'http_url': self.get('napcat.http_url', 'http://127.0.0.1:3000'),
            'token': self.get('napcat.token', ''),
            'ws_port': self.get('napcat.ws_port', 9998),
        }

    def get_earthquake_config(self) -> Dict[str, Any]:
        """获取地震配置"""
        return {
            'sources': self.get('earthquake.sources', {}),
            'source_rules': self.get('earthquake.source_rules', {}),
            'time_window_hours': self.get('earthquake.time_window.max_hours', 1),
            'drawing': {
                'sources': self.get('earthquake.drawing.sources', []),
                'timeout': self.get('earthquake.drawing.timeout', 20),
                'output_dir': self.get('earthquake.drawing.output_dir', 'pictures'),
            },
            'heartbeat_log_interval': self.get('earthquake.heartbeat.log_interval', 5),
            'cleanup_interval': self.get('earthquake.cleanup.interval', 86400),
            'retention_days': self.get('earthquake.cleanup.retention_days', 14),
        }

    def get_qweather_config(self) -> Dict[str, Any]:
        """获取和风天气配置"""
        return {
            'api_host': self.get('qweather.api_host', ''),
            'api_key': self.get('qweather.api_key', ''),
            'jwt_token': self.get('qweather.jwt_token', ''),
            'use_jwt': self.get('qweather.use_jwt', False),
            'cache_enabled': self.get('qweather.cache_enabled', True),
            'cache_ttl': self.get('qweather.cache_ttl', 600),
            'daily_limit': self.get('qweather.daily_limit', 1500),
            'enabled': self.get('qweather.enabled', True),
        }

    def get_uapi_config(self) -> Dict[str, Any]:
        """获取UAPI配置"""
        return {
            'base_url': self.get('uapi.base_url', 'https://uapis.cn'),
            'api_key': self.get('uapi.api_key', ''),
            'timeout': self.get('uapi.timeout', 30),
            'cache_enabled': self.get('uapi.cache_enabled', True),
            'cache_ttl': self.get('uapi.cache_ttl', 600),
        }

    def get_uapi_rate_limit(self) -> Dict[str, Any]:
        """获取UAPI频率限制配置"""
        return {
            'max_calls_per_minute': self.get('uapi_rate_limit.max_calls_per_minute', 10),
            'enable_per_user_limits': self.get('uapi_rate_limit.enable_per_user_limits', True),
        }

    def get_weather_commands(self) -> Dict[str, str]:
        """获取天气命令配置"""
        return self.get('weather_commands', {})

    def get_weather_templates(self) -> Dict[str, str]:
        """获取天气模板配置"""
        return self.get('weather_templates', {})

    def get_earthquake_templates(self) -> Dict[str, str]:
        """获取地震模板配置"""
        return self.get('earthquake_templates', {})

    def get_help_config(self) -> Dict[str, Any]:
        """获取帮助配置"""
        return {
            'image_enabled': self.get('help.image_enabled', True),
            'image_paths': self.get('help.image_paths', []),
            'text_enabled': self.get('help.text_enabled', False),
        }

    def get_field_rules(self) -> Dict[str, Any]:
        """获取字段处理规则"""
        return self.get('field_rules', {})

    def get_groups(self) -> Dict[str, Dict[str, Any]]:
        """获取群组配置"""
        return self.get('groups', {})

    def __getitem__(self, key: str) -> Any:
        """支持字典式访问"""
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        """支持 in 操作符"""
        return self.get(key) is not None


# 全局配置实例
_config_adapter: Optional[ConfigAdapter] = None


def get_config() -> ConfigAdapter:
    """获取全局配置实例"""
    global _config_adapter
    if _config_adapter is None:
        _config_adapter = ConfigAdapter()
    return _config_adapter


def load_config(config_path: str = "config.json") -> ConfigAdapter:
    """加载配置文件"""
    global _config_adapter
    _config_adapter = ConfigAdapter(config_path)
    return _config_adapter