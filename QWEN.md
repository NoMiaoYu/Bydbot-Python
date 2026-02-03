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
├── AGENTS.md               # 项目说明文档
├── QWEN.md                 # 项目说明文档
├── strat.bat               # 启动脚本
├── data/                   # 数据目录（包含断层数据等）
├── 实现/                   # 开发实现目录
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

### 使用启动脚本

```bash
strat.bat
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

## 核心模块说明

### main.py
主程序入口，负责：
- 加载配置文件
- 设置日志记录
- 初始化消息发送器
- 启动FAN WS数据接收任务
- 启动NapCat WebSocket服务器
- 处理程序关闭信号

### ws_handler.py
WebSocket处理器，负责：
- 连接FAN Studio地震数据WebSocket
- 处理接收到的地震数据
- 实现黑白名单推送逻辑
- 处理NapCat反向WebSocket连接
- 响应测试命令
- 优化后的代码结构，减少重复逻辑

### message_sender.py
消息发送模块，负责：
- 与NapCat HTTP API通信
- 发送文本消息到QQ群
- 发送图片消息到QQ群
- 改进的错误处理和资源管理

### draw_eq.py
地震地图绘制模块，负责：
- 使用matplotlib和cartopy绘制地震位置地图
- 添加震中标识和详细信息
- 处理中国断层数据绘制
- 生成带有信息框的地震可视化图像
- 优化后的性能和代码结构

### command_handler.py
命令处理模块，负责：
- 处理QQ群中的命令
- 执行测试命令验证机器人功能
- 优化后的命令处理逻辑

## 开发约定

- 使用异步编程模型处理并发连接
- 遵循OneBot v11协议标准与QQ机器人框架通信
- 采用模块化设计，各功能职责分离
- 使用logging模块进行日志记录
- 配置文件使用JSON格式，便于维护
- 添加类型提示以提高代码可读性
- 优化错误处理和资源管理

## 故障排查

- 检查NapCat服务是否正常运行
- 确认网络连接是否正常
- 查看eqbot.log中的错误信息
- 验证配置文件格式是否正确
- 确保依赖包版本兼容性

## 重构说明

在最近的重构中，我们对EQBot进行了以下改进：

1. **代码结构优化**：将重复的逻辑提取为独立函数，减少代码重复
2. **错误处理改进**：增强了各模块的错误处理能力
3. **性能优化**：优化了地图绘制和消息处理的性能
4. **类型提示**：添加了类型提示以提高代码可读性
5. **资源管理**：改进了资源管理和清理机制
6. **配置验证**：添加了配置文件验证逻辑
7. **信号处理**：添加了程序关闭信号处理

## 维护说明

本项目主要用于地震信息的实时推送，需要确保：
- 与NapCat服务的稳定连接
- FAN Studio数据源的可靠访问
- 地图绘制功能的性能优化
- 对不同地震机构数据格式的持续适配
- 定期检查和更新依赖包