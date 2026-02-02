import asyncio
import json
import logging
import re
import websockets
import os
from message_sender import send_group_msg, send_group_img
from draw_eq import draw_earthquake_async

HEARTBEAT_COUNT = 0

# 存储接收到的地震数据，用于测试命令
received_earthquake_data = {}

# 存储FAN提供的initial数据，用于测试命令
initial_earthquake_data = []

async def process_message(message, config, target_group=None):
    global HEARTBEAT_COUNT
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        logging.error("FAN WS 消息解析失败")
        return None

    msg_type = data.get('type')

    if msg_type == 'heartbeat':
        HEARTBEAT_COUNT += 1
        if HEARTBEAT_COUNT % 5 == 0:
            return json.dumps({"type": "ping"})
        return None

    if msg_type == 'initial_all':
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

    if msg_type != 'update':
        return None

    source = data.get('source')
    event_data = data.get('Data', {})

    logging.info(f"收到新消息: 数据源={source}, 时间={event_data.get('shockTime', '未知')}, "
                 f"震级={event_data.get('magnitude', '未知')}, 位置={event_data.get('placeName', '未知')}")

    if not config['sources'].get(source, False):
        logging.info(f"数据源 {source} 未启用，跳过处理")
        return None

    # 存储接收到的数据，用于测试命令（不管过滤规则如何）
    if source in config['draw_sources']:  # 只存储需要绘图的数据源
        received_earthquake_data[source] = event_data
        logging.info(f"存储数据源 {source} 用于测试命令")

    rule = config['source_rules'].get(source)
    if rule and rule['enabled']:
        field_value = str(event_data.get(rule['match_field'], ''))
        if not re.search(rule['regex'], field_value):
            logging.info(f"数据源 {source} 未通过过滤规则，跳过推送")
            return None
        else:
            logging.info(f"数据源 {source} 通过过滤规则，准备推送")

    # 推送目标
    if target_group:
        groups_to_push = [target_group]
        logging.info(f"指定推送群: {target_group}")
    else:
        groups_to_push = config['groups'].keys()
        logging.info(f"向所有配置群推送: {list(groups_to_push)}")

    for group_id in groups_to_push:
        group_config = config['groups'].get(group_id, {})
        mode = group_config.get('mode', 'blacklist')
        sources_list = group_config.get('sources', [])

        # 检查推送规则
        should_push = False
        if mode == 'blacklist' and source not in sources_list:
            should_push = True
            logging.info(f"群 {group_id}: 黑名单模式，数据源 {source} 不在黑名单中，推送")
        elif mode == 'blacklist' and source in sources_list:
            logging.info(f"群 {group_id}: 黑名单模式，数据源 {source} 在黑名单中，跳过")
            continue
        elif mode == 'whitelist' and source in sources_list:
            should_push = True
            logging.info(f"群 {group_id}: 白名单模式，数据源 {source} 在白名单中，推送")
        elif mode == 'whitelist' and source not in sources_list:
            logging.info(f"群 {group_id}: 白名单模式，数据源 {source} 不在白名单中，跳过")
            continue

        if should_push:
            template = config['message_templates'].get(source, config['message_templates'].get('default', ''))
            if template:
                try:
                    def get_nested(d, path):
                        keys = path.split('.')
                        v = d
                        for k in keys:
                            v = v.get(k, '')
                            if v == '':
                                return ''
                        return v

                    placeholders = re.findall(r'\{([^{}]+)\}', template)
                    formatted = {ph: get_nested(event_data, ph) for ph in placeholders}

                    # 添加经纬度方向判断
                    if 'longitude' in event_data and 'latitude' in event_data:
                        lon = float(event_data['longitude'])
                        lat = float(event_data['latitude'])
                        # 格式化经纬度为带方向的形式
                        lon_direction = "E" if lon >= 0 else "W"
                        lat_direction = "N" if lat >= 0 else "S"
                        formatted_lon = f"{abs(lon):.2f}°{lon_direction}"
                        formatted_lat = f"{abs(lat):.2f}°{lat_direction}"
                        # 添加到格式化字典中
                        formatted['longitude_formatted'] = formatted_lon
                        formatted['latitude_formatted'] = formatted_lat

                    formatted['source_upper'] = source.upper()
                    msg_text = template.format(**formatted)
                    if msg_text.strip():
                        logging.info(f"向群 {group_id} 发送消息: {msg_text}")
                        await send_group_msg(group_id, msg_text)
                except Exception as e:
                    logging.warning(f"模板填充失败 (群 {group_id}): {e}")

            # 绘图
            if source in config['draw_sources']:
                filters = config['draw_filters'].get(source, {})
                if all(re.search(regex, str(event_data.get(field, ''))) for field, regex in filters.items()):
                    # 检查是否有cwa提供的imageURI
                    if source == "cwa" and "imageURI" in event_data:
                        image_url = event_data["imageURI"]
                        logging.info(f"使用cwa提供的图片URL: {image_url}")
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
                                        img_path = await asyncio.wait_for(
                                            draw_earthquake_async(event_data),
                                            timeout=config.get('draw_timeout', 10)
                                        )
                                        if img_path:
                                            await send_group_img(group_id, img_path)
                                            os.remove(img_path)
                                            logging.info(f"成功向群 {group_id} 发送本地绘制的地震地图")
                        except Exception as e:
                            logging.error(f"下载或发送cwa图片失败: {e}，切换到本地绘图")
                            # 如果下载或发送失败，使用本地绘图
                            img_path = await asyncio.wait_for(
                                draw_earthquake_async(event_data),
                                timeout=config.get('draw_timeout', 10)
                            )
                            if img_path:
                                await send_group_img(group_id, img_path)
                                import os
                                os.remove(img_path)
                                logging.info(f"成功向群 {group_id} 发送本地绘制的地震地图")
                    else:
                        # 非cwa数据源或没有imageURI字段，使用本地绘图
                        logging.info(f"为群 {group_id} 生成地震地图")
                        img_path = await asyncio.wait_for(
                            draw_earthquake_async(event_data),
                            timeout=config.get('draw_timeout', 10)
                        )
                        if img_path:
                            await send_group_img(group_id, img_path)
                            os.remove(img_path)
                            logging.info(f"成功向群 {group_id} 发送地震地图")
                else:
                    logging.info(f"数据源 {source} 未通过绘图过滤规则，跳过绘图")

