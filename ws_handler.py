import asyncio
import json
import logging
import re
import websockets
from message_sender import send_group_msg, send_group_img
from draw_eq import draw_earthquake_async

# 用于心跳计数的变量
HEARTBEAT_COUNT = 0

# 存储接收到的地震数据，用于测试命令
received_earthquake_data = {}

# 存储FAN提供的initial数据，用于测试命令
initial_earthquake_data = []


def get_nested_value(data, path):
    """从嵌套字典中获取值"""
    keys = path.split('.')
    value = data
    for key in keys:
        value = value.get(key, '')
        if value == '':
            return ''
    return value


def format_coordinates(event_data):
    """格式化经纬度为带方向的形式"""
    formatted = {}

    if 'longitude' in event_data and 'latitude' in event_data:
        # 处理经度
        lon_raw = event_data['longitude']
        lat_raw = event_data['latitude']

        # 规范化经度值
        lon = normalize_longitude(lon_raw)
        # 规范化纬度值
        lat = normalize_latitude(lat_raw)

        # 格式化经纬度为带方向的形式
        lon_direction = "E" if lon >= 0 else "W"
        lat_direction = "N" if lat >= 0 else "S"
        formatted_lon = f"{abs(lon):.2f}°{lon_direction}"
        formatted_lat = f"{abs(lat):.2f}°{lat_direction}"

        # 添加到格式化字典中
        formatted['longitude_formatted'] = formatted_lon
        formatted['latitude_formatted'] = formatted_lat
        # 添加数值形式的经纬度，供绘图使用
        formatted['longitude_normalized'] = lon
        formatted['latitude_normalized'] = lat

    return formatted


def normalize_longitude(lon):
    """规范化经度值，确保在-180到180之间"""
    try:
        original_lon = lon  # 保存原始值用于方向检测

        # 如果输入是字符串，尝试解析
        if isinstance(lon, str):
            # 检查是否包含方向字符
            has_direction = 'E' in lon.upper() or 'W' in lon.upper()
            is_west = 'W' in lon.upper()

            # 移除可能的方向字符并转换为浮点数
            lon_clean = lon.replace('°', '').replace('E', '').replace('W', '').strip()
            lon = float(lon_clean)

            # 如果原字符串包含方向且是西经，则转为负值
            if has_direction and is_west:
                lon = -abs(lon)
            elif has_direction and not is_west:  # 东经显式标记
                lon = abs(lon)
        else:
            lon = float(lon)

        # 将经度标准化到-180到180的范围内
        while lon > 180:
            lon -= 360
        while lon <= -180:
            lon += 360

        return lon
    except (ValueError, TypeError):
        logging.warning(f"无法解析经度值: {original_lon}")
        return 0.0  # 返回默认值


def normalize_latitude(lat):
    """规范化纬度值，确保在-90到90之间"""
    try:
        original_lat = lat  # 保存原始值用于方向检测

        # 如果输入是字符串，尝试解析
        if isinstance(lat, str):
            # 检查是否包含方向字符
            has_direction = 'N' in lat.upper() or 'S' in lat.upper()
            is_south = 'S' in lat.upper()

            # 移除可能的方向字符并转换为浮点数
            lat_clean = lat.replace('°', '').replace('N', '').replace('S', '').strip()
            lat = float(lat_clean)

            # 如果原字符串包含方向且是南纬，则转为负值
            if has_direction and is_south:
                lat = -abs(lat)
            elif has_direction and not is_south:  # 北纬显式标记
                lat = abs(lat)
        else:
            lat = float(lat)

        # 将纬度标准化到-90到90的范围内
        while lat > 90:
            lat = 180 - lat
        while lat < -90:
            lat = -180 - lat

        return lat
    except (ValueError, TypeError):
        logging.warning(f"无法解析纬度值: {original_lat}")
        return 0.0  # 返回默认值


def should_push_to_group(group_id, source, group_config):
    """检查是否应该推送消息到群组"""
    mode = group_config.get('mode', 'blacklist')
    sources_list = group_config.get('sources', [])

    if mode == 'blacklist' and source not in sources_list:
        logging.info(f"群 {group_id}: 黑名单模式，数据源 {source} 不在黑名单中，推送")
        return True
    elif mode == 'blacklist' and source in sources_list:
        logging.info(f"群 {group_id}: 黑名单模式，数据源 {source} 在黑名单中，跳过")
        return False
    elif mode == 'whitelist' and source in sources_list:
        logging.info(f"群 {group_id}: 白名单模式，数据源 {source} 在白名单中，推送")
        return True
    elif mode == 'whitelist' and source not in sources_list:
        logging.info(f"群 {group_id}: 白名单模式，数据源 {source} 不在白名单中，跳过")
        return False

    return False


