"""
Bydbot - CMA气象预警订阅模块
负责处理用户订阅的气象预警功能
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
import aiosqlite
import os
import requests
import aiohttp
from bs4 import BeautifulSoup

from message_sender import send_group_msg
from weather_alarm_client import CMWeatherAlarmClient


class CMAWeatherSubscriber:
    def __init__(self, config: Dict):
        self.config = config
        self.client = CMWeatherAlarmClient()
        self.subscribers = {}  # {location: [(group_id, user_id), ...]}  # 支持省市级别订阅
        self.location_subscribers = {}  # {full_location: [(group_id, user_id), ...]}  # 新增：支持省市区三级格式订阅
        self.last_checked_time = 0
        self.check_interval = 7 * 60  # 7分钟检查一次
        self.last_processed_alarms = set()  # 已处理的预警ID集合
        self.db_path = os.path.join(os.path.dirname(__file__), 'data', 'eqdata.db')
        # 图标缓存目录
        self.icon_cache_dir = os.path.join(os.path.dirname(__file__), 'pictures', 'weather_icons')
        os.makedirs(self.icon_cache_dir, exist_ok=True)
        
    async def init_db(self):
        """初始化订阅相关的数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            # 创建订阅表 - 添加新的列以支持省市区格式
            await db.execute('''
                CREATE TABLE IF NOT EXISTS weather_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    province TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    location_type TEXT DEFAULT 'province',  -- 'province' 或 'location' 表示不同格式
                    full_location TEXT DEFAULT '',  -- 存储完整的省市区格式
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(province, group_id, user_id, location_type)
                )
            ''')

            # 创建已处理预警表
            await db.execute('''
                CREATE TABLE IF NOT EXISTS processed_weather_alarms (
                    alertid TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    issuetime TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await db.commit()

        logging.info("CMA气象预警订阅数据库初始化完成")
        
    async def load_subscriptions(self):
        """从数据库加载订阅信息"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 检查表是否存在
                cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='weather_subscriptions'")
                table_exists = await cursor.fetchone()
                if not table_exists:
                    logging.info("气象预警订阅表不存在，创建新表")
                    await self.init_db()
                else:
                    # 检查表结构，如果缺少新列则添加
                    cursor = await db.execute("PRAGMA table_info(weather_subscriptions)")
                    columns = await cursor.fetchall()
                    column_names = [col[1] for col in columns]
                    
                    # 检查是否缺少location_type列
                    if 'location_type' not in column_names:
                        logging.info("检测到旧版本数据库，正在更新表结构...")
                        await db.execute("ALTER TABLE weather_subscriptions ADD COLUMN location_type TEXT DEFAULT 'province'")
                    
                    # 检查是否缺少full_location列
                    if 'full_location' not in column_names:
                        await db.execute("ALTER TABLE weather_subscriptions ADD COLUMN full_location TEXT DEFAULT ''")
                    
                    await db.commit()
                
                # 加载订阅数据
                async with db.execute("SELECT province, group_id, user_id, location_type, full_location FROM weather_subscriptions") as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        province, group_id, user_id, location_type, full_location = row
                        # 使用完整的省市区路径作为键
                        location_key = full_location if location_type == 'location' and full_location else province
                        if location_key not in self.subscribers:
                            self.subscribers[location_key] = []
                        self.subscribers[location_key].append((group_id, user_id))
                    logging.info(f"加载了 {len(rows)} 条气象预警订阅记录")
        except Exception as e:
            logging.error(f"加载气象预警订阅记录失败: {e}")
        
    async def subscribe_province(self, province: str, group_id: str, user_id: str) -> bool:
        """订阅特定省份的气象预警"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO weather_subscriptions (province, group_id, user_id) VALUES (?, ?, ?)",
                    (province, group_id, user_id)
                )
                await db.commit()
                
            # 更新内存中的订阅信息
            if province not in self.subscribers:
                self.subscribers[province] = []
            if (group_id, user_id) not in self.subscribers[province]:
                self.subscribers[province].append((group_id, user_id))
                
            logging.info(f"用户 {user_id} 在群 {group_id} 订阅了 {province} 的气象预警")
            return True
            
        except Exception as e:
            logging.error(f"订阅失败: {e}")
            return False
            
    async def subscribe_location(self, full_location: str, group_id: str, user_id: str) -> bool:
        """订阅特定地区的气象预警（支持省市区格式）"""
        try:
            # 提取省份作为主要匹配字段
            # 从完整地区名称中提取省份部分
            province = self.extract_province_from_location(full_location)
            if not province:
                logging.error(f"无法从 {full_location} 中提取省份信息")
                return False
            
            # 使用省份作为主要匹配字段，但存储完整路径
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO weather_subscriptions (province, group_id, user_id, location_type, full_location) VALUES (?, ?, ?, 'location', ?)",
                    (province, group_id, user_id, full_location)
                )
                await db.commit()
                
            # 更新内存中的订阅信息
            if full_location not in self.location_subscribers:
                self.location_subscribers[full_location] = []
            if (group_id, user_id) not in self.location_subscribers[full_location]:
                self.location_subscribers[full_location].append((group_id, user_id))
                
            logging.info(f"用户 {user_id} 在群 {group_id} 订阅了 {full_location} 的气象预警")
            return True
            
        except Exception as e:
            logging.error(f"地区订阅失败: {e}")
            return False
            
    async def unsubscribe_location(self, full_location: str, group_id: str, user_id: str) -> bool:
        """取消订阅特定地区的气象预警（支持省市区格式）"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM weather_subscriptions WHERE full_location=? AND group_id=? AND user_id=? AND location_type='location'",
                    (full_location, group_id, user_id)
                )
                await db.commit()
                
            # 更新内存中的订阅信息
            if full_location in self.location_subscribers:
                self.location_subscribers[full_location] = [
                    (g, u) for g, u in self.location_subscribers[full_location] 
                    if not (g == group_id and u == user_id)
                ]
                if not self.location_subscribers[full_location]:
                    del self.location_subscribers[full_location]
                    
            logging.info(f"用户 {user_id} 在群 {group_id} 取消订阅了 {full_location} 的气象预警")
            return True
            
        except Exception as e:
            logging.error(f"取消地区订阅失败: {e}")
            return False
            
    async def unsubscribe_province(self, province: str, group_id: str, user_id: str) -> bool:
        """取消订阅特定省份的气象预警"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM weather_subscriptions WHERE province=? AND group_id=? AND user_id=?",
                    (province, group_id, user_id)
                )
                await db.commit()
                
            # 更新内存中的订阅信息
            if province in self.subscribers:
                self.subscribers[province] = [
                    (g, u) for g, u in self.subscribers[province] 
                    if not (g == group_id and u == user_id)
                ]
                if not self.subscribers[province]:
                    del self.subscribers[province]
                    
            logging.info(f"用户 {user_id} 在群 {group_id} 取消订阅了 {province} 的气象预警")
            return True
            
        except Exception as e:
            logging.error(f"取消订阅失败: {e}")
            return False
            
    async def subscribe_nationwide(self, group_id: str, user_id: str) -> bool:
        """订阅全国气象预警（接收所有预警）"""
        try:
            # 使用特殊标识"全国"作为省份字段
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO weather_subscriptions (province, group_id, user_id, location_type, full_location) VALUES (?, ?, ?, 'nationwide', '全国')",
                    ("全国", group_id, user_id)
                )
                await db.commit()
                
            # 更新内存中的订阅信息
            if "全国" not in self.subscribers:
                self.subscribers["全国"] = []
            if (group_id, user_id) not in self.subscribers["全国"]:
                self.subscribers["全国"].append((group_id, user_id))
                
            logging.info(f"用户 {user_id} 在群 {group_id} 订阅了全国气象预警")
            return True
            
        except Exception as e:
            logging.error(f"全国订阅失败: {e}")
            return False
            
    async def unsubscribe_nationwide(self, group_id: str, user_id: str) -> bool:
        """取消订阅全国气象预警"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "DELETE FROM weather_subscriptions WHERE province='全国' AND group_id=? AND user_id=? AND location_type='nationwide'",
                    (group_id, user_id)
                )
                await db.commit()
                
            # 更新内存中的订阅信息
            if "全国" in self.subscribers:
                self.subscribers["全国"] = [
                    (g, u) for g, u in self.subscribers["全国"] 
                    if not (g == group_id and u == user_id)
                ]
                if not self.subscribers["全国"]:
                    del self.subscribers["全国"]
                    
            logging.info(f"用户 {user_id} 在群 {group_id} 取消订阅了全国气象预警")
            return True
            
        except Exception as e:
            logging.error(f"取消全国订阅失败: {e}")
            return False
            
    async def get_user_subscriptions(self, user_id: str) -> List[Tuple[str, str, str]]:
        """获取用户的订阅列表 (display_name, group_id, location_type)"""
        subscriptions = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT province, group_id, location_type, full_location FROM weather_subscriptions WHERE user_id=?", 
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                for province, group_id, location_type, full_location in rows:
                    # 根据订阅类型决定显示名称
                    if location_type == 'location' and full_location:
                        display_name = full_location  # 显示完整地区名称
                    else:
                        display_name = province  # 显示省份名称
                    subscriptions.append((display_name, group_id, location_type))
                
        return subscriptions
        
    async def get_subscribed_provinces(self) -> List[str]:
        """获取所有被订阅的省份列表"""
        provinces = set()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT DISTINCT province FROM weather_subscriptions") as cursor:
                rows = await cursor.fetchall()
                provinces = {row[0] for row in rows}
                
        return list(provinces)
        
    def extract_province_from_title(self, title: str) -> List[str]:
        """从预警标题中提取省份信息"""
        # 常见的中国省份列表（不包含"省"、"市"、"自治区"、"特别行政区"等后缀）
        provinces = [
            "北京", "天津", "上海", "重庆",
            "河北", "山西", "辽宁", "吉林", "黑龙江",
            "江苏", "浙江", "安徽", "福建", "江西", "山东",
            "河南", "湖北", "湖南", "广东", "海南",
            "四川", "贵州", "云南", "陕西", "甘肃", "青海",
            "内蒙古", "广西", "西藏", "宁夏", "新疆",
            "香港", "澳门", "台湾"
        ]
        
        found_provinces = []
        for province in provinces:
            if province in title:
                found_provinces.append(province)
                
        return found_provinces
        
    async def download_and_cache_icon(self, pic_url: str, alertid: str) -> Optional[str]:
        """下载并缓存预警图标，返回本地文件路径"""
        if not pic_url:
            return None
                
        try:
            # 生成本地文件名
            filename = f"weather_icon_{alertid}.png"
            local_path = os.path.join(self.icon_cache_dir, filename)
                
            # 检查是否已缓存
            if os.path.exists(local_path):
                logging.info(f"使用已缓存的预警图标: {local_path}")
                return local_path
                
            # 下载图标
            full_url = pic_url if pic_url.startswith('http') else f"https://www.nmc.cn{pic_url}"
                
            async with aiohttp.ClientSession() as session:
                async with session.get(full_url) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        with open(local_path, 'wb') as f:
                            f.write(img_data)
                        logging.info(f"预警图标下载并缓存成功: {local_path}")
                        return local_path
                    else:
                        logging.error(f"下载预警图标失败，状态码: {resp.status}")
                        return None
        except Exception as e:
            logging.error(f"下载预警图标时出错: {e}")
            return None
        
    def extract_province_from_location(self, location: str) -> str:
        """从完整地区名称中提取省份信息"""
        # 常见的中国省份列表（包含后缀）
        province_patterns = [
            "北京市", "天津市", "上海市", "重庆市",
            "河北省", "山西省", "辽宁省", "吉林省", "黑龙江省",
            "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
            "河南省", "湖北省", "湖南省", "广东省", "海南省",
            "四川省", "贵州省", "云南省", "陕西省", "甘肃省", "青海省",
            "内蒙古自治区", "广西壮族自治区", "西藏自治区", "宁夏回族自治区", "新疆维吾尔自治区",
            "香港特别行政区", "澳门特别行政区", "台湾省"
        ]
        
        # 简化版本的省份列表（不包含后缀）
        simple_provinces = [
            "北京", "天津", "上海", "重庆",
            "河北", "山西", "辽宁", "吉林", "黑龙江",
            "江苏", "浙江", "安徽", "福建", "江西", "山东",
            "河南", "湖北", "湖南", "广东", "海南",
            "四川", "贵州", "云南", "陕西", "甘肃", "青海",
            "内蒙古", "广西", "西藏", "宁夏", "新疆",
            "香港", "澳门", "台湾"
        ]
        
        # 先尝试匹配完整格式
        for pattern in province_patterns:
            if location.startswith(pattern):
                # 返回简化版本的省份名
                for simple_prov in simple_provinces:
                    if pattern.startswith(simple_prov):
                        return simple_prov
                return pattern.replace("省", "").replace("市", "").replace("自治区", "").replace("特别行政区", "")
        
        # 再尝试匹配简化格式
        for simple_prov in simple_provinces:
            if location.startswith(simple_prov):
                return simple_prov
                
        return ""
        
    async def check_and_send_alarms(self):
        """检查并发送气象预警"""
        current_time = time.time()
        
        # 检查是否到了检查时间
        if current_time - self.last_checked_time < self.check_interval:
            return
            
        self.last_checked_time = current_time
        logging.info("开始检查CMA气象预警...")
        
        try:
            # 获取最新的预警信息
            latest_alarms = self.client.get_latest_alarms(count=20)
            
            if not latest_alarms:
                logging.warning("未能获取到最新的气象预警信息")
                return
                
            # 检查每个预警是否与订阅的省份匹配
            for alarm in latest_alarms:
                alertid = alarm.get('alertid', '')
                title = alarm.get('title', '')
                issuetime = alarm.get('issuetime', '')
                
                # 检查是否已经处理过这个预警
                async with aiosqlite.connect(self.db_path) as db:
                    async with db.execute(
                        "SELECT 1 FROM processed_weather_alarms WHERE alertid=?", 
                        (alertid,)
                    ) as cursor:
                        exists = await cursor.fetchone()
                        
                if exists:
                    continue  # 已经处理过，跳过
                    
                # 提取标题中的省份信息
                provinces_in_title = self.extract_province_from_title(title)
                
                # 检查是否有订阅的省份匹配
                matched_subscribers = []
                
                # 检查普通省份订阅
                for province in provinces_in_title:
                    if province in self.subscribers:
                        matched_subscribers.extend(self.subscribers[province])
                
                # 检查全国订阅（接收所有预警）
                if "全国" in self.subscribers:
                    matched_subscribers.extend(self.subscribers["全国"])
                    logging.info(f"全国订阅者匹配到预警: {title}")
                
                # 检查地区级订阅
                for full_location, subscribers_list in self.location_subscribers.items():
                    # 简单匹配逻辑
                    if full_location in title:
                        matched_subscribers.extend(subscribers_list)
                        logging.info(f"地区订阅者 {full_location} 匹配到预警: {title}")
                        
                if not matched_subscribers:
                    continue  # 没有匹配的订阅者，跳过
                    
                # 获取预警详情
                detail = self.client.get_alarm_detail(alarm.get('url', ''))
                
                # 保存已处理的预警
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        "INSERT OR IGNORE INTO processed_weather_alarms (alertid, title, issuetime) VALUES (?, ?, ?)",
                        (alertid, title, issuetime)
                    )
                    await db.commit()
                    
                # 发送预警给所有匹配的订阅者
                for group_id, user_id in matched_subscribers:
                    try:
                        # 构建预警消息
                        message, icon_path = await self.build_warning_message(alarm, detail, user_id, group_id)
                        
                        # 使用复合消息发送函数，在同一消息中发送文本和图片，并正确@用户
                        from message_sender import send_group_msg_with_text_and_image
                        success = await send_group_msg_with_text_and_image(group_id, message, icon_path, user_id)
                        
                        if success:
                            logging.info(f"成功发送预警消息到群 {group_id} @用户 {user_id}")
                        else:
                            logging.error(f"发送预警消息到群 {group_id} @用户 {user_id} 失败")
                        
                    except Exception as e:
                        logging.error(f"发送预警给群 {group_id} 用户 {user_id} 时出错: {e}")
                        
        except Exception as e:
            logging.error(f"检查气象预警时出错: {e}")
            
    async def build_warning_message(self, alarm: Dict, detail: Dict, user_id: str, group_id: str = None) -> tuple[str, Optional[str]]:
        """构建预警消息，返回(文本消息, 图标文件路径)"""
        title = alarm.get('title', '未知标题')
        issuetime = alarm.get('issuetime', '未知时间')
        pic_url = alarm.get('pic', '')
        alertid = alarm.get('alertid', '')
        url = f"https://www.nmc.cn{alarm.get('url', '')}"
        
        detail_content = detail.get('content', '暂无详情')
        # 不截断详细内容，完整显示所有信息
            
        message = f"[中国气象局气象预警]\n"
        message += f"| 预警标题: {title}\n"
        message += f"| 发布时间: {issuetime}\n"
        message += f"| 详细内容: {detail_content}\n"
        message += f"| 详细链接: {url}"
        
        # 下载并缓存图标
        icon_path = None
        if pic_url and group_id:
            icon_path = await self.download_and_cache_icon(pic_url, alertid)
            
        return message, icon_path
        
    async def start_periodic_check(self):
        """启动定期检查任务"""
        while True:
            try:
                await self.check_and_send_alarms()
                await asyncio.sleep(60)  # 每分钟检查一次是否到了检查时间
            except Exception as e:
                logging.error(f"定期检查任务出错: {e}")
                await asyncio.sleep(60)  # 出错后等待一分钟再继续


# 全局实例
subscriber_instance = None


async def init_cma_weather_subscriber(config: Dict):
    """初始化CMA气象预警订阅器"""
    global subscriber_instance
    if subscriber_instance is None:
        subscriber_instance = CMAWeatherSubscriber(config)
        await subscriber_instance.init_db()
        await subscriber_instance.load_subscriptions()
        
        # 启动定期检查任务
        asyncio.create_task(subscriber_instance.start_periodic_check())
        
        logging.info("CMA气象预警订阅器初始化完成")
        
    return subscriber_instance


def get_subscriber():
    """获取订阅器实例"""
    return subscriber_instance