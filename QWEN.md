# EQBot - 地震信息推送机器人

EQBot是一个基于Python开发的地震信息实时推送机器人，通过WebSocket连接FAN Studio的地震数据源，并将地震信息推送到QQ群聊中。该机器人支持多种国内外地震监测机构的数据源，并提供可视化地震地图功能。

## 项目概述

- **主要功能**：实时获取全球地震信息并推送到QQ群
- **技术栈**：Python 3.13+, asyncio, websockets, aiohttp, matplotlib, cartopy
- **架构**：采用异步WebSocket通信，支持多源数据聚合
- **数据源**：支持CENC、CEA、JMA、USGS、EMSC等20+地震监测机构
- **可视化**：提供地震位置的地图可视化功能

## 文件结构

```
eqbot/
├── main.py                 # 主程序入口
├── config.json             # 配置文件
├── ws_handler.py           # WebSocket处理器（连接FAN WS和NapCat）
├── message_sender.py       # 消息发送模块（与NapCat HTTP API通信）
├── draw_eq.py              # 地震地图绘制模块
├── command_handler.py      # 命令处理模块
├── requirements.txt        # 依赖包列表
├── eqbot.log               # 日志文件
└── __pycache__/            # Python缓存目录
```

## 依赖安装

```bash
pip install -r requirements.txt
```

需要安装的依赖包：
- `aiohttp` - HTTP客户端库
- `websockets` - WebSocket协议实现
- `matplotlib` - 绘图库
- `cartopy` - 地理信息可视化库
- `numpy` - 数值计算库

## 配置说明

### config.json 配置项

- `napcat_http_url`: NapCat HTTP API服务地址（默认：http://127.0.0.1:3000）
- `napcat_token`: NapCat访问令牌（可选）
- `ws_port`: 机器人WebSocket监听端口（默认：9998）
- `log_file`: 日志文件路径（默认：eqbot.log）
- `enable_command_listener`: 是否启用命令监听（默认：true）
- `test_command`: 测试命令（默认：/eqbottest）
- `test_groups_only`: 是否仅在配置的群组中响应测试命令（默认：true）

### 群组配置

- `groups`: 群组配置对象，键为群号，值包含：
  - `mode`: 黑名单模式（blacklist）或白名单模式（whitelist）
  - `sources`: 在该模式下生效的数据源列表

### 数据源配置

- `sources`: 启用的数据源开关（true/false）
- `source_rules`: 各数据源的过滤规则（如震级阈值）
- `message_templates`: 不同数据源的消息模板
- `draw_sources`: 需要生成地图的数据源列表

## 运行方式

### 直接运行

```bash
python main.py
```

### 环境要求

- Python 3.13+
- 已部署并运行的NapCat服务（用于QQ机器人通信）
- 网络能够连接到 ws://ws.fanstudio.tech/all

## 功能特性

1. **多源数据聚合**：支持来自全球20多个地震监测机构的数据
2. **智能过滤**：可根据震级等条件设置过滤规则
3. **群组管理**：支持黑白名单模式控制不同群组接收的数据源
4. **可视化地图**：自动生成地震位置地图并发送到群聊
5. **命令交互**：支持测试命令验证机器人功能
6. **日志记录**：详细的运行日志便于调试和监控

## 消息模板

机器人支持多种地震数据源的定制化消息模板，包括：
- 中国地震台网（CENC）
- 中国地震预警网（CEA）
- 日本气象厅（JMA）
- 美国地质调查局（USGS）
- 欧洲地中海地震中心（EMSC）
- 及其他多个国家和地区机构

## 开发约定

- 使用异步编程模型处理并发连接
- 遵循OneBot v11协议标准与QQ机器人框架通信
- 采用模块化设计，各功能职责分离
- 使用logging模块进行日志记录
- 配置文件使用JSON格式，便于维护

## 故障排查

- 检查NapCat服务是否正常运行
- 确认网络连接是否正常
- 查看eqbot.log中的错误信息
- 验证配置文件格式是否正确
- 确保依赖包版本兼容性