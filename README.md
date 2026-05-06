# sjagent - 门店业务自动化执行智能体

基于 **Python + LangGraph** 从零自研的门店业务智能体，复刻完整 `order-flow` 业务流程，接入 `sjbzwiki` 本地知识库。

## 核心能力

- **图片订单**：收到设计稿图片 → 自动裁切 → OCR识别 → 创建工作流订单 → 开单
- **文字下单**：客户查询 → 商品匹配 → 件套换算 → 库存决策 → 进货/调拨 → 统一开单
- **库存管理**：MySQL直查库存（节省Token）→礼盒/非礼盒分类决策
- **知识库问答**：常驻加载 sjbzwiki 全量文档，业务问题优先检索知识库
- **配置管理**：通过自然语言动态修改业务规则（件套换算、库存决策、打印规则等），无需手动编辑配置文件
- **多渠道接入**：飞书机器人、HTTP API、外部系统调用

## 开发步骤

| 步骤 | 内容 | 状态 |
|------|------|------|
| 步骤1 | 读取 order-flow + sjbzwiki，输出架构设计 | ✅ |
| 步骤2 | LangGraph骨架、全局配置、数据库长连接、日志，知识库常驻加载 | ✅ |
| 步骤3 | 通用工具：件套换算、商品查询、库存SQL查询、工具注册中心 | ✅ |
| 步骤4 | 图片订单全链路（黑框检测→裁切→OCR→解析→工作流订单→开单判断） | ✅ |
| 步骤5 | 文字下单、库存决策、进货调拨（完整B流程） | ✅ |
| 步骤6 | ERP全接口封装（28个API + 36个工具） | ✅ |
| 步骤7 | 飞书渠道、HTTP API、硬件扩展、外部调用 | ✅ |
| 步骤8 | 联调优化、Docker部署 | 🔄 |

## 快速启动

```bash
# 控制台模式
python main.py --mode console

# 单次执行
python main.py --message "客户银茗，要1件喜悦三小盒"

# 飞书渠道
python main.py --mode feishu --feishu-port 5000

# HTTP API
python main.py --mode http --http-port 8080

# 全部渠道
python main.py --mode all
```

## HTTP API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/agent/chat` | POST | 对话接口 |
| `/api/inventory/query` | GET | 库存查询 |
| `/api/product/search` | GET | 商品搜索 |
| `/api/sales/add` | POST | 开销售单 |
| `/api/tools/list` | GET | 工具列表 |
| `/health` | GET | 健康检查 |

## 渠道接入

```
┌─────────────────────────────────────────────────────┐
│                    多渠道接入层                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ 飞书   │  │ HTTP API │  │ 硬件扩展 │  │ 外部调用 │ │
│  │ 机器人  │  │ WebUI   │  │ 串口/网络 │  │ REST API │ │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────────────────┘
```

## 核心业务规则

| 规则 | 文件 |
|------|------|
| 件套换算 | `scripts/common/unit_converter.py` |
| 颜色过滤（UV） | `scripts/common/color_filter.py` |
| 库存决策 | `src/core/nodes/inventory.py` |
| 进货规则 | `src/core/nodes/inventory.py` |
| 统一开单 | `src/core/nodes/executor.py` |
| 进货汇总格式 | `src/core/nodes/response.py` |

## 非1件起系列配置

修改 `config.yaml` 中 `business_rules.unit_conversion.non_one_piece_series` 列表即可。常量通过延迟加载自动生效。

## 敏感凭证配置

`config.yaml` 中的敏感信息使用 `${ENV_VAR}` 占位符，运行时从环境变量读取：

```bash
export ERP_API_KEY="your_key"
export DB_HOST="localhost"
export DB_USER="root"
export DB_PASSWORD="your_password"
export OSS_ACCESS_KEY_ID="your_key"
export OSS_ACCESS_KEY_SECRET="your_secret"
```

## ERP API（28个接口）

库存(4)、产品(2)、客户(2)、销售(7)、打印(3)、采购(1)、出入库(2)、调拨(1)、仓库(1)、工作流(4)

## 工具注册中心（36个工具）

ERP工具(15) + 订单工具(11) + 数据库工具(6) + 脚本工具(3) + 外部调用工具(1)
