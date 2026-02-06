import base64
import aiohttp
import logging
from typing import Optional, Dict, Any

# 全局变量
SESSION: Optional[aiohttp.ClientSession] = None
HEADERS: Dict[str, str] = {}


"""
Bydbot - 消息发送器
负责向QQ群发送文本和图片消息
"""


async def init_sender(url: str, token: str) -> None:
    """
    初始化消息发送器
    :param url: NapCat HTTP API服务地址
    :param token: NapCat访问令牌（可选）
    """
    global SESSION, HEADERS
    
    # 关闭现有的会话（如果存在）
    if SESSION:
        await SESSION.close()
    
    # 创建新的会话
    SESSION = aiohttp.ClientSession(base_url=url, timeout=aiohttp.ClientTimeout(total=30))
    HEADERS.clear()  # 清空旧的头部信息
    
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
        # 检查消息长度，如果超过250字符则使用合并转发
        if len(text) > 250:
            # 发送合并转发消息
            return await send_forward_msg(group_id, text)
        else:
            payload = {
                "group_id": int(group_id),
                "message": text
            }

            async with SESSION.post('/send_group_msg', json=payload, headers=HEADERS) as resp:
                response_text = await resp.text()

                if resp.status == 200:
                    logging.info(f"发送文本到群 {group_id}: {text[:50]}...")  # 只记录前50个字符
                    return True
                else:
                    logging.error(f"发送失败，状态码 {resp.status}: {response_text}")
                    return False

    except ValueError as e:
        logging.error(f"群号格式错误: {e}")
        return False
    except aiohttp.ClientError as e:
        logging.error(f"HTTP客户端错误: {e}")
        return False
    except Exception as e:
        logging.error(f"发送文本消息时发生未知错误: {e}")
        return False


async def send_forward_msg(group_id: str, text: str) -> bool:
    """
    发送合并转发消息到QQ群（用于长消息）
    :param group_id: 群号
    :param text: 消息文本
    :return: 发送是否成功
    """
    global SESSION, HEADERS
    if not SESSION:
        logging.error("消息发送器未初始化")
        return False

    try:
        # 准备合并转发消息节点，将整个文本作为一个节点
        forward_nodes = [{
            "type": "node",
            "data": {
                "name": "Bydbot",
                "uin": "1000000",  # 使用机器人QQ号或默认值
                "content": text  # 整个文本内容作为一个节点
            }
        }]

        # 尝试使用合并转发API
        payload = {
            "group_id": int(group_id),
            "messages": forward_nodes
        }

        # 首先尝试使用 send_group_forward_msg API
        try:
            async with SESSION.post('/send_group_forward_msg', json=payload, headers=HEADERS) as resp:
                response_text = await resp.text()

                if resp.status == 200:
                    logging.info(f"发送合并转发消息到群 {group_id}，消息长度: {len(text)} 字符")
                    return True
                else:
                    logging.warning(f"合并转发API失败，状态码 {resp.status}: {response_text}")
        except Exception as api_error:
            logging.warning(f"合并转发API调用失败: {api_error}")

        # 如果合并转发API不可用，直接发送原始文本（虽然超过了长度限制）
        # 这里我们尝试直接发送，让底层API处理
        payload_fallback = {
            "group_id": int(group_id),
            "message": text
        }
        
        async with SESSION.post('/send_group_msg', json=payload_fallback, headers=HEADERS) as fallback_resp:
            if fallback_resp.status == 200:
                logging.info(f"使用普通消息方式发送长消息到群 {group_id}，消息长度: {len(text)} 字符")
                return True
            else:
                fallback_response_text = await fallback_resp.text()
                logging.error(f"发送长消息失败，状态码 {fallback_resp.status}: {fallback_response_text}")
                return False

    except ValueError as e:
        logging.error(f"群号格式错误: {e}")
        return False
    except aiohttp.ClientError as e:
        logging.error(f"HTTP客户端错误: {e}")
        return False
    except Exception as e:
        logging.error(f"发送合并转发消息时发生未知错误: {e}")
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
                logging.info(f"发送 base64 图片到群 {group_id} 成功: {file_path}")
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
    except ValueError as e:
        logging.error(f"群号格式错误: {e}")
        return False
    except aiohttp.ClientError as e:
        logging.error(f"HTTP客户端错误: {e}")
        return False
    except Exception as e:
        logging.error(f"发送图片消息时发生未知错误: {e}")
        return False


async def close_sender() -> None:
    """关闭HTTP会话"""
    global SESSION
    if SESSION:
        await SESSION.close()
        SESSION = None  # 重置为None以便后续初始化
