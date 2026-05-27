# React 后台 API 合同

版本：V1.0  
日期：2026-05-22  
适用入口：未来 `/admin` React + Radix 后台  
前置文档：[服务层与路由映射表](service_layer_route_map.md)

## 1. 目的

这份合同用于约束 React 新后台怎么调用后端：

- 每个页面先看这份表，不临时猜接口。
- 每个接口必须能落到明确的 service。
- 页面只负责展示、输入和交互，不自己拼库存、余额、付款、删除回滚规则。
- 旧 `/web` 在新后台验收前继续可用。

## 2. 通用约定

### 2.1 请求认证

| 场景 | 方式 | 说明 |
| --- | --- | --- |
| React 后台 `/admin` | Flask session cookie | 复用 `/api/web-auth/*`。未登录返回 `401` 或跳转登录页。 |
| 小程序 | `Authorization: Bearer <token>` 或 `X-SJ-Token` | 只用于小程序接口，不用于后台。 |
| 打印代理 | `SJAGENT_PRINT_AGENT_TOKEN` 或本机请求 | 只用于 `/api/print-agent/*`。 |

### 2.2 返回格式

后台 API 默认使用：

```json
{
  "code": 0,
  "msg": "",
  "data": {}
}
```

列表接口建议统一成：

```json
{
  "code": 0,
  "data": {
    "list": [],
    "total": 0,
    "page": 1,
    "page_size": 20
  }
}
```

### 2.3 错误格式

| HTTP 状态 | 含义 | 前端处理 |
| --- | --- | --- |
| 400 | 参数错误或业务校验失败 | 表单上提示。 |
| 401 | 未登录或 token 失效 | 跳登录。 |
| 403 | 没有权限 | 弹权限提示。 |
| 404 | 资源不存在 | 弹提示并刷新列表。 |
| 500 | 服务异常 | 弹错误并保留当前输入。 |

## 3. 页面和接口总表

| React 页面 | 路由建议 | 主要接口 | 归属服务 | 状态 |
| --- | --- | --- | --- | --- |
| 登录 | `/admin/login` | `/api/web-auth/login`, `/api/web-auth/me`, `/api/web-auth/logout` | `AuthService` | 已可用 |
| 工作台 | `/admin` | `/api/dashboard/summary`, `/api/orders/recent` | `DashboardService` | 已可用 |
| 开单 | `/admin/sales/new` | `/api/customer/list`, `/api/product/search`, `/api/customer/price`, `/api/sales/add` | `CustomerService`, `ProductService`, `SalesService` | 已可用 |
| 销售单 | `/admin/sales` | `/api/sales/cards`, `/api/sales/<id>/detail`, `DELETE /api/sales/<id>`, `/api/sales/<id>/print-task` | `SalesService` | 已可用 |
| 客户 | `/admin/customers` | `/api/customers`, `/api/customers/<id>`, `/api/customers/<id>/sales`, `/api/customers/<id>/balance*` | `CustomerService`, `CustomerBalanceService` | 已可用 |
| 商品 | `/admin/products` | `/api/product/list`, `/api/product/<id>`, `/api/product/save`, `/api/product/delete`, `/api/product/<id>/shelves` | `ProductService` | 已可用 |
| 图片资产 | `/admin/media` | `/api/product/media`, `/api/product/upload`, `/api/product/media/<id>` | `ProductService` | 已可用 |
| 库存 | `/admin/inventory` | `/api/inventory/cards`, `/api/inventory/balances`, `/api/inventory/ledger` | `InventoryService` | 已可用 |
| 出入库 | `/admin/inventory/documents` | `/api/stock-documents`, `/api/inventory/purchase` | `InventoryService` | 已可用 |
| 盘点 | `/admin/inventory/stocktakes` | `/api/stocktakes`, `/api/inventory/stocktaking` | `InventoryService` | 已可用 |
| 调拨 | `/admin/inventory/transfers` | `/api/transfers`, `/api/inventory/transfer` | `InventoryService` | 已可用 |
| 订单（过程订单） | `/admin/orders`，兼容 `/admin/workflow` | `/api/workflow/orders`, `/api/workflow/orders/<id>/status`, `DELETE /api/workflow/orders/<id>` | `WorkflowService` | 已可用 |
| 设置 | `/admin/settings` | `/api/settings/*`, `/api/users`, `/api/warehouses` | `SettingsService`, `UserService`, `InventoryService` | React 基础版已接入 |
| Agent 工作台 | `/admin/agent` | `/api/agent/chat`, `/api/session/pending`, `/api/agent/history` | Agent + service wrappers | 后续迁移 |
| 小程序兼容接口 | 小程序侧 | `/api/mini/home`, `/api/mini/user/center`, `/api/mini/goods/detail` | `MiniAppService`, `ProductService` | 已可用 |

