# command_handler.py
import json
import logging
from typing import Dict, Any
from message_sender import send_group_msg, send_group_img
from draw_eq import draw_earthquake_async
from ws_handler import process_message  # 复用处理逻辑


def is_valid_test_command_event(event: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """
    检查事件是否为有效的测试命令
    :param event: 事件数据
    :param config: 配置
    :return: 是否为有效测试命令
    """
    # 检查是否启用命令监听
    if not config.get("enable_command_listener", False):
        return False

    # 检查事件类型
    if event.get("post_type") != "message" or event.get("message_type") != "group":
        return False

    group_id = str(event.get("group_id"))
    
    # 检查是否只在配置的群组中响应命令
    if config.get("test_groups_only", True) and group_id not in config.get("groups", {}):
        return False

    # 检查是否为测试命令
    raw_message = event.get("raw_message", "").strip()
    test_cmd = config.get("test_command", "/eqbottest")
    
    return raw_message == test_cmd


def create_test_earthquake_data() -> list:
    """
    创建测试地震数据
    :return: 测试数据列表
    """
    return [
        {
            "type": "update",
            "source": "emsc",
            "Data": {
                "id": "test_emsc_001",
                "shockTime": "2026-02-02 03:00:00",
                "latitude": 33.993,
                "longitude": -116.949,
                "depth": 6,
                "magnitude": 2.1,
                "placeName": "SOUTHERN CALIFORNIA (测试)"
            }
        },
        {
            "type": "update",
            "source": "usgs",
            "Data": {
                "id": "test_usgs_001",
                "shockTime": "2026-02-02 04:59:59",
                "placeName": "汤加群岛附近[正式(已核实)] (测试)",
                "magnitude": 5.8,
                "latitude": -20.0,
                "longitude": -175.0,
                "depth": 10
            }
        }
    ]


async def handle_command(event: Dict[str, Any], config: Dict[str, Any]) -> None:
    """
    处理测试命令
    :param event: 事件数据
    :param config: 配置
    """
    if not is_valid_test_command_event(event, config):
        return

    group_id = str(event.get("group_id"))
    test_cmd = config.get("test_command", "/eqbottest")
    
    logging.info(f"收到测试命令 {test_cmd} 来自群 {group_id}")

    # 发送测试提示
    await send_group_msg(group_id, "开始运行 /eqbottest 测试...\n模拟两条地震消息（emsc M2.1 + usgs M5.8）")

    # 创建并发送测试数据
    test_data_list = create_test_earthquake_data()
    
    for test_data in test_data_list:
        await process_message(json.dumps(test_data), config, target_group=group_id)

    await send_group_msg(group_id, "测试完成！如果没收到消息，请检查日志 eqbot.log")