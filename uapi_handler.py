"""
Bydbot - UAPI处理器
处理UAPI相关命令和响应格式化
"""

import logging
from typing import Dict, Any, Optional, List
from uapi_client import UApiClient


def format_uapi_response(command_name: str, data: Dict[str, Any], config: Dict[str, Any]) -> str:
    """
    格式化UAPI响应数据
    :param command_name: 命令名称
    :param data: API响应数据
    :param config: 配置
    :return: 格式化后的消息字符串
    """
    try:
        # 根据不同的命令类型进行格式化
        if command_name == "B站直播间查询":
            if not data or 'uid' not in data:
                return "未找到直播间信息"

            status_map = {0: "🔴 未开播", 1: "🟢 直播中", 2: "🟡 轮播中"}
            status = status_map.get(data.get("live_status", 0), "❓ 未知")

            uid = data.get('uid', 'N/A')
            title = data.get('title', 'N/A')
            online = f"{data.get('online', 0):,}"
            attention = f"{data.get('attention', 0):,}"
            parent_area = data.get('parent_area_name', 'N/A')
            area = data.get('area_name', 'N/A')
            room_id = data.get('room_id', 'N/A')
            short_id = data.get('short_id', 'N/A')
            live_time = data.get('live_time', 'N/A')
            tags = data.get('tags', 'N/A')
            hot_words = data.get('hot_words', [])
            hot_words_str = ', '.join(hot_words[:3]) if hot_words else 'N/A'  # 只显示前3个热词
            description = data.get('description', 'N/A')
            background = data.get('background', 'N/A')
            user_cover = data.get('user_cover', 'N/A')

            room_link = f"https://live.bilibili.com/{room_id}"
            if short_id and short_id != '0' and short_id != 'N/A':
                room_link = f"https://live.bilibili.com/{short_id}"

            return f"[B站直播间查询]\n主播UID: {uid}\n标题: {title}\n状态: {status}\n人气: {online}\n粉丝: {attention}\n分区: {parent_area} - {area}\n标签: {tags}\n热词: {hot_words_str}\n开播时间: {live_time}\n直播间: {room_link}\n描述: {description}"

        elif command_name == "B站用户查询":
            if not data or 'data' not in data:
                return "未找到用户信息"

            user_data = data['data']
            name = user_data.get('name', 'N/A')
            level = user_data.get('level', 'N/A')
            sex = user_data.get('sex', 'N/A')
            sign = user_data.get('sign', 'N/A')
            face = user_data.get('face', 'N/A')
            mid = user_data.get('mid', 'N/A')
            birthday = user_data.get('birthday', 'N/A')
            place = user_data.get('place', 'N/A')
            description = user_data.get('description', 'N/A')
            article_count = user_data.get('article_count', 'N/A')
            following = user_data.get('following', 'N/A')
            follower = user_data.get('follower', 'N/A')
            likes = user_data.get('likes', 'N/A')
            archive_view = user_data.get('archive_view', 'N/A')
            live_room_id = user_data.get('live_room_id', 'N/A')
            live_room_status = user_data.get('live_room_status', 'N/A')
            pendant = user_data.get('pendant', 'N/A')
            nameplate = user_data.get('nameplate', 'N/A')
            official_verify_type = user_data.get('official_verify_type', 'N/A')
            official_verify_desc = user_data.get('official_verify_desc', 'N/A')
            vip_type = user_data.get('vip_type', 'N/A')
            vip_status = user_data.get('vip_status', 'N/A')

            return f"[B站用户查询]\nUID: {mid}\n昵称: {name}\n等级: {level}\n性别: {sex}\n生日: {birthday}\n地区: {place}\n签名: {sign}\n描述: {description}\n文章数: {article_count}\n关注数: {following}\n粉丝数: {follower}\n获赞数: {likes}\n播放量: {archive_view}\n直播间ID: {live_room_id}\n直播状态: {live_room_status}\n头像框: {pendant}\n勋章: {nameplate}\n认证类型: {official_verify_type}\n认证描述: {official_verify_desc}\nVIP类型: {vip_type}\nVIP状态: {vip_status}"

        elif command_name == "B站投稿查询":
            if not data or 'videos' not in data:
                return "未找到投稿信息"

            total = data.get('total', 0)
            page = data.get('page', 'N/A')
            size = data.get('size', 'N/A')
            mid = data.get('mid', 'N/A')
            name = data.get('name', 'N/A')
            videos = data['videos'][:5]  # 只显示前5个视频

            video_list = []
            for video in videos:
                aid = video.get('aid', 'N/A')
                bvid = video.get('bvid', 'N/A')
                title = video.get('title', 'N/A')
                cover = video.get('cover', 'N/A')
                duration = video.get('duration', 0)
                play_count = f"{video.get('play_count', 0):,}"
                danmaku_count = f"{video.get('danmaku', 0):,}"
                comment_count = f"{video.get('comment', 0):,}"
                like_count = f"{video.get('like', 0):,}"
                coin_count = f"{video.get('coin', 0):,}"
                share_count = f"{video.get('share', 0):,}"
                favorite_count = f"{video.get('favorite', 0):,}"
                publish_time = video.get('publish_time', 'N/A')
                pubdate = video.get('pubdate', 'N/A')
                description = video.get('description', 'N/A')[:50]  # 限制描述长度
                tag = video.get('tag', 'N/A')
                typename = video.get('typename', 'N/A')
                copyright = video.get('copyright', 'N/A')
                pic = video.get('pic', 'N/A')
                
                mins = duration // 60
                secs = duration % 60
                duration_str = f"{mins}:{secs:02d}"

                video_list.append(f"- {title} (BV: {bvid})\n  播放:{play_count}, 弹幕:{danmaku_count}, 时长:{duration_str}\n  发布时间: {pubdate}\n  类型: {typename}, 标签: {tag}")

            video_str = "\n".join(video_list)
            return f"[B站投稿查询]\nUP主: {name} (UID: {mid})\n总计稿件: {total}\n当前页: {page}/{size}\n最近投稿:\n{video_str}"

        elif command_name == "GitHub仓库查询":
            if not data or ('full_name' not in data and 'name' not in data):
                return "未找到仓库信息"

            full_name = data.get('full_name', data.get('name', 'N/A'))
            name = data.get('name', data.get('full_name', 'N/A'))
            owner_login = data.get('owner', {}).get('login', data.get('owner', {}).get('login', 'N/A')) if data.get('owner') or data.get('owner') else 'N/A'
            description = data.get('description', 'N/A')
            language = data.get('language', 'N/A')
            languages = data.get('languages', {})
            stargazers = data.get('stargazers', data.get('stargazers_count', 0))
            forks = data.get('forks', data.get('forks_count', 0))
            open_issues = data.get('open_issues', data.get('open_issues_count', 0))
            watchers = data.get('watchers', data.get('watchers_count', 0))
            subscribers = data.get('subscribers', 'N/A')
            size = data.get('size', 'N/A')
            default_branch = data.get('default_branch', 'N/A')
            primary_branch = data.get('primary_branch', 'N/A')
            license_info = data.get('license', data.get('license', 'N/A'))
            created_at = data.get('created_at', 'N/A')
            updated_at = data.get('updated_at', 'N/A')
            pushed_at = data.get('pushed_at', 'N/A')
            homepage = data.get('homepage', 'N/A')
            topics = data.get('topics', [])
            topics_str = ', '.join(topics[:10]) if topics else 'N/A'  # 只显示前10个话题
            visibility = data.get('visibility', 'N/A')
            archived = data.get('archived', 'N/A')
            disabled = data.get('disabled', 'N/A')
            fork = data.get('fork', 'N/A')
            has_issues = data.get('has_issues', 'N/A')
            has_projects = data.get('has_projects', 'N/A')
            has_wiki = data.get('has_wiki', 'N/A')
            has_pages = data.get('has_pages', 'N/A')
            has_downloads = data.get('has_downloads', 'N/A')
            has_discussions = data.get('has_discussions', 'N/A')
            clone_url = data.get('clone_url', 'N/A')
            ssh_url = data.get('ssh_url', 'N/A')
            git_url = data.get('git_url', 'N/A')
            html_url = data.get('html_url', 'N/A')
            collaborators = data.get('collaborators', [])
            maintainer_count = len(collaborators) if collaborators else 0
            latest_release = data.get('latest_release', {})
            release_name = latest_release.get('name', 'N/A') if latest_release else 'N/A'
            release_published_at = latest_release.get('published_at', 'N/A') if latest_release else 'N/A'

            return f"[GitHub仓库查询]\n仓库: {full_name}\n所有者: {owner_login}\n名称: {name}\n描述: {description}\n主要语言: {language}\n语言分布: {str(languages)[:100]}...\n许可证: {license_info}\nStar数: {stargazers}\nFork数: {forks}\nIssue数: {open_issues}\nWatchers数: {watchers}\n订阅者数: {subscribers}\n大小: {size}KB\n默认分支: {default_branch}\n主分支: {primary_branch}\n可见性: {visibility}\n归档: {archived}\n禁用: {disabled}\nFork: {fork}\n话题: {topics_str}\n主页: {homepage}\n创建时间: {created_at}\n更新时间: {updated_at}\n最后推送: {pushed_at}\n克隆地址: {clone_url}\n协作人数: {maintainer_count}\n最新发布: {release_name} ({release_published_at})"

        elif command_name == "热榜查询":
            if not data or 'list' not in data:
                return "未获取到热榜数据"

            hot_list = data['list'][:10]  # 只显示前10条
            type_name = data.get('type', '未知')
            subtype = data.get('subtype', 'N/A')
            update_time = data.get('update_time', 'N/A')
            source = data.get('source', 'N/A')
            total_count = data.get('total', len(hot_list))

            hot_items = []
            for i, item in enumerate(hot_list, 1):
                title = item.get('title', 'N/A')
                hot_score = item.get('hot', item.get('score', 'N/A'))
                url = item.get('url', 'N/A')
                note = item.get('note', '')
                category = item.get('category', '')
                author = item.get('author', '')
                publish_time = item.get('publish_time', '')
                media = item.get('media', '')
                image = item.get('image', '')
                summary = item.get('summary', '')[:50] + '...' if item.get('summary') else ''
                
                item_info = f"{i:2d}. {title}"
                if hot_score != 'N/A':
                    item_info += f" (热度:{hot_score})"
                if url != 'N/A':
                    item_info += f"\n     链接: {url}"
                if note:
                    item_info += f"\n     备注: {note}"
                if author:
                    item_info += f"\n     作者: {author}"
                if publish_time:
                    item_info += f"\n     发布时间: {publish_time}"
                if media:
                    item_info += f"\n     媒体: {media}"
                if summary:
                    item_info += f"\n     摘要: {summary}"

                hot_items.append(item_info)

            hot_str = "\n".join(hot_items)
            return f"[{type_name}热榜]\n子类型: {subtype}\n数据源: {source}\n总数: {total_count}\n更新时间: {update_time}\n\n{hot_str}"

        elif command_name == "世界时间查询":
            if not data or 'datetime' not in data:
                return "未获取到时间信息"

            datetime = data.get('datetime', 'N/A')
            timezone = data.get('timezone', 'N/A')
            weekday = data.get('weekday', 'N/A')
            offset_string = data.get('offset_string', 'N/A')
            unix_time = data.get('unix_time', 'N/A')
            timestamp = data.get('timestamp', 'N/A')
            country = data.get('country', 'N/A')
            region = data.get('region', 'N/A')
            abbreviation = data.get('abbreviation', 'N/A')
            dst = data.get('dst', 'N/A')  # 是否夏令时
            dst_start = data.get('dst_start', 'N/A')
            dst_end = data.get('dst_end', 'N/A')
            utc_offset = data.get('utc_offset', 'N/A')
            formatted_date = data.get('formatted_date', 'N/A')
            formatted_time = data.get('formatted_time', 'N/A')
            timezone_name = data.get('timezone_name', 'N/A')
            gmt_offset = data.get('gmt_offset', 'N/A')

            return f"[世界时间查询]\n时区: {timezone}\n时区名称: {timezone_name}\n国家: {country}\n地区: {region}\n缩写: {abbreviation}\nUTC偏移: {utc_offset}\nGMT偏移: {gmt_offset}\n夏令时: {dst}\n偏移量: {offset_string}\n星期: {weekday}\n日期: {formatted_date}\n时间: {formatted_time}\nUnix时间戳: {unix_time}\n时间戳: {timestamp}\n完整时间: {datetime}"

        elif command_name == "天气查询":
            if not data or 'temperature' not in data:
                return "未获取到天气信息"

            city = data.get('city', '未知城市')
            province = data.get('province', '未知省份')
            temperature = data.get('temperature', 'N/A')
            weather = data.get('weather', 'N/A')
            humidity = data.get('humidity', 'N/A')
            wind_direction = data.get('wind_direction', 'N/A')
            wind_power = data.get('wind_power', 'N/A')
            report_time = data.get('report_time', 'N/A')
            feels_like = data.get('feels_like', 'N/A')
            visibility = data.get('visibility', 'N/A')
            pressure = data.get('pressure', 'N/A')
            uv_index = data.get('uv_index', 'N/A')
            aqi = data.get('aqi', 'N/A')
            pm25 = data.get('pm25', 'N/A')
            pm10 = data.get('pm10', 'N/A')
            co = data.get('co', 'N/A')
            no2 = data.get('no2', 'N/A')
            o3 = data.get('o3', 'N/A')
            so2 = data.get('so2', 'N/A')
            air_quality = data.get('air_quality', 'N/A')
            sunrise = data.get('sunrise', 'N/A')
            sunset = data.get('sunset', 'N/A')
            precipitation = data.get('precipitation', 'N/A')
            dew_point = data.get('dew_point', 'N/A')
            cloud_cover = data.get('cloud_cover', 'N/A')
            hourly_forecast = data.get('hourly_forecast', [])
            daily_forecast = data.get('daily_forecast', [])

            return f"[天气查询 - {province}{city}]\n温度: {temperature}°C (体感{feels_like}°C)\n天气: {weather}\n湿度: {humidity}%\n风向: {wind_direction}\n风力: {wind_power}\n能见度: {visibility}km\n气压: {pressure}hPa\n紫外线指数: {uv_index}\n空气质量指数: {aqi}\nPM2.5: {pm25}μg/m³\nPM10: {pm10}μg/m³\n一氧化碳: {co}mg/m³\n二氧化氮: {no2}μg/m³\n臭氧: {o3}μg/m³\n二氧化硫: {so2}μg/m³\n空气质量: {air_quality}\n日出: {sunrise}\n日落: {sunset}\n降水量: {precipitation}mm\n露点: {dew_point}°C\n云量: {cloud_cover}%\n报告时间: {report_time}"

        elif command_name == "手机归属地查询":
            if not data or 'province' not in data:
                return "未查询到归属地信息"

            province = data.get('province', 'N/A')
            city = data.get('city', 'N/A')
            sp = data.get('sp', 'N/A')
            zip_code = data.get('zip_code', 'N/A')
            area_code = data.get('area_code', 'N/A')
            card_type = data.get('card_type', 'N/A')
            company = data.get('company', 'N/A')
            brand = data.get('brand', 'N/A')
            province_code = data.get('province_code', 'N/A')
            city_code = data.get('city_code', 'N/A')
            country_code = data.get('country_code', 'N/A')
            timezone = data.get('timezone', 'N/A')
            latitude = data.get('latitude', 'N/A')
            longitude = data.get('longitude', 'N/A')
            accuracy = data.get('accuracy', 'N/A')
            source = data.get('source', 'N/A')
            update_time = data.get('update_time', 'N/A')

            return f"[手机归属地查询]\n省份: {province}\n城市: {city}\n运营商: {sp}\n卡类型: {card_type}\n公司: {company}\n品牌: {brand}\n邮编: {zip_code}\n区号: {area_code}\n省份代码: {province_code}\n城市代码: {city_code}\n国家代码: {country_code}\n时区: {timezone}\n经纬度: {latitude}, {longitude}\n精度: {accuracy}\n数据源: {source}\n更新时间: {update_time}"

        elif command_name == "随机数生成":
            if not data or 'numbers' not in data:
                return "随机数生成失败"

            numbers = data.get('numbers', [])
            min_val = data.get('min', 'N/A')
            max_val = data.get('max', 'N/A')
            count = data.get('count', 'N/A')
            allow_repeat = data.get('allow_repeat', 'N/A')
            allow_decimal = data.get('allow_decimal', 'N/A')
            decimal_places = data.get('decimal_places', 'N/A')
            seed = data.get('seed', 'N/A')
            algorithm = data.get('algorithm', 'N/A')
            timestamp = data.get('timestamp', 'N/A')
            sum_total = sum(numbers) if numbers else 0
            average = sum_total / len(numbers) if numbers else 0

            numbers_str = ', '.join(map(str, numbers[:20]))  # 只显示前20个数字，避免消息过长
            if len(numbers) > 20:
                numbers_str += f", ...(还有{len(numbers)-20}个)"

            return f"[随机数生成]\n参数: {min_val} ~ {max_val}, 生成{count}个\n允许重复: {allow_repeat}\n允许小数: {allow_decimal}\n小数位数: {decimal_places}\n种子: {seed}\n算法: {algorithm}\n生成时间: {timestamp}\n生成的随机数: {numbers_str}\n总和: {sum_total}\n平均值: {average:.2f}"

        elif command_name == "ICP备案查询":
            if not data or data.get('code') != '200':
                return "未查询到备案信息或查询失败"
            
            domain = data.get('domain', 'N/A')
            service_license = data.get('serviceLicence', 'N/A')
            unit_name = data.get('unitName', 'N/A')
            nature_name = data.get('natureName', 'N/A')
            
            return f"[ICP备案查询]\n域名: {domain}\n备案号: {service_license}\n主办单位: {unit_name}\n单位性质: {nature_name}"

        elif command_name == "IP信息查询":
            if not data or 'ip' not in data:
                return "未查询到IP信息"
            
            ip = data.get('ip', 'N/A')
            region = data.get('region', 'N/A')
            isp = data.get('isp', 'N/A')
            asn = data.get('asn', 'N/A')
            latitude = data.get('latitude', 'N/A')
            longitude = data.get('longitude', 'N/A')
            llc = data.get('llc', 'N/A')
            district = data.get('district', 'N/A')
            
            return f"[IP信息查询]\nIP地址: {ip}\n地理位置: {region}\n行政区: {district}\n运营商: {isp}\n归属机构: {llc}\nASN: {asn}\n经纬度: {latitude}, {longitude}"

        elif command_name == "一言":
            if not data or 'text' not in data:
                return "获取一言失败"
            
            text = data.get('text', 'N/A')
            
            return f"[一言]\n{text}"

        elif command_name == "随机图片":
            return "[随机图片]\n图片已生成并发送"

        elif command_name == "答案之书":
            if not data or 'answer' not in data:
                return "获取答案失败"
            
            question = data.get('question', 'N/A')
            answer = data.get('answer', 'N/A')
            
            return f"[答案之书]\n问题: {question}\n答案: {answer}"

        elif command_name == "随机字符串":
            if not data or 'text' not in data:
                return "生成随机字符串失败"
            
            text = data.get('text', 'N/A')
            
            return f"[随机字符串]\n生成的字符串: {text}"

        elif command_name == "必应壁纸":
            return "[必应壁纸]\n壁纸已获取并发送"

        elif command_name == "生成二维码":
            return "[生成二维码]\n二维码已生成并发送"

        elif command_name == "GrAvatar头像":
            return "[GrAvatar头像]\n头像已获取并发送"

        elif command_name == "摸摸头":
            return "[摸摸头]\nGIF已生成并发送"

        elif command_name == "生成摸摸头GIF POST":
            return "[生成摸摸头GIF POST]\nGIF已生成并发送"

        elif command_name == "每日新闻图":
            return "[每日新闻图]\n新闻图已获取并发送"

        elif command_name == "上传图片":
            if not data or 'image_url' not in data:
                return "上传图片失败"

            image_url = data.get('image_url', 'N/A')
            msg = data.get('msg', 'N/A')

            return f"[上传图片]\n图片URL: {image_url}\n状态: {msg}"

        elif command_name == "图片转Base64":
            if not data or 'base64' not in data:
                return "图片转Base64失败"

            base64_data = data.get('base64', 'N/A')
            msg = data.get('msg', 'N/A')

            return f"[图片转Base64]\nBase64数据: {base64_data[:50]}...\n状态: {msg}"

        elif command_name == "翻译":
            if not data or ('translated_text' not in data and 'text' not in data):
                return "翻译失败"
            
            source_lang = data.get('source_lang', 'N/A')
            translated_text = data.get('translated_text', data.get('text', 'N/A'))
            
            return f"[翻译]\n原文语言: {source_lang}\n翻译结果: {translated_text}"

        elif command_name == "MC服务器查询":
            if not data or 'ip' not in data:
                return "未查询到服务器信息"
            
            online = data.get('online', False)
            if not online:
                return "[MC服务器查询]\n服务器离线或无法连接"
            
            ip = data.get('ip', 'N/A')
            port = data.get('port', 'N/A')
            players = data.get('players', 0)
            max_players = data.get('max_players', 0)
            version = data.get('version', 'N/A')
            motd_clean = data.get('motd_clean', 'N/A')
            
            status = "🟢 在线" if online else "🔴 离线"
            return f"[MC服务器查询]\n状态: {status}\nIP: {ip}:{port}\n在线玩家: {players}/{max_players}\n版本: {version}\nMOTD: {motd_clean}"

        elif command_name == "Steam用户查询":
            if not data or 'steamid' not in data:
                return "未查询到用户信息"
            
            personaname = data.get('personaname', 'N/A')
            profileurl = data.get('profileurl', 'N/A')
            personastate = data.get('personastate', 0)
            communityvisibilitystate = data.get('communityvisibilitystate', 1)
            realname = data.get('realname', 'N/A')
            loccountrycode = data.get('loccountrycode', 'N/A')
            timecreated_str = data.get('timecreated_str', 'N/A')
            
            state_map = {
                0: "🔴 离线", 1: "🟢 在线", 2: "🟡 忙碌", 3: "🔵 离开",
                4: "🌙 打盹", 5: "💡 想交易", 6: "🎮 想玩"
            }
            state = state_map.get(personastate, "❓ 未知")
            
            visibility = "公开" if communityvisibilitystate == 3 else "私密"
            
            return f"[Steam用户查询]\n昵称: {personaname}\n真实姓名: {realname}\n状态: {state}\n可见性: {visibility}\n国家: {loccountrycode}\n账户创建: {timecreated_str}\n个人资料: {profileurl}"

        elif command_name == "Epic免费游戏":
            if not data:
                return "未查询到免费游戏信息"

            # 尝试不同的数据结构
            games = None
            if 'data' in data and isinstance(data['data'], list):
                games = data['data']
            elif isinstance(data, list):
                games = data
            elif 'games' in data and isinstance(data['games'], list):
                games = data['games']
            
            if not games:
                return "[Epic免费游戏]\n当前没有免费游戏"

            game_list = []
            for i, game in enumerate(games[:5], 1):  # 最多显示5个
                if isinstance(game, dict):
                    title = game.get('title', game.get('name', 'N/A'))
                    description = game.get('description', '暂无描述')
                    price = game.get('price', game.get('originalPrice', 'N/A'))
                    end_date = game.get('end_date', game.get('expiryDate', 'N/A'))
                    
                    # 如果价格是数字，格式化为货币形式
                    if isinstance(price, (int, float)):
                        price = f"${price:.2f}"
                    if isinstance(price, dict) and 'discountPrice' in price:
                        price = f"${price['discountPrice']:.2f}"
                
                    game_list.append(f"{i}. {title} - {price} (截止: {end_date})\n   {description}")
                else:
                    # 如果游戏不是字典格式，直接显示
                    game_list.append(f"{i}. {str(game)[:100]}...")

            game_str = "\n".join(game_list)
            return f"[Epic免费游戏]\n{game_str}"

        elif command_name == "MC玩家查询":
            if not data or 'username' not in data:
                return "未查询到玩家信息"
            
            username = data.get('username', 'N/A')
            uuid = data.get('uuid', 'N/A')
            skin_url = data.get('skin_url', 'N/A')
            
            return f"[MC玩家查询]\n用户名: {username}\nUUID: {uuid}\n皮肤URL: {skin_url}"

        elif command_name == "MD5校验":
            if not data or 'match' not in data:
                return "MD5校验失败"
            
            match = data.get('match', False)
            match_status = "✅ 匹配" if match else "❌ 不匹配"
            
            return f"[MD5校验]\n校验结果: {match_status}"

        elif command_name == "Base64编码":
            if not data or 'encoded' not in data:
                return "Base64编码失败"
            
            encoded = data.get('encoded', 'N/A')
            
            return f"[Base64编码]\n{encoded}"

        elif command_name == "Base64解码":
            if not data or 'decoded' not in data:
                return "Base64解码失败"
            
            decoded = data.get('decoded', 'N/A')
            
            return f"[Base64解码]\n{decoded}"

        elif command_name == "AES加密":
            if not data or 'ciphertext' not in data:
                return "AES加密失败"
            
            ciphertext = data.get('ciphertext', 'N/A')
            
            return f"[AES加密]\n{ciphertext}"

        elif command_name == "AES解密":
            if not data or 'plaintext' not in data:
                return "AES解密失败"
            
            plaintext = data.get('plaintext', 'N/A')
            
            return f"[AES解密]\n{plaintext}"

        elif command_name == "AES高级加密":
            if not data or 'ciphertext' not in data:
                return "AES高级加密失败"
            
            ciphertext = data.get('ciphertext', 'N/A')
            mode = data.get('mode', 'N/A')
            padding = data.get('padding', 'N/A')
            
            return f"[AES高级加密] {mode}/{padding}\n{ciphertext}"

        elif command_name == "AES高级解密":
            if not data or 'plaintext' not in data:
                return "AES高级解密失败"
            
            plaintext = data.get('plaintext', 'N/A')
            
            return f"[AES高级解密]\n{plaintext}"

        elif command_name == "格式转换":
            if not data or 'result' not in data:
                return "格式转换失败"
            
            result = data.get('result', 'N/A')
            from_format = data.get('from', 'unknown')
            to_format = data.get('to', 'unknown')
            
            return f"[格式转换] {from_format} → {to_format}\n{result}"

        elif command_name == "Ping主机":
            if not data or 'host' not in data:
                return "Ping测试失败"
            
            host = data.get('host', 'N/A')
            ip = data.get('ip', 'N/A')
            location = data.get('location', 'N/A')
            avg = data.get('avg', 'N/A')
            
            return f"[Ping主机]\n目标: {host} ({ip})\n地理位置: {location}\n平均延迟: {avg}ms"

        elif command_name == "DNS查询":
            if not data or 'records' not in data:
                return "DNS查询失败"

            domain = data.get('domain', 'N/A')
            records = data.get('records', [])

            record_list = []
            for record in records:
                record_type = record.get('type', 'N/A')
                value = record.get('value', 'N/A')
                ttl = record.get('ttl', 'N/A')
                record_list.append(f"  {record_type}: {value} (TTL: {ttl})")

            record_str = "\n".join(record_list)
            return f"[DNS查询 - {domain}]\n{record_str}"

        elif command_name == "WHOIS查询":
            if not data:
                return "WHOIS查询失败"

            # WHOIS查询可能返回不同格式的数据，根据格式处理
            if 'whois' in data:
                whois_data = data['whois']
                if isinstance(whois_data, str):
                    # 如果是原始文本格式
                    return f"[WHOIS查询]\n{whois_data[:500]}..."  # 限制长度
                elif isinstance(whois_data, dict):
                    # 如果是结构化JSON格式，提取关键信息
                    domain_name = whois_data.get('domain_name', 'N/A')
                    registrar = whois_data.get('registrar', 'N/A')
                    registrant_name = whois_data.get('registrant_name', 'N/A')
                    registrant_email = whois_data.get('registrant_email', 'N/A')
                    registrant_org = whois_data.get('registrant_org', 'N/A')
                    creation_date = whois_data.get('creation_date', 'N/A')
                    updated_date = whois_data.get('updated_date', 'N/A')
                    expiration_date = whois_data.get('expiration_date', 'N/A')
                    status = whois_data.get('status', 'N/A')
                    name_servers = whois_data.get('name_servers', [])
                    dnssec = whois_data.get('dnssec', 'N/A')
                    abuse_email = whois_data.get('abuse_email', 'N/A')
                    abuse_phone = whois_data.get('abuse_phone', 'N/A')

                    ns_str = ", ".join(name_servers[:10]) if name_servers else "N/A"  # 显示前10个NS

                    return f"[WHOIS查询]\n域名: {domain_name}\n注册商: {registrar}\n注册人: {registrant_name}\n注册组织: {registrant_org}\n注册邮箱: {registrant_email}\n创建时间: {creation_date}\n更新时间: {updated_date}\n到期时间: {expiration_date}\n状态: {status}\nDNSSEC: {dnssec}\n域名服务器: {ns_str}\n滥用邮箱: {abuse_email}\n滥用电话: {abuse_phone}"
                else:
                    return f"[WHOIS查询]\n{str(whois_data)[:500]}..."
            else:
                # 如果直接是WHOIS数据（没有嵌套在whois键下）
                domain_name = data.get('domain_name', data.get('domain', 'N/A'))
                registrar = data.get('registrar', 'N/A')
                registrant_name = data.get('registrant_name', 'N/A')
                registrant_email = data.get('registrant_email', 'N/A')
                registrant_org = data.get('registrant_org', 'N/A')
                creation_date = data.get('creation_date', 'N/A')
                updated_date = data.get('updated_date', 'N/A')
                expiration_date = data.get('expiration_date', 'N/A')
                status = data.get('status', 'N/A')
                name_servers = data.get('name_servers', [])
                dnssec = data.get('dnssec', 'N/A')
                abuse_email = data.get('abuse_email', 'N/A')
                abuse_phone = data.get('abuse_phone', 'N/A')

                ns_str = ", ".join(name_servers[:10]) if name_servers else "N/A"  # 显示前10个NS

                return f"[WHOIS查询]\n域名: {domain_name}\n注册商: {registrar}\n注册人: {registrant_name}\n注册组织: {registrant_org}\n注册邮箱: {registrant_email}\n创建时间: {creation_date}\n更新时间: {updated_date}\n到期时间: {expiration_date}\n状态: {status}\nDNSSEC: {dnssec}\n域名服务器: {ns_str}\n滥用邮箱: {abuse_email}\n滥用电话: {abuse_phone}"

        elif command_name == "URL可访问性":
            if not data or 'url' not in data:
                return "URL可访问性检查失败"
            
            url = data.get('url', 'N/A')
            status = data.get('status', 'N/A')
            
            status_desc = "✅ 可访问" if 200 <= status < 300 else f"❌ 不可访问 ({status})"
            
            return f"[URL可访问性]\n{status_desc}\nURL: {url}"

        elif command_name == "端口扫描":
            if not data or 'ip' not in data:
                return "端口扫描失败"

            ip = data.get('ip', 'N/A')
            port = data.get('port', 'N/A')
            protocol = data.get('protocol', 'N/A')
            port_status = data.get('port_status', 'N/A')

            status_map = {
                'open': '🟢 开放',
                'closed': '🔴 关闭',
                'timeout': '⏰ 超时'
            }
            status_desc = status_map.get(port_status, port_status)

            return f"[端口扫描]\nIP: {ip}\n端口: {port}/{protocol}\n状态: {status_desc}"

        elif command_name == "无损压缩图片":
            return "[无损压缩图片]\n图片已压缩并发送"

        elif command_name == "生成你们怎么不说话了表情包":
            return "[生成你们怎么不说话了表情包]\n表情包已生成并发送"

        elif command_name == "SVG转图片":
            return "[SVG转图片]\n图片已转换并发送"

        elif command_name == "时间戳转换":
            if not data or 'datetime' not in data:
                return "时间戳转换失败"
            
            datetime_str = data.get('datetime', 'N/A')
            timestamp = data.get('timestamp', 'N/A')
            
            return f"[时间戳转换]\n日期时间: {datetime_str}\n时间戳: {timestamp}"

        elif command_name == "JSON格式化":
            if not data or 'content' not in data:
                return "JSON格式化失败"

            formatted_content = data.get('content', 'N/A')

            return f"[JSON格式化]\n{formatted_content}"

        elif command_name == "网页元数据提取":
            if not data or 'page_url' not in data:
                return "网页元数据提取失败"

            page_url = data.get('page_url', 'N/A')
            title = data.get('title', 'N/A')
            description = data.get('description', 'N/A')
            keywords = data.get('keywords', [])
            favicon_url = data.get('favicon_url', 'N/A')
            
            keywords_str = ", ".join(keywords[:5]) if keywords else "N/A"  # 只显示前5个关键词

            return f"[网页元数据提取]\n页面URL: {page_url}\n标题: {title}\n描述: {description}\n关键词: {keywords_str}\nFavicon: {favicon_url}"

        elif command_name == "网页图片提取":
            if not data or 'url' not in data:
                return "网页图片提取失败"

            url = data.get('url', 'N/A')
            count = data.get('count', 0)
            images = data.get('images', [])

            image_list = images[:5]  # 只显示前5张图片
            image_str = "\n".join([f"- {img}" for img in image_list])

            return f"[网页图片提取]\n网页URL: {url}\n图片总数: {count}\n前几张图片:\n{image_str}"

        elif command_name == "程序员历史上的今天":
            if not data or 'events' not in data:
                return "程序员历史上的今天查询失败"

            date = data.get('date', 'N/A')
            events = data.get('events', [])
            message = data.get('message', 'N/A')

            event_list = []
            for i, event in enumerate(events[:5], 1):  # 只显示前5个事件
                year = event.get('year', 'N/A')
                title = event.get('title', 'N/A')
                desc = event.get('desc', 'N/A')
                event_list.append(f"{i}. [{year}] {title}\n   {desc}")

            event_str = "\n".join(event_list)
            return f"[程序员历史上的今天]\n日期: {date}\n今日事件:\n{event_str}"

        elif command_name == "程序员历史事件":
            if not data or 'events' not in data:
                return "程序员历史事件查询失败"

            date = data.get('date', 'N/A')
            events = data.get('events', [])

            event_list = []
            for i, event in enumerate(events[:5], 1):  # 只显示前5个事件
                year = event.get('year', 'N/A')
                title = event.get('title', 'N/A')
                desc = event.get('desc', 'N/A')
                event_list.append(f"{i}. [{year}] {title}\n   {desc}")

            event_str = "\n".join(event_list)
            return f"[程序员历史事件]\n日期: {date}\n历史事件:\n{event_str}"

        elif command_name == "MD5哈希":
            if not data or 'md5' not in data:
                return "MD5计算失败"
            
            md5_hash = data.get('md5', 'N/A')
            
            return f"[MD5哈希]\n{md5_hash}"

        elif command_name == "MD5哈希 POST":
            if not data or 'md5' not in data:
                return "MD5计算失败"
            
            md5_hash = data.get('md5', 'N/A')
            
            return f"[MD5哈希(POST)]\n{md5_hash}"

        elif command_name == "MD5校验":
            if not data or 'match' not in data:
                return "MD5校验失败"
            
            match = data.get('match', False)
            match_status = "✅ 匹配" if match else "❌ 不匹配"
            
            return f"[MD5校验]\n校验结果: {match_status}"

        elif command_name == "Base64编码":
            if not data or 'encoded' not in data:
                return "Base64编码失败"
            
            encoded = data.get('encoded', 'N/A')
            
            return f"[Base64编码]\n{encoded}"

        elif command_name == "Base64解码":
            if not data or 'decoded' not in data:
                return "Base64解码失败"
            
            decoded = data.get('decoded', 'N/A')
            
            return f"[Base64解码]\n{decoded}"

        elif command_name == "AES加密":
            if not data or 'ciphertext' not in data:
                return "AES加密失败"
            
            ciphertext = data.get('ciphertext', 'N/A')
            
            return f"[AES加密]\n{ciphertext}"

        elif command_name == "AES解密":
            if not data or 'plaintext' not in data:
                return "AES解密失败"
            
            plaintext = data.get('plaintext', 'N/A')
            
            return f"[AES解密]\n{plaintext}"

        elif command_name == "AES高级加密":
            if not data or 'ciphertext' not in data:
                return "AES高级加密失败"
            
            ciphertext = data.get('ciphertext', 'N/A')
            mode = data.get('mode', 'N/A')
            padding = data.get('padding', 'N/A')
            
            return f"[AES高级加密] {mode}/{padding}\n{ciphertext}"

        elif command_name == "AES高级解密":
            if not data or 'plaintext' not in data:
                return "AES高级解密失败"
            
            plaintext = data.get('plaintext', 'N/A')
            
            return f"[AES高级解密]\n{plaintext}"

        elif command_name == "格式转换":
            if not data or 'result' not in data:
                return "格式转换失败"
            
            result = data.get('result', 'N/A')
            from_format = data.get('from', 'unknown')
            to_format = data.get('to', 'unknown')
            info = data.get('info', '')
            
            output = f"[格式转换] {from_format} → {to_format}\n{result}"
            if info:
                output += f"\n说明: {info}"
            
            return output

        elif command_name == "Ping主机":
            if not data or 'host' not in data:
                return "Ping测试失败"
            
            host = data.get('host', 'N/A')
            ip = data.get('ip', 'N/A')
            location = data.get('location', 'N/A')
            avg = data.get('avg', 'N/A')
            
            return f"[Ping主机]\n目标: {host} ({ip})\n地理位置: {location}\n平均延迟: {avg}ms"

        elif command_name == "DNS查询":
            if not data or 'records' not in data:
                return "DNS查询失败"

            domain = data.get('domain', 'N/A')
            records = data.get('records', [])

            record_list = []
            for record in records:
                record_type = record.get('type', 'N/A')
                value = record.get('value', 'N/A')
                ttl = record.get('ttl', 'N/A')
                record_list.append(f"  {record_type}: {value} (TTL: {ttl})")

            record_str = "\n".join(record_list)
            return f"[DNS查询 - {domain}]\n{record_str}"

        elif command_name == "WHOIS查询":
            if not data:
                return "WHOIS查询失败"

            # WHOIS查询可能返回不同格式的数据，根据格式处理
            if 'whois' in data:
                whois_data = data['whois']
                if isinstance(whois_data, str):
                    # 如果是原始文本格式
                    return f"[WHOIS查询]\n{whois_data[:500]}..."  # 限制长度
                elif isinstance(whois_data, dict):
                    # 如果是结构化JSON格式，提取关键信息
                    domain_name = whois_data.get('domain_name', 'N/A')
                    registrar = whois_data.get('registrar', 'N/A')
                    registrant_name = whois_data.get('registrant_name', 'N/A')
                    registrant_email = whois_data.get('registrant_email', 'N/A')
                    registrant_org = whois_data.get('registrant_org', 'N/A')
                    creation_date = whois_data.get('creation_date', 'N/A')
                    updated_date = whois_data.get('updated_date', 'N/A')
                    expiration_date = whois_data.get('expiration_date', 'N/A')
                    status = whois_data.get('status', 'N/A')
                    name_servers = whois_data.get('name_servers', [])
                    dnssec = whois_data.get('dnssec', 'N/A')
                    abuse_email = whois_data.get('abuse_email', 'N/A')
                    abuse_phone = whois_data.get('abuse_phone', 'N/A')

                    ns_str = ", ".join(name_servers[:10]) if name_servers else "N/A"  # 显示前10个NS

                    return f"[WHOIS查询]\n域名: {domain_name}\n注册商: {registrar}\n注册人: {registrant_name}\n注册组织: {registrant_org}\n注册邮箱: {registrant_email}\n创建时间: {creation_date}\n更新时间: {updated_date}\n到期时间: {expiration_date}\n状态: {status}\nDNSSEC: {dnssec}\n域名服务器: {ns_str}\n滥用邮箱: {abuse_email}\n滥用电话: {abuse_phone}"
                else:
                    return f"[WHOIS查询]\n{str(whois_data)[:500]}..."
            else:
                # 如果直接是WHOIS数据（没有嵌套在whois键下）
                domain_name = data.get('domain_name', data.get('domain', 'N/A'))
                registrar = data.get('registrar', 'N/A')
                registrant_name = data.get('registrant_name', 'N/A')
                registrant_email = data.get('registrant_email', 'N/A')
                registrant_org = data.get('registrant_org', 'N/A')
                creation_date = data.get('creation_date', 'N/A')
                updated_date = data.get('updated_date', 'N/A')
                expiration_date = data.get('expiration_date', 'N/A')
                status = data.get('status', 'N/A')
                name_servers = data.get('name_servers', [])
                dnssec = data.get('dnssec', 'N/A')
                abuse_email = data.get('abuse_email', 'N/A')
                abuse_phone = data.get('abuse_phone', 'N/A')

                ns_str = ", ".join(name_servers[:10]) if name_servers else "N/A"  # 显示前10个NS

                return f"[WHOIS查询]\n域名: {domain_name}\n注册商: {registrar}\n注册人: {registrant_name}\n注册组织: {registrant_org}\n注册邮箱: {registrant_email}\n创建时间: {creation_date}\n更新时间: {updated_date}\n到期时间: {expiration_date}\n状态: {status}\nDNSSEC: {dnssec}\n域名服务器: {ns_str}\n滥用邮箱: {abuse_email}\n滥用电话: {abuse_phone}"

        elif command_name == "URL可访问性":
            if not data or 'url' not in data:
                return "URL可访问性检查失败"
            
            url = data.get('url', 'N/A')
            status = data.get('status', 'N/A')
            
            status_desc = "✅ 可访问" if 200 <= status < 300 else f"❌ 不可访问 ({status})"
            
            return f"[URL可访问性]\n{status_desc}\nURL: {url}"

        elif command_name == "端口扫描":
            if not data or 'ip' not in data:
                return "端口扫描失败"

            ip = data.get('ip', 'N/A')
            port = data.get('port', 'N/A')
            protocol = data.get('protocol', 'N/A')
            port_status = data.get('port_status', 'N/A')

            status_map = {
                'open': '🟢 开放',
                'closed': '🔴 关闭',
                'filtered': '🟡 过滤',
                'timeout': '⏰ 超时'
            }
            status_desc = status_map.get(port_status, port_status)

            return f"[端口扫描]\nIP: {ip}\n端口: {port}/{protocol}\n状态: {status_desc}"

        elif command_name == "MC玩家查询":
            if not data or 'username' not in data:
                return "未查询到玩家信息"
            
            username = data.get('username', 'N/A')
            uuid = data.get('uuid', 'N/A')
            skin_url = data.get('skin_url', 'N/A')
            
            return f"[MC玩家查询]\n用户名: {username}\nUUID: {uuid}\n皮肤URL: {skin_url}"

        elif command_name == "MC曾用名查询":
            if not data or 'history' not in data:
                return "未查询到曾用名信息"
            
            current_name = data.get('id', 'N/A')
            uuid = data.get('uuid', 'N/A')
            name_num = data.get('name_num', 'N/A')
            history = data.get('history', [])
            
            name_list = []
            for item in history:
                name = item.get('name', 'N/A')
                changed_time = item.get('changedToAt', 'N/A')
                if changed_time != 'N/A':
                    # 将时间戳转换为可读格式
                    try:
                        import datetime
                        readable_time = datetime.datetime.fromtimestamp(changed_time/1000).strftime('%Y-%m-%d %H:%M:%S')
                        name_list.append(f"  - {name} (变更为: {readable_time})")
                    except:
                        name_list.append(f"  - {name} (时间戳: {changed_time})")
                else:
                    name_list.append(f"  - {name}")
            
            name_str = "\n".join(name_list)
            return f"[MC曾用名查询]\n当前用户名: {current_name}\nUUID: {uuid}\n历史用户名数: {name_num}\n历史用户名:\n{name_str}"

        elif command_name == "文本分析":
            if not data:
                return "文本分析失败"

            # 根据实际API响应数据结构进行格式化
            original_text = data.get('original_text', 'N/A')
            total_chars_unicode = data.get('total_chars_unicode', 'N/A')
            total_bytes = data.get('total_bytes', 'N/A')
            chinese_chars = data.get('chinese_chars', 'N/A')
            english_letters = data.get('english_letters', 'N/A')
            numbers = data.get('numbers', 'N/A')
            punctuation_marks = data.get('punctuation_marks', 'N/A')
            whitespace_chars = data.get('whitespace_chars', 'N/A')
            
            return f"[文本分析]\nUnicode字符数: {total_chars_unicode}\n字节数: {total_bytes}\n中文字符: {chinese_chars}\n英文字符: {english_letters}\n数字: {numbers}\n标点符号: {punctuation_marks}\n空白字符: {whitespace_chars}"

        elif command_name == "程序员历史上的今天":
            if not data or 'events' not in data:
                return "程序员历史上的今天查询失败"

            date = data.get('date', 'N/A')
            events = data.get('events', [])
            message = data.get('message', 'N/A')

            event_list = []
            for i, event in enumerate(events[:5], 1):  # 只显示前5个事件
                year = event.get('year', 'N/A')
                title = event.get('title', 'N/A')
                desc = event.get('desc', 'N/A')
                event_list.append(f"{i}. [{year}] {title}\n   {desc}")

            event_str = "\n".join(event_list)
            return f"[程序员历史上的今天]\n日期: {date}\n今日事件:\n{event_str}"

        elif command_name == "网页元数据提取":
            if not data or 'page_url' not in data:
                return "网页元数据提取失败"

            page_url = data.get('page_url', 'N/A')
            title = data.get('title', 'N/A')
            description = data.get('description', 'N/A')
            keywords = data.get('keywords', [])
            favicon_url = data.get('favicon_url', 'N/A')
            language = data.get('language', 'N/A')
            author = data.get('author', 'N/A')
            published_time = data.get('published_time', 'N/A')
            canonical_url = data.get('canonical_url', 'N/A')
            generator = data.get('generator', 'N/A')
            open_graph = data.get('open_graph', {})
            
            keywords_str = ", ".join(keywords[:5]) if keywords else "N/A"  # 只显示前5个关键词

            og_info = ""
            if open_graph:
                og_title = open_graph.get('title', 'N/A')
                og_description = open_graph.get('description', 'N/A')
                og_image = open_graph.get('image', 'N/A')
                og_info = f"\nOG标题: {og_title}\nOG描述: {og_description}\nOG图片: {og_image}"

            return f"[网页元数据提取]\n页面URL: {page_url}\n标题: {title}\n描述: {description}\n关键词: {keywords_str}\n语言: {language}\n作者: {author}\n发布时间: {published_time}\n规范URL: {canonical_url}\n生成器: {generator}\nFavicon: {favicon_url}{og_info}"

        elif command_name == "网页图片提取":
            if not data or 'url' not in data:
                return "网页图片提取失败"

            url = data.get('url', 'N/A')
            count = data.get('count', 0)
            images = data.get('images', [])

            image_list = images[:5]  # 只显示前5张图片
            image_str = "\n".join([f"- {img}" for img in image_list])

            return f"[网页图片提取]\n网页URL: {url}\n图片总数: {count}\n前几张图片:\n{image_str}"

        elif command_name == "时间戳转换":
            if not data or 'datetime' not in data:
                return "时间戳转换失败"
            
            datetime_str = data.get('datetime', 'N/A')
            timestamp = data.get('timestamp', 'N/A')
            
            return f"[时间戳转换]\n日期时间: {datetime_str}\n时间戳: {timestamp}"

        elif command_name == "JSON格式化":
            if not data or 'content' not in data:
                return "JSON格式化失败"

            formatted_content = data.get('content', 'N/A')

            return f"[JSON格式化]\n{formatted_content}"

        elif command_name == "无损压缩图片":
            return "[无损压缩图片]\n图片已压缩并发送"

        elif command_name == "生成你们怎么不说话了表情包":
            return "[生成你们怎么不说话了表情包]\n表情包已生成并发送"

        elif command_name == "SVG转图片":
            return "[SVG转图片]\n图片已转换并发送"

        else:
            # 默认格式化，直接返回原始数据的字符串表示
            if data:
                # 尝试找出一些通用字段进行格式化
                if 'message' in data:
                    return f"[UAPI响应]\n{data['message']}"
                elif 'text' in data:
                    return f"[UAPI响应]\n{data['text']}"
                elif 'result' in data:
                    return f"[UAPI响应]\n{data['result']}"
                else:
                    return f"[UAPI响应]\n{str(data)}"
            else:
                return "[UAPI响应]\n无数据返回"

    except Exception as e:
        logging.error(f"格式化UAPI响应失败: {e}")
        return f"UAPI信息格式化错误: {str(e)}"


