import requests
import json
from datetime import datetime
from typing import Optional, Dict, List
import re
from bs4 import BeautifulSoup

class CMWeatherAlarmClient:
    """
    用于从中国气象局获取气象预警数据的客户端
    """

    def __init__(self):
        self.base_url = "https://www.nmc.cn/rest/findAlarm"
        self.detail_base_url = "https://www.nmc.cn"
        self.session = requests.Session()
        # 设置模拟浏览器请求的头部
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.nmc.cn/publish/alarm.html'
        })
    
    def get_weather_alarms(
        self, 
        page_no: int = 1, 
        page_size: int = 10
    ) -> Dict:
        """
        获取气象预警数据
        
        Args:
            page_no: 页码（从1开始）
            page_size: 每页记录数（默认10）
        
        Returns:
            包含预警数据的字典
        """
        params = {
            'pageNo': page_no,
            'pageSize': page_size
        }
        
        try:
            response = self.session.get(self.base_url, params=params)
            response.raise_for_status()  # 为错误状态码引发异常
            
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"获取数据时出错: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"解码JSON响应时出错: {e}")
            return {}
    
    def get_latest_alarms(self, count: int = 10) -> List[Dict]:
        """
        Get the latest weather alarms
        
        Args:
            count: Number of latest alarms to retrieve
        
        Returns:
            List of alarm dictionaries
        """
        # Calculate page size and number of pages needed
        page_size = min(count, 30)  # Max page size is typically 30
        result = []
        
        page_no = 1
        while len(result) < count:
            data = self.get_weather_alarms(page_no=page_no, page_size=page_size)
            
            if 'data' in data and 'page' in data['data']:
                alarms = data['data']['page']['list']
                
                for alarm in alarms:
                    if len(result) >= count:
                        break
                    result.append(alarm)
                
                # Check if we need more pages
                total_pages = data['data']['page'].get('totalPage', 1)
                if page_no >= total_pages:
                    break
                
                page_no += 1
            else:
                break  # No more data
        
        return result[:count]  # Return only the requested count

    def get_alarm_detail(self, alarm_url: str) -> Dict:
        """
        获取单个预警的详细内容

        Args:
            alarm_url: 预警详情页面的URL（可以是相对路径或完整URL）

        Returns:
            包含预警详细信息的字典
        """
        # 如果是相对路径，拼接完整URL
        if alarm_url.startswith('/'):
            full_url = self.detail_base_url + alarm_url
        else:
            full_url = alarm_url

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://www.nmc.cn/publish/alarm.html'
        }

        try:
            response = self.session.get(full_url, headers=headers)
            response.raise_for_status()
            response.encoding = 'utf-8'

            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找包含预警详情的元素
            # 根据之前的分析，预警详情通常在id为alarmtext的div中
            alarm_text_div = soup.find('div', id='alarmtext')
            
            detail_content = ""
            if alarm_text_div:
                # 提取预警详情内容
                detail_content = alarm_text_div.get_text(strip=True)
            else:
                # 如果没找到id为alarmtext的div，尝试其他可能的选择器
                # 查找包含预警相关内容的段落
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if '防御' in text or '预警' in text or '影响' in text:
                        detail_content = text
                        break

            # 尝试提取标题（如果页面标题不同于预警标题）
            page_title = ""
            title_tag = soup.find('title')
            if title_tag:
                page_title = title_tag.get_text().strip()

            return {
                'url': full_url,
                'title': page_title,
                'content': detail_content,
                'raw_html': str(alarm_text_div) if alarm_text_div else ""  # 保留原始HTML（如果找到的话）
            }

        except requests.exceptions.RequestException as e:
            print(f"获取预警详情时出错: {e}")
            return {}
        except Exception as e:
            print(f"解析预警详情页面时出错: {e}")
            return {}

    def get_alarm_detail_by_id(self, alertid: str, title: str = "", url: str = "") -> Dict:
        """
        通过预警ID获取预警详细内容
        
        Args:
            alertid: 预警ID
            title: 预警标题（可选）
            url: 预警URL（可选，如果不提供则根据ID构造）
            
        Returns:
            包含预警详细信息的字典
        """
        if not url:
            # 根据预警ID构造URL
            url = f"/publish/alarm/{alertid}.html"
        
        detail = self.get_alarm_detail(url)
        detail['alertid'] = alertid
        detail['original_title'] = title
        
        return detail


def main():
    """
    演示CMWeatherAlarmClient用法的主函数
    """
    client = CMWeatherAlarmClient()

    print("=== 获取最新气象预警 ===")
    latest_alarms = client.get_latest_alarms(count=5)

    if latest_alarms:
        print(f"找到 {len(latest_alarms)} 条最新预警:\n")
        for i, alarm in enumerate(latest_alarms, 1):
            print(f"{i}. 标题: {alarm['title']}")
            print(f"   发布时间: {alarm['issuetime']}")
            print(f"   预警ID: {alarm['alertid']}")
            print(f"   URL: https://www.nmc.cn{alarm['url']}")
            print(f"   图片: {alarm['pic']}")
            
            # 获取第一条预警的详细内容作为演示
            if i == 1:
                print("   正在获取详细内容...")
                detail = client.get_alarm_detail(alarm['url'])
                if detail and detail.get('content'):
                    print(f"   详情: {detail['content'][:100]}...")
            
            print("-" * 80)
    else:
        print("未找到预警或发生错误。")


if __name__ == "__main__":
    main()