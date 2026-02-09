"""
Bydbot - 多功能信息推送机器人
主程序入口
"""

import asyncio
import json
import logging
import os
import signal
import sys
from typing import Dict, Any

import websockets

# 检查CMA气象预警订阅模块是否可用
try:
    import cma_weather_subscriber
    CMA_WEATHER_SUBSCRIBER_AVAILABLE = True
except ImportError:
    CMA_WEATHER_SUBSCRIBER_AVAILABLE = False

# 设置事件循环策略（Windows兼容性）
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 全局变量用于跟踪广播模式
broadcast_mode = {}  # {user_id: True} 表示该用户处于广播模式

# UAPI可用性标志
UAPI_AVAILABLE = True

# 用于在模块间共享状态
def get_broadcast_mode():
    return broadcast_mode


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件 {config_path} 不存在，请创建 config.json")

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def setup_logging(log_file: str) -> None:
    """设置日志"""
    # 确保data目录存在
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)

    # 如果日志文件在根目录，移动到data目录
    if not log_file.startswith(os.path.join(data_dir, '')):
        log_file = os.path.join(data_dir, os.path.basename(log_file))

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a', encoding='utf-8'),
            logging.StreamHandler()  # 同时输出到控制台
        ]
    )


async def init_db():
    """初始化数据库 - 委托给ws_handler"""
    from ws_handler import init_db as ws_init_db
    return await ws_init_db()


async def load_recent_ids_from_db():
    """从数据库加载最近的ID - 委托给ws_handler"""
    from ws_handler import load_recent_ids_from_db as ws_load_recent_ids
    return await ws_load_recent_ids()


async def close_sender():
    """关闭消息发送器"""
    from message_sender import close_sender as close_msg_sender
    await close_msg_sender()


async def init_sender(napcat_url: str, token: str):
    """初始化消息发送器"""
    from message_sender import init_sender as init_msg_sender
    await init_msg_sender(napcat_url, token)


async def napcat_ws_handler(websocket, path, config):
    """处理NapCat WebSocket连接"""
    from command_handler import handle_command
    
    async for message in websocket:
        try:
            event = json.loads(message)
            await handle_command(event, config)
        except Exception as e:
            logging.error(f"NapCat WebSocket 处理错误: {e}")


async def connect_to_fan_ws(config):
    """连接到FAN WebSocket"""
    from ws_handler import connect_to_fan_ws as connect_fan
    await connect_fan(config)


async def periodic_cleanup():
    """定期清理任务"""
    from ws_handler import cleanup_processed_ids
    while True:
        try:
            # 每小时执行一次清理
            await asyncio.sleep(3600)
            await cleanup_processed_ids()
        except Exception as e:
            logging.error(f"定期清理任务出错: {e}")


def validate_config(config: Dict[str, Any]) -> bool:
    """验证配置文件的必要字段"""
    required_fields = ['napcat_http_url']
    for field in required_fields:
        if field not in config:
            logging.error(f"配置文件缺少必要字段: {field}")
            return False
    return True


async def shutdown_handler():
    """关闭处理程序"""
    logging.info("正在关闭Bydbot...")
    await close_sender()
    logging.info("Bydbot已关闭")