# UAPI命令帮助信息字典
UAPI_COMMAND_HELP = {
    "B站直播间查询": """【B站直播间查询 帮助】
功能：查询B站直播间信息
用法：B站直播间查询 [mid|room_id] [ID值]
示例：B站直播间查询 672328094
示例：B站直播间查询 room_id 22637261
参数说明：
- mid: B站用户ID
- room_id: 直播间ID""",

    "B站用户查询": """【B站用户查询 帮助】
功能：查询B站用户信息
用法：B站用户查询 [UID]
示例：B站用户查询 483307278
参数说明：
- UID: B站用户唯一标识符""",

    "B站投稿查询": """【B站投稿查询 帮助】
功能：查询B站用户投稿视频
用法：B站投稿查询 [mid]
示例：B站投稿查询 483307278
参数说明：
- mid: B站用户ID""",

    "GitHub仓库查询": """【GitHub仓库查询 帮助】
功能：查询GitHub仓库信息
用法：GitHub仓库查询 [owner] [repo]
示例：GitHub仓库查询 torvalds linux
参数说明：
- owner: 仓库拥有者
- repo: 仓库名称""",

    "热榜查询": """【热榜查询 帮助】
功能：查询各平台热榜
用法：热榜查询 [type]
示例：热榜查询 weibo
示例：热榜查询 zhihu
参数说明：
- type: 平台类型
支持平台：weibo, zhihu, baidu, toutiao, douban-movie, tieba, acfun, bilibili等""",

    "世界时间查询": """【世界时间查询 帮助】
功能：查询世界时间
用法：世界时间查询 [city]
示例：世界时间查询 Asia/Shanghai
示例：世界时间查询 Europe/London
参数说明：
- city: 时区名称（IANA标准）""",

    "天气查询": """【天气查询 帮助】
功能：查询天气信息
用法：天气查询 [city]
示例：天气查询 北京
示例：天气查询 上海
参数说明：
- city: 城市名称""",

    "手机归属地查询": """【手机归属地查询 帮助】
功能：查询手机号归属地
用法：手机归属地查询 [phone]
示例：手机归属地查询 13800138000
参数说明：
- phone: 11位手机号码""",

    "随机数生成": """【随机数生成 帮助】
功能：生成随机数
用法：随机数生成 [min] [max] [count]
示例：随机数生成 1 100 5
示例：随机数生成 10 20
参数说明：
- min: 最小值
- max: 最大值
- count: 生成数量""",

    "ICP备案查询": """【ICP备案查询 帮助】
功能：查询域名ICP备案信息
用法：ICP备案查询 [domain]
示例：ICP备案查询 baidu.com
参数说明：
- domain: 域名""",

    "IP信息查询": """【IP信息查询 帮助】
功能：查询IP地理位置
用法：IP信息查询 [ip|domain]
示例：IP信息查询 8.8.8.8
示例：IP信息查询 baidu.com
参数说明：
- ip|domain: IP地址或域名""",

    "WHOIS查询": """【WHOIS查询 帮助】
功能：查询域名WHOIS信息
用法：WHOIS查询 [domain] [format]
示例：WHOIS查询 google.com
示例：WHOIS查询 google.com json
参数说明：
- domain: 域名
- format: 格式（text/json）""",

    "Ping主机": """【Ping主机 帮助】
功能：Ping测试主机连通性
用法：Ping主机 [host]
示例：Ping主机 google.com
示例：Ping主机 8.8.8.8
参数说明：
- host: 主机地址或IP""",

    "DNS查询": """【DNS查询 帮助】
功能：查询DNS记录
用法：DNS查询 [domain] [type]
示例：DNS查询 google.com A
示例：DNS查询 google.com MX
参数说明：
- domain: 域名
- type: 记录类型（A, AAAA, CNAME, MX, NS, TXT）""",

    "URL可访问性": """【URL可访问性 帮助】
功能：检查URL可访问性
用法：URL可访问性 [url]
示例：URL可访问性 https://www.baidu.com
参数说明：
- url: 完整URL地址""",

    "端口扫描": """【端口扫描 帮助】
功能：扫描端口状态
用法：端口扫描 [host] [port] [protocol]
示例：端口扫描 127.0.0.1 80
示例：端口扫描 google.com 443 tcp
参数说明：
- host: 主机地址
- port: 端口号
- protocol: 协议（tcp/udp）""",

    "MC服务器查询": """【MC服务器查询 帮助】
功能：查询Minecraft服务器状态
用法：MC服务器查询 [server]
示例：MC服务器查询 mc.hypixel.net
示例：MC服务器查询 localhost:25565
参数说明：
- server: 服务器地址""",

    "Steam用户查询": """【Steam用户查询 帮助】
功能：查询Steam用户信息
用法：Steam用户查询 [steamid]
示例：Steam用户查询 76561197960435530
参数说明：
- steamid: Steam用户ID""",

    "Epic免费游戏": """【Epic免费游戏 帮助】
功能：查询Epic免费游戏
用法：Epic免费游戏
示例：Epic免费游戏""",

    "MC玩家查询": """【MC玩家查询 帮助】
功能：查询Minecraft玩家信息
用法：MC玩家查询 [username]
示例：MC玩家查询 Notch
参数说明：
- username: 玩家名""",

    "MC曾用名查询": """【MC曾用名查询 帮助】
功能：查询Minecraft玩家曾用名
用法：MC曾用名查询 [name|uuid]
示例：MC曾用名查询 Notch
参数说明：
- name|uuid: 玩家名或UUID""",

    "文本分析": """【文本分析 帮助】
功能：分析文本统计信息
用法：文本分析 [text]
示例：文本分析 这是一段测试文本
参数说明：
- text: 要分析的文本""",

    "MD5哈希": """【MD5哈希 帮助】
功能：计算MD5哈希值
用法：MD5哈希 [text]
示例：MD5哈希 hello world
参数说明：
- text: 要计算哈希的文本""",



    "MD5校验": """【MD5校验 帮助】
功能：校验MD5哈希值
用法：MD5校验 [text] [hash]
示例：MD5校验 hello world 5d41402abc4b2a76b9719d911017c592
参数说明：
- text: 原文
- hash: MD5哈希值""",

    "Base64编码": """【Base64编码 帮助】
功能：Base64编码
用法：Base64编码 [text]
示例：Base64编码 hello world
参数说明：
- text: 要编码的文本""",

    "Base64解码": """【Base64解码 帮助】
功能：Base64解码
用法：Base64解码 [text]
示例：Base64解码 aGVsbG8gd29ybGQ=
参数说明：
- text: 要解码的Base64文本""",

    "AES加密": """【AES加密 帮助】
功能：AES加密
用法：AES加密 [key] [text]
示例：AES加密 mypassword hello world
参数说明：
- key: 加密密钥
- text: 要加密的文本""",

    "AES解密": """【AES解密 帮助】
功能：AES解密
用法：AES解密 [key] [ciphertext] [nonce]
示例：AES解密 mypassword encrypted_text nonce123
参数说明：
- key: 解密密钥
- ciphertext: 密文
- nonce: 随机数""",

    "AES高级加密": """【AES高级加密 帮助】
功能：高级AES加密
用法：AES高级加密 [key] [text] [mode] [padding]
示例：AES高级加密 mypassword hello GCM PKCS7
参数说明：
- key: 加密密钥
- text: 要加密的文本
- mode: 加密模式
- padding: 填充方式""",

    "AES高级解密": """【AES高级解密 帮助】
功能：高级AES解密
用法：AES高级解密 [key] [ciphertext] [mode] [padding]
示例：AES高级解密 mypassword encrypted GCM NONE
参数说明：
- key: 解密密钥
- ciphertext: 密文
- mode: 加密模式
- padding: 填充方式""",

    "格式转换": """【格式转换 帮助】
功能：文本格式转换
用法：格式转换 [text] [from] [to]
示例：格式转换 hello plain base64
参数说明：
- text: 要转换的文本
- from: 源格式
- to: 目标格式
支持格式：plain, base64, hex, url, html, unicode, binary, md5, sha1, sha256, sha512""",

    "随机图片": """【随机图片 帮助】
功能：获取随机图片
用法：随机图片 [category] [type]
示例：随机图片 acg
示例：随机图片 landscape
参数说明：
- category: 图片类别
- type: 图片子类别
支持类别：acg, landscape, anime, pc_wallpaper, mobile_wallpaper, ai_drawing, bq, furry等""",

    "答案之书": """【答案之书 帮助】
功能：获取神秘答案
用法：答案之书 [question]
示例：答案之书 我今天会有好运吗？
参数说明：
- question: 问题""",



    "随机字符串": """【随机字符串 帮助】
功能：生成随机字符串
用法：随机字符串 [length] [type]
示例：随机字符串 16
示例：随机字符串 32 alphanumeric
参数说明：
- length: 字符串长度
- type: 字符类型（numeric, lower, upper, alpha, alphanumeric, hex）""",

    "必应壁纸": """【必应壁纸 帮助】
功能：获取必应每日壁纸
用法：必应壁纸
示例：必应壁纸""",

    "上传图片": """【上传图片 帮助】
功能：上传Base64图片
用法：上传图片 [base64_data]
示例：上传图片 iVBORw0KGgoAAAANSUE...
参数说明：
- base64_data: Base64编码的图片数据""",

    "图片转Base64": """【图片转Base64 帮助】
功能：图片转Base64
用法：图片转Base64 [url]
示例：图片转Base64 https://example.com/image.jpg
参数说明：
- url: 图片URL""",

    "生成二维码": """【生成二维码 帮助】
功能：生成二维码
用法：生成二维码 [text] [size]
示例：生成二维码 https://www.bilibili.com
示例：生成二维码 Hello 512
参数说明：
- text: 二维码内容
- size: 二维码尺寸""",

    "GrAvatar头像": """【GrAvatar头像 帮助】
功能：获取GrAvatar头像
用法：GrAvatar头像 [email]
示例：GrAvatar头像 user@example.com
参数说明：
- email: 邮箱地址""",

    "摸摸头": """【摸摸头 帮助】
功能：生成摸摸头GIF
用法：摸摸头 [qq]
示例：摸摸头 10001
参数说明：
- qq: QQ号码""",

    "生成摸摸头GIF POST": """【生成摸摸头GIF POST 帮助】
功能：通过图片URL生成摸摸头GIF
用法：生成摸摸头GIF POST [image_url]
示例：生成摸摸头GIF POST https://example.com/image.jpg
参数说明：
- image_url: 图片URL""",

    "无损压缩图片": """【无损压缩图片 帮助】
功能：无损压缩图片
用法：无损压缩图片 [file_path] [level] [format]
示例：无损压缩图片 image.jpg
示例：无损压缩图片 image.jpg 2 png
参数说明：
- file_path: 图片文件路径
- level: 压缩等级(1-5，默认3)
- format: 输出格式(png/jpeg，默认png)""",

    "SVG转图片": """【SVG转图片 帮助】
功能：将SVG矢量图转换为光栅图片
用法：SVG转图片 [file_path] [format] [width] [height] [quality]
示例：SVG转图片 input.svg
示例：SVG转图片 input.svg png 800 600 90
参数说明：
- file_path: SVG文件路径
- format: 输出格式(png,jpeg,jpg,gif,tiff,bmp，默认png)
- width: 输出宽度(可选)
- height: 输出高度(可选)
- quality: JPEG质量(1-100，默认90)""",

    "生成你们怎么不说话了表情包": """【生成你们怎么不说话了表情包 帮助】
功能：生成梗图表情包
用法：生成你们怎么不说话了表情包 [top_text] [bottom_text]
示例：生成你们怎么不说话了表情包 玩UAPI 们不要玩UAPI了
参数说明：
- top_text: 上方文字
- bottom_text: 下方文字""",

    "SVG转图片": """【SVG转图片 帮助】
功能：SVG转图片
用法：SVG转图片 [file_path]
示例：SVG转图片 input.svg
参数说明：
- file_path: SVG文件路径""",

    "翻译": """【翻译 帮助】
功能：文本翻译
用法：翻译 [to_lang] [text]
示例：翻译 zh-CHS hello world
示例：翻译 en 你好世界
参数说明：
- to_lang: 目标语言代码
- text: 要翻译的文本
支持语言：zh-CHS, zh-CHT, en, ja, ko, fr, de, es, ru, ar等""",

    "一言": """【一言 帮助】
功能：获取随机诗词/名言
用法：一言
示例：一言""",

    "网页元数据提取": """【网页元数据提取 帮助】
功能：提取网页元数据
用法：网页元数据提取 [url]
示例：网页元数据提取 https://www.bilibili.com
参数说明：
- url: 网页URL""",

    "网页图片提取": """【网页图片提取 帮助】
功能：提取网页图片
用法：网页图片提取 [url]
示例：网页图片提取 https://cn.bing.com/
参数说明：
- url: 网页URL""",

    "时间戳转换": """【时间戳转换 帮助】
功能：时间戳与日期转换
用法：时间戳转换 [time]
示例：时间戳转换 1698380645
示例：时间戳转换 2023-10-27 15:04:05
参数说明：
- time: 时间戳或日期字符串""",

    "JSON格式化": """【JSON格式化 帮助】
功能：JSON格式化
用法：JSON格式化 [content]
示例：JSON格式化 {"name":"test","value":123}
参数说明：
- content: JSON内容""",

    "每日新闻图": """【每日新闻图 帮助】
功能：获取每日新闻图
用法：每日新闻图
示例：每日新闻图""",

    "程序员历史上的今天": """【程序员历史上的今天 帮助】
功能：查询今天的历史事件
用法：程序员历史上的今天
示例：程序员历史上的今天""",

    "程序员历史事件": """【程序员历史事件 帮助】
功能：查询指定日期历史事件
用法：程序员历史事件 [month] [day]
示例：程序员历史事件 4 1
参数说明：
- month: 月份
- day: 日期"""
}


