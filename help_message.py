"""
Bydbot - 帮助消息模块
提供帮助信息的获取功能
"""

import os
from typing import Dict, Any


def get_help_file_path(config: Dict[str, Any] = None) -> str:
    """获取帮助文件路径"""
    # 始终返回主帮助文件路径
    return os.path.join(os.path.dirname(__file__), 'help命令.txt')


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
• /摸摸头 [qq] [bg_color] - 通过QQ号或@某人生成摸摸头GIF
• /生成你们怎么不说话了表情包 [top_text] [bottom_text] - 生成梗图表情包
• /SVG转图片 [file] [format] [width] [height] [quality] - SVG矢量图转光栅图

【翻译类 API】
• /翻译 [to_lang] [text] - 文本翻译（支持100+种语言，可用单引号括起来支持带空格的句子）

【诗词类 API】
• /一言 - 随机返回一句诗词、动漫台词或名人名言

【网页解析类 API】
• /网页元数据提取 [url] - 提取网页元数据

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