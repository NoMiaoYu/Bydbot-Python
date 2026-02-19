"""
Bydbot - UAPI处理器
处理UAPI相关命令和响应格式化
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from uapi_client import UApiClient
import time
from collections import defaultdict
import os
import aiohttp
import asyncio
from message_sender import send_group_msg, send_group_img


# API调用频率限制相关
# 使用字典记录每个用户在每个群的API调用次数
uapi_usage = defaultdict(lambda: defaultdict(list))

def check_api_rate_limit(user_id: str, group_id: str, config: Dict[str, Any]) -> tuple[bool, str]:
    """
    检查API调用频率限制
    :param user_id: 用户ID
    :param group_id: 群ID
    :param config: 配置
    :return: (是否允许调用, 拒绝原因)
    """
    # 从配置中获取限制参数，默认值
    rate_limit_config = config.get('uapi_rate_limit', {})
    max_calls = rate_limit_config.get('max_calls_per_minute', 10)  # 每分钟最大调用次数
    time_window = 60  # 时间窗口（秒）
    
    current_time = time.time()
    
    # 清理过期的记录
    user_group_key = (user_id, group_id)
    uapi_usage[user_group_key] = [
        call_time for call_time in uapi_usage[user_group_key] 
        if current_time - call_time < time_window
    ]
    
    # 检查是否超过限制
    if len(uapi_usage[user_group_key]) >= max_calls:
        # 计算还需要等待多少秒
        oldest_call = min(uapi_usage[user_group_key])
        wait_time = int(time_window - (current_time - oldest_call))
        return False, f"API调用频率超限，请等待 {wait_time} 秒后重试"
    
    # 记录本次调用
    uapi_usage[user_group_key].append(current_time)
    return True, ""

async def download_skin_image(skin_url: str, username: str) -> Optional[str]:
    """
    下载MC玩家皮肤图片
    :param skin_url: 皮肤URL
    :param username: 玩家用户名
    :return: 图片文件路径，失败返回None
    """
    try:
        # 创建pictures目录
        pictures_dir = os.path.join(os.path.dirname(__file__), 'pictures', 'minecraft')
        os.makedirs(pictures_dir, exist_ok=True)
        
        # 生成文件名
        filename = f"{username}_skin.png"
        file_path = os.path.join(pictures_dir, filename)
        
        # 下载图片
        async with aiohttp.ClientSession() as session:
            async with session.get(skin_url) as resp:
                if resp.status == 200:
                    img_data = await resp.read()
                    with open(file_path, 'wb') as f:
                        f.write(img_data)
                    logging.info(f"MC玩家皮肤下载成功: {file_path}")
                    return file_path
                else:
                    logging.error(f"下载皮肤失败，状态码: {resp.status}")
                    return None
    except Exception as e:
        logging.error(f"下载MC玩家皮肤失败: {e}")
        return None

async def format_uapi_response_with_skin(command_name: str, data: Any, config: Dict[str, Any], group_id: str, username: str = None) -> Optional[str]:
    """
    格式化UAPI响应（带图片发送）
    :param command_name: 命令名称
    :param data: API返回的数据
    :param config: 配置
    :param group_id: 群ID
    :param username: 用户名（用于MC皮肤）
    :return: 文本消息，如果成功发送图片则返回None
    """
    if command_name == "MC玩家查询" and username and data:
        if 'skin_url' in data and data['skin_url'] != 'N/A':
            skin_url = data['skin_url']
            img_path = await download_skin_image(skin_url, username)
            
            if img_path:
                # 生成文本消息
                text = f"[MC玩家查询]\n用户名: {data.get('username', 'N/A')}\nUUID: {data.get('uuid', 'N/A')}"
                
                # 先发送文本消息
                await send_group_msg(group_id, text)
                
                # 然后发送图片
                await send_group_img(group_id, img_path)
                
                # 返回None表示已处理
                return None
    
    # 其他情况返回普通文本
    return format_uapi_response(command_name, data, config)

def format_uapi_response(command_name: str, data: Any, config: Dict[str, Any]) -> str:
    """
    格式化UAPI响应数据
    :param command_name: 命令名称
    :param data: API响应数据
    :param config: 配置
    :return: 格式化后的消息字符串
    """
    try:
        # 确保data是字典类型
        if not isinstance(data, dict):
            logging.warning(f"UAPI响应数据格式不正确: {type(data)}, 命令: {command_name}")
            return f"UAPI响应数据格式错误: {str(data)[:200]}..."
        
        # 根据不同的命令类型进行格式化
        if command_name == "B站直播间查询":
            # 检查API是否返回了错误信息
            if not data:
                return "B站直播间查询失败：无响应数据或网络错误"
            
            # 检查是否包含错误信息 - B站API可能返回错误码或直接的错误信息
            if isinstance(data, dict):
                # 检查是否是标准的B站API响应格式，或包含错误信息
                if 'code' in data:
                    code = data.get('code')
                    message = data.get('message', '')
                    
                    if code == -404 or code == 404 or '不存在' in str(message) or '404' in str(message):
                        return "未找到该B站直播间，请检查房间号或主播UID是否正确"
                    elif code == -502 or code == 502 or '上游' in str(message) or '风控' in str(message):
                        return f"B站API错误：{message}（可能由于B站反爬机制）"
                    elif code != 0:
                        return f"B站直播间查询失败：{message or f'错误码 {code}'}"
                
                # 检查是否包含预期的直播数据
                if 'uid' in data:
                    status_map = {0: "🔴 未开播", 1: "🟢 直播中", 2: "🟡 轮播中"}
                    status = status_map.get(data.get("live_status", 0), "❓ 未知")

                    uid = data.get('uid', 'N/A')
                    title = data.get('title', 'N/A')
                    online = f"{data.get('online', 0):,}"
                    attention = f"{data.get('attention', 0):,}"
                    parent_area = data.get('parent_area_name', 'N/A')
                    area = data.get('area_name', 'N/A')
                    room_id = data.get('room_id', 'N/A')
                    short_id = data.get('short_id', 'N/A')
                    live_time = data.get('live_time', 'N/A')
                    tags = data.get('tags', 'N/A')
                    hot_words = data.get('hot_words', [])
                    hot_words_str = ', '.join(hot_words[:3]) if hot_words else 'N/A'  # 只显示前3个热词
                    description = data.get('description', 'N/A')
                    background = data.get('background', 'N/A')
                    user_cover = data.get('user_cover', 'N/A')

                    room_link = f"https://live.bilibili.com/{room_id}"
                    if short_id and short_id != '0' and short_id != 'N/A':
                        room_link = f"https://live.bilibili.com/{short_id}"

                    return f"[B站直播间查询]\n主播UID: {uid}\n标题: {title}\n状态: {status}\n人气: {online}\n粉丝: {attention}\n分区: {parent_area} - {area}\n标签: {tags}\n热词: {hot_words_str}\n开播时间: {live_time}\n直播间: {room_link}\n描述: {description}"
                else:
                    # 没有找到uid字段，检查是否是错误信息
                    if 'message' in data:
                        msg = data['message']
                        if '404' in str(msg) or '不存在' in str(msg):
                            return "未找到该B站直播间，请检查房间号或主播UID是否正确"
                    return "未找到直播间信息或查询失败"
            else:
                # data不是字典，返回错误信息
                return f"B站直播间查询失败：响应格式错误 - {str(data)}"

        elif command_name == "B站用户查询":
            # 检查API是否返回了错误信息
            if not data:
                return "B站用户查询失败：无响应数据或网络错误"
            
            # 确保数据是字典格式
            if not isinstance(data, dict):
                return f"B站用户查询失败：响应格式错误 - {str(data)}"
            
            # 检查是否是标准的B站API响应格式 {code, message, data}
            if 'code' in data:
                code = data.get('code')
                message = data.get('message', '')
                
                if code == -404 or code == 404 or '不存在' in str(message) or '404' in str(message):
                    return "未找到该B站用户，请检查UID是否正确"
                elif code == -502 or code == 502 or '上游' in str(message) or '风控' in str(message):
                    return f"B站API错误：{message}（可能由于B站反爬机制）"
                elif code != 0:
                    return f"B站用户查询失败：{message or f'错误码 {code}'}"
                
                # 如果code为0但没有data字段，也表示错误或格式异常
                if code == 0 and 'data' not in data:
                    logging.warning(f"B站用户API返回code为0但无data字段: {data}")
                    return "B站用户查询失败：响应数据格式异常"
            
            # 检查是否包含data字段（标准UAPI响应格式）
            if 'data' in data:
                user_data = data['data']
                # 尝试从用户数据中提取各个字段
                name = user_data.get('name', user_data.get('uname', 'N/A'))  # 有些API可能使用uname
                level = user_data.get('level', user_data.get('level_info', {}).get('current_level', 'N/A'))  # level_info.current_level是另一种可能的格式
                sex = user_data.get('sex', 'N/A')
                sign = user_data.get('sign', user_data.get('signature', 'N/A'))  # signature是另一种可能的字段名
                face = user_data.get('face', user_data.get('face_url', 'N/A'))  # face_url是另一种可能的字段名
                mid = user_data.get('mid', user_data.get('id', user_data.get('userID', 'N/A')))  # 尝试其他可能的ID字段名
                birthday = user_data.get('birthday', user_data.get('user_birthday', 'N/A'))  # user_birthday是另一种可能的字段名
                place = user_data.get('place', user_data.get('address', 'N/A'))  # address是另一种可能的字段名
                description = user_data.get('description', 'N/A')
                article_count = user_data.get('article_count', user_data.get('articles', 'N/A'))  # articles是另一种可能的字段名
                following = user_data.get('following', user_data.get('attention', 'N/A'))  # attention是另一种可能的字段名
                follower = user_data.get('follower', user_data.get('fans', 'N/A'))  # fans是另一种可能的字段名
                likes = user_data.get('likes', user_data.get('like_num', 'N/A'))  # like_num是另一种可能的字段名
                archive_view = user_data.get('archive_view', 'N/A')
                live_room_id = user_data.get('live_room_id', user_data.get('room_id', 'N/A'))  # room_id是另一种可能的字段名
                live_room_status = user_data.get('live_room_status', user_data.get('live_status', 'N/A'))  # live_status是另一种可能的字段名
                pendant = user_data.get('pendant', 'N/A')
                nameplate = user_data.get('nameplate', 'N/A')
                official_verify_type = user_data.get('official_verify_type', user_data.get('official', {}).get('type', 'N/A'))  # official.type是另一种可能的格式
                official_verify_desc = user_data.get('official_verify_desc', user_data.get('official', {}).get('desc', 'N/A'))  # official.desc是另一种可能的格式
                vip_type = user_data.get('vip_type', user_data.get('vip', {}).get('type', 'N/A'))  # vip.type是另一种可能的格式
                vip_status = user_data.get('vip_status', user_data.get('vip', {}).get('status', 'N/A'))  # vip.status是另一种可能的格式

                # 构建用户信息，过滤掉空值、0值或N/A值
                user_info_parts = ["[B站用户查询]"]
                if mid and str(mid) != 'N/A' and str(mid) != '0':
                    user_info_parts.append(f"UID: {mid}")
                if name and str(name) != 'N/A' and str(name) != '':
                    user_info_parts.append(f"昵称: {name}")
                if level and str(level) != 'N/A' and str(level) != '0':
                    user_info_parts.append(f"等级: {level}")
                if sex and str(sex) != 'N/A' and str(sex) != '':
                    user_info_parts.append(f"性别: {sex}")
                if birthday and str(birthday) != 'N/A' and str(birthday) != '':
                    user_info_parts.append(f"生日: {birthday}")
                if place and str(place) != 'N/A' and str(place) != '':
                    user_info_parts.append(f"地区: {place}")
                if sign and str(sign) != 'N/A' and str(sign) != '':
                    user_info_parts.append(f"签名: {sign}")
                if description and str(description) != 'N/A' and str(description) != '':
                    user_info_parts.append(f"描述: {description}")
                if article_count and str(article_count) != 'N/A' and str(article_count) != '0':
                    user_info_parts.append(f"文章数: {article_count}")
                if following and str(following) != 'N/A' and str(following) != '0':
                    user_info_parts.append(f"关注数: {following}")
                if follower and str(follower) != 'N/A' and str(follower) != '0':
                    user_info_parts.append(f"粉丝数: {follower}")
                if likes and str(likes) != 'N/A' and str(likes) != '0':
                    user_info_parts.append(f"获赞数: {likes}")
                if archive_view and str(archive_view) != 'N/A' and str(archive_view) != '0':
                    user_info_parts.append(f"播放量: {archive_view}")
                if live_room_id and str(live_room_id) != 'N/A' and str(live_room_id) != '0':
                    user_info_parts.append(f"直播间ID: {live_room_id}")
                if live_room_status and str(live_room_status) != 'N/A' and str(live_room_status) != '0':
                    user_info_parts.append(f"直播状态: {live_room_status}")
                if pendant and str(pendant) != 'N/A' and str(pendant) != '0':
                    user_info_parts.append(f"头像框: {pendant}")
                if nameplate and str(nameplate) != 'N/A' and str(nameplate) != '0':
                    user_info_parts.append(f"勋章: {nameplate}")
                if official_verify_type and str(official_verify_type) != 'N/A' and str(official_verify_type) != '0':
                    user_info_parts.append(f"认证类型: {official_verify_type}")
                if official_verify_desc and str(official_verify_desc) != 'N/A' and str(official_verify_desc) != '0':
                    user_info_parts.append(f"认证描述: {official_verify_desc}")
                # 只有当vip_type不是0时才显示VIP类型
                if vip_type and str(vip_type) != 'N/A' and str(vip_type) != '0':
                    user_info_parts.append(f"VIP类型: {vip_type}")
                # 只有当vip_status不是0时才显示VIP状态
                if vip_status and str(vip_status) != 'N/A' and str(vip_status) != '0':
                    user_info_parts.append(f"VIP状态: {vip_status}")

                # 返回用户信息和头像URL的元组
                user_info = '\n'.join(user_info_parts)
                return {"text": user_info, "face_url": face}
            else:
                # 没有data字段，检查是否是B站API透传的直接响应格式
                # 根据日志显示，API可能直接返回用户信息，没有包装在data字段中
                if 'mid' in data and 'name' in data:
                    # 这是直接的用户数据格式，直接使用data作为用户数据
                    user_data = data
                    name = user_data.get('name', 'N/A')
                    level = user_data.get('level', 'N/A')
                    sex = user_data.get('sex', 'N/A')
                    sign = user_data.get('sign', 'N/A')
                    face = user_data.get('face', 'N/A')
                    mid = user_data.get('mid', 'N/A')
                    birthday = user_data.get('birthday', 'N/A')
                    # 注意：日志显示的字段中没有place/address字段，所以这些会是N/A
                    place = user_data.get('place', user_data.get('address', 'N/A'))
                    description = user_data.get('description', 'N/A')
                    article_count = user_data.get('article_count', 'N/A')
                    following = user_data.get('following', user_data.get('attention', 'N/A'))  # following是B站实际返回的字段名
                    follower = user_data.get('follower', user_data.get('fans', 'N/A'))  # follower是B站实际返回的字段名
                    likes = user_data.get('likes', user_data.get('like_num', 'N/A'))
                    archive_view = user_data.get('archive_view', user_data.get('archive_count', 'N/A'))  # 使用archive_count作为播放量的替代
                    live_room_id = user_data.get('live_room_id', user_data.get('room_id', 'N/A'))
                    live_room_status = user_data.get('live_room_status', user_data.get('live_status', 'N/A'))
                    pendant = user_data.get('pendant', 'N/A')
                    nameplate = user_data.get('nameplate', 'N/A')
                    official_verify_type = user_data.get('official_verify_type', user_data.get('official', {}).get('type', 'N/A'))
                    official_verify_desc = user_data.get('official_verify_desc', user_data.get('official', {}).get('desc', 'N/A'))
                    vip_type = user_data.get('vip_type', user_data.get('vip', {}).get('type', 'N/A'))
                    vip_status = user_data.get('vip_status', user_data.get('vip', {}).get('status', 'N/A'))

                    # 构建用户信息，过滤掉空值、0值或N/A值
                    user_info_parts = ["[B站用户查询]"]
                    if mid and str(mid) != 'N/A' and str(mid) != '0':
                        user_info_parts.append(f"UID: {mid}")
                    if name and str(name) != 'N/A' and str(name) != '':
                        user_info_parts.append(f"昵称: {name}")
                    if level and str(level) != 'N/A' and str(level) != '0':
                        user_info_parts.append(f"等级: {level}")
                    if sex and str(sex) != 'N/A' and str(sex) != '':
                        user_info_parts.append(f"性别: {sex}")
                    if birthday and str(birthday) != 'N/A' and str(birthday) != '':
                        user_info_parts.append(f"生日: {birthday}")
                    if place and str(place) != 'N/A' and str(place) != '':
                        user_info_parts.append(f"地区: {place}")
                    if sign and str(sign) != 'N/A' and str(sign) != '':
                        user_info_parts.append(f"签名: {sign}")
                    if description and str(description) != 'N/A' and str(description) != '':
                        user_info_parts.append(f"描述: {description}")
                    if article_count and str(article_count) != 'N/A' and str(article_count) != '0':
                        user_info_parts.append(f"文章数: {article_count}")
                    if following and str(following) != 'N/A' and str(following) != '0':
                        user_info_parts.append(f"关注数: {following}")
                    if follower and str(follower) != 'N/A' and str(follower) != '0':
                        user_info_parts.append(f"粉丝数: {follower}")
                    if likes and str(likes) != 'N/A' and str(likes) != '0':
                        user_info_parts.append(f"获赞数: {likes}")
                    if archive_view and str(archive_view) != 'N/A' and str(archive_view) != '0':
                        user_info_parts.append(f"播放量: {archive_view}")
                    if live_room_id and str(live_room_id) != 'N/A' and str(live_room_id) != '0':
                        user_info_parts.append(f"直播间ID: {live_room_id}")
                    if live_room_status and str(live_room_status) != 'N/A' and str(live_room_status) != '0':
                        user_info_parts.append(f"直播状态: {live_room_status}")
                    if pendant and str(pendant) != 'N/A' and str(pendant) != '0':
                        user_info_parts.append(f"头像框: {pendant}")
                    if nameplate and str(nameplate) != 'N/A' and str(nameplate) != '0':
                        user_info_parts.append(f"勋章: {nameplate}")
                    if official_verify_type and str(official_verify_type) != 'N/A' and str(official_verify_type) != '0':
                        user_info_parts.append(f"认证类型: {official_verify_type}")
                    if official_verify_desc and str(official_verify_desc) != 'N/A' and str(official_verify_desc) != '0':
                        user_info_parts.append(f"认证描述: {official_verify_desc}")
                    # 只有当vip_type不是0时才显示VIP类型
                    if vip_type and str(vip_type) != 'N/A' and str(vip_type) != '0':
                        user_info_parts.append(f"VIP类型: {vip_type}")
                    # 只有当vip_status不是0时才显示VIP状态
                    if vip_status and str(vip_status) != 'N/A' and str(vip_status) != '0':
                        user_info_parts.append(f"VIP状态: {vip_status}")

                    # 返回用户信息和头像URL的元组
                    user_info = '\n'.join(user_info_parts)
                    return {"text": user_info, "face_url": face}
                else:
                    # 没有找到标准格式也没有找到直接的用户数据格式
                    if 'message' in data:
                        msg = data['message']
                        if '404' in str(msg) or '不存在' in str(msg):
                            return "未找到该B站用户，请检查UID是否正确"
                    logging.warning(f"B站用户API响应格式不符合预期: {data}")
                    return f"B站用户查询失败：响应格式异常 - 无法找到用户数据"

        elif command_name == "B站投稿查询":
            # 检查API是否返回了错误信息
            if not data:
                return "B站投稿查询失败：无响应数据或网络错误"
            
            # 检查是否包含错误信息 - B站API可能返回错误码或直接的错误信息
            if isinstance(data, dict):
                # 检查是否是标准的B站API响应格式，或包含错误信息
                if 'code' in data:
                    code = data.get('code')
                    message = data.get('message', '')
                    
                    if code == -404 or code == 404 or '不存在' in str(message) or '404' in str(message):
                        return "未找到该B站用户的投稿信息，请检查mid是否正确"
                    elif code == -502 or code == 502 or '上游' in str(message) or '风控' in str(message):
                        return f"B站API错误：{message}（可能由于B站反爬机制）"
                    elif code != 0:
                        return f"B站投稿查询失败：{message or f'错误码 {code}'}"
                
                # 检查是否包含预期的视频数据
                if 'videos' in data:
                    total = data.get('total', 0)
                    page = data.get('page', 1)
                    size = data.get('size', 20)
                    videos = data['videos'][:10]  # 只显示前10个视频

                    video_list = []
                    for video in videos:
                        title = video.get('title', 'N/A')
                        bvid = video.get('bvid', 'N/A')
                        duration = video.get('duration', 0)
                        play_count = video.get('play_count', 0)
                        
                        # 格式化时长
                        mins = duration // 60
                        secs = duration % 60
                        duration_str = f"{mins}:{secs:02d}"
                        
                        # 格式化播放量
                        if play_count >= 10000:
                            play_str = f"{play_count//10000}万"
                        elif play_count >= 1000:
                            play_str = f"{play_count//1000}千"
                        else:
                            play_str = str(play_count)
                        
                        # 处理发布时间
                        publish_time = video.get('publish_time', 0)
                        if publish_time > 0:
                            import time
                            try:
                                publish_date = time.strftime("%Y-%m-%d %H:%M", time.localtime(publish_time))
                                time_str = publish_date
                            except (ValueError, OSError):
                                time_str = "未知时间"
                        else:
                            time_str = "未知时间"
                        
                        video_list.append(f"- {title} (BV: {bvid})\n  播放:{play_str} | 时长:{duration_str} | {time_str}")

                    video_str = "\n".join(video_list)
                    return f"[B站投稿查询]\n总计稿件: {total}\n当前页: {page}/{size}\n最近投稿:\n{video_str}"
                else:
                    # 没有找到videos字段，检查是否是错误信息
                    if 'message' in data:
                        msg = data['message']
                        if '404' in str(msg) or '不存在' in str(msg):
                            return "未找到该B站用户的投稿信息，请检查mid是否正确"
                    return "未找到投稿信息或查询失败"
            else:
                # data不是字典，返回错误信息
                return f"B站投稿查询失败：响应格式错误 - {str(data)}"

        elif command_name == "GitHub仓库查询":
            if not data or ('full_name' not in data and 'name' not in data):
                return "未找到仓库信息"

            full_name = data.get('full_name', data.get('name', 'N/A'))
            description = data.get('description', 'N/A')
            language = data.get('language', 'N/A')
            languages = data.get('languages', {})
            stargazers = data.get('stargazers', data.get('stargazers_count', 0))
            forks = data.get('forks', data.get('forks_count', 0))
            open_issues = data.get('open_issues', data.get('open_issues_count', 0))
            watchers = data.get('watchers', data.get('watchers_count', 0))
            default_branch = data.get('default_branch', 'N/A')
            primary_branch = data.get('primary_branch', 'N/A')
            license_info = data.get('license', data.get('license', 'N/A'))
            created_at = data.get('created_at', 'N/A')
            updated_at = data.get('updated_at', 'N/A')
            pushed_at = data.get('pushed_at', 'N/A')
            homepage = data.get('homepage', 'N/A')
            topics = data.get('topics', [])
            topics_str = ', '.join(topics[:10]) if topics else 'N/A'
            
            # 可见性处理
            visibility_raw = data.get('visibility', 'N/A')
            if visibility_raw == 'public':
                visibility = '公开'
            elif visibility_raw == 'private':
                visibility = '隐藏'
            else:
                visibility = str(visibility_raw)
            
            # 归档状态处理
            archived_raw = data.get('archived', 'N/A')
            archived = '是' if archived_raw is True else '否' if archived_raw is False else str(archived_raw)
            
            # 禁用状态处理
            disabled_raw = data.get('disabled', 'N/A')
            disabled = '是' if disabled_raw is True else '否' if disabled_raw is False else str(disabled_raw)
            
            # Fork状态处理
            fork_raw = data.get('fork', 'N/A')
            fork_status = '允许' if fork_raw is True else '不允许' if fork_raw is False else str(fork_raw)
            
            # 语言分布格式化
            if languages and isinstance(languages, dict):
                # 计算总行数
                total_lines = sum(languages.values())
                if total_lines > 0:
                    # 按行数降序排序，只显示前5个
                    sorted_languages = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]
                    lang_items = []
                    for lang, lines in sorted_languages:
                        percentage = (lines / total_lines) * 100
                        lang_items.append(f"{lang}: {percentage:.1f}%")
                    languages_str = ', '.join(lang_items) if lang_items else 'N/A'
                else:
                    languages_str = 'N/A'
            else:
                languages_str = 'N/A'
            
            latest_release = data.get('latest_release', {})
            release_name = latest_release.get('name', 'N/A') if latest_release else 'N/A'
            release_published_at = latest_release.get('published_at', 'N/A') if latest_release else 'N/A'

            return f"[GitHub仓库查询]\n仓库: {full_name}\n描述: {description}\n主要语言: {language}\n语言分布: {languages_str}\n许可证: {license_info}\nStar数: {stargazers}\nFork数: {forks}\nIssue数: {open_issues}\nWatchers数: {watchers}\n默认分支: {default_branch}\n主分支: {primary_branch}\n可见性: {visibility}\n归档: {archived}\n禁用: {disabled}\nFork: {fork_status}\n话题: {topics_str}\n主页: {homepage}\n创建时间: {created_at}\n更新时间: {updated_at}\n最后推送: {pushed_at}\n最新发布: {release_name} ({release_published_at})"
        elif command_name == "热榜查询":
            if not data or 'list' not in data:
                return "未获取到热榜数据"

            hot_list = data['list'][:10]  # 只显示前10条
            type_name = data.get('type', '未知')
            update_time = data.get('update_time', 'N/A')

            # 根据热榜类型进行特殊格式化（参考热榜返回.txt文件中的结构）
            if type_name == 'bilibili':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    hot_value = item.get('hot_value', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    item_lines.append(f"     🔥 {hot_value}")
                    
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    # 添加额外信息（根据bilibili数据结构）
                    if 'owner' in extra:
                        owner_name = extra['owner'].get('name', '')
                        if owner_name:
                            item_lines.append(f"     👤 {owner_name}")
                    if 'stat' in extra:
                        stat = extra['stat']
                        view = stat.get('view', 0)
                        if view:
                            view_str = f"{view//10000}万" if view >= 10000 else str(view)
                            item_lines.append(f"     👁️ {view_str}播放")
                    if 'tname' in extra:
                        item_lines.append(f"     🏷️ {extra['tname']}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[B站热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'weibo':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    hot_value = item.get('hot_value', 'N/A')
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    item_lines.append(f"     🔥 {hot_value}")
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[微博热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'zhihu':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    hot_value = item.get('hot_value', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    item_lines.append(f"     🔥 {hot_value}")
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    # 添加额外信息（根据zhihu数据结构）
                    if 'desc' in extra:
                        desc = extra['desc']
                        if len(desc) > 60:
                            desc = desc[:57] + "..."
                        item_lines.append(f"     📝 {desc}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[知乎热榜]\n更新时间: {update_time}\n\n{hot_str}"
                

                
            elif type_name == 'douyin':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    hot_value = item.get('hot_value', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    item_lines.append(f"     🔥 {hot_value}")
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    # 添加额外信息（根据douyin数据结构）
                    if 'hot_value' in extra:
                        extra_hot_value = extra['hot_value']
                        item_lines.append(f"     💡 热度: {extra_hot_value}")
                    if 'view_count' in extra:
                        view_count = extra['view_count']
                        view_str = f"{view_count//10000}万" if view_count >= 10000 else str(view_count)
                        item_lines.append(f"     👁️ {view_str}次观看")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[抖音热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'acfun':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    hot_value = item.get('hot_value', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    item_lines.append(f"     🔥 {hot_value}")
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    # 添加额外信息（根据acfun数据结构）
                    if 'info' in extra and isinstance(extra['info'], list):
                        info_list = extra['info']
                        for info in info_list:
                            item_lines.append(f"     💡 {info}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[AcFun热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'kuaishou':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    hot_value = item.get('hot_value', 'N/A')
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    item_lines.append(f"     🔥 {hot_value}")
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[快手热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'douban-movie':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    hot_value = item.get('hot_value', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    item_lines.append(f"     ⭐ 评分: {hot_value}")
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    # 添加额外信息（根据douban-movie数据结构）
                    if 'info' in extra:
                        info = extra['info']
                        if len(info) > 60:
                            info = info[:57] + "..."
                        item_lines.append(f"     📖 {info}")
                    if 'score' in extra:
                        item_lines.append(f"     ⭐ 评分: {extra['score']}")
                    if 'ratings_count' in extra:
                        ratings = extra['ratings_count']
                        ratings_str = f"{ratings//10000}万" if ratings >= 10000 else str(ratings)
                        item_lines.append(f"     👥 {ratings_str}人评价")
                    if 'poster' in extra:
                        item_lines.append(f"     🖼️ 有海报")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[豆瓣电影榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'douban-group':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    hot_value = item.get('hot_value', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    item_lines.append(f"     👍 {hot_value}")
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    # 添加额外信息（根据douban-group数据结构）
                    if 'description' in extra:
                        desc = extra['description']
                        if len(desc) > 60:
                            desc = desc[:57] + "..."
                        item_lines.append(f"     📝 {desc}")
                    if 'group_name' in extra:
                        item_lines.append(f"     🏘️ {extra['group_name']}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[豆瓣小组热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'coolapk':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    # 添加额外信息（根据coolapk数据结构）
                    if 'author' in extra:
                        item_lines.append(f"     👤 {extra['author']}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[酷安热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'thepaper':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[澎湃新闻热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'ithome':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[IT之家热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'ithome-xijiayi':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    # 添加额外信息（根据ithome-xijiayi数据结构）
                    if 'description' in extra:
                        desc = extra['description']
                        if len(desc) > 60:
                            desc = desc[:57] + "..."
                        item_lines.append(f"     📝 {desc}")
                    if 'editor' in extra:
                        item_lines.append(f"     👨‍💼 编辑: {extra['editor']}")
                    if 'post_time' in extra:
                        item_lines.append(f"     📅 发布时间: {extra['post_time']}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[IT之家喜加一]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'guokr':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[果壳热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == '36kr':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[36氪热榜]\n更新时间: {update_time}\n\n{hot_str}"
                
            elif type_name == 'history':
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    extra = item.get('extra', {})
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    
                    # 添加额外信息（根据history数据结构）
                    if 'year' in extra:
                        item_lines.append(f"     📅 {extra['year']}年")
                    
                    hot_items.append("\n".join(item_lines))
                hot_str = "\n\n".join(hot_items)
                return f"[历史上的今天]\n更新时间: {update_time}\n\n{hot_str}"
                
            else:
                # 通用格式处理其他类型的热榜
                hot_items = []
                for i, item in enumerate(hot_list, 1):
                    title = item.get('title', 'N/A')
                    url = item.get('url', 'N/A')
                    hot_value = item.get('hot_value', 'N/A')
                    
                    # 构建热榜条目
                    item_lines = [f"{i:2d}. {title}"]
                    if hot_value != 'N/A':
                        item_lines.append(f"     🔥 {hot_value}")
                    if url != 'N/A':
                        item_lines.append(f"     🔗 {url}")
                    
                    hot_items.append("\n".join(item_lines))

                hot_str = "\n\n".join(hot_items)
                return f"[{type_name}热榜]\n更新时间: {update_time}\n\n{hot_str}"
        elif command_name == "世界时间查询":
            if not data or 'datetime' not in data:
                return "未获取到时间信息"

            datetime = data.get('datetime', 'N/A')
            timezone = data.get('timezone', 'N/A')
            weekday = data.get('weekday', 'N/A')
            offset_string = data.get('offset_string', 'N/A')
            timestamp_unix = data.get('timestamp_unix', 'N/A')
            offset_seconds = data.get('offset_seconds', 'N/A')
            query = data.get('query', 'N/A')

            return f"[世界时间查询]\n查询时区: {query}\n当前时区: {timezone}\n日期时间: {datetime}\n星期: {weekday}\nUTC偏移: {offset_string}\n偏移秒数: {offset_seconds}\nUnix时间戳: {timestamp_unix}"

        elif command_name == "天气查询":
            if not data or 'temperature' not in data:
                return "未获取到天气信息"

            city = data.get('city', '未知城市')
            province = data.get('province', '未知省份')
            adcode = data.get('adcode', 'N/A')
            weather = data.get('weather', 'N/A')
            weather_code = data.get('weather_code', 'N/A')
            temperature = data.get('temperature', 'N/A')
            wind_direction = data.get('wind_direction', 'N/A')
            wind_power = data.get('wind_power', 'N/A')
            humidity = data.get('humidity', 'N/A')
            report_time = data.get('report_time', 'N/A')

            return f"[天气查询 - {province}{city}]\n天气: {weather}\n天气代码: {weather_code}\n温度: {temperature}°C\n湿度: {humidity}%\n风向: {wind_direction}\n风力: {wind_power}\n报告时间: {report_time}"

        elif command_name == "手机归属地查询":
            if not data or 'province' not in data:
                return "未查询到归属地信息"

            province = data.get('province', 'N/A')
            city = data.get('city', 'N/A')
            sp = data.get('sp', 'N/A')

            return f"[手机归属地查询]\n省份: {province}\n城市: {city}\n运营商: {sp}"

        elif command_name == "随机数生成":
            if not data or 'numbers' not in data:
                return "随机数生成失败"

            numbers = data.get('numbers', [])
            sum_total = sum(numbers) if numbers else 0
            average = sum_total / len(numbers) if numbers else 0
            
            # 计算最小值和最大值
            min_generated = min(numbers) if numbers else 'N/A'
            max_generated = max(numbers) if numbers else 'N/A'

            # 检查是否包含小数
            has_decimals = any(isinstance(num, float) or ('.' in str(num) and not str(num).endswith('.0')) for num in numbers)
            
            if len(numbers) <= 10:
                # 如果数字较少，显示全部数字
                numbers_str = ', '.join(map(str, numbers))
                return f"[随机数生成]\n数字类型: {'小数' if has_decimals else '整数'}\n生成数量: {len(numbers)}\n生成的随机数: {numbers_str}\n最小值: {min_generated}\n最大值: {max_generated}\n总和: {sum_total}\n平均值: {average:.2f}"
            else:
                # 如果数字较多，只显示统计信息
                return f"[随机数生成]\n数字类型: {'小数' if has_decimals else '整数'}\n生成数量: {len(numbers)}\n最小值: {min_generated}\n最大值: {max_generated}\n总和: {sum_total}\n平均值: {average:.2f}"

        elif command_name == "ICP备案查询":
            if not data or data.get('code') != '200':
                return "未查询到备案信息或查询失败"
            
            domain = data.get('domain', 'N/A')
            service_license = data.get('serviceLicence', 'N/A')
            unit_name = data.get('unitName', 'N/A')
            nature_name = data.get('natureName', 'N/A')
            
            return f"[ICP备案查询]\n域名: {domain}\n备案号: {service_license}\n主办单位: {unit_name}\n单位性质: {nature_name}"

        elif command_name == "IP信息查询":
            if not data or 'ip' not in data:
                return "未查询到IP信息"
            
            ip = data.get('ip', 'N/A')
            beginip = data.get('beginip', 'N/A')
            endip = data.get('endip', 'N/A')
            region = data.get('region', 'N/A')
            isp = data.get('isp', 'N/A')
            asn = data.get('asn', 'N/A')
            latitude = data.get('latitude', 'N/A')
            longitude = data.get('longitude', 'N/A')
            llc = data.get('llc', 'N/A')
            
            return f"[IP信息查询]\nIP地址: {ip}\nIP段: {beginip} - {endip}\n地理位置: {region}\n运营商: {isp}\n归属机构: {llc}\nASN: {asn}\n经纬度: {latitude}, {longitude}"

        elif command_name == "一言":
            if not data or 'text' not in data:
                return "获取一言失败"
            
            text = data.get('text', 'N/A')
            
            return f"[一言]\n{text}"

        elif command_name == "随机图片":
            return "[随机图片]\n图片已生成并发送"

        elif command_name == "答案之书":
            if not data or 'answer' not in data:
                return "获取答案失败"
            
            question = data.get('question', 'N/A')
            answer = data.get('answer', 'N/A')
            
            return f"[答案之书]\n问题: {question}\n答案: {answer}"

        elif command_name == "随机字符串":
            if not data or 'text' not in data:
                return "生成随机字符串失败"
            
            text = data.get('text', 'N/A')
            
            return f"[随机字符串]\n生成的字符串: {text}"

        elif command_name == "必应壁纸":
            return "[必应壁纸]\n壁纸已获取并发送"

        elif command_name == "生成二维码":
            return "[生成二维码]\n二维码已生成并发送"

        elif command_name == "GrAvatar头像":
            return "[GrAvatar头像]\n头像已获取并发送"

        elif command_name == "摸摸头":
            return "[摸摸头]\nGIF已生成并发送"

        elif command_name == "每日新闻图":
            return "[每日新闻图]\n新闻图已获取并发送"

        elif command_name == "上传图片":
            if not data or 'image_url' not in data:
                return "上传图片失败"

            image_url = data.get('image_url', 'N/A')
            msg = data.get('msg', 'N/A')

            return f"[上传图片]\n图片URL: {image_url}\n状态: {msg}"

        elif command_name == "图片转Base64":
            if not data or 'base64' not in data:
                return "图片转Base64失败"

            base64_data = data.get('base64', 'N/A')
            msg = data.get('msg', 'N/A')

            return f"[图片转Base64]\nBase64数据: {base64_data[:50]}...\n状态: {msg}"

        elif command_name == "翻译":
            if not data:
                return "翻译失败"
            
            # 根据实际API返回格式调整字段名
            original_text = data.get('text', 'N/A')
            translated_text = data.get('translate', 'N/A')
            
            return f"[翻译]\n原文: {original_text}\n翻译结果: {translated_text}"

        elif command_name == "MC服务器查询":
            if not data or 'ip' not in data:
                return "未查询到服务器信息"
            
            online = data.get('online', False)
            if not online:
                return "[MC服务器查询]\n服务器离线或无法连接"
            
            ip = data.get('ip', 'N/A')
            port = data.get('port', 'N/A')
            players = data.get('players', 0)
            max_players = data.get('max_players', 0)
            version = data.get('version', 'N/A')
            motd_clean = data.get('motd_clean', 'N/A')
            
            status = "🟢 在线" if online else "🔴 离线"
            return f"[MC服务器查询]\n状态: {status}\nIP: {ip}:{port}\n在线玩家: {players}/{max_players}\n版本: {version}\nMOTD: {motd_clean}"

        elif command_name == "Steam用户查询":
            if not data or 'steamid' not in data:
                return "未查询到用户信息"
            
            personaname = data.get('personaname', 'N/A')
            profileurl = data.get('profileurl', 'N/A')
            personastate = data.get('personastate', 0)
            communityvisibilitystate = data.get('communityvisibilitystate', 1)
            realname = data.get('realname', 'N/A')
            loccountrycode = data.get('loccountrycode', 'N/A')
            timecreated_str = data.get('timecreated_str', 'N/A')
            
            state_map = {
                0: "🔴 离线", 1: "🟢 在线", 2: "🟡 忙碌", 3: "🔵 离开",
                4: "🌙 打盹", 5: "💡 想交易", 6: "🎮 想玩"
            }
            state = state_map.get(personastate, "❓ 未知")
            
            visibility = "公开" if communityvisibilitystate == 3 else "私密"
            
            return f"[Steam用户查询]\n昵称: {personaname}\n真实姓名: {realname}\n状态: {state}\n可见性: {visibility}\n国家: {loccountrycode}\n账户创建: {timecreated_str}\n个人资料: {profileurl}"

        elif command_name == "Epic免费游戏":
            if not data:
                return "未查询到免费游戏信息"

            # 尝试不同的数据结构
            games = None
            if 'data' in data and isinstance(data['data'], list):
                games = data['data']
            elif isinstance(data, list):
                games = data
            elif 'games' in data and isinstance(data['games'], list):
                games = data['games']

            if not games:
                return "[Epic免费游戏]\n当前没有免费游戏"

            # 分类：当前免费和即将免费
            current_free = []
            upcoming_free = []

            for game in games:
                if not isinstance(game, dict):
                    continue

                is_free_now = game.get('is_free_now', False)
                title = game.get('title', game.get('name', 'N/A'))
                description = game.get('description', '暂无描述').strip()
                original_price = game.get('original_price_desc', game.get('originalPrice', 'N/A'))
                free_start = game.get('free_start', game.get('startDate', 'N/A'))
                free_end = game.get('free_end', game.get('endDate', 'N/A'))
                link = game.get('link', '')

                # 限制描述长度
                if len(description) > 150:
                    description = description[:150] + "..."

                game_info = {
                    'title': title,
                    'description': description,
                    'original_price': original_price,
                    'free_start': free_start,
                    'free_end': free_end,
                    'link': link
                }

                if is_free_now:
                    current_free.append(game_info)
                else:
                    upcoming_free.append(game_info)

            # 构建返回字符串
            result_lines = ["[Epic免费游戏]"]

            if current_free:
                result_lines.append("\n🎮 当前免费：")
                for i, game in enumerate(current_free, 1):
                    result_lines.append(f"{i}. {game['title']}")
                    result_lines.append(f"   原价: {game['original_price']} | 免费截止: {game['free_end']}")
                    result_lines.append(f"   {game['description']}")
                    if game['link']:
                        result_lines.append(f"   🔗 {game['link']}")
                    result_lines.append("")

            if upcoming_free:
                result_lines.append("\n🔜 即将免费：")
                for i, game in enumerate(upcoming_free, 1):
                    result_lines.append(f"{i}. {game['title']}")
                    result_lines.append(f"   原价: {game['original_price']} | 免费期间: {game['free_start']} ~ {game['free_end']}")
                    result_lines.append(f"   {game['description']}")
                    if game['link']:
                        result_lines.append(f"   🔗 {game['link']}")
                    result_lines.append("")

            if not current_free and not upcoming_free:
                result_lines.append("\n当前没有免费游戏信息")

            return "\n".join(result_lines).strip()

        elif command_name == "MC玩家查询":
            if not data or 'username' not in data:
                return "未查询到玩家信息"
            
            username = data.get('username', 'N/A')
            uuid = data.get('uuid', 'N/A')
            skin_url = data.get('skin_url', 'N/A')
            
            return f"[MC玩家查询]\n用户名: {username}\nUUID: {uuid}\n皮肤URL: {skin_url}"

        elif command_name == "MD5校验":
            if not data or 'match' not in data:
                return "MD5校验失败"
            
            match = data.get('match', False)
            match_status = "✅ 匹配" if match else "❌ 不匹配"
            
            return f"[MD5校验]\n校验结果: {match_status}"

        elif command_name == "Base64编码":
            if not data or 'encoded' not in data:
                return "Base64编码失败"
            
            encoded = data.get('encoded', 'N/A')
            
            return f"[Base64编码]\n{encoded}"

        elif command_name == "Base64解码":
            if not data or 'decoded' not in data:
                return "Base64解码失败"
            
            decoded = data.get('decoded', 'N/A')
            
            return f"[Base64解码]\n{decoded}"

        elif command_name == "AES加密":
            if not data or 'ciphertext' not in data:
                return "AES加密失败"
            
            ciphertext = data.get('ciphertext', 'N/A')
            
            return f"[AES加密]\n{ciphertext}"

        elif command_name == "AES解密":
            if not data or 'plaintext' not in data:
                return "AES解密失败"
            
            plaintext = data.get('plaintext', 'N/A')
            
            return f"[AES解密]\n{plaintext}"

        elif command_name == "AES高级加密":
            if not data or 'ciphertext' not in data:
                return "AES高级加密失败"
            
            ciphertext = data.get('ciphertext', 'N/A')
            mode = data.get('mode', 'N/A')
            padding = data.get('padding', 'N/A')
            
            return f"[AES高级加密] {mode}/{padding}\n{ciphertext}"

        elif command_name == "AES高级解密":
            if not data or 'plaintext' not in data:
                return "AES高级解密失败"
            
            plaintext = data.get('plaintext', 'N/A')
            
            return f"[AES高级解密]\n{plaintext}"

        elif command_name == "格式转换":
            if not data or 'result' not in data:
                return "格式转换失败"
            
            result = data.get('result', 'N/A')
            from_format = data.get('from', 'unknown')
            to_format = data.get('to', 'unknown')
            
            return f"[格式转换] {from_format} → {to_format}\n{result}"

        elif command_name == "Ping主机":
            if not data or 'host' not in data:
                return "Ping测试失败"
            
            host = data.get('host', 'N/A')
            ip = data.get('ip', 'N/A')
            location = data.get('location', 'N/A')
            avg = data.get('avg', 'N/A')
            
            return f"[Ping主机]\n目标: {host} ({ip})\n地理位置: {location}\n平均延迟: {avg}ms"

        elif command_name == "DNS查询":
            if not data or 'records' not in data:
                return "DNS查询失败"

            domain = data.get('domain', 'N/A')
            records = data.get('records', [])

            record_list = []
            for record in records:
                record_type = record.get('type', 'N/A')
                value = record.get('value', 'N/A')
                ttl = record.get('ttl', 'N/A')
                record_list.append(f"  {record_type}: {value} (TTL: {ttl})")

            record_str = "\n".join(record_list)
            return f"[DNS查询 - {domain}]\n{record_str}"

        elif command_name == "WHOIS查询":
            if not data:
                return "WHOIS查询失败"

            # WHOIS查询可能返回不同格式的数据，根据格式处理
            if 'whois' in data:
                whois_data = data['whois']
                if isinstance(whois_data, str):
                    # 如果是原始文本格式
                    return f"[WHOIS查询]\n{whois_data[:500]}..."  # 限制长度
                elif isinstance(whois_data, dict):
                    # 如果是结构化JSON格式，提取关键信息
                    # 从嵌套结构中提取域名信息
                    domain_info = whois_data.get('domain', {})
                    registrar_info = whois_data.get('registrar', {})
                    registrant_info = whois_data.get('registrant', {})
                    
                    domain_name = domain_info.get('domain', data.get('domain', 'N/A'))
                    registry_domain_id = domain_info.get('id', 'N/A')
                    whois_server = domain_info.get('whois_server', 'N/A')
                    name_servers = domain_info.get('name_servers', [])
                    created_date = domain_info.get('created_date', 'N/A')
                    updated_date = domain_info.get('updated_date', 'N/A')
                    expiration_date = domain_info.get('expiration_date', 'N/A')
                    status_list = domain_info.get('status', [])
                    
                    registrar_name = registrar_info.get('name', 'N/A')
                    registrar_id = registrar_info.get('id', 'N/A')
                    registrar_url = registrar_info.get('referral_url', 'N/A')
                    registrar_email = registrar_info.get('email', 'N/A')
                    registrar_phone = registrar_info.get('phone', 'N/A')
                    
                    registrant_province = registrant_info.get('province', 'N/A')
                    registrant_country = registrant_info.get('country', 'N/A')
                    registrant_email = registrant_info.get('email', 'N/A')

                    status_str = ", ".join(status_list) if status_list else "N/A"
                    ns_str = ", ".join(name_servers[:10]) if name_servers else "N/A"  # 显示前10个NS

                    return f"[WHOIS查询]\n域名: {domain_name}\n注册局域名ID: {registry_domain_id}\n域名服务器: {ns_str}\nWHOIS服务器: {whois_server}\n注册商: {registrar_name}\n注册商ID: {registrar_id}\n注册商URL: {registrar_url}\n注册商邮箱: {registrar_email}\n注册商电话: {registrar_phone}\n注册人省份: {registrant_province}\n注册人国家: {registrant_country}\n注册人邮箱: {registrant_email}\n创建时间: {created_date}\n更新时间: {updated_date}\n到期时间: {expiration_date}\n状态: {status_str}"
                else:
                    return f"[WHOIS查询]\n{str(whois_data)[:500]}..."
            else:
                # 如果直接是WHOIS数据（没有嵌套在whois键下）
                domain_info = data.get('domain', data)
                registrar_info = data.get('registrar', {})
                registrant_info = data.get('registrant', {})
                
                domain_name = domain_info.get('domain', data.get('domain', 'N/A'))
                registry_domain_id = domain_info.get('id', 'N/A')
                whois_server = domain_info.get('whois_server', 'N/A')
                name_servers = domain_info.get('name_servers', [])
                created_date = domain_info.get('created_date', 'N/A')
                updated_date = domain_info.get('updated_date', 'N/A')
                expiration_date = domain_info.get('expiration_date', 'N/A')
                status_list = domain_info.get('status', [])
                
                registrar_name = registrar_info.get('name', 'N/A')
                registrar_id = registrar_info.get('id', 'N/A')
                registrar_url = registrar_info.get('referral_url', 'N/A')
                registrar_email = registrar_info.get('email', 'N/A')
                registrar_phone = registrar_info.get('phone', 'N/A')
                
                registrant_province = registrant_info.get('province', 'N/A')
                registrant_country = registrant_info.get('country', 'N/A')
                registrant_email = registrant_info.get('email', 'N/A')

                status_str = ", ".join(status_list) if status_list else "N/A"
                ns_str = ", ".join(name_servers[:10]) if name_servers else "N/A"  # 显示前10个NS

                return f"[WHOIS查询]\n域名: {domain_name}\n注册局域名ID: {registry_domain_id}\n域名服务器: {ns_str}\nWHOIS服务器: {whois_server}\n注册商: {registrar_name}\n注册商ID: {registrar_id}\n注册商URL: {registrar_url}\n注册商邮箱: {registrar_email}\n注册商电话: {registrar_phone}\n注册人省份: {registrant_province}\n注册人国家: {registrant_country}\n注册人邮箱: {registrant_email}\n创建时间: {created_date}\n更新时间: {updated_date}\n到期时间: {expiration_date}\n状态: {status_str}"

        elif command_name == "URL可访问性":
            if not data or 'url' not in data:
                return "URL可访问性检查失败"
            
            url = data.get('url', 'N/A')
            status = data.get('status', 'N/A')
            
            status_desc = "✅ 可访问" if 200 <= status < 300 else f"❌ 不可访问 ({status})"
            
            return f"[URL可访问性]\n{status_desc}\nURL: {url}"

        elif command_name == "端口扫描":
            if not data or 'ip' not in data:
                return "端口扫描失败"

            ip = data.get('ip', 'N/A')
            port = data.get('port', 'N/A')
            protocol = data.get('protocol', 'N/A')
            port_status = data.get('port_status', 'N/A')

            status_map = {
                'open': '🟢 开放',
                'closed': '🔴 关闭',
                'timeout': '⏰ 超时'
            }
            status_desc = status_map.get(port_status, port_status)

            return f"[端口扫描]\nIP: {ip}\n端口: {port}/{protocol}\n状态: {status_desc}"

        elif command_name == "生成你们怎么不说话了表情包":
            return "[生成你们怎么不说话了表情包]\n表情包已生成并发送"

        elif command_name == "时间戳转换":
            if not data or 'datetime' not in data:
                return "时间戳转换失败"
            
            datetime_str = data.get('datetime', 'N/A')
            timestamp = data.get('timestamp', 'N/A')
            
            return f"[时间戳转换]\n日期时间: {datetime_str}\n时间戳: {timestamp}"

        elif command_name == "JSON格式化":
            if not data or 'content' not in data:
                return "JSON格式化失败"

            formatted_content = data.get('content', 'N/A')

            return f"[JSON格式化]\n{formatted_content}"

        elif command_name == "网页元数据提取":
            if not data or 'page_url' not in data:
                return "网页元数据提取失败"

            page_url = data.get('page_url', 'N/A')
            title = data.get('title', 'N/A')
            description = data.get('description', 'N/A')
            keywords = data.get('keywords', [])
            favicon_url = data.get('favicon_url', 'N/A')
            
            keywords_str = ", ".join(keywords[:5]) if keywords else "N/A"  # 只显示前5个关键词

            return f"[网页元数据提取]\n页面URL: {page_url}\n标题: {title}\n描述: {description}\n关键词: {keywords_str}\nFavicon: {favicon_url}"

        elif command_name == "程序员历史上的今天":
            if not data or 'events' not in data:
                return "程序员历史上的今天查询失败"

            date = data.get('date', 'N/A')
            events = data.get('events', [])
            message = data.get('message', 'N/A')

            event_list = []
            for i, event in enumerate(events, 1):  # 显示所有事件，不只是前5个
                year = event.get('year', 'N/A')
                title = event.get('title', 'N/A')
                description = event.get('description', 'N/A')
                category = event.get('category', 'N/A')
                importance = event.get('importance', 'N/A')
                source = event.get('source', 'N/A')
                tags = event.get('tags', [])
                
                tags_str = ', '.join(tags) if tags else 'N/A'
                
                event_info = f"{i}. [{year}] {title}\n   📚 分类: {category}\n   ⭐ 重要性: {importance}\n   🏷️ 标签: {tags_str}\n   📖 来源: {source}\n   📝 {description}"
                event_list.append(event_info)

            event_str = "\n\n".join(event_list)
            return f"[程序员历史上的今天]\n📅 日期: {date}\n📊 总事件数: {len(events)}\n\n{event_str}"

        elif command_name == "程序员历史事件":
            if not data or 'events' not in data:
                return "程序员历史事件查询失败"

            date = data.get('date', 'N/A')
            events = data.get('events', [])

            event_list = []
            for i, event in enumerate(events, 1):  # 显示所有事件，不只是前5个
                year = event.get('year', 'N/A')
                title = event.get('title', 'N/A')
                description = event.get('description', 'N/A')
                category = event.get('category', 'N/A')
                importance = event.get('importance', 'N/A')
                source = event.get('source', 'N/A')
                tags = event.get('tags', [])
                
                tags_str = ', '.join(tags) if tags else 'N/A'
                
                event_info = f"{i}. [{year}] {title}\n   📚 分类: {category}\n   ⭐ 重要性: {importance}\n   🏷️ 标签: {tags_str}\n   📖 来源: {source}\n   📝 {description}"
                event_list.append(event_info)

            event_str = "\n\n".join(event_list)
            return f"[程序员历史事件]\n📅 日期: {date}\n📊 总事件数: {len(events)}\n\n{event_str}"

        elif command_name == "MD5哈希":
            if not data or 'md5' not in data:
                return "MD5计算失败"
            
            md5_hash = data.get('md5', 'N/A')
            
            return f"[MD5哈希]\n{md5_hash}"

        elif command_name == "MD5哈希 POST":
            if not data or 'md5' not in data:
                return "MD5计算失败"
            
            md5_hash = data.get('md5', 'N/A')
            
            return f"[MD5哈希(POST)]\n{md5_hash}"

        elif command_name == "MD5校验":
            if not data or 'match' not in data:
                return "MD5校验失败"
            
            match = data.get('match', False)
            match_status = "✅ 匹配" if match else "❌ 不匹配"
            
            return f"[MD5校验]\n校验结果: {match_status}"

        elif command_name == "Base64编码":
            if not data or 'encoded' not in data:
                return "Base64编码失败"
            
            encoded = data.get('encoded', 'N/A')
            
            return f"[Base64编码]\n{encoded}"

        elif command_name == "Base64解码":
            if not data or 'decoded' not in data:
                return "Base64解码失败"
            
            decoded = data.get('decoded', 'N/A')
            
            return f"[Base64解码]\n{decoded}"

        elif command_name == "AES加密":
            if not data or 'ciphertext' not in data:
                return "AES加密失败"
            
            ciphertext = data.get('ciphertext', 'N/A')
            
            return f"[AES加密]\n{ciphertext}"

        elif command_name == "AES解密":
            if not data or 'plaintext' not in data:
                return "AES解密失败"
            
            plaintext = data.get('plaintext', 'N/A')
            
            return f"[AES解密]\n{plaintext}"

        elif command_name == "AES高级加密":
            if not data or 'ciphertext' not in data:
                return "AES高级加密失败"
            
            ciphertext = data.get('ciphertext', 'N/A')
            mode = data.get('mode', 'N/A')
            padding = data.get('padding', 'N/A')
            
            return f"[AES高级加密] {mode}/{padding}\n{ciphertext}"

        elif command_name == "AES高级解密":
            if not data or 'plaintext' not in data:
                return "AES高级解密失败"
            
            plaintext = data.get('plaintext', 'N/A')
            
            return f"[AES高级解密]\n{plaintext}"

        elif command_name == "格式转换":
            if not data or 'result' not in data:
                return "格式转换失败"
            
            result = data.get('result', 'N/A')
            from_format = data.get('from', 'unknown')
            to_format = data.get('to', 'unknown')
            info = data.get('info', '')
            
            output = f"[格式转换] {from_format} → {to_format}\n{result}"
            if info:
                output += f"\n说明: {info}"
            
            return output

        elif command_name == "Ping主机":
            if not data or 'host' not in data:
                return "Ping测试失败"
            
            host = data.get('host', 'N/A')
            ip = data.get('ip', 'N/A')
            location = data.get('location', 'N/A')
            avg = data.get('avg', 'N/A')
            
            return f"[Ping主机]\n目标: {host} ({ip})\n地理位置: {location}\n平均延迟: {avg}ms"

        elif command_name == "DNS查询":
            if not data or 'records' not in data:
                return "DNS查询失败"

            domain = data.get('domain', 'N/A')
            records = data.get('records', [])

            record_list = []
            for record in records:
                record_type = record.get('type', 'N/A')
                value = record.get('value', 'N/A')
                ttl = record.get('ttl', 'N/A')
                record_list.append(f"  {record_type}: {value} (TTL: {ttl})")

            record_str = "\n".join(record_list)
            return f"[DNS查询 - {domain}]\n{record_str}"

        elif command_name == "WHOIS查询":
            if not data:
                return "WHOIS查询失败"

            # WHOIS查询可能返回不同格式的数据，根据格式处理
            if 'whois' in data:
                whois_data = data['whois']
                if isinstance(whois_data, str):
                    # 如果是原始文本格式
                    return f"[WHOIS查询]\n{whois_data[:500]}..."  # 限制长度
                elif isinstance(whois_data, dict):
                    # 如果是结构化JSON格式，提取关键信息
                    # 从嵌套结构中提取域名信息
                    domain_info = whois_data.get('domain', {})
                    registrar_info = whois_data.get('registrar', {})
                    registrant_info = whois_data.get('registrant', {})
                    
                    domain_name = domain_info.get('domain', data.get('domain', 'N/A'))
                    registry_domain_id = domain_info.get('id', 'N/A')
                    whois_server = domain_info.get('whois_server', 'N/A')
                    name_servers = domain_info.get('name_servers', [])
                    created_date = domain_info.get('created_date', 'N/A')
                    updated_date = domain_info.get('updated_date', 'N/A')
                    expiration_date = domain_info.get('expiration_date', 'N/A')
                    status_list = domain_info.get('status', [])
                    
                    registrar_name = registrar_info.get('name', 'N/A')
                    registrar_id = registrar_info.get('id', 'N/A')
                    registrar_url = registrar_info.get('referral_url', 'N/A')
                    registrar_email = registrar_info.get('email', 'N/A')
                    registrar_phone = registrar_info.get('phone', 'N/A')
                    
                    registrant_province = registrant_info.get('province', 'N/A')
                    registrant_country = registrant_info.get('country', 'N/A')
                    registrant_email = registrant_info.get('email', 'N/A')

                    status_str = ", ".join(status_list) if status_list else "N/A"
                    ns_str = ", ".join(name_servers[:10]) if name_servers else "N/A"  # 显示前10个NS

                    return f"[WHOIS查询]\n域名: {domain_name}\n注册局域名ID: {registry_domain_id}\n域名服务器: {ns_str}\nWHOIS服务器: {whois_server}\n注册商: {registrar_name}\n注册商ID: {registrar_id}\n注册商URL: {registrar_url}\n注册商邮箱: {registrar_email}\n注册商电话: {registrar_phone}\n注册人省份: {registrant_province}\n注册人国家: {registrant_country}\n注册人邮箱: {registrant_email}\n创建时间: {created_date}\n更新时间: {updated_date}\n到期时间: {expiration_date}\n状态: {status_str}"
                else:
                    return f"[WHOIS查询]\n{str(whois_data)[:500]}..."
            else:
                # 如果直接是WHOIS数据（没有嵌套在whois键下）
                domain_info = data.get('domain', data)
                registrar_info = data.get('registrar', {})
                registrant_info = data.get('registrant', {})
                
                domain_name = domain_info.get('domain', data.get('domain', 'N/A'))
                registry_domain_id = domain_info.get('id', 'N/A')
                whois_server = domain_info.get('whois_server', 'N/A')
                name_servers = domain_info.get('name_servers', [])
                created_date = domain_info.get('created_date', 'N/A')
                updated_date = domain_info.get('updated_date', 'N/A')
                expiration_date = domain_info.get('expiration_date', 'N/A')
                status_list = domain_info.get('status', [])
                
                registrar_name = registrar_info.get('name', 'N/A')
                registrar_id = registrar_info.get('id', 'N/A')
                registrar_url = registrar_info.get('referral_url', 'N/A')
                registrar_email = registrar_info.get('email', 'N/A')
                registrar_phone = registrar_info.get('phone', 'N/A')
                
                registrant_province = registrant_info.get('province', 'N/A')
                registrant_country = registrant_info.get('country', 'N/A')
                registrant_email = registrant_info.get('email', 'N/A')

                status_str = ", ".join(status_list) if status_list else "N/A"
                ns_str = ", ".join(name_servers[:10]) if name_servers else "N/A"  # 显示前10个NS

                return f"[WHOIS查询]\n域名: {domain_name}\n注册局域名ID: {registry_domain_id}\n域名服务器: {ns_str}\nWHOIS服务器: {whois_server}\n注册商: {registrar_name}\n注册商ID: {registrar_id}\n注册商URL: {registrar_url}\n注册商邮箱: {registrar_email}\n注册商电话: {registrar_phone}\n注册人省份: {registrant_province}\n注册人国家: {registrant_country}\n注册人邮箱: {registrant_email}\n创建时间: {created_date}\n更新时间: {updated_date}\n到期时间: {expiration_date}\n状态: {status_str}"

        elif command_name == "URL可访问性":
            if not data or 'url' not in data:
                return "URL可访问性检查失败"
            
            url = data.get('url', 'N/A')
            status = data.get('status', 'N/A')
            
            status_desc = "✅ 可访问" if 200 <= status < 300 else f"❌ 不可访问 ({status})"
            
            return f"[URL可访问性]\n{status_desc}\nURL: {url}"

        elif command_name == "端口扫描":
            if not data or 'ip' not in data:
                return "端口扫描失败"

            ip = data.get('ip', 'N/A')
            port = data.get('port', 'N/A')
            protocol = data.get('protocol', 'N/A')
            port_status = data.get('port_status', 'N/A')

            status_map = {
                'open': '🟢 开放',
                'closed': '🔴 关闭',
                'filtered': '🟡 过滤',
                'timeout': '⏰ 超时'
            }
            status_desc = status_map.get(port_status, port_status)

            return f"[端口扫描]\nIP: {ip}\n端口: {port}/{protocol}\n状态: {status_desc}"

        elif command_name == "MC玩家查询":
            if not data or 'username' not in data:
                return "未查询到玩家信息"
            
            username = data.get('username', 'N/A')
            uuid = data.get('uuid', 'N/A')
            skin_url = data.get('skin_url', 'N/A')
            
            return f"[MC玩家查询]\n用户名: {username}\nUUID: {uuid}\n皮肤URL: {skin_url}"



        elif command_name == "程序员历史上的今天":
            if not data or 'events' not in data:
                return "程序员历史上的今天查询失败"

            date = data.get('date', 'N/A')
            events = data.get('events', [])
            message = data.get('message', 'N/A')

            event_list = []
            for i, event in enumerate(events, 1):  # 显示所有事件，不只是前5个
                year = event.get('year', 'N/A')
                title = event.get('title', 'N/A')
                description = event.get('description', 'N/A')
                category = event.get('category', 'N/A')
                importance = event.get('importance', 'N/A')
                source = event.get('source', 'N/A')
                tags = event.get('tags', [])
                
                tags_str = ', '.join(tags) if tags else 'N/A'
                
                event_info = f"{i}. [{year}] {title}\n   📚 分类: {category}\n   ⭐ 重要性: {importance}\n   🏷️ 标签: {tags_str}\n   📖 来源: {source}\n   📝 {description}"
                event_list.append(event_info)

            event_str = "\n\n".join(event_list)
            return f"[程序员历史上的今天]\n📅 日期: {date}\n📊 总事件数: {len(events)}\n\n{event_str}"

        elif command_name == "网页元数据提取":
            if not data or 'page_url' not in data:
                return "网页元数据提取失败"

            page_url = data.get('page_url', 'N/A')
            title = data.get('title', 'N/A')
            description = data.get('description', 'N/A')
            keywords = data.get('keywords', [])
            favicon_url = data.get('favicon_url', 'N/A')
            language = data.get('language', 'N/A')
            author = data.get('author', 'N/A')
            published_time = data.get('published_time', 'N/A')
            canonical_url = data.get('canonical_url', 'N/A')
            generator = data.get('generator', 'N/A')
            open_graph = data.get('open_graph', {})
            
            keywords_str = ", ".join(keywords[:5]) if keywords else "N/A"  # 只显示前5个关键词

            og_info = ""
            if open_graph:
                og_title = open_graph.get('title', 'N/A')
                og_description = open_graph.get('description', 'N/A')
                og_image = open_graph.get('image', 'N/A')
                og_info = f"\nOG标题: {og_title}\nOG描述: {og_description}\nOG图片: {og_image}"

            return f"[网页元数据提取]\n页面URL: {page_url}\n标题: {title}\n描述: {description}\n关键词: {keywords_str}\n语言: {language}\n作者: {author}\n发布时间: {published_time}\n规范URL: {canonical_url}\n生成器: {generator}\nFavicon: {favicon_url}{og_info}"

        elif command_name == "时间戳转换":
            if not data or 'datetime' not in data:
                return "时间戳转换失败"
            
            datetime_str = data.get('datetime', 'N/A')
            timestamp = data.get('timestamp', 'N/A')
            
            return f"[时间戳转换]\n日期时间: {datetime_str}\n时间戳: {timestamp}"

        elif command_name == "JSON格式化":
            if not data or 'content' not in data:
                return "JSON格式化失败"

            formatted_content = data.get('content', 'N/A')

            return f"[JSON格式化]\n{formatted_content}"

        elif command_name == "生成你们怎么不说话了表情包":
            return "[生成你们怎么不说话了表情包]\n表情包已生成并发送"

        else:
            # 默认格式化，直接返回原始数据的字符串表示
            if data:
                # 尝试找出一些通用字段进行格式化
                if 'message' in data:
                    return f"[UAPI响应]\n{data['message']}"
                elif 'text' in data:
                    return f"[UAPI响应]\n{data['text']}"
                elif 'result' in data:
                    return f"[UAPI响应]\n{data['result']}"
                else:
                    return f"[UAPI响应]\n{str(data)}"
            else:
                return "[UAPI响应]\n无数据返回"

    except Exception as e:
        logging.error(f"格式化UAPI响应失败: {e}")
        return f"UAPI信息格式化错误: {str(e)}"


# UAPI命令帮助信息字典
UAPI_COMMAND_HELP = {
"B站直播间查询": """【B站直播间查询 帮助】
功能：查询B站直播间的详细信息
用法：B站直播间查询 [mid] 或 B站直播间查询 room_id [room_id]
参数详解：
- mid: B站用户ID（可选参数）
  * 用户的唯一数字标识符
  * 如：672328094（某主播的UID）
  * 查询该用户的直播间信息