## 4. 认证模块

| 动作 | 方法 | 接口 | 请求字段 | 返回数据 | Service |
| --- | --- | --- | --- | --- | --- |
| 当前账号 | GET | `/api/web-auth/me` | 无 | `data.user` | `AuthService.current_web_user()` |
| 登录 | POST | `/api/web-auth/login` | `username`, `password` | `data.user` | `AuthService.login_web_user()` |
| 退出 | POST/GET | `/api/web-auth/logout` | 无 | 空对象或跳转 | session helper |
| 注册 | POST | `/api/web-auth/register` | `username`, `password`, `display_name` | `data.user`, `pending` | `AuthService.register_web_user()` |
| 审批列表 | GET | `/api/web-auth/users?status=all` | `status` | `data.items` | `AuthService.web_users()` |
| 通过账号 | POST | `/api/web-auth/users/<id>/approve` | 无 | `affected` | `AuthService.approve_user()` |
| 拒绝账号 | POST | `/api/web-auth/users/<id>/reject` | 无 | `affected` | `AuthService.reject_user()` |

前端要求：

- `/admin` 启动时先调 `/api/web-auth/me`。
- `401` 进入 `/admin/login`。
- `403` 不跳登录，显示没有权限。
- 登录成功后再进入上一次想访问的页面。

## 5. 工作台模块

| 动作 | 方法 | 接口 | 参数 | 用途 | Service |
| --- | --- | --- | --- | --- | --- |
| 首页数字 | GET | `/api/dashboard/summary` | 无 | 今日销售、今日金额、待处理订单 | `DashboardService.summary()` |
| 最近业务记录 | GET | `/api/orders/recent` | `limit` | 右侧最近销售单和过程订单 | `DashboardService.recent_orders()` |
| 屏幕数据 | GET | `/api/screen/dashboard` | 无 | 可选，用于小屏/看板预览 | `DashboardService` |

React 第一版工作台只放业务入口和近期动态，不做复杂报表。

## 6. 开单和销售单模块

### 6.1 开单页

| 动作 | 方法 | 接口 | 参数 | 用途 | Service |
| --- | --- | --- | --- | --- | --- |
| 搜索客户 | GET | `/api/customer/list` | `keyword`, `limit` | 客户输入框候选 | `CustomerService.list()` |
| 创建客户 | POST | `/api/customer/create` | `name`, `phone` 等 | 开单时新增客户 | `CustomerService.create()` |
| 搜索商品 | GET | `/api/product/search` | `keyword`, `limit` | 商品输入框候选 | `ProductService.search()` |
| 商品历史价 | GET | `/api/customer/price` | `customer_id`, `product_id` | 自动填客户历史价 | `SalesService.history_price()` |
| 商品零售价 | GET | `/api/product/retail-price` | `product_id` | 没历史价时兜底 | `ProductService.price()` |
| 仓库列表 | GET | `/api/warehouse/list` | 无 | 默认出库仓选择 | `InventoryService.warehouse_list()` |
| 创建销售单 | POST | `/api/sales/add` | `customer_id`, `warehouse_id`, `products`, `pay_status`, `pay_type`, `create_time` | 真正开单 | `SalesService.create_order()` |

前端要求：

- 客户选中后自动带出是否月结。普通客户默认已付，月结客户默认月结。
- 页面不能自己扣库存、扣余额、计算删除回滚。
- 商品行要保留 `product_id`, `unit_id`, `buy_number`, `price`, `warehouse_id`。

### 6.2 销售单列表和详情

