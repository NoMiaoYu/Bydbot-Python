"""
Bydbot - 早晚安功能模块
处理用户的早安/晚安命令，计算清醒时间，发送个性化问候
"""

import asyncio
import logging
import aiosqlite
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from message_sender import send_group_msg, send_group_msg_with_text_and_image
from weather_api import QWeatherAPI

# 全局变量
morning_evening_db_path = None

async def init_morning_evening_db():
    """初始化早晚安数据库路径"""
    global morning_evening_db_path
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    morning_evening_db_path = os.path.join(data_dir, 'eqdata.db')
    logging.info("早晚安数据库路径初始化完成")

def get_db_path() -> str:
    """获取数据库路径"""
    global morning_evening_db_path
    if morning_evening_db_path is None:
        raise RuntimeError("早晚安数据库未初始化")
    return morning_evening_db_path

async def get_user_status(user_id: str, group_id: str) -> Optional[Dict]:
    """获取用户早晚安状态"""
    try:
        async with aiosqlite.connect(get_db_path()) as db:
            async with db.execute(
                """SELECT last_morning_time, last_evening_time, wake_up_time, location_id 
                   FROM morning_evening_status 
                   WHERE user_id = ? AND group_id = ?""",
                (user_id, group_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'last_morning_time': row[0],
                        'last_evening_time': row[1],
                        'wake_up_time': row[2],
                        'location_id': row[3]
                    }
        return None
    except Exception as e:
        logging.error(f"获取用户状态失败: {e}")
        return None

async def update_user_status(user_id: str, group_id: str, is_morning: bool, location_id: str = None) -> bool:
    """更新用户早晚安状态"""
    try:
        current_time = datetime.now()
        async with aiosqlite.connect(get_db_path()) as db:
            # 先检查记录是否存在
            async with db.execute(
                "SELECT id FROM morning_evening_status WHERE user_id = ? AND group_id = ?",
                (user_id, group_id)
            ) as cursor:
                existing_record = await cursor.fetchone()
            
            if existing_record:
                # 记录存在，使用UPDATE
                if is_morning:
                    # 早安：更新早安时间，计算清醒时间
                    last_evening = await get_last_evening_time(user_id, group_id)
                    wake_up_time = calculate_wake_up_time(last_evening, current_time) if last_evening else "未知"
                    
                    await db.execute("""
                        UPDATE morning_evening_status 
                        SET last_morning_time = ?, wake_up_time = ?, location_id = ?, updated_at = ?
                        WHERE user_id = ? AND group_id = ?
                    """, (current_time.isoformat(), wake_up_time, location_id, current_time.isoformat(), user_id, group_id))
                else:
                    # 晚安：只更新晚安时间
                    await db.execute("""
                        UPDATE morning_evening_status 
                        SET last_evening_time = ?, location_id = ?, updated_at = ?
                        WHERE user_id = ? AND group_id = ?
                    """, (current_time.isoformat(), location_id, current_time.isoformat(), user_id, group_id))
            else:
                # 记录不存在，使用INSERT
                if is_morning:
                    # 早安：插入新记录
                    last_evening = await get_last_evening_time(user_id, group_id)
                    wake_up_time = calculate_wake_up_time(last_evening, current_time) if last_evening else "未知"
                    
                    await db.execute("""
                        INSERT INTO morning_evening_status 
                        (user_id, group_id, last_morning_time, wake_up_time, location_id, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (user_id, group_id, current_time.isoformat(), wake_up_time, location_id, current_time.isoformat()))
                else:
                    # 晚安：插入新记录
                    await db.execute("""
                        INSERT INTO morning_evening_status 
                        (user_id, group_id, last_evening_time, location_id, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, group_id, current_time.isoformat(), location_id, current_time.isoformat()))
            
            await db.commit()
        return True
    except Exception as e:
        logging.error(f"更新用户状态失败: {e}")
        return False

async def get_last_evening_time(user_id: str, group_id: str) -> Optional[datetime]:
    """获取用户上次晚安时间"""
    try:
        async with aiosqlite.connect(get_db_path()) as db:
            async with db.execute(
                "SELECT last_evening_time FROM morning_evening_status WHERE user_id = ? AND group_id = ?",
                (user_id, group_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return datetime.fromisoformat(row[0])
        return None
    except Exception as e:
        logging.error(f"获取上次晚安时间失败: {e}")
        return None

def calculate_wake_up_time(last_evening: datetime, current_morning: datetime) -> str:
    """计算清醒时间"""
    try:
        # 如果晚安时间在早上6点之后，说明跨天了
        evening_cutoff = last_evening.replace(hour=6, minute=0, second=0, microsecond=0)
        if last_evening > evening_cutoff:
            # 跨天情况：从晚安到第二天早上6点 + 从早上6点到早安
            time_diff = (current_morning - last_evening).total_seconds()
        else:
            # 同一天情况
            time_diff = (current_morning - last_evening).total_seconds()
        
        hours = int(time_diff // 3600)
        minutes = int((time_diff % 3600) // 60)
        
        if hours > 0:
            return f"{hours}小时{minutes}分钟"
        else:
            return f"{minutes}分钟"
    except Exception as e:
        logging.error(f"计算清醒时间失败: {e}")
        return "未知"

async def is_already_greeted_today(user_id: str, group_id: str, is_morning: bool) -> bool:
    """检查用户今天是否已经发送过早安/晚安"""
    # 测试群(1071528933)无视重复机制，用于测试功能
    test_group_id = "1071528933"
    if group_id == test_group_id:
        logging.info(f"测试群 {group_id} 无视重复机制")
        return False
    
    try:
        async with aiosqlite.connect(get_db_path()) as db:
            if is_morning:
                # 检查今天的早安记录（从早上6点开始算作新的一天）
                today_start = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
                if datetime.now().hour < 6:
                    # 如果现在是凌晨，检查昨天6点到现在
                    today_start = today_start - timedelta(days=1)
                
                async with db.execute(
                    """SELECT 1 FROM morning_evening_status 
                       WHERE user_id = ? AND group_id = ? AND last_morning_time >= ?""",
                    (user_id, group_id, today_start.isoformat())
                ) as cursor:
                    return await cursor.fetchone() is not None
            else:
                # 检查今天的晚安记录
                today_start = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
                if datetime.now().hour < 6:
                    today_start = today_start - timedelta(days=1)
                
                async with db.execute(
                    """SELECT 1 FROM morning_evening_status 
                       WHERE user_id = ? AND group_id = ? AND last_evening_time >= ?""",
                    (user_id, group_id, today_start.isoformat())
                ) as cursor:
                    return await cursor.fetchone() is not None
    except Exception as e:
        logging.error(f"检查重复问候失败: {e}")
        return False

async def get_user_location_id(user_id: str, group_id: str) -> Optional[str]:
    """获取用户订阅地区的LocationID"""
    try:
        # 从订阅表中获取用户订阅的最小行政区域
        async with aiosqlite.connect(get_db_path()) as db:
            async with db.execute(
                """SELECT full_location FROM weather_subscriptions 
                   WHERE user_id = ? AND group_id = ? AND location_type = 'location' 
                   ORDER BY full_location DESC LIMIT 1""",
                (user_id, group_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    # 使用城市搜索获取LocationID
                    return await get_location_id_by_name(row[0])
        return None
    except Exception as e:
        logging.error(f"获取用户LocationID失败: {e}")
        return None

async def get_location_id_by_name(location_name: str) -> Optional[str]:
    """通过地区名称获取LocationID"""
    try:
        # 从配置中获取天气API配置
        from config_wrapper import ConfigWrapper
        config_wrapper = ConfigWrapper()
        config = {
            'qweather': {
                'api_host': config_wrapper.get('qweather.api_host', 'devapi.qweather.com'),
                'api_key': config_wrapper.get('qweather.api_key', ''),
                'jwt_token': config_wrapper.get('qweather.jwt_token', ''),
                'use_jwt': config_wrapper.get('qweather.use_jwt', False),
                'cache_enabled': config_wrapper.get('qweather.cache_enabled', True),
                'cache_ttl': config_wrapper.get('qweather.cache_ttl', 600),
                'daily_limit': config_wrapper.get('qweather.daily_limit', 1500),
                'enabled': config_wrapper.get('qweather.enabled', True)
            }
        }
        
        # 使用城市搜索获取LocationID
        location_id = await search_city_location(location_name, config)
        if location_id:
            logging.info(f"成功获取 {location_name} 的LocationID: {location_id}")
            return location_id
        else:
            logging.warning(f"无法获取 {location_name} 的LocationID，使用默认值")
            return "101010100"  # 默认北京的LocationID
    except Exception as e:
        logging.error(f"获取LocationID失败: {e}")
        return "101010100"  # 默认北京的LocationID

async def handle_morning_evening_command(command: str, user_id: str, group_id: str, config: Dict) -> bool:
    """处理早晚安命令"""
    try:
        is_morning = command == "早安"
        
        # 检查是否已经问候过
        if await is_already_greeted_today(user_id, group_id, is_morning):
            greeting = "早安" if is_morning else "晚安"
            # 测试群添加特殊提示
            test_group_id = "1071528933"
            if group_id == test_group_id:
                from message_sender import send_group_msg_with_at
                message = f"测试模式：无视重复机制，继续处理{greeting}命令"
                await send_group_msg_with_at(group_id, message, user_id)
            else:
                from message_sender import send_group_msg_with_at
                message = f"您今天已经{greeting}过了哦~"
                await send_group_msg_with_at(group_id, message, user_id)
                return True
        
        # 获取用户订阅的LocationID
        location_id = await get_user_location_id(user_id, group_id)
        
        # 更新用户状态
        if not await update_user_status(user_id, group_id, is_morning, location_id):
            from message_sender import send_group_msg_with_at
            await send_group_msg_with_at(group_id, "系统繁忙，请稍后再试", user_id)
            return False
        
        # 发送问候消息
        if is_morning:
            await send_morning_greeting(user_id, group_id, location_id, config)
        else:
            await send_evening_greeting(user_id, group_id)
            
        return True
    except Exception as e:
        logging.error(f"处理早晚安命令失败: {e}")
        from message_sender import send_group_msg_with_at
        await send_group_msg_with_at(group_id, "处理失败，请稍后再试", user_id)
        return False

async def send_morning_greeting(user_id: str, group_id: str, location_id: str, config: Dict):
    """发送早安问候"""
    try:
        from message_sender import send_group_msg_with_at, send_group_msg_with_text_and_image
        
        # 构建基础问候消息
        message = "早安喵~"
        
        # 如果有LocationID，获取天气预报
        weather_info = None
        if location_id:
            weather_info = await get_weather_forecast(location_id, config)
            if weather_info:
                message += f"\n今日天气预报：{weather_info}"
        
        # 发送带@的消息
        await send_group_msg_with_at(group_id, message, user_id)
        
        # 发送每日新闻图
        news_image_path = await get_daily_news_image()
        if news_image_path:
            await send_group_msg_with_text_and_image(group_id, "每日新闻图：", news_image_path, user_id)
        
    except Exception as e:
        logging.error(f"发送早安问候失败: {e}")
        from message_sender import send_group_msg_with_at
        await send_group_msg_with_at(group_id, "早安喵~", user_id)

async def send_evening_greeting(user_id: str, group_id: str):
    """发送晚安问候"""
    try:
        from message_sender import send_group_msg_with_at
        
        # 获取用户状态
        user_status = await get_user_status(user_id, group_id)
        has_morning_record = user_status and user_status.get('last_morning_time')
        
        if has_morning_record:
            # 有早安记录，显示清醒时间
            wake_up_time = user_status.get('wake_up_time', '未知')
            message = f"晚安喵~ 今天清醒了{wake_up_time}"
        else:
            # 没有早安记录，只发送基本晚安
            message = "晚安喵~"
            
            # 测试群添加特殊提示
            test_group_id = "1071528933"
            if group_id == test_group_id:
                message += " (测试模式：今天未发送早安)"
        
        # 发送带@的消息
        await send_group_msg_with_at(group_id, message, user_id)
        
    except Exception as e:
        logging.error(f"发送晚安问候失败: {e}")
        from message_sender import send_group_msg_with_at
        await send_group_msg_with_at(group_id, "晚安喵~", user_id)

async def get_weather_forecast(location_id: str, config: Dict) -> Optional[str]:
    """获取天气预报信息"""
    try:
        api = QWeatherAPI(config)
        result = await api.weather_forecast("3d", location_id, "zh", "m")
        if result and 'daily' in result:
            # 提取今日天气信息
            today_weather = result['daily'][0] if result['daily'] else None
            if today_weather:
                temp_max = today_weather.get('tempMax', 'N/A')
                temp_min = today_weather.get('tempMin', 'N/A')
                text_day = today_weather.get('textDay', 'N/A')
                return f"{text_day}，气温{temp_min}-{temp_max}°C"
        return None
    except Exception as e:
        logging.error(f"获取天气预报失败: {e}")
        return None

async def get_daily_news_image() -> Optional[str]:
    """获取每日新闻图"""
    try:
        # 调用UAPI的每日新闻图功能
        from uapi_client import UApiClient
        from config_wrapper import ConfigWrapper
        
        config_wrapper = ConfigWrapper()
        config = {
            'uapi': {
                'base_url': config_wrapper.get('uapi.base_url', 'https://uapis.cn'),
                'api_key': config_wrapper.get('uapi.api_key', ''),
                'timeout': config_wrapper.get('uapi.timeout', 30),
                'cache_enabled': config_wrapper.get('uapi.cache_enabled', True),
                'cache_ttl': config_wrapper.get('uapi.cache_ttl', 600)
            }
        }
        
        api = UApiClient(config)
        image_data = await api.get_daily_news_image()
        
        if image_data:
            # 下载图片到本地缓存
            import aiohttp
            import os
            
            cache_dir = os.path.join(os.path.dirname(__file__), 'pictures', 'news_images')
            os.makedirs(cache_dir, exist_ok=True)
            
            filename = f"daily_news_{datetime.now().strftime('%Y%m%d')}.jpg"
            local_path = os.path.join(cache_dir, filename)
            
            # 如果本地已存在，直接返回
            if os.path.exists(local_path):
                return local_path
            
            # 保存图片数据
            with open(local_path, 'wb') as f:
                f.write(image_data)
            logging.info(f"每日新闻图保存成功: {local_path}")
            return local_path
        
        logging.warning("每日新闻图API返回数据格式错误")
        return None
    except Exception as e:
        logging.error(f"获取每日新闻图失败: {e}")
        return None

async def search_city_location(city_name: str, config: Dict) -> Optional[str]:
    """通过城市名称搜索LocationID"""
    try:
        api = QWeatherAPI(config)
        result = await api.geo_lookup(city_name, None, None, 1, "zh")
        if result and 'location' in result and result['location']:
            location = result['location'][0]
            return location.get('id')
        return None
    except Exception as e:
        logging.error(f"搜索城市LocationID失败: {e}")
        return None