# 客户、订单、库存数据库明细设计

更新时间：2026-05-20

目标：把客户、用户、订单流、销售单、库存、出入库、盘点、调拨和库存日志迁移到北极星自有数据库。商品主数据见 `product_database_schema.md`，这里主要设计“交易和库存流转”。

参考业务规则：[[ERP API]]、[[数据库结构]]、[[进货规则]]、[[百鑫仓库]]、[[客户类型]]、[[全套礼盒定制]]

## 1. 总体结构

| 表 | 第一轮是否建 | 用途 | 说明 |
|---|---|---|---|
| `party` | 是 | 客户/供应商 | 客户和供应商统一放这里，旧 ERP company 表收进来 |
| `auth_user` | 是 | 系统用户 | 北极星后台、小程序、员工账号 |
| `auth_identity` | 是 | 外部账号绑定 | 绑定微信、ShopXO、飞书等登录身份 |
| `auth_session` | 是 | 登录会话 | token/session，不再依赖 ShopXO token |
| `workflow_order` | 是 | 订单流/工作流订单 | 图片识别、设计稿、制作、交付过程 |
| `workflow_order_log` | 是 | 订单流日志 | 记录订单流每次状态变化 |
| `sales_order` | 是 | 销售单主表 | 真正开单、收款、打印、扣库存的单据 |
| `sales_order_item` | 是 | 销售单明细 | 每个商品一行，保存价格和商品快照 |
| `warehouse` | 是 | 仓库 | 自己店里、百鑫仓库等 |
| `inventory_balance` | 是 | 库存余额 | 当前库存，给查询使用 |
| `stock_document` | 是 | 普通出入库单 | 采购入库、其他入库、其他出库、报损出库 |
| `stock_document_item` | 是 | 普通出入库明细 | 每个出入库商品一行 |
| `stocktake_order` | 是 | 盘点单 | 盘点某个仓库的库存 |
| `stocktake_item` | 是 | 盘点明细 | 账面数、实盘数、差异数 |
| `transfer_order` | 是 | 调拨单 | 仓库之间移动库存 |
| `transfer_order_item` | 是 | 调拨明细 | 每个调拨商品一行 |
| `inventory_ledger` | 是 | 库存日志/流水 | 所有库存变化都写这里，不允许改历史 |
| `inventory_reservation` | 后置 | 库存占用 | 以后需要未开单先锁库存时再做 |
| `print_task` | 后置 | 打印任务 | 销售单打印队列，后面接本地/云打印 |

## 2. 表之间怎么走

| 业务动作 | 写哪些表 | 库存怎么变 |
|---|---|---|
| 新增客户 | `party` | 不影响库存 |
| 用户登录 | `auth_user`、`auth_identity`、`auth_session` | 不影响库存 |
| 图片/OCR生成订单流 | `workflow_order`、`workflow_order_log` | 不直接扣库存 |
| 确认开销售单 | `sales_order`、`sales_order_item`、`inventory_ledger`、`inventory_balance` | 销售明细里的仓库扣库存 |
| 删除销售单 | 更新 `sales_order.status=deleted`，追加反向 `inventory_ledger` | 从普通对账视图隐藏，并回滚对应库存 |
| 进货/普通入库 | `stock_document`、`stock_document_item`、`inventory_ledger`、`inventory_balance` | 入库仓库加库存 |
| 普通出库/报损 | `stock_document`、`stock_document_item`、`inventory_ledger`、`inventory_balance` | 出库仓库减库存 |
| 盘点 | `stocktake_order`、`stocktake_item`、`inventory_ledger`、`inventory_balance` | 用实盘数修正余额 |
| 调拨 | `transfer_order`、`transfer_order_item`、两条 `inventory_ledger` | 调出仓减、调入仓加 |

## 3. `party` 客户/供应商表

