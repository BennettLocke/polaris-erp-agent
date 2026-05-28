# 服务层与路由映射表

版本：V1.0  
日期：2026-05-22  
适用范围：`sjagent` 当前 React 后台、小程序兼容 API、Agent 工具、打印代理。

## 1. 目的

这份文档用于回答三个问题：

- 现在每个业务入口到底走哪一层。
- 哪些入口已经统一到服务层。
- 哪些入口还只是查询或登录 helper，后续可以慢慢迁。

后续 React + Radix 后台、小程序联调、Agent 对话能力，都必须按这张表走统一服务层，不能在页面、路由或技能里各自拼库存、余额、付款、删除逻辑。

React 新后台页面级接口以 [React 后台 API 合同](react_admin_api_contract.md) 为准。

## 2. 当前分层

```text
React 后台 / 小程序兼容 API / Agent 工具 / 打印代理
  -> src/channels/http_api 或 src/core/tools
    -> src/services/business/*
      -> src/engine/native_db.py
        -> sjagent_core
```

`NativeDBClient` 仍是底层数据网关和事务承载层。  
业务入口不应该直接绕过 `src/services/business/*` 写核心表。

## 3. 已建立服务

| 服务 | 文件 | 当前职责 |
| --- | --- | --- |
| `SalesService` | `src/services/business/sales.py` | 销售单创建、删除、详情、列表、历史价、打印 HTML、打印任务、打印失败。 |
| `InventoryService` | `src/services/business/inventory.py` | 库存查询、库存明细、库存日志、进货、调拨、盘点、仓库列表。 |
| `CustomerService` | `src/services/business/customers.py` | 客户列表、客户创建、月结客户设置、客户销售单查询。 |
| `CustomerBalanceService` | `src/services/business/customers.py` | 余额明细、收款、充值、调余额、月结结款。 |
| `ProductService` | `src/services/business/products.py` | 商品查询、商品详情、商品保存、删除、上下架、编号、图片资产、起订规则同步。 |
| `WorkflowService` | `src/services/business/workflow.py` | 工作流订单保存、列表、详情、删除、状态更新。 |
| `SettingsService` | `src/services/business/settings.py` | 编号设置、系统设置、销售单打印设置。 |
| `UserService` | `src/services/business/users.py` | 用户列表、角色、启停。 |
| `DashboardService` | `src/services/business/dashboard.py` | 首页汇总、右侧最近记录、屏幕待配送统计。 |
| `AuthService` | `src/services/business/auth.py` | 后台注册、登录、审批、小程序 token、微信登录、权限判断。 |
| `IdentityLinkService` | `src/services/business/identity.py` | 手机号、微信 `auth_identity`、后台账号 `auth_user`、客户 `party` 的统一绑定。 |
| `MiniAppService` | `src/services/business/miniapp.py` | 小程序首页设计读取、商品货架聚合、用户中心订单统计。 |

## 4. 核心写入口映射