def get_help_message():
    """获取帮助信息"""
    # 从文件读取帮助信息
    try:
        help_file_path = os.path.join(os.path.dirname(__file__), 'help命令.txt')
        with open(help_file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # 如果文件不存在，返回默认帮助信息
        help_text = """=== Bydbot 帮助菜单 ===
    
 earthquak earthquake bot
  bydbot v2.0 - 多功能信息推送机器人
  
【地震信息】
• 自动推送全球地震信息（根据配置过滤）
• 支持多种数据源（CENC, CEA, JMA, USGS等）
• 实时地震地图绘制与推送

【天气信息】
• /天气统计 - 查看API使用统计
• /天气开关 [开启/关闭] - 控制天气API（仅主人）

【天气查询】
• /城市搜索 [城市名] - 搜索城市信息
• /热门城市查询 - 查询热门城市
• /POI搜索 [地点] [类型] - 搜索兴趣点
• /实时天气 [location] - 查询实时天气
• /每日天气预报 [天数] [location] - 查询天气预报
• /逐小时天气预报 [小时数] [location] - 查询小时预报
• /分钟级降水 [location] - 查询降水预报
• /实时天气预警 [lat] [lon] - 查询天气预警
• /实时空气质量 [lat] [lon] - 查询空气质量

【UAPI功能】
• /B站直播间查询 [mid/room_id] [ID] - 查询B站直播间
• /B站用户查询 [UID] - 查询B站用户信息
• /B站投稿查询 [mid] [关键词] [排序] [每页数量] [页码] - 查询B站用户投稿
• /GitHub仓库查询 [owner] [repo] - 查询GitHub仓库
• /热榜查询 [type] - 查询各平台热榜
• /世界时间查询 [city] - 查询世界时间
• /天气查询 [city] - 查询天气（UAPI）
• /手机归属地查询 [phone] - 查询手机号归属地
• /随机数生成 [min] [max] [count] - 生成随机数
• /ICP备案查询 [domain] - 查询域名ICP备案
• /IP信息查询 [ip] - 查询IP地理位置
• /一言 - 获取一句优美的话

【气象预警订阅】
• /订阅预警 [省份] - 订阅某省气象预警
• /取消订阅预警 [省份] - 取消订阅某省预警
• /我的订阅 - 查看个人订阅列表

【系统命令】
• /bydbottest - 运行测试命令
• /broadcast 或 /群发 - 进入广播模式（仅主人）

【数据源说明】
• 当前支持30+个地震数据源
• 可配置黑白名单过滤规则
• 支持多种预警类型（地震、海啸、气象等）

注：[...]表示必填参数，(...)表示选填参数
更多帮助请查看具体命令后加-h或-help
"""
        return help_text


def handle_signal(signum, frame):
    """信号处理函数"""
    logging.info(f"收到信号 {signum}，正在关闭...")
    sys.exit(0)


async def main():
    """主程序入口"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # 加载配置
    try:
        config = load_config()
    except Exception as e:
        logging.error(str(e))
        return

    # 验证配置
    if not validate_config(config):
        logging.error("配置验证失败，程序退出")
        return

    # 设置日志
    log_file = config.get('log_file', 'bydbot.log')
    setup_logging(log_file)
    logging.info("Bydbot启动")

    # 初始化数据库
    db_path = await init_db()

    # 加载最近2周的地震消息ID到内存
    from ws_handler import processed_ids
    recent_ids = await load_recent_ids_from_db()
    processed_ids.update(recent_ids)

    # 初始化消息发送器
    napcat_url = config.get('napcat_http_url', 'http://127.0.0.1:3000')
    token = config.get('napcat_token', '')
    await init_sender(napcat_url, token)

    # 初始化CMA气象预警订阅器
    if CMA_WEATHER_SUBSCRIBER_AVAILABLE:
        from cma_weather_subscriber import init_cma_weather_subscriber
        await init_cma_weather_subscriber(config)



    # 启动 FAN WS 真实数据推送
    fan_ws_task = asyncio.create_task(connect_to_fan_ws(config))

    # 启动定期清理任务
    cleanup_task = asyncio.create_task(periodic_cleanup())

    # 启动 NapCat 反向 WebSocket 服务器（用于接收群消息和命令）
    server_task = None
    if config.get("enable_command_listener", True):
        ws_port = config.get("ws_port", 9998)

        start_server = websockets.serve(
            lambda ws, path: napcat_ws_handler(ws, path, config),
            "0.0.0.0",
            ws_port,
            ping_interval=20,
            ping_timeout=20
        )

        server = await start_server
        addr = server.sockets[0].getsockname()
        logging.info(f"NapCat 反向 WebSocket 服务器启动于 ws://0.0.0.0:{addr[1]} (用于接收群消息)")

        # 保持运行
        server_task = asyncio.Future()  # 永远等待，直到被取消

    else:
        logging.warning("命令监听已禁用，只运行 FAN WS 推送")
        # 保持运行
        server_task = asyncio.Event().wait()

    try:
        # 等待任务完成
        await asyncio.gather(fan_ws_task, server_task, cleanup_task)
    except asyncio.CancelledError:
        logging.info("任务被取消")
    except Exception as e:
        logging.error(f"主程序运行出错: {e}")
    finally:
        await shutdown_handler()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("程序被用户中断")
    except Exception as e:
        logging.error(f"程序运行出错: {e}")
        raise