- room_id: 直播间ID（可选参数）
  * 直播间的唯一数字标识符
  * 如：22637261（某个直播间的房间号）
  * 直接查询指定直播间
使用说明：
- 两种查询方式任选其一
- 如果同时提供两个参数，优先使用room_id
- 返回信息包括：直播间标题、主播信息、在线人数、直播状态等
使用示例：
- B站直播间查询 672328094
- B站直播间查询 room_id 22637261
注意事项：
- 需要有效的B站用户ID或直播间ID
- 直播间ID通常比用户ID更容易获得
- 离线直播间也能查询基本信息""",

"B站用户查询": """【B站用户查询 帮助】
功能：查询B站用户的详细个人信息
用法：B站用户查询 [UID]
参数详解：
- UID: B站用户唯一标识符（必选参数）
  * 用户的数字ID，如483307278
  * 可在B站用户主页URL中找到
  * 也可通过其他方式获取
返回信息包含：
- 用户昵称和头像
- 用户签名和个人简介
- 关注数和粉丝数
- 性别信息
- 等级和认证信息
- 注册时间和生日
使用示例：
- B站用户查询 483307278
- B站用户查询 282994
注意事项：
- UID必须是有效的数字ID
- 部分隐私信息可能无法获取
- 被注销或封禁的账号可能查询失败""",

"B站投稿查询": """【B站投稿查询 帮助】
功能：查询B站用户的历史投稿视频列表
用法：B站投稿查询 [mid]
参数详解：
- mid: B站用户ID（必选参数）
  * 用户的唯一数字标识符
  * 如：483307278
  * 可在B站用户主页找到
