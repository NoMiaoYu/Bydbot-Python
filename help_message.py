"""
Bydbot - 帮助消息模块
提供帮助信息的获取功能
"""

import os
from typing import Dict, Any


def get_help_message(config: Dict[str, Any] = None) -> str:
    """获取帮助信息"""
    # 检查配置中的帮助设置
    if config:
        help_config = config.get('help', {})
        # 如果配置了help且启用了文字模式
        if help_config and help_config.get('text_enabled', False):
            # 返回简化的UAPI帮助
            return get_uapi_help_message()
    
    # 从文件读取帮助信息
    try:
        help_file_path = os.path.join(os.path.dirname(__file__), 'help命令.txt')
        with open(help_file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # 如果文件不存在，返回默认帮助信息
        help_text = """=== Bydbot 帮助菜单 ===
    
 earthquak earthquake bot
  bydbot v2.0 - 多功能信息推送机器人
  
【地震信息】
• 自动推送全球地震信息（根据配置过滤）
• 支持多种数据源（CENC, CEA, JMA, USGS等）
• 实时地震地图绘制与推送

【天气信息】
• /天气统计 - 查看API使用统计
• /天气开关 [开启/关闭] - 控制天气API（仅主人）

【天气查询】
• /城市搜索 [城市名] - 搜索城市信息
• /热门城市查询 - 查询热门城市
• /POI搜索 [地点] [类型] - 搜索兴趣点
• /实时天气 [location] - 查询实时天气
• /每日天气预报 [天数] [location] - 查询天气预报
• /逐小时天气预报 [小时数] [location] - 查询小时预报
• /分钟级降水 [location] - 查询降水预报
• /实时天气预警 [lat] [lon] - 查询天气预警
• /实时空气质量 [lat] [lon] - 查询空气质量

【UAPI功能】
• /B站直播间查询 [mid/room_id] [ID] - 查询B站直播间
• /B站用户查询 [UID] - 查询B站用户信息
• /B站投稿查询 [mid] - 查询B站用户投稿
• /GitHub仓库查询 [owner] [repo] - 查询GitHub仓库
• /热榜查询 [type] - 查询各平台热榜
• /世界时间查询 [city] - 查询世界时间
• /天气查询 [city] - 查询天气（UAPI）
• /手机归属地查询 [phone] - 查询手机号归属地
• /随机数生成 [min] [max] [count] - 生成随机数
• /ICP备案查询 [domain] - 查询域名ICP备案
• /IP信息查询 [ip] - 查询IP地理位置
• /一言 - 获取一句优美的话

【气象预警订阅】
• /订阅预警 [省份] - 订阅某省气象预警
• /取消订阅预警 [省份] - 取消订阅某省预警
• /我的订阅 - 查看个人订阅列表

【系统命令】
• /bydbottest - 运行测试命令
• /broadcast 或 /群发 - 进入广播模式（仅主人）

【数据源说明】
• 当前支持30+个地震数据源
• 可配置黑白名单过滤规则
• 支持多种预警类型（地震、海啸、气象等）

注：[...]表示必填参数，(...)表示选填参数
更多帮助请查看具体命令后加-h或-help
"""
        return help_text


def get_uapi_help_message() -> str:
    """获取UAPI帮助信息"""
    return """=== UAPI 帮助菜单 ===
    
Bydbot v2.0 - UAPI功能模块

【社交类 API】
• /B站直播间查询 [mid/room_id] [ID] - 查询B站直播间
• /B站用户查询 [UID] - 查询B站用户信息  
• /B站投稿查询 [mid] [关键词] [排序] [每页数量] [页码] - 查询B站用户投稿
• /GitHub仓库查询 [owner/repo] - 查询GitHub仓库

【杂项类 API】
• /热榜查询 [type] - 查询各平台热榜（支持weibo, zhihu, baidu, toutiao等）
• /世界时间查询 [city] - 查询世界时间（使用IANA时区格式，如Asia/Shanghai）
• /天气查询 [city] [adcode] [extended] [indices] [forecast] - 查询天气
• /手机归属地查询 [phone] - 查询手机号归属地
• /随机数生成 [min] [max] [count] [allow_repeat] [allow_decimal] [decimal_places] - 生成随机数
• /程序员历史上的今天 - 获取今日程序员历史事件
• /程序员历史事件 [month] [day] - 查询指定日期程序员历史事件

【网络类 API】
• /ICP备案查询 [domain] - 查询域名ICP备案信息
• /IP信息查询 [ip/domain] [source] - 查询IP地理位置和运营商
• /WHOIS查询 [domain] [format] - 查询域名WHOIS注册信息
• /Ping主机 [host] - 网络连通性Ping测试
• /DNS查询 [domain] [type] - DNS记录查询（A, AAAA, CNAME, MX, NS, TXT）
• /URL可访问性 [url] - 检查URL可访问性状态
• /端口扫描 [host] [port] [protocol] - 端口开放状态检测

【游戏类 API】
• /MC服务器查询 [server] - 查询Minecraft服务器状态
• /Steam用户查询 [steamid/id/id3] [key] - 查询Steam用户资料
• /Epic免费游戏 - 获取Epic商店当前免费游戏
• /MC玩家查询 [username] - 查询Minecraft玩家信息
• /MC曾用名查询 [name/uuid] - 查询Minecraft玩家历史用户名

【文本类 API】
• /文本分析 [text] - 文本字符数、词数、句子数统计
• /MD5哈希 [text] - 计算文本MD5哈希值
• /MD5校验 [text] [hash] - 校验文本MD5哈希值
• /Base64编码 [text] - 文本Base64编码
• /Base64解码 [text] - Base64解码为文本
• /AES加密 [key] [text] - AES标准加密
• /AES解密 [key] [text] [nonce] - AES标准解密
• /AES高级加密 [text] [key] [mode] [padding] [iv] [output_format] - 高级AES加密
• /AES高级解密 [text] [key] [mode] [padding] [iv] - 高级AES解密
• /格式转换 [text] [from] [to] - 支持7种双向格式和4种单向哈希转换

【随机类 API】
• /随机图片 [category] [type] - 获取随机图片（acg, landscape, anime等）
• /答案之书 [question] - 获取神秘答案（GET/POST版本）
• /随机字符串 [length] [type] - 生成随机字符串（numeric, lower, upper, alpha, alphanumeric, hex）

【图像类 API】
• /必应壁纸 - 获取Bing每日壁纸
• /上传图片 [base64_data] - 上传Base64图片获取公开URL
• /图片转Base64 [url] - 将图片URL转换为Base64 Data URI
• /生成二维码 [text] [size] [format] [transparent] [fgcolor] [bgcolor] - 生成自定义二维码
• /GrAvatar头像 [email/hash] [s] [d] [r] - 获取Gravatar头像
• /摸摸头 [qq] [bg_color] - 通过QQ号生成摸摸头GIF
• /生成摸摸头GIF POST [image_url] [bg_color] - 通过图片URL生成摸摸头GIF
• /无损压缩图片 [file] [level] [format] - 无损压缩PNG/JPG图片
• /生成你们怎么不说话了表情包 [top_text] [bottom_text] - 生成梗图表情包
• /SVG转图片 [file] [format] [width] [height] [quality] - SVG矢量图转光栅图

【翻译类 API】
• /翻译 [to_lang] [text] - 文本翻译（支持100+种语言）

【诗词类 API】
• /一言 - 随机返回一句诗词、动漫台词或名人名言

【网页解析类 API】
• /网页元数据提取 [url] - 提取网页标题、描述、关键词、Open Graph等元数据
• /网页图片提取 [url] - 提取网页中所有图片URL列表

【转换类 API】
• /时间戳转换 [time] - Unix时间戳与日期字符串智能转换
• /JSON格式化 [content] - JSON字符串格式化为美观带缩进版本

【日常类 API】
• /每日新闻图 - 生成包含今日热点新闻摘要的图片

更多帮助请查看具体命令后加-h或-help
注意：UAPI无需API Key，直接调用即可
"""


def get_simple_help_message() -> str:
    """获取简化帮助信息"""
    return """=== Bydbot 帮助 ===
    
地震信息机器人 v2.0

【主要功能】
• 地震信息自动推送
• 天气查询
• UAPI多功能工具
• 气象预警订阅

输入具体命令获取详细帮助
如：/help 或 /地震帮助
"""