| 业务动作 | HTTP / Agent 入口 | 当前服务 | 状态 |
| --- | --- | --- | --- |
| 创建销售单 | `/api/sales/add`, Agent `sales_add` | `SalesService.create_order()` | 已统一 |
| 删除销售单 | `DELETE /api/sales/<id>`, Agent `sales_delete` | `SalesService.delete_order()` | 已统一 |
| 查询销售单详情 | `/api/sales/<id>/detail`, Agent `sales_detail` | `SalesService.detail()` | 已统一 |
| 销售单列表/卡片 | `/api/sales/cards`, Agent `sales_list` | `SalesService.cards()` | 已统一 |
| 创建打印任务 | `/api/sales/<id>/print-task`, Agent `sales_print_task` | `SalesService.create_print_task()` | 已统一 |
| 打印完成 | `/api/print-agent/sales/tasks/<id>/done` | `SalesService.print_task_done()` | 已统一 |
| 打印失败 | `/api/print-agent/sales/tasks/<id>/fail` | `SalesService.print_task_failed()` | 已统一 |
| 进货入库 | `/api/inventory/purchase`, Agent `purchase_add` / `other_enter_add` | `InventoryService.create_stock_in()` | 已统一 |
| 仓库调拨 | `/api/inventory/transfer`, Agent `inventory_transfer` | `InventoryService.create_transfer()` | 已统一 |
| 盘点 | `/api/inventory/stocktaking`, Agent `inventory_sync` | `InventoryService.create_stocktake()` | 已统一 |
| 收款/充值/结款/调余额 | `/api/customers/<id>/balance` | `CustomerBalanceService.apply_action()` | 已统一 |
| 客户月结设置 | `/api/customers/<id>` | `CustomerService.update_monthly()` | 已统一 |
| 商品保存 | `/api/product/save`, Agent `product_add`, 泡袋上传 | `ProductService.save()` | 已统一 |
| 商品删除 | `/api/product/delete` | `ProductService.delete()` | 已统一 |
| 商品上下架 | `/api/product/<id>/shelves` | `ProductService.update_shelves()` | 已统一 |
| 图片上传后入资产表 | `/api/product/upload` | `ProductService.record_upload()` | 已统一 |
| 图片资产删除 | `/api/product/media/<id>` | `ProductService.delete_media()` | 已统一 |
| 工作流订单保存 | `/api/workflow/orders`, `/api/mini/workflow-order/save`, Agent `workflow_order_save` | `WorkflowService.save_order()` | 已统一 |
| 工作流状态更新 | `/api/workflow/orders/<id>/status`, `/api/mini/workflow-order/status-update` | `WorkflowService.update_status()` | 已统一 |
| 工作流删除 | `/api/workflow/orders/<id>`, Agent `workflow_order_delete` | `WorkflowService.delete_orders()` | 已统一 |
| 用户角色/启停 | `/api/users/<id>` | `UserService.update()` | 已统一 |
| 后台用户手机号绑定 | `/api/users/<id>` | `UserService.update()` -> `IdentityLinkService.sync_user_phone()` | 已统一 |
| 客户手机号回填绑定 | `/api/customers/<id>`, `/api/customer/create` | `CustomerService.sync_phone()` -> `IdentityLinkService.sync_customer_phone()` | 已统一 |
| 设置保存 | `/api/settings/*` | `SettingsService` | 已统一 |
| 后台注册 | `/api/web-auth/register` | `AuthService.register_web_user()` | 已统一 |
| 后台登录 | `/api/web-auth/login` | `AuthService.login_web_user()` | 已统一 |
| 后台账号审批 | `/api/web-auth/users/<id>/approve`, `/api/web-auth/users/<id>/reject` | `AuthService.approve_user()` / `AuthService.reject_user()` | 已统一 |
| 小程序账号登录 | `/api/auth/login` | `AuthService.native_login()` | 已统一 |
| 微信快捷登录 | `/api/auth/wechat-quick-login` | `AuthService.wechat_quick_login()` -> `IdentityLinkService.link_wechat()` | 已统一 |

## 5. 查询入口映射

| 业务查询 | 入口 | 当前服务 | 状态 |
| --- | --- | --- | --- |
| 库存卡片 | `/api/inventory/cards`, Agent `inventory_search` | `InventoryService.search()` | 已统一 |
| 单 SKU 库存 | `/api/inventory/query`, Agent `inventory_query_by_id` | `InventoryService.product_inventory()` | 已统一 |
| 仓库库存 | `/api/inventory/query`, Agent `inventory_query_by_warehouse` | `InventoryService.warehouse_inventory()` | 已统一 |
| 库存明细 | `/api/inventory/balances` | `InventoryService.balances()` | 已统一 |
| 库存日志 | `/api/inventory/ledger` | `InventoryService.ledger()` | 已统一 |
| 出入库明细 | `/api/stock-documents` | `InventoryService.stock_documents()` | 已统一 |
| 盘点明细 | `/api/stocktakes` | `InventoryService.stocktakes()` | 已统一 |
| 调拨明细 | `/api/transfers` | `InventoryService.transfers()` | 已统一 |
| 商品搜索 | `/api/product/search`, Agent `product_search` | `ProductService.search()` | 已统一 |
| 商品列表 | `/api/product/list`, 小程序商品列表 | `ProductService.list()` | 已统一 |
| 商品分类 | `/api/product/categories`, 小程序分类/搜索初始化 | `ProductService.categories()` | 已统一 |
| 商品详情 | `/api/product/<id>`, Agent `product_info` | `ProductService.info()` | 已统一 |
| 小程序首页 | `/api/mini/home` | `MiniAppService.design_payload()` / `MiniAppService.product_shelf_items()` | 已统一 |
| 小程序用户中心 | `/api/mini/user/center` | `MiniAppService.user_center_payload()` | 已统一 |
| 商品编辑选项 | `/api/product/options` | `ProductService.options()` | 已统一 |
| 图片资产 | `/api/product/media` | `ProductService.media_assets()` | 已统一 |
| 客户列表 | `/api/customer/list`, `/api/customers`, Agent `customer_query` | `CustomerService.list()` | 已统一 |
| 客户销售单 | `/api/customers/<id>/sales` | `CustomerService.sales()` | 已统一 |
| 客户余额明细 | `/api/customers/<id>/balance-ledger` | `CustomerBalanceService.ledger()` | 已统一 |
| 用户列表 | `/api/users` | `UserService.list()` | 已统一 |
| 后台当前账号 | `/api/web-auth/me` | `AuthService.current_web_user()` / `AuthService.web_user_payload()` | 已统一 |
| 后台审批账号列表 | `/api/web-auth/users` | `AuthService.web_users()` | 已统一 |
| 小程序 token 校验 | `/api/auth/me`, miniapp guard | `AuthService.verify_token()` | 已统一 |
| 仓库列表 | `/api/warehouse/list`, `/api/warehouses`, Agent `warehouse_list` | `InventoryService.warehouse_list()` | 已统一 |
| 首页汇总 | `/api/dashboard/summary` | `DashboardService.summary()` | 已统一 |
| 右侧最近业务记录 | `/api/orders/recent` | `DashboardService.recent_orders()` | 已统一 |
| 屏幕仪表盘汇总/待配送 | `/api/screen/dashboard` | `DashboardService.summary()` / `DashboardService.pending_delivery_count()` | 已统一 |