async def handle_uapi_command(command_name: str, args: List[str], group_id: str, config: Dict[str, Any], user_id: str = None) -> Optional[str]:
    """
    处理UAPI命令
    :param command_name: 命令名称
    :param args: 参数列表
    :param group_id: 群ID
    :param config: 配置
    :param user_id: 用户ID
    :return: 格式化的响应消息
    """
    try:
        # 检查UAPI是否启用
        uapi_config = config.get('uapi', {})
        if not uapi_config:
            return "UAPI功能未配置，请检查config.json中的uapi配置"

        # 检查是否请求帮助
        if args and (args[0] == "-h" or args[0] == "-help"):
            help_text = UAPI_COMMAND_HELP.get(command_name, f"【{command_name} 帮助】\n未找到该命令的帮助信息")
            return help_text

        # 创建UAPI客户端
        api = UApiClient(config)

        # 根据命令名称处理不同的UAPI请求
        if command_name == "B站直播间查询":
            if not args or (not args[0].isdigit() and not (len(args) > 1 and args[1].isdigit())):
                return "请提供B站用户mid或直播间room_id\n示例: /B站直播间查询 672328094 或 /B站直播间查询 room_id 22637261"

            mid = None
            room_id = None

            if len(args) == 1:
                # 可能是mid或room_id
                if args[0].isdigit():
                    # 判断长度来决定是mid还是room_id
                    if len(args[0]) > 8:  # 通常room_id更长
                        room_id = args[0]
                    else:
                        mid = args[0]
            elif len(args) >= 2:
                if args[0] in ['mid', 'room_id']:
                    if args[0] == 'mid':
                        mid = args[1]
                    else:
                        room_id = args[1]
                else:
                    # 如果第一个参数不是mid或room_id，则认为是直接传递的ID
                    if args[0].isdigit():
                        if len(args[0]) > 8:
                            room_id = args[0]
                        else:
                            mid = args[0]
                    if args[1].isdigit():
                        if len(args[1]) > 8:
                            room_id = args[1]
                        else:
                            mid = args[1]

            result = await api.get_bilibili_liveroom(mid=mid, room_id=room_id)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "B站直播间查询失败"

        elif command_name == "B站用户查询":
            if not args or not args[0].isdigit():
                return "请提供B站用户UID\n示例: /B站用户查询 483307278"

            uid = args[0]
            result = await api.get_bilibili_userinfo(uid=uid)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "B站用户查询失败"

        elif command_name == "B站投稿查询":
            if not args or not args[0].isdigit():
                return "请提供B站用户mid\n示例: /B站投稿查询 483307278"
            
            mid = args[0]
            result = await api.get_bilibili_archives(mid=mid)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "B站投稿查询失败"

        elif command_name == "GitHub仓库查询":
            if not args or len(args) < 2:
                return "请提供GitHub仓库的owner和repo\n示例: /GitHub仓库查询 torvalds linux"
            
            owner = args[0]
            repo = args[1]
            repo_full = f"{owner}/{repo}"
            result = await api.get_github_repo(repo=repo_full)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "GitHub仓库查询失败"

        elif command_name == "热榜查询":
            if not args or not args[0]:
                return "请提供热榜类型\n示例: /热榜查询 weibo"
            
            type_param = args[0]
            result = await api.get_hotboard(type_param=type_param)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "热榜查询失败"

        elif command_name == "世界时间查询":
            if not args or not args[0]:
                return "请提供时区名称\n示例: /世界时间查询 Asia/Shanghai"
            
            city = args[0]
            result = await api.get_worldtime(city=city)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "世界时间查询失败"

        elif command_name == "天气查询":
            if not args or not args[0]:
                return "请提供城市名称\n示例: /天气查询 北京"
            
            city = args[0]
            result = await api.get_weather(city=city)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "天气查询失败"

        elif command_name == "手机归属地查询":
            if not args or not args[0] or not args[0].isdigit() or len(args[0]) != 11:
                return "请提供11位手机号码\n示例: /手机归属地查询 13800138000"
            
            phone = args[0]
            result = await api.get_phoneinfo(phone=phone)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "手机归属地查询失败"

        elif command_name == "随机数生成":
            min_val = 1
            max_val = 100
            count = 1
            
            if args:
                try:
                    if len(args) >= 1:
                        min_val = int(args[0])
                    if len(args) >= 2:
                        max_val = int(args[1])
                    if len(args) >= 3:
                        count = int(args[2])
                except ValueError:
                    return "参数必须是数字\n示例: /随机数生成 1 100 5"
            
            result = await api.get_randomnumber(min_val=min_val, max_val=max_val, count=count)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "随机数生成失败"

        elif command_name == "ICP备案查询":
            if not args or not args[0]:
                return "请提供域名\n示例: /ICP备案查询 baidu.com"
            
            domain = args[0]
            result = await api.get_icp(domain=domain)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "ICP备案查询失败"

        elif command_name == "IP信息查询":
            if not args or not args[0]:
                return "请提供IP地址或域名\n示例: /IP信息查询 8.8.8.8"
            
            ip = args[0]
            result = await api.get_ipinfo(ip=ip)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "IP信息查询失败"

        elif command_name == "一言":
            result = await api.get_saying()
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "获取一言失败"

        elif command_name == "随机图片":
            category = args[0] if args else None
            result = await api.get_random_image(category=category)
            if result:
                # 返回图片二进制数据
                return result
            else:
                return "随机图片获取失败"

        elif command_name == "答案之书":
            if not args:
                return "请提供问题\n示例: /答案之书 我今天会有好运吗？"
            
            question = " ".join(args)
            result = await api.get_answerbook_ask(question=question)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "答案之书查询失败"



        elif command_name == "随机字符串":
            length = 16
            type_param = "alphanumeric"
            
            if args:
                try:
                    if len(args) >= 1:
                        length = int(args[0])
                    if len(args) >= 2:
                        type_param = args[1]
                except ValueError:
                    return "长度参数必须是数字\n示例: /随机字符串 32 alphanumeric"
            
            result = await api.get_random_string(length=length, type_param=type_param)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "随机字符串生成失败"

        elif command_name == "必应壁纸":
            result = await api.get_bing_daily()
            if result:
                return result  # 返回图片二进制数据
            else:
                return "必应壁纸获取失败"

        elif command_name == "生成二维码":
            if not args:
                return "请提供要生成二维码的文本\n示例: /生成二维码 https://www.bilibili.com"
            
            text = " ".join(args)
            result = await api.get_image_qrcode(text=text)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "二维码生成失败"

        elif command_name == "GrAvatar头像":
            if not args or not args[0]:
                return "请提供邮箱地址\n示例: /GrAvatar头像 user@example.com"

            email = args[0]
            result = await api.get_avatar_gravatar(email=email)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "GrAvatar头像获取失败"

        elif command_name == "摸摸头":
            if not args or not args[0].isdigit():
                return "请提供QQ号码\n示例: /摸摸头 10001"

            qq = args[0]
            result = await api.get_image_motou(qq=qq)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "摸摸头GIF生成失败"

        elif command_name == "每日新闻图":
            result = await api.get_daily_news_image()
            if result:
                return result  # 返回图片二进制数据
            else:
                return "每日新闻图获取失败"

        elif command_name == "翻译":
            if not args or len(args) < 2:
                return "请提供目标语言和要翻译的文本\n示例: /翻译 zh-CHS hello world"

            to_lang = args[0]
            text = " ".join(args[1:])
            result = await api.post_translate_text(to_lang=to_lang, text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "翻译失败"

        elif command_name == "程序员历史上的今天":
            result = await api.get_history_programmer_today()
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "程序员历史上的今天查询失败"

        elif command_name == "程序员历史事件":
            if not args or len(args) < 2:
                return "请提供月份和日期\n示例: /程序员历史事件 4 1"
            
            try:
                month = int(args[0])
                day = int(args[1])
                
                result = await api.get_history_programmer(month=month, day=day)
                if result:
                    return format_uapi_response(command_name, result, config)
                else:
                    return "程序员历史事件查询失败"
            except ValueError:
                return "月份和日期必须是数字\n示例: /程序员历史事件 4 1"

        elif command_name == "WHOIS查询":
            if not args or not args[0]:
                return "请提供域名\n示例: /WHOIS查询 google.com"
            
            domain = args[0]
            format_param = args[1] if len(args) > 1 else "text"
            
            result = await api.get_whois(domain=domain, format_param=format_param)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "WHOIS查询失败"

        elif command_name == "Ping主机":
            if not args or not args[0]:
                return "请提供主机地址\n示例: /Ping主机 google.com"
            
            host = args[0]
            result = await api.get_ping(host=host)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "Ping主机失败"

        elif command_name == "DNS查询":
            if not args or not args[0]:
                return "请提供域名\n示例: /DNS查询 google.com"
            
            domain = args[0]
            type_param = args[1] if len(args) > 1 else "A"
            
            result = await api.get_dns(domain=domain, type_param=type_param)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "DNS查询失败"

        elif command_name == "URL可访问性":
            if not args or not args[0]:
                return "请提供URL\n示例: /URL可访问性 https://www.baidu.com"
            
            url = args[0]
            result = await api.get_urlstatus(url=url)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "URL可访问性检查失败"

        elif command_name == "端口扫描":
            if not args or len(args) < 2:
                return "请提供主机和端口\n示例: /端口扫描 127.0.0.1 80"
            
            host = args[0]
            try:
                port = int(args[1])
                protocol = args[2] if len(args) > 2 else "tcp"
                
                result = await api.get_portscan(host=host, port=port, protocol=protocol)
                if result:
                    return format_uapi_response(command_name, result, config)
                else:
                    return "端口扫描失败"
            except ValueError:
                return "端口号必须是数字\n示例: /端口扫描 127.0.0.1 80"

        elif command_name == "MC服务器查询":
            if not args or not args[0]:
                return "请提供服务器地址\n示例: /MC服务器查询 mc.hypixel.net"
            
            server = args[0]
            result = await api.get_minecraft_serverstatus(server=server)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "MC服务器查询失败"

        elif command_name == "Steam用户查询":
            if not args or not args[0]:
                return "请提供Steam ID\n示例: /Steam用户查询 76561197960435530"
            
            steamid = args[0]
            key = args[1] if len(args) > 1 else None
            
            result = await api.get_steam_summary(steamid=steamid, key=key)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "Steam用户查询失败"

        elif command_name == "Epic免费游戏":
            result = await api.get_epic_free()
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "Epic免费游戏查询失败"

        elif command_name == "MC玩家查询":
            if not args or not args[0]:
                return "请提供MC用户名\n示例: /MC玩家查询 Notch"
            
            username = args[0]
            result = await api.get_minecraft_userinfo(username=username)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "MC玩家查询失败"

        elif command_name == "MC曾用名查询":
            if not args or not args[0]:
                return "请提供MC用户名或UUID\n示例: /MC曾用名查询 Notch"
            
            name_or_uuid = args[0]
            result = await api.get_minecraft_historyid(name=name_or_uuid)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "MC曾用名查询失败"

        elif command_name == "文本分析":
            if not args:
                return "请提供要分析的文本\n示例: /文本分析 这是一段测试文本"
            
            text = " ".join(args)
            result = await api.post_text_analyze(text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "文本分析失败"

        elif command_name == "MD5哈希":
            if not args:
                return "请提供要计算MD5的文本\n示例: /MD5哈希 hello world"
            
            text = " ".join(args)
            result = await api.get_text_md5(text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "MD5哈希计算失败"



        elif command_name == "MD5校验":
            if not args or len(args) < 2:
                return "请提供文本和MD5哈希值\n示例: /MD5校验 hello world 5d41402abc4b2a76b9719d911017c592"
            
            text = args[0]
            hash_val = args[1]
            result = await api.post_text_md5_verify(text=text, hash_val=hash_val)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "MD5校验失败"

        elif command_name == "Base64编码":
            if not args:
                return "请提供要编码的文本\n示例: /Base64编码 hello world"
            
            text = " ".join(args)
            result = await api.post_text_base64_encode(text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "Base64编码失败"

        elif command_name == "Base64解码":
            if not args:
                return "请提供要解码的Base64文本\n示例: /Base64解码 aGVsbG8gd29ybGQ="
            
            text = " ".join(args)
            result = await api.post_text_base64_decode(text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "Base64解码失败"

        elif command_name == "AES加密":
            if not args or len(args) < 2:
                return "请提供密钥和要加密的文本\n示例: /AES加密 mysecretkey hello world"
            
            key = args[0]
            text = " ".join(args[1:])
            result = await api.post_text_aes_encrypt(key=key, text=text)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "AES加密失败"

        elif command_name == "AES解密":
            if not args or len(args) < 3:
                return "请提供密钥、密文和nonce\n示例: /AES解密 mysecretkey encrypted_text nonce123"
            
            key = args[0]
            text = args[1]
            nonce = args[2]
            result = await api.post_text_aes_decrypt(key=key, text=text, nonce=nonce)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "AES解密失败"

        elif command_name == "AES高级加密":
            if not args or len(args) < 2:
                return "请提供密钥和要加密的文本\n示例: /AES高级加密 mysecretkey hello world"
            
            key = args[0]
            text = " ".join(args[1:])
            mode = args[2] if len(args) > 2 else "GCM"
            padding = args[3] if len(args) > 3 else "PKCS7"
            iv = args[4] if len(args) > 4 else None
            output_format = args[5] if len(args) > 5 else "base64"
            
            result = await api.post_text_aes_encrypt_advanced(text=text, key=key, mode=mode, 
                                                            padding=padding, iv=iv, 
                                                            output_format=output_format)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "AES高级加密失败"

        elif command_name == "AES高级解密":
            if not args or len(args) < 3:
                return "请提供密钥、密文和模式\n示例: /AES高级解密 mysecretkey encrypted_text GCM"
            
            key = args[0]
            text = args[1]
            mode = args[2] if len(args) > 2 else "GCM"
            padding = args[3] if len(args) > 3 else "NONE"
            iv = args[4] if len(args) > 4 else None
            
            result = await api.post_text_aes_decrypt_advanced(text=text, key=key, mode=mode, 
                                                            padding=padding, iv=iv)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "AES高级解密失败"

        elif command_name == "格式转换":
            if not args or len(args) < 3:
                return "请提供文本、源格式和目标格式\n示例: /格式转换 hello world plain base64"
            
            text = args[0]
            from_format = args[1]
            to_format = args[2]
            options = {}
            if len(args) > 3:
                # 解析选项参数
                for opt in args[3:]:
                    if '=' in opt:
                        key, value = opt.split('=', 1)
                        options[key] = value
            
            result = await api.post_text_convert(text=text, from_format=from_format, 
                                               to_format=to_format, options=options)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "格式转换失败"

        elif command_name == "网页元数据提取":
            if not args or not args[0]:
                return "请提供网页URL\n示例: /网页元数据提取 https://www.bilibili.com"
            
            url = args[0]
            result = await api.get_webparse_metadata(url=url)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "网页元数据提取失败"

        elif command_name == "网页图片提取":
            if not args or not args[0]:
                return "请提供网页URL\n示例: /网页图片提取 https://www.bilibili.com"
            
            url = args[0]
            result = await api.get_webparse_extractimages(url=url)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "网页图片提取失败"

        elif command_name == "时间戳转换":
            if not args or not args[0]:
                return "请提供时间戳或日期\n示例: /时间戳转换 1698380645 或 /时间戳转换 2023-10-27 15:04:05"
            
            time_param = args[0]
            result = await api.get_convert_unixtime(time_param=time_param)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "时间戳转换失败"

        elif command_name == "JSON格式化":
            if not args:
                return "请提供要格式化的JSON内容\n示例: /JSON格式化 {\"name\":\"test\",\"value\":123}"
            
            content = " ".join(args)
            result = await api.post_convert_json(content=content)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "JSON格式化失败"

        elif command_name == "无损压缩图片":
            if not args or not args[0]:
                return "请提供图片文件路径\n示例: /无损压缩图片 image.jpg"
            
            image_path = args[0]
            level = int(args[1]) if len(args) > 1 else 3
            format_param = args[2] if len(args) > 2 else "png"
            
            result = await api.post_image_compress(file_path=image_path, level=level, format_param=format_param)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "无损压缩图片失败"

        elif command_name == "生成你们怎么不说话了表情包":
            if not args or len(args) < 2:
                return "请提供顶部和底部文字\n示例: /生成你们怎么不说话了表情包 玩UAPI 们不要玩UAPI了"
            
            top_text = args[0]
            bottom_text = " ".join(args[1:])
            result = await api.post_image_speechless(top_text=top_text, bottom_text=bottom_text)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "表情包生成失败"

        elif command_name == "SVG转图片":
            if not args or not args[0]:
                return "请提供SVG文件路径\n示例: /SVG转图片 input.svg"

            svg_path = args[0]
            format_param = args[1] if len(args) > 1 else "png"
            width = int(args[2]) if len(args) > 2 and args[2].isdigit() else None
            height = int(args[3]) if len(args) > 3 and args[3].isdigit() else None
            quality = int(args[4]) if len(args) > 4 and args[4].isdigit() else 90

            result = await api.post_image_svg(file_path=svg_path, format_param=format_param, 
                                           width=width, height=height, quality=quality)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "SVG转图片失败"

        elif command_name == "上传图片":
            if not args or not args[0]:
                return "请提供Base64编码的图片数据\n示例: /上传图片 iVBORw0KGgoAAAANSUE..."

            image_data = args[0]
            result = await api.post_image_frombase64(image_data=image_data)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "上传图片失败"

        elif command_name == "图片转Base64":
            if not args or not args[0]:
                return "请提供图片URL\n示例: /图片转Base64 https://example.com/image.jpg"

            url = args[0]
            result = await api.get_image_tobase64(url=url)
            if result:
                return format_uapi_response(command_name, result, config)
            else:
                return "图片转Base64失败"

        elif command_name == "生成摸摸头GIF POST":
            if not args or not args[0]:
                return "请提供图片URL\n示例: /生成摸摸头GIF POST https://example.com/image.jpg"

            image_url = args[0]
            bg_color = args[1] if len(args) > 1 else "transparent"
            
            result = await api.post_image_motou(image_url=image_url, bg_color=bg_color)
            if result:
                return result  # 返回图片二进制数据
            else:
                return "生成摸摸头GIF POST失败"

        else:
            return f"未知的UAPI命令: {command_name}"

    except Exception as e:
        logging.error(f"处理UAPI命令异常: {e}")
        return f"UAPI命令处理出错: {str(e)}"