"""
Bydbot - UAPI客户端
支持UAPI所有可用的API端点
"""

import aiohttp
import json
import logging
from typing import Dict, Any, Optional
import asyncio
from datetime import datetime, timedelta


class UApiClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config.get('uapi', {})
        self.base_url = self.config.get('base_url', 'https://uapis.cn')
        self.api_key = self.config.get('api_key', '')
        self.timeout = self.config.get('timeout', 30)
        
        if not self.base_url:
            logging.warning("UAPI配置不完整，请在config.json中配置base_url")

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {'Accept-Encoding': 'gzip'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers

    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, 
                           json_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """发送API请求"""
        try:
            url = f"{self.base_url}/api/v1{endpoint}"
            headers = self._get_headers()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                if method.upper() == 'GET':
                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            logging.error(f"UAPI GET请求失败 {url}: {response.status} - {error_text}")
                            return None
                elif method.upper() == 'POST':
                    async with session.post(url, params=params, json=json_data, headers=headers) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            logging.error(f"UAPI POST请求失败 {url}: {response.status} - {error_text}")
                            return None
        except Exception as e:
            logging.error(f"UAPI请求异常 {endpoint}: {e}")
            return None

    async def _make_request_with_fallback(self, endpoint: str, get_params: Optional[Dict[str, Any]] = None, 
                                         post_json: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        优先使用POST请求，如果POST失败则使用GET请求
        如果两个都失败，则通知主人
        """
        # 首先尝试POST请求
        if post_json is not None:
            result = await self._make_request('POST', endpoint, json_data=post_json)
            if result is not None:
                return result
            logging.warning(f"POST请求失败，尝试GET请求: {endpoint}")
        
        # 如果POST失败或没有POST数据，尝试GET请求
        if get_params is not None:
            result = await self._make_request('GET', endpoint, params=get_params)
            if result is not None:
                return result
            logging.error(f"GET请求也失败: {endpoint}")
        
        # 如果两个都失败，通知主人
        logging.error(f"POST和GET请求都失败: {endpoint}，请检查网络连接或API状态")
        return None

    # 社交类 API
    async def get_bilibili_liveroom(self, mid: str = None, room_id: str = None) -> Optional[Dict[str, Any]]:
        """查询B站直播间"""
        params = {}
        if mid:
            params['mid'] = mid
        if room_id:
            params['room_id'] = room_id
        
        if not params:
            return None
            
        return await self._make_request('GET', '/social/bilibili/liveroom', params)

    async def get_bilibili_userinfo(self, uid: str) -> Optional[Dict[str, Any]]:
        """查询B站用户信息"""
        params = {'uid': uid}
        return await self._make_request('GET', '/social/bilibili/userinfo', params)

    async def get_bilibili_archives(self, mid: str, keywords: str = "", orderby: str = "pubdate", 
                                    ps: str = "20", pn: str = "1") -> Optional[Dict[str, Any]]:
        """查询B站投稿"""
        params = {
            'mid': mid,
            'keywords': keywords,
            'orderby': orderby,
            'ps': ps,
            'pn': pn
        }
        return await self._make_request('GET', '/social/bilibili/archives', params)

    async def get_github_repo(self, repo: str) -> Optional[Dict[str, Any]]:
        """查询GitHub仓库"""
        params = {'repo': repo}
        return await self._make_request('GET', '/github/repo', params)

    # 杂项类 API
    async def get_hotboard(self, type_param: str) -> Optional[Dict[str, Any]]:
        """查询热榜"""
        params = {'type': type_param}
        return await self._make_request('GET', '/misc/hotboard', params)

    async def get_worldtime(self, city: str) -> Optional[Dict[str, Any]]:
        """查询世界时间"""
        params = {'city': city}
        return await self._make_request('GET', '/misc/worldtime', params)

    async def get_weather(self, city: str = None, adcode: str = None, extended: bool = False, 
                          indices: bool = False, forecast: bool = False) -> Optional[Dict[str, Any]]:
        """查询天气"""
        params = {}
        if city:
            params['city'] = city
        if adcode:
            params['adcode'] = adcode
        if extended:
            params['extended'] = 'true'
        if indices:
            params['indices'] = 'true'
        if forecast:
            params['forecast'] = 'true'
        
        return await self._make_request('GET', '/misc/weather', params)

    async def get_phoneinfo(self, phone: str) -> Optional[Dict[str, Any]]:
        """查询手机归属地"""
        params = {'phone': phone}
        return await self._make_request('GET', '/misc/phoneinfo', params)

    async def get_randomnumber(self, min_val: int = 1, max_val: int = 100, count: int = 1, 
                               allow_repeat: bool = False, allow_decimal: bool = False, 
                               decimal_places: int = 2) -> Optional[Dict[str, Any]]:
        """随机数生成"""
        params = {
            'min': min_val,
            'max': max_val,
            'count': count,
            'allow_repeat': str(allow_repeat).lower(),
            'allow_decimal': str(allow_decimal).lower(),
            'decimal_places': decimal_places
        }
        return await self._make_request('GET', '/misc/randomnumber', params)

    async def get_history_programmer_today(self) -> Optional[Dict[str, Any]]:
        """程序员历史上的今天"""
        return await self._make_request('GET', '/history/programmer/today')

    async def get_history_programmer(self, month: int, day: int) -> Optional[Dict[str, Any]]:
        """指定日期程序员历史事件"""
        params = {'month': month, 'day': day}
        return await self._make_request('GET', '/history/programmer', params)

    # 网络类 API
    async def get_icp(self, domain: str) -> Optional[Dict[str, Any]]:
        """查询域名ICP备案信息"""
        params = {'domain': domain}
        return await self._make_request('GET', '/network/icp', params)

    async def get_ipinfo(self, ip: str, source: str = None) -> Optional[Dict[str, Any]]:
        """查询IP地理位置"""
        params = {'ip': ip}
        if source:
            params['source'] = source
        return await self._make_request('GET', '/network/ipinfo', params)

    async def get_whois(self, domain: str, format_param: str = "text") -> Optional[Dict[str, Any]]:
        """查询域名的WHOIS注册信息"""
        params = {'domain': domain, 'format': format_param}
        return await self._make_request('GET', '/network/whois', params)

    async def get_ping(self, host: str) -> Optional[Dict[str, Any]]:
        """Ping主机"""
        params = {'host': host}
        return await self._make_request('GET', '/network/ping', params)

    async def get_dns(self, domain: str, type_param: str = "A") -> Optional[Dict[str, Any]]:
        """执行DNS解析查询"""
        params = {'domain': domain, 'type': type_param}
        return await self._make_request('GET', '/network/dns', params)

    async def get_urlstatus(self, url: str) -> Optional[Dict[str, Any]]:
        """检查URL的可访问性状态"""
        params = {'url': url}
        return await self._make_request('GET', '/network/urlstatus', params)

    async def get_portscan(self, host: str, port: int, protocol: str = "tcp") -> Optional[Dict[str, Any]]:
        """端口扫描"""
        params = {'host': host, 'port': port, 'protocol': protocol}
        return await self._make_request('GET', '/network/portscan', params)

    # 游戏类 API
    async def get_minecraft_serverstatus(self, server: str) -> Optional[Dict[str, Any]]:
        """查询MC服务器"""
        params = {'server': server}
        return await self._make_request('GET', '/game/minecraft/serverstatus', params)

    async def get_steam_summary(self, steamid: str = None, id_param: str = None, id3: str = None, 
                                key: str = None) -> Optional[Dict[str, Any]]:
        """查询Steam用户"""
        params = {}
        if steamid:
            params['steamid'] = steamid
        if id_param:
            params['id'] = id_param
        if id3:
            params['id3'] = id3
        if key:
            params['key'] = key
        
        return await self._make_request('GET', '/game/steam/summary', params)

    async def get_epic_free(self) -> Optional[Dict[str, Any]]:
        """Epic免费游戏"""
        return await self._make_request('GET', '/game/epic-free')

    async def get_minecraft_userinfo(self, username: str) -> Optional[Dict[str, Any]]:
        """查询MC玩家"""
        params = {'username': username}
        return await self._make_request('GET', '/game/minecraft/userinfo', params)

    async def get_minecraft_historyid(self, name: str = None, uuid: str = None) -> Optional[Dict[str, Any]]:
        """查询MC曾用名"""
        params = {}
        if name:
            params['name'] = name
        if uuid:
            params['uuid'] = uuid
        
        return await self._make_request('GET', '/game/minecraft/historyid', params)

    # 文本类 API
    async def post_text_analyze(self, text: str) -> Optional[Dict[str, Any]]:
        """文本分析"""
        json_data = {'text': text}
        return await self._make_request('POST', '/text/analyze', json_data=json_data)

    async def get_text_md5(self, text: str) -> Optional[Dict[str, Any]]:
        """MD5哈希 - 优先使用POST方法，如果失败则使用GET方法"""
        params = {'text': text}
        json_data = {'text': text}
        return await self._make_request_with_fallback('/text/md5', get_params=params, post_json=json_data)

    async def post_text_md5_verify(self, text: str, hash_val: str) -> Optional[Dict[str, Any]]:
        """MD5校验"""
        json_data = {'text': text, 'hash': hash_val}
        return await self._make_request('POST', '/text/md5/verify', json_data=json_data)

    async def post_text_base64_encode(self, text: str) -> Optional[Dict[str, Any]]:
        """Base64编码"""
        json_data = {'text': text}
        return await self._make_request('POST', '/text/base64/encode', json_data=json_data)

    async def post_text_base64_decode(self, text: str) -> Optional[Dict[str, Any]]:
        """Base64解码"""
        json_data = {'text': text}
        return await self._make_request('POST', '/text/base64/decode', json_data=json_data)

    async def post_text_aes_encrypt(self, key: str, text: str) -> Optional[Dict[str, Any]]:
        """AES加密"""
        json_data = {'key': key, 'text': text}
        return await self._make_request('POST', '/text/aes/encrypt', json_data=json_data)

    async def post_text_aes_decrypt(self, key: str, text: str, nonce: str) -> Optional[Dict[str, Any]]:
        """AES解密"""
        json_data = {'key': key, 'text': text, 'nonce': nonce}
        return await self._make_request('POST', '/text/aes/decrypt', json_data=json_data)

    async def post_text_aes_encrypt_advanced(self, text: str, key: str, mode: str = "GCM", 
                                            padding: str = "PKCS7", iv: str = None, 
                                            output_format: str = "base64") -> Optional[Dict[str, Any]]:
        """AES高级加密"""
        json_data = {
            'text': text,
            'key': key,
            'mode': mode,
            'padding': padding,
            'output_format': output_format
        }
        if iv:
            json_data['iv'] = iv
        return await self._make_request('POST', '/text/aes/encrypt-advanced', json_data=json_data)

    async def post_text_aes_decrypt_advanced(self, text: str, key: str, mode: str = "GCM", 
                                            padding: str = "NONE", iv: str = None) -> Optional[Dict[str, Any]]:
        """AES高级解密"""
        json_data = {
            'text': text,
            'key': key,
            'mode': mode,
            'padding': padding
        }
        if iv:
            json_data['iv'] = iv
        return await self._make_request('POST', '/text/aes/decrypt-advanced', json_data=json_data)

    async def post_text_convert(self, text: str, from_format: str, to_format: str, 
                                options: Dict[str, Any] = {}) -> Optional[Dict[str, Any]]:
        """格式转换"""
        json_data = {
            'text': text,
            'from': from_format,
            'to': to_format,
            'options': options
        }
        return await self._make_request('POST', '/text/convert', json_data=json_data)

    # 随机类 API
    async def get_random_image(self, category: str = None, type_param: str = None) -> Optional[bytes]:
        """随机图片"""
        params = {}
        if category:
            params['category'] = category
        if type_param:
            params['type'] = type_param
        
        try:
            url = f"{self.base_url}/api/v1/random/image"
            if params:
                import urllib.parse
                query_string = urllib.parse.urlencode(params)
                url = f"{url}?{query_string}"
                
            headers = self._get_headers()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()  # 返回二进制图片数据
                    else:
                        error_text = await response.text()
                        logging.error(f"UAPI随机图片请求失败 {url}: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logging.error(f"UAPI随机图片请求异常: {e}")
            return None

    async def get_answerbook_ask(self, question: str) -> Optional[Dict[str, Any]]:
        """答案之书 - 优先使用POST方法，如果失败则使用GET方法"""
        params = {'question': question}
        json_data = {'question': question}
        return await self._make_request_with_fallback('/answerbook/ask', get_params=params, post_json=json_data)

    async def get_random_string(self, length: int = 16, type_param: str = "alphanumeric") -> Optional[Dict[str, Any]]:
        """随机字符串生成"""
        params = {'length': length, 'type': type_param}
        return await self._make_request('GET', '/random/string', params)

    # 图像类 API
    async def get_bing_daily(self) -> Optional[bytes]:
        """必应壁纸"""
        try:
            url = f"{self.base_url}/api/v1/image/bing-daily"
            headers = self._get_headers()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()  # 返回二进制图片数据
                    else:
                        error_text = await response.text()
                        logging.error(f"UAPI必应壁纸请求失败 {url}: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logging.error(f"UAPI必应壁纸请求异常: {e}")
            return None

    async def post_image_frombase64(self, image_data: str) -> Optional[Dict[str, Any]]:
        """通过Base64编码上传图片"""
        json_data = {'imageData': image_data}
        return await self._make_request('POST', '/image/frombase64', json_data=json_data)

    async def get_image_tobase64(self, url: str) -> Optional[Dict[str, Any]]:
        """图片转Base64"""
        params = {'url': url}
        return await self._make_request('GET', '/image/tobase64', params)

    async def get_image_qrcode(self, text: str, size: int = 256, format_param: str = "image", 
                               transparent: bool = False, fgcolor: str = "#000000", 
                               bgcolor: str = "#FFFFFF") -> Optional[bytes]:
        """生成二维码"""
        params = {
            'text': text,
            'size': size,
            'format': format_param,
            'transparent': str(transparent).lower(),
            'fgcolor': fgcolor,
            'bgcolor': bgcolor
        }
        
        try:
            import urllib.parse
            url = f"{self.base_url}/api/v1/image/qrcode"
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"
            
            headers = self._get_headers()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()  # 返回二进制图片数据
                    else:
                        error_text = await response.text()
                        logging.error(f"UAPI二维码请求失败 {url}: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logging.error(f"UAPI二维码请求异常: {e}")
            return None

    async def get_avatar_gravatar(self, email: str = None, hash_val: str = None, s: int = 80, 
                                  d: str = "mp", r: str = "g") -> Optional[bytes]:
        """获取GrAvatar头像"""
        params = {'s': s, 'd': d, 'r': r}
        if email:
            params['email'] = email
        if hash_val:
            params['hash'] = hash_val
        
        try:
            import urllib.parse
            url = f"{self.base_url}/api/v1/avatar/gravatar"
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"
            
            headers = self._get_headers()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()  # 返回二进制图片数据
                    else:
                        error_text = await response.text()
                        logging.error(f"UAPI GrAvatar请求失败 {url}: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logging.error(f"UAPI GrAvatar请求异常: {e}")
            return None

    async def get_image_motou(self, qq: str, bg_color: str = "transparent") -> Optional[bytes]:
        """生成摸摸头GIF (QQ号)"""
        params = {'qq': qq, 'bg_color': bg_color}
        
        try:
            import urllib.parse
            url = f"{self.base_url}/api/v1/image/motou"
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"
            
            headers = self._get_headers()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()  # 返回二进制图片数据
                    else:
                        error_text = await response.text()
                        logging.error(f"UAPI摸摸头GIF请求失败 {url}: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logging.error(f"UAPI摸摸头GIF请求异常: {e}")
            return None

    async def post_image_motou(self, image_url: str = None, bg_color: str = "transparent") -> Optional[bytes]:
        """生成摸摸头GIF (POST版本，通过图片URL)"""
        try:
            import aiohttp
            from aiohttp import FormData

            url = f"{self.base_url}/api/v1/image/motou"
            headers = self._get_headers()

            # 创建表单数据
            form_data = FormData()
            if image_url:
                form_data.add_field('image_url', image_url)
            form_data.add_field('bg_color', bg_color)

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(url, data=form_data, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()  # 返回二进制图片数据
                    else:
                        error_text = await response.text()
                        logging.error(f"UAPI摸摸头GIF POST请求失败 {url}: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logging.error(f"UAPI摸摸头GIF POST请求异常: {e}")
            return None

    # 图片压缩、SVG转换等功能也需要特殊的文件上传处理

    # 翻译类 API
    async def post_translate_text(self, to_lang: str, text: str) -> Optional[Dict[str, Any]]:
        """翻译"""
        json_data = {'text': text}
        params = {'to_lang': to_lang}
        return await self._make_request('POST', '/translate/text', params=params, json_data=json_data)

    # 诗词类 API
    async def get_saying(self) -> Optional[Dict[str, Any]]:
        """一言"""
        return await self._make_request('GET', '/saying')

    # 网页解析类 API
    async def get_webparse_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """提取网页元数据"""
        params = {'url': url}
        return await self._make_request('GET', '/webparse/metadata', params)

    async def get_webparse_extractimages(self, url: str) -> Optional[Dict[str, Any]]:
        """提取网页图片"""
        params = {'url': url}
        return await self._make_request('GET', '/webparse/extractimages', params)

    # 转换类 API
    async def get_convert_unixtime(self, time_param: str) -> Optional[Dict[str, Any]]:
        """时间戳转换"""
        params = {'time': time_param}
        return await self._make_request('GET', '/convert/unixtime', params)

    async def post_convert_json(self, content: str) -> Optional[Dict[str, Any]]:
        """JSON格式化"""
        json_data = {'content': content}
        return await self._make_request('POST', '/convert/json', json_data=json_data)

    # 日常类 API
    async def get_daily_news_image(self) -> Optional[bytes]:
        """每日新闻图"""
        try:
            url = f"{self.base_url}/api/v1/daily/news-image"
            headers = self._get_headers()
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()  # 返回二进制图片数据
                    else:
                        error_text = await response.text()
                        logging.error(f"UAPI每日新闻图请求失败 {url}: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logging.error(f"UAPI每日新闻图请求异常: {e}")
            return None

    # 图像类 API - 补充缺失的API端点
    async def post_image_compress(self, file_path: str, level: int = 3, format_param: str = "png") -> Optional[bytes]:
        """无损压缩图片"""
        try:
            import aiohttp
            from aiohttp import FormData
            
            url = f"{self.base_url}/api/v1/image/compress"
            headers = self._get_headers()
            
            # 创建表单数据
            form_data = FormData()
            with open(file_path, 'rb') as f:
                form_data.add_field('file', f, filename='image.jpg', content_type='image/jpeg')
            form_data.add_field('level', str(level))
            form_data.add_field('format', format_param)
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(url, data=form_data, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()  # 返回二进制图片数据
                    else:
                        error_text = await response.text()
                        logging.error(f"UAPI图片压缩请求失败 {url}: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logging.error(f"UAPI图片压缩请求异常: {e}")
            return None

    async def post_image_speechless(self, top_text: str, bottom_text: str) -> Optional[bytes]:
        """生成你们怎么不说话了表情包"""
        try:
            url = f"{self.base_url}/api/v1/image/speechless"
            headers = self._get_headers()
            headers['Content-Type'] = 'application/json'
            
            json_data = {
                'top_text': top_text,
                'bottom_text': bottom_text
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(url, json=json_data, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()  # 返回二进制图片数据
                    else:
                        error_text = await response.text()
                        logging.error(f"UAPI表情包生成请求失败 {url}: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logging.error(f"UAPI表情包生成请求异常: {e}")
            return None

    async def post_image_svg(self, file_path: str, format_param: str = "png", width: int = None, 
                             height: int = None, quality: int = 90) -> Optional[bytes]:
        """SVG转图片"""
        try:
            import aiohttp
            from aiohttp import FormData
            
            url = f"{self.base_url}/api/v1/image/svg"
            headers = self._get_headers()
            
            # 创建表单数据
            form_data = FormData()
            with open(file_path, 'rb') as f:
                form_data.add_field('file', f, filename='image.svg', content_type='image/svg+xml')
            
            # 添加查询参数
            params = {'format': format_param, 'quality': str(quality)}
            if width:
                params['width'] = str(width)
            if height:
                params['height'] = str(height)
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(url, data=form_data, params=params, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()  # 返回二进制图片数据
                    else:
                        error_text = await response.text()
                        logging.error(f"UAPI SVG转图片请求失败 {url}: {response.status} - {error_text}")
                        return None
        except Exception as e:
            logging.error(f"UAPI SVG转图片请求异常: {e}")
            return None


async def test_uapi_client(config: Dict[str, Any]):
    """测试UAPI客户端"""
    client = UApiClient(config)

    # 测试一言功能
    result = await client.get_saying()
    if result:
        logging.info(f"UAPI一言测试成功: {result.get('text', 'N/A')}")
    else:
        logging.error("UAPI一言测试失败")

    # 测试世界时间
    result = await client.get_worldtime(city="Asia/Shanghai")
    if result:
        logging.info(f"UAPI世界时间测试成功: {result.get('datetime', 'N/A')}")
    else:
        logging.error("UAPI世界时间测试失败")

    # 测试热榜
    result = await client.get_hotboard(type_param="weibo")
    if result:
        logging.info(f"UAPI热榜测试成功: {result.get('type', 'N/A')}")
    else:
        logging.error("UAPI热榜测试失败")