返回信息包含：
- 最新投稿的视频列表
- 视频标题和封面
- 播放量、点赞数、评论数
- 投稿时间
- 视频时长
- 分区信息
使用示例：
- B站投稿查询 483307278
- B站投稿查询 282994
适用场景：
- 了解UP主的创作历史
- 查看最受欢迎的作品
- 研究内容创作趋势
注意事项：
- 只返回公开的投稿视频
- 按时间倒序排列
- 默认返回最新的一些投稿""",

"GitHub仓库查询": """【GitHub仓库查询 帮助】
功能：查询GitHub开源仓库的详细信息
用法：GitHub仓库查询 [owner] [repo]
参数详解：
- owner: 仓库拥有者（必选参数）
  * GitHub用户名或组织名
  * 如：torvalds（Linus Torvalds）
  * microsoft、google等组织
- repo: 仓库名称（必选参数）
  * 仓库的具体名称
  * 如：linux（Linux内核）
  * react、vue等项目名
返回信息包含：
- 仓库基本信息（名称、描述、创建时间）
- Star数量和Fork数量
- 语言统计和大小
- 最后更新时间
- 许可证信息
- Issues和Pull Requests数量
使用示例：
- GitHub仓库查询 torvalds linux
- GitHub仓库查询 facebook react
- GitHub仓库查询 microsoft vscode
适用场景：
- 了解开源项目信息
- 评估项目活跃度
- 查看技术栈和贡献情况
注意事项：
- 需要正确的用户名和仓库名
- 私有仓库无法查询
- 遵守GitHub API使用限制""",

"热榜查询": """【热榜查询 帮助】
功能：查询各大平台的实时热门榜单
用法：热榜查询 [type]
参数详解：
- type: 平台类型（可选参数，默认返回微博热榜）
  * weibo：新浪微博热搜榜
  * zhihu：知乎热榜
  * baidu：百度热搜榜
  * toutiao：今日头条热榜
  * douban-movie：豆瓣电影排行榜
  * tieba：百度贴吧热议榜
  * acfun：AcFun热榜
  * bilibili：哔哩哔哩热榜