## 6. 允许暂留的直接数据库调用

这些调用目前可以暂留，因为它们不是核心业务写入口，或者属于登录/兼容层。

| 位置 | 类型 | 暂留原因 | 后续建议 |
| --- | --- | --- | --- |
| `_native_db().product_list()` | 商品列表和分类统计 | 已迁到 `ProductService.list()`。 | 后续只允许在服务层内部调用。 |
| `_native_db().product_categories()` | 商品分类列表 | 已迁到 `ProductService.categories()`。 | 后续只允许在服务层内部调用。 |
| `_native_db().system_setting("miniapp_design")` | 小程序展示配置 | 已迁到 `SettingsService.get()`。 | 后续只允许在服务层内部调用。 |
| `db_tools.db_query` | Agent 只读 SQL 工具 | 已限制 SELECT，用于排查。 | 保留，但禁止写 SQL。 |

## 7. 禁止规则

- 新路由禁止直接调用 `NativeDBClient.create_sales_order()`、`delete_sales_order()`、`create_stock_in()`、`create_transfer()`、`create_stocktake()`。
- 新页面禁止自己计算库存回滚、余额扣减、月结欠款。
- Agent 技能禁止直接写核心业务 SQL。
- 小程序禁止创建销售出库、扣库存、扣余额。
- 打印代理只处理打印任务，不直接改销售单业务状态，必须走服务层。

## 8. 当前验收结果

已执行：

```text
python -m unittest tests.test_business_services -v
python tests\agent_dialog_regression.py
python tests\sales_flow_regression.py
npm.cmd run build  # admin React
python -m py_compile src\channels\http_api\__init__.py
git diff --check
Flask test client: /admin, /admin/login
Flask test client: /api/mini/goods/category, /api/mini/search/index, /api/mini/search/datalist, /api/mini/home, /api/mini/user/center, /api/mini/goods/detail?id=12
Flask test client: /api/dashboard/summary, /api/orders/recent, /api/screen/dashboard
Flask test client: /api/web-auth/me, /api/web-auth/users, /api/auth/me
Flask test client: /api/customers, /api/customers/<id>/sales, /api/customers/<id>/balance-ledger, /api/sales/cards, /api/sales/<id>/detail
Flask test client: /api/users, /api/customers
```

结果：

- 服务层单元测试通过。
- Agent 对话查询、开单预览、pending 切换通过。
- 销售单库存、余额、月结、删除回滚通过。
- 小程序商品分类、搜索初始化、商品列表、首页、用户中心、商品详情接口 smoke 通过。
- 首页汇总、右侧最近记录、屏幕仪表盘接口 smoke 通过。
- 后台认证当前账号、审批账号列表、小程序 token 校验 smoke 通过。
- 身份绑定服务单元测试通过，后台用户/客户列表接口 smoke 通过。
- React 后台 `/admin` 已能独立构建，`/admin` 和 `/admin/login` smoke 通过。
- React 客户列表、客户详情所需 API、销售单列表和销售单详情 smoke 通过。
- 旧 `/web` 页面已下线，后台入口统一为 `/admin`。
- 2026-05-24 服务层基础版已定向部署到服务器 `/opt/sjagent`，重启 `sjagent.service` 后验证 `/api/mini/home`、`/api/mini/goods/detail?id=12`、`/api/auth/wechat-quick-login` 和 `/admin` 基础 smoke 通过。
- 小程序手机号绑定当前支持直接传真实手机号字段；微信 `phoneCode` 换手机号接口尚未实现，后续小程序联调阶段补。
- React 销售单打印、打印预览和删除确认已接入 `/api/sales/<id>/print-task`、`/api/sales/<id>/print-html`、`DELETE /api/sales/<id>`，前端合同测试和构建通过。
- React 开单页基础版已接入客户搜索/创建、商品 SPU 分组搜索、颜色规格选择、客户历史价、仓库、付款状态和 `/api/sales/add` 提交；前端合同测试和构建通过。
- React 商品列表和图片资产列表已接入 `/api/product/list`、`/api/product/categories`、`/api/product/media`、`/api/product/media/<id>`；商品按 SPU 展示颜色和件规，图片资产分页懒加载。
- React 商品编辑基础版已接入 `/api/product/<id>`、`/api/product/options`、`/api/product/save`、`/api/product/upload`；图片选择器支持未绑定、本产品图片、全部图片和搜索，保存 payload 走 `ProductService.save()`。
- `git diff --check` 只有 Windows 换行提示，没有空白错误。

