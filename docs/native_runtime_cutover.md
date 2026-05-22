# 自有库运行切换记录

更新时间：2026-05-21

## 2026-05-21 本轮切换

| 链路 | 本轮结果 | 说明 |
|---|---|---|
| 智能体通用 DB 工具 | 已切到 `sjagent_core` | `db_tools.py` 里的单位、仓库、商品、库存件规查询不再直查 `sxo_*` 旧表 |
| 小程序/API 登录 | 已切到 `auth_user` + `auth_session` | `/api/auth/login` 发自有 token；`/api/auth/me` 校验自有 token；小程序请求用自有 token 识别操作人 |
| 微信快捷登录 | 已切到 `auth_identity` | 有 `openid` 时直接查/建自有身份；有 `WECHAT_MINIAPP_APPID/SECRET` 时可用 code 换 openid；新微信用户默认等待审批 |
| 验证码接口 | 已停止代理 ShopXO | `/api/auth/captcha` 保留兼容响应，但自有登录不需要图片验证码 |
| ASR 热词 | 已切到自有表 | 商品、销售明细、仓库、客户热词来自 `product_*`、`sales_order_item`、`warehouse`、`party` |
| 采购工具 | 已停止直接调 ERP | `purchase_add` 改为创建自有入库单，默认入百鑫仓库 |

说明：源码里仍有部分旧 ShopXO/ERP 代码块作为迁移参考或不可达兜底片段，下一步会继续做物理清理；本轮已把上述运行入口改成先返回自有库逻辑，不再走旧接口。

## 已切到 sjagent_core 的链路

| 链路 | 旧来源 | 新来源 | 说明 |
|---|---|---|---|
| 商品搜索 | ERP API / 旧 ERP 商品表 | `product_spu`、`product_sku`、`product_alias` | 智能体 `product_search`、WebUI `/api/product/search`、开单商品搜索已走自有库 |
| 商品详情/列表 | ERP API / 旧 ERP 商品表 | `product_sku`、`product_spu`、`product_category`、`product_unit`、`product_media` | WebUI 商品列表、分类、编辑基础数据已走自有库 |
| 客户搜索 | ERP API 客户 | `party` | 智能体 `customer_query`、WebUI `/api/customer/list`、`/api/customers` 已走自有库 |
| 用户列表/后台登录 | ShopXO 用户/旧 WebUI 表 | `auth_user` | WebUI 登录、审批和用户管理统一读写 `auth_user`；旧 `sjagent_web_users` 只作为迁移来源 |
| 仓库列表 | ERP API 仓库 | `warehouse` | `/api/warehouse/list`、`/api/warehouses` 已走自有库 |
| 库存查询 | 旧 ERP 库存表 | `inventory_balance` | 智能体查库存、WebUI 库存卡片/库存明细已走自有库 |
| 库存日志 | 无统一页面 | `inventory_ledger` | 新增 `/api/inventory/ledger` |
| 进货入库 | ERP `OtherEnterAdd` | `stock_document`、`stock_document_item`、`inventory_balance`、`inventory_ledger` | 智能体和 WebUI 进货会直接写自有库 |
| 调拨 | ERP `InventoryTransfer` | `transfer_order`、`transfer_order_item`、`inventory_balance`、`inventory_ledger` | 智能体和 WebUI 调拨会直接写自有库 |
| 盘点同步 | ERP `InventorySync` | `stocktake_order`、`stocktake_item`、`inventory_balance`、`inventory_ledger` | 智能体盘点会直接写自有库 |
| 销售开单 | ERP `SalesAdd` | `sales_order`、`sales_order_item`、`inventory_balance`、`inventory_ledger` | WebUI 开单/智能体开单会扣自有库存 |
| 工作流订单 | ERP 工作流 API | `workflow_order`、`workflow_order_log` | WebUI 工作流列表、保存、状态、删除已走自有库 |
| 商品自动编号 | 旧系统散乱编号/脚本内固定起点 | `number_sequence_setting`、`number_sequence_log` | WebUI 设置里可调整后续 SKU 起点；当前统一从 `SJ1570` 往后找空号 |

## 新增 WebUI 页面

| 主导航 | 子页面/功能 | API |
|---|---|---|
| 设置 | 编号设置 | `/api/settings/number/sku` |
| 设置 | 商品基础设置 | `/api/settings/system/product_basic` |
| 设置 | 库存规则设置 | `/api/settings/system/inventory_rules` |
| 设置 | 收款/结款设置 | `/api/settings/system/payment_rules` |
| 设置 | 图片/OSS 设置 | `/api/settings/system/image_rules` |
| 设置 | 用户和权限设置 | `/api/settings/system/permission_rules`、`/api/users` |
| 客户 | 客户管理 | `/api/customers` |
| 客户 | 用户管理 | `/api/users` |
| 库存 | 库存卡片 | `/api/inventory/cards` |
| 库存 | 库存明细 | `/api/inventory/balances` |
| 库存 | 出入库明细 | `/api/stock-documents` |
| 库存 | 盘点明细 | `/api/stocktakes` |
| 库存 | 调拨明细 | `/api/transfers` |
| 库存 | 库存日志 | `/api/inventory/ledger` |
| 库存 | 仓库设置 | `/api/warehouses` |

## 仍保留的外部依赖

| 功能 | 当前状态 | 后续建议 |
|---|---|---|
| 商城/小程序登录、验证码、微信快捷登录 | 已改为自有 `auth_user` / `auth_identity` / `auth_session` | 后续清理源码中不可达的 ShopXO 参考代码，并补小程序端联调 |
| 销售单打印 HTML / 打印任务 | 已改为自有 `print_template` / `print_job` | 后续继续完善模板设置和本地打印服务管理 |
| OSS 图片上传 | 仍使用现有 OSS 上传配置 | 可以保留，不属于 ShopXO/ERP 数据依赖 |

## 运行配置

运行时自有库读取以下环境变量：

| 环境变量 | 用途 |
|---|---|
| `SJAGENT_CORE_DB_HOST` | 自有库 MySQL 地址 |
| `SJAGENT_CORE_DB_PORT` | 自有库 MySQL 端口 |
| `SJAGENT_CORE_DB_NAME` | 默认 `sjagent_core` |
| `SJAGENT_CORE_DB_USER` | 自有库用户名 |
| `SJAGENT_CORE_DB_PASSWORD` | 自有库密码 |
| `SJAGENT_LEGACY_FALLBACK` | 已废弃；运行时不再允许自动回退旧 ERP/旧库 |