| 动作 | 方法 | 接口 | 参数 | 用途 | Service |
| --- | --- | --- | --- | --- | --- |
| 销售单卡片 | GET | `/api/sales/cards` | `page`, `page_size`, `keyword`, `status`, `customer_id` | 列表/卡片 | `SalesService.cards()` |
| 销售单详情 | GET | `/api/sales/<id>/detail` | 无 | 弹窗详情、账单明细 | `SalesService.detail()` |
| 删除销售单 | DELETE | `/api/sales/<id>` | 无 | 软删除并回滚库存/余额 | `SalesService.delete_order()` |
| 创建打印任务 | POST | `/api/sales/<id>/print-task` | `template_id` 可选 | 加入打印队列 | `SalesService.create_print_task()` |
| 打印预览 | GET | `/api/sales/<id>/print-html` | `auto=0/1` | 打印预览页面 | `SalesService.sales_print_html()` |

验收重点：

- 默认隐藏已删除销售单。
- 删除按钮文案用“删除”，后端按软删除处理。
- 详情弹窗必须显示：付款状态、付款方式、开单人、删除人/删除时间、商品明细、库存影响。

## 7. 客户和余额模块

| 动作 | 方法 | 接口 | 参数 | 用途 | Service |
| --- | --- | --- | --- | --- | --- |
| 客户列表 | GET | `/api/customers` | `keyword`, `page`, `page_size` | 客户卡片列表 | `CustomerService.list()` |
| 快速客户搜索 | GET | `/api/customer/list` | `keyword`, `limit` | 选择器 | `CustomerService.list()` |
| 更新客户 | PATCH/POST | `/api/customers/<id>` | `is_monthly_customer`, `phone` 等 | 月结开关、资料维护 | `CustomerService.update_monthly()` |
| 客户销售单 | GET | `/api/customers/<id>/sales` | `period`, `month`, `page`, `page_size` | 客户详情销售记录；`period=1m/3m` 或 `month=YYYY-MM` | `CustomerService.sales()` |
| 余额明细 | GET | `/api/customers/<id>/balance-ledger` | `page`, `page_size` | 余额流水 | `CustomerBalanceService.ledger()` |
| 收款/充值/结款/调余额 | POST | `/api/customers/<id>/balance` | `action`, `amount`, `pay_type`, `month`, `note` | 钱账动作 | `CustomerBalanceService.apply_action()` |

前端要求：

- 客户列表显示：最近下单时间、最近金额、近 1 年消费、余额。
- 客户详情按月份筛销售单，未选月份显示总计。
- 余额只能通过收款、充值、结款、调余额动作改变。
- React 基础版已接入：客户卡片、详情抽屉、月结开关、收款/充值/结款/调余额入口、余额明细。

## 8. 商品和图片资产模块

### 8.1 商品

| 动作 | 方法 | 接口 | 参数 | 用途 | Service |
| --- | --- | --- | --- | --- | --- |
| 商品列表 | GET | `/api/product/list` | `keyword`, `page`, `page_size`, `category_id`, `group` | SPU/SKU 列表 | `ProductService.list()` |
| 商品分类 | GET/POST/PATCH | `/api/product/categories` | 新增/编辑时传 `name`, `product_type`, `inventory_policy` | 分类筛选；设置页可新增分类并同步库存策略 | `ProductService.categories()`, `ProductService.save_category()` |
| 商品详情 | GET | `/api/product/<id>` | 无 | 编辑弹窗数据 | `ProductService.info()` |
| 编辑选项 | GET | `/api/product/options` | `product_id` 可选 | 单位、分类、颜色等选项 | `ProductService.options()` |
| 保存商品 | POST | `/api/product/save` | 商品表单 payload | 新增/编辑 | `ProductService.save()` |
| 删除商品 | POST | `/api/product/delete` | `ids` | 商品删除 | `ProductService.delete()` |
| 上下架 | POST | `/api/product/<id>/shelves` | `state` | 上架/下架 | `ProductService.update_shelves()` |
| 颜色选项 | GET | `/api/product/color-options` | `keyword` 可选 | 编辑颜色选择 | `ProductService` |

前端要求：

- 商品卡片显示颜色数、颜色列表、件规。
- 0 颜色显示“默认颜色”，但颜色数仍算 1。
- `1件X套` 文案用“件规：1件 X 套”。
- 起订规则在编辑页可维护。
- React 基础版已接入：商品编辑弹窗、分类、件规、1 件起订、规格价格、主图/详情页/颜色图和保存。

### 8.2 图片资产