返回信息包含：
- 排名前50的热门话题/内容
- 标题和简要描述
- 热度指数或浏览量
- 更新时间
使用示例：
- 热榜查询
- 热榜查询 weibo
- 热榜查询 zhihu
- 热榜查询 baidu
适用场景：
- 了解时事热点
- 追踪网络流行趋势
- 获取热门话题讨论
注意事项：
- 不同平台更新频率不同
- 部分平台可能存在地域限制
- 数据来源于公开接口""",

"世界时间查询": """【世界时间查询 帮助】
功能：查询世界各地的当前时间
用法：世界时间查询 [city]
参数详解：
- city: 时区名称（可选参数，默认Asia/Shanghai）
  * 使用IANA时区数据库标准
  * 格式：大洲/城市
  * 如：Asia/Shanghai（上海）
  * Europe/London（伦敦）
  * America/New_York（纽约）
常用时区示例：
- Asia/Shanghai：中国标准时间
- Asia/Tokyo：日本标准时间
- Europe/London：英国时间
- America/New_York：美国东部时间
- America/Los_Angeles：美国西部时间
返回信息包含：
- 当前日期和时间
- 时区信息
- 与UTC的时间差
- 是否处于夏令时
使用示例：
- 世界时间查询
- 世界时间查询 Asia/Shanghai
- 世界时间查询 Europe/London
- 世界时间查询 America/New_York
注意事项：
- 时区名称区分大小写
- 支持主要城市和时区
- 时间基于网络时间同步""",

"天气查询": """【天气查询 帮助】
功能：查询指定城市的当前天气状况
用法：天气查询 [city]
参数详解：
- city: 城市名称（必选参数）
  * 支持中文城市名：北京、上海、广州
  * 支持拼音：beijing、shanghai
  * 支持英文：Beijing、Shanghai
  * 支持城市代码
