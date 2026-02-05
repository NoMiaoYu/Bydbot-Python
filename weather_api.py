"""
Bydbot - 和风天气API处理模块
支持免费版所有可用的API端点
"""

import aiohttp
import json
import logging
from typing import Dict, Any, Optional
import asyncio
from datetime import datetime, timedelta

# 缓存字典
_weather_cache = {}

class QWeatherAPI:
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('qweather', {})
        self.api_host = self.config.get('api_host', 'devapi.qweather.com')
        self.api_key = self.config.get('api_key', '')
        self.jwt_token = self.config.get('jwt_token', '')
        self.use_jwt = self.config.get('use_jwt', False)
        self.cache_enabled = self.config.get('cache_enabled', True)
        self.cache_ttl = self.config.get('cache_ttl', 600)  # 默认10分钟
        
        if not self.api_host or not (self.api_key or (self.use_jwt and self.jwt_token)):
            logging.warning("和风天气API配置不完整，请在config.json中配置api_host和api_key或jwt_token")
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {'Accept-Encoding': 'gzip'}
        if self.use_jwt:
            headers['Authorization'] = f'Bearer {self.jwt_token}'
        else:
            headers['X-QW-Api-Key'] = self.api_key
        return headers
    
    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        return f"{endpoint}?{param_str}"
    
    def _is_cache_valid(self, cache_time: datetime) -> bool:
        """检查缓存是否有效"""
        return datetime.now() - cache_time < timedelta(seconds=self.cache_ttl)
    
    async def _make_request(self, session: aiohttp.ClientSession, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """发送API请求"""
        try:
            url = f"https://{self.api_host}{endpoint}"
            headers = self._get_headers()
            
            # 检查缓存
            if self.cache_enabled:
                cache_key = self._get_cache_key(endpoint, params)
                if cache_key in _weather_cache:
                    cached_data, cache_time = _weather_cache[cache_key]
                    if self._is_cache_valid(cache_time):
                        logging.info(f"使用缓存数据: {cache_key}")
                        return cached_data
            
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    # 存储到缓存
                    if self.cache_enabled:
                        cache_key = self._get_cache_key(endpoint, params)
                        _weather_cache[cache_key] = (data, datetime.now())
                    return data
                else:
                    error_text = await response.text()
                    logging.error(f"API请求失败 {url}: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logging.error(f"API请求异常 {endpoint}: {e}")
            return None
    
    async def geo_lookup(self, location: str, adm: str = None, range: str = None, number: int = 10, lang: str = "zh") -> Optional[Dict[str, Any]]:
        """城市搜索"""
        params = {"location": location, "number": number, "lang": lang}
        if adm:
            params["adm"] = adm
        if range:
            params["range"] = range
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "/geo/v2/city/lookup", params)
    
    async def geo_top(self, range: str = None, number: int = 10, lang: str = "zh") -> Optional[Dict[str, Any]]:
        """热门城市查询"""
        params = {"number": number, "lang": lang}
        if range:
            params["range"] = range
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "/geo/v2/city/top", params)
    
    async def weather_now(self, location: str, lang: str = "zh", unit: str = "m") -> Optional[Dict[str, Any]]:
        """实时天气"""
        params = {"location": location, "lang": lang, "unit": unit}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "/v7/weather/now", params)
    
    async def weather_forecast(self, days: str, location: str, lang: str = "zh", unit: str = "m") -> Optional[Dict[str, Any]]:
        """每日天气预报"""
        valid_days = ["3d", "7d", "10d", "15d", "30d"]
        if days not in valid_days:
            days = "3d"
        
        params = {"location": location, "lang": lang, "unit": unit}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, f"/v7/weather/{days}", params)
    
    async def weather_hourly(self, hours: str, location: str, lang: str = "zh", unit: str = "m") -> Optional[Dict[str, Any]]:
        """逐小时天气预报"""
        valid_hours = ["24h", "72h", "168h"]
        if hours not in valid_hours:
            hours = "24h"
        
        params = {"location": location, "lang": lang, "unit": unit}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, f"/v7/weather/{hours}", params)
    
    async def grid_weather_now(self, location: str, lang: str = "zh", unit: str = "m") -> Optional[Dict[str, Any]]:
        """格点实时天气"""
        params = {"location": location, "lang": lang, "unit": unit}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "/v7/grid-weather/now", params)
    
    async def grid_weather_forecast(self, days: str, location: str, lang: str = "zh", unit: str = "m") -> Optional[Dict[str, Any]]:
        """格点每日天气预报"""
        valid_days = ["3d", "7d"]
        if days not in valid_days:
            days = "3d"
        
        params = {"location": location, "lang": lang, "unit": unit}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, f"/v7/grid-weather/{days}", params)
    
    async def grid_weather_hourly(self, hours: str, location: str, lang: str = "zh", unit: str = "m") -> Optional[Dict[str, Any]]:
        """格点逐小时天气预报"""
        valid_hours = ["24h", "72h", "168h"]
        if hours not in valid_hours:
            hours = "24h"
        
        params = {"location": location, "lang": lang, "unit": unit}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, f"/v7/grid-weather/{hours}", params)
    
    async def minutely_precipitation(self, location: str, lang: str = "zh") -> Optional[Dict[str, Any]]:
        """分钟级降水"""
        params = {"location": location, "lang": lang}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "/v7/minutely/5m", params)
    
    async def weather_alert(self, latitude: float, longitude: float, localTime: bool = False, lang: str = "zh") -> Optional[Dict[str, Any]]:
        """实时天气预警"""
        params = {"localTime": str(localTime).lower(), "lang": lang}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, f"/weatheralert/v1/current/{latitude}/{longitude}", params)
    
    async def weather_indices(self, type: str, location: str, days: str = "1d", lang: str = "zh") -> Optional[Dict[str, Any]]:
        """天气指数预报"""
        valid_days = ["1d", "3d"]
        if days not in valid_days:
            days = "1d"
        
        params = {"location": location, "type": type, "lang": lang}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, f"/v7/indices/{days}", params)
    
    async def air_quality_current(self, latitude: float, longitude: float, lang: str = "zh") -> Optional[Dict[str, Any]]:
        """实时空气质量"""
        params = {"lang": lang}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, f"/airquality/v1/current/{latitude}/{longitude}", params)
    
    async def air_quality_daily(self, latitude: float, longitude: float, localTime: bool = False, lang: str = "zh") -> Optional[Dict[str, Any]]:
        """空气质量每日预报"""
        params = {"localTime": str(localTime).lower(), "lang": lang}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, f"/airquality/v1/daily/{latitude}/{longitude}", params)
    
    async def air_quality_hourly(self, latitude: float, longitude: float, localTime: bool = False, lang: str = "zh") -> Optional[Dict[str, Any]]:
        """空气质量小时预报"""
        params = {"localTime": str(localTime).lower(), "lang": lang}
        
        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, f"/airquality/v1/hourly/{latitude}/{longitude}", params)

