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

    async def poi_lookup(self, location: str, type_param: str = "scenic", city: str = None, number: int = 10, lang: str = "zh") -> Optional[Dict[str, Any]]:
        """POI搜索"""
        params = {"location": location, "type": type_param, "number": number, "lang": lang}
        if city:
            params["city"] = city

        async with aiohttp.ClientSession() as session:
            return await self._make_request(session, "/geo/v2/poi/lookup", params)
    
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
    """
    格式化天气API响应数据
    :param template_name: 模板名称
    :param data: API响应数据
    :param config: 配置
    :return: 格式化后的消息字符串
    """
    try:
        # 获取语言设置（从data中提取或使用默认值）
        lang = "zh-hans"
        if isinstance(data, dict):
            # 尝试从请求参数中获取语言
            if 'lang' in data:
                lang = data['lang']
            elif template_name in ['实时天气', '每日天气预报', '逐小时天气预报'] and 'now' in data:
                # 从实时天气数据中可能包含的语言信息
                pass
        
        # 标准化数据
        standardized_data = standardize_weather_data(data, lang)
        
        # 获取模板
        templates = config.get('weather_templates', {})
        template = templates.get(template_name, '{data}')
        
        if template_name == "城市搜索":
            locations = standardized_data.get('location', [])
            if not locations:
                return "未找到匹配的城市"
            
            location = locations[0]
            return template.format(
                name=location.get('name', '未知'),
                country=location.get('country', '未知'),
                adm1=location.get('adm1', '未知'),
                adm2=location.get('adm2', '未知'),
                id=location.get('id', '未知'),
                lon=location.get('lon', '未知'),
                lat=location.get('lat', '未知')
            )
        
        elif template_name == "热门城市查询":
            locations = standardized_data.get('topCityList', [])
            if not locations:
                return "未获取到热门城市数据"
            
            city_lines = []
            for city in locations[:10]:  # 最多显示10个
                city_lines.append(f"- {city.get('name', '未知')} ({city.get('country', '未知')})")
            
            city_list = "\n".join(city_lines)
            return template.format(city_list=city_list)
        
        elif template_name == "POI搜索":
            pois = standardized_data.get('poi', [])
            if not pois:
                return "未找到匹配的POI"
            
            poi = pois[0]
            return template.format(
                name=poi.get('name', '未知'),
                type=poi.get('type', '未知'),
                address=poi.get('address', '未知'),
                lon=poi.get('lon', '未知'),
                lat=poi.get('lat', '未知'),
                id=poi.get('id', '未知')
            )
        
        elif template_name == "实时天气":
            now_data = standardized_data.get('now', {})
            location_data = standardized_data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            
            return template.format(
                location=location_name,
                temp=now_data.get('temp', 'N/A'),
                feelsLike=now_data.get('feelsLike', 'N/A'),
                text=now_data.get('weatherText', now_data.get('text', 'N/A')),
                humidity=now_data.get('humidity', 'N/A'),
                windDir=now_data.get('windDir', 'N/A'),
                windScale=now_data.get('windScale', 'N/A'),
                windSpeed=now_data.get('windSpeed', 'N/A'),
                vis=now_data.get('vis', 'N/A'),
                pressure=now_data.get('pressure', 'N/A'),
                cloud=now_data.get('cloud', 'N/A'),
                obsTime=standardized_data.get('updateTime', 'N/A')
            )
        
        elif template_name.startswith("每日天气预报_"):
            location_data = standardized_data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            daily_data = standardized_data.get('daily', [])
            
            if not daily_data:
                return "天气预报数据为空"
            
            daily_lines = []
            for day in daily_data:
                date = day.get('fxDate', 'N/A')
                temp_max = day.get('tempMax', 'N/A')
                temp_min = day.get('tempMin', 'N/A')
                text_day = day.get('textDay', 'N/A')
                text_night = day.get('textNight', 'N/A')
                wind_dir_day = day.get('windDirDay', 'N/A')
                wind_scale_day = day.get('windScaleDay', 'N/A')
                daily_lines.append(f"{date}: {temp_min}°C~{temp_max}°C {text_day}/{text_night} {wind_dir_day}{wind_scale_day}级")
            
            daily_forecast = "\n".join(daily_lines)
            
            # 提取天数
            days = template_name.split('_')[1]
            template_key = f"每日天气预报_{days}"
            actual_template = templates.get(template_key, template)
            
            return actual_template.format(
                location=location_name,
                daily_forecast=daily_forecast,
                updateTime=standardized_data.get('updateTime', 'N/A')
            )
        
        elif template_name.startswith("逐小时天气预报_"):
            location_data = standardized_data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            hourly_data = standardized_data.get('hourly', [])
            
            if not hourly_data:
                return "逐小时预报数据为空"
            
            hourly_lines = []
            for hour in hourly_data[:24]:
                time = hour.get('fxTime', '').split('T')[1][:5] if 'T' in hour.get('fxTime', '') else hour.get('fxTime', '')
                temp = hour.get('temp', 'N/A')
                text = hour.get('text', 'N/A')
                wind_scale = hour.get('windScale', 'N/A')
                hourly_lines.append(f"{time}: {temp}°C {text} {wind_scale}级")
            
            hourly_forecast = "\n".join(hourly_lines)
            
            # 提取小时数
            hours = template_name.split('_')[1]
            template_key = f"逐小时天气预报_{hours}"
            actual_template = templates.get(template_key, template)
            
            return actual_template.format(
                location=location_name,
                hourly_forecast=hourly_forecast,
                updateTime=standardized_data.get('updateTime', 'N/A')
            )
        
        elif template_name == "格点实时天气":
            now_data = standardized_data.get('now', {})
            
            return template.format(
                lon=now_data.get('lon', 'N/A'),
                lat=now_data.get('lat', 'N/A'),
                temp=now_data.get('temp', 'N/A'),
                feelsLike=now_data.get('feelsLike', 'N/A'),
                text=now_data.get('weatherText', now_data.get('text', 'N/A')),
                humidity=now_data.get('humidity', 'N/A'),
                windDir=now_data.get('windDir', 'N/A'),
                windScale=now_data.get('windScale', 'N/A'),
                vis=now_data.get('vis', 'N/A'),
                obsTime=standardized_data.get('updateTime', 'N/A')
            )
        
        elif template_name.startswith("格点每日天气预报_"):
            grid_daily_data = standardized_data.get('daily', [])
            
            if not grid_daily_data:
                return "格点预报数据为空"
            
            grid_daily_lines = []
            for day in grid_daily_data:
                date = day.get('fxDate', 'N/A')
                temp_max = day.get('tempMax', 'N/A')
                temp_min = day.get('tempMin', 'N/A')
                text_day = day.get('textDay', 'N/A')
                text_night = day.get('textNight', 'N/A')
                grid_daily_lines.append(f"{date}: {temp_min}°C~{temp_max}°C {text_day}/{text_night}")
            
            grid_daily_forecast = "\n".join(grid_daily_lines)
            
            # 提取天数
            days = template_name.split('_')[1]
            template_key = f"格点每日天气预报_{days}"
            actual_template = templates.get(template_key, template)
            
            return actual_template.format(
                lon=standardized_data.get('lon', 'N/A'),
                lat=standardized_data.get('lat', 'N/A'),
                grid_daily_forecast=grid_daily_forecast,
                updateTime=standardized_data.get('updateTime', 'N/A')
            )
        
        elif template_name.startswith("格点逐小时天气预报_"):
            grid_hourly_data = standardized_data.get('hourly', [])
            
            if not grid_hourly_data:
                return "格点逐小时预报数据为空"
            
            grid_hourly_lines = []
            for hour in grid_hourly_data[:24]:
                time = hour.get('fxTime', '').split('T')[1][:5] if 'T' in hour.get('fxTime', '') else hour.get('fxTime', '')
                temp = hour.get('temp', 'N/A')
                text = hour.get('text', 'N/A')
                grid_hourly_lines.append(f"{time}: {temp}°C {text}")
            
            grid_hourly_forecast = "\n".join(grid_hourly_lines)
            
            # 提取小时数
            hours = template_name.split('_')[1]
            template_key = f"格点逐小时天气预报_{hours}"
            actual_template = templates.get(template_key, template)
            
            return actual_template.format(
                lon=standardized_data.get('lon', 'N/A'),
                lat=standardized_data.get('lat', 'N/A'),
                grid_hourly_forecast=grid_hourly_forecast,
                updateTime=standardized_data.get('updateTime', 'N/A')
            )
        
        elif template_name == "分钟级降水":
            minutely_data = standardized_data.get('minutely', [])
            location_data = standardized_data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            
            if not minutely_data:
                return "分钟级降水数据为空"
            
            precip_lines = []
            for item in minutely_data[:12]:  # 显示前2小时（每10分钟一个点）
                time = item.get('time', 'N/A')
                precip = item.get('precip', 'N/A')
                precip_lines.append(f"{time}: {precip}mm")
            
            minutely_result = "\n".join(precip_lines)
            
            return template.format(
                location=location_name,
                minutely_data=minutely_result,
                updateTime=standardized_data.get('updateTime', 'N/A')
            )
        
        elif template_name == "实时天气预警":
            warning_data = standardized_data.get('warning', [])
            
            if not warning_data:
                return "当前无天气预警"
            
            warning = warning_data[0]  # 取第一个预警
            return template.format(
                headline=warning.get('headline', 'N/A'),
                eventType=warning.get('eventType', 'N/A'),
                severity=warning.get('severity', 'N/A'),
                effectiveTime=warning.get('effectiveTime', 'N/A'),
                expireTime=warning.get('expireTime', 'N/A'),
                description=warning.get('description', 'N/A'),
                instruction=warning.get('instruction', 'N/A'),
                sender=warning.get('sender', 'N/A')
            )
        
        elif template_name.startswith("天气指数预报_"):
            location_data = standardized_data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            indices_data = standardized_data.get('daily', [])
            
            if not indices_data:
                return "天气指数数据为空"
            
            indices_lines = []
            for day in indices_data:
                date = day.get('fxDate', 'N/A')
                index_items = day.get('index', [])
                for index_item in index_items[:5]:  # 显示前5个指数
                    name = index_item.get('name', 'N/A')
                    level = index_item.get('level', 'N/A')
                    category = index_item.get('category', 'N/A')
                    indices_lines.append(f"{name}: {category} ({level})")
                break  # 只显示第一天
            
            indices_result = "\n".join(indices_lines)
            
            # 提取天数
            days = template_name.split('_')[1]
            template_key = f"天气指数预报_{days}"
            actual_template = templates.get(template_key, template)
            
            return actual_template.format(
                location=location_name,
                indices_data=indices_result,
                updateTime=standardized_data.get('updateTime', 'N/A')
            )
        
        elif template_name == "实时空气质量":
            aqi_data = standardized_data.get('current', {})
            location_data = standardized_data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            
            return template.format(
                location=location_name,
                aqi=aqi_data.get('aqi', 'N/A'),
                category=aqi_data.get('aqiCategory', aqi_data.get('category', 'N/A')),
                primaryPollutant=aqi_data.get('primaryPollutant', 'N/A'),
                pm2p5=aqi_data.get('pm2p5', 'N/A'),
                pm10=aqi_data.get('pm10', 'N/A'),
                so2=aqi_data.get('so2', 'N/A'),
                no2=aqi_data.get('no2', 'N/A'),
                co=aqi_data.get('co', 'N/A'),
                o3=aqi_data.get('o3', 'N/A'),
                pubTime=standardized_data.get('pubTime', 'N/A')
            )
        
        elif template_name == "空气质量每日预报":
            location_data = standardized_data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            daily_data = standardized_data.get('daily', [])
            
            if not daily_data:
                return "空气质量日预报数据为空"
            
            air_daily_lines = []
            for day in daily_data[:7]:  # 显示7天
                date = day.get('fxDate', 'N/A')
                aqi = day.get('aqi', 'N/A')
                category = day.get('aqiCategory', day.get('category', 'N/A'))
                air_daily_lines.append(f"{date}: AQI {aqi} - {category}")
            
            air_daily_forecast = "\n".join(air_daily_lines)
            
            return template.format(
                location=location_name,
                air_daily_forecast=air_daily_forecast,
                updateTime=standardized_data.get('updateTime', 'N/A')
            )
        
        elif template_name == "空气质量小时预报":
            location_data = standardized_data.get('location', {})
            location_name = location_data.get('name', '未知地点')
            hourly_data = standardized_data.get('hourly', [])
            
            if not hourly_data:
                return "空气质量小时预报数据为空"
            
            air_hourly_lines = []
            for hour in hourly_data[:24]:
                time = hour.get('fxTime', '').split('T')[1][:5] if 'T' in hour.get('fxTime', '') else hour.get('fxTime', '')
                aqi = hour.get('aqi', 'N/A')
                category = hour.get('aqiCategory', hour.get('category', 'N/A'))
                air_hourly_lines.append(f"{time}: AQI {aqi} - {category}")
            
            air_hourly_forecast = "\n".join(air_hourly_lines)
            
            return template.format(
                location=location_name,
                air_hourly_forecast=air_hourly_forecast,
                updateTime=standardized_data.get('updateTime', 'N/A')
            )
        
        # 财务汇总
        elif template_name == "财务汇总":
            return template.format(
                totalRequests=standardized_data.get('totalRequests', 'N/A'),
                freeQuota=standardized_data.get('freeQuota', 'N/A'),
                overQuota=standardized_data.get('overQuota', 'N/A'),
                billingStatus=standardized_data.get('billingStatus', 'N/A'),
                nextBillingDate=standardized_data.get('nextBillingDate', 'N/A')
            )
        
        # 请求量统计
        elif template_name == "请求量统计":
            return template.format(
                project=standardized_data.get('project', 'N/A'),
                credential=standardized_data.get('credential', 'N/A'),
                totalRequests=standardized_data.get('totalRequests', 'N/A'),
                todayRequests=standardized_data.get('todayRequests', 'N/A'),
                monthRequests=standardized_data.get('monthRequests', 'N/A'),
                lastUpdateTime=standardized_data.get('lastUpdateTime', 'N/A')
            )
        
        else:
            # 默认格式化，直接返回原始数据的字符串表示
            return json.dumps(standardized_data, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logging.error(f"格式化天气响应失败: {e}")
        return f"天气信息格式化错误: {str(e)}"


def standardize_weather_data(data: Dict[str, Any], lang: str = "zh-hans") -> Dict[str, Any]:
    """
    标准化天气数据，将API返回的原始数据转换为用户友好的标准化格式
    根据提供的特殊文档进行字段值替换和标准化
    """
    if not data:
        return data
    
    # 深拷贝避免修改原始数据
    standardized = {}
    for key, value in data.items():
        if isinstance(value, dict):
            standardized[key] = standardize_weather_data(value, lang)
        elif isinstance(value, list):
            standardized[key] = [standardize_weather_data(item, lang) if isinstance(item, dict) else item for item in value]
        else:
            standardized[key] = value
    
    # 处理风力等级标准化
    if 'windScale' in standardized:
        try:
            wind_scale = int(standardized['windScale'])
            wind_level_text = get_wind_level_text(wind_scale, lang)
            standardized['windScaleText'] = wind_level_text
        except (ValueError, TypeError):
            pass
    
    # 处理天气状况文本标准化
    if 'text' in standardized:
        weather_text = standardized['text']
        icon_code = standardized.get('icon', '')
        standardized['weatherText'] = get_standardized_weather_text(weather_text, icon_code, lang)
    
    # 处理空气质量标准化
    if 'aqi' in standardized and 'category' in standardized:
        aqi = standardized.get('aqi', 'N/A')
        category = standardized.get('category', 'N/A')
        standardized['aqiCategory'] = get_standardized_aqi_category(aqi, category, lang)
    
    # 处理天气指数标准化
    if 'level' in standardized and 'name' in standardized:
        level = standardized.get('level', 'N/A')
        index_name = standardized.get('name', '')
        standardized['indexLevelText'] = get_standardized_index_level(index_name, level, lang)
    
    return standardized


def get_wind_level_text(wind_scale: int, lang: str = "zh-hans") -> str:
    """获取风力等级文本描述"""
    wind_levels_zh = {
        0: "无风", 1: "软风", 2: "轻风", 3: "微风", 4: "和风",
        5: "清风", 6: "强风", 7: "疾风", 8: "大风", 9: "烈风",
        10: "狂风", 11: "暴风", 12: "飓风", 13: "台风", 14: "强台风",
        15: "强台风", 16: "超强台风", 17: "超强台风"
    }
    
    wind_levels_en = {
        0: "Calm", 1: "Light air", 2: "Light breeze", 3: "Gentle breeze", 4: "Moderate breeze",
        5: "Fresh breeze", 6: "Strong breeze", 7: "Near gale", 8: "Gale", 9: "Strong gale",
        10: "Storm", 11: "Violent storm", 12: "Hurricane", 13: "TY", 14: "STY",
        15: "STY", 16: "SuperTY", 17: "SuperTY"
    }
    
    if lang.startswith("zh"):
        return wind_levels_zh.get(wind_scale, f"{wind_scale}级")
    else:
        return wind_levels_en.get(wind_scale, f"Level {wind_scale}")


def get_standardized_weather_text(weather_text: str, icon_code: str, lang: str = "zh-hans") -> str:
    """获取标准化的天气状况文本"""
    # 根据图标代码和语言返回标准化天气文本
    # 这里简化处理，实际可以根据完整的图标代码表进行映射
    if lang.startswith("zh"):
        weather_mapping = {
            "100": "晴", "101": "多云", "102": "少云", "103": "晴间多云", "104": "阴",
            "150": "晴", "151": "多云", "152": "少云", "153": "晴间多云",
            "300": "阵雨", "301": "强阵雨", "302": "雷阵雨", "303": "强雷阵雨",
            "304": "雷阵雨伴有冰雹", "305": "小雨", "306": "中雨", "307": "大雨",
            "308": "极端降雨", "309": "毛毛雨/细雨", "310": "暴雨", "311": "大暴雨",
            "312": "特大暴雨", "313": "冻雨", "314": "小到中雨", "315": "中到大雨",
            "316": "大到暴雨", "317": "暴雨到大暴雨", "318": "大暴雨到特大暴雨",
            "399": "雨", "400": "小雪", "401": "中雪", "402": "大雪", "403": "暴雪",
            "404": "雨夹雪", "405": "雨雪天气", "406": "阵雨夹雪", "407": "阵雪",
            "408": "小到中雪", "409": "中到大雪", "410": "大到暴雪", "499": "雪",
            "500": "薄雾", "501": "雾", "502": "霾", "503": "扬沙", "504": "浮尘",
            "507": "沙尘暴", "508": "强沙尘暴", "509": "浓雾", "510": "强浓雾",
            "511": "中度霾", "512": "重度霾", "513": "严重霾", "514": "大雾",
            "515": "特强浓雾", "900": "热", "901": "冷", "999": "未知"
        }
        return weather_mapping.get(icon_code, weather_text)
    else:
        # 英文或其他语言保持原样或简单映射
        return weather_text


def get_standardized_aqi_category(aqi: str, category: str, lang: str = "zh-hans") -> str:
    """获取标准化的空气质量等级描述"""
    if lang.startswith("zh"):
        aqi_categories = {
            "1": "优", "2": "良", "3": "轻度污染", "4": "中度污染",
            "5": "重度污染", "6": "严重污染"
        }
        # 尝试从AQI数值推断等级
        try:
            aqi_num = int(aqi)
            if aqi_num <= 50:
                return "优"
            elif aqi_num <= 100:
                return "良"
            elif aqi_num <= 150:
                return "轻度污染"
            elif aqi_num <= 200:
                return "中度污染"
            elif aqi_num <= 300:
                return "重度污染"
            else:
                return "严重污染"
        except (ValueError, TypeError):
            return aqi_categories.get(category, category)
    else:
        return category


def get_standardized_index_level(index_name: str, level: str, lang: str = "zh-hans") -> str:
    """获取标准化的天气指数等级描述"""
    if lang.startswith("zh"):
        index_levels = {
            "运动指数": {"1": "适宜", "2": "较适宜", "3": "较不宜"},
            "洗车指数": {"1": "适宜", "2": "较适宜", "3": "较不宜", "4": "不宜"},
            "穿衣指数": {"1": "寒冷", "2": "冷", "3": "较冷", "4": "较舒适", "5": "舒适", "6": "热", "7": "炎热"},
            "钓鱼指数": {"1": "适宜", "2": "较适宜", "3": "不宜"},
            "紫外线指数": {"1": "最弱", "2": "弱", "3": "中等", "4": "强", "5": "很强"},
            "旅游指数": {"1": "适宜", "2": "较适宜", "3": "一般", "4": "较不宜", "5": "不适宜"},
            "花粉过敏指数": {"1": "极不易发", "2": "不易发", "3": "较易发", "4": "易发", "5": "极易发"},
            "舒适度指数": {"1": "舒适", "2": "较舒适", "3": "较不舒适", "4": "很不舒适", "5": "极不舒适", "6": "不舒适", "7": "非常不舒适"},
            "感冒指数": {"1": "少发", "2": "较易发", "3": "易发", "4": "极易发"},
            "空气污染扩散条件指数": {"1": "优", "2": "良", "3": "中", "4": "较差", "5": "很差"},
            "空调开启指数": {"1": "长时间开启", "2": "部分时间开启", "3": "较少开启", "4": "开启制暖空调"},
            "太阳镜指数": {"1": "不需要", "2": "需要", "3": "必要", "4": "很必要", "5": "非常必要"},
            "化妆指数": {"1": "保湿", "2": "保湿防晒", "3": "去油防晒", "4": "防脱水防晒", "5": "去油", "6": "防脱水", "7": "防晒", "8": "滋润保湿"},
            "晾晒指数": {"1": "极适宜", "2": "适宜", "3": "基本适宜", "4": "不太适宜", "5": "不宜", "6": "不适宜"},
            "交通指数": {"1": "良好", "2": "较好", "3": "一般", "4": "较差", "5": "很差"},
            "防晒指数": {"1": "弱", "2": "较弱", "3": "中等", "4": "强", "5": "极强"}
        }
        
        index_map = index_levels.get(index_name, {})
        return index_map.get(level, level)
    else:
        return level


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