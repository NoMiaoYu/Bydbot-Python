"""
Bydbot - 命令别名处理器（新版）
支持多别名映射，每个原命令可以有多个别名
"""

import json
import logging
from typing import Dict, Any, Optional, List, Set
import os

# 全局别名映射：{别名: 原命令}
_alias_reverse_map: Dict[str, str] = {}
# 原命令到别名的映射：{原命令: [别名列表]}
_command_alias_map: Dict[str, List[str]] = {}
_alias_enabled: bool = True

def init_alias_system(config: Dict[str, Any]) -> None:
    """
    初始化别名系统
    :param config: 配置字典
    """
    global _alias_reverse_map, _command_alias_map, _alias_enabled
    
    alias_config = config.get('aliases', {})
    _alias_enabled = alias_config.get('enabled', True)
    
    if _alias_enabled:
        commands_config = alias_config.get('commands', {})
        
        # 构建反向映射（别名 -> 原命令）
        _alias_reverse_map.clear()
        _command_alias_map.clear()
        
        duplicate_aliases = []
        
        for original_command, aliases in commands_config.items():
            if isinstance(aliases, list):
                _command_alias_map[original_command] = aliases.copy()
                for alias in aliases:
                    if alias in _alias_reverse_map:
                        duplicate_aliases.append(alias)
                        logging.warning(f"重复的别名 '{alias}'，原映射: '{_alias_reverse_map[alias]}'，新映射: '{original_command}'")
                    else:
                        _alias_reverse_map[alias] = original_command
            else:
                logging.warning(f"命令 '{original_command}' 的别名配置格式错误，应为列表")
        
        if duplicate_aliases:
            logging.error(f"发现 {len(duplicate_aliases)} 个重复别名: {duplicate_aliases}")
        
        logging.info(f"别名系统已启用，加载了 {len(_alias_reverse_map)} 个别名，映射到 {len(_command_alias_map)} 个原命令")
    else:
        _alias_reverse_map.clear()
        _command_alias_map.clear()
        logging.info("别名系统已禁用")

def is_alias_enabled() -> bool:
    """检查别名系统是否启用"""
    return _alias_enabled

def resolve_command(command_name: str) -> str:
    """
    解析命令名，如果是别名则返回原命令，否则返回原命令名
    :param command_name: 可能是别名的命令名
    :return: 原始命令名
    """
    if not _alias_enabled:
        return command_name
    
    # 先检查是否为别名
    if command_name in _alias_reverse_map:
        return _alias_reverse_map[command_name]
    
    # 再检查是否为原命令（原命令也可以直接使用）
    if command_name in _command_alias_map:
        return command_name
    
    # 如果都不是，返回原名
    return command_name

def is_alias(command_name: str) -> bool:
    """
    检查给定的名称是否为别名
    :param command_name: 命令名称
    :return: 是否为别名
    """
    if not _alias_enabled:
        return False
    
    return command_name in _alias_reverse_map

def is_valid_command(command_name: str) -> bool:
    """
    检查给定的名称是否为有效的命令（原命令或别名）
    :param command_name: 命令名称
    :return: 是否为有效命令
    """
    if not _alias_enabled:
        return False
    
    return command_name in _alias_reverse_map or command_name in _command_alias_map

def get_original_command(alias: str) -> Optional[str]:
    """
    获取别名对应的真实命令
    :param alias: 别名
    :return: 原始命令名，如果不存在则返回None
    """
    if not _alias_enabled:
        return None
    
    return _alias_reverse_map.get(alias)

def get_aliases_for_command(original_command: str) -> List[str]:
    """
    获取指定命令的所有别名
    :param original_command: 原始命令名
    :return: 该命令的所有别名列表
    """
    if not _alias_enabled:
        return []
    
    return _command_alias_map.get(original_command, []).copy()

def get_all_aliases() -> Dict[str, str]:
    """
    获取所有别名到原命令的映射
    :return: {别名: 原命令} 的字典
    """
    if not _alias_enabled:
        return {}
    
    return _alias_reverse_map.copy()

def get_all_commands_with_aliases() -> Dict[str, List[str]]:
    """
    获取所有原命令及其别名
    :return: {原命令: [别名列表]} 的字典
    """
    if not _alias_enabled:
        return {}
    
    return {cmd: aliases.copy() for cmd, aliases in _command_alias_map.items()}

