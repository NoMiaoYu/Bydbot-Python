# command_handler.py
import json
import logging
from message_sender import send_group_msg, send_group_img
from draw_eq import draw_earthquake_async
from ws_handler import process_message  # 复用处理逻辑

async def handle_command(event, config):
    if not config.get("enable_command_listener", False):
        return

    # 假设 NapCat 上报的群消息事件格式（OneBot v11 标准）
    # 你需要根据 NapCat 实际上报调整字段名
    if event.get("post_type") != "message" or event.get("message_type") != "group":
        return

    group_id = str(event.get("group_id"))
    raw_message = event.get("raw_message", "").strip()

    # 只响应配置的群（可选）
    if config.get("test_groups_only", True) and group_id not in config["groups"]:
        return

    test_cmd = config.get("test_command", "/eqbottest")
    if raw_message != test_cmd:
        return

    logging.info(f"收到测试命令 {test_cmd} 来自群 {group_id}")

    # 发送测试提示
    await send_group_msg(group_id, "开始运行 /eqbottest 测试...\n模拟两条地震消息（emsc M2.1 + usgs M5.8）")

    # 第一条测试：emsc 小震（通常不触发，因为震级低）
    test1 = {
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
    }
    await process_message(json.dumps(test1), config, target_group=group_id)  # 加 target_group 参数，只推当前群

    # 第二条测试：usgs M5.8（应该触发文本 + 绘图）
    test2 = {
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
    await process_message(json.dumps(test2), config, target_group=group_id)

    await send_group_msg(group_id, "测试完成！如果没收到消息，请检查日志 eqbot.log")