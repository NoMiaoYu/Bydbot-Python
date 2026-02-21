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
    """获取用户早晚安状态（简化版）"""
    try:
        async with aiosqlite.connect(get_db_path()) as db:
            async with db.execute(
                """SELECT last_morning_time, last_evening_time, location_id 
                   FROM morning_evening_status 
                   WHERE user_id = ? AND group_id = ?""",
                (user_id, group_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'last_morning_time': row[0],
                        'last_evening_time': row[1],
                        'location_id': row[2]
                    }
        return None
    except Exception as e:
        logging.error(f"获取用户状态失败: {e}")
        return None

async def update_user_status(user_id: str, group_id: str, is_morning: bool, location_id: str = None) -> bool:
    """更新用户早晚安状态 - 简化版（移除清醒时间计算）"""
    try:
        current_time = datetime.now()
        async with aiosqlite.connect(get_db_path()) as db:
            # 定义一天的开始时间
            today_start = current_time.replace(hour=6, minute=0, second=0, microsecond=0)
            if current_time.hour < 6:
                today_start = today_start - timedelta(days=1)
            
            # 先检查记录是否存在
            async with db.execute(
                "SELECT id FROM morning_evening_status WHERE user_id = ? AND group_id = ?",
                (user_id, group_id)
            ) as cursor:
                existing_record = await cursor.fetchone()
            
            if existing_record:
                # 记录存在，使用UPDATE
                if is_morning:
                    # 早安：只更新早安时间和位置
                    await db.execute("""
                        UPDATE morning_evening_status 
                        SET last_morning_time = ?, location_id = ?, updated_at = ?
                        WHERE user_id = ? AND group_id = ?
                    """, (current_time.isoformat(), location_id, current_time.isoformat(), user_id, group_id))
                else:
                    # 晚安：只更新晚安时间和位置
                    await db.execute("""
                        UPDATE morning_evening_status 
                        SET last_evening_time = ?, location_id = ?, updated_at = ?
                        WHERE user_id = ? AND group_id = ?
                    """, (current_time.isoformat(), location_id, current_time.isoformat(), user_id, group_id))
            else:
                # 记录不存在，使用INSERT
                if is_morning:
                    # 早安：插入新记录（只记录早安时间）
                    await db.execute("""
                        INSERT INTO morning_evening_status 
                        (user_id, group_id, last_morning_time, location_id, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, group_id, current_time.isoformat(), location_id, current_time.isoformat()))
                else:
                    # 晚安：插入新记录（只记录晚安时间）
                    await db.execute("""
                        INSERT INTO morning_evening_status 
                        (user_id, group_id, last_evening_time, location_id, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (user_id, group_id, current_time.isoformat(), location_id, current_time.isoformat()))
            
            await db.commit()
            logging.info(f"用户 {user_id} 状态更新成功 (早安: {is_morning})")
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
    """计算清醒时间 - 重写版本"""
    try:
        # 基本验证
        if not isinstance(last_evening, datetime) or not isinstance(current_morning, datetime):
            logging.warning("时间参数类型错误")
            return "未知"
        
        # 时间顺序验证：早安必须晚于晚安
        if current_morning <= last_evening:
            logging.warning(f"时间顺序错误：早安({current_morning}) <= 晚安({last_evening})")
            return "未知"
        
        # 计算时间差（秒）
        time_diff_seconds = (current_morning - last_evening).total_seconds()
        
        # 合理性检查
        if time_diff_seconds <= 0:
            logging.warning(f"清醒时间非正数: {time_diff_seconds}秒")
            return "未知"
        
        if time_diff_seconds > 86400:  # 24小时 = 86400秒
            logging.warning(f"清醒时间过长: {time_diff_seconds}秒 ({time_diff_seconds/3600:.1f}小时)")
            return "未知"
        
        # 转换为小时和分钟
        hours = int(time_diff_seconds // 3600)
        remaining_seconds = time_diff_seconds % 3600
        minutes = int(remaining_seconds // 60)
        
        # 格式化输出
        if hours > 0:
            if minutes > 0:
                return f"{hours}小时{minutes}分钟"
            else:
                return f"{hours}小时"
        else:
            if minutes > 0:
                return f"{minutes}分钟"
            else:
                # 小于1分钟的情况
                seconds = int(remaining_seconds)
                if seconds > 0:
                    return f"{seconds}秒"
                else:
                    return "0分钟"
                    
    except Exception as e:
        logging.error(f"计算清醒时间异常: {e}")
        return "未知"

async def is_already_greeted_today(user_id: str, group_id: str, is_morning: bool) -> bool:
    """检查用户今天是否已经发送过早安/晚安 - 增强版"""
    # 测试群(1071528933)无视重复机制，用于测试功能
    test_group_id = "1071528933"
    if group_id == test_group_id:
        logging.info(f"测试群 {group_id} 无视重复机制")
        return False
    
    try:
        async with aiosqlite.connect(get_db_path()) as db:
            # 定义一天的开始时间为早上6点
            now = datetime.now()
            today_start = now.replace(hour=6, minute=0, second=0, microsecond=0)
            
            # 如果现在是凌晨(0-6点)，则今天的开始时间是昨天6点
            if now.hour < 6:
                today_start = today_start - timedelta(days=1)
            
            # 计算昨天的开始时间（用于清理过期数据）
            yesterday_start = today_start - timedelta(days=1)
            
            # 清理过期数据（超过2天的记录）
            await db.execute("""
                DELETE FROM morning_evening_status 
                WHERE updated_at < ?
            """, (yesterday_start.isoformat(),))
            
            if is_morning:
                # 检查今天的早安记录
                async with db.execute(
                    """SELECT 1 FROM morning_evening_status 
                       WHERE user_id = ? AND group_id = ? AND last_morning_time >= ?""",
                    (user_id, group_id, today_start.isoformat())
                ) as cursor:
                    has_morning_today = await cursor.fetchone() is not None
                
                # 如果今天还没有早安记录，重置昨天的状态
                if not has_morning_today:
                    await db.execute("""
                        UPDATE morning_evening_status 
                        SET last_morning_time = NULL
                        WHERE user_id = ? AND group_id = ? AND last_morning_time < ?
                    """, (user_id, group_id, today_start.isoformat()))
                    logging.info(f"用户 {user_id} 状态已重置（跨天）")
                
                return has_morning_today
            else:
                # 检查今天的晚安记录
                async with db.execute(
                    """SELECT 1 FROM morning_evening_status 
                       WHERE user_id = ? AND group_id = ? AND last_evening_time >= ?""",
                    (user_id, group_id, today_start.isoformat())
                ) as cursor:
                    has_evening_today = await cursor.fetchone() is not None
                
                # 如果今天还没有晚安记录，重置昨天的状态
                if not has_evening_today:
                    await db.execute("""
                        UPDATE morning_evening_status 
                        SET last_evening_time = NULL
                        WHERE user_id = ? AND group_id = ? AND last_evening_time < ?
                    """, (user_id, group_id, today_start.isoformat()))
                    logging.info(f"用户 {user_id} 晚安状态已重置（跨天）")
                
                return has_evening_today
                
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
    """发送晚安问候 - 简化版（移除清醒时间）"""
    try:
        from message_sender import send_group_msg_with_at
        
        # 直接发送简单的晚安消息
        message = "晚安喵~"
        
        # 测试群添加特殊提示
        test_group_id = "1071528933"
        if group_id == test_group_id:
            message += " (测试模式)"
        
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