def format_weather_response(template_name: str, data: Dict[str, Any], config: Dict[str, Any]) -> str:
    """格式化天气API响应数据"""
    try:
        # 获取天气模板配置
        weather_templates = config.get('weather_templates', {})
        template = weather_templates.get(template_name, "{data}")
        
        # 根据模板名称进行不同的格式化处理
        if template_name == "城市搜索":
            location_data = data.get('location', [])
            if not location_data:
                return "未找到匹配的城市"
            
            locations = []
            for loc in location_data[:10]:  # 最多显示10个结果
                # 坐标系统处理
                lon = loc.get('lon', 'N/A')
                lat = loc.get('lat', 'N/A')
                
                # 行政区划处理
                country = loc.get('country', 'N/A')
                adm1 = loc.get('adm1', 'N/A')  # 一级行政区划
                adm2 = loc.get('adm2', 'N/A')  # 次级行政区划
                
                # LocationID处理
                loc_id = loc.get('id', 'N/A')
                
                # Rank值处理（如果存在）
                rank = loc.get('rank', 'N/A')
                
                locations.append(template.format(
                    name=loc.get('name', 'N/A'),
                    country=country,
                    adm1=adm1,
                    adm2=adm2,
                    id=loc_id,
                    lon=lon,
                    lat=lat,
                    rank=rank
                ))
            
            return "\n\n".join(locations)
        
        elif template_name == "热门城市查询":
            location_data = data.get('location', [])
            if not location_data:
                return "未找到热门城市"
            
            cities = []
            for loc in location_data[:10]:
                city_info = f"地点: {loc.get('name', 'N/A')}\n国家: {loc.get('country', 'N/A')}\nLocationID: {loc.get('id', 'N/A')}\n经度: {loc.get('lon', 'N/A')}\n纬度: {loc.get('lat', 'N/A')}"
                cities.append(city_info)
            
            city_list = "\n---\n".join(cities)
            return template.format(city_list=city_list)
        
        elif template_name == "POI搜索":
            poi_data = data.get('poi', [])
            if not poi_data:
                return "未找到匹配的POI"
            
            pois = []
            for poi in poi_data[:10]:
                # POI类型映射
                poi_type = poi.get('type', 'N/A')
                type_mapping = {
                    'scenic': '景点',
                    'TSTA': '潮汐站点', 
                    'city': '城市',
                    'airport': '机场',
                    'port': '港口',
                    'railway': '火车站',
                    'aqi': '空气质量监测站'
                }
                display_type = type_mapping.get(poi_type, poi_type)
                
                pois.append(template.format(
                    name=poi.get('name', 'N/A'),
                    type=display_type,
                    address=poi.get('address', 'N/A'),
                    lon=poi.get('lon', 'N/A'),
                    lat=poi.get('lat', 'N/A'),
                    id=poi.get('id', 'N/A')
                ))
            
            return "\n\n".join(pois)
        
        elif template_name == "实时天气":
            now_data = data.get('now', {})
            location_data = data.get('location', {})
            
            # 多语言处理
            text = now_data.get('text', 'N/A')
            wind_dir = now_data.get('windDir', 'N/A')
            
            # 风向方位映射（支持8位和16位）
            wind_direction_map = {
                'N': '北风', 'NE': '东北风', 'E': '东风', 'SE': '东南风',
                'S': '南风', 'SW': '西南风', 'W': '西风', 'NW': '西北风',
                'NNE': '东北偏北风', 'ENE': '东北偏东风', 'ESE': '东南偏东风',
                'SSE': '东南偏南风', 'SSW': '西南偏南风', 'WSW': '西南偏西风',
                'WNW': '西北偏西风', 'NNW': '西北偏北风',
                'Rotational': '旋转风', 'None': '无持续风向'
            }
            display_wind_dir = wind_direction_map.get(wind_dir, wind_dir)
            
            # 风力等级处理
            wind_scale = now_data.get('windScale', 'N/A')
            if wind_scale == '0':
                display_wind_dir = '无持续风向'
            
            # 单位系统处理
            temp = now_data.get('temp', 'N/A')
            feels_like = now_data.get('feelsLike', 'N/A')
            wind_speed = now_data.get('windSpeed', 'N/A')
            vis = now_data.get('vis', 'N/A')
            pressure = now_data.get('pressure', 'N/A')
            
            return template.format(
                location=location_data.get('name', 'N/A'),
                temp=temp,
                feelsLike=feels_like,
                text=text,
                humidity=now_data.get('humidity', 'N/A'),
                windDir=display_wind_dir,
                windScale=wind_scale,
                windSpeed=wind_speed,
                vis=vis,
                pressure=pressure,
                cloud=now_data.get('cloud', 'N/A'),
                obsTime=now_data.get('obsTime', 'N/A')
            )
        
        elif template_name.startswith("每日天气预报_"):
            days = template_name.split('_')[1]
            daily_data = data.get('daily', [])
            location_data = data.get('location', {})
            
            if not daily_data:
                return f"{days}天天气预报数据为空"
            
            daily_lines = []
            for day in daily_data:
                date = day.get('fxDate', 'N/A')
                temp_max = day.get('tempMax', 'N/A')
                temp_min = day.get('tempMin', 'N/A')
                text_day = day.get('textDay', 'N/A')
                text_night = day.get('textNight', 'N/A')
                wind_dir_day = day.get('windDirDay', 'N/A')
                wind_scale_day = day.get('windScaleDay', 'N/A')
                humidity = day.get('humidity', 'N/A')
                
                # 天气图标处理
                icon_day = day.get('iconDay', 'N/A')
                icon_night = day.get('iconNight', 'N/A')
                
                daily_line = f"{date}: {text_day}转{text_night} {temp_min}°C~{temp_max}°C 风向:{wind_dir_day} 风力:{wind_scale_day}级 湿度:{humidity}%"
                daily_lines.append(daily_line)
            
            daily_forecast = "\n".join(daily_lines)
            
            return template.format(
                location=location_data.get('name', 'N/A'),
                daily_forecast=daily_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        elif template_name.startswith("逐小时天气预报_"):
            hours = template_name.split('_')[1]
            hourly_data = data.get('hourly', [])
            location_data = data.get('location', {})
            
            if not hourly_data:
                return f"{hours}小时逐小时预报数据为空"
            
            hourly_lines = []
            for hour in hourly_data[:24]:
                time = hour.get('fxTime', '').split('T')[1][:5] if 'T' in hour.get('fxTime', '') else hour.get('fxTime', '')
                temp = hour.get('temp', 'N/A')
                text = hour.get('text', 'N/A')
                wind_dir = hour.get('windDir', 'N/A')
                wind_scale = hour.get('windScale', 'N/A')
                humidity = hour.get('humidity', 'N/A')
                
                hourly_line = f"{time}: {text} {temp}°C 风向:{wind_dir} 风力:{wind_scale}级 湿度:{humidity}%"
                hourly_lines.append(hourly_line)
            
            hourly_forecast = "\n".join(hourly_lines)
            
            return template.format(
                location=location_data.get('name', 'N/A'),
                hourly_forecast=hourly_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        elif template_name == "格点实时天气":
            now_data = data.get('now', {})
            
            # 坐标系统处理
            lon = data.get('lon', 'N/A')
            lat = data.get('lat', 'N/A')
            
            # 风向处理
            wind_dir = now_data.get('windDir', 'N/A')
            wind_direction_map = {
                'N': '北风', 'NE': '东北风', 'E': '东风', 'SE': '东南风',
                'S': '南风', 'SW': '西南风', 'W': '西风', 'NW': '西北风'
            }
            display_wind_dir = wind_direction_map.get(wind_dir, wind_dir)
            
            return template.format(
                lon=lon,
                lat=lat,
                temp=now_data.get('temp', 'N/A'),
                feelsLike=now_data.get('feelsLike', 'N/A'),
                text=now_data.get('text', 'N/A'),
                humidity=now_data.get('humidity', 'N/A'),
                windDir=display_wind_dir,
                windScale=now_data.get('windScale', 'N/A'),
                vis=now_data.get('vis', 'N/A'),
                obsTime=now_data.get('obsTime', 'N/A')
            )
        
        elif template_name.startswith("格点每日天气预报_"):
            days = template_name.split('_')[1]
            daily_data = data.get('daily', [])
            
            if not daily_data:
                return f"格点{days}天预报数据为空"
            
            grid_daily_lines = []
            for day in daily_data:
                date = day.get('fxDate', 'N/A')
                temp_max = day.get('tempMax', 'N/A')
                temp_min = day.get('tempMin', 'N/A')
                text_day = day.get('textDay', 'N/A')
                text_night = day.get('textNight', 'N/A')
                wind_dir_day = day.get('windDirDay', 'N/A')
                wind_scale_day = day.get('windScaleDay', 'N/A')
                
                grid_line = f"{date}: {text_day}转{text_night} {temp_min}°C~{temp_max}°C 风向:{wind_dir_day} 风力:{wind_scale_day}级"
                grid_daily_lines.append(grid_line)
            
            grid_daily_forecast = "\n".join(grid_daily_lines)
            
            return template.format(
                lon=data.get('lon', 'N/A'),
                lat=data.get('lat', 'N/A'),
                grid_daily_forecast=grid_daily_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        elif template_name.startswith("格点逐小时天气预报_"):
            hours = template_name.split('_')[1]
            hourly_data = data.get('hourly', [])
            
            if not hourly_data:
                return f"格点{hours}小时预报数据为空"
            
            grid_hourly_lines = []
            for hour in hourly_data[:24]:
                time = hour.get('fxTime', '').split('T')[1][:5] if 'T' in hour.get('fxTime', '') else hour.get('fxTime', '')
                temp = hour.get('temp', 'N/A')
                text = hour.get('text', 'N/A')
                wind_dir = hour.get('windDir', 'N/A')
                wind_scale = hour.get('windScale', 'N/A')
                
                grid_line = f"{time}: {text} {temp}°C 风向:{wind_dir} 风力:{wind_scale}级"
                grid_hourly_lines.append(grid_line)
            
            grid_hourly_forecast = "\n".join(grid_hourly_lines)
            
            return template.format(
                lon=data.get('lon', 'N/A'),
                lat=data.get('lat', 'N/A'),
                grid_hourly_forecast=grid_hourly_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        elif template_name == "分钟级降水":
            minutely_data = data.get('minutely', [])
            location_data = data.get('location', {})
            
            if not minutely_data:
                return "分钟级降水预报数据为空"
            
            precip_lines = []
            for precip in minutely_data[:60]:  # 最多60分钟
                time = precip.get('fxTime', '').split('T')[1][:5] if 'T' in precip.get('fxTime', '') else precip.get('fxTime', '')
                precip_value = precip.get('precip', 'N/A')
                precip_lines.append(f"{time}: {precip_value}mm")
            
            minutely_data_str = "\n".join(precip_lines)
            
            return template.format(
                location=location_data.get('name', 'N/A'),
                minutely_data=minutely_data_str,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        elif template_name == "实时天气预警":
            warning_data = data.get('warning', [])
            
            if not warning_data:
                return "当前无天气预警"
            
            # 取第一个预警（最新）
            warning = warning_data[0]
            
            # 紧迫程度映射
            urgency_map = {
                'immediate': '必须立刻采取行动',
                'expected': '应尽快采取行动',
                'future': '应在近期采取行动',
                'past': '事件已不再发生',
                'unknown': '紧迫性未知'
            }
            
            # 严重程度映射
            severity_map = {
                'unknown': '严重性未知',
                'minor': '对生命或财产构成的威胁极小',
                'moderate': '对生命或财产可能构成威胁',
                'severe': '对生命或财产构成的重大威胁',
                'extreme': '对生命或财产构成的严重威胁'
            }
            
            # 确定性映射
            certainty_map = {
                'observed': '事件已经发生或正在发生',
                'likely': '发生概率大于约50%',
                'possible': '有可能发生，但概率较低',
                'unlikely': '预计不会发生',
                'unknown': '确定性未知'
            }
            
            # 颜色映射
            color_map = {
                'white': '白色',
                'gray': '灰色',
                'green': '绿色',
                'blue': '蓝色',
                'yellow': '黄色',
                'amber': '琥珀色',
                'orange': '橙色',
                'red': '红色',
                'purple': '紫色',
                'black': '黑色'
            }
            
            return template.format(
                headline=warning.get('headline', 'N/A'),
                eventType=warning.get('eventType', 'N/A'),
                severity=severity_map.get(warning.get('severity', 'unknown'), warning.get('severity', 'N/A')),
                effectiveTime=warning.get('effectiveTime', 'N/A'),
                expireTime=warning.get('expireTime', 'N/A'),
                description=warning.get('description', 'N/A'),
                instruction=warning.get('instruction', 'N/A'),
                sender=warning.get('sender', 'N/A')
            )
        
        elif template_name.startswith("天气指数预报_"):
            days = template_name.split('_')[1]
            indices_data = data.get('daily', [])
            location_data = data.get('location', {})
            
            if not indices_data:
                return f"{days}天天气指数数据为空"
            
            # 天气指数类型映射
            index_type_map = {
                '1': '运动指数', '2': '洗车指数', '3': '穿衣指数', '4': '钓鱼指数',
                '5': '紫外线指数', '6': '旅游指数', '7': '花粉过敏指数', '8': '舒适度指数',
                '9': '感冒指数', '10': '空气污染扩散条件指数', '11': '空调开启指数',
                '12': '太阳镜指数', '13': '化妆指数', '14': '晾晒指数', '15': '交通指数',
                '16': '防晒指数'
            }
            
            # 指数等级映射
            def get_index_level(index_type, level):
                level_map = {
                    '1': {'1': '适宜', '2': '较适宜', '3': '较不宜'},
                    '2': {'1': '适宜', '2': '较适宜', '3': '较不宜', '4': '不宜'},
                    '3': {'1': '寒冷', '2': '冷', '3': '较冷', '4': '较舒适', '5': '舒适', '6': '热', '7': '炎热'},
                    '4': {'1': '适宜', '2': '较适宜', '3': '不宜'},
                    '5': {'1': '最弱', '2': '弱', '3': '中等', '4': '强', '5': '很强'},
                    '6': {'1': '适宜', '2': '较适宜', '3': '一般', '4': '较不宜', '5': '不适宜'},
                    '7': {'1': '极不易发', '2': '不易发', '3': '较易发', '4': '易发', '5': '极易发'},
                    '8': {'1': '舒适', '2': '较舒适', '3': '较不舒适', '4': '很不舒适', '5': '极不舒适', '6': '不舒适', '7': '非常不舒适'},
                    '9': {'1': '少发', '2': '较易发', '3': '易发', '4': '极易发'},
                    '10': {'1': '优', '2': '良', '3': '中', '4': '较差', '5': '很差'},
                    '11': {'1': '长时间开启', '2': '部分时间开启', '3': '较少开启', '4': '开启制暖空调'},
                    '12': {'1': '不需要', '2': '需要', '3': '必要', '4': '很必要', '5': '非常必要'},
                    '13': {'1': '保湿', '2': '保湿防晒', '3': '去油防晒', '4': '防脱水防晒', '5': '去油', '6': '防脱水', '7': '防晒', '8': '滋润保湿'},
                    '14': {'1': '极适宜', '2': '适宜', '3': '基本适宜', '4': '不太适宜', '5': '不宜', '6': '不适宜'},
                    '15': {'1': '良好', '2': '较好', '3': '一般', '4': '较差', '5': '很差'},
                    '16': {'1': '弱', '2': '较弱', '3': '中等', '4': '强', '5': '极强'}
                }
                return level_map.get(index_type, {}).get(str(level), str(level))
            
            indices_lines = []
            for day in indices_data:
                date = day.get('fxDate', 'N/A')
                index_info = []
                for idx in day.get('index', []):
                    index_type = idx.get('type', 'N/A')
                    index_level = idx.get('level', 'N/A')
                    index_name = index_type_map.get(index_type, f'指数{index_type}')
                    level_name = get_index_level(index_type, index_level)
                    index_desc = idx.get('desc', 'N/A')
                    index_info.append(f"{index_name}: {level_name} - {index_desc}")
                indices_lines.append(f"{date}:\n" + "\n".join(index_info))
            
            indices_data_str = "\n\n".join(indices_lines)
            
            return template.format(
                location=location_data.get('name', 'N/A'),
                indices_data=indices_data_str,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        elif template_name == "实时空气质量":
            air_data = data.get('current', {})
            location_data = data.get('location', {})
            
            # AQI类型映射
            aqi_type_map = {
                'cn-mee': '中国环境部标准',
                'us-epa': '美国EPA标准',
                'eu-eea': '欧洲环境署标准',
                'qaqi': '通用AQI标准'
            }
            
            # 空气质量等级映射
            category_map = {
                '1': '优', '2': '良', '3': '轻度污染', '4': '中度污染',
                '5': '重度污染', '6': '严重污染'
            }
            
            # 首要污染物映射
            pollutant_map = {
                'pm2p5': 'PM2.5', 'pm10': 'PM10', 'so2': '二氧化硫',
                'no2': '二氧化氮', 'co': '一氧化碳', 'o3': '臭氧'
            }
            
            aqi_display = air_data.get('aqi', 'N/A')
            aqi_category = air_data.get('category', 'N/A')
            primary_pollutant = air_data.get('primaryPollutant', 'N/A')
            
            # 转换首要污染物显示
            display_primary_pollutant = pollutant_map.get(primary_pollutant, primary_pollutant)
            
            return template.format(
                location=location_data.get('name', 'N/A'),
                aqi=aqi_display,
                category=category_map.get(aqi_category, aqi_category),
                primaryPollutant=display_primary_pollutant,
                pm2p5=air_data.get('pm2p5', 'N/A'),
                pm10=air_data.get('pm10', 'N/A'),
                so2=air_data.get('so2', 'N/A'),
                no2=air_data.get('no2', 'N/A'),
                co=air_data.get('co', 'N/A'),
                o3=air_data.get('o3', 'N/A'),
                pubTime=air_data.get('pubTime', 'N/A')
            )
        
        elif template_name == "空气质量每日预报":
            daily_data = data.get('daily', [])
            location_data = data.get('location', {})
            
            if not daily_data:
                return "空气质量日预报数据为空"
            
            air_daily_lines = []
            for day in daily_data:
                date = day.get('fxDate', 'N/A')
                aqi = day.get('aqi', 'N/A')
                category = day.get('category', 'N/A')
                primary_pollutant = day.get('primaryPollutant', 'N/A')
                
                # 空气质量等级映射
                category_map = {
                    '1': '优', '2': '良', '3': '轻度污染', '4': '中度污染',
                    '5': '重度污染', '6': '严重污染'
                }
                display_category = category_map.get(category, category)
                
                air_daily_lines.append(f"{date}: AQI {aqi} - {display_category}")
            
            air_daily_forecast = "\n".join(air_daily_lines)
            
            return template.format(
                location=location_data.get('name', 'N/A'),
                air_daily_forecast=air_daily_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        elif template_name == "空气质量小时预报":
            hourly_data = data.get('hourly', [])
            location_data = data.get('location', {})
            
            if not hourly_data:
                return "空气质量小时预报数据为空"
            
            air_hourly_lines = []
            for hour in hourly_data[:24]:
                time = hour.get('fxTime', '').split('T')[1][:5] if 'T' in hour.get('fxTime', '') else hour.get('fxTime', '')
                aqi = hour.get('aqi', 'N/A')
                category = hour.get('category', 'N/A')
                
                # 空气质量等级映射
                category_map = {
                    '1': '优', '2': '良', '3': '轻度污染', '4': '中度污染',
                    '5': '重度污染', '6': '严重污染'
                }
                display_category = category_map.get(category, category)
                
                air_hourly_lines.append(f"{time}: AQI {aqi} - {display_category}")
            
            air_hourly_forecast = "\n".join(air_hourly_lines)
            
            return template.format(
                location=location_data.get('name', 'N/A'),
                air_hourly_forecast=air_hourly_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        # 财务汇总
        elif template_name == "财务汇总":
            return template.format(
                totalRequests=data.get('totalRequests', 'N/A'),
                freeQuota=data.get('freeQuota', 'N/A'),
                overQuota=data.get('overQuota', 'N/A'),
                billingStatus=data.get('billingStatus', 'N/A'),
                nextBillingDate=data.get('nextBillingDate', 'N/A')
            )
        
        # 请求量统计
        elif template_name == "请求量统计":
            return template.format(
                project=data.get('project', 'N/A'),
                credential=data.get('credential', 'N/A'),
                totalRequests=data.get('totalRequests', 'N/A'),
                todayRequests=data.get('todayRequests', 'N/A'),
                monthRequests=data.get('monthRequests', 'N/A'),
                lastUpdateTime=data.get('lastUpdateTime', 'N/A')
            )
        
        else:
            # 默认格式化，直接返回原始数据的字符串表示
            return json.dumps(data, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logging.error(f"格式化天气响应失败: {e}")
        return f"天气信息格式化错误: {str(e)}"

async def test_qweather_api(config: Dict[str, Any]):
    """测试和风天气API"""
    api = QWeatherAPI(config)
    
    # 测试实时天气（北京）
    result = await api.weather_now("101010100")
    if result:
        logging.info(f"实时天气测试成功: {result.get('now', {}).get('temp', 'N/A')}°C")
    else:
        logging.error("实时天气测试失败")
    
    # 测试城市搜索
    result = await api.geo_lookup("北京")
    if result:
        logging.info(f"城市搜索测试成功: 找到 {len(result.get('location', []))} 个结果")
    else:
        logging.error("城市搜索测试失败")