async def connect_to_fan_ws(config):
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
        except Exception as e:
            logging.error(f"FAN WS 断开: {e}，10秒后重连")
            await asyncio.sleep(10)

# 绕过规则检查直接处理消息
async def process_message_without_rules(message, config, target_group=None):
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        logging.error("消息解析失败")
        return

    msg_type = data.get('type')
    if msg_type != 'update':
        return

    source = data.get('source')
    event_data = data.get('Data', {})

    logging.info(f"[测试命令] 收到新消息: 数据源={source}, 时间={event_data.get('shockTime', '未知')}, "
                 f"震级={event_data.get('magnitude', '未知')}, 位置={event_data.get('placeName', '未知')}")

    # 推送目标
    if target_group:
        groups_to_push = [target_group]
        logging.info(f"[测试命令] 指定推送群: {target_group}")
    else:
        groups_to_push = config['groups'].keys()
        logging.info(f"[测试命令] 向所有配置群推送: {list(groups_to_push)}")

    for group_id in groups_to_push:
        group_config = config['groups'].get(group_id, {})
        mode = group_config.get('mode', 'blacklist')
        sources_list = group_config.get('sources', [])

        # 检查推送规则
        should_push = False
        if mode == 'blacklist' and source not in sources_list:
            should_push = True
            logging.info(f"[测试命令] 群 {group_id}: 黑名单模式，数据源 {source} 不在黑名单中，推送")
        elif mode == 'blacklist' and source in sources_list:
            logging.info(f"[测试命令] 群 {group_id}: 黑名单模式，数据源 {source} 在黑名单中，跳过")
            continue
        elif mode == 'whitelist' and source in sources_list:
            should_push = True
            logging.info(f"[测试命令] 群 {group_id}: 白名单模式，数据源 {source} 在白名单中，推送")
        elif mode == 'whitelist' and source not in sources_list:
            logging.info(f"[测试命令] 群 {group_id}: 白名单模式，数据源 {source} 不在白名单中，跳过")
            continue

        if should_push:
            template = config['message_templates'].get(source, config['message_templates'].get('default', ''))
            if template:
                try:
                    def get_nested(d, path):
                        keys = path.split('.')
                        v = d
                        for k in keys:
                            v = v.get(k, '')
                            if v == '':
                                return ''
                        return v

                    placeholders = re.findall(r'\{([^{}]+)\}', template)
                    formatted = {ph: get_nested(event_data, ph) for ph in placeholders}

                    # 添加经纬度方向判断
                    if 'longitude' in event_data and 'latitude' in event_data:
                        lon = float(event_data['longitude'])
                        lat = float(event_data['latitude'])
                        # 格式化经纬度为带方向的形式
                        lon_direction = "E" if lon >= 0 else "W"
                        lat_direction = "N" if lat >= 0 else "S"
                        formatted_lon = f"{abs(lon):.2f}°{lon_direction}"
                        formatted_lat = f"{abs(lat):.2f}°{lat_direction}"
                        # 添加到格式化字典中
                        formatted['longitude_formatted'] = formatted_lon
                        formatted['latitude_formatted'] = formatted_lat

                    formatted['source_upper'] = source.upper()
                    msg_text = template.format(**formatted)
                    if msg_text.strip():
                        logging.info(f"[测试命令] 向群 {group_id} 发送消息: {msg_text}")
                        await send_group_msg(group_id, msg_text)
                except Exception as e:
                    logging.warning(f"[测试命令] 模板填充失败 (群 {group_id}): {e}")

            # 绘图
            if source in config['draw_sources']:
                filters = config['draw_filters'].get(source, {})
                if all(re.search(regex, str(event_data.get(field, ''))) for field, regex in filters.items()):
                    # 检查是否有cwa提供的imageURI
                    if source == "cwa" and "imageURI" in event_data:
                        image_url = event_data["imageURI"]
                        logging.info(f"[测试命令] 使用cwa提供的图片URL: {image_url}")
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
                                        logging.info(f"[测试命令] 成功向群 {group_id} 发送cwa提供的地震图片")
                                    else:
                                        logging.warning(f"[测试命令] 下载cwa图片失败，状态码: {resp.status}，切换到本地绘图")
                                        # 如果下载失败，使用本地绘图
                                        img_path = await asyncio.wait_for(
                                            draw_earthquake_async(event_data),
                                            timeout=config.get('draw_timeout', 10)
                                        )
                                        if img_path:
                                            await send_group_img(group_id, img_path)
                                            os.remove(img_path)
                                            logging.info(f"[测试命令] 成功向群 {group_id} 发送本地绘制的地震地图")
                        except Exception as e:
                            logging.error(f"[测试命令] 下载或发送cwa图片失败: {e}，切换到本地绘图")
                            # 如果下载或发送失败，使用本地绘图
                            img_path = await asyncio.wait_for(
                                draw_earthquake_async(event_data),
                                timeout=config.get('draw_timeout', 10)
                            )
                            if img_path:
                                await send_group_img(group_id, img_path)
                                import os
                                os.remove(img_path)
                                logging.info(f"[测试命令] 成功向群 {group_id} 发送本地绘制的地震地图")
                    else:
                        # 非cwa数据源或没有imageURI字段，使用本地绘图
                        logging.info(f"[测试命令] 为群 {group_id} 生成地震地图")
                        img_path = await asyncio.wait_for(
                            draw_earthquake_async(event_data),
                            timeout=config.get('draw_timeout', 10)
                        )
                        if img_path:
                            await send_group_img(group_id, img_path)
                            os.remove(img_path)
                            logging.info(f"[测试命令] 成功向群 {group_id} 发送地震地图")
                else:
                    logging.info(f"[测试命令] 数据源 {source} 未通过绘图过滤规则，跳过绘图")