| 动作 | 方法 | 接口 | 参数 | 用途 | Service |
| --- | --- | --- | --- | --- | --- |
| 资产列表 | GET | `/api/product/media` | `role`, `keyword`, `category`, `product_id`, `page`, `page_size` | 图片资产管理和选择弹窗 | `ProductService.media_assets()` |
| 上传图片 | POST | `/api/product/upload` | `file` | 上传并写资产表 | `ProductService.record_upload()` |
| 删除资产 | DELETE/POST | `/api/product/media/<id>` | 无 | 删除误上传图片 | `ProductService.delete_media()` |
| 本地图片预览 | GET | `/api/images/file/<filename>` | 无 | 展示本地上传文件 | 文件服务 |

前端要求：

- 图片资产按大类、SPU、角色分页。
- 主图按 SPU 聚合，只显示一个主图。
- 图片选择弹窗包含：未绑定、本产品、全部图片、搜索。React 基础版已接入。
- 大图多时必须用分页和懒加载，不一次性渲染全部。

## 9. 库存模块

| 动作 | 方法 | 接口 | 参数 | 用途 | Service |
| --- | --- | --- | --- | --- | --- |
| 库存卡片 | GET | `/api/inventory/cards` | `keyword`, `only_in_stock`, `limit` | 库存总览 | `InventoryService.search()` |
| 单品/仓库库存 | GET | `/api/inventory/query` | `product_id` 或 `warehouse_id` | 商品详情里的库存 | `InventoryService.product_inventory()` / `warehouse_inventory()` |
| 库存明细 | GET | `/api/inventory/balances` | `keyword`, `warehouse_id`, `page`, `page_size` | 当前库存余额 | `InventoryService.balances()` |
| 库存日志 | GET | `/api/inventory/ledger` | `keyword`, `page`, `page_size` | 库存流水 | `InventoryService.ledger()` |
| 出入库明细 | GET | `/api/stock-documents` | `keyword`, `page`, `page_size` | 出入库单列表 | `InventoryService.stock_documents()` |
| 进货入库 | POST | `/api/inventory/purchase` | `warehouse_id`, `products`, `note` | 入库 | `InventoryService.create_stock_in()` |
| 盘点明细 | GET | `/api/stocktakes` | `keyword`, `page`, `page_size` | 盘点记录 | `InventoryService.stocktakes()` |
| 盘点 | POST | `/api/inventory/stocktaking` | `warehouse_id`, `products`, `note` | 盘点写入 | `InventoryService.create_stocktake()` |
| 调拨明细 | GET | `/api/transfers` | `keyword`, `page`, `page_size` | 调拨记录 | `InventoryService.transfers()` |
| 调拨 | POST | `/api/inventory/transfer` | `out_warehouse_id`, `enter_warehouse_id`, `products`, `note` | 调拨写入 | `InventoryService.create_transfer()` |
| 仓库列表 | GET | `/api/warehouses` | 无 | 仓库设置/选择 | `InventoryService.warehouse_list()` |

库存规则：

- 分类的 `inventory_policy` 优先于关键词规则；设置页可以新增分类并设置扣/不扣库存。
- 泡袋、纸箱、PVC 礼盒等历史默认不扣库存，但后续应通过分类策略和关键词配置维护，不再只靠前端只读说明。
- 小程序不做扣库存。
- 库存变化必须能看到来源和操作人。

## 10. 订单模块（过程订单）

React 后台用户可见名称统一为“订单”。第一阶段仍复用后端 `/api/workflow/orders`，因为这里承接的是 `workflow_order` 过程订单，不是正式扣库存的销售单。

| 动作 | 方法 | 接口 | 参数 | 用途 | Service |
| --- | --- | --- | --- | --- | --- |
| 订单列表 | GET | `/api/workflow/orders` | `keyword`, `page`, `page_size`, `filter` | 过程订单列表 | `WorkflowService.list_orders()` |
| 创建/编辑订单 | POST | `/api/workflow/orders` | `customer_name`, `goods_name`, `order_quantity`, `color`, `order_images`, `remark` | 保存过程订单 | `WorkflowService.save_order()` |
| 状态更新 | POST | `/api/workflow/orders/<id>/status` | `field`, `value` | 制作/发货/完成状态 | `WorkflowService.update_status()` |
| 删除订单 | DELETE | `/api/workflow/orders/<id>` | 无 | 删除过程订单 | `WorkflowService.delete_orders()` |
| 订单图片上传 | POST | `/api/workflow/images/upload` | `image` | 图片识别/过程订单附件 | 上传服务 |

前端要求：