返回信息包含：
- 当前温度和体感温度
- 天气状况描述（晴、雨、雪等）
- 湿度和风力信息
- 能见度和气压
- 空气质量指数
使用示例：
- 天气查询 北京
- 天气查询 上海
- 天气查询 guangzhou
- 天气查询 New York
注意事项：
- 支持国内外主要城市
- 城市名称尽量准确
- 返回数据基于实时气象信息""",

"手机归属地查询": """【手机归属地查询 帮助】
功能：查询中国大陆手机号码的归属地信息
用法：手机归属地查询 [phone]
参数详解：
- phone: 11位手机号码（必选参数）
  * 必须是中国大陆手机号
  * 格式：11位数字，如13800138000
  * 支持移动、联通、电信等运营商
返回信息包含：
- 手机号码段信息
- 归属地省市
- 运营商信息
- 邮政编码
- 区号信息
使用示例：
- 手机归属地查询 13800138000
- 手机归属地查询 15912345678
- 手机归属地查询 18888888888
适用范围：
- 仅支持中国大陆手机号码
- 港澳台地区号码暂不支持
- 虚拟运营商号码可能查询不准确
注意事项：
- 号码必须完整且有效
- 数据来源于公开数据库
- 仅供参考，实际情况可能有变化""",

"随机数生成": """【随机数生成 帮助】
功能：生成指定范围内的随机数
用法：随机数生成 [min] [max] [count] [allow_repeat] [allow_decimal] [decimal_places]
参数详解：
- min: 最小值（必选参数）
  * 数字范围的下限
  * 可以为负数
  * 如：1、-100、0
- max: 最大值（必选参数）
  * 数字范围的上限
  * 必须大于最小值
  * 如：100、1000、50
- count: 生成数量（可选参数，默认1）
  * 要生成的随机数个数
  * 范围：1-100
- allow_repeat: 是否允许重复（可选参数，默认true）
  * true：允许生成重复数字
  * false：不允许重复（数量不能超过范围）
- allow_decimal: 是否允许小数（可选参数，默认false）
  * true：生成小数
  * false：生成整数
- decimal_places: 小数位数（可选参数，默认2）
  * 当allow_decimal为true时生效
  * 范围：1-10
使用示例：
- 随机数生成 1 100
- 随机数生成 1 100 5 true false 2
- 随机数生成 10 20 10
- 随机数生成 -50 50 5 false
- 随机数生成 0 1 1 true true 3
应用场景：
- 抽奖活动
- 随机分组
- 游戏数值生成
- 统计抽样
注意事项：
- 最大值必须大于最小值
- 不允许重复时数量不能超过范围
- 小数位数最多10位""",

"ICP备案查询": """【ICP备案查询 帮助】
功能：查询域名在中国的ICP备案信息
用法：ICP备案查询 [domain]
参数详解：
- domain: 域名（必选参数）
  * 完整域名，如baidu.com
  * 支持二级域名，如www.baidu.com
  * 不需要包含http://或https://
返回信息包含：
- 备案号
- 主办单位名称
- 主办单位性质
- 网站名称
- 审核时间
- 备案状态
使用示例：
- ICP备案查询 baidu.com
- ICP备案查询 www.taobao.com
- ICP备案查询 qq.com
注意事项：
- 数据来源于工信部备案系统
- 查询结果仅供参考
- 备案信息可能有延迟更新""",

"IP信息查询": """【IP信息查询 帮助】
功能：查询IP地址或域名的地理位置信息
用法：IP信息查询 [ip|domain]
参数详解：
- ip|domain: IP地址或域名（必选参数）
  * IP地址格式：如8.8.8.8、114.114.114.114
  * 域名格式：如baidu.com、google.com
  * 支持IPv4和IPv6地址
