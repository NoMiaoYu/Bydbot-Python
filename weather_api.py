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
    """格式化天气响应消息"""
    templates = config.get('weather_templates', {})
    template = templates.get(template_name, "")
    
    if not template:
        return f"天气信息模板 '{template_name}' 未找到，请检查配置"
    
    try:
        # 城市搜索
        if template_name == "城市搜索":
            locations = data.get('location', [])
            if not locations:
                return "未找到匹配的城市"
            
            location = locations[0]
            return template.format(
                name=location.get('name', 'N/A'),
                country=location.get('country', 'N/A'),
                adm1=location.get('adm1', 'N/A'),
                adm2=location.get('adm2', 'N/A'),
                id=location.get('id', 'N/A'),
                lon=location.get('lon', 'N/A'),
                lat=location.get('lat', 'N/A')
            )
        
        # 热门城市查询
        elif template_name == "热门城市查询":
            cities = data.get('top', [])
            if not cities:
                return "获取热门城市失败"
            
            city_list = []
            for city in cities[:20]:
                name = city.get('name', 'N/A')
                country = city.get('country', 'N/A')
                city_list.append(f"{name} ({country})")
            
            return template.format(city_list="\n".join(city_list))
        
        # POI搜索
        elif template_name == "POI搜索":
            pois = data.get('poi', [])
            if not pois:
                return "未找到匹配的POI"
            
            poi = pois[0]
            return template.format(
                name=poi.get('name', 'N/A'),
                type=poi.get('type', 'N/A'),
                address=poi.get('address', 'N/A'),
                lon=poi.get('lon', 'N/A'),
                lat=poi.get('lat', 'N/A'),
                id=poi.get('id', 'N/A')
            )
        
        # 实时天气
        elif template_name == "实时天气":
            now_data = data.get('now', {})
            location_data = data.get('location', [{}])[0] if data.get('location') else {}
            location_name = location_data.get('name', '未知地点')
            
            return template.format(
                location=location_name,
                temp=now_data.get('temp', 'N/A'),
                feelsLike=now_data.get('feelsLike', 'N/A'),
                text=now_data.get('text', 'N/A'),
                humidity=now_data.get('humidity', 'N/A'),
                windDir=now_data.get('windDir', 'N/A'),
                windScale=now_data.get('windScale', 'N/A'),
                windSpeed=now_data.get('windSpeed', 'N/A'),
                vis=now_data.get('vis', 'N/A'),
                pressure=now_data.get('pressure', 'N/A'),
                cloud=now_data.get('cloud', 'N/A'),
                obsTime=now_data.get('obsTime', 'N/A')
            )
        
        # 每日天气预报
        elif template_name.startswith("每日天气预报_"):
            location_data = data.get('location', [{}])[0] if data.get('location') else {}
            location_name = location_data.get('name', '未知地点')
            daily_data = data.get('daily', [])
            
            forecast_lines = []
            for day in daily_data:
                date = day.get('fxDate', '')
                temp_max = day.get('tempMax', 'N/A')
                temp_min = day.get('tempMin', 'N/A')
                text_day = day.get('textDay', 'N/A')
                text_night = day.get('textNight', 'N/A')
                wind_dir_day = day.get('windDirDay', 'N/A')
                wind_scale_day = day.get('windScaleDay', 'N/A')
                
                forecast_lines.append(f"{date}: {text_day}/{text_night} {temp_min}°C~{temp_max}°C {wind_dir_day}{wind_scale_day}级")
            
            daily_forecast = "\n".join(forecast_lines)
            
            return template.format(
                location=location_name,
                daily_forecast=daily_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        # 逐小时天气预报
        elif template_name.startswith("逐小时天气预报_"):
            location_data = data.get('location', [{}])[0] if data.get('location') else {}
            location_name = location_data.get('name', '未知地点')
            hourly_data = data.get('hourly', [])
            
            hourly_lines = []
            for hour in hourly_data[:24]:
                time = hour.get('fxTime', '').split('T')[1][:5] if 'T' in hour.get('fxTime', '') else hour.get('fxTime', '')
                temp = hour.get('temp', 'N/A')
                text = hour.get('text', 'N/A')
                humidity = hour.get('humidity', 'N/A')
                hourly_lines.append(f"{time}: {text} {temp}°C 湿度{humidity}%")
            
            hourly_forecast = "\n".join(hourly_lines)
            
            return template.format(
                location=location_name,
                hourly_forecast=hourly_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        # 格点实时天气
        elif template_name == "格点实时天气":
            now_data = data.get('now', {})
            return template.format(
                lon=now_data.get('lon', 'N/A'),
                lat=now_data.get('lat', 'N/A'),
                temp=now_data.get('temp', 'N/A'),
                feelsLike=now_data.get('feelsLike', 'N/A'),
                text=now_data.get('text', 'N/A'),
                humidity=now_data.get('humidity', 'N/A'),
                windDir=now_data.get('windDir', 'N/A'),
                windScale=now_data.get('windScale', 'N/A'),
                vis=now_data.get('vis', 'N/A'),
                obsTime=now_data.get('obsTime', 'N/A')
            )
        
        # 格点每日天气预报
        elif template_name.startswith("格点每日天气预报_"):
            daily_data = data.get('daily', [])
            if not daily_data:
                return "格点预报数据为空"
            
            first_day = daily_data[0]
            grid_daily_lines = []
            for day in daily_data:
                date = day.get('fxDate', '')
                temp_max = day.get('tempMax', 'N/A')
                temp_min = day.get('tempMin', 'N/A')
                text_day = day.get('textDay', 'N/A')
                grid_daily_lines.append(f"{date}: {text_day} {temp_min}°C~{temp_max}°C")
            
            grid_daily_forecast = "\n".join(grid_daily_lines)
            
            return template.format(
                lon=first_day.get('lon', 'N/A'),
                lat=first_day.get('lat', 'N/A'),
                grid_daily_forecast=grid_daily_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        # 格点逐小时天气预报
        elif template_name.startswith("格点逐小时天气预报_"):
            hourly_data = data.get('hourly', [])
            if not hourly_data:
                return "格点逐小时预报数据为空"
            
            first_hour = hourly_data[0]
            grid_hourly_lines = []
            for hour in hourly_data[:24]:
                time = hour.get('fxTime', '').split('T')[1][:5] if 'T' in hour.get('fxTime', '') else hour.get('fxTime', '')
                temp = hour.get('temp', 'N/A')
                text = hour.get('text', 'N/A')
                grid_hourly_lines.append(f"{time}: {text} {temp}°C")
            
            grid_hourly_forecast = "\n".join(grid_hourly_lines)
            
            return template.format(
                lon=first_hour.get('lon', 'N/A'),
                lat=first_hour.get('lat', 'N/A'),
                grid_hourly_forecast=grid_hourly_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        # 分钟级降水
        elif template_name == "分钟级降水":
            location_data = data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            minutely_data = data.get('minutely', [])
            
            if not minutely_data:
                return "分钟级降水数据为空"
            
            precipitation_lines = []
            for i, item in enumerate(minutely_data[:60]):  # 最多显示60分钟
                time = i + 1
                precip = item.get('precip', '0')
                precipitation_lines.append(f"{time}分钟后: {precip}mm")
            
            minutely_data_str = "\n".join(precipitation_lines)
            
            return template.format(
                location=location_name,
                minutely_data=minutely_data_str,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        # 实时天气预警
        elif template_name == "实时天气预警":
            alerts = data.get('alerts', [])
            if not alerts:
                return "当前无天气预警"
            
            alert = alerts[0]
            return template.format(
                headline=alert.get('headline', 'N/A'),
                eventType=alert.get('eventType', 'N/A'),
                severity=alert.get('severity', 'N/A'),
                effectiveTime=alert.get('effectiveTime', 'N/A'),
                expireTime=alert.get('expireTime', 'N/A'),
                description=alert.get('description', 'N/A'),
                instruction=alert.get('instruction', 'N/A'),
                sender=alert.get('sender', 'N/A')
            )
        
        # 天气指数预报
        elif template_name.startswith("天气指数预报_"):
            location_data = data.get('location', [{}])[0] if data.get('location') else {}
            location_name = location_data.get('name', '未知地点')
            indices_data = data.get('daily', [])
            
            if not indices_data:
                return "天气指数数据为空"
            
            indices_lines = []
            for index in indices_data:
                name = index.get('name', 'N/A')
                category = index.get('category', 'N/A')
                level = index.get('level', 'N/A')
                desc = index.get('desc', 'N/A')
                indices_lines.append(f"{name}: {category} (等级{level}) - {desc}")
            
            indices_data_str = "\n".join(indices_lines)
            
            return template.format(
                location=location_name,
                indices_data=indices_data_str,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        # 实时空气质量
        elif template_name == "实时空气质量":
            location_data = data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            air_data = data.get('current', {})
            
            return template.format(
                location=location_name,
                aqi=air_data.get('aqi', 'N/A'),
                category=air_data.get('category', 'N/A'),
                primaryPollutant=air_data.get('primaryPollutant', 'N/A'),
                pm2p5=air_data.get('pm2p5', 'N/A'),
                pm10=air_data.get('pm10', 'N/A'),
                so2=air_data.get('so2', 'N/A'),
                no2=air_data.get('no2', 'N/A'),
                co=air_data.get('co', 'N/A'),
                o3=air_data.get('o3', 'N/A'),
                pubTime=air_data.get('pubTime', 'N/A')
            )
        
        # 空气质量每日预报
        elif template_name == "空气质量每日预报":
            location_data = data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            daily_data = data.get('daily', [])
            
            if not daily_data:
                return "空气质量日预报数据为空"
            
            air_daily_lines = []
            for day in daily_data[:7]:
                date = day.get('fxDate', '')
                aqi = day.get('aqi', 'N/A')
                category = day.get('category', 'N/A')
                air_daily_lines.append(f"{date}: AQI {aqi} - {category}")
            
            air_daily_forecast = "\n".join(air_daily_lines)
            
            return template.format(
                location=location_name,
                air_daily_forecast=air_daily_forecast,
                updateTime=data.get('updateTime', 'N/A')
            )
        
        # 空气质量小时预报
        elif template_name == "空气质量小时预报":
            location_data = data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            hourly_data = data.get('hourly', [])
            
            if not hourly_data:
                return "空气质量小时预报数据为空"
            
            air_hourly_lines = []
            for hour in hourly_data[:24]:
                time = hour.get('fxTime', '').split('T')[1][:5] if 'T' in hour.get('fxTime', '') else hour.get('fxTime', '')
                aqi = hour.get('aqi', 'N/A')
                category = hour.get('category', 'N/A')
                air_hourly_lines.append(f"{time}: AQI {aqi} - {category}")
            
            air_hourly_forecast = "\n".join(air_hourly_lines)
            
            return template.format(
                location=location_name,
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