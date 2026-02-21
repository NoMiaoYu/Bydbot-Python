"""
Bydbot - 命令处理器
处理来自QQ群的各种命令
"""

import json
import logging
import os
import asyncio
from typing import Dict, Any, Tuple, List, Optional
from help_message import get_help_file_path
from message_sender import send_group_msg, send_group_img, send_forward_msg
from ws_handler import process_message  # 复用处理逻辑

# 导入天气API模块
try:
    from weather_api import QWeatherAPI, format_weather_response
    WEATHER_API_AVAILABLE = True
except ImportError as e:
    logging.warning(f"天气API模块导入失败: {e}")
    WEATHER_API_AVAILABLE = False

# 导入CMA气象预警订阅模块
try:
    from cma_weather_subscriber import init_cma_weather_subscriber, get_subscriber
    CMA_WEATHER_SUBSCRIBER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"CMA气象预警订阅模块导入失败: {e}")
    CMA_WEATHER_SUBSCRIBER_AVAILABLE = False

# 导入UAPI模块
try:
    from uapi_handler import handle_uapi_command
    UAPI_AVAILABLE = True
except ImportError as e:
    logging.warning(f"UAPI模块导入失败: {e}")
    UAPI_AVAILABLE = False

# 导入全局变量
import sys
import re
sys.path.append(os.path.dirname(__file__))

# 导入别名处理模块
try:
    from alias_handler import init_alias_system, resolve_command, is_alias, get_alias_help, is_valid_command, is_alias_enabled
    ALIAS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"别名处理模块导入失败: {e}")
    ALIAS_AVAILABLE = False

# 导入绘图模块
try:
    from draw_eq import draw_earthquake_async
    DRAW_EQ_AVAILABLE = True
except ImportError as e:
    logging.warning(f"绘图模块导入失败: {e}")
    DRAW_EQ_AVAILABLE = False