返回信息包含：
- 国家和地区信息
- 省市位置
- 运营商信息
- 经纬度坐标
- 时区信息
使用示例：
- IP信息查询 8.8.8.8
- IP信息查询 baidu.com
- IP信息查询 114.114.114.114
- IP信息查询 github.com
适用场景：
- 网络故障排查
- 访问来源分析
- 地理位置验证
- 网络安全检测
注意事项：
- 查询频率可能有限制
- 部分CDN节点位置可能不准确
- 内网IP无法查询地理位置""",

"WHOIS查询": """【WHOIS查询 帮助】
功能：查询域名的注册和管理信息
用法：WHOIS查询 [domain] [format]
参数详解：
- domain: 域名（必选参数）
  * 完整域名，如google.com
  * 支持各种顶级域名
  * 不需要包含www前缀
- format: 返回格式（可选参数，默认json）
  * json：结构化JSON格式（推荐）
  * text：纯文本格式
返回信息包含：
- 域名注册商信息
- 注册和到期时间
- 域名状态
- DNS服务器信息
- 注册人联系信息（部分隐藏）
使用示例：
- WHOIS查询 google.com
- WHOIS查询 baidu.com json
- WHOIS查询 github.com text
适用场景：
- 域名信息核查
- 域名到期提醒
- 域名纠纷处理
- 网络安全调查
注意事项：
- 部分敏感信息会被隐私保护隐藏
- 不同注册商返回信息格式可能差异
- 查询过于频繁可能被限制""",

"Ping主机": """【Ping主机 帮助】
功能：测试目标主机的网络连通性和响应时间
用法：Ping主机 [host]
参数详解：
- host: 主机地址或IP（必选参数）
  * 域名格式：如google.com、baidu.com
  * IP地址格式：如8.8.8.8、114.114.114.114
  * 支持IPv4和IPv6
返回信息包含：
- Ping包传输统计
- 平均响应时间
- 丢包率
- 最小/最大/平均延迟
使用示例：
- Ping主机 google.com
- Ping主机 8.8.8.8
- Ping主机 baidu.com
- Ping主机 114.114.114.114
适用场景：
- 网络连通性测试
- 网络延迟测量
- 服务器状态检查
- 网络故障诊断
注意事项：
- 部分主机可能禁用Ping响应
- 防火墙可能阻止Ping请求
- 结果受网络环境影响""",

"DNS查询": """【DNS查询 帮助】
功能：查询域名的各种DNS记录信息
用法：DNS查询 [domain] [type]
参数详解：
- domain: 域名（必选参数）
  * 完整域名，如google.com
  * 支持子域名，如www.google.com
  * 不需要包含协议前缀
- type: 记录类型（可选参数，默认A记录）
  * A：IPv4地址记录
  * AAAA：IPv6地址记录
  * CNAME：别名记录
  * MX：邮件交换记录
  * NS：域名服务器记录
  * TXT：文本记录
  * SRV：服务记录
返回信息包含：
- 记录类型和值
- TTL（生存时间）
- 优先级（MX记录）
- 多个记录的完整列表
使用示例：
- DNS查询 google.com
- DNS查询 google.com A
- DNS查询 google.com MX
- DNS查询 baidu.com NS
- DNS查询 qq.com TXT
应用场景：
- 域名解析问题排查
- 邮件服务器配置验证
- CDN配置检查
- 网络安全分析
注意事项：
- 不同记录类型返回格式不同
- 部分记录可能被CDN服务商修改
- DNS缓存可能影响查询结果""",

"URL可访问性": """【URL可访问性 帮助】
功能：检查指定URL的可访问性和响应状态
用法：URL可访问性 [url]
参数详解：
- url: 完整URL地址（必选参数）
  * 必须包含协议：http://或https://
  * 完整格式：https://www.example.com
  * 支持带路径和参数的URL
返回信息包含：
- HTTP状态码
- 响应时间
- 服务器响应头信息
- 页面标题（如果可获取）
- 错误详情（如访问失败）
使用示例：
- URL可访问性 https://www.baidu.com
- URL可访问性 https://github.com
- URL可访问性 http://httpbin.org/status/200
- URL可访问性 https://www.nonexistent-domain.com
适用场景：
- 网站状态监控
- 接口可用性检查
- 网络连通性测试
- 故障排查辅助
注意事项：
- 必须提供完整URL（包含协议）
- 可能受到防火墙或网络策略限制
- 重定向会影响响应时间""",

"端口扫描": """【端口扫描 帮助】
功能：扫描目标主机指定端口的开放状态
用法：端口扫描 [host] [port] [protocol]
参数详解：
- host: 主机地址（必选参数）
  * IP地址：如127.0.0.1、192.168.1.1
  * 域名：如google.com、localhost
- port: 端口号（必选参数）
  * 常用端口：80(HTTP)、443(HTTPS)、22(SSH)
  * 端口范围：1-65535
- protocol: 协议（可选参数，默认tcp）
  * tcp：传输控制协议
  * udp：用户数据报协议
返回信息包含：
- 端口状态（开放/关闭/过滤）
- 服务类型（如HTTP、SSH等）
- 响应时间
- 详细错误信息（如连接失败）
使用示例：
- 端口扫描 127.0.0.1 80
- 端口扫描 google.com 443 tcp
- 端口扫描 8.8.8.8 53 udp
- 端口扫描 baidu.com 22
常见端口说明：
- 21：FTP文件传输
- 22：SSH安全壳
- 23：Telnet远程登录
- 25：SMTP邮件传输
- 53：DNS域名解析
- 80：HTTP网页服务
- 443：HTTPS加密网页
- 3306：MySQL数据库
注意事项：
- 未经授权扫描他人服务器可能违法
- 扫描速度和频率有限制
- 防火墙可能阻止扫描请求
- 仅用于合法的安全测试""",

"MC服务器查询": """【MC服务器查询 帮助】
功能：查询Minecraft服务器的实时状态和信息
用法：MC服务器查询 [server]
参数详解：
- server: 服务器地址（必选参数）
  * 完整地址格式：mc.hypixel.net
  * 带端口号：localhost:25565
  * IP地址格式：127.0.0.1:25565
  * 默认端口为25565，可省略
返回信息包含：
- 服务器在线状态
- 当前在线玩家数
- 服务器最大玩家容量
- 服务器版本信息
- 服务器描述/欢迎信息
- 延迟时间
使用示例：
- MC服务器查询 mc.hypixel.net
- MC服务器查询 play.minesuperior.com
适用场景：
- 检查服务器是否在线
- 查看服务器负载情况
- 验证服务器版本兼容性
- 监控服务器状态
注意事项：
- 服务器必须开启查询功能
- 部分服务器可能禁用状态查询
- 网络延迟影响响应时间
- 只能查询Java版Minecraft服务器""",

"Steam用户查询": """【Steam用户查询 帮助】
功能：查询Steam用户的公开个人信息
用法：Steam用户查询 [steamid]
参数详解：
- steamid: Steam用户ID（必选参数）
  * 64位SteamID格式：76561197960435530
  * Steam自定义URL：如customurl
  * 社区ID：如123456789
返回信息包含：
- 用户昵称和头像
- 用户等级
- 好友数量
- 游戏总时长
- 最近游玩的游戏
- 账号创建时间
- 在线状态
使用示例：
- Steam用户查询 76561197960435530
- Steam用户查询 customurl
适用场景：
- 查看朋友游戏信息
- 验证用户身份
- 了解游戏偏好
- 社交互动参考
注意事项：
- 只能查询公开资料
- 隐私设置会影响可见信息
- 部分信息可能不完整
- 需要有效的SteamID""",

"Epic免费游戏": """【Epic免费游戏 帮助】
功能：查询Epic游戏商城当前和未来的免费游戏
用法：Epic免费游戏
功能说明：
此命令无需参数，直接执行即可
返回信息包含：
- 当前免费游戏列表
- 游戏名称和封面图片
- 原价和折扣信息
- 免费领取截止时间
- 游戏简介和评分
- 下周即将免费的游戏预告
使用示例：
- Epic免费游戏
适用场景：
- 获取免费游戏信息
- 规划游戏领取时间
- 了解游戏优惠活动
- 发现新游戏
注意事项：
- 免费游戏每周更新
- 领取有时间限制
- 部分地区可能不可用
- 需要登录Epic账户才能领取""",

"MC玩家查询": """【MC玩家查询 帮助】
功能：查询Minecraft玩家的基本信息和皮肤
用法：MC玩家查询 [username]
参数详解：
- username: 玩家名（必选参数）
  * Minecraft官方用户名
  * 区分大小写
  * 如：Notch、Dream、Technoblade
返回信息包含：
- 玩家UUID
- 玩家皮肤头像
- 玩家披风信息
- 账号状态
- 历史用户名记录
使用示例：
- MC玩家查询 Notch
- MC玩家查询 Dream
- MC玩家查询 Technoblade
适用场景：
- 验证玩家身份
- 获取玩家皮肤
- 查看账号信息
- 玩家社区互动
注意事项：
- 需要是正版Minecraft账号
- 用户名必须准确
- 部分信息可能涉及隐私
- 仅支持Java版玩家查询""",


"MD5哈希": """【MD5哈希 帮助】
功能：计算MD5哈希值
用法：MD5哈希 [text]
示例：MD5哈希 'hello world'
示例：MD5哈希 hello
参数说明：
- text: 要计算哈希的文本（可用单引号括起来以支持带空格的文本）""",



"MD5校验": """【MD5校验 帮助】
功能：校验MD5哈希值
用法：MD5校验 [text] [hash]
示例：MD5校验 'hello world' 5d41402abc4b2a76b9719d911017c592
示例：MD5校验 hello 5d41402abc4b2a76b9719d911017c592
参数说明：
- text: 原文（可用单引号括起来以支持带空格的文本）
- hash: MD5哈希值""",

"Base64编码": """【Base64编码 帮助】
功能：Base64编码
用法：Base64编码 [text]
示例：Base64编码 'hello world'
示例：Base64编码 hello
参数说明：
- text: 要编码的文本（可用单引号括起来以支持带空格的文本）""",

"Base64解码": """【Base64解码 帮助】
功能：Base64解码
用法：Base64解码 [text]
示例：Base64解码 'aGVsbG8gd29ybGQ='
示例：Base64解码 aGVsbG8=
参数说明：
- text: 要解码的Base64文本（可用单引号括起来以支持带空格的文本）""",

"AES加密": """【AES加密 帮助】
功能：AES加密
用法：AES加密 [key] [text]
示例：AES加密 mypassword 'hello world'
示例：AES加密 mypassword hello
参数说明：
- key: 加密密钥
- text: 要加密的文本（可用单引号括起来以支持带空格的文本）""",

"AES解密": """【AES解密 帮助】
功能：AES解密
用法：AES解密 [key] [ciphertext] [nonce]
示例：AES解密 mypassword 'encrypted text' nonce123
示例：AES解密 mypassword encrypted nonce123
参数说明：
- key: 解密密钥
- ciphertext: 密文（可用单引号括起来以支持带空格的文本）
- nonce: 随机数""",

"AES高级加密": """【AES高级加密 帮助】
功能：高级AES加密
用法：AES高级加密 [key] [text] [mode] [padding]
示例：AES高级加密 mypassword 'hello world' GCM PKCS7
示例：AES高级加密 mypassword hello GCM PKCS7
参数说明：
- key: 加密密钥
- text: 要加密的文本（可用单引号括起来以支持带空格的文本）
- mode: 加密模式
- padding: 填充方式""",

"AES高级解密": """【AES高级解密 帮助】
功能：高级AES解密
用法：AES高级解密 [key] [ciphertext] [mode] [padding]
示例：AES高级解密 mypassword 'encrypted text' GCM NONE
示例：AES高级解密 mypassword encrypted GCM NONE
参数说明：
- key: 解密密钥
- ciphertext: 密文（可用单引号括起来以支持带空格的文本）
- mode: 加密模式
- padding: 填充方式""",

"格式转换": """【格式转换 帮助】
功能：文本格式转换
用法：格式转换 [text] [from] [to]
示例：格式转换 'hello world' plain base64
示例：格式转换 hello plain base64
参数说明：
- text: 要转换的文本（可用单引号括起来以支持带空格的文本）
- from: 源格式
- to: 目标格式
支持格式：plain, base64, hex, url, html, unicode, binary, md5, sha1, sha256, sha512""",

    "随机图片": """【随机图片 帮助】
功能：获取随机图片
用法：随机图片 [category] [type]
示例：随机图片 acg
示例：随机图片 landscape
参数说明：
- category: 图片类别
- type: 图片子类别
支持类别：acg, landscape, anime, pc_wallpaper, mobile_wallpaper, ai_drawing, bq, furry等""",

"答案之书": """【答案之书 帮助】
功能：获取来自神秘答案之书的随机回答
用法：答案之书 [question]
参数详解：
- question: 问题（可选参数）
  * 可以是任何你想问的问题
  * 如：我今天会有好运吗？
  * 会得到随机的神秘回答
返回信息包含：
- 神秘的答案文本
- 富有哲理的回答
- 趣味性的建议
使用示例：
- 答案之书
- 答案之书 我今天会有好运吗？
- 答案之书 我应该辞职吗？
- 答案之书 他会喜欢我吗？
适用场景：
- 娱乐消遣
- 决策参考
- 心理暗示
- 趣味互动
注意事项：
- 答案仅供娱乐，不要过于认真
- 回答是随机生成的
- 不能替代理性思考和专业建议""",



"随机字符串": """【随机字符串 帮助】
功能：生成指定长度和类型的随机字符串
用法：随机字符串 [length] [type]
参数详解：
- length: 字符串长度（可选参数，默认16）
  * 数字，如：8、16、32
  * 长度范围：1-1000
- type: 字符类型（可选参数，默认alphanumeric）
  * numeric：纯数字（0-9）
  * lower：小写字母（a-z）
  * upper：大写字母（A-Z）
  * alpha：字母（a-zA-Z）
  * alphanumeric：字母数字组合（默认）
  * hex：十六进制（0-9a-f）
返回信息包含：
- 生成的随机字符串
- 字符串长度信息
使用示例：
- 随机字符串
- 随机字符串 16
- 随机字符串 32 alphanumeric
- 随机字符串 8 numeric
- 随机字符串 10 hex
应用场景：
- 密码生成
- 验证码创建
- 唯一标识符
- 测试数据生成
注意事项：
- 长度过大会影响生成速度
- 不同类型安全性不同
- 生成结果每次都不相同""",

"必应壁纸": """【必应壁纸 帮助】
功能：获取必应搜索引擎的每日精选壁纸
用法：必应壁纸
功能说明：
此命令无需参数，直接执行即可
返回信息包含：
- 高清壁纸图片
- 壁纸标题和描述
- 拍摄地点信息
- 版权信息
使用示例：
- 必应壁纸
适用场景：
- 桌面壁纸更换
- 图片欣赏
- 摄影作品收集
- 美图分享
注意事项：
- 每日更新一张新壁纸
- 图片质量很高
- 可能因网络原因加载缓慢
- 版权归原作者所有""",

"上传图片": """【上传图片 帮助】
功能：将Base64编码的图片数据上传并处理
用法：上传图片 [base64_data]
参数详解：
- base64_data: Base64编码的图片数据（必选参数）
  * 完整的Base64图片编码字符串
  * 支持常见图片格式：JPG、PNG、GIF等
  * 数据较长，建议使用代码或工具生成
