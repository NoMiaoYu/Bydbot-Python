import asyncio
import json
import logging
import re
import websockets
import aiosqlite
import os
from datetime import datetime, timedelta
from message_sender import send_group_msg, send_group_img
from draw_eq import draw_earthquake_async

# 用于心跳计数的变量
HEARTBEAT_COUNT = 0

# 存储接收到的地震数据，用于测试命令
received_earthquake_data = {}

# 存储FAN提供的initial数据，用于测试命令
initial_earthquake_data = []

# 用于存储已处理的地震消息ID集合
processed_ids = set()

# 用于存储待处理的绘图任务（源ID -> 任务信息）
pending_draw_tasks = {}

# 用于缓存已绘制的图片路径（消息ID -> 图片路径）
cached_image_paths = {}


async def init_db():
    """异步初始化数据库"""
    # 确保data目录存在
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)

    db_path = os.path.join(data_dir, 'eqdata.db')

    async with aiosqlite.connect(db_path) as db:
        # 创建地震数据表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS earthquakes (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                shock_time TEXT,
                latitude REAL,
                longitude REAL,
                magnitude REAL,
                depth REAL,
                place_name TEXT,
                info_type_name TEXT,
                data_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建API使用统计表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS weather_api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,          -- YYYY-MM-DD
                month TEXT NOT NULL,         -- YYYY-MM
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                command TEXT NOT NULL,
                api_endpoint TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建索引以提高查询性能
        await db.execute('CREATE INDEX IF NOT EXISTS idx_shock_time ON earthquakes(shock_time)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON earthquakes(created_at)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_api_usage(date)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_weather_month ON weather_api_usage(month)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_weather_group ON weather_api_usage(group_id)')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_weather_user ON weather_api_usage(user_id)')

        await db.commit()

    logging.info(f"数据库初始化完成: {db_path}")
    return db_path


async def load_recent_ids_from_db():
    """异步从数据库加载最近2周的地震消息ID到内存"""
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')

    # 计算2周前的时间
    two_weeks_ago = datetime.now() - timedelta(weeks=2)

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("""
            SELECT DISTINCT id FROM earthquakes
            WHERE created_at >= ?
        """, (two_weeks_ago.strftime('%Y-%m-%d %H:%M:%S'),)) as cursor:
            rows = await cursor.fetchall()
            ids = {row[0] for row in rows}

    logging.info(f"从数据库加载了 {len(ids)} 个最近2周的地震消息ID")
    return ids


async def is_duplicate_message(event_data, source):
    """异步检查消息是否重复"""
    # 尝试获取地震消息的唯一ID
    eq_id = event_data.get('id')

    if not eq_id:
        # 如果没有ID，尝试使用其他字段组合生成唯一标识
        eq_id = f"{event_data.get('shockTime', '')}_{event_data.get('latitude', '')}_{event_data.get('longitude', '')}_{event_data.get('magnitude', '')}"

    # 创建源+ID的组合键
    composite_id = f"{source}_{eq_id}"
    
    logging.debug(f"检查消息是否重复，复合ID: {composite_id}")

    # 检查ID是否已经在内存中
    if composite_id in processed_ids:
        logging.info(f"发现重复消息（内存中），复合ID: {composite_id}")
        return True

    # 检查数据库中是否已有此ID
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT COUNT(*) FROM earthquakes WHERE source = ? AND id = ?", (source, eq_id)) as cursor:
            count = await cursor.fetchone()
            count = count[0] if count else 0

    if count > 0:
        logging.info(f"发现重复消息（数据库中），复合ID: {composite_id}")
        # 将ID加入内存集合，避免后续重复检查
        processed_ids.add(composite_id)
        return True

    # 如果不是重复消息，将ID加入内存集合
    logging.debug(f"新消息，复合ID: {composite_id}，已加入内存集合")
    processed_ids.add(composite_id)
    return False


