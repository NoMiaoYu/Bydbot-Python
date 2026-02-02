import asyncio
import json
import logging
from ws_handler import connect_to_fan_ws, napcat_ws_handler

def setup_logging(log_file):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    handler = logging.FileHandler(log_file, mode='w')  # 覆盖模式
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(handler)

async def main():
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        print(f"加载 config.json 失败: {e}")
        return

    setup_logging(config.get('log_file', 'eqbot.log'))
    logging.info("地震推送机器人启动")

    from message_sender import init_sender
    init_sender(config['napcat_http_url'], config.get('napcat_token', ''))

    # 启动 FAN WS 真实数据推送
    asyncio.create_task(connect_to_fan_ws(config))

    # 启动 NapCat 反向 WebSocket 服务器（用于接收群消息和命令）
    if config.get("enable_command_listener", True):
        import websockets

        start_server = websockets.serve(
            lambda ws, path: napcat_ws_handler(ws, path, config),
            "0.0.0.0",
            config["ws_port"],
            ping_interval=20,
            ping_timeout=20
        )

        server = await start_server
        addr = server.sockets[0].getsockname()
        logging.info(f"NapCat 反向 WebSocket 服务器启动于 ws://0.0.0.0:{addr[1]} (用于接收群消息)")

        await asyncio.Future()  # 保持运行
    else:
        logging.warning("命令监听已禁用，只运行 FAN WS 推送")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())