## 9. 下一步迁移顺序

### 第一步：查询服务继续收口

已完成：

1. `ProductService.list()`
2. `ProductService.categories()`
3. `SettingsService.get("miniapp_design")`
4. `DashboardService.summary()`
5. `DashboardService.recent_orders()`
6. `DashboardService.pending_delivery_count()`
7. `AuthService.register_web_user()`
8. `AuthService.login_web_user()`
9. `AuthService.verify_token()`
10. `AuthService.web_users()` / `approve_user()` / `reject_user()`
11. `MiniAppService.design_payload()` / `product_shelf_items()` / `user_center_payload()`

剩余优先级：

1. React 库存模块迁移。
2. React 商品编辑继续补浏览器人工验收、上传缩略图、资产分组细化。

验收标准：

- `/api/product/list` 不再直接调用 `_native_db().product_list()`。已完成。
- `/api/product/categories` 不再直接调用 `_native_db().product_categories()`。已完成。
- `/api/dashboard/summary` 不再直接调用 `_native_db().dashboard_summary()`。已完成。
- `/api/orders/recent` 不再调用 Agent 工具兜一圈。已完成。
- `/api/screen/dashboard` 的汇总和待配送统计走 `DashboardService`。已完成。
- `/api/mini/home` 的首页设计和商品货架聚合走 `MiniAppService`。已完成。
- `/api/mini/user/center` 的订单流/销售单统计走 `MiniAppService`。已完成。
- `/admin` 商品页、库存页、工作台可用。

### 第二步：认证服务独立

已完成：新增 `AuthService`，把注册、登录、审批、session、token 校验迁出 HTTP 路由。

本步要迁移的入口：

| 入口 | 目标服务 | 验收重点 |
| --- | --- | --- |
| `/api/web-auth/register` | `AuthService.register_web_user()` | 首个账号、待审批账号规则不变。 |
| `/api/web-auth/login` | `AuthService.login_web_user()` | 登录成功写 session，失败提示不变。 |
| `/api/web-auth/me` | `AuthService.current_web_user()` | 能拿到当前后台账号。 |
| `/api/web-auth/users` | `AuthService.web_users()` | 管理员能查看待审批和已启用账号。 |
| `/api/web-auth/users/<id>/approve` | `AuthService.approve_user()` | 审批后可登录。 |
| `/api/web-auth/users/<id>/reject` | `AuthService.reject_user()` | 拒绝后不可登录。 |
| token 校验 helper | `AuthService.verify_token()` | 小程序 token 校验逻辑不散在 HTTP。 |

验收标准：

- `/api/web-auth/login` 正常登录。
- `/api/web-auth/me` 能拿到当前账号。
- `/api/web-auth/users/<id>/approve` 和 reject 正常。
- 不影响已有后台账号。
- 服务层单元测试覆盖登录、审批、token 校验。
- `/admin` 打开和权限拦截正常。
状态：已完成基础迁移和 smoke，后续继续压测。

### 第三步：Dashboard 服务

已新增 `DashboardService`，只做汇总和最近记录查询。

验收标准：

- 首页数字一致。已完成。
- 最近业务记录一致。已完成。
- 查询性能不比现在慢。已完成基础 smoke，后续 React 新后台继续压测。

### 第四步：React 后台 API 合同

已完成：[React 后台 API 合同](react_admin_api_contract.md)。

验收标准：

- 每个 React 页面都有对应 API。已完成。
- 每个 API 都能说明落在哪个 service。已完成。
- 没有页面绕过 service 自己拼核心规则。已写入合同。

### 第五步：React + Radix 后台底座

已完成：创建独立 `/admin` 前端，并下线旧 `/web` 页面。

验收标准：

- `/admin` 能独立工作。
- `/admin` 能独立构建。
- React API client 统一处理 `code`、`401`、`403`。
- 登录页和工作台能用现有接口 smoke。

状态：已完成基础底座。源码在 `admin/`，构建产物在 `src/channels/http_api/admin_dist/`，Flask 使用 `/admin` 作为唯一后台页面入口。