async def is_recent_duplicate_by_time(event_data, source, time_window_minutes=5):
    """基于时间窗口检查是否为近期重复消息（防止相同事件的不同报告）"""
    # 排除非地震源
    non_earthquake_sources = {'weatheralarm', 'tsunami'}
    if source in non_earthquake_sources:
        return False
        
    shock_time_str = event_data.get('shockTime')
    if not shock_time_str:
        return False
    
    try:
        # 解析震发时间
        shock_time = datetime.strptime(shock_time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # 尝试其他时间格式
            shock_time = datetime.fromisoformat(shock_time_str.replace('Z', '+00:00'))
        except ValueError:
            logging.warning(f"无法解析震发时间: {shock_time_str}")
            return False
    
    # 获取经纬度和震级
    latitude = event_data.get('latitude')
    longitude = event_data.get('longitude') 
    magnitude = event_data.get('magnitude')
    
    if latitude is None or longitude is None or magnitude is None:
        return False
    
    # 计算时间窗口
    current_time = datetime.now()
    time_threshold = current_time - timedelta(minutes=time_window_minutes)
    
    # 如果震发时间太旧（超过24小时），不进行时间窗口去重
    if shock_time < current_time - timedelta(hours=24):
        return False
    
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
    async with aiosqlite.connect(db_path) as db:
        # 查询在时间窗口内、位置相近、震级相近的地震事件
        query = """
            SELECT id, shock_time, latitude, longitude, magnitude 
            FROM earthquakes 
            WHERE source = ?
            AND created_at >= ? 
            AND ABS(latitude - ?) <= 0.5 
            AND ABS(longitude - ?) <= 0.5 
            AND ABS(magnitude - ?) <= 0.3
        """
        
        async with db.execute(query, (
            source,
            time_threshold.strftime('%Y-%m-%d %H:%M:%S'),
            float(latitude),
            float(longitude), 
            float(magnitude)
        )) as cursor:
            rows = await cursor.fetchall()
            
        if rows:
            # 找到相似的近期事件
            for row in rows:
                existing_shock_time_str = row[1]
                try:
                    existing_shock_time = datetime.strptime(existing_shock_time_str, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue
                
                # 如果震发时间相差很小（比如小于1分钟），认为是同一个事件
                time_diff = abs((shock_time - existing_shock_time).total_seconds())
                if time_diff < 60:  # 60秒内
                    logging.info(f"发现时间窗口内的重复地震事件: 原ID={row[0]}, 新事件时间={shock_time_str}, 位置=({latitude}, {longitude}), 震级={magnitude}")
                    return True
    
    return False


async def save_earthquake_to_db(event_data, source):
    """异步将地震数据保存到数据库"""
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')

    eq_id = event_data.get('id')
    if not eq_id:
        # 如果没有ID，生成一个唯一标识
        eq_id = f"{event_data.get('shockTime', '')}_{event_data.get('latitude', '')}_{event_data.get('longitude', '')}_{event_data.get('magnitude', '')}"

    async with aiosqlite.connect(db_path) as db:
        # 检查是否已存在
        async with db.execute("SELECT COUNT(*) FROM earthquakes WHERE id = ?", (eq_id,)) as cursor:
            count = await cursor.fetchone()
            count = count[0] if count else 0

        if count > 0:
            logging.debug(f"数据库中已存在地震数据，ID: {eq_id}，跳过插入")
            return

        await db.execute("""
            INSERT INTO earthquakes
            (id, source, shock_time, latitude, longitude, magnitude, depth, place_name, info_type_name, data_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            eq_id,
            source,
            event_data.get('shockTime'),
            event_data.get('latitude'),
            event_data.get('longitude'),
            event_data.get('magnitude'),
            event_data.get('depth'),
            event_data.get('placeName'),
            event_data.get('infoTypeName'),
            json.dumps(event_data)
        ))
        await db.commit()

    logging.info(f"地震数据已保存到数据库，ID: {eq_id}, 数据源: {source}, 时间: {event_data.get('shockTime', '未知')}, 震级: {event_data.get('magnitude', '未知')}")


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


def apply_field_rules(event_data, source, config):
    """
    应用字段规则到事件数据
    :param event_data: 原始事件数据
    :param source: 数据源名称
    :param config: 配置字典
    :return: 处理后的事件数据副本
    """
    field_rules = config.get('field_rules', {})
    source_rules = field_rules.get(source, {})
    
    if not source_rules:
        return event_data.copy()
    
    # 创建事件数据的副本以避免修改原始数据
    processed_data = event_data.copy()
    
    for field_name, rules in source_rules.items():
        if field_name not in processed_data:
            continue
            
        field_value = processed_data[field_name]
        
        # 应用所有规则（按顺序）
        for rule in rules:
            try:
                condition = rule.get('condition', '')
                true_value = rule.get('true_value', '{value}')
                false_value = rule.get('false_value', '{value}')
                
                # 准备条件评估的上下文
                context = {
                    'value': field_value,
                    'str': str,
                    'int': int,
                    'float': float,
                    'len': len,
                    'in': lambda x, y: x in y,
                    'not_in': lambda x, y: x not in y
                }
                
                # 安全地评估条件
                if evaluate_condition(condition, field_value, context):
                    # 使用true_value替换
                    processed_data[field_name] = true_value.format(value=field_value)
                    break  # 条件满足后跳出，不再应用后续规则
                else:
                    # 使用false_value替换，但继续检查后续规则
                    processed_data[field_name] = false_value.format(value=field_value)
                    
            except Exception as e:
                logging.warning(f"应用字段规则时出错 (source={source}, field={field_name}): {e}")
                continue
    
    return processed_data


def evaluate_condition(condition, value, context):
    """
    安全地评估条件表达式
    :param condition: 条件字符串
    :param value: 字段值
    :param context: 评估上下文
    :return: 布尔值
    """
    if not condition:
        return False
        
    try:
        # 替换value为实际值的字符串表示
        safe_condition = condition.replace('value', 'context["value"]')
        
        # 限制可用的内置函数和操作符
        allowed_names = {
            "__builtins__": {},
            "context": context,
            "str": str,
            "int": int,
            "float": float,
            "len": len,
            "abs": abs,
            "min": min,
            "max": max,
            "round": round,
            "True": True,
            "False": False,
            "None": None
        }
        
        result = eval(safe_condition, allowed_names)
        return bool(result)
    except Exception as e:
        logging.warning(f"条件评估失败: {condition}, 错误: {e}")
        return False


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
        # 应用字段规则
        processed_event_data = apply_field_rules(event_data, source, config)
        
        placeholders = re.findall(r'\{([^{}]+)\}', template)
        formatted = {ph: get_nested_value(processed_event_data, ph) for ph in placeholders}

        # 添加格式化坐标
        formatted.update(format_coordinates(processed_event_data))

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
        
        # 获取消息ID用于缓存
        msg_id = event_data.get('id', f"{event_data.get('shockTime', '')}_{event_data.get('latitude', '')}_{event_data.get('longitude', '')}_{event_data.get('magnitude', '')}")
        
        # 检查是否已有缓存的图片
        if msg_id in cached_image_paths:
            img_path = cached_image_paths[msg_id]
            if os.path.exists(img_path):
                logging.info(f"复用已缓存的图片: {img_path}")
                await send_group_img(group_id, img_path)
                return
            else:
                # 缓存的文件不存在，移除缓存
                del cached_image_paths[msg_id]
                logging.info(f"缓存的图片不存在，重新绘制: {msg_id}")
        
        # 应用字段规则（但保留原始数值用于绘图）
        processed_event_data = apply_field_rules(event_data, source, config)
        
        # 使用规范化后的经纬度数据
        normalized_event_data = processed_event_data.copy()
        formatted_coords = format_coordinates(processed_event_data)
        if 'longitude_normalized' in formatted_coords:
            normalized_event_data['longitude'] = formatted_coords['longitude_normalized']
        if 'latitude_normalized' in formatted_coords:
            normalized_event_data['latitude'] = formatted_coords['latitude_normalized']
        
        # 添加数据源信息用于断层绘制判断
        normalized_event_data['_source'] = source

        logging.info(f"为群 {group_id} 生成地震地图")
        img_path = await asyncio.wait_for(
            draw_earthquake_async(normalized_event_data, source),
            timeout=config.get('draw_timeout', 20)
        )
        if img_path:
            # 缓存图片路径
            cached_image_paths[msg_id] = img_path
            await send_group_img(group_id, img_path)
            logging.info(f"成功向群 {group_id} 发送地震地图: {img_path}")


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
    # 获取数据源（从event_data中提取，如果有的话）
    source = event_data.get('_source', 'unknown')
    
    # 获取消息ID用于缓存
    msg_id = event_data.get('id', f"{event_data.get('shockTime', '')}_{event_data.get('latitude', '')}_{event_data.get('longitude', '')}_{event_data.get('magnitude', '')}")
    
    # 检查是否已有缓存的图片
    if msg_id in cached_image_paths:
        img_path = cached_image_paths[msg_id]
        if os.path.exists(img_path):
            logging.info(f"复用已缓存的图片: {img_path}")
            await send_group_img(group_id, img_path)
            return
        else:
            # 缓存的文件不存在，移除缓存
            del cached_image_paths[msg_id]
            logging.info(f"缓存的图片不存在，重新绘制: {msg_id}")
    
    # 使用规范化后的经纬度数据
    normalized_event_data = event_data.copy()
    formatted_coords = format_coordinates(event_data)
    if 'longitude_normalized' in formatted_coords:
        normalized_event_data['longitude'] = formatted_coords['longitude_normalized']
    if 'latitude_normalized' in formatted_coords:
        normalized_event_data['latitude'] = formatted_coords['latitude_normalized']
    
    normalized_event_data['_source'] = source

    img_path = await asyncio.wait_for(
        draw_earthquake_async(normalized_event_data, source),
        timeout=config.get('draw_timeout', 20)
    )
    if img_path:
        # 缓存图片路径
        cached_image_paths[msg_id] = img_path
        await send_group_img(group_id, img_path)
        logging.info(f"成功向群 {group_id} 发送本地绘制的地震地图: {img_path}")


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
        
        # 将初始数据的ID加入去重集合
        eq_id = event_data.get('id')
        if not eq_id:
            eq_id = f"{event_data.get('shockTime', '')}_{event_data.get('latitude', '')}_{event_data.get('longitude', '')}_{event_data.get('magnitude', '')}"
        if eq_id:
            processed_ids.add(eq_id)
            logging.debug(f"将初始数据ID加入去重集合: {eq_id}")
        
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


async def get_stored_earthquake_data(eq_id, source):
    """从数据库获取已存储的地震数据"""
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT data_json FROM earthquakes WHERE source = ? AND id = ?", (source, eq_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return json.loads(row[0])
    return None


def has_significant_update(old_data, new_data):
    """检查新数据是否有任何更新（只要有字段不同就视为更新）"""
    if not old_data:
        return True
    
    # 比较所有字段，只要有任何不同就视为更新
    for key in set(list(old_data.keys()) + list(new_data.keys())):
        old_value = old_data.get(key)
        new_value = new_data.get(key)
        
        # 如果一个存在另一个不存在，视为更新
        if (old_value is None) != (new_value is None):
            return True
            
        # 如果都存在但值不同，视为更新
        if old_value is not None and new_value is not None:
            if str(old_value) != str(new_value):
                return True
    
    return False


async def cancel_pending_draw_task(source_id):
    """取消待处理的绘图任务"""
    if source_id in pending_draw_tasks:
        task_info = pending_draw_tasks[source_id]
        if not task_info['task'].done():
            task_info['task'].cancel()
            try:
                await task_info['task']
            except asyncio.CancelledError:
                pass
        del pending_draw_tasks[source_id]
        logging.debug(f"已取消待处理的绘图任务: {source_id}")


async def delayed_draw_and_send(event_data, source, config, target_group=None):
    """延迟绘图并发送"""
    try:
        # 等待15秒，如果期间没有收到更新，则进行绘图
        await asyncio.sleep(15)
        
        # 检查是否仍然需要绘图（可能在等待期间被取消）
        source_id = f"{source}_{event_data.get('id', event_data.get('shockTime', ''))}"
        if source_id not in pending_draw_tasks:
            return
            
        logging.info(f"15秒内未收到更新，开始绘图: {source_id}")
        
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

            try:
                # 绘制并发送图片（使用复用逻辑）
                await send_earthquake_image(group_id, event_data, source, config)
            except Exception as e:
                logging.error(f"向群 {group_id} 发送地震图片失败: {e}")
                continue
            
    except asyncio.CancelledError:
        logging.debug(f"绘图任务被取消: {source}")
    except Exception as e:
        logging.error(f"延迟绘图失败: {e}")


async def is_within_time_window(event_data, source, max_hours=1):
    """检查地震事件是否在指定时间窗口内（默认1小时）"""
    # 排除非地震源，这些源不需要时间窗口检查
    non_earthquake_sources = {'weatheralarm', 'tsunami'}
    if source in non_earthquake_sources:
        return True
        
    shock_time_str = event_data.get('shockTime')
    if not shock_time_str:
        logging.warning("消息缺少震发时间，跳过处理")
        return False
    
    try:
        # 解析震发时间
        shock_time = datetime.strptime(shock_time_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        try:
            # 尝试其他时间格式
            shock_time = datetime.fromisoformat(shock_time_str.replace('Z', '+00:00'))
        except ValueError:
            logging.warning(f"无法解析震发时间: {shock_time_str}，跳过处理")
            return False
    
    # 计算当前时间和时间差
    current_time = datetime.now()
    time_diff = current_time - shock_time
    
    # 检查是否在时间窗口内（1小时内）
    if time_diff.total_seconds() <= max_hours * 3600 and time_diff.total_seconds() >= 0:
        return True
    else:
        logging.info(f"地震事件超出时间窗口（{max_hours}小时），跳过处理: 震发时间={shock_time_str}, 当前时间={current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        return False


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

    # 获取地震消息的唯一ID
    eq_id = event_data.get('id')
    if not eq_id:
        eq_id = f"{event_data.get('shockTime', '')}_{event_data.get('latitude', '')}_{event_data.get('longitude', '')}_{event_data.get('magnitude', '')}"

    # 创建源+ID的组合键用于去重
    composite_id = f"{source}_{eq_id}"

    # 检查是否为重复消息但有数据更新
    is_duplicate = False
    has_update = False
    
    # 检查内存中的重复
    if composite_id in processed_ids:
        is_duplicate = True
        # 获取已存储的数据进行比较
        stored_data = await get_stored_earthquake_data(eq_id, source)
        has_update = has_significant_update(stored_data, event_data)
        if has_update:
            logging.info(f"发现重复消息但有显著更新，复合ID: {composite_id}")
        else:
            logging.info(f"发现重复消息且无更新，跳过处理: {composite_id}")
            return None
    else:
        # 检查数据库中的重复
        db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM earthquakes WHERE source = ? AND id = ?", (source, eq_id)) as cursor:
                count = await cursor.fetchone()
                count = count[0] if count else 0
        
        if count > 0:
            is_duplicate = True
            stored_data = await get_stored_earthquake_data(eq_id, source)
            has_update = has_significant_update(stored_data, event_data)
            if has_update:
                logging.info(f"发现重复消息但有显著更新（数据库中），复合ID: {composite_id}")
            else:
                logging.info(f"发现重复消息且无更新（数据库中），跳过处理: {composite_id}")
                # 将ID加入内存集合避免后续重复检查
                processed_ids.add(composite_id)
                return None
    
    # 如果不是重复消息或有更新，则继续处理
    if not is_duplicate or has_update:
        # 将ID加入内存集合
        processed_ids.add(composite_id)
        
        # 一收到消息就进行时间校验（仅处理1小时内发生的地震）
        if not await is_within_time_window(event_data, source, max_hours=1):
            logging.info(f"地震事件超出1小时时间窗口，跳过处理: {event_data.get('id', 'unknown')}")
            return None

        # 检查数据源是否启用
        if apply_rules:
            if not await check_source_enabled(source, event_data, config):
                # 即使消息被过滤，也要保存到数据库，但不推送
                await save_earthquake_to_db(event_data, source)
                return None

        # 存储接收到的数据，用于测试命令（不管过滤规则如何）
        if source in config['draw_sources']:  # 只存储需要绘图的数据源
            received_earthquake_data[source] = event_data
            logging.info(f"存储数据源 {source} 用于测试命令")

        # 发送文本消息（立即发送）
        await process_text_message_only(event_data, source, config, target_group)

        # 处理绘图逻辑
        if source in config['draw_sources']:
            # 取消之前的待处理绘图任务（如果有）
            source_id = f"{source}_{eq_id}"
            await cancel_pending_draw_task(source_id)
            
            # 创建新的延迟绘图任务
            draw_task = asyncio.create_task(
                delayed_draw_and_send(event_data, source, config, target_group)
            )
            pending_draw_tasks[source_id] = {
                'task': draw_task,
                'event_data': event_data,
                'timestamp': datetime.now()
            }
            logging.info(f"创建延迟绘图任务: {source_id}")

        # 将地震数据保存到数据库
        await save_earthquake_to_db(event_data, source)

    return None


async def process_text_message_only(event_data, source, config, target_group=None):
    """仅处理文本消息（不包含绘图）"""
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


# API使用统计相关函数
async def record_weather_api_usage(group_id: str, user_id: str, command: str, api_endpoint: str):
    """记录天气API调用"""
    from datetime import datetime
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    current_month = datetime.now().strftime('%Y-%m')
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            '''INSERT INTO weather_api_usage (date, month, group_id, user_id, command, api_endpoint) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (current_date, current_month, group_id, user_id, command, api_endpoint)
        )
        await db.commit()


async def get_daily_usage_count():
    """获取今日API调用次数"""
    from datetime import datetime
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            'SELECT COUNT(*) FROM weather_api_usage WHERE date = ?', 
            (current_date,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_monthly_usage_count():
    """获取本月API调用次数"""
    from datetime import datetime
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
    current_month = datetime.now().strftime('%Y-%m')
    
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            'SELECT COUNT(*) FROM weather_api_usage WHERE month = ?', 
            (current_month,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_top_users_daily():
    """获取今日调用最多的用户"""
    from datetime import datetime
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            '''SELECT group_id, user_id, COUNT(*) as count 
               FROM weather_api_usage 
               WHERE date = ? 
               GROUP BY group_id, user_id 
               ORDER BY count DESC 
               LIMIT 1''',
            (current_date,)
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else None


async def get_top_users_monthly():
    """获取本月调用最多的用户"""
    from datetime import datetime
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
    current_month = datetime.now().strftime('%Y-%m')
    
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            '''SELECT group_id, user_id, COUNT(*) as count 
               FROM weather_api_usage 
               WHERE month = ? 
               GROUP BY group_id, user_id 
               ORDER BY count DESC 
               LIMIT 1''',
            (current_month,)
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else None


async def get_top_groups_daily():
    """获取今日调用最多的群组"""
    from datetime import datetime
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            '''SELECT group_id, COUNT(*) as count 
               FROM weather_api_usage 
               WHERE date = ? 
               GROUP BY group_id 
               ORDER BY count DESC 
               LIMIT 1''',
            (current_date,)
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else None


async def get_top_groups_monthly():
    """获取本月调用最多的群组"""
    from datetime import datetime
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
    current_month = datetime.now().strftime('%Y-%m')
    
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            '''SELECT group_id, COUNT(*) as count 
               FROM weather_api_usage 
               WHERE month = ? 
               GROUP BY group_id 
               ORDER BY count DESC 
               LIMIT 1''',
            (current_month,)
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else None