async def process_earthquake_message(event_data, source, config, target_group=None):
    """处理地震消息的核心逻辑"""
    # 推送目标
    if target_group:
        groups_to_push = [target_group]
        logging.info(f"指定推送群: {target_group}")
    else:
        groups_to_push = config['groups'].keys()
        logging.info(f"向所有配置群推送: {list(groups_to_push)}")

    for group_id in groups_to_push:
        group_config = config['groups'].get(group_id, {})
        
        # 检查推送规则
        if not should_push_to_group(group_id, source, group_config):
            continue

        # 发送文本消息
        await send_earthquake_message(group_id, event_data, source, config)
        
        # 绘制并发送图片
        await send_earthquake_image(group_id, event_data, source, config)


async def send_earthquake_message(group_id, event_data, source, config):
    """发送地震消息到群组"""
    template = config['message_templates'].get(source, config['message_templates'].get('default', ''))
    if not template:
        return

    try:
        placeholders = re.findall(r'\{([^{}]+)\}', template)
        formatted = {ph: get_nested_value(event_data, ph) for ph in placeholders}

        # 添加格式化坐标
        formatted.update(format_coordinates(event_data))

        # 使用规范化后的经纬度替换原始经纬度值
        if 'longitude_normalized' in formatted:
            formatted['longitude'] = formatted['longitude_formatted']
        if 'latitude_normalized' in formatted:
            formatted['latitude'] = formatted['latitude_formatted']

        formatted['source_upper'] = source.upper()
        msg_text = template.format(**formatted)
        if msg_text.strip():
            logging.info(f"向群 {group_id} 发送消息: {msg_text}")
            await send_group_msg(group_id, msg_text)
    except Exception as e:
        logging.warning(f"模板填充失败 (群 {group_id}): {e}")


async def send_earthquake_image(group_id, event_data, source, config):
    """发送地震图像到群组"""
    if source not in config['draw_sources']:
        return

    filters = config['draw_filters'].get(source, {})
    if not all(re.search(regex, str(event_data.get(field, ''))) for field, regex in filters.items()):
        logging.info(f"数据源 {source} 未通过绘图过滤规则，跳过绘图")
        return

    # 检查是否有cwa提供的imageURI
    if source == "cwa" and "imageURI" in event_data:
        image_url = event_data["imageURI"]
        logging.info(f"使用cwa提供的图片URL: {image_url}")
        await download_and_send_cwa_image(group_id, image_url, event_data, config)
    else:
        # 非cwa数据源或没有imageURI字段，使用本地绘图
        # 使用规范化后的经纬度数据
        normalized_event_data = event_data.copy()
        formatted_coords = format_coordinates(event_data)
        if 'longitude_normalized' in formatted_coords:
            normalized_event_data['longitude'] = formatted_coords['longitude_normalized']
        if 'latitude_normalized' in formatted_coords:
            normalized_event_data['latitude'] = formatted_coords['latitude_normalized']

        logging.info(f"为群 {group_id} 生成地震地图")
        img_path = await asyncio.wait_for(
            draw_earthquake_async(normalized_event_data),
            timeout=config.get('draw_timeout', 10)
        )
        if img_path:
            await send_group_img(group_id, img_path)
            import os
            os.remove(img_path)
            logging.info(f"成功向群 {group_id} 发送地震地图")


async def download_and_send_cwa_image(group_id, image_url, event_data, config):
    """下载并发送CWA提供的图像"""
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status == 200:
                    # 下载图片到临时文件
                    import tempfile
                    import os
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                        tmp_file.write(await resp.read())
                        tmp_file_path = tmp_file.name

                    # 发送图片
                    await send_group_img(group_id, tmp_file_path)
                    os.remove(tmp_file_path)  # 发送后删除临时文件
                    logging.info(f"成功向群 {group_id} 发送cwa提供的地震图片")
                else:
                    logging.warning(f"下载cwa图片失败，状态码: {resp.status}，切换到本地绘图")
                    # 如果下载失败，使用本地绘图
                    await send_local_earthquake_image(group_id, event_data, config)
    except Exception as e:
        logging.error(f"下载或发送cwa图片失败: {e}，切换到本地绘图")
        # 如果下载或发送失败，使用本地绘图
        await send_local_earthquake_image(group_id, event_data, config)


