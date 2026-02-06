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
from typing import Dict, List, Set, Tuple
import aiosqlite
import os
import requests
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
            # 解析完整地区名称
            # 假设格式为 "省份+城市+区县" 如 "广东深圳南山"
            province = full_location[:2] if len(full_location) >= 2 else full_location
            city = full_location[2:4] if len(full_location) >= 4 else ""
            district = full_location[4:] if len(full_location) > 4 else ""
            
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
            
    async def get_user_subscriptions(self, user_id: str) -> List[Tuple[str, str]]:
        """获取用户的订阅列表 (province, group_id)"""
        subscriptions = []
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT province, group_id FROM weather_subscriptions WHERE user_id=?", 
                (user_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                subscriptions = [(province, group_id) for province, group_id in rows]
                
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
                for province in provinces_in_title:
                    if province in self.subscribers:
                        matched_subscribers.extend(self.subscribers[province])
                        
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
                        message = self.build_warning_message(alarm, detail, user_id)
                        
                        # 发送消息到群聊
                        success = await send_group_msg(group_id, message)
                        if success:
                            logging.info(f"成功发送预警到群 {group_id} @用户 {user_id}")
                        else:
                            logging.error(f"发送预警到群 {group_id} 失败")
                            
                    except Exception as e:
                        logging.error(f"发送预警给群 {group_id} 用户 {user_id} 时出错: {e}")
                        
        except Exception as e:
            logging.error(f"检查气象预警时出错: {e}")
            
    def build_warning_message(self, alarm: Dict, detail: Dict, user_id: str) -> str:
        """构建预警消息"""
        title = alarm.get('title', '未知标题')
        issuetime = alarm.get('issuetime', '未知时间')
        pic_url = alarm.get('pic', '')
        url = f"https://www.nmc.cn{alarm.get('url', '')}"
        
        detail_content = detail.get('content', '暂无详情')
        if len(detail_content) > 200:  # 截断过长的详情
            detail_content = detail_content[:200] + "..."
            
        message = f"@{user_id}\n"
        message += f"[中国气象局气象预警]\n"
        message += f"| 预警标题: {title}\n"
        message += f"| 发布时间: {issuetime}\n"
        message += f"| 详细内容: {detail_content}\n"
        message += f"| 详细链接: {url}\n"
        if pic_url:
            message += f"| 预警图标: {pic_url}"
            
        return message
        
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