返回信息包含：
- 上传成功的确认信息
- 图片处理结果
- 可能的错误提示
使用示例：
- 上传图片 [完整的Base64数据]
适用场景：
- 图片分享
- 图床服务
- 图片处理前置步骤
注意事项：
- Base64数据必须完整有效
- 图片大小有限制
- 仅支持特定格式的图片""",

"图片转Base64": """【图片转Base64 帮助】
功能：将网络图片转换为Base64编码格式
用法：图片转Base64 [url]
参数详解：
- url: 图片URL（必选参数）
  * 完整的图片网址
  * 支持http和https协议
  * 如：https://example.com/image.jpg
返回信息包含：
- 图片的完整Base64编码数据
- 编码后的数据长度
使用示例：
- 图片转Base64 https://example.com/image.jpg
- 图片转Base64 https://avatars.githubusercontent.com/u/123456
适用场景：
- 图片嵌入到网页或代码中
- 数据传输格式转换
- 图片存储和备份
注意事项：
- 图片必须可公开访问
- 大图片转换后数据量很大
- 转换过程需要网络连接""",

"生成二维码": """【生成二维码 帮助】
功能：根据文本内容生成二维码图片
用法：生成二维码 [text] [size]
参数详解：
- text: 二维码内容（必选参数）
  * 可以是网址、文本、联系方式等
  * 如：https://www.bilibili.com
  * 或：Hello World
- size: 二维码尺寸（可选参数，默认256）
  * 像素大小，如：256、512
  * 范围：64-1024像素
返回信息包含：
- 生成的二维码图片
- 图片尺寸信息
使用示例：
- 生成二维码 https://www.bilibili.com
- 生成二维码 Hello 512
- 生成二维码 tel:13800138000 300
适用场景：
- 网站链接分享
- 联系方式交换
- 产品信息展示
- 活动推广
注意事项：
- 内容过长会影响二维码密度
- 尺寸过小可能难以扫描
- 建议在光线充足环境下扫描""",

"GrAvatar头像": """【GrAvatar头像 帮助】
功能：根据邮箱地址获取对应的Gravatar全球头像
用法：GrAvatar头像 [email]
参数详解：
- email: 邮箱地址（必选参数）
  * 有效的电子邮箱地址
  * 如：user@example.com
  * 系统会自动进行MD5哈希处理
返回信息包含：
- 对应的Gravatar头像图片
- 头像尺寸信息
使用示例：
- GrAvatar头像 user@example.com
- GrAvatar头像 john.doe@gmail.com
适用场景：
- 用户头像显示
- 评论系统头像
- 社区论坛头像
- 个人资料页面
注意事项：
- 邮箱必须在Gravatar注册过
- 未注册的邮箱显示默认头像
- 头像更新可能有延迟""",

"摸摸头": """【摸摸头 帮助】
功能：生成有趣的摸摸头GIF动图
用法：摸摸头 [qq] 或 摸摸头 @某人
参数详解：
- qq: QQ号码（可选参数）
  * 直接输入QQ号码
  * 如：10001、123456789
- @某人: 支持@群成员自动提取QQ号
  * 在群聊中@指定用户
  * 系统自动识别被@用户的QQ号
返回信息包含：
- 生成的摸摸头GIF动图
- 动图文件
使用示例：
- 摸摸头 10001
- 摸摸头 @张三
- 摸摸头 123456789
适用场景：
- 群聊互动娱乐
- 表达友好情感
- 活跃聊天氛围
- 趣味性社交
注意事项：
- 需要在群聊环境中使用
- @功能需要群成员支持
- 生成的GIF文件较大""",

"生成你们怎么不说话了表情包": """【生成你们怎么不说话了表情包 帮助】
功能：生成经典的"你们怎么不说话了"梗图表情包
用法：生成你们怎么不说话了表情包 [top_text] [bottom_text]
参数详解：
- top_text: 上方文字（可选参数）
  * 表情包上方显示的文字
  * 如：玩UAPI
  * 可以为空
- bottom_text: 下方文字（可选参数）
  * 表情包下方显示的文字
  * 如：们不要玩UAPI了
  * 可以为空
返回信息包含：
- 生成的表情包图片
- 自定义文字的表情包
使用示例：
- 生成你们怎么不说话了表情包 玩UAPI 们不要玩UAPI了
- 生成你们怎么不说话了表情包 学习 们不要学了
- 生成你们怎么不说话了表情包
适用场景：
- 群聊娱乐互动
- 表达特定情境
- 制作个性化表情
- 趣味性沟通
注意事项：
- 文字内容请保持文明
- 表情包仅供娱乐使用
- 文字过长可能显示不全""",

"翻译": """【翻译 帮助】
功能：多语言文本翻译服务
用法：翻译 [to_lang] [text]
参数详解：
- to_lang: 目标语言代码（必选参数）
  * zh-CHS：简体中文
  * zh-CHT：繁体中文
  * en：英语
  * ja：日语
  * ko：韩语
  * fr：法语
  * de：德语
  * es：西班牙语
  * ru：俄语
  * ar：阿拉伯语
  * 更多语言代码请参考语言列表
- text: 要翻译的文本（必选参数）
  * 支持单引号括起包含空格的句子
  * 如：'hello world today'
  * 或直接输入：hello world
返回信息包含：
- 翻译后的文本内容
- 源语言和目标语言标识
- 翻译质量评估
使用示例：
- 翻译 zh-CHS hello world
- 翻译 en 你好世界
- 翻译 zh-CHS 'hello world today'
- 翻译 ja Hello
适用场景：
- 跨语言交流
- 学习外语
- 国际业务沟通
- 内容本地化
注意事项：
- 翻译质量取决于原文清晰度
- 长文本可能需要更多处理时间
- 某些专业术语可能翻译不够准确""",

"一言": """【一言 帮助】
功能：获取随机的诗词名句或名人名言
用法：一言
功能说明：
此命令无需参数，直接执行即可
返回信息包含：
- 随机选取的经典诗词或名言
- 作者信息
- 作品出处
- 文字内容
使用示例：
- 一言
适用场景：
- 文学欣赏
- 写作灵感
- 心灵鸡汤
- 文化学习
- 日常问候
注意事项：
- 内容来源于经典文学作品
- 每次执行返回不同内容
- 可能包含古文或现代文""",

"网页元数据提取": """【网页元数据提取 帮助】
功能：提取指定网页的元数据信息
用法：网页元数据提取 [url]
参数详解：
- url: 网页URL（必选参数）
  * 完整的网页地址
  * 必须包含http://或https://
  * 如：https://www.bilibili.com
  * https://github.com
返回信息包含：
- 网页标题
- 页面描述
- 关键词信息
- 作者信息
- 发布时间
- 字符集编码
使用示例：
- 网页元数据提取 https://www.bilibili.com
- 网页元数据提取 https://github.com
- 网页元数据提取 https://www.zhihu.com
适用场景：
- SEO优化分析
- 网页信息收集
- 内容抓取预处理
- 网站分析
注意事项：
- 网页必须可公开访问
- 部分网站可能反爬虫保护
- 提取速度受网络影响""",

"时间戳转换": """【时间戳转换 帮助】
功能：在Unix时间戳和人类可读日期之间相互转换
用法：时间戳转换 [time]
参数详解：
- time: 时间戳或日期字符串（必选参数）
  * Unix时间戳：如1698380645
  * 日期时间格式：如2023-10-27 15:04:05
  * 支持多种日期格式
返回信息包含：
- 转换后的时间格式
- 对应的另一种时间表示
- 时区信息
使用示例：
- 时间戳转换 1698380645
- 时间戳转换 2023-10-27 15:04:05
- 时间戳转换 2023/10/27 15:04:05
适用场景：
- 程序开发调试
- 日志时间分析
- 系统维护
- 数据处理
注意事项：
- 时间戳为UTC时间
- 日期格式需标准规范
- 支持常用的时间格式""",

"JSON格式化": """【JSON格式化 帮助】
功能：将混乱的JSON字符串格式化为易读的标准格式
用法：JSON格式化 [content]
参数详解：
- content: JSON内容（必选参数）
  * 完整的JSON字符串
  * 可以是压缩格式或混乱格式
  * 如：{"name":"test","value":123}
返回信息包含：
- 格式化后的标准JSON
- 良好的缩进和换行
- 语法验证结果
使用示例：
- JSON格式化 {"name":"test","value":123}
- JSON格式化 {'users':[{'id':1,'name':'张三'},{'id':2,'name':'李四'}]}
适用场景：
- API调试
- 配置文件编辑
- 数据分析
- 代码开发
注意事项：
- JSON语法必须正确
- 支持嵌套结构
- 会自动添加适当的缩进""",

"每日新闻图": """【每日新闻图 帮助】
功能：获取当日精选的新闻资讯汇总图片
用法：每日新闻图
功能说明：
此命令无需参数，直接执行即可
返回信息包含：
- 当日重要新闻摘要图片
- 热点事件汇总
- 时效性强的资讯内容
- 精美的图文排版
使用示例：
- 每日新闻图
适用场景：
- 快速了解当日要闻
- 朋友圈分享
- 信息获取
- 时事关注
注意事项：
- 每日定时更新
- 内容来源于权威媒体
- 图片质量较高
- 更新时间可能有延迟""",

"程序员历史上的今天": """【程序员历史上的今天 帮助】
功能：查询历史上今天发生的程序员相关重要事件
用法：程序员历史上的今天
功能说明：
此命令无需参数，直接执行即可
返回信息包含：
- 历史上今天发生的技术事件
- 重要软件发布记录
- 科技公司成立纪念
- 程序员节日信息
- 技术发展里程碑
使用示例：
- 程序员历史上的今天
适用场景：
- 技术历史文化了解
- 程序员节日庆祝
- 技术发展历程学习
- 行业知识拓展
注意事项：
- 内容聚焦程序员和技术领域
- 事件真实可靠
- 每天内容可能不同""",

"程序员历史事件": """【程序员历史事件 帮助】
功能：查询指定日期历史上发生的程序员相关事件
用法：程序员历史事件 [month] [day]
参数详解：
- month: 月份（必选参数）
  * 数字格式：1-12
  * 如：4表示四月
- day: 日期（必选参数）
  * 数字格式：1-31
  * 如：1表示第一天