`party` 是业务对象表，客户和供应商都放这里。旧 ERP 的 `sxo_plugins_erp_company` 可以迁过来。一个对象可以既是客户又是供应商。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 客商系统 ID | 数据库内部关联用 |
| `name` | VARCHAR(160) | 是 | 客户/供应商名称 | 如齐唯茶业、鑫创意、百鑫 |
| `kind` | VARCHAR(20) | 是 | 客商类型 | `customer` 客户、`supplier` 供应商、`both` 两者都是 |
| `contact_name` | VARCHAR(80) | 否 | 默认联系人 | 旧 ERP contacts_name |
| `phone` | VARCHAR(40) | 否 | 主手机号/识别电话 | 旧 ERP contacts_tel；和 `auth_user.phone`、`auth_identity(provider=phone)` 同步 |
| `phone_normalized` | VARCHAR(40) | 否 | 标准化手机号 | 去空格、去符号后用于唯一匹配客户 |
| `address` | VARCHAR(300) | 否 | 默认地址 | 开单、送货、寄件使用 |
| `wechat_name` | VARCHAR(120) | 否 | 微信名/常用称呼 | 方便聊天识别客户 |
| `auto_print_sales` | TINYINT | 是 | 开单后是否自动打印 | 如齐唯茶业可设为 1 |
| `settlement_type` | VARCHAR(30) | 否 | 结算方式 | `cash` 现结、`monthly` 月结、`account` 账期 |
| `tags` | JSON | 否 | 标签 | 如老客户、常做礼盒、常做泡袋 |
| `note` | TEXT | 否 | 内部备注 | 客户特殊要求、供应商规则 |
| `source` | VARCHAR(30) | 是 | 来源 | `migration`、`manual`、`wechat` |
| `status` | VARCHAR(20) | 是 | 状态 | `active`、`inactive`、`deleted` |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |
| `deleted_at` | DATETIME | 否 | 软删除时间 | 不物理删除 |

手机号匹配规则：小程序或 Web 用户绑定手机号后，先写 `auth_user.phone`，同时写一条 `auth_identity(provider='phone')`。系统用标准化手机号匹配 `party.phone_normalized`，匹配到后自动填 `auth_user.linked_party_id`。这样用户账号和客户资料仍然分开，但手机号可以把两边连起来。

唯一约束建议：`phone_normalized` 唯一；为空时允许多个客户没有手机号。

## 4. `auth_user` 用户表

`auth_user` 是登录北极星的人，不等于客户。员工、管理员、小程序用户都属于用户；客户资料仍然放 `party`。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 用户系统 ID | 数据库内部关联用 |
| `username` | VARCHAR(80) | 是 | 登录账号 | 手机号、邮箱或自定义账号 |
| `password_hash` | VARCHAR(255) | 否 | 密码哈希 | 微信免密登录用户可为空 |
| `display_name` | VARCHAR(80) | 是 | 显示名 | 页面右上角、操作日志显示 |
| `phone` | VARCHAR(40) | 否 | 手机号 | 和客户 `party.phone` 同步；可用于找回、通知、自动识别客户 |
| `role` | VARCHAR(30) | 是 | 角色 | `admin`、`staff`、`viewer`、`customer` |
| `linked_party_id` | BIGINT | 否 | 关联客户 | 客户账号才需要，指向 `party.id` |
| `approval_status` | VARCHAR(20) | 是 | 审批状态 | `pending`、`approved`、`rejected` |
| `is_active` | TINYINT | 是 | 是否启用 | 停用后不能登录 |
| `is_admin` | TINYINT | 是 | 是否管理员 | 兼容当前 React 后台管理员逻辑 |
| `last_login_at` | DATETIME | 否 | 最后登录时间 | 审计用 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |

## 5. `auth_identity` 外部账号绑定表

一个用户可能有多个外部身份，比如手机号、微信 openid、ShopXO user id、飞书 open_id。不要把这些字段全塞进 `auth_user`。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 绑定 ID | 自增 |
| `user_id` | BIGINT | 是 | 用户 ID | 指向 `auth_user.id` |
| `provider` | VARCHAR(30) | 是 | 外部平台/身份类型 | `phone`、`wechat`、`shopxo`、`feishu`、`password` |
| `external_user_id` | VARCHAR(160) | 是 | 外部用户 ID | 手机号标准值、ShopXO 用户 ID、飞书 open_id 等 |
| `openid` | VARCHAR(160) | 否 | 微信 openid | 微信登录使用 |
| `unionid` | VARCHAR(160) | 否 | 微信 unionid | 多端统一身份时使用 |
| `raw_profile` | JSON | 否 | 外部资料快照 | 昵称、头像等 |
| `is_enabled` | TINYINT | 是 | 是否启用 | 解绑时停用 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |

