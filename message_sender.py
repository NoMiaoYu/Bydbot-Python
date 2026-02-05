import base64
import aiohttp
import logging
from typing import Optional

SESSION = None
HEADERS = {}


"""
Bydbot - 消息发送器
负责向QQ群发送文本和图片消息
"""


def init_sender(url: str, token: str) -> None:
    """
    初始化消息发送器
    :param url: NapCat HTTP API服务地址
    :param token: NapCat访问令牌（可选）
    """
    global SESSION, HEADERS
    SESSION = aiohttp.ClientSession(base_url=url)
    if token:
        HEADERS['Authorization'] = f'Bearer {token}'


async def send_group_msg(group_id: str, text: str) -> bool:
    """
    发送文本消息到QQ群
    :param group_id: 群号
    :param text: 消息文本
    :return: 发送是否成功
    """
    global SESSION, HEADERS
    if not SESSION:
        logging.error("消息发送器未初始化")
        return False

    try:
        payload = {
            "group_id": int(group_id),
            "message": text
        }
        async with SESSION.post('/send_group_msg', json=payload, headers=HEADERS) as resp:
            response_text = await resp.text()
            if resp.status == 200:
                logging.info(f"发送文本到群 {group_id}: {text}")
                return True
            else:
                logging.error(f"发送失败，状态码 {resp.status}: {response_text}")
                return False
    except aiohttp.ClientError as e:
        logging.error(f"HTTP客户端错误: {e}")
        return False
    except ValueError as e:
        logging.error(f"群号格式错误: {e}")
        return False
    except Exception as e:
        logging.error(f"发送文本消息时发生未知错误: {e}")
        return False


async def send_group_img(group_id: str, file_path: str) -> bool:
    """
    发送图片消息到QQ群
    :param group_id: 群号
    :param file_path: 图片文件路径
    :return: 发送是否成功
    """
    global SESSION, HEADERS
    if not SESSION:
        logging.error("消息发送器未初始化")
        return False

    try:
        # 读取并编码图片数据
        with open(file_path, 'rb') as f:
            img_data = f.read()
            b64 = base64.b64encode(img_data).decode('utf-8')
        
        payload = {
            "group_id": int(group_id),
            "message": [{
                "type": "image",
                "data": {
                    "file": f"base64://{b64}"  # NapCat 支持 base64:// 前缀
                }
            }]
        }
        
        async with SESSION.post('/send_group_msg', json=payload, headers=HEADERS) as resp:
            response_text = await resp.text()
            if resp.status == 200:
                logging.info(f"发送 base64 图片到群 {group_id} 成功")
                return True
            else:
                logging.error(f"发送 base64 图片失败，状态码 {resp.status}: {response_text}")
                return False
    except FileNotFoundError:
        logging.error(f"图片文件不存在: {file_path}")
        return False
    except PermissionError:
        logging.error(f"没有权限访问图片文件: {file_path}")
        return False
    except aiohttp.ClientError as e:
        logging.error(f"HTTP客户端错误: {e}")
        return False
    except ValueError as e:
        logging.error(f"群号格式错误: {e}")
        return False
    except Exception as e:
        logging.error(f"发送图片消息时发生未知错误: {e}")
        return False


async def close_sender() -> None:
    """关闭HTTP会话"""
    global SESSION
    if SESSION:
        await SESSION.close()