async def send_local_earthquake_image(group_id, event_data, config):
    """发送本地绘制的地震图像"""
    # 使用规范化后的经纬度数据
    normalized_event_data = event_data.copy()
    formatted_coords = format_coordinates(event_data)
    if 'longitude_normalized' in formatted_coords:
        normalized_event_data['longitude'] = formatted_coords['longitude_normalized']
    if 'latitude_normalized' in formatted_coords:
        normalized_event_data['latitude'] = formatted_coords['latitude_normalized']

    img_path = await asyncio.wait_for(
        draw_earthquake_async(normalized_event_data),
        timeout=config.get('draw_timeout', 10)
    )
    if img_path:
        await send_group_img(group_id, img_path)
        import os
        os.remove(img_path)
        logging.info(f"成功向群 {group_id} 发送本地绘制的地震地图")


async def handle_heartbeat():
    """处理心跳消息"""
    global HEARTBEAT_COUNT
    HEARTBEAT_COUNT += 1
    if HEARTBEAT_COUNT % 5 == 0:
        return json.dumps({"type": "ping"})
    return None


async def handle_initial_data(data, config):
    """处理初始数据"""
    logging.info("收到 FAN 初始全量数据")
    # 存储initial数据，用于测试命令
    initial_data = data.get('Data', [])
    stored_count = 0
    for item in initial_data:
        source = item.get('source')
        event_data = item.get('Data', {})
        # 只存储有绘图功能的数据源
        if source in config['draw_sources']:
            initial_earthquake_data.append(item)
            stored_count += 1
    logging.info(f"解析 initial_all 数据: 总计 {len(initial_data)} 条，存储 {stored_count} 条用于绘图的数据源")
    return None


async def check_source_enabled(source, event_data, config):
    """检查数据源是否启用并满足过滤规则"""
    if not config['sources'].get(source, False):
        logging.info(f"数据源 {source} 未启用，跳过处理")
        return False

    rule = config['source_rules'].get(source)
    if rule and rule['enabled']:
        field_value = str(event_data.get(rule['match_field'], ''))
        if not re.search(rule['regex'], field_value):
            logging.info(f"数据源 {source} 未通过过滤规则，跳过推送")
            return False
        else:
            logging.info(f"数据源 {source} 通过过滤规则，准备推送")

    return True


async def process_message(message, config, target_group=None, apply_rules=True):
    """
    处理消息
    :param message: 接收到的消息
    :param config: 配置对象
    :param target_group: 目标群组（可选）
    :param apply_rules: 是否应用过滤规则
    """
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        logging.error("FAN WS 消息解析失败")
        return None

    msg_type = data.get('type')

    if msg_type == 'heartbeat':
        return await handle_heartbeat()

    if msg_type == 'initial_all':
        return await handle_initial_data(data, config)

    if msg_type != 'update':
        return None

    source = data.get('source')
    event_data = data.get('Data', {})

    logging.info(f"收到新消息: 数据源={source}, 时间={event_data.get('shockTime', '未知')}, "
                 f"震级={event_data.get('magnitude', '未知')}, 位置={event_data.get('placeName', '未知')}")

    # 检查数据源是否启用
    if apply_rules:
        if not await check_source_enabled(source, event_data, config):
            return None

    # 存储接收到的数据，用于测试命令（不管过滤规则如何）
    if source in config['draw_sources']:  # 只存储需要绘图的数据源
        received_earthquake_data[source] = event_data
        logging.info(f"存储数据源 {source} 用于测试命令")

    # 处理地震消息
    await process_earthquake_message(event_data, source, config, target_group)

    return None


async def connect_to_fan_ws(config):
    """连接到FAN的WebSocket服务"""
    uri = "wss://ws.fanstudio.tech/all"
    while True:
        try:
            async with websockets.connect(uri, ping_interval=None) as ws:
                logging.info("FAN WS 连接成功")
                while True:
                    msg = await ws.recv()
                    reply = await process_message(msg, config)
                    if reply:
                        await ws.send(reply)
        except websockets.exceptions.ConnectionClosedOK:
            logging.info("FAN WS 连接关闭，10秒后重连")
            await asyncio.sleep(10)
        except Exception as e:
            logging.error(f"FAN WS 断开: {e}，10秒后重连")
            await asyncio.sleep(10)