唯一约束建议：`provider + external_user_id` 唯一，防止同一个手机号、微信或 ShopXO 身份绑定到多个用户。

## 6. `auth_session` 登录会话表

这张表替代 ShopXO token 校验，React 后台、小程序、后续移动端都可以用。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 会话 ID | 自增 |
| `user_id` | BIGINT | 是 | 用户 ID | 指向 `auth_user.id` |
| `token_hash` | CHAR(64) | 是 | token 哈希 | 不明文保存 token |
| `client_type` | VARCHAR(30) | 否 | 客户端类型 | `web`、`miniapp`、`feishu`、`api` |
| `ip` | VARCHAR(80) | 否 | 登录 IP | 审计用 |
| `user_agent` | VARCHAR(500) | 否 | 浏览器/设备信息 | 审计用 |
| `expires_at` | DATETIME | 是 | 过期时间 | token 到期 |
| `revoked_at` | DATETIME | 否 | 注销时间 | 主动退出或管理员踢下线 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |

## 7. `workflow_order` 订单流/工作流订单表

`workflow_order` 管“还没完全变成销售单”的过程，比如客户发图片、OCR识别、设计稿制作、是否丝印、是否做完、是否交付。它可以关联销售单，但不要和销售单合并。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 订单流 ID | 自增 |
| `workflow_no` | VARCHAR(80) | 是 | 订单流编号 | 如 `WF202605200001` |
| `customer_id` | BIGINT | 否 | 客户 ID | 能匹配到客户时指向 `party.id` |
| `customer_name_snapshot` | VARCHAR(160) | 是 | 客户名称快照 | 即使客户改名，历史订单仍清楚 |
| `customer_phone_snapshot` | VARCHAR(40) | 否 | 客户电话快照 | 下单时的电话 |
| `sku_id` | BIGINT | 否 | 商品 SKU | 能匹配到商品时指向 `product_sku.id` |
| `sku_no_snapshot` | VARCHAR(80) | 否 | SKU 编号快照 | 如 SJ0506 |
| `goods_name_snapshot` | VARCHAR(180) | 是 | 商品名快照 | OCR 或人工确认后的商品名 |
| `color_snapshot` | VARCHAR(60) | 否 | 颜色快照 | 红色、黄色等 |
| `quantity` | DECIMAL(12,3) | 是 | 数量 | 客户确认的数量 |
| `unit_id` | BIGINT | 否 | 单位 | 套、捆、个等 |
| `order_type` | VARCHAR(40) | 是 | 订单流类型 | `design`、`screen_print`、`bag`、`full_service`、`other` |
| `order_image_urls` | JSON | 否 | 订单图片 | 客户图片、设计稿、OCR 图片 URL |
| `ocr_text` | TEXT | 否 | OCR 原文 | 方便追溯智能体识别依据 |
| `is_screen_print` | TINYINT | 是 | 是否丝印 | 兼容现有流程字段 |
| `is_made` | TINYINT | 是 | 是否制作完成 | 当前 React 后台常用状态 |
| `is_delivered` | TINYINT | 是 | 是否已交付 | 当前 React 后台常用状态 |
| `sales_order_id` | BIGINT | 否 | 关联销售单 | 开单后指向 `sales_order.id` |
| `status` | VARCHAR(30) | 是 | 总状态 | `pending`、`confirmed`、`processing`、`done`、`canceled` |
| `remark` | TEXT | 否 | 备注 | 人工补充要求 |
| `source` | VARCHAR(30) | 是 | 来源 | `image_ocr`、`manual`、`chat`、`migration` |
| `created_by_user_id` | BIGINT | 否 | 创建人 | 指向 `auth_user.id` |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |
| `deleted_at` | DATETIME | 否 | 软删除时间 | 不物理删除 |