def add_alias(alias: str, original_command: str, config_path: str = "config.json") -> bool:
    """
    添加新的别名
    :param alias: 别名
    :param original_command: 原始命令
    :param config_path: 配置文件路径
    :return: 是否添加成功
    """
    global _alias_reverse_map, _command_alias_map
    
    if not _alias_enabled:
        logging.warning("别名系统已禁用，无法添加别名")
        return False
    
    # 检查别名是否已存在
    if alias in _alias_reverse_map:
        logging.warning(f"别名 '{alias}' 已存在，指向 '{_alias_reverse_map[alias]}'")
        return False
    
    # 检查原始命令是否存在
    if original_command not in _command_alias_map:
        logging.warning(f"原始命令 '{original_command}' 不存在或不受支持")
        return False
    
    try:
        # 更新内存中的映射
        _alias_reverse_map[alias] = original_command
        _command_alias_map[original_command].append(alias)
        
        # 更新配置文件
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if 'aliases' not in config:
                config['aliases'] = {'enabled': True, 'commands': {}}
            
            if original_command not in config['aliases']['commands']:
                config['aliases']['commands'][original_command] = []
            
            config['aliases']['commands'][original_command].append(alias)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        
        logging.info(f"成功添加别名: '{alias}' -> '{original_command}'")
        return True
        
    except Exception as e:
        logging.error(f"添加别名失败: {e}")
        return False

def remove_alias(alias: str, config_path: str = "config.json") -> bool:
    """
    删除别名
    :param alias: 要删除的别名
    :param config_path: 配置文件路径
    :return: 是否删除成功
    """
    global _alias_reverse_map, _command_alias_map
    
    if not _alias_enabled:
        logging.warning("别名系统已禁用")
        return False
    
    if alias not in _alias_reverse_map:
        logging.warning(f"别名 '{alias}' 不存在")
        return False
    
    try:
        original_command = _alias_reverse_map.pop(alias)
        
        # 从命令的别名列表中移除
        if original_command in _command_alias_map:
            if alias in _command_alias_map[original_command]:
                _command_alias_map[original_command].remove(alias)
        
        # 更新配置文件
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            if 'aliases' in config and 'commands' in config['aliases']:
                if original_command in config['aliases']['commands']:
                    if alias in config['aliases']['commands'][original_command]:
                        config['aliases']['commands'][original_command].remove(alias)
                
                # 如果某个命令的别名列表为空，可以考虑删除该命令条目
                # 但保留空列表以便后续添加别名
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
        
        logging.info(f"成功删除别名: '{alias}' (原指向 '{original_command}')")
        return True
        
    except Exception as e:
        logging.error(f"删除别名失败: {e}")
        return False

def list_aliases() -> Dict[str, List[str]]:
    """
    列出所有命令及其别名
    :return: {原命令: [别名列表]} 的字典
    """
    if not _alias_enabled:
        return {}
    
    return get_all_commands_with_aliases()

def get_alias_help() -> str:
    """
    获取别名系统帮助信息
    """
    if not _alias_enabled:
        return "别名系统当前已禁用"
    
    help_text = "=== 命令别名系统帮助 ===\n\n"
    help_text += "别名系统允许您为常用命令创建多个简短的别名\n"
    help_text += "原命令和所有别名都可以正常使用\n\n"
    help_text += "【管理命令】\n"
    help_text += "• 添加别名: 添加别名 [别名] [原始命令]\n"
    help_text += "• 删除别名: 删除别名 [别名]\n"
    help_text += "• 查看别名: 查看别名\n"
    help_text += "• 别名帮助: 别名帮助\n\n"
    help_text += "【使用示例】\n"
    help_text += "• 添加别名 cs 城市搜索\n"
    help_text += "• 添加别名 now 实时天气\n"
    help_text += "• 城市搜索 北京  (使用原命令)\n"
    help_text += "• cs 北京        (使用别名)\n"
    help_text += "• now 101010100  (使用别名)\n\n"
    
    total_aliases = len(_alias_reverse_map)
    total_commands = len(_command_alias_map)
    help_text += f"当前共有 {total_aliases} 个别名，映射到 {total_commands} 个原命令"
    
    return help_text

# 兼容性函数
def resolve_alias(command_name: str) -> str:
    """兼容旧版本的别名解析函数"""
    return resolve_command(command_name)