import base64
import aiohttp
import logging
import os
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


async def send_group_msg_with_at(group_id: str, text: str, user_id: str = None) -> bool:
    """
    发送带@的文本消息到QQ群（使用OneBot v11标准CQ码）
    :param group_id: 群号
    :param text: 消息文本
    :param user_id: 要@的用户ID（可选）
    :return: 发送是否成功
    """
    global SESSION, HEADERS
    if not SESSION:
        logging.error("消息发送器未初始化")
        return False

    try:
        # 构建消息内容
        message_content = []
        
        # 如果有用户ID，添加@CQ码
        if user_id:
            message_content.append({
                "type": "at",
                "data": {
                    "qq": str(user_id)
                }
            })
            # 添加换行
            message_content.append({
                "type": "text",
                "data": {
                    "text": "\n"
                }
            })
        
        # 添加文本内容
        message_content.append({
            "type": "text",
            "data": {
                "text": text
            }
        })
        
        payload = {
            "group_id": int(group_id),
            "message": message_content
        }

        async with SESSION.post('/send_group_msg', json=payload, headers=HEADERS) as resp:
            response_text = await resp.text()

            if resp.status == 200:
                at_info = f"@{user_id} " if user_id else ""
                logging.info(f"发送带@消息到群 {group_id}: {at_info}{text[:50]}...")
                return True
            else:
                logging.error(f"发送带@消息失败，状态码 {resp.status}: {response_text}")
                return False

    except ValueError as e:
        logging.error(f"群号格式错误: {e}")
        return False
    except aiohttp.ClientError as e:
        logging.error(f"HTTP客户端错误: {e}")
        return False
    except Exception as e:
        logging.error(f"发送带@消息时发生未知错误: {e}")
        return False


async def send_group_msg_with_text_and_image(group_id: str, text: str, image_path: str = None, user_id: str = None) -> bool:
    """
    在同一消息中发送文本和图片到QQ群
    :param group_id: 群号
    :param text: 文本内容
    :param image_path: 图片文件路径（可选）
    :param user_id: 要@的用户ID（可选）
    :return: 发送是否成功
    """
    global SESSION, HEADERS
    if not SESSION:
        logging.error("消息发送器未初始化")
        return False

    try:
        message_content = []
        
        # 如果有用户ID，添加@CQ码
        if user_id:
            message_content.append({
                "type": "at",
                "data": {
                    "qq": str(user_id)
                }
            })
            # 添加换行
            message_content.append({
                "type": "text",
                "data": {
                    "text": "\n"
                }
            })
        
        # 添加文本内容
        message_content.append({
            "type": "text",
            "data": {
                "text": text
            }
        })
        
        # 如果有图片，添加图片
        if image_path and os.path.exists(image_path):
            # 添加换行分隔文本和图片
            message_content.append({
                "type": "text",
                "data": {
                    "text": "\n"
                }
            })
            
            # 读取并编码图片数据
            with open(image_path, 'rb') as f:
                img_data = f.read()
                b64 = base64.b64encode(img_data).decode('utf-8')
            
            message_content.append({
                "type": "image",
                "data": {
                    "file": f"base64://{b64}"
                }
            })
        
        payload = {
            "group_id": int(group_id),
            "message": message_content
        }

        async with SESSION.post('/send_group_msg', json=payload, headers=HEADERS) as resp:
            response_text = await resp.text()
            
            if resp.status == 200:
                at_info = f"@{user_id} " if user_id else ""
                img_info = "含图片" if image_path else "纯文本"
                logging.info(f"发送复合消息到群 {group_id}: {at_info}{img_info}, 文本长度: {len(text)}")
                return True
            else:
                logging.error(f"发送复合消息失败，状态码 {resp.status}: {response_text}")
                return False
                
    except Exception as e:
        logging.error(f"发送复合消息时发生错误: {e}")
        return False


async def send_group_msg(group_id: str, text: str, no_merge_forward: bool = False) -> bool:
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
        # 检查消息长度，如果超过250字符且不禁用合并转发，则使用合并转发
        if len(text) > 250 and not no_merge_forward:
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
                    forward_info = "(禁用合并转发)" if no_merge_forward else ""
                    logging.info(f"发送文本到群 {group_id}{forward_info}: {text[:50]}...")  # 只记录前50个字符
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