- 订单页管理过程订单，不扣库存。
- 过程订单转销售单必须走销售单服务，不由前端直接拼数据写库。
- 前端查询参数使用当前路由实际支持的 `filter`，不是历史文档里的 `status`。

## 11. 设置模块

| 设置页 | 方法 | 接口 | 用途 | Service |
| --- | --- | --- | --- | --- |
| 编号设置 | GET/POST | `/api/settings/number/sku` | SKU 起始号、下一号、变更记录 | `SettingsService` |
| 商品基础 | GET/POST | `/api/settings/system/product_basic` | 分类、单位、泡袋版型等 | `SettingsService` |
| 库存规则 | GET/POST | `/api/settings/system/inventory_rules` | 默认仓库、负库存开关、扣/不扣库存关键词、分类库存策略展示 | `SettingsService` |
| 收款/结款 | GET/POST | `/api/settings/system/payment_rules` | 付款方式、余额原因、月结说明 | `SettingsService` |
| 图片/OSS | GET/POST | `/api/settings/system/media_rules` | 上传路径、缩略图、清理规则 | `SettingsService` |
| 打印设置 | GET/POST | `/api/settings/print/sales` | 销售单打印模板 | `SettingsService` |
| 用户权限 | GET/PATCH | `/api/users`, `/api/users/<id>` | 用户角色、启停 | `UserService` |
| 仓库设置 | GET | `/api/warehouses` | 仓库列表 | `InventoryService` |

设置页要求：

- 商品分类和分类库存策略允许在设置页编辑，后端保存时必须同步 SKU 的 `is_stock_item/inventory_policy`。
- 可配置项必须用选择器、开关、列表管理，不用一堆 textarea。
- 保存后写设置日志，前端提示保存结果。

## 12. Agent 工作台模块

| 动作 | 方法 | 接口 | 用途 | 状态 |
| --- | --- | --- | --- | --- |
| 对话 | POST | `/api/agent/chat` | 普通文本对话 | 旧接口可用 |
| 流式对话 | POST | `/api/agent/chat/stream` | 流式输出 | 旧接口可用 |
| pending 表单 | POST | `/api/session/pending` | 修改确认单状态 | 旧接口可用 |
| 历史 | GET | `/api/agent/history` | 会话历史 | 旧接口可用 |

后续要求：

- Agent 工作台只是入口，最终业务写入仍走服务层。
- React 第一阶段可以先不迁 Agent 工作台，保留旧 `/web` 使用。

## 13. 第一批 React 实现顺序

建议第一批不要一次性迁全部页面：

1. `/admin/login`：验证 `AuthService` 和 session。
2. `/admin` 工作台：验证布局、API client、401/403。
3. `/admin/settings`：先迁设置，因为它决定业务规则入口。
4. `/admin/customers` + `/admin/sales`：日常业务主链路。
5. `/admin/products` + `/admin/media`：商品和图片资产。
6. `/admin/inventory`：库存全链路。

每一批都必须满足：

- API 都能在本合同里查到。
- 接口落点能在 `service_layer_route_map.md` 查到。
- 有 smoke 或单元测试。
- `/web` 不受影响。

## 14. 当前缺口

| 缺口 | 影响 | 建议处理 |
| --- | --- | --- |
| 没有独立 `/api/admin/bootstrap` | React 启动时要分别请求 `me`、设置、汇总 | 第一版可接受，后续可加聚合接口。 |
| 设置页部分 system key 还没有强 schema | 前端不好做结构化表单 | 做设置页前先固定 key 和 JSON 字段。 |
| Agent 工作台仍是旧接口 | 可用但不够组件化 | React 后期再迁。 |
| 图片缩略图策略未完全接口化 | 大量图片时性能受影响 | 商品图片迁移前补缩略图字段和分页策略。 |

## 15. 验收清单

React 后台底座开始前，先确认：

- [x] `AuthService` 已完成基础迁移。
- [x] `DashboardService` 已完成基础迁移。
- [x] 销售、客户、库存、商品、设置已有 service 入口。
- [x] API 合同已写入本文档。
- [x] `/admin` Vite 项目创建。
- [x] API client 统一处理 `code`、`401`、`403`。
- [x] 旧 `/web` 不受影响。
- [x] 小程序首页、用户中心、商品详情 smoke 通过，首页/用户中心聚合已收进 `MiniAppService`。
