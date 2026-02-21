#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试help命令功能
"""

import sys
import os
sys.path.append('.')

from help_message import get_help_file_path
from message_sender import send_forward_msg

async def test_help_command():
    """测试help命令功能"""
    try:
        # 获取帮助文件路径
        help_file_path = get_help_file_path()
        print(f"Help file path: {help_file_path}")
        
        # 检查文件是否存在
        if not os.path.exists(help_file_path):
            print("Help file not found!")
            return False
            
        # 读取文件内容
        with open(help_file_path, 'r', encoding='utf-8') as f:
            help_content = f.read()
        
        print(f"File size: {len(help_content)} characters")
        print(f"First 100 chars: {help_content[:100]}")
        
        # 模拟群号进行测试
        test_group_id = "1071528933"
        
        # 这里只是打印内容，实际使用时会调用send_forward_msg
        print("Would send help content via send_forward_msg...")
        print("Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    import asyncio
    result = asyncio.run(test_help_command())
    print(f"Test result: {'PASS' if result else 'FAIL'}")