import base64
import aiohttp
import logging

SESSION = None
HEADERS = {}

def init_sender(url, token):
    global SESSION, HEADERS
    SESSION = aiohttp.ClientSession(base_url=url)
    if token:
        HEADERS['Authorization'] = f'Bearer {token}'

async def send_group_msg(group_id, text):
    payload = {
        "group_id": int(group_id),
        "message": text
    }
    async with SESSION.post('/send_group_msg', json=payload, headers=HEADERS) as resp:
        if resp.status == 200:
            logging.info(f"发送文本到群 {group_id}: {text}")
        else:
            logging.error(f"发送失败: {await resp.text()}")

async def send_group_img(group_id, file_path):
    try:
        with open(file_path, 'rb') as f:
            img_data = f.read()
            b64 = base64.b64encode(img_data).decode('utf-8')
        
        payload = {
            "group_id": int(group_id),
            "message": [{
                "type": "image",
                "data": {
                    "file": f"base64://{b64}"  # NapCat 支持 base64:// 前缀
                }
            }]
        }
        async with SESSION.post('/send_group_msg', json=payload, headers=HEADERS) as resp:
            text = await resp.text()
            if resp.status == 200:
                logging.info(f"发送 base64 图片到群 {group_id} 成功")
            else:
                logging.error(f"发送 base64 图片失败: {text}")
    except Exception as e:
        logging.error(f"base64 图片准备失败: {e}")