def parse_cq_code(message: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    解析消息中的CQ码
    :param message: 原始消息
    :return: (纯文本消息, CQ码列表)
    """
    cq_codes = []
    
    # 匹配CQ码格式: [CQ:type,key=value,key=value,...]
    pattern = r'\[CQ:([a-zA-Z]+)((?:,[^,\]]+=[^,\]]+)*)\]'
    
    def replace_cq(match):
        cq_type = match.group(1)
        params_str = match.group(2)
        
        # 解析参数
        params = {}
        if params_str:
            param_pairs = params_str[1:].split(',')  # 去掉开头的逗号
            for pair in param_pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[key] = value
        
        cq_codes.append({
            'type': cq_type,
            'data': params
        })
        
        return ''  # 替换为空字符串
    
    # 替换所有CQ码
    clean_message = re.sub(pattern, replace_cq, message)
    
    return clean_message, cq_codes


def extract_qq_from_at(event: Dict[str, Any]) -> Optional[str]:
    """
    从事件中提取@的QQ号
    :param event: 事件数据
    :return: QQ号，如果没有@则返回None
    """
    # 方法1: 从message字段解析CQ码
    message = event.get('message', '')
    if isinstance(message, list):
        # message是数组格式
        for segment in message:
            if isinstance(segment, dict):
                if segment.get('type') == 'at':
                    qq = segment.get('data', {}).get('qq')
                    if qq and qq != 'all':
                        return qq
    elif isinstance(message, str):
        # message是字符串格式，包含CQ码
        _, cq_codes = parse_cq_code(message)
        for cq in cq_codes:
            if cq['type'] == 'at':
                qq = cq['data'].get('qq')
                if qq and qq != 'all':
                    return qq
    
    return None


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

    group_id = str(event.get("group_id", ""))

    # 检查是否只在配置的群组中响应命令
    if config.get("test_groups_only", True) and group_id not in config.get("groups", {}):
        return False

    # 检查是否为测试命令
    raw_message = event.get("raw_message", "").strip()
    test_cmd = config.get("test_command", "/eqtest")

    return raw_message == test_cmd


def is_help_command_event(event: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """
    检查事件是否为帮助命令
    :param event: 事件数据
    :param config: 配置
    :return: 是否为帮助命令
    """
    # 检查是否启用命令监听
    if not config.get("enable_command_listener", False):
        return False

    # 检查事件类型
    if event.get("post_type") != "message" or event.get("message_type") != "group":
        return False

    group_id = str(event.get("group_id", ""))

    # 检查是否只在配置的群组中响应命令
    if config.get("test_groups_only", True) and group_id not in config.get("groups", {}):
        return False

    # 检查是否为帮助命令
    raw_message = event.get("raw_message", "").strip().lower()
    return raw_message == "/help" or raw_message == "help"


    # 检查是否为帮助命令
    raw_message = event.get("raw_message", "").strip().lower()
    return raw_message == "/help" or raw_message == "help"


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
                "shockTime": "2026-02-16 10:30:00",
                "latitude": 33.993,
                "longitude": -116.949,
                "depth": 6,
                "magnitude": 6.2,
                "placeName": "SOUTHERN CALIFORNIA (测试)"
            }
        },
        {
            "type": "update",
            "source": "usgs",
            "Data": {
                "id": "test_usgs_001",
                "shockTime": "2026-02-16 11:45:00",
                "placeName": "汤加群岛附近[正式(已核实)] (测试)",
                "magnitude": 7.1,
                "latitude": -20.0,
                "longitude": -175.0,
                "depth": 10
            }
        }
    ]


async def send_test_message(test_data: dict, group_id: str, config: dict):
    """
    发送测试消息（直接发送，不经过数据库处理）
    :param test_data: 测试数据
    :param group_id: 群ID
    :param config: 配置
    """
    try:
        data = test_data.get("Data", {})
        source = test_data.get("source", "test")

        # 构建测试消息
        message = f"[测试数据 - {source.upper()}]\n"
        message += f"| 发生时间: {data.get('shockTime', 'N/A')}\n"
        message += f"| 震级: M {data.get('magnitude', 'N/A')}\n"
        message += f"| 深度: {data.get('depth', 'N/A')}km\n"
        message += f"| 震中: {data.get('placeName', 'N/A')}\n"
        message += f"| 经纬度: {data.get('longitude', 'N/A')} {data.get('latitude', 'N/A')}\n"
        message += f"| 数据ID: {data.get('id', 'N/A')}"

        # 发送文本消息
        await send_group_msg(group_id, message)
        logging.info(f"已发送测试消息到群 {group_id}")

        # 尝试绘制地震地图
        if DRAW_EQ_AVAILABLE:
            try:
                # 检查配置中是否启用该数据源的绘图
                drawing_config = config.get("earthquake", {}).get("drawing", {})
                draw_sources = drawing_config.get("sources", [])

                # 测试数据也检查是否在绘图源列表中
                if source in draw_sources or not draw_sources:  # 如果列表为空则所有源都绘图
                    # 准备绘图数据
                    draw_data = {
                        'latitude': data.get('latitude'),
                        'longitude': data.get('longitude'),
                        'magnitude': data.get('magnitude'),
                        'shockTime': data.get('shockTime'),
                        'placeName': data.get('placeName'),
                        'infoTypeName': '测试数据',
                        '_source': source
                    }

                    # 调用异步绘图
                    image_path = await draw_earthquake_async(draw_data, source)

                    if image_path:
                        # 发送图片
                        await send_group_img(group_id, image_path)
                        logging.info(f"已发送测试地震图到群 {group_id}")
                    else:
                        logging.warning(f"测试地震图绘制失败: {source}")
                else:
                    logging.debug(f"数据源 {source} 不在绘图源列表中，跳过绘图")
            except Exception as e:
                logging.error(f"绘制测试地震图失败: {e}")
        else:
            logging.warning("绘图模块不可用，跳过测试数据绘图")

    except Exception as e:
        logging.error(f"发送测试消息失败: {e}")
        await send_group_msg(group_id, f"测试消息发送失败: {str(e)}")


def get_weather_command_help(command_name: str) -> str:
    """获取天气命令的帮助信息"""
    help_info = {
        "城市搜索": "【城市搜索 帮助】\n功能：根据关键词搜索全球城市信息\n用法：城市搜索 location [adm] [range] [number] [lang]\n参数详解：\n- location: 城市名称、经纬度坐标、LocationID或Adcode（必选参数）\n  * 城市名称：如\"北京\"、\"上海\"、\"New York\"\n  * 经纬度：格式为\"经度,纬度\"，如\"116.4074,39.9042\"\n  * LocationID：和风天气城市ID，如\"101010100\"\n  * Adcode：行政区域代码\n- adm: 上级行政区划名称，用于精确匹配同名城市（可选参数）\n  * 例如搜索\"西安\"时，可指定\"陕西省\"来排除其他同名城市\n- range: 搜索范围限制，使用ISO 3166国家代码（可选参数）\n  * 如\"CN\"表示仅在中国范围内搜索\n  * \"US\"表示仅在美国范围内搜索\n  * 留空表示全球搜索\n- number: 返回结果数量，范围1-20，默认10个（可选参数）\n  * 数值越大返回结果越多，但会增加响应时间\n- lang: 多语言设置，支持多种语言（可选参数）\n  * zh：简体中文（默认）\n  * en：英语\n  * ja：日语\n  * 其他语言代码\n使用示例：\n- 城市搜索 北京\n- 城市搜索 上海 CN 10 zh\n- 城市搜索 116.4074,39.9042\n- 城市搜索 New York US 5 en\n注意事项：\n- location参数为必填项，其他参数均为可选\n- 当搜索结果较多时，建议使用adm参数进行精确匹配\n- 返回结果按相关性排序，最匹配的结果排在前面",

        "热门城市查询": "【热门城市查询 帮助】\n功能：查询全球或指定国家/地区的热门城市列表\n用法：热门城市查询 [range] [number] [lang]\n参数详解：\n- range: 国家/地区范围限制，使用ISO 3166国家代码（可选参数）\n  * CN：中国\n  * US：美国\n  * JP：日本\n  * GB：英国\n  * 留空表示查询全球热门城市\n- number: 返回城市数量，范围1-20，默认10个（可选参数）\n  * 建议根据需要调整，避免返回过多无关结果\n- lang: 语言设置（可选参数）\n  * zh：简体中文（默认）\n  * en：英语\n  * ja：日语\n  * 其他支持的语言代码\n使用示例：\n- 热门城市查询\n- 热门城市查询 CN 15 zh\n- 热门城市查询 US 20 en\n- 热门城市查询 JP 8 ja\n注意事项：\n- 热门城市基于搜索热度和人口规模综合排序\n- 不同语言环境下返回的城市名称会相应本地化\n- 全球热门城市通常包含国际大都市",

        "POI搜索": "【POI搜索 帮助】\n功能：搜索兴趣点(Points of Interest)信息\n用法：POI搜索 location type [city] [number] [lang]\n参数详解：\n- location: 兴趣点名称或坐标位置（必选参数）\n  * 地点名称：如\"故宫\"、\"东方明珠\"、\"Central Park\"\n  * 经纬度坐标：格式\"经度,纬度\"\n  * 地址信息\n- type: 兴趣点类型（必选参数）\n  * scenic：旅游景点\n  * TSTA：潮汐观测站点\n  * city：城市信息\n  * station：气象站点\n- city: 指定搜索的城市范围（可选参数）\n  * 用于缩小搜索范围，提高准确性\n  * 如\"北京市\"、\"上海市\"\n- number: 返回结果数量，1-20个，默认10个（可选参数）\n- lang: 多语言设置（可选参数）\n  * zh：简体中文（默认）\n  * en：英语\n  * 其他支持的语言\n使用示例：\n- POI搜索 故宫 scenic\n- POI搜索 Central Park scenic New York 5 en\n- POI搜索 121.4997,31.2397 scenic 上海市 10 zh\n注意事项：\n- location和type为必填参数\n- city参数有助于提高搜索精度\n- 不同类型的POI返回的信息结构可能不同",

        "实时天气": "【实时天气 帮助】\n功能：查询指定地点的当前实时天气状况\n用法：实时天气 location [lang] [unit]\n参数详解：\n- location: 查询位置标识（必选参数）\n  * LocationID：和风天气城市ID，如\"101010100\"（推荐）\n  * 经纬度坐标：格式\"经度,纬度\"，如\"116.4074,39.9042\"\n  * 城市名称：如\"北京\"、\"上海\"（准确度较低）\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n  * ja：日语\n  * 其他支持的语言代码\n- unit: 度量单位系统（可选参数，默认m）\n  * m：公制单位（摄氏度、公里/小时等）\n  * i：英制单位（华氏度、英里/小时等）\n使用示例：\n- 实时天气 101010100\n- 实时天气 116.4074,39.9042 zh m\n- 实时天气 101020100 en i\n- 实时天气 -74.0059,40.7128 en i\n返回信息包含：\n- 当前温度、体感温度\n- 天气状况描述\n- 湿度、风向风力\n- 能见度、气压\n- 数据更新时间\n注意事项：\n- 使用LocationID查询最为准确\n- 经纬度查询适合偏远地区\n- 英制单位下温度显示为华氏度",

        "每日天气预报": "【每日天气预报 帮助】\n功能：查询未来几天的天气预报\n用法：每日天气预报 days location [lang] [unit]\n参数详解：\n- days: 预报天数（必选参数）\n  * 3d：未来3天预报\n  * 7d：未来7天预报（推荐）\n  * 10d：未来10天预报\n  * 15d：未来15天预报\n  * 30d：未来30天预报\n- location: 查询位置标识（必选参数）\n  * LocationID：和风天气城市ID，如\"101010100\"（推荐）\n  * 经纬度坐标：格式\"经度,纬度\"，如\"116.4074,39.9042\"\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n  * ja：日语\n  * 其他支持的语言代码\n- unit: 度量单位系统（可选参数，默认m）\n  * m：公制单位（摄氏度、公里/小时等）\n  * i：英制单位（华氏度、英里/小时等）\n使用示例：\n- 每日天气预报 7d 101010100\n- 每日天气预报 3d 116.4074,39.9042 zh m\n- 每日天气预报 10d 101020100 en i\n- 每日天气预报 15d -74.0059,40.7128 en\n返回信息包含：\n- 每日最高温度和最低温度\n- 白天和夜间天气状况\n- 风向风力预报\n- 降水概率\n- 紫外线指数等\n注意事项：\n- 预报时间越长，准确度相对降低\n- 3-7天预报准确度最高\n- 30天预报仅供参考趋势",

        "逐小时天气预报": "【逐小时天气预报 帮助】\n功能：查询未来几小时的详细天气变化\n用法：逐小时天气预报 hours location [lang] [unit]\n参数详解：\n- hours: 预报小时数（必选参数）\n  * 24h：未来24小时预报（推荐日常使用）\n  * 72h：未来72小时预报\n  * 168h：未来168小时预报（一周）\n- location: 查询位置标识（必选参数）\n  * LocationID：和风天气城市ID，如\"101010100\"（推荐）\n  * 经纬度坐标：格式\"经度,纬度\"，如\"116.4074,39.9042\"\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n  * ja：日语\n  * 其他支持的语言代码\n- unit: 度量单位系统（可选参数，默认m）\n  * m：公制单位（摄氏度、公里/小时等）\n  * i：英制单位（华氏度、英里/小时等）\n使用示例：\n- 逐小时天气预报 24h 101010100\n- 逐小时天气预报 72h 116.4074,39.9042 zh m\n- 逐小时天气预报 168h 101020100 en i\n返回信息包含：\n- 每小时具体温度\n- 天气状况变化\n- 降水量预测\n- 风向风力变化\n- 湿度变化趋势\n注意事项：\n- 24小时预报准确度最高\n- 适合安排短期出行计划\n- 每小时数据更新及时",

        "格点实时天气": "【格点实时天气 帮助】\n功能：基于网格点查询精确位置的实时天气\n用法：格点实时天气 location [lang] [unit]\n参数详解：\n- location: 精确经纬度坐标（必选参数）\n  * 格式必须为\"经度,纬度\"\n  * 如\"116.4074,39.9042\"（北京）\n  * \"-74.0059,40.7128\"（纽约）\n  * 精度越高，查询结果越准确\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n  * ja：日语\n  * 其他支持的语言代码\n- unit: 度量单位系统（可选参数，默认m）\n  * m：公制单位（摄氏度、公里/小时等）\n  * i：英制单位（华氏度、英里/小时等）\n使用示例：\n- 格点实时天气 116.4074,39.9042\n- 格点实时天气 -74.0059,40.7128 en i\n- 格点实时天气 139.6917,35.6895 ja m\n适用场景：\n- 查询具体地址的天气\n- 户外活动地点天气\n- 精确位置气象数据\n- 科研用途\n注意事项：\n- 必须使用经纬度坐标，不支持城市名称\n- 坐标精度影响查询准确性\n- 返回数据更加精细化",

        "格点每日天气预报": "【格点每日天气预报 帮助】\n功能：基于网格点查询精确位置的未来天气预报\n用法：格点每日天气预报 days location [lang] [unit]\n参数详解：\n- days: 预报天数（必选参数）\n  * 3d：未来3天预报\n  * 7d：未来7天预报\n- location: 精确经纬度坐标（必选参数）\n  * 格式必须为\"经度,纬度\"\n  * 如\"116.4074,39.9042\"（北京某点）\n  * \"-74.0059,40.7128\"（纽约某点）\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n  * ja：日语\n  * 其他支持的语言代码\n- unit: 度量单位系统（可选参数，默认m）\n  * m：公制单位（摄氏度、公里/小时等）\n  * i：英制单位（华氏度、英里/小时等）\n使用示例：\n- 格点每日天气预报 3d 116.4074,39.9042\n- 格点每日天气预报 7d -74.0059,40.7128 en i\n- 格点每日天气预报 3d 139.6917,35.6895 ja\n优势特点：\n- 位置精度高，适合具体地点\n- 数据颗粒度细\n- 适合专业气象应用\n注意事项：\n- 仅支持3天和7天预报\n- 必须使用经纬度坐标\n- 预报准确度较高",

        "格点逐小时天气预报": "【格点逐小时天气预报 帮助】\n功能：基于网格点查询精确位置的逐小时天气预报\n用法：格点逐小时天气预报 hours location [lang] [unit]\n参数详解：\n- hours: 预报小时数（必选参数）\n  * 24h：未来24小时预报\n  * 72h：未来72小时预报\n  * 168h：未来168小时预报（一周）\n- location: 精确经纬度坐标（必选参数）\n  * 格式必须为\"经度,纬度\"\n  * 精度越高结果越准确\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n  * ja：日语\n- unit: 度量单位系统（可选参数，默认m）\n  * m：公制单位\n  * i：英制单位\n使用示例：\n- 格点逐小时天气预报 24h 116.4074,39.9042\n- 格点逐小时天气预报 72h -74.0059,40.7128 en\n应用场景：\n- 精确位置短期天气规划\n- 户外活动详细安排\n- 专业气象研究\n注意事项：\n- 必须使用经纬度坐标\n- 24小时预报准确度最高\n- 数据更新频率高",

        "分钟级降水": "【分钟级降水 帮助】\n功能：查询未来2小时内每5分钟的降水预报\n用法：分钟级降水 location [lang]\n参数详解：\n- location: 精确经纬度坐标（必选参数）\n  * 格式必须为\"经度,纬度\"\n  * 如\"116.4074,39.9042\"（北京）\n  * 精度影响预报准确性\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n  * ja：日语\n使用示例：\n- 分钟级降水 116.4074,39.9042\n- 分钟级降水 -74.0059,40.7128 en\n- 分钟级降水 139.6917,35.6895 ja\n预报特点：\n- 时间分辨率：每5分钟一个预报点\n- 预报时长：未来2小时\n- 预报内容：降水量（毫米）\n适用场景：\n- 短期出行决策\n- 户外活动安排\n- 交通路况预判\n注意事项：\n- 仅支持经纬度坐标查询\n- 预报时效性很强\n- 临近预报准确度较高",

        "实时天气预警": "【实时天气预警 帮助】\n功能：查询指定坐标的当前天气预警信息\n用法：实时天气预警 latitude longitude [localTime] [lang]\n参数详解：\n- latitude: 纬度坐标（必选参数）\n  * 数值范围：-90到90\n  * 如39.9042（北京纬度）\n  * 51.5074（伦敦纬度）\n- longitude: 经度坐标（必选参数）\n  * 数值范围：-180到180\n  * 如116.4074（北京经度）\n  * -0.1278（伦敦经度）\n- localTime: 是否返回本地时间（可选参数，默认false）\n  * true：返回当地时间\n  * false：返回UTC时间\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n  * ja：日语\n使用示例：\n- 实时天气预警 39.9042 116.4074\n- 实时天气预警 31.2304 121.4737 true zh\n- 实时天气预警 51.5074 -0.1278 false en\n预警类型：\n- 暴雨预警\n- 台风预警\n- 暴雪预警\n- 大风预警\n- 高温预警\n- 其他气象灾害预警\n注意事项：\n- 纬度和经度均为必填参数\n- 坐标精度影响预警范围判断\n- 无预警时返回\"当前无天气预警\"",

        "天气指数预报": "【天气指数预报 帮助】\n功能：查询各类生活气象指数预报\n用法：天气指数预报 days location type [lang]\n参数详解：\n- days: 预报天数（必选参数）\n  * 1d：未来1天指数预报\n  * 3d：未来3天指数预报\n- location: 查询位置标识（必选参数）\n  * LocationID：如\"101010100\"\n  * 经纬度坐标：如\"116.4074,39.9042\"\n- type: 指数类型ID（可选参数，默认0）\n  * 0：返回所有指数类型\n  * 1：运动指数\n  * 2：洗车指数\n  * 3：穿衣指数\n  * 4：钓鱼指数\n  * 5：紫外线指数\n  * 6：旅游指数\n  * 其他具体指数ID\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n使用示例：\n- 天气指数预报 1d 101010100 0 zh\n- 天气指数预报 3d 116.4074,39.9042 5 en\n- 天气指数预报 1d 101020100\n指数类型说明：\n- 运动指数：适宜户外运动程度\n- 洗车指数：洗车适宜程度\n- 穿衣指数：着装建议\n- 钓鱼指数：钓鱼适宜程度\n- 紫外线指数：防晒建议\n- 旅游指数：出游适宜程度\n注意事项：\n- 不同地区指数种类可能不同\n- 指数等级分为多个级别\n- 提供生活指导建议",

        "实时空气质量": "【实时空气质量 帮助】\n功能：查询指定坐标的当前空气质量状况\n用法：实时空气质量 latitude longitude [lang]\n参数详解：\n- latitude: 纬度坐标（必选参数）\n  * 数值范围：-90到90\n  * 如39.9042（北京）\n  * 31.2304（上海）\n- longitude: 经度坐标（必选参数）\n  * 数值范围：-180到180\n  * 如116.4074（北京）\n  * 121.4737（上海）\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n使用示例：\n- 实时空气质量 39.9042 116.4074\n- 实时空气质量 31.2304 121.4737 en\n返回信息包含：\n- AQI指数数值\n- 空气质量等级\n- 首要污染物\n- PM2.5浓度\n- PM10浓度\n- SO2、NO2、CO、O3浓度\n- 数据发布时间\n空气质量等级：\n- 0-50：优\n- 51-100：良\n- 101-150：轻度污染\n- 151-200：中度污染\n- 201-300：重度污染\n- 300+：严重污染\n注意事项：\n- 纬度和经度均为必填\n- 数据来源于最近的监测站点\n- 更新频率约每小时一次",

        "空气质量每日预报": "【空气质量每日预报 帮助】\n功能：查询未来几天的空气质量预报\n用法：空气质量每日预报 latitude longitude [localTime] [lang]\n参数详解：\n- latitude: 纬度坐标（必选参数）\n  * 数值范围：-90到90\n  * 精确到小数点后4-6位\n- longitude: 经度坐标（必选参数）\n  * 数值范围：-180到180\n  * 精确到小数点后4-6位\n- localTime: 是否返回本地时间（可选参数，默认false）\n  * true：显示当地时区时间\n  * false：显示UTC时间\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n使用示例：\n- 空气质量每日预报 39.9042 116.4074\n- 空气质量每日预报 31.2304 121.4737 true zh\n- 空气质量每日预报 51.5074 -0.1278 false en\n预报内容：\n- 未来7天AQI预报\n- 每日空气质量等级\n- 主要污染物预测\n- 污染趋势分析\n适用场景：\n- 健康出行规划\n- 户外活动安排\n- 呼吸道疾病预防\n- 环境政策制定参考\n注意事项：\n- 预报准确度随时间延长而降低\n- 受气象条件影响较大\n- 仅供参考，以实际监测为准",

        "空气质量小时预报": "【空气质量小时预报 帮助】\n功能：查询未来24小时的空气质量逐小时变化\n用法：空气质量小时预报 latitude longitude [localTime] [lang]\n参数详解：\n- latitude: 纬度坐标（必选参数）\n  * 数值范围：-90到90\n  * 建议精确到小数点后4位以上\n- longitude: 经度坐标（必选参数）\n  * 数值范围：-180到180\n  * 建议精确到小数点后4位以上\n- localTime: 是否返回本地时间（可选参数，默认false）\n  * true：显示当地时间\n  * false：显示UTC时间\n- lang: 多语言设置（可选参数，默认zh）\n  * zh：简体中文\n  * en：英语\n使用示例：\n- 空气质量小时预报 39.9042 116.4074\n- 空气质量小时预报 31.2304 121.4737 true zh\n- 空气质量小时预报 40.7128 -74.0060 false en\n预报特点：\n- 时间分辨率：每小时一个预报点\n- 预报时长：未来24小时\n- 预报指标：AQI、主要污染物浓度\n应用场景：\n- 短期健康防护安排\n- 户外运动时间选择\n- 通勤路线规划\n- 敏感人群活动调整\n注意事项：\n- 短期预报准确度相对较高\n- 受气象条件变化影响\n- 临近时段预报更可靠\n- 数据更新及时",

        "天气统计": "【天气统计 帮助】\n功能：查看天气API的使用统计信息\n用法：天气统计\n功能说明：\n此命令无需参数，直接执行即可\n返回信息包含：\n- 今日API调用次数及剩余次数\n- 本月API调用总量\n- 调用最多的用户和群组\n- API使用趋势分析\n统计维度：\n- 按用户统计：各用户调用次数排名\n- 按群组统计：各群组调用次数排名\n- 按时间统计：日/月调用趋势\n使用示例：\n- 天气统计\n适用对象：\n- 所有用户均可查看\n- 主人可查看详细统计\n- 普通用户查看基本统计\n注意事项：\n- 统计数据每日更新\n- 有助于合理使用API资源\n- 超过限制会有相应提示",

        "天气开关": "【天气开关 帮助】\n功能：控制天气API服务的开启与关闭状态\n用法：天气开关 [开启|关闭]\n权限说明：\n⚠️ 此命令仅机器人主人可以使用\n⚠️ 普通用户无权执行此操作\n参数说明：\n- 开启：启用天气API服务\n  * 恢复所有用户正常使用\n  * 重新计算调用次数限制\n  * 恢复天气查询功能\n- 关闭：禁用天气API服务\n  * 除主人外其他用户无法使用\n  * 保留统计功能\n  * 节约API调用资源\n使用示例：\n- 天气开关 开启\n- 天气开关 关闭\n操作效果：\n开启时：\n- 所有用户可正常使用天气功能\n- 按照配置的限制次数执行\n- 显示正常的天气信息\n关闭时：\n- 仅主人可继续使用天气功能\n- 其他用户收到\"天气API调用已关闭\"提示\n- 统计功能仍然可用\n注意事项：\n- 操作前请确认必要性\n- 关闭后请及时开启\n- 影响所有非主人用户的使用\n- 建议在API额度不足时使用"
    }

    return help_info.get(command_name, f"未知命令: {command_name}")


def is_weather_command(raw_message: str) -> tuple[bool, str, list]:
    """
    检查是否为天气命令（使用空格分隔参数）
    :param raw_message: 原始消息
    :return: (是否为天气命令, 命令名称, 参数列表)
    """
    if not WEATHER_API_AVAILABLE and not CMA_WEATHER_SUBSCRIBER_AVAILABLE:
        return False, "", []

    msg_parts = raw_message.strip().split()
    if not msg_parts:
        return False, "", []

    command_name = msg_parts[0].strip()
    args = [arg.strip() for arg in msg_parts[1:]] if len(msg_parts) > 1 else []
    
    # 如果别名系统可用，尝试解析别名
    if ALIAS_AVAILABLE and is_alias_enabled():
        resolved_command = resolve_command(command_name)
        if resolved_command != command_name:
            logging.info(f"别名解析: '{command_name}' -> '{resolved_command}'")
            command_name = resolved_command

    # 支持的命令列表
    supported_commands = [
        "城市搜索", "热门城市查询", "POI搜索", "实时天气", "每日天气预报", "逐小时天气预报",
        "格点实时天气", "格点每日天气预报", "格点逐小时天气预报", "分钟级降水", "实时天气预警",
        "天气指数预报", "实时空气质量", "空气质量每日预报", "空气质量小时预报",
        "天气统计", "天气开关",
        # CMA气象预警订阅命令
        "订阅预警", "取消订阅预警", "我的订阅",
        # 早晚安命令
        "早安", "晚安",
        # 测试命令
        "测试气象预警",
        # 别名管理命令
        "添加别名", "删除别名", "查看别名", "别名帮助"
    ]

    if command_name in supported_commands:
        return True, command_name, args

    return False, "", []


async def check_weather_api_limit(config: Dict[str, Any]) -> bool:
    """检查是否达到API调用限制"""
    from ws_handler import get_daily_usage_count

    daily_limit = config.get("weather_api_daily_limit", 1500)
    current_usage = await get_daily_usage_count()

    return current_usage < daily_limit


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

    # 处理特殊命令：天气统计
    if command_name == "天气统计":
        await handle_weather_stats(group_id, config)
        return

    # 处理特殊命令：天气开关
    if command_name == "天气开关":
        await handle_weather_toggle(args, group_id, user_id, config)
        return

    # 检查天气API是否启用
    if not config.get("weather_api_enabled", True):
        owner_id = config.get("owner_id", "")
        if not owner_id or user_id != owner_id:
            await send_group_msg(group_id, "天气API调用已关闭，仅主人可使用")
            return

    # 检查API调用限制
    if not await check_weather_api_limit(config):
        await send_group_msg(group_id, f"今日天气API调用已达上限（{config.get('weather_api_daily_limit', 1500)}次），请明天再试")
        return

    api = QWeatherAPI(config)

    try:
        # 记录API调用
        if user_id:
            from ws_handler import record_weather_api_usage
            await record_weather_api_usage(group_id, user_id, command_name, command_name)
        
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

            result = await api.poi_lookup(location, type_param, city, number, lang)
            if result:
                formatted_msg = format_weather_response("POI搜索", result, config)
                await send_group_msg(group_id, formatted_msg)
            else:
                await send_group_msg(group_id, "POI搜索失败")

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

        # CMA气象预警订阅相关命令
        elif command_name == "订阅预警":
            await handle_subscribe_warning(args, group_id, user_id, config)
        elif command_name == "取消订阅预警":
            await handle_unsubscribe_warning(args, group_id, user_id, config)
        elif command_name == "我的订阅":
            await handle_my_subscriptions(user_id, group_id)
        # 早晚安命令
        elif command_name in ["早安", "晚安"]:
            await handle_morning_evening_command(command_name, user_id, group_id, config)
        elif command_name == "测试气象预警":
            # 检查是否为主人
            owner_id = config.get("owner_id", "")
            if user_id != owner_id:
                await send_group_msg(group_id, "只有主人才能使用测试气象预警命令")
                return
            await handle_test_weather_alarm(args, group_id, user_id, config)

        else:
            await send_group_msg(group_id, f"未知的天气命令: {command_name}")

    except Exception as e:
        logging.error(f"处理天气命令异常: {e}")
        await send_group_msg(group_id, f"天气命令处理出错: {str(e)}")


async def handle_weather_stats(group_id: str, config: Dict[str, Any]) -> None:
    """处理天气统计命令"""
    try:
        from ws_handler import (
            get_daily_usage_count, get_monthly_usage_count,
            get_top_users_daily, get_top_users_monthly,
            get_top_groups_daily, get_top_groups_monthly
        )
        
        daily_count = await get_daily_usage_count()
        monthly_count = await get_monthly_usage_count()
        
        top_user_daily = await get_top_users_daily()
        top_user_monthly = await get_top_users_monthly()
        top_group_daily = await get_top_groups_daily()
        top_group_monthly = await get_top_groups_monthly()
        
        stats_msg = "【天气API使用统计】\n"
        stats_msg += f"今日调用次数: {daily_count}/{config.get('weather_api_daily_limit', 1500)}\n"
        stats_msg += f"本月调用次数: {monthly_count}\n\n"
        
        if top_user_daily:
            stats_msg += f"今日调用最多: 群{top_user_daily[0]} 用户{top_user_daily[1]} ({top_user_daily[2]}次)\n"
        else:
            stats_msg += "今日调用最多: 无数据\n"
            
        if top_user_monthly:
            stats_msg += f"本月调用最多: 群{top_user_monthly[0]} 用户{top_user_monthly[1]} ({top_user_monthly[2]}次)\n"
        else:
            stats_msg += "本月调用最多: 无数据\n"
            
        if top_group_daily:
            stats_msg += f"今日群组最多: 群{top_group_daily[0]} ({top_group_daily[1]}次)\n"
        else:
            stats_msg += "今日群组最多: 无数据\n"
            
        if top_group_monthly:
            stats_msg += f"本月群组最多: 群{top_group_monthly[0]} ({top_group_monthly[1]}次)\n"
        else:
            stats_msg += "本月群组最多: 无数据\n"
        
        await send_group_msg(group_id, stats_msg)
        
    except Exception as e:
        logging.error(f"获取天气统计失败: {e}")
        await send_group_msg(group_id, "获取天气统计信息失败")


async def handle_weather_toggle(args: list, group_id: str, user_id: str, config: Dict[str, Any]) -> None:
    """处理天气开关命令"""
    owner_id = config.get("owner_id", "")

    if not owner_id or user_id != owner_id:
        await send_group_msg(group_id, "只有主人才能控制天气API开关")
        return

    if not args:
        current_status = "开启" if config.get("weather_api_enabled", True) else "关闭"
        await send_group_msg(group_id, f"当前天气API状态: {current_status}\n使用 '天气开关 开启' 或 '天气开关 关闭' 来切换")
        return

    action = args[0].lower()
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')

    if action in ["开启", "开", "enable", "on"]:
        config["weather_api_enabled"] = True
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        await send_group_msg(group_id, "天气API已开启")

    elif action in ["关闭", "关", "disable", "off"]:
        config["weather_api_enabled"] = False
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        await send_group_msg(group_id, "天气API已关闭（仅主人可使用）")

    else:
        await send_group_msg(group_id, "无效操作，请使用 '开启' 或 '关闭'")


async def handle_subscribe_warning(args: list, group_id: str, user_id: str, config: Dict[str, Any]) -> None:
    """处理订阅预警命令"""
    if not CMA_WEATHER_SUBSCRIBER_AVAILABLE:
        await send_group_msg(group_id, "CMA气象预警订阅功能不可用")
        return

    if not args:
        await send_group_msg(group_id, "请提供要订阅的地区名称，格式为：省级行政区名称接上市级行政区名称接上县级行政区名称（可选）\n示例: 订阅预警 上海市上海市崇明区 或 订阅预警 广东省惠州市惠城区")
        return

    location = args[0].strip()
    if not location:
        await send_group_msg(group_id, "请输入有效的地区名称，格式为：省级行政区名称接上市级行政区名称接上县级行政区名称（可选）")
        return

    # 特殊处理：全国订阅
    if location == "全国":
        # 全国订阅使用特殊标识
        province = "全国"
        full_location = "全国"
    else:
        # 解析地区名称，格式为：省级行政区名称+市级行政区名称+县级行政区名称（可选）
        # 例如：上海市上海市崇明区 或 广东省惠州市惠城区
        
        # 使用更简单可靠的方法解析
        full_location = location
        
        # 验证基本格式：至少包含两个分隔符（省/市 和 市/区）
        separators = ['省', '市', '自治区', '自治州', '盟', '区', '县', '旗']
        separator_count = sum(1 for sep in separators if sep in location)
        
        if separator_count < 2:
            await send_group_msg(group_id, "地区名称格式错误，请使用：省级行政区名称+市级行政区名称+县级行政区名称（可选）\n示例: 订阅预警 上海市上海市崇明区 或 订阅预警 广东省惠州市惠城区\n特殊选项: 订阅预警 全国 (接收所有预警)")
            return
        
        # 提取省份信息
        subscriber = get_subscriber()
        if not subscriber:
            await send_group_msg(group_id, "订阅服务未初始化")
            return
        province = subscriber.extract_province_from_location(location)
        if not province:
            await send_group_msg(group_id, "无法识别的地区格式，请检查输入是否正确")
            return

    subscriber = get_subscriber()
    if not subscriber:
        await send_group_msg(group_id, "订阅服务未初始化")
        return

    # 根据订阅类型选择不同的订阅方法
    if location == "全国":
        success = await subscriber.subscribe_nationwide(group_id, user_id)
    else:
        success = await subscriber.subscribe_location(location, group_id, user_id)
    if success:
        await send_group_msg(group_id, f"成功订阅 {location} 的气象预警！当该地区发布气象预警时，将会在此群通知您。")
    else:
        await send_group_msg(group_id, f"订阅 {location} 的气象预警失败，请重试。")


async def handle_unsubscribe_warning(args: list, group_id: str, user_id: str, config: Dict[str, Any]) -> None:
    """处理取消订阅预警命令"""
    if not CMA_WEATHER_SUBSCRIBER_AVAILABLE:
        await send_group_msg(group_id, "CMA气象预警订阅功能不可用")
        return

    if not args:
        await send_group_msg(group_id, "请指定要取消订阅的地区，例如：取消订阅预警 广东 或 取消订阅预警 广东深圳南山")
        return

    location = args[0]
    
    # 特殊处理：全国订阅
    if location == "全国":
        subscriber = get_subscriber()
        if not subscriber:
            await send_group_msg(group_id, "订阅服务未初始化")
            return
        
        success = await subscriber.unsubscribe_nationwide(group_id, user_id)
        if success:
            await send_group_msg(group_id, "已取消订阅全国气象预警。")
        else:
            await send_group_msg(group_id, "取消订阅全国气象预警失败，请重试。")
        return
    
    # 判断是传统省份格式还是新的省市区格式
    separators = ['省', '市', '自治区', '自治州', '盟', '区', '县', '旗']
    separator_count = sum(1 for sep in separators if sep in location)
    
    if separator_count >= 2:  # 是新的省市区格式
        # 尝试取消地区订阅
        subscriber = get_subscriber()
        if not subscriber:
            await send_group_msg(group_id, "订阅服务未初始化")
            return

        success = await subscriber.unsubscribe_location(location, group_id, user_id)
        if success:
            await send_group_msg(group_id, f"已取消订阅 {location} 的气象预警。")
        else:
            await send_group_msg(group_id, f"取消订阅 {location} 的气象预警失败，请重试。")
    else:
        # 验证省份名称（传统格式）
        valid_provinces = [
            "北京", "天津", "上海", "重庆",
            "河北", "山西", "辽宁", "吉林", "黑龙江",
            "江苏", "浙江", "安徽", "福建", "江西", "山东",
            "河南", "湖北", "湖南", "广东", "海南",
            "四川", "贵州", "云南", "陕西", "甘肃", "青海",
            "内蒙古", "广西", "西藏", "宁夏", "新疆",
            "香港", "澳门", "台湾"
        ]
        
        if location not in valid_provinces:
            await send_group_msg(group_id, f"无效的省份名称：{location}")
            return

        subscriber = get_subscriber()
        if not subscriber:
            await send_group_msg(group_id, "订阅服务未初始化")
            return

        success = await subscriber.unsubscribe_province(location, group_id, user_id)
        if success:
            await send_group_msg(group_id, f"已取消订阅 {location} 的气象预警。")
        else:
            await send_group_msg(group_id, f"取消订阅 {location} 的气象预警失败，请重试。")


async def handle_my_subscriptions(user_id: str, group_id: str) -> None:
    """处理查询我的订阅命令"""
    if not CMA_WEATHER_SUBSCRIBER_AVAILABLE:
        await send_group_msg(group_id, "CMA气象预警订阅功能不可用")
        return

    subscriber = get_subscriber()
    if not subscriber:
        await send_group_msg(group_id, "订阅服务未初始化")
        return

    subscriptions = await subscriber.get_user_subscriptions(user_id)
    
    if not subscriptions:
        await send_group_msg(group_id, "您目前没有订阅任何地区的气象预警。")
        return

    subscription_list = []
    for display_name, sub_group_id, location_type in subscriptions:
        # 如果是在同一个群聊中订阅的，直接显示
        if sub_group_id == group_id:
            subscription_list.append(display_name)
        else:
            # 如果在其他群聊中订阅的，显示群号信息
            subscription_list.append(f"{display_name}(群{sub_group_id})")

    if subscription_list:
        await send_group_msg(group_id, f"您订阅的气象预警地区：\n{', '.join(subscription_list)}")
    else:
        await send_group_msg(group_id, "您在当前群聊中没有订阅任何地区的气象预警。")


async def handle_morning_evening_command(command_name: str, user_id: str, group_id: str, config: Dict[str, Any]) -> None:
    """处理早晚安命令"""
    try:
        from morning_evening import handle_morning_evening_command as me_handler
        success = await me_handler(command_name, user_id, group_id, config)
        if not success:
            logging.warning(f"早晚安命令处理失败: {command_name} 用户 {user_id}")
    except Exception as e:
        logging.error(f"处理早晚安命令异常: {e}")
        from message_sender import send_group_msg_with_at
        await send_group_msg_with_at(group_id, "命令处理出错，请稍后再试", user_id)

async def handle_test_weather_alarm(args: list, group_id: str, user_id: str, config: Dict[str, Any]) -> None:
    """处理测试气象预警命令"""
    if not CMA_WEATHER_SUBSCRIBER_AVAILABLE:
        await send_group_msg(group_id, "CMA气象预警订阅功能不可用")
        return
    
    subscriber = get_subscriber()
    if not subscriber:
        await send_group_msg(group_id, "订阅服务未初始化")
        return
    
    try:
        # 获取最新的气象预警
        latest_alarms = subscriber.client.get_latest_alarms(count=1)
        
        if not latest_alarms:
            await send_group_msg(group_id, "未获取到最新的气象预警信息")
            return
        
        latest_alarm = latest_alarms[0]
        await send_group_msg(group_id, f"正在测试最新的气象预警推送...\n预警标题: {latest_alarm.get('title', '未知标题')}\n发布时间: {latest_alarm.get('issuetime', '未知时间')}")
        
        # 获取预警详情
        alarm_detail = subscriber.client.get_alarm_detail(latest_alarm.get('url', ''))
        if not alarm_detail:
            await send_group_msg(group_id, "获取预警详情失败")
            return
        
        # 模拟检查订阅并推送的逻辑
        matched_subscribers = []
        
        # 检查所有订阅者
        for location_key, subscribers_list in subscriber.subscribers.items():
            # 检查省份匹配
            if subscriber.extract_province_from_title(latest_alarm.get('title', '')):
                for sub_group_id, sub_user_id in subscribers_list:
                    if sub_group_id == group_id:  # 只推送给当前群
                        matched_subscribers.append((location_key, sub_user_id))
        
        # 检查地区订阅
        for full_location, subscribers_list in subscriber.location_subscribers.items():
            # 简单匹配逻辑（实际应该更复杂）
            if full_location in latest_alarm.get('title', ''):
                for sub_group_id, sub_user_id in subscribers_list:
                    if sub_group_id == group_id:  # 只推送给当前群
                        matched_subscribers.append((full_location, sub_user_id))
        
        if matched_subscribers:
            # 构建推送消息
            message, icon_path = await subscriber.build_warning_message(latest_alarm, alarm_detail, user_id, group_id)
            # 使用复合消息发送函数，在同一消息中发送文本和图片，并正确@用户
            from message_sender import send_group_msg_with_text_and_image
            await send_group_msg_with_text_and_image(group_id, message, icon_path, user_id)
            await send_group_msg(group_id, f"测试完成！共匹配到 {len(matched_subscribers)} 个订阅者")
        else:
            await send_group_msg(group_id, "测试完成！当前群没有匹配的订阅者")
            
    except Exception as e:
        logging.error(f"测试气象预警命令执行失败: {e}")
        await send_group_msg(group_id, f"测试命令执行失败: {str(e)}")


# 别名管理命令处理函数
async def handle_add_alias(args: list, group_id: str, user_id: str, config: Dict[str, Any]) -> None:
    """处理添加别名命令"""
    if not ALIAS_AVAILABLE:
        await send_group_msg(group_id, "别名功能未启用")
        return
    
    if len(args) < 2:
        await send_group_msg(group_id, "用法: 添加别名 [别名] [原始命令]\n示例: 添加别名 cs 城市搜索")
        return
    
    alias = args[0].strip()
    original_command = args[1].strip()
    
    # 检查权限（只有主人才能添加别名）
    owner_id = config.get("owner_id", "")
    if not owner_id or user_id != owner_id:
        await send_group_msg(group_id, "只有主人才能添加别名")
        return
    
    # 调用别名处理模块添加别名
    from alias_handler import add_alias
    success = add_alias(alias, original_command)
    
    if success:
        await send_group_msg(group_id, f"✅ 成功添加别名: '{alias}' -> '{original_command}'")
    else:
        await send_group_msg(group_id, f"❌ 添加别名失败: 别名 '{alias}' 可能已存在或原始命令无效")


async def handle_remove_alias(args: list, group_id: str, user_id: str, config: Dict[str, Any]) -> None:
    """处理删除别名命令"""
    if not ALIAS_AVAILABLE:
        await send_group_msg(group_id, "别名功能未启用")
        return
    
    if len(args) < 1:
        await send_group_msg(group_id, "用法: 删除别名 [别名]\n示例: 删除别名 cs")
        return
    
    alias = args[0].strip()
    
    # 检查权限（只有主人才能删除别名）
    owner_id = config.get("owner_id", "")
    if not owner_id or user_id != owner_id:
        await send_group_msg(group_id, "只有主人才能删除别名")
        return
    
    # 调用别名处理模块删除别名
    from alias_handler import remove_alias
    success = remove_alias(alias)
    
    if success:
        await send_group_msg(group_id, f"✅ 成功删除别名: '{alias}'")
    else:
        await send_group_msg(group_id, f"❌ 删除别名失败: 别名 '{alias}' 不存在")


async def handle_list_aliases(group_id: str) -> None:
    """处理查看别名命令"""
    if not ALIAS_AVAILABLE:
        await send_group_msg(group_id, "别名功能未启用")
        return
    
    from alias_handler import list_aliases, is_alias_enabled
    
    if not is_alias_enabled():
        await send_group_msg(group_id, "别名系统当前已禁用")
        return
    
    aliases = list_aliases()
    
    if not aliases:
        await send_group_msg(group_id, "当前没有任何别名")
        return
    
    # 构建别名列表消息
    alias_list = "=== 当前别名列表 ===\n\n"
    aliases_dict = list_aliases()
    
    # 按原命令分组显示
    for original_command, alias_list_items in sorted(aliases_dict.items()):
        if alias_list_items:  # 只显示有别名的命令
            alias_list += f"{original_command}:\n"
            for alias in alias_list_items:
                alias_list += f"  • {alias}\n"
            alias_list += "\n"
    
    alias_list += f"总计: {sum(len(aliases) for aliases in aliases_dict.values())} 个别名，映射到 {len([cmd for cmd, aliases in aliases_dict.items() if aliases])} 个原命令"
    
    # 使用合并转发发送长文本
    await send_forward_msg(group_id, alias_list)


async def handle_alias_help(group_id: str) -> None:
    """处理别名帮助命令"""
    if not ALIAS_AVAILABLE:
        await send_group_msg(group_id, "别名功能未启用")
        return
    
    from alias_handler import get_alias_help
    help_text = get_alias_help()
    await send_group_msg(group_id, help_text)


async def is_uapi_command(raw_message: str) -> tuple[bool, str, list]:
    """
    检查是否为UAPI命令（使用空格分隔参数）
    :param raw_message: 原始消息
    :return: (是否为UAPI命令, 命令名称, 参数列表)
    """
    if not UAPI_AVAILABLE:
        return False, "", []

    msg_parts = raw_message.strip().split()
    if not msg_parts:
        return False, "", []

    command_name = msg_parts[0].strip()
    args = [arg.strip() for arg in msg_parts[1:]] if len(msg_parts) > 1 else []
    
    # 如果别名系统可用，尝试解析别名
    if ALIAS_AVAILABLE and is_alias_enabled():
        resolved_command = resolve_command(command_name)
        if resolved_command != command_name:
            logging.info(f"别名解析: '{command_name}' -> '{resolved_command}'")
            command_name = resolved_command

    # 支持的UAPI命令列表
    supported_commands = [
        # 社交类 API
        "B站直播间查询", "B站用户查询", "B站投稿查询", "GitHub仓库查询",
        
        # 杂项类 API
        "热榜查询", "世界时间查询", "天气查询", "手机归属地查询", "随机数生成",
        "程序员历史上的今天", "程序员历史事件",
        
        # 网络类 API
        "ICP备案查询", "IP信息查询", "WHOIS查询", "Ping主机", "DNS查询", 
        "URL可访问性", "端口扫描",
        
        # 游戏类 API
        "MC服务器查询", "Steam用户查询", "Epic免费游戏", "MC玩家查询",
        
        # 文本类 API
        "MD5哈希", "MD5校验", "Base64编码", "Base64解码", 
        "AES加密", "AES解密", "AES高级加密", "AES高级解密", "格式转换",
        
        # 随机类 API
        "随机图片", "答案之书", "随机字符串",
        
        # 图像类 API
        "必应壁纸", "上传图片", "图片转Base64", "生成二维码", "GrAvatar头像", 
        "摸摸头", "生成你们怎么不说话了表情包",
        
        # 翻译类 API
        "翻译",
        
        # 诗词类 API
        "一言",
        
        # 网页解析类 API
        "网页元数据提取",
        
        # 转换类 API
        "时间戳转换", "JSON格式化",
        
        # 日常类 API
        "每日新闻图"
    ]

    if command_name in supported_commands:
        return True, command_name, args

    return False, "", []


async def handle_command(event: Dict[str, Any], config: Dict[str, Any]) -> None:
    """
    处理命令（包括测试命令、帮助命令、广播命令、天气命令和UAPI命令）
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
    user_id = str(event.get("user_id", ""))

    logging.debug(f"收到消息: '{raw_message}' 来自群 {group_id} 用户 {user_id}")

    # 检查是否为广播命令（仅限主人）
    if raw_message == "/broadcast" or raw_message == "/群发":
        owner_id = config.get("owner_id", "")
        if user_id != owner_id:
            await send_group_msg(group_id, "只有主人才能使用群发功能")
            return
        
        # 启动广播模式
        from bydbot import get_broadcast_mode
        broadcast_mode = get_broadcast_mode()
        broadcast_mode[user_id] = True
        
        await send_group_msg(group_id, "已进入广播模式，请发送您要群发的消息（发送'0'退出广播模式）")
        return

    # 检查用户是否处于广播模式
    from bydbot import get_broadcast_mode
    broadcast_mode = get_broadcast_mode()
    if user_id in broadcast_mode and broadcast_mode[user_id]:
        if raw_message == "0":
            # 退出广播模式
            broadcast_mode[user_id] = False
            await send_group_msg(group_id, "已退出广播模式")
            return
        
        # 发送消息到所有群
        await broadcast_message_to_all_groups(raw_message, config, group_id, user_id)
        return

    # 检查是否为帮助命令
    if is_help_command_event(event, config):
        logging.info(f"收到帮助命令来自群 {group_id}")
        
        # 获取help配置
        help_config = config.get("help", {})
        help_image_enabled = help_config.get("image_enabled", True)
        help_text_enabled = help_config.get("text_enabled", False)
        
        # 如果两个都为false，则停用help命令
        if not help_image_enabled and not help_text_enabled:
            return  # 停用help命令
        
        # 如果text_enabled为true，则发送文字帮助
        if help_text_enabled and not help_image_enabled:
            from help_message import get_help_file_path, get_uapi_help_message
            
            # 根据配置决定使用哪种帮助内容
            help_config = config.get("help", {})
            use_uapi_help = help_config.get("use_uapi_help", False)
            
            if use_uapi_help:
                # 使用简化的UAPI帮助
                help_content = get_uapi_help_message()
            else:
                # 使用完整的帮助文件
                help_file_path = get_help_file_path(config)
                try:
                    with open(help_file_path, 'r', encoding='utf-8') as f:
                        help_content = f.read()
                except FileNotFoundError:
                    # 如果主帮助文件不存在，使用UAPI帮助作为后备
                    help_content = get_uapi_help_message()
                except Exception as e:
                    logging.error(f"读取帮助文件失败: {e}")
                    await send_group_msg(group_id, "帮助文件读取失败")
                    return
            
            # 使用合并转发发送长文本
            await send_forward_msg(group_id, help_content)
            return
        
        # 如果image_enabled为true，则发送帮助图片
        if help_image_enabled:
            # 获取图片路径列表
            image_paths = help_config.get("image_paths", ["help命令.png"])
            sent_any = False
            
            for image_path in image_paths:
                # 如果路径不是绝对路径，则相对于主程序目录
                if not os.path.isabs(image_path):
                    image_path = os.path.join(os.path.dirname(__file__), image_path)
                
                if os.path.exists(image_path):
                    success = await send_group_img(group_id, image_path)
                    if success:
                        sent_any = True
                    else:
                        logging.warning(f"帮助图片发送失败: {image_path}")
                else:
                    logging.warning(f"帮助图片文件不存在: {image_path}")
            
            if not sent_any:
                await send_group_msg(group_id, "帮助图片发送失败，请联系管理员")
        return

    # 检查是否为测试命令
    if is_valid_test_command_event(event, config):
        # 检查是否为主人
        owner_id = config.get("owner_id", "")
        if user_id != owner_id:
            await send_group_msg(group_id, "只有主人才能使用测试命令")
            return
            
        test_cmd = config.get("test_command", "/eqtest")

        logging.info(f"收到测试命令 {test_cmd} 来自群 {group_id} 用户 {user_id}")

        # 创建并发送测试数据（直接发送，不经过数据库处理）
        test_data_list = create_test_earthquake_data()

        for test_data in test_data_list:
            await send_test_message(test_data, group_id, config)
        return

    # 检查是否为天气命令（直接匹配命令名称，使用空格分隔）
    is_weather, command_name, args = is_weather_command(raw_message)

    if is_weather:
        logging.debug(f"识别为天气命令: {command_name}, 参数: {args}")
        # 检查是否只在配置的群组中响应命令
        if config.get("test_groups_only", True) and group_id not in config.get("groups", {}):
            logging.debug(f"群 {group_id} 不在配置的群组列表中，忽略命令")
            return

        # 获取用户ID用于统计
        user_id = str(event.get("user_id", ""))

        logging.info(f"收到天气命令 {raw_message} 来自群 {group_id} 用户 {user_id}")
        await handle_weather_command(command_name, args, group_id, config, user_id)
    else:
        logging.debug(f"不是有效的天气命令: {raw_message}")

        # 检查是否为UAPI命令
        is_uapi, uapi_command_name, uapi_args = await is_uapi_command(raw_message)

        if is_uapi:
            logging.debug(f"识别为UAPI命令: {uapi_command_name}, 参数: {uapi_args}")
            
            # 特殊处理：如果是"摸摸头"命令，尝试提取@的QQ号
            if uapi_command_name == "摸摸头":
                # 检查参数是否为空或者是CQ码
                if not uapi_args:
                    # 尝试从消息中提取@的QQ号
                    at_qq = extract_qq_from_at(event)
                    if at_qq:
                        uapi_args = [at_qq]
                        logging.info(f"从消息中提取到@的QQ号: {at_qq}")
                elif uapi_args and uapi_args[0].startswith('[CQ:at,'):
                    # 第一个参数是CQ码，提取QQ号
                    _, cq_codes = parse_cq_code(uapi_args[0])
                    for cq in cq_codes:
                        if cq['type'] == 'at':
                            qq = cq['data'].get('qq')
                            if qq and qq != 'all':
                                uapi_args = [qq]
                                logging.info(f"从CQ码中提取到QQ号: {qq}")
                                break
            
            # 特殊处理：如果是"翻译"命令或文本类API，处理单引号括起来的文本
            text_api_commands = ["MD5哈希", "MD5校验", "Base64编码", "Base64解码", "AES加密", "AES解密", "AES高级加密", "AES高级解密", "格式转换"]
            if (uapi_command_name == "翻译" and len(uapi_args) > 1) or (uapi_command_name in text_api_commands and len(uapi_args) >= 1):
                # 重新解析原始消息，正确处理单引号
                import shlex
                try:
                    # 使用shlex.split来正确处理引号
                    # 移除命令名称，只保留参数部分
                    raw_params = raw_message[len(uapi_command_name):].strip()
                    parsed_args = shlex.split(raw_params)
                    if len(parsed_args) >= 1:
                        uapi_args = parsed_args
                        logging.info(f"{uapi_command_name}命令参数已重新解析: {uapi_args}")
                except Exception as e:
                    logging.warning(f"{uapi_command_name}命令参数解析失败，使用原始参数: {e}")
                    # 解析失败时使用原始参数
            
            # 检查是否只在配置的群组中响应命令
            if config.get("test_groups_only", True) and group_id not in config.get("groups", {}):
                logging.debug(f"群 {group_id} 不在配置的群组列表中，忽略UAPI命令")
                return

            # 获取用户ID用于统计
            user_id = str(event.get("user_id", ""))

            logging.info(f"收到UAPI命令 {raw_message} 来自群 {group_id} 用户 {user_id}")
            try:
                # 修改处理逻辑以支持图片和其他类型的数据
                result = await handle_uapi_command(uapi_command_name, uapi_args, group_id, config, user_id)
                
                # 检查返回结果的类型
                if isinstance(result, dict):
                    # 检查是否是包含文本和图片路径的特殊格式（如B站用户查询）
                    if result.get("type") == "uapi_bilibili_user" and "text" in result:
                        text_info = result["text"]
                        image_path = result.get("image_path")
                        
                        # 先发送文本信息
                        await send_group_msg(group_id, text_info)
                        
                        # 如果有图片路径，发送图片
                        if image_path and os.path.exists(image_path):
                            success = await send_group_img(group_id, image_path)
                            if not success:
                                logging.warning(f"发送B站用户头像失败: {image_path}")
                            
                            # 发送完后删除临时文件
                            try:
                                os.unlink(image_path)
                            except Exception as e:
                                logging.warning(f"删除临时头像文件失败 {image_path}: {e}")
                    else:
                        # 其他字典类型，按字符串处理
                        await send_group_msg(group_id, str(result))
                elif isinstance(result, tuple):
                    # 如果返回的是元组，第一个元素是消息类型，第二个是数据
                    msg_type, data = result
                    if msg_type == 'image' and data:
                        # 发送图片
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                            tmp_file.write(data)
                            tmp_file_path = tmp_file.name
                        
                        success = await send_group_img(group_id, tmp_file_path)
                        os.unlink(tmp_file_path)  # 删除临时文件
                        
                        if not success:
                            await send_group_msg(group_id, f"发送{uapi_command_name}图片失败")
                    elif msg_type == 'text' and data:
                        await send_group_msg(group_id, data)
                    else:
                        await send_group_msg(group_id, f"UAPI命令 {uapi_command_name} 执行失败或无返回结果")
                elif isinstance(result, str) and not result:
                    # 对于返回空字符串的命令，不发送额外消息（如MC玩家查询已发送文本和图片）
                    pass
                elif isinstance(result, bytes):
                    # 如果返回的是字节数据（图片），保存到临时文件并发送
                    import tempfile
                    tmp_file_path = None
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                            tmp_file.write(result)
                            tmp_file_path = tmp_file.name
                        
                        success = await send_group_img(group_id, tmp_file_path)
                        
                        if not success:
                            await send_group_msg(group_id, f"发送{uapi_command_name}图片失败")
                    finally:
                        # 确保临时文件被删除
                        if tmp_file_path and os.path.exists(tmp_file_path):
                            try:
                                os.unlink(tmp_file_path)
                            except Exception as e:
                                logging.warning(f"删除临时文件失败 {tmp_file_path}: {e}")
                elif result:
                    # 如果返回的是字符串，直接发送
                    await send_group_msg(group_id, result)
                else:
                    await send_group_msg(group_id, f"UAPI命令 {uapi_command_name} 执行失败或无返回结果")
            except Exception as e:
                logging.error(f"处理UAPI命令异常: {e}")
                await send_group_msg(group_id, f"UAPI命令处理出错: {str(e)}")
        # 只有当消息明确是UAPI命令格式但UAPI不可用时才显示错误
        elif UAPI_AVAILABLE and raw_message.strip():
            first_word = raw_message.strip().split()[0].strip()
            # 检查是否是潜在的UAPI命令前缀
            potential_uapi_commands = [
                # 社交类 API
                "B站直播间查询", "B站用户查询", "B站投稿查询", "GitHub仓库查询",
                
                # 杂项类 API
                "热榜查询", "世界时间查询", "天气查询", "手机归属地查询", "随机数生成",
                "程序员历史上的今天", "程序员历史事件",
                
                # 网络类 API
                "ICP备案查询", "IP信息查询", "WHOIS查询", "Ping主机", "DNS查询", 
                "URL可访问性", "端口扫描",
                
                # 游戏类 API
                "MC服务器查询", "Steam用户查询", "Epic免费游戏", "MC玩家查询",
                
                # 文本类 API
                "MD5哈希", "MD5校验", "Base64编码", "Base64解码", 
                "AES加密", "AES解密", "AES高级加密", "AES高级解密", "格式转换",
                
                # 随机类 API
                "随机图片", "答案之书", "随机字符串",
                
                # 图像类 API
                "必应壁纸", "上传图片", "图片转Base64", "生成二维码", "GrAvatar头像", 
                "摸摸头", "生成摸摸头GIF", "生成你们怎么不说话了表情包",
                
                # 翻译类 API
                "翻译",
                
                # 诗词类 API
                "一言",
                
                # 网页解析类 API
                "网页元数据提取", "网页图片提取",
                
                # 转换类 API
                "时间戳转换", "JSON格式化",
                
                # 日常类 API
                "每日新闻图"
            ]
            
            if first_word in potential_uapi_commands:
                await send_group_msg(group_id, "UAPI功能未启用，请检查配置")
        # 其他情况（如地震消息）直接忽略，不显示任何错误信息
        return


async def broadcast_message_to_all_groups(message: str, config: Dict[str, Any], source_group: str, user_id: str) -> None:
    """
    将消息广播到所有群
    :param message: 要广播的消息
    :param config: 配置
    :param source_group: 消息来源群
    :param sender_user: 发送者用户ID
    """
    groups = config.get("groups", {})
    success_count = 0
    fail_count = 0
    
    await send_group_msg(source_group, f"开始向 {len(groups)} 个群发送消息...")
    
    for target_group in groups.keys():
        try:
            # 避免向原群重复发送
            if target_group != source_group:
                success = await send_group_msg(target_group, message)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            else:
                success_count += 1  # 计入成功，因为原群不需要发送
        except Exception as e:
            logging.error(f"向群 {target_group} 发送广播消息失败: {e}")
            fail_count += 1
    
    result_msg = f"广播完成！成功: {success_count} 个群，失败: {fail_count} 个群"
    await send_group_msg(source_group, result_msg)