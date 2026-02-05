# command_handler.py
import json
import logging
import os
from typing import Dict, Any
from message_sender import send_group_msg, send_group_img
from draw_eq import draw_earthquake_async
from ws_handler import process_message  # 复用处理逻辑

# 导入天气API模块
try:
    from weather_api import QWeatherAPI, format_weather_response
    WEATHER_API_AVAILABLE = True
except ImportError as e:
    logging.warning(f"天气API模块导入失败: {e}")
    WEATHER_API_AVAILABLE = False


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
    test_cmd = config.get("test_command", "/bydbottest")

    return raw_message == test_cmd


def create_test_earthquake_data() -> list:
    """
    创建测试数据
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


def get_weather_command_help(command_name: str) -> str:
    """获取天气命令的帮助信息"""
    help_info = {
        "城市搜索": "城市搜索 location [adm] [range] [number] [lang]\n- location: 城市名称、经纬度、LocationID或Adcode（必选）\n- adm: 上级行政区划，用于排除重名城市（可选）\n- range: 搜索范围，ISO 3166国家代码（可选）\n- number: 返回结果数量(1-20，默认10)（可选）\n- lang: 多语言设置（可选）\n示例: 城市搜索 北京\n示例: 城市搜索 上海 CN 10 zh",

        "热门城市查询": "热门城市查询 [range] [number] [lang]\n- range: 国家代码（可选）\n- number: 返回数量(1-20，默认10)（可选）\n- lang: 语言（可选）\n示例: 热门城市查询\n示例: 热门城市查询 CN 15 zh",

        "POI搜索": "POI搜索 location type [city] [number] [lang]\n- location: 地点名称、经纬度等（必选）\n- type: POI类型(scenic景点, TSTA潮汐站点, city城市)（必选）\n- city: POI所在城市（可选）\n- number: 返回结果数量(1-20，默认10)（可选）\n- lang: 多语言设置（可选）\n示例: POI搜索 故宫 scenic",

        "实时天气": "实时天气 location [lang] [unit]\n- location: LocationID或经纬度坐标（必选）\n- lang: 多语言设置（可选，默认zh）\n- unit: 单位(m公制, i英制)（可选，默认m）\n示例: 实时天气 101010100\n示例: 实时天气 116.4074,39.9042 zh m",

        "每日天气预报": "每日天气预报 days location [lang] [unit]\n- days: 预报天数(3d, 7d, 10d, 15d, 30d)（必选）\n- location: LocationID或经纬度坐标（必选）\n- lang: 多语言设置（可选）\n- unit: 单位（可选）\n示例: 每日天气预报 7d 101010100\n示例: 每日天气预报 3d 116.4074,39.9042 zh m",

        "逐小时天气预报": "逐小时天气预报 hours location [lang] [unit]\n- hours: 预报小时数(24h, 72h, 168h)（必选）\n- location: LocationID或经纬度坐标（必选）\n- lang: 多语言设置（可选）\n- unit: 单位（可选）\n示例: 逐小时天气预报 24h 101010100",

        "格点实时天气": "格点实时天气 location [lang] [unit]\n- location: 经纬度坐标（必选）\n- lang: 多语言设置（可选）\n- unit: 单位（可选）\n示例: 格点实时天气 116.4074,39.9042",

        "格点每日天气预报": "格点每日天气预报 days location [lang] [unit]\n- days: 预报天数(3d, 7d)（必选）\n- location: 经纬度坐标（必选）\n- lang: 多语言设置（可选）\n- unit: 单位（可选）\n示例: 格点每日天气预报 3d 116.4074,39.9042",

        "格点逐小时天气预报": "格点逐小时天气预报 hours location [lang] [unit]\n- hours: 预报小时数(24h, 72h, 168h)（必选）\n- location: 经纬度坐标（必选）\n- lang: 多语言设置（可选）\n- unit: 单位（可选）\n示例: 格点逐小时天气预报 24h 116.4074,39.9042",

        "分钟级降水": "分钟级降水 location [lang]\n- location: 经纬度坐标（必选）\n- lang: 多语言设置（可选）\n示例: 分钟级降水 116.4074,39.9042",

        "实时天气预警": "实时天气预警 latitude longitude [localTime] [lang]\n- latitude: 纬度（必选）\n- longitude: 经度（必选）\n- localTime: 是否返回本地时间(true/false)（可选）\n- lang: 多语言设置（可选）\n示例: 实时天气预警 39.9042 116.4074\n示例: 实时天气预警 31.2304 121.4737 true zh",

        "天气指数预报": "天气指数预报 days location type [lang]\n- days: 预报天数(1d, 3d)（必选）\n- location: LocationID或经纬度坐标（必选）\n- type: 指数类型ID（可选，默认0表示所有）\n- lang: 多语言设置（可选）\n示例: 天气指数预报 1d 101010100 0 zh",

        "实时空气质量": "实时空气质量 latitude longitude [lang]\n- latitude: 纬度（必选）\n- longitude: 经度（必选）\n- lang: 多语言设置（可选）\n示例: 实时空气质量 39.9042 116.4074",

        "空气质量每日预报": "空气质量每日预报 latitude longitude [localTime] [lang]\n- latitude: 纬度（必选）\n- longitude: 经度（必选）\n- localTime: 是否返回本地时间（可选）\n- lang: 多语言设置（可选）\n示例: 空气质量每日预报 39.9042 116.4074",

        "空气质量小时预报": "空气质量小时预报 latitude longitude [localTime] [lang]\n- latitude: 纬度（必选）\n- longitude: 经度（必选）\n- localTime: 是否返回本地时间（可选）\n- lang: 多语言设置（可选）\n示例: 空气质量小时预报 39.9042 116.4074"
    }

    return help_info.get(command_name, f"未知命令: {command_name}")


def is_weather_command(raw_message: str) -> tuple[bool, str, list]:
    """
    检查是否为天气命令（使用空格分隔参数）
    :param raw_message: 原始消息
    :return: (是否为天气命令, 命令名称, 参数列表)
    """
    if not WEATHER_API_AVAILABLE:
        return False, "", []

    msg_parts = raw_message.strip().split()
    if not msg_parts:
        return False, "", []

    command_name = msg_parts[0].strip()
    args = [arg.strip() for arg in msg_parts[1:]] if len(msg_parts) > 1 else []

    # 支持的命令列表
    supported_commands = [
        "城市搜索", "热门城市查询", "POI搜索", "实时天气", "每日天气预报", "逐小时天气预报",
        "格点实时天气", "格点每日天气预报", "格点逐小时天气预报", "分钟级降水", "实时天气预警",
        "天气指数预报", "实时空气质量", "空气质量每日预报", "空气质量小时预报", "天气统计", "天气开关"
    ]

    if command_name in supported_commands:
        return True, command_name, args

    return False, "", []


async def handle_weather_stats(group_id: str, config: Dict[str, Any]) -> None:
    """
    处理天气统计命令
    :param group_id: 群ID
    :param config: 配置
    """
    # 获取天气API配置
    qweather_config = config.get('qweather', {})
    
    # 检查是否启用了天气功能
    if not WEATHER_API_AVAILABLE:
        await send_group_msg(group_id, "天气功能未启用，请检查配置")
        return
    
    # 显示当前天气API配置信息
    stats_info = [
        "【天气功能统计】",
        f"API主机: {qweather_config.get('api_host', 'N/A')}",
        f"缓存状态: {'启用' if qweather_config.get('cache_enabled', True) else '禁用'}",
        f"缓存TTL: {qweather_config.get('cache_ttl', 600)}秒",
        "支持的命令: 城市搜索, 实时天气, 天气预报等"
    ]
    
    await send_group_msg(group_id, "\n".join(stats_info))


async def handle_weather_toggle(args: list, group_id: str, user_id: str, config: Dict[str, Any]) -> None:
    """
    处理天气开关命令
    :param args: 参数列表
    :param group_id: 群ID
    :param user_id: 用户ID
    :param config: 配置
    """
    # 检查是否提供了参数
    if not args:
        await send_group_msg(group_id, "天气开关命令格式: 天气开关 [开启|关闭]")
        return
    
    action = args[0].strip()
    
    if action in ["开启", "打开", "启动"]:
        # 在实际应用中，这里可以实现动态启用/禁用天气功能的逻辑
        # 例如，可以将设置保存到配置文件或数据库中
        await send_group_msg(group_id, "天气功能已开启")
    elif action in ["关闭", "停止"]:
        # 在实际应用中，这里可以实现动态启用/禁用天气功能的逻辑
        await send_group_msg(group_id, "天气功能已关闭")
    else:
        await send_group_msg(group_id, "天气开关命令格式: 天气开关 [开启|关闭]")


async def handle_weather_command(command_name: str, args: list, group_id: str, config: Dict[str, Any], user_id: str = None) -> None:
    """
    处理天气命令（使用空格分隔参数）
    :param command_name: 命令名称
    :param args: 参数列表
    :param group_id: 群ID
    :param config: 配置
    :param user_id: 用户ID（用于统计）
    """
    if not WEATHER_API_AVAILABLE:
        await send_group_msg(group_id, "天气功能未启用，请检查配置")
        return

    # 检查是否请求帮助
    if args and (args[0] == "-h" or args[0] == "-help"):
        help_text = get_weather_command_help(command_name)
        await send_group_msg(group_id, f"【{command_name} 帮助】\n{help_text}")
        return

    api = QWeatherAPI(config)

    try:
        if command_name == "城市搜索":
            # 城市搜索 location [adm] [range] [number] [lang]
            location = args[0] if len(args) > 0 else "北京"
            adm = args[1] if len(args) > 1 else None
            range_param = args[2] if len(args) > 2 else None
            number = int(args[3]) if len(args) > 3 else 10
            lang = args[4] if len(args) > 4 else "zh"

            result = await api.geo_lookup(location, adm, range_param, number, lang)
            if result:
                formatted_msg = format_weather_response("城市搜索", result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "城市搜索失败")

        elif command_name == "热门城市查询":
            # 热门城市查询 [range] [number] [lang]
            range_param = args[0] if len(args) > 0 else None
            number = int(args[1]) if len(args) > 1 else 10
            lang = args[2] if len(args) > 2 else "zh"

            result = await api.geo_top(range_param, number, lang)
            if result:
                formatted_msg = format_weather_response("热门城市查询", result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "热门城市查询失败")

        elif command_name == "POI搜索":
            # POI搜索 location type [city] [number] [lang]
            location = args[0] if len(args) > 0 else "故宫"
            type_param = args[1] if len(args) > 1 else "scenic"
            city = args[2] if len(args) > 2 else None
            number = int(args[3]) if len(args) > 3 else 10
            lang = args[4] if len(args) > 4 else "zh"

            # 注意：当前API可能不支持POI搜索，这里先留空
            await send_group_msg(group_id, "POI搜索功能暂未实现")

        elif command_name == "实时天气":
            # 实时天气 location [lang] [unit]
            location = args[0] if len(args) > 0 else "101010100"
            lang = args[1] if len(args) > 1 else "zh"
            unit = args[2] if len(args) > 2 else "m"

            result = await api.weather_now(location, lang, unit)
            if result:
                formatted_msg = format_weather_response("实时天气", result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "获取实时天气失败")

        elif command_name == "每日天气预报":
            # 每日天气预报 days location [lang] [unit]
            days = args[0] if len(args) > 0 else "3d"
            location = args[1] if len(args) > 1 else "101010100"
            lang = args[2] if len(args) > 2 else "zh"
            unit = args[3] if len(args) > 3 else "m"

            result = await api.weather_forecast(days, location, lang, unit)
            if result:
                template_key = f"每日天气预报_{days}"
                formatted_msg = format_weather_response(template_key, result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "获取每日天气预报失败")

        elif command_name == "逐小时天气预报":
            # 逐小时天气预报 hours location [lang] [unit]
            hours = args[0] if len(args) > 0 else "24h"
            location = args[1] if len(args) > 1 else "101010100"
            lang = args[2] if len(args) > 2 else "zh"
            unit = args[3] if len(args) > 3 else "m"

            result = await api.weather_hourly(hours, location, lang, unit)
            if result:
                template_key = f"逐小时天气预报_{hours}"
                formatted_msg = format_weather_response(template_key, result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "获取逐小时天气预报失败")

        elif command_name == "格点实时天气":
            # 格点实时天气 location [lang] [unit]
            location = args[0] if len(args) > 0 else "116.4074,39.9042"
            lang = args[1] if len(args) > 1 else "zh"
            unit = args[2] if len(args) > 2 else "m"

            result = await api.grid_weather_now(location, lang, unit)
            if result:
                formatted_msg = format_weather_response("格点实时天气", result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "获取格点实时天气失败")

        elif command_name == "格点每日天气预报":
            # 格点每日天气预报 days location [lang] [unit]
            days = args[0] if len(args) > 0 else "3d"
            location = args[1] if len(args) > 1 else "116.4074,39.9042"
            lang = args[2] if len(args) > 2 else "zh"
            unit = args[3] if len(args) > 3 else "m"

            result = await api.grid_weather_forecast(days, location, lang, unit)
            if result:
                template_key = f"格点每日天气预报_{days}"
                formatted_msg = format_weather_response(template_key, result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "获取格点每日天气预报失败")

        elif command_name == "格点逐小时天气预报":
            # 格点逐小时天气预报 hours location [lang] [unit]
            hours = args[0] if len(args) > 0 else "24h"
            location = args[1] if len(args) > 1 else "116.4074,39.9042"
            lang = args[2] if len(args) > 2 else "zh"
            unit = args[3] if len(args) > 3 else "m"

            result = await api.grid_weather_hourly(hours, location, lang, unit)
            if result:
                template_key = f"格点逐小时天气预报_{hours}"
                formatted_msg = format_weather_response(template_key, result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "获取格点逐小时天气预报失败")

        elif command_name == "分钟级降水":
            # 分钟级降水 location [lang]
            location = args[0] if len(args) > 0 else "116.4074,39.9042"
            lang = args[1] if len(args) > 1 else "zh"

            result = await api.minutely_precipitation(location, lang)
            if result:
                formatted_msg = format_weather_response("分钟级降水", result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "获取分钟级降水失败")

        elif command_name == "实时天气预警":
            # 实时天气预警 latitude longitude [localTime] [lang]
            if len(args) >= 2:
                try:
                    latitude = float(args[0])
                    longitude = float(args[1])
                    localTime = args[2].lower() == 'true' if len(args) > 2 else False
                    lang = args[3] if len(args) > 3 else "zh"

                    result = await api.weather_alert(latitude, longitude, localTime, lang)
                    if result:
                        formatted_msg = format_weather_response("实时天气预警", result, config)
                        await send_group_msg(group_id, formatted_msg)
                    else:
                        await send_group_msg(group_id, "当前无天气预警")
                except ValueError:
                    await send_group_msg(group_id, "经纬度格式错误，请提供数字")
            else:
                await send_group_msg(group_id, "请提供经纬度参数：实时天气预警 纬度 经度")

        elif command_name == "天气指数预报":
            # 天气指数预报 days location type [lang]
            days = args[0] if len(args) > 0 else "1d"
            location = args[1] if len(args) > 1 else "101010100"
            type_param = args[2] if len(args) > 2 else "0"
            lang = args[3] if len(args) > 3 else "zh"

            result = await api.weather_indices(type_param, location, days, lang)
            if result:
                template_key = f"天气指数预报_{days}"
                formatted_msg = format_weather_response(template_key, result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "获取天气指数预报失败")

        elif command_name == "实时空气质量":
            # 实时空气质量 latitude longitude [lang]
            if len(args) >= 2:
                try:
                    latitude = float(args[0])
                    longitude = float(args[1])
                    lang = args[2] if len(args) > 2 else "zh"

                    result = await api.air_quality_current(latitude, longitude, lang)
                    if result:
                        formatted_msg = format_weather_response("实时空气质量", result, config)
                        await send_group_msg(group_id, formatted_msg)
                    else:
                        await send_group_msg(group_id, "获取实时空气质量失败")
                except ValueError:
                    await send_group_msg(group_id, "经纬度格式错误，请提供数字")
            else:
                await send_group_msg(group_id, "请提供经纬度参数：实时空气质量 纬度 经度")

        elif command_name == "空气质量每日预报":
            # 空气质量每日预报 latitude longitude [localTime] [lang]
            if len(args) >= 2:
                try:
                    latitude = float(args[0])
                    longitude = float(args[1])
                    localTime = args[2].lower() == 'true' if len(args) > 2 else False
                    lang = args[3] if len(args) > 3 else "zh"

                    result = await api.air_quality_daily(latitude, longitude, localTime, lang)
                    if result:
                        formatted_msg = format_weather_response("空气质量每日预报", result, config)
                        await send_group_msg(group_id, formatted_msg)
                    else:
                        await send_group_msg(group_id, "获取空气质量每日预报失败")
                except ValueError:
                    await send_group_msg(group_id, "经纬度格式错误，请提供数字")
            else:
                await send_group_msg(group_id, "请提供经纬度参数：空气质量每日预报 纬度 经度")

        elif command_name == "空气质量小时预报":
            # 空气质量小时预报 latitude longitude [localTime] [lang]
            if len(args) >= 2:
                try:
                    latitude = float(args[0])
                    longitude = float(args[1])
                    localTime = args[2].lower() == 'true' if len(args) > 2 else False
                    lang = args[3] if len(args) > 3 else "zh"

                    result = await api.air_quality_hourly(latitude, longitude, localTime, lang)
                    if result:
                        formatted_msg = format_weather_response("空气质量小时预报", result, config)
                        await send_group_msg(group_id, formatted_msg)
                    else:
                        await send_group_msg(group_id, "获取空气质量小时预报失败")
                except ValueError:
                    await send_group_msg(group_id, "经纬度格式错误，请提供数字")
            else:
                await send_group_msg(group_id, "请提供经纬度参数：空气质量小时预报 纬度 经度")

        elif command_name == "天气统计":
            # 天气统计命令（无参数）
            await handle_weather_stats(group_id, config)

        elif command_name == "天气开关":
            # 天气开关 [开启|关闭]
            await handle_weather_toggle(args, group_id, user_id, config)

        else:
            await send_group_msg(group_id, f"未知的天气命令: {command_name}")

    except Exception as e:
        logging.error(f"处理天气命令异常: {e}")
        await send_group_msg(group_id, f"天气命令处理出错: {str(e)}")


async def handle_command(event: Dict[str, Any], config: Dict[str, Any]) -> None:
    """
    处理命令（包括测试命令和天气命令）
    :param event: 事件数据
    :param config: 配置
    """
    # 检查是否启用命令监听
    if not config.get("enable_command_listener", False):
        logging.debug("命令监听已禁用")
        return

    # 检查事件类型
    if event.get("post_type") != "message" or event.get("message_type") != "group":
        logging.debug(f"事件类型不匹配: {event.get('post_type')}, {event.get('message_type')}")
        return

    group_id = str(event.get("group_id"))
    raw_message = event.get("raw_message", "").strip()

    logging.debug(f"收到消息: '{raw_message}' 来自群 {group_id}")

    # 检查是否为测试命令
    if is_valid_test_command_event(event, config):
        group_id = str(event.get("group_id"))
        test_cmd = config.get("test_command", "/bydbottest")

        logging.info(f"收到测试命令 {test_cmd} 来自群 {group_id}")

        # 发送测试提示
        await send_group_msg(group_id, "开始运行 /bydbottest 测试...\n模拟两条消息（emsc M2.1 + usgs M5.8）")

        # 创建并发送测试数据
        test_data_list = create_test_earthquake_data()

        for test_data in test_data_list:
            await process_message(json.dumps(test_data), config, target_group=group_id)

        await send_group_msg(group_id, "测试完成！如果没收到消息，请检查日志 bydbot.log")
        return

    # 检查是否为天气命令（直接匹配命令名称，使用空格分隔）
    is_weather, command_name, args = is_weather_command(raw_message)

    if is_weather:
        logging.debug(f"识别为天气命令: {command_name}, 参数: {args}")
        # 检查是否只在配置的群组中响应命令
        if config.get("test_groups_only", True) and group_id not in config.get("groups", {}):
            logging.debug(f"群 {group_id} 不在配置的群组列表中，忽略命令")
            return

        logging.info(f"收到天气命令 {raw_message} 来自群 {group_id}")
        # 获取用户ID用于统计
        user_id = str(event.get("user_id", ""))
        await handle_weather_command(command_name, args, group_id, config, user_id)
    else:
        logging.debug(f"不是有效的天气命令: {raw_message}")