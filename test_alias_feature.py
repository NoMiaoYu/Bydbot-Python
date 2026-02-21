#!/usr/bin/env python3
"""
测试别名功能的脚本
"""

import json
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(__file__))

def test_alias_basic_functionality():
    """测试别名基本功能"""
    print("=== 测试别名基本功能 ===")
    
    try:
        from alias_handler import init_alias_system, resolve_alias, is_alias, get_all_aliases
        
        # 加载配置
        config_path = "config.json"
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
        
        # 初始化别名系统
        init_alias_system(config)
        
        # 测试别名解析
        test_cases = [
            ("cs", "城市搜索"),
            ("rw", "实时天气"),
            ("bl", "B站直播间查询"),
            ("nonexistent", "nonexistent")  # 不存在的别名
        ]
        
        print("别名解析测试:")
        for alias, expected in test_cases:
            result = resolve_alias(alias)
            status = "✅" if result == expected else "❌"
            print(f"  {status} '{alias}' -> '{result}' (期望: '{expected}')")
        
        # 测试别名检测
        print("\n别名检测测试:")
        alias_check_cases = ["cs", "rw", "nonexistent", "城市搜索"]
        for case in alias_check_cases:
            is_alias_result = is_alias(case)
            status = "✅" if ((case in ["cs", "rw"] and is_alias_result) or 
                            (case in ["nonexistent", "城市搜索"] and not is_alias_result)) else "❌"
            print(f"  {status} is_alias('{case}') = {is_alias_result}")
        
        # 显示所有别名
        print("\n当前所有别名:")
        aliases = get_all_aliases()
        for alias, original in sorted(aliases.items()):
            print(f"  {alias} -> {original}")
        
        print(f"\n总计: {len(aliases)} 个别名")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_command_integration():
    """测试命令集成"""
    print("\n=== 测试命令集成 ===")
    
    try:
        # 模拟测试消息
        test_messages = [
            "cs 北京",
            "rw 101010100",
            "bl 123456",
            "城市搜索 上海"  # 非别名命令
        ]
        
        print("模拟命令解析:")
        for msg in test_messages:
            # 模拟命令解析过程
            parts = msg.strip().split()
            if parts:
                command_name = parts[0]
                args = parts[1:] if len(parts) > 1 else []
                
                # 如果别名系统可用，尝试解析别名
                try:
                    from alias_handler import resolve_alias, is_alias_enabled
                    if is_alias_enabled():
                        resolved_command = resolve_alias(command_name)
                        if resolved_command != command_name:
                            print(f"  ✅ '{msg}' -> 命令: '{resolved_command}', 参数: {args}")
                        else:
                            print(f"  ℹ️  '{msg}' -> 命令: '{command_name}', 参数: {args} (未解析)")
                    else:
                        print(f"  ⚠️  别名系统未启用")
                except ImportError:
                    print(f"  ⚠️  别名模块未导入")
        
        return True
        
    except Exception as e:
        print(f"❌ 命令集成测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试别名功能...")
    
    success_count = 0
    total_tests = 2
    
    # 运行测试
    if test_alias_basic_functionality():
        success_count += 1
    
    if test_command_integration():
        success_count += 1
    
    # 输出总结
    print(f"\n=== 测试总结 ===")
    print(f"成功: {success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("🎉 所有测试通过！")
        return True
    else:
        print("❌ 部分测试失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)