## 8. `workflow_order_log` 订单流日志表

订单流状态变化要能查出来，比如谁把“未制作”改成“已制作”，谁关联了销售单。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 日志 ID | 自增 |
| `workflow_order_id` | BIGINT | 是 | 订单流 ID | 指向 `workflow_order.id` |
| `action` | VARCHAR(40) | 是 | 操作 | `create`、`update_status`、`attach_image`、`link_sales`、`delete` |
| `field_name` | VARCHAR(80) | 否 | 变化字段 | 如 `is_made`、`status` |
| `old_value` | TEXT | 否 | 旧值 | 修改前 |
| `new_value` | TEXT | 否 | 新值 | 修改后 |
| `operator_user_id` | BIGINT | 否 | 操作人 | 指向 `auth_user.id` |
| `note` | VARCHAR(500) | 否 | 操作说明 | 人工说明或系统说明 |
| `created_at` | DATETIME | 是 | 发生时间 | 新库时间 |

## 9. `sales_order` 销售单主表

销售单是开单、价格、打印、扣库存的核心。删除销售单默认做软删除，从普通列表和对账统计隐藏，并写反向库存流水。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 销售单 ID | 自增 |
| `sales_no` | VARCHAR(80) | 是 | 销售单号 | 如 `XS202605200001`，唯一 |
| `customer_id` | BIGINT | 是 | 客户 ID | 指向 `party.id` |
| `customer_name_snapshot` | VARCHAR(160) | 是 | 客户名称快照 | 历史单据不随客户改名变化 |
| `status` | VARCHAR(30) | 是 | 单据状态 | `draft`、`completed`、`canceled`、`deleted` |
| `pay_type` | VARCHAR(30) | 否 | 收款方式 | `cash`、`wechat`、`monthly`、`account` |
| `pay_status` | VARCHAR(30) | 是 | 收款状态 | `unpaid`、`partial`、`paid` |
| `total_quantity` | DECIMAL(12,3) | 是 | 总数量 | 明细数量汇总 |
| `goods_amount` | DECIMAL(12,2) | 是 | 商品金额 | 明细金额汇总 |
| `discount_amount` | DECIMAL(12,2) | 是 | 优惠金额 | 没有优惠填 0 |
| `receivable_amount` | DECIMAL(12,2) | 是 | 应收金额 | 商品金额 - 优惠 |
| `source` | VARCHAR(30) | 是 | 来源 | `manual`、`workflow`、`chat`、`migration` |
| `source_workflow_id` | BIGINT | 否 | 来源订单流 | 一张销售单由一个订单流生成时填写 |
| `print_status` | VARCHAR(30) | 是 | 打印状态 | `none`、`queued`、`printed`、`failed` |
| `note` | TEXT | 否 | 备注 | 打印备注、开单说明 |
| `created_by_user_id` | BIGINT | 否 | 开单人 | 指向 `auth_user.id` |
| `sales_at` | DATETIME | 是 | 开单时间 | 业务发生时间 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |
| `canceled_at` | DATETIME | 否 | 取消时间 | 取消销售单时填写 |
| `cancel_reason` | VARCHAR(500) | 否 | 取消原因 | 用于查账 |
| `deleted_at` | DATETIME | 否 | 软删除时间 | 删除销售单时填写 |
| `deleted_by_user_id` | BIGINT | 否 | 删除人 | 关联 `auth_user.id` |
| `delete_reason` | VARCHAR(500) | 否 | 删除原因 | 默认 `web delete` |

## 10. `sales_order_item` 销售单明细表