返回信息包含：
- 指定日期的历史技术事件
- 重要产品发布时间
- 科技公司重大事件
- 技术标准确立时间
使用示例：
- 程序员历史事件 4 1
- 程序员历史事件 10 24
- 程序员历史事件 1 1
适用场景：
- 历史事件查询
- 技术发展回顾
- 特定日期纪念
- 行业知识学习
注意事项：
- 日期必须有效
- 内容专注于技术领域
- 事件经过考证核实"""
}


async def handle_uapi_command(command_name: str, args: List[str], group_id: str, config: Dict[str, Any], user_id: str = None) -> Optional[str]:
    """
    处理UAPI命令
    :param command_name: 命令名称
    :param args: 参数列表
    :param group_id: 群ID
    :param config: 配置
    :param user_id: 用户ID
    :return: 格式化的响应消息
    """
    try:
        # 检查API调用频率限制
        if user_id:
            allowed, reason = check_api_rate_limit(user_id, group_id, config)
            if not allowed:
                return reason

        # 检查UAPI是否启用
        uapi_config = config.get('uapi', {})
        if not uapi_config:
            return "UAPI功能未配置，请检查config.json中的uapi配置"

        # 检查是否请求帮助
        if args and (args[0] == "-h" or args[0] == "-help"):
            help_text = UAPI_COMMAND_HELP.get(command_name, f"【{command_name} 帮助】\n未找到该命令的帮助信息")
            return help_text

        # 创建UAPI客户端
        api = UApiClient(config)

        # 根据命令名称处理不同的UAPI请求
        if command_name == "B站直播间查询":
            if not args or (not args[0].isdigit() and not (len(args) > 1 and args[1].isdigit())):
                return "请提供B站用户mid或直播间room_id\n示例: /B站直播间查询 672328094 或 /B站直播间查询 room_id 22637261"

            mid = None
            room_id = None

            if len(args) == 1:
                # 可能是mid或room_id
                if args[0].isdigit():
                    # 判断长度来决定是mid还是room_id
                    if len(args[0]) > 8:  # 通常room_id更长
                        room_id = args[0]
                    else:
                        mid = args[0]
            elif len(args) >= 2:
                if args[0] in ['mid', 'room_id']:
                    if args[0] == 'mid':
                        mid = args[1]
                    else:
                        room_id = args[1]
                else:
                    # 如果第一个参数不是mid或room_id，则认为是直接传递的ID
                    if args[0].isdigit():
                        if len(args[0]) > 8:
                            room_id = args[0]
                        else:
                            mid = args[0]
                    if args[1].isdigit():
                        if len(args[1]) > 8:
                            room_id = args[1]
                        else:
                            mid = args[1]

            result = await api.get_bilibili_liveroom(mid=mid, room_id=room_id)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "B站直播间查询失败"

        elif command_name == "B站用户查询":
            if not args or not args[0].isdigit():
                return "请提供B站用户UID\n示例: /B站用户查询 483307278"

            # 提前导入需要的模块，以避免在异常处理时出现变量作用域问题
            import aiohttp
            import tempfile

            uid = args[0]
            result = await api.get_bilibili_userinfo(uid=uid)
            if result:
                # 先格式化结果，获得包含文本和头像URL的格式化结果
                formatted_result = format_uapi_response(command_name, result, config)
                
                # 检查格式化结果是否是包含头像URL的特殊格式
                text_info = formatted_result["text"]
                face_url = formatted_result["face_url"]
                
                # 如果头像URL存在且有效，则下载图片
                if face_url and face_url != 'N/A' and face_url.startswith('http'):
                    try:
                        # 下载头像图片
                        timeout = aiohttp.ClientTimeout(total=10)
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            async with session.get(face_url) as resp:
                                if resp.status == 200:
                                    # 保存图片到临时文件
                                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                                        tmp_file.write(await resp.read())
                                        tmp_file_path = tmp_file.name
                                    
                                    # 返回包含文本和图片路径的特殊格式
                                    return {"type": "uapi_bilibili_user", "text": text_info, "image_path": tmp_file_path}
                                else:
                                    # 如果下载失败，仅返回文本信息
                                    logging.warning(f"下载B站用户头像失败: {face_url}, 状态码: {resp.status}")
                                    return text_info
                    except Exception as e:
                        logging.error(f"下载B站用户头像异常: {e}")
                        # 如果下载异常，仅返回文本信息
                        return text_info
                else:
                    # 如果没有有效头像URL，仅返回文本信息
                    return text_info
            else:
                return "B站用户查询失败"

        elif command_name == "B站投稿查询":
            if not args or not args[0].isdigit():
                return "请提供B站用户mid\n示例: /B站投稿查询 483307278"
            
            mid = args[0]
            result = await api.get_bilibili_archives(mid=mid)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "B站投稿查询失败"

        elif command_name == "GitHub仓库查询":
            if not args or len(args) < 2:
                return "请提供GitHub仓库的owner和repo\n示例: /GitHub仓库查询 torvalds linux"
            
            owner = args[0]
            repo = args[1]
            repo_full = f"{owner}/{repo}"
            result = await api.get_github_repo(repo=repo_full)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "GitHub仓库查询失败"

        elif command_name == "热榜查询":
            if not args or not args[0]:
                return "请提供热榜类型\n示例: /热榜查询 weibo"
            
            type_param = args[0]
            result = await api.get_hotboard(type_param=type_param)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "热榜查询失败"

        elif command_name == "世界时间查询":
            if not args or not args[0]:
                return "请提供时区名称\n示例: /世界时间查询 Asia/Shanghai"
            
            city = args[0]
            result = await api.get_worldtime(city=city)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "世界时间查询失败"

        elif command_name == "天气查询":
            if not args or not args[0]:
                return "请提供城市名称\n示例: /天气查询 北京"
            
            city = args[0]
            result = await api.get_weather(city=city)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "天气查询失败"

        elif command_name == "手机归属地查询":
            if not args or not args[0] or not args[0].isdigit() or len(args[0]) != 11:
                return "请提供11位手机号码\n示例: /手机归属地查询 13800138000"
            
            phone = args[0]
            result = await api.get_phoneinfo(phone=phone)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "手机归属地查询失败"

        elif command_name == "随机数生成":
            min_val = 1
            max_val = 100
            count = 1
            allow_repeat = False  # 默认不允许重复（与API客户端一致）
            allow_decimal = False  # 默认不生成小数
            decimal_places = 2  # 默认小数位数
            
            if args:
                try:
                    if len(args) >= 1:
                        min_val = int(args[0])
                    if len(args) >= 2:
                        max_val = int(args[1])
                    if len(args) >= 3:
                        count = int(args[2])
                    if len(args) >= 4:
                        allow_repeat = args[3].lower() in ['true', '1', 'yes', 'y', '是', '允许']
                    if len(args) >= 5:
                        allow_decimal = args[4].lower() in ['true', '1', 'yes', 'y', '是', '允许']
                    if len(args) >= 6:
                        decimal_places = int(args[5])
                except ValueError:
                    return "参数必须是数字\n示例: /随机数生成 1 100 5 true false 2"
            
            result = await api.get_randomnumber(min_val=min_val, max_val=max_val, count=count, 
                                              allow_repeat=allow_repeat, allow_decimal=allow_decimal, 
                                              decimal_places=decimal_places)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "随机数生成失败"

        elif command_name == "ICP备案查询":
            if not args or not args[0]:
                return "请提供域名\n示例: /ICP备案查询 baidu.com"
            
            domain = args[0]
            result = await api.get_icp(domain=domain)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "ICP备案查询失败"

        elif command_name == "B站投稿查询":
            if not args or not args[0].isdigit():
                return "请提供B站用户mid\n示例: /B站投稿查询 483307278\n示例: /B站投稿查询 483307278 地震 pubdate 10 1"
            
            mid = args[0]
            keywords = ""
            orderby = "pubdate"
            ps = "20"
            pn = "1"
            
            # 解析可选参数
            if len(args) > 1:
                keywords = args[1]
            if len(args) > 2:
                orderby = args[2].lower()
                if orderby not in ["pubdate", "views"]:
                    return "排序方式无效，请使用 'pubdate' (最新发布) 或 'views' (最多播放)"
            if len(args) > 3:
                try:
                    ps_int = int(args[3])
                    if ps_int < 1 or ps_int > 50:
                        return "每页条数必须在1-50之间"
                    ps = str(ps_int)
                except ValueError:
                    return "每页条数必须是数字"
            if len(args) > 4:
                try:
                    pn_int = int(args[4])
                    if pn_int < 1:
                        return "页码必须大于0"
                    pn = str(pn_int)
                except ValueError:
                    return "页码必须是数字"
            
            result = await api.get_bilibili_archives(mid=mid, keywords=keywords, orderby=orderby, ps=ps, pn=pn)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "B站投稿查询失败"

                return "ICP备案查询失败"

        elif command_name == "IP信息查询":
            if not args or not args[0]:
                return "请提供IP地址或域名\n示例: /IP信息查询 8.8.8.8"
            
            ip = args[0]
            result = await api.get_ipinfo(ip=ip)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "IP信息查询失败"

        elif command_name == "一言":
            result = await api.get_saying()
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "获取一言失败"

        elif command_name == "随机图片":
            category = args[0] if args else None
            result = await api.get_random_image(category=category)
            if result:
                # 返回图片二进制数据
                return result
            else:
                return "随机图片获取失败"

        elif command_name == "答案之书":
            if not args:
                return "请提供问题\n示例: /答案之书 我今天会有好运吗？"
            
            question = " ".join(args)
            result = await api.get_answerbook_ask(question=question)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "答案之书查询失败"



        elif command_name == "随机字符串":
            length = 16
            type_param = "alphanumeric"
            
            if args:
                try:
                    if len(args) >= 1:
                        length = int(args[0])
                    if len(args) >= 2:
                        type_param = args[1]
                except ValueError:
                    return "长度参数必须是数字\n示例: /随机字符串 32 alphanumeric"
            
            result = await api.get_random_string(length=length, type_param=type_param)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "随机字符串生成失败"

        elif command_name == "必应壁纸":
            result = await api.get_image_bing_daily()
            if result:
                return result  # 返回图片二进制数据
            else:
                return "必应壁纸获取失败"

        elif command_name == "生成二维码":
            if not args:
                return "请提供要生成二维码的文本\n示例: /生成二维码 https://www.bilibili.com"
            
            text = " ".join(args)
            result = await api.get_image_qrcode(text=text)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "二维码生成失败"

        elif command_name == "GrAvatar头像":
            if not args or not args[0]:
                return "请提供邮箱地址\n示例: /GrAvatar头像 user@example.com"

            email = args[0]
            result = await api.get_avatar_gravatar(email=email)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "GrAvatar头像获取失败"

        elif command_name == "摸摸头":
            if not args or not args[0].isdigit():
                return "请提供QQ号码或@某人\n示例: /摸摸头 10001 或 /摸摸头 @某人"

            qq = args[0]
            result = await api.get_image_motou(qq=qq)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "摸摸头GIF生成失败"

        elif command_name == "每日新闻图":
            result = await api.get_daily_news_image()
            if result:
                return result  # 返回图片二进制数据
            else:
                return "每日新闻图获取失败"

        elif command_name == "翻译":
            if not args or len(args) < 2:
                return "请提供目标语言和要翻译的文本\n示例: /翻译 zh-CHS hello\n示例: /翻译 zh-CHS 'hello world'"

            to_lang = args[0]
            text = " ".join(args[1:])  # 参数已经在command_handler.py中正确处理了引号
            
            result = await api.post_translate_text(to_lang=to_lang, text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "翻译失败"

        elif command_name == "程序员历史上的今天":
            result = await api.get_history_programmer_today()
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "程序员历史上的今天查询失败"

        elif command_name == "程序员历史事件":
            if not args or len(args) < 2:
                return "请提供月份和日期\n示例: /程序员历史事件 4 1"
            
            try:
                month = int(args[0])
                day = int(args[1])
                
                result = await api.get_history_programmer(month=month, day=day)
                if result:
                    return format_uapi_response(command_name, result, config)
                else:
                    return "程序员历史事件查询失败"
            except ValueError:
                return "月份和日期必须是数字\n示例: /程序员历史事件 4 1"

        elif command_name == "WHOIS查询":
            if not args or not args[0]:
                return "请提供域名\n示例: /WHOIS查询 google.com"
            
            domain = args[0]
            format_param = args[1] if len(args) > 1 else "json"
            
            result = await api.get_whois(domain=domain, format_param=format_param)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "WHOIS查询失败"

        elif command_name == "Ping主机":
            if not args or not args[0]:
                return "请提供主机地址\n示例: /Ping主机 google.com"
            
            host = args[0]
            result = await api.get_ping(host=host)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "Ping主机失败"

        elif command_name == "DNS查询":
            if not args or not args[0]:
                return "请提供域名\n示例: /DNS查询 google.com"
            
            domain = args[0]
            type_param = args[1] if len(args) > 1 else "A"
            
            result = await api.get_dns(domain=domain, type_param=type_param)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "DNS查询失败"

        elif command_name == "URL可访问性":
            if not args or not args[0]:
                return "请提供URL\n示例: /URL可访问性 https://www.baidu.com"
            
            url = args[0]
            result = await api.get_urlstatus(url=url)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "URL可访问性检查失败"

        elif command_name == "端口扫描":
            if not args or len(args) < 2:
                return "请提供主机和端口\n示例: /端口扫描 127.0.0.1 80"
            
            host = args[0]
            try:
                port = int(args[1])
                protocol = args[2] if len(args) > 2 else "tcp"
                
                result = await api.get_portscan(host=host, port=port, protocol=protocol)
                if result:
                    return format_uapi_response(command_name, result, config)
                else:
                    return "端口扫描失败"
            except ValueError:
                return "端口号必须是数字\n示例: /端口扫描 127.0.0.1 80"

        elif command_name == "MC服务器查询":
            if not args or not args[0]:
                return "请提供服务器地址\n示例: /MC服务器查询 mc.hypixel.net"
            
            server = args[0]
            result = await api.get_minecraft_serverstatus(server=server)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "MC服务器查询失败"

        elif command_name == "Steam用户查询":
            if not args or not args[0]:
                return "请提供Steam ID\n示例: /Steam用户查询 76561197960435530"
            
            steamid = args[0]
            key = args[1] if len(args) > 1 else None
            
            result = await api.get_steam_summary(steamid=steamid, key=key)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "Steam用户查询失败"

        elif command_name == "Epic免费游戏":
            result = await api.get_epic_free()
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "Epic免费游戏查询失败"

        elif command_name == "MC玩家查询":
            if not args or not args[0]:
                return "请提供MC用户名\n示例: /MC玩家查询 Notch"
            
            username = args[0]
            result = await api.get_minecraft_userinfo(username=username)
            if result:
                # 尝试下载并发送皮肤图片
                if 'skin_url' in result and result['skin_url'] != 'N/A':
                    img_path = await download_skin_image(result['skin_url'], username)
                    if img_path:
                        # 先发送文本消息
                        text = f"[MC玩家查询]\n用户名: {result.get('username', 'N/A')}\nUUID: {result.get('uuid', 'N/A')}"
                        await send_group_msg(group_id, text)
                        # 然后发送图片
                        await send_group_img(group_id, img_path)
                        return ""  # 返回空字符串，表示已处理完
                
                # 如果没有皮肤URL或下载失败，返回普通文本
                return format_uapi_response(command_name, result, config)
            else:
                return "MC玩家查询失败"

        elif command_name == "MD5哈希":
            if not args:
                return "请提供要计算MD5的文本\n示例: /MD5哈希 hello world"
            
            text = " ".join(args)
            result = await api.get_text_md5(text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "MD5哈希计算失败"



        elif command_name == "MD5校验":
            if not args or len(args) < 2:
                return "请提供文本和MD5哈希值\n示例: /MD5校验 hello world 5d41402abc4b2a76b9719d911017c592"
            
            text = args[0]
            hash_val = args[1]
            result = await api.post_text_md5_verify(text=text, hash_val=hash_val)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "MD5校验失败"

        elif command_name == "Base64编码":
            if not args:
                return "请提供要编码的文本\n示例: /Base64编码 hello world"
            
            text = " ".join(args)
            result = await api.post_text_base64_encode(text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "Base64编码失败"

        elif command_name == "Base64解码":
            if not args:
                return "请提供要解码的Base64文本\n示例: /Base64解码 aGVsbG8gd29ybGQ="
            
            text = " ".join(args)
            result = await api.post_text_base64_decode(text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "Base64解码失败"

        elif command_name == "AES加密":
            if not args or len(args) < 2:
                return "请提供密钥和要加密的文本\n示例: /AES加密 mysecretkey hello world"
            
            key = args[0]
            text = " ".join(args[1:])
            result = await api.post_text_aes_encrypt(key=key, text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "AES加密失败"

        elif command_name == "AES解密":
            if not args or len(args) < 3:
                return "请提供密钥、密文和nonce\n示例: /AES解密 mysecretkey encrypted_text nonce123"
            
            key = args[0]
            text = args[1]
            nonce = args[2]
            result = await api.post_text_aes_decrypt(key=key, text=text, nonce=nonce)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "AES解密失败"

        elif command_name == "AES高级加密":
            if not args or len(args) < 2:
                return "请提供密钥和要加密的文本\n示例: /AES高级加密 mysecretkey hello world"
            
            key = args[0]
            text = " ".join(args[1:])
            mode = args[2] if len(args) > 2 else "GCM"
            padding = args[3] if len(args) > 3 else "PKCS7"
            iv = args[4] if len(args) > 4 else None
            output_format = args[5] if len(args) > 5 else "base64"
            
            result = await api.post_text_aes_encrypt_advanced(text=text, key=key, mode=mode, 
                                                            padding=padding, iv=iv, 
                                                            output_format=output_format)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "AES高级加密失败"

        elif command_name == "AES高级解密":
            if not args or len(args) < 3:
                return "请提供密钥、密文和模式\n示例: /AES高级解密 mysecretkey encrypted_text GCM"
            
            key = args[0]
            text = args[1]
            mode = args[2] if len(args) > 2 else "GCM"
            padding = args[3] if len(args) > 3 else "NONE"
            iv = args[4] if len(args) > 4 else None
            
            result = await api.post_text_aes_decrypt_advanced(text=text, key=key, mode=mode, 
                                                            padding=padding, iv=iv)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "AES高级解密失败"

        elif command_name == "格式转换":
            if not args or len(args) < 3:
                return "请提供文本、源格式和目标格式\n示例: /格式转换 hello world plain base64"
            
            text = args[0]
            from_format = args[1]
            to_format = args[2]
            options = {}
            if len(args) > 3:
                # 解析选项参数
                for opt in args[3:]:
                    if '=' in opt:
                        key, value = opt.split('=', 1)
                        options[key] = value
            
            result = await api.post_text_convert(text=text, from_format=from_format, 
                                               to_format=to_format, options=options)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "格式转换失败"

        elif command_name == "网页元数据提取":
            if not args or not args[0]:
                return "请提供网页URL\n示例: /网页元数据提取 https://www.bilibili.com"
            
            url = args[0]
            result = await api.get_webparse_metadata(url=url)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "网页元数据提取失败"

        elif command_name == "时间戳转换":
            if not args or not args[0]:
                return "请提供时间戳或日期\n示例: /时间戳转换 1698380645 或 /时间戳转换 2023-10-27 15:04:05"
            
            time_param = args[0]
            result = await api.get_convert_unixtime(time_param=time_param)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "时间戳转换失败"

        elif command_name == "JSON格式化":
            if not args:
                return "请提供要格式化的JSON内容\n示例: /JSON格式化 {\"name\":\"test\",\"value\":123}"
            
            content = " ".join(args)
            result = await api.post_convert_json(content=content)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "JSON格式化失败"

        elif command_name == "生成你们怎么不说话了表情包":
            if not args or len(args) < 2:
                return "请提供顶部和底部文字\n示例: /生成你们怎么不说话了表情包 玩UAPI 们不要玩UAPI了"
            
            top_text = args[0]
            bottom_text = " ".join(args[1:])
            result = await api.post_image_speechless(top_text=top_text, bottom_text=bottom_text)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "表情包生成失败"



        elif command_name == "上传图片":
            if not args or not args[0]:
                return "请提供Base64编码的图片数据\n示例: /上传图片 iVBORw0KGgoAAAANSUE..."

            image_data = args[0]
            result = await api.post_image_frombase64(image_data=image_data)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "上传图片失败"

        elif command_name == "图片转Base64":
            if not args or not args[0]:
                return "请提供图片URL\n示例: /图片转Base64 https://example.com/image.jpg"

            url = args[0]
            result = await api.get_image_tobase64(url=url)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "图片转Base64失败"

        elif command_name == "每日新闻图":
            result = await api.get_daily_news_image()
            if result:
                return result  # 返回图片二进制数据
            else:
                return "每日新闻图获取失败"

        else:
            return f"未知的UAPI命令: {command_name}"

    except Exception as e:
        logging.error(f"处理UAPI命令异常: {e}")
        return f"UAPI命令处理出错: {str(e)}"