# NapCat WebSocket 处理器（支持 Array 格式）
async def napcat_ws_handler(websocket, path, config):
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
                            await process_message(json.dumps(test1), config, target_group=group_id)

                            # 构建测试消息2
                            test2 = {
                                "type": "update",
                                "source": source2,
                                "Data": received_earthquake_data[source2]
                            }
                            await process_message(json.dumps(test2), config, target_group=group_id)
                        elif len(test_sources) == 1:
                            # 如果只有一个数据源，则使用该数据源两次
                            source1 = test_sources[0]

                            # 构建测试消息1
                            test1 = {
                                "type": "update",
                                "source": source1,
                                "Data": received_earthquake_data[source1]
                            }
                            await process_message(json.dumps(test1), config, target_group=group_id)

                            # 构建测试消息2（使用相同的数据源，但添加测试标识）
                            test2_data = received_earthquake_data[source1].copy()
                            test2_data['placeName'] = test2_data.get('placeName', '未知地点') + " (测试)"

                            test2 = {
                                "type": "update",
                                "source": source1,
                                "Data": test2_data
                            }
                            await process_message(json.dumps(test2), config, target_group=group_id)
                        else:
                            # 如果没有存储的数据，则使用原始的测试数据
                            # 测试1 emsc
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
                            await process_message(json.dumps(test1), config, target_group=group_id)

                            # 测试2 usgs
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

                        await send_group_msg(group_id, "测试完成！请检查消息和图片。")

    except websockets.exceptions.ConnectionClosedOK:
        logging.info("NapCat WS 正常关闭")
    except Exception as e:
        logging.error(f"NapCat WS 处理异常: {e}")