明细必须保存商品和价格快照。以后商品改名、改颜色、改价格，不影响历史单据和客户历史成交价。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 明细 ID | 自增 |
| `sales_order_id` | BIGINT | 是 | 销售单 ID | 指向 `sales_order.id` |
| `line_no` | INT | 是 | 行号 | 一张单内从 1 开始 |
| `sku_id` | BIGINT | 是 | SKU ID | 指向 `product_sku.id` |
| `sku_no_snapshot` | VARCHAR(80) | 是 | SKU 编号快照 | 如 SJ0506 |
| `title_snapshot` | VARCHAR(180) | 是 | 商品标题快照 | 开单时客户能看懂的名称 |
| `color_snapshot` | VARCHAR(60) | 否 | 颜色快照 | 红色、黄色等 |
| `warehouse_id` | BIGINT | 是 | 发货仓库 | 该商品从哪个仓库扣 |
| `unit_id` | BIGINT | 是 | 单位 | 套、捆、个等 |
| `quantity` | DECIMAL(12,3) | 是 | 销售数量 | 开单实际数量 |
| `unit_price` | DECIMAL(12,2) | 是 | 单价 | 开单价格 |
| `amount` | DECIMAL(12,2) | 是 | 行金额 | 数量 × 单价 |
| `cost_price_snapshot` | DECIMAL(12,2) | 否 | 成本价快照 | 利润统计用 |
| `price_source` | VARCHAR(30) | 否 | 价格来源 | `history`、`default`、`manual`、`customer_rule` |
| `workflow_order_id` | BIGINT | 否 | 来源订单流 | 明细对应的订单流 |
| `note` | VARCHAR(500) | 否 | 明细备注 | 特殊说明 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |

## 11. `warehouse` 仓库表

仓库先保留现有两个：自己店里、百鑫仓库。后续如果有供应商仓、临时仓，也能继续加。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 仓库 ID | 可保留旧 ID：1 自己店里、2 百鑫仓库 |
| `code` | VARCHAR(60) | 是 | 仓库编码 | `self_store`、`baixin` |
| `name` | VARCHAR(120) | 是 | 仓库名称 | 自己店里、百鑫仓库 |
| `warehouse_type` | VARCHAR(30) | 是 | 仓库类型 | `store`、`main`、`supplier`、`temporary` |
| `address` | VARCHAR(300) | 否 | 地址 | 仓库地址 |
| `contact_name` | VARCHAR(80) | 否 | 联系人 | 仓库联系人 |
| `phone` | VARCHAR(40) | 否 | 电话 | 仓库电话 |
| `is_default_sales` | TINYINT | 是 | 是否默认销售仓 | 通常百鑫为 1 |
| `is_default_inbound` | TINYINT | 是 | 是否默认入库仓 | 通常百鑫为 1 |
| `sort_order` | INT | 否 | 排序 | 页面展示 |
| `is_enabled` | TINYINT | 是 | 是否启用 | 停用后不再新建单据 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |

## 12. `inventory_balance` 库存余额表

这张表只存当前库存，给查询和开单校验用。它不是查账依据，查账看 `inventory_ledger`。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 库存余额 ID | 自增 |
| `sku_id` | BIGINT | 是 | SKU ID | 指向 `product_sku.id` |
| `warehouse_id` | BIGINT | 是 | 仓库 ID | 指向 `warehouse.id` |
| `unit_id` | BIGINT | 是 | 单位 | 套、捆、个等 |
| `quantity` | DECIMAL(12,3) | 是 | 当前库存数 | 实际余额 |
| `reserved_qty` | DECIMAL(12,3) | 是 | 已占用数量 | 第一轮可为 0，后续有库存占用再用 |
| `available_qty` | DECIMAL(12,3) | 是 | 可用库存 | `quantity - reserved_qty`，可做生成字段 |
| `low_stock_qty` | DECIMAL(12,3) | 否 | 低库存预警线 | 低于该值提醒 |
| `last_ledger_id` | BIGINT | 否 | 最近流水 ID | 指向 `inventory_ledger.id` |
| `version` | BIGINT | 是 | 乐观锁版本 | 防止并发扣错库存 |
| `updated_at` | DATETIME | 是 | 更新时间 | 每次库存变化更新 |

唯一约束建议：`sku_id + warehouse_id + unit_id` 唯一。

## 13. `stock_document` 普通出入库单主表