# NapCat WebSocket 处理器（支持 Array 格式）
async def napcat_ws_handler(websocket, path, config):
    """处理来自NapCat的WebSocket消息"""
    try:
        async for message in websocket:
            # message 是字符串，可能为 JSON 对象或 Array
            logging.debug(f"NapCat 收到消息: {message[:300]}...")

            try:
                event_data = json.loads(message)
            except json.JSONDecodeError:
                logging.warning("NapCat 消息非有效 JSON")
                continue

            # 处理 Array 或单个对象
            events = event_data if isinstance(event_data, list) else [event_data]

            for event in events:
                if not isinstance(event, dict):
                    continue

                post_type = event.get('post_type')
                if post_type in ('meta_event', 'heartbeat'):
                    continue  # 忽略心跳和 meta

                if post_type == 'message' and event.get('message_type') == 'group':
                    group_id = str(event.get('group_id', ''))
                    # 处理 message 内容（Array 或 string）
                    msg_content = event.get('message', '')
                    if isinstance(msg_content, list):
                        raw_message = ''.join(
                            seg.get('data', {}).get('text', '')
                            for seg in msg_content if seg.get('type') == 'text'
                        ).strip()
                    else:
                        raw_message = str(msg_content).strip()

                    test_cmd = config.get('test_command', '/eqbottest')
                    if raw_message == test_cmd:
                        logging.info(f"收到测试命令 来自群 {group_id}")

                        await send_group_msg(group_id, "开始 /eqbottest 测试...")

                        # 从存储的数据中选择两个不同的数据源进行测试
                        test_sources = list(received_earthquake_data.keys())

                        if len(test_sources) >= 2:
                            # 选择前两个可用的数据源进行测试
                            source1 = test_sources[0]
                            source2 = test_sources[1]

                            # 构建测试消息1
                            test1 = {
                                "type": "update",
                                "source": source1,
                                "Data": received_earthquake_data[source1]
                            }
                            await process_message(json.dumps(test1), config, target_group=group_id, apply_rules=False)

                            # 构建测试消息2
                            test2 = {
                                "type": "update",
                                "source": source2,
                                "Data": received_earthquake_data[source2]
                            }
                            await process_message(json.dumps(test2), config, target_group=group_id, apply_rules=False)
                        elif len(test_sources) == 1:
                            # 如果只有一个数据源，则使用该数据源两次
                            source1 = test_sources[0]

                            # 构建测试消息1
                            test1 = {
                                "type": "update",
                                "source": source1,
                                "Data": received_earthquake_data[source1]
                            }
                            await process_message(json.dumps(test1), config, target_group=group_id, apply_rules=False)

                            # 构建测试消息2（使用相同的数据源，但添加测试标识）
                            test2_data = received_earthquake_data[source1].copy()
                            test2_data['placeName'] = test2_data.get('placeName', '未知地点') + " (测试)"

                            test2 = {
                                "type": "update",
                                "source": source1,
                                "Data": test2_data
                            }
                            await process_message(json.dumps(test2), config, target_group=group_id, apply_rules=False)
                        else:
                            # 如果没有存储的数据，则使用硬编码的测试数据
                            # 测试1 cenc - 中国内部地震
                            test1 = {
                                "type": "update",
                                "source": "cenc",
                                "Data": {
                                    "id": "test_cenc_001",
                                    "shockTime": "2026-02-02 03:00:00",
                                    "latitude": 31.0,
                                    "longitude": 103.4,
                                    "depth": 10,
                                    "magnitude": 5.5,
                                    "placeName": "四川汶川县",
                                    "infoTypeName": "正式测定"
                                }
                            }
                            await process_message(json.dumps(test1), config, target_group=group_id, apply_rules=False)

                            # 测试2 usgs - 外国M5.0以上地震
                            test2 = {
                                "type": "update",
                                "source": "usgs",
                                "Data": {
                                    "id": "test_usgs_001",
                                    "shockTime": "2026-02-02 04:59:59",
                                    "placeName": "Near coast of Ecuador",
                                    "magnitude": 6.2,
                                    "latitude": -0.719,
                                    "longitude": -80.236,
                                    "depth": 10,
                                    "title": "M 6.2 - Near coast of Ecuador"
                                }
                            }
                            await process_message(json.dumps(test2), config, target_group=group_id, apply_rules=False)

                        await send_group_msg(group_id, "测试完成！请检查消息和图片。")

    except websockets.exceptions.ConnectionClosedOK:
        logging.info("NapCat WS 正常关闭")
    except Exception as e:
        logging.error(f"NapCat WS 处理异常: {e}")