普通出入库用一套表，不把采购入库、其他入库、报损出库拆成很多表。盘点和调拨因为业务语义特殊，单独建表。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 单据 ID | 自增 |
| `doc_no` | VARCHAR(80) | 是 | 出入库单号 | 如 `RK202605200001`、`CK202605200001` |
| `doc_type` | VARCHAR(30) | 是 | 单据类型 | `purchase_in`、`other_in`、`return_in`、`other_out`、`loss_out` |
| `direction` | VARCHAR(10) | 是 | 方向 | `in` 入库、`out` 出库 |
| `warehouse_id` | BIGINT | 是 | 仓库 | 入库进哪个仓、出库从哪个仓 |
| `related_party_id` | BIGINT | 否 | 关联客户/供应商 | 供应商入库或客户退货时用 |
| `related_sales_order_id` | BIGINT | 否 | 关联销售单 | 销售退货、补发等场景 |
| `status` | VARCHAR(30) | 是 | 状态 | `draft`、`confirmed`、`canceled` |
| `total_quantity` | DECIMAL(12,3) | 是 | 总数量 | 明细汇总 |
| `note` | TEXT | 否 | 备注 | 进货原因、报损原因 |
| `created_by_user_id` | BIGINT | 否 | 创建人 | 指向 `auth_user.id` |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `confirmed_at` | DATETIME | 否 | 确认时间 | 库存生效时间 |
| `canceled_at` | DATETIME | 否 | 取消时间 | 取消时填写 |

## 14. `stock_document_item` 普通出入库明细表

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 明细 ID | 自增 |
| `stock_document_id` | BIGINT | 是 | 出入库单 ID | 指向 `stock_document.id` |
| `line_no` | INT | 是 | 行号 | 单据内排序 |
| `sku_id` | BIGINT | 是 | SKU ID | 指向 `product_sku.id` |
| `sku_no_snapshot` | VARCHAR(80) | 是 | SKU 编号快照 | 查账用 |
| `title_snapshot` | VARCHAR(180) | 是 | 商品标题快照 | 查账用 |
| `unit_id` | BIGINT | 是 | 单位 | 套、捆、个等 |
| `quantity` | DECIMAL(12,3) | 是 | 数量 | 入库或出库数量，正数 |
| `unit_cost` | DECIMAL(12,2) | 否 | 成本单价 | 入库成本或报损参考 |
| `amount` | DECIMAL(12,2) | 否 | 金额 | 数量 × 成本单价 |
| `reason` | VARCHAR(200) | 否 | 原因 | 报损、补录、进货等 |
| `ledger_id` | BIGINT | 否 | 对应库存流水 | 指向 `inventory_ledger.id` |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |

## 15. `stocktake_order` 盘点单主表

盘点是“把系统库存改成实盘库存”。它和普通出入库不一样，所以单独放。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 盘点单 ID | 自增 |
| `stocktake_no` | VARCHAR(80) | 是 | 盘点单号 | 如 `PD202605200001` |
| `warehouse_id` | BIGINT | 是 | 盘点仓库 | 指向 `warehouse.id` |
| `scope_type` | VARCHAR(30) | 是 | 盘点范围 | `all`、`category`、`sku_list` |
| `scope_value` | JSON | 否 | 范围值 | 分类 ID 列表或 SKU ID 列表 |
| `status` | VARCHAR(30) | 是 | 状态 | `draft`、`counting`、`confirmed`、`canceled` |
| `total_diff_qty` | DECIMAL(12,3) | 是 | 总差异数 | 明细差异汇总 |
| `note` | TEXT | 否 | 备注 | 盘点说明 |
| `created_by_user_id` | BIGINT | 否 | 创建人 | 指向 `auth_user.id` |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `confirmed_at` | DATETIME | 否 | 确认时间 | 库存修正时间 |

## 16. `stocktake_item` 盘点明细表

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 明细 ID | 自增 |
| `stocktake_order_id` | BIGINT | 是 | 盘点单 ID | 指向 `stocktake_order.id` |
| `sku_id` | BIGINT | 是 | SKU ID | 指向 `product_sku.id` |
| `unit_id` | BIGINT | 是 | 单位 | 套、捆、个等 |
| `book_qty` | DECIMAL(12,3) | 是 | 账面库存 | 盘点前系统数量 |
| `counted_qty` | DECIMAL(12,3) | 是 | 实盘库存 | 人工盘点数量 |
| `diff_qty` | DECIMAL(12,3) | 是 | 差异数量 | 实盘 - 账面 |
| `reason` | VARCHAR(200) | 否 | 差异原因 | 少货、补录、损耗等 |
| `ledger_id` | BIGINT | 否 | 对应库存流水 | 指向 `inventory_ledger.id` |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |

## 17. `transfer_order` 调拨单主表

调拨必须同一事务完成：调出仓扣库存，调入仓加库存。不要只扣不加，也不要只加不扣。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 调拨单 ID | 自增 |
| `transfer_no` | VARCHAR(80) | 是 | 调拨单号 | 如 `DB202605200001` |
| `from_warehouse_id` | BIGINT | 是 | 调出仓库 | 如自己店里 |
| `to_warehouse_id` | BIGINT | 是 | 调入仓库 | 如百鑫仓库 |
| `status` | VARCHAR(30) | 是 | 状态 | `draft`、`confirmed`、`canceled` |
| `total_quantity` | DECIMAL(12,3) | 是 | 总调拨数量 | 明细汇总 |
| `note` | TEXT | 否 | 备注 | 调拨原因 |
| `created_by_user_id` | BIGINT | 否 | 创建人 | 指向 `auth_user.id` |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `confirmed_at` | DATETIME | 否 | 确认时间 | 库存生效时间 |
| `canceled_at` | DATETIME | 否 | 取消时间 | 取消时填写 |

## 18. `transfer_order_item` 调拨明细表

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 明细 ID | 自增 |
| `transfer_order_id` | BIGINT | 是 | 调拨单 ID | 指向 `transfer_order.id` |
| `line_no` | INT | 是 | 行号 | 单据内排序 |
| `sku_id` | BIGINT | 是 | SKU ID | 指向 `product_sku.id` |
| `sku_no_snapshot` | VARCHAR(80) | 是 | SKU 编号快照 | 查账用 |
| `title_snapshot` | VARCHAR(180) | 是 | 商品标题快照 | 查账用 |
| `unit_id` | BIGINT | 是 | 单位 | 套、捆、个等 |
| `quantity` | DECIMAL(12,3) | 是 | 调拨数量 | 正数 |
| `out_ledger_id` | BIGINT | 否 | 调出流水 | 指向 `inventory_ledger.id` |
| `in_ledger_id` | BIGINT | 否 | 调入流水 | 指向 `inventory_ledger.id` |
| `note` | VARCHAR(500) | 否 | 备注 | 单行说明 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |

## 19. `inventory_ledger` 库存日志/流水表

`inventory_ledger` 是库存查账核心。只追加，不修改，不删除。`inventory_balance` 可以从这张表重算出来。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 流水 ID | 自增 |
| `ledger_no` | VARCHAR(80) | 是 | 流水号 | 唯一，方便查账 |
| `sku_id` | BIGINT | 是 | SKU ID | 指向 `product_sku.id` |
| `sku_no_snapshot` | VARCHAR(80) | 是 | SKU 编号快照 | 查账用 |
| `warehouse_id` | BIGINT | 是 | 仓库 ID | 哪个仓发生变化 |
| `unit_id` | BIGINT | 是 | 单位 | 套、捆、个等 |
| `change_qty` | DECIMAL(12,3) | 是 | 变化数量 | 入库为正，出库为负，盘点按差异正负 |
| `before_qty` | DECIMAL(12,3) | 是 | 变化前库存 | 写流水前余额 |
| `after_qty` | DECIMAL(12,3) | 是 | 变化后库存 | 写流水后余额 |
| `biz_type` | VARCHAR(40) | 是 | 业务类型 | `sales_out`、`sales_delete`、`sales_cancel`、`stock_in`、`stock_out`、`stocktake_adjust`、`transfer_out`、`transfer_in`、`migration_init` |
| `biz_id` | BIGINT | 否 | 业务单据 ID | 销售单、出入库单、盘点单、调拨单 ID |
| `biz_item_id` | BIGINT | 否 | 业务明细 ID | 对应明细行 ID |
| `counterparty_warehouse_id` | BIGINT | 否 | 对方仓库 | 调拨时记录另一边仓库 |
| `operator_user_id` | BIGINT | 否 | 操作人 | 指向 `auth_user.id` |
| `note` | VARCHAR(500) | 否 | 备注 | 系统说明或人工说明 |
| `occurred_at` | DATETIME | 是 | 发生时间 | 业务生效时间 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |

## 20. 写入规则

| 规则 | 说明 |
|---|---|
| 销售单默认软删除 | 删除销售单时改 `sales_order.status=deleted`，再写 `sales_delete` 反向库存流水，普通对账视图过滤掉 |
| 库存余额不手工改 | 所有库存变化都必须先写业务单据和 `inventory_ledger`，再更新 `inventory_balance` |
| 调拨写两条流水 | 同一个调拨明细写 `transfer_out` 和 `transfer_in`，两边数量绝对值相等 |
| 盘点写差异流水 | 实盘数和账面数不同才写 `stocktake_adjust`，差异为 0 可以不写流水 |
| 出入库单确认后才生效 | 草稿不动库存，确认时统一写流水和更新余额 |
| 销售明细保存快照 | 商品名、颜色、编号、价格都保存开单时快照，用于历史价和查账 |
| 工作流不直接扣库存 | 订单流只是业务过程，确认开销售单时才扣库存；以后需要锁库存再加 `inventory_reservation` |

## 21. 第一轮先不做或后置

| 表/能力 | 建议 | 原因 |
|---|---|---|
| `inventory_reservation` | 后置 | 现在业务主要是确认开单后扣库存；未开单先锁库存以后再加 |
| `sales_payment` | 后置 | 第一轮可把收款状态和方式放 `sales_order`，复杂收款再拆 |
| `party_contact` | 后置 | 当前默认联系人/电话/地址够用，多个联系人再拆 |
| `auth_role`、`auth_permission` | 后置 | 第一轮 `role` + `is_admin` 足够，精细权限再拆 |
| `print_task` | 后置 | 销售闭环稳定后再独立打印队列 |

## 22. 当前落地状态

2026-05-20 已建表并导入第一批业务数据到 `sjagent_core`。

| 表 | 当前数量 | 来源/说明 |
|---|---:|---|
| `warehouse` | 2 | 旧 ERP 仓库，保留 1 自己店里、2 百鑫仓库 |
| `party` | 63 | 旧 ERP 客户/供应商；客户电话旧库为空，暂未自动关联用户 |
| `auth_user` | 60 | Web 用户 2 个 + ShopXO 用户 58 个 |
| `auth_identity` | 104 | phone 3、web 2、shopxo 58、wechat 41；只保留合法 11 位手机号 |
| `inventory_balance` | 260 | 旧库存余额 261 行中 260 行成功映射到新 SKU |
| `inventory_ledger` | 260 | 初始库存流水，`biz_type=migration_init` |
| `sales_order` | 149 | 旧 ERP 销售单主表 |
| `sales_order_item` | 214 | 旧 ERP 当前销售单可映射明细；孤儿明细和缺商品映射明细未进主表 |
| `workflow_order` | 108 | 普通工作流 105 + BX 工作流 3 |
| `workflow_order_log` | 108 | 每张迁移工作流订单写一条导入日志 |
| `stock_document` | 266 | 普通入库 242 + 普通出库 24 |
| `stock_document_item` | 318 | 普通出入库明细 319 行中 318 行成功映射到新 SKU |
| `stocktake_order` | 145 | 旧 ERP 盘点单 |
| `stocktake_item` | 258 | 旧 ERP 盘点明细；旧表无账面数，迁移时 `book_qty=counted_qty`、`diff_qty=0` |
| `transfer_order` | 19 | 旧 ERP 调拨单 |
| `transfer_order_item` | 19 | 旧 ERP 调拨明细 |

异常项：旧 `product_id=877` 没有 `migration_product_ref` 映射，导致 1 条库存余额、1 条销售明细、1 条普通入库明细未迁移。旧销售明细一共 295 行，其中 80 行引用已不存在销售单，暂不进入 `sales_order_item`。

导入报告：`data/migration/business_core_import_report.json`。
