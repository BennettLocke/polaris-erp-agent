# 北极星自有业务系统迁移表

更新时间：2026-05-20

目标：把当前依赖 ShopXO 商城库和 ERP 插件库的业务能力，逐步迁移到北极星自己的数据库和服务层。迁移期间先兼容旧数据，稳定后再下线 ShopXO/ERP 写链路。

详细字段文档：
- 商品中心：`docs/product_database_schema.md`
- 客户、用户、订单、库存：`docs/business_database_schema.md`

## 1. 当前依赖总表

| 业务能力 | 当前依赖 | 当前位置 | 问题 | 迁移目标 |
|---|---|---|---|---|
| 商品列表/搜索 | `sxo_plugins_erp_product`、`sxo_goods`、ERP API `ProductList` | `src/channels/http_api/__init__.py`、`src/engine/db_client.py` | 商城商品和 ERP 商品两套数据，需要同步，字段语义混杂 | 统一到 `product_spu` + `product_sku` |
| 商品编辑/新增 | ERP API `ProductSave`、`ProductAdd` | `src/engine/api_client.py`、`src/skills/bag_upload/workflow.py` | 写入别人插件接口，字段结构受 ERP 表单限制 | 自有 `CatalogService.save_product` |
| 商品上下架 | ERP API `ProductShelvesUpdate` + ShopXO 商品表 | `src/channels/http_api/__init__.py` | 上下架本质是商城展示状态，不应影响库存商品主数据 | 自有 `product_channel_listing` |
| 库存查询 | 直查 `sxo_plugins_erp_warehouse_product_inventory` | `src/engine/db_client.py`、`src/core/tools/erp_tools.py` | 只有余额表，业务语义依赖旧 ERP | 自有 `inventory_balance` |
| 库存变动 | ERP API `OtherEnterAdd`、`InventoryTransfer`、`InventorySync`、`SalesAdd` | `src/engine/api_client.py` | 库存变化藏在 API 副作用里，不好审计 | 自有库存流水 `inventory_ledger` |
| 销售开单 | ERP API `SalesAdd` | `src/core/nodes/executor.py`、`src/core/tools/erp_tools.py` | 开单、扣库存、价格快照耦合在外部系统 | 自有 `sales_order` + 事务扣库存 |
| 删除销售单 | ERP API `SalesDelete` | `src/core/tools/erp_tools.py` | 删除语义不透明，依赖旧系统自动回滚库存 | 自有软删除 + 反向库存流水 |
| 客户/供应商 | `sxo_plugins_erp_company`、API `CompanyList/CompanyAdd` | `src/core/tools/erp_tools.py`、`http_api` | 客户和供应商字段依赖 ERP 命名 | 自有 `party` |
| 工作流订单 | `sxo_workflow_order`、API `WorkflowOrder*` | `src/core/tools/order_tools.py` | 设计稿订单依赖 ShopXO 表 | 自有 `workflow_order` |
| 打印任务 | ERP API `SalesPrintTask*` | `src/core/tools/order_tools.py` | 打印队列受 ERP 页面影响 | 自有 `print_task` |
| 小程序登录 | ShopXO `user/login`、`tokenuserinfo` | `src/channels/http_api/__init__.py` | 用户认证绑定商城账号 | 自有 `auth_user` + token/session |
| 语音热词 | 直查 ERP 商品、客户、仓库、销售明细 | `src/services/volc_realtime_asr.py` | 火山 ASR 请求动态携带热词 | 从自有商品/客户/仓库生成 |

## 2. 目标数据模型总表

| 新表/模块 | 核心含义 | 关键字段 | 替代旧表/接口 | 备注 |
|---|---|---|---|---|
| `product_spu` | 商品组/款式 | `id`、`title`、`series`、`size_label`、`available_colors`、`product_type` | ERP `group_key` | 例如 `【喜悦】半斤`，旧 group_key 只进迁移对照 |
| `product_sku` | 可销售、可库存 SKU | `id`、`spu_id`、`sku_no`、`primary_category_id`、`category_ids`、`color`、`unit_id`、`price`、`cost_price`、`status` | `sxo_plugins_erp_product` | 业务唯一编号统一用 `SJxx`，分类直接写在 SKU，旧乱编号不进主表 |
| `product_category` | 商品分类 | `id`、`name`、`parent_id`、`sort`、`is_enabled` | ERP/ShopXO 分类表 | 礼盒、泡袋、辅料、服务统一分类 |
| `product_unit` | 单位 | `id`、`name` | `sxo_plugins_erp_unit` | 当前有套、捆、个、斤、张 |
| `unit_conversion` | 件套换算 | `spu_id`、`from_unit`、`to_unit`、`ratio`、`rule_source` | `simple_desc` 中的 `20套/件` | 第一轮可先收敛到 `product_spu.case_pack_qty` |
| `warehouse` | 仓库 | `id`、`name`、`alias`、`address`、`is_enabled` | `sxo_plugins_erp_warehouse` | 保留 1 自己店里、2 百鑫仓库 |
| `inventory_balance` | 库存余额 | `sku_id`、`warehouse_id`、`unit_id`、`quantity` | `sxo_plugins_erp_warehouse_product_inventory` | 只存当前余额 |
| `inventory_ledger` | 库存流水 | `id`、`sku_id`、`warehouse_id`、`change_qty`、`biz_type`、`biz_id`、`before_qty`、`after_qty` | ERP 各类库存副作用 | 所有库存变化必须落流水 |
| `party` | 客户/供应商 | `id`、`name`、`kind`、`contact_name`、`phone`、`phone_normalized`、`address`、`is_enabled` | `sxo_plugins_erp_company` | `kind` 可为 customer/supplier/both；手机号用于匹配小程序用户 |
| `auth_user` | 北极星用户 | `id`、`username`、`display_name`、`phone`、`linked_party_id`、`role`、`approval_status`、`is_active` | `sjagent_web_users`、`sxo_user` | 用户账号不等于客户资料，但手机号可同步关联客户 |
| `auth_identity` | 外部账号绑定 | `user_id`、`provider`、`external_user_id`、`openid`、`unionid` | `sxo_user_platform`、ShopXO token | 绑定手机号、微信、ShopXO、飞书身份 |
| `auth_session` | 登录会话 | `user_id`、`token_hash`、`client_type`、`expires_at` | ShopXO token/session | React 后台/小程序自有登录 |
| `sales_order` | 销售单主表 | `id`、`sales_no`、`customer_id`、`status`、`total_price`、`created_at` | `sxo_plugins_erp_sales` | 删除改为软删除，不进入普通对账 |
| `sales_order_item` | 销售单明细 | `sales_id`、`sku_id`、`title_snapshot`、`spec_snapshot`、`quantity`、`price`、`warehouse_id` | `sxo_plugins_erp_sales_detail` | 必须保存商品快照 |
| `stock_document` | 普通出入库单 | `doc_no`、`doc_type`、`direction`、`warehouse_id`、`status` | `OtherEnterAdd`、`OtherOutAdd` | 采购入库、其他入库、报损出库等合并 |
| `stock_document_item` | 普通出入库明细 | `stock_document_id`、`sku_id`、`quantity`、`unit_id` | 其他出入库明细 | 每个商品一行 |
| `transfer_order` | 仓库调拨单 | `from_warehouse_id`、`to_warehouse_id`、`status` | `InventoryTransfer` | 调出扣、调入加，必须同事务 |
| `transfer_order_item` | 调拨明细 | `transfer_order_id`、`sku_id`、`quantity`、`unit_id` | 调拨明细 | 每个商品一行，两条库存流水 |
| `stocktake_order` | 盘点单 | `warehouse_id`、`status`、`scope_type`、`note` | `InventorySync`、`InventoryCheckAdd` | 支持绝对库存修正 |
| `stocktake_item` | 盘点明细 | `stocktake_order_id`、`sku_id`、`book_qty`、`counted_qty`、`diff_qty` | 盘点明细 | 只按差异写库存流水 |
| `workflow_order` | 设计稿/生产/交付订单 | `customer_name`、`sku_id`、`goods_name_snapshot`、`images`、`is_made`、`is_delivered` | `sxo_workflow_order` | 可继续支持无 SKU 的设计稿订单 |
| `workflow_order_log` | 工作流订单日志 | `workflow_order_id`、`action`、`field_name`、`old_value`、`new_value` | 状态更新操作 | 追踪谁改了制作/交付/关联销售单 |
| `product_media` | 商品图片资产 | `sku_id`、`spu_id`、`media_type`、`url`、`storage`、`path`、`sha256` | ShopXO/OSS 图片字段 | 商品主图、详情图、源图、缩略图统一管理 |
| `product_channel_listing` | 商城/小程序展示状态 | `sku_id`、`channel`、`is_shelves`、`display_title`、`display_images` | `sxo_goods` | 未来可接小程序商城，不污染 SKU |
| `print_task` | 打印任务 | `sales_id`、`status`、`printer`、`printed_at` | `SalesPrintTask*` | 后续接本地打印/云打印 |
| `external_ref` | 旧系统映射 | `entity_type`、`entity_id`、`source`、`external_id` | 同步日志和旧 ID | 迁移期查账和回滚用 |

## 3. 商品数据放置规则

| 商品类型 | SPU 怎么放 | SKU 怎么放 | 库存策略 | 关键结构字段 |
|---|---|---|---|---|
| 礼盒类 | 一款一组，例如 `【见喜】一两` | 颜色/规格为 SKU，例如红色、黄色 | 查库存，销售扣库存 | `series`、`box_size`、`color`、`piece_ratio`、`min_purchase_rule` |
| 泡袋类 | SJ 编号或茶类款式可作为组 | 每个 SJ 编号/版型为 SKU | 默认弱库存或不查库存，按业务再开 | `sku_no`、`tea_type`、`bag_type`；`bag_type` 只放长泡袋/短泡袋/红茶袋/宽版/空白，公版放分类 |
| 辅料 | 可按品类建组 | 具体规格为 SKU | 视品类决定是否查库存 | `material_type`、`unit_id`、`price` |
| 加工服务 | 服务项为 SPU | 服务档位为 SKU | 不查库存 | `service_type`、`pricing_rule` |
| 快递纸箱/包装耗材 | 品类为 SPU | 尺寸/规格为 SKU | 可查库存 | `size`、`unit_id`、`warehouse_id` |

## 4. 旧表到新表映射

| 旧来源 | 当前规模/作用 | 新目标 | 迁移方式 | 校验方法 |
|---|---:|---|---|---|
| `sxo_plugins_erp_product` | 约 922 条 ERP 商品 | `product_sku`、部分生成 `product_spu` | 旧 `id/group_key` 只参与迁移聚合和对照，不进商品主表 | SKU 数一致，标题/颜色/价格抽样一致 |
| `sxo_plugins_erp_product_base` | 约 922 条规格/单位/编号 | `product_sku`、`unit_conversion` | 合并 `unit_id`、`price`、`cost_price`，旧 coding 只参与迁移匹配 | 新业务编号统一生成 `sku_no` |
| `sxo_plugins_erp_product_category` | 22 个分类 | `product_category` | 原 ID 保留 | 分类数量一致 |
| `sxo_plugins_erp_product_category_join` | 商品分类关联 | `product_sku.primary_category_id/category_ids` | 按 SKU 汇总分类 ID；主分类取原主分类或最常用分类 | 每分类 SKU 计数一致 |
| `sxo_goods` | 约 563 条商城商品 | `product_channel_listing`、`product_media` | 通过同步日志和旧数据关联 SKU | 上架状态和主图抽样一致 |
| `sxo_plugins_erp_system_goods_sync_product_log` | ERP/商城同步日志 | `external_ref`、展示关联 | 取最新 product_id/goods_id 关系 | 每个已同步 SKU 能找到旧 goods_id |
| `sxo_plugins_erp_warehouse` | 2 个仓库 | `warehouse` | 原 ID 保留 | 1=自己店里，2=百鑫仓库 |
| `sxo_plugins_erp_warehouse_product_inventory` | 约 259 行库存余额 | `inventory_balance` + 初始 `inventory_ledger` | 导入余额，同时写一条 `migration_init` 流水 | 各仓库总库存一致 |
| `sxo_plugins_erp_company` | 约 63 个客户/供应商 | `party` | `is_customer/is_supplier` 转 kind | 客户搜索结果一致 |
| `sxo_plugins_erp_sales` | 约 148 张销售单 | `sales_order` | 原 ID 可保留为旧映射，也可新 ID + external_ref | 订单数量、金额汇总一致 |
| `sxo_plugins_erp_sales_detail` | 约 294 条销售明细 | `sales_order_item` | 保存商品快照和旧 product_id 映射 | 客户历史成交价一致 |
| `sxo_workflow_order` | 约 105 条工作流订单 | `workflow_order` | 直接导入，商品能匹配则补 `sku_id` | 未完成订单数量一致 |
| `sxo_user`、`sxo_user_platform` | 小程序/商城用户 | `auth_user`、`auth_identity` | 可后迁移，先保留 ShopXO 登录桥 | 登录可用，权限一致 |

## 5. 服务层替换计划

| 现有类/函数 | 当前职责 | 新服务 | 第一阶段做法 | 最终状态 |
|---|---|---|---|---|
| `ERPSystemClient.product_list` | 调 ERP 查询商品 | `CatalogService.list_products` | 保留方法名，内部切到新库 | 删除 ERP HTTP 调用 |
| `ERPSystemClient.product_save` | 调 ERP 新增/编辑商品 | `CatalogService.save_product` | 新旧双写，生成对账报告 | 只写新库 |
| `DatabaseClient.search_products` | 查 ERP 商品表 | `CatalogRepository.search_skus` | SQL 改成新表 | 旧表只读归档 |
| `DatabaseClient.get_product_inventory` | 查库存余额 | `InventoryService.get_balance` | 读新 `inventory_balance` | 余额由流水维护 |
| `erp_tools.sales_add` | 开销售单 | `SalesService.create_order` | 新库试运行，不扣旧库 | 新库事务开单扣库存 |
| `erp_tools.sales_delete` | 删除销售单 | `SalesService.delete_order` | 新库软删除对账 | 反向流水回滚库存 |
| `order_tools.workflow_order_save` | 保存工作流订单 | `WorkflowService.save_order` | 切新库，保留字段兼容 | 完全自有 |
| `volc_realtime_asr._fetch_dynamic_hotwords` | 从自有库取热词 | 火山 ASR `corpus.context` 动态热词 | 改读新商品/客户/仓库 | 旧库无依赖 |
| `auth_login/auth_me` | ShopXO 登录和 token 校验 | `AuthService` | 先桥接旧 token | 自有用户体系 |

## 6. 分阶段迁移排期

| 阶段 | 目标 | 主要任务 | 是否影响业务 | 完成标准 |
|---|---|---|---|---|
| P0 盘点 | 只读摸清现状 | 导出旧表结构、统计脏数据、确认商品/分类/库存计数 | 不影响 | 生成迁移校验报告 |
| P1 建新库 | 建立北极星自有 schema | 新建 `sjagent_core`、建表、迁移脚本骨架、配置 `data_backend.mode` | 不影响 | 空库迁移测试通过 |
| P2 主数据导入 | 商品中心先独立 | 导入商品、分类、单位、件套换算、图片、仓库、客户 | 不影响 | 商品列表和库存查询可从新库返回 |
| P3 读链路切换 | React 后台和智能体读新库 | 商品搜索、库存查询、客户查询、热词生成切新库 | 低风险 | 查询结果和旧库抽样一致 |
| P4 工作流切换 | 设计稿订单独立 | 工作流订单新增、查询、状态更新写新库 | 中低风险 | 新订单不再写 `sxo_workflow_order` |
| P5 商品写切换 | 商品管理独立 | 商品新增/编辑/上传/上下架写新库，旧库只做可选同步 | 中风险 | 泡袋上传能新建/更新自有商品 |
| P6 库存流水切换 | 库存变动可审计 | 入库、盘点、调拨全部写自有流水和余额 | 高风险 | 所有库存变化都有 ledger |
| P7 销售开单切换 | 开单不依赖 ERP | 开销售单、扣库存、删除回滚、历史价都走新库 | 高风险 | 连续一周新旧对账无差异 |
| P8 登录/打印替换 | 去掉剩余 ShopXO 绑定 | 自有用户、权限、打印任务 | 中风险 | 小程序/React 后台不再需要 ShopXO token |
| P9 下线旧依赖 | ShopXO/ERP 只归档 | 禁止写旧库，保留 external_ref，清理旧 API 调用 | 需要冻结窗口 | `ERPSystemClient` 不再发外部请求 |

## 7. 商品中心字段建议

| 字段 | 放在哪张表 | 用途 | 说明 |
|---|---|---|---|
| 客户可见标题 | `product_spu.title` | 给客户看清楚款式 | 如 `【喜悦】半斤` |
| 口头商品名 | 自动生成 | 平时搜索和语音使用 | 由 `series + size_label + color` 生成，如 `喜悦半斤红色` |
| 标准颜色 | `product_sku.color` | SKU 区分和搜索 | 旧 `spec` 只用于迁移清洗，主表只保留标准颜色 |
| SJ 编号 | `product_sku.sku_no` | 内部唯一业务编号 | 建唯一索引；界面、开单、导入导出只认这个 |
| 系列 | `product_spu.series` | 起订规则、分类、搜索 | 见喜、岩味、星禾等 |
| 商品类型 | `product_spu.product_type` | 库存决策 | gift_box/bag/material/service |
| 每件数量 | `product_spu.case_pack_qty` | 件套换算 | 从 `simple_desc` 解析后按 SPU 汇总确认 |
| 默认销售单位 | `product_sku.unit_id` | 开单单位 | 套/捆/个/斤/张 |
| 是否查库存 | `product_sku.inventory_policy` | 库存决策 | strict/weak/none |
| 起订规则 | `product_sku.purchase_policy` | 进货数量计算 | one_piece/min_qty/free |
| 默认仓库 | `product_sku.default_warehouse_id` | 开单/入库建议 | 默认百鑫 |
| 默认供应商 | `product_sku.default_supplier_id` | 采购建议 | 后续可从 wiki/规则补齐 |
| 零售价 | `product_sku.price` | 无历史价时使用 | 替代旧 `price/min_price` |
| 成本价 | `product_sku.cost_price` | 利润统计 | 旧数据有则迁入 |
| 主图/详情图 | `product_media` + `product_sku.main_image_url/detail_image_urls` | 商品管理、小程序展示、图片上传插件 | 图片明细进 `product_media`；SKU 里同步快捷 URL，方便列表和商品页读取 |

## 8. 关键业务规则表

| 规则 | 当前实现 | 新实现 | 备注 |
|---|---|---|---|
| 礼盒查库存，泡袋/辅料可不查 | `inventory.py` 里用关键词判断 | `product_sku.inventory_policy` + 分类规则 | 不再只靠 OCR 或商品名关键词 |
| 1 件起订系列 | `config.yaml` 和 wiki 维护系列名单 | `purchase_policy` + `product_spu.case_pack_qty` | 规则可后台编辑 |
| 用户报 X 件要换算成套 | 正则解析 `simple_desc` | 查 `product_spu.case_pack_qty` | 旧 simple_desc 不进主表，只在迁移报告里留 |
| 历史成交价优先 | 查 `sxo_plugins_erp_sales_detail` | 查 `sales_order_item` | 明细必须保存 price_snapshot |
| 多商品统一开单 | `executor.py` 合并后调用 `SalesAdd` | `SalesService.create_order` 单事务创建 | 失败整体回滚 |
| 销售单删除自动回库存 | ERP API 副作用 | `delete_order` 反向 ledger | 软删除，不进普通列表/对账 |
| 调拨先确认 | 当前 pending confirmation | 业务流保留，执行落 `transfer_order` | 调拨明细可追踪 |
| 进货剩余留百鑫 | 当前默认 warehouse_id=2 | `stock_document(doc_type=purchase_in)` 入库到百鑫 | 规则不变 |

## 9. 验收和对账表

| 对账项 | 计算方式 | 允许误差 | 失败处理 |
|---|---|---|---|
| SKU 数量 | 旧 `sxo_plugins_erp_product` 数量 vs 新 `product_sku` | 0 | 停止切换，输出缺失列表 |
| 分类数量 | 旧分类 vs 新分类 | 0 | 检查分类 ID 和关联表 |
| 分类下 SKU 数 | 每个分类 `COUNT(DISTINCT product_id)` | 0 | 输出分类差异 |
| 仓库库存合计 | 旧库存余额 vs 新库存余额 | 0 | 检查初始库存流水 |
| 客户数量 | 旧 customer 数 vs 新 party customer 数 | 可有人工排除 | 输出无法识别客户 |
| 历史成交价 | 抽样客户+SKU 历史价 | 0 | 检查销售明细迁移 |
| 商品搜索 | 常用关键词前 20 结果 | 排序可不同，核心 SKU 要一致 | 调整搜索索引/别名 |
| 泡袋 SJ 编号 | 编号唯一性 | 0 重复 | 人工处理重复编号 |
| 件套换算 | simple_desc 解析结果 | 异常必须列出 | 人工补 `unit_conversion` |
| 开单扣库存 | 新建测试单前后库存变化 | 0 | 回滚并检查事务 |

## 10. 推荐先做的最小版本

| 优先级 | 任务 | 产出 | 原因 |
|---|---|---|---|
| 1 | 建 `sjagent_core` schema 和迁移脚本 | 空库 + 表结构 | 后续所有迁移的地基 |
| 2 | 导入商品、分类、单位、仓库 | 商品中心可查 | 先解决双商品库问题 |
| 3 | 导入库存余额并生成初始流水 | 库存可查、可对账 | 让库存脱离 ERP 查询 |
| 4 | 改商品列表/搜索/库存查询读新库 | React 后台查询切新源 | 风险低，收益明显 |
| 5 | 导入销售历史和客户 | 历史价可用 | 开单前必须有价格依据 |
| 6 | 新增库存流水服务 | 入库/调拨/盘点可试跑 | 为开单扣库存做准备 |
| 7 | 新销售单服务灰度 | 测试开单闭环 | 最后再替换高风险写链路 |

## 11. 数据整合建议

总体建议：核心交易数据要分开，辅助展示数据可以先合并。商品、库存、销售单是查账基础，不要为了少几张表把它们揉在一起；图片、商城展示、旧系统映射这类数据，可以先简化，等业务真的需要多渠道或复杂管理时再拆。

| 数据块 | 建议 | 理由 | 收敛后的做法 |
|---|---|---|---|
| ERP 商品表 + ERP 商品基础规格表 | 合并 | 当前 `sxo_plugins_erp_product` 和 `sxo_plugins_erp_product_base` 基本一对一，拆开会增加查询复杂度 | `product_sku` 直接放 `unit_id`、`price`、`cost_price`，业务编号用 `sku_no` |
| ShopXO 商品表 + ERP 商品表 | 不要直接合并为一张 | 商城商品是展示，ERP 商品是库存/开单 SKU，生命周期不同 | 用 `product_sku` 做主数据，商城展示字段先放 SKU，未来多渠道再拆 `product_channel_listing` |
| SPU + SKU | 不建议完全合并 | 当前有 551 个商品组、922 个 SKU，礼盒按颜色/规格多变体，SPU/SKU 分开更清楚 | 保留 `product_spu` + `product_sku`，但单变体商品可自动一组一 SKU |
| 件套换算表 | 可以先合并 | 当前业务主要是 `1件 = N套/捆/个`，而且同一款/系列通常统一 | 在 `product_spu` 增加 `case_pack_qty`、`case_unit_id`，后续复杂了再拆 `unit_conversion` |
| 客户表 + 供应商表 | 合并 | 旧 ERP 本来也是 company 表，客户/供应商只是角色不同 | 用 `party`，字段 `is_customer`、`is_supplier` 或 `kind` |
| 普通入库单 + 普通出库单 | 合并 | 采购入库、其他入库、报损出库结构接近，合并后页面和接口更简单 | 用 `stock_document` + `stock_document_item`，通过 `doc_type` 和 `direction` 区分 |
| 盘点单 + 调拨单 | 不要和普通出入库揉在一起 | 盘点是绝对库存修正，调拨是两仓同时变化，查账逻辑不同 | 保留 `stocktake_order/item` 和 `transfer_order/item`，最终都写 `inventory_ledger` |
| 销售单 + 库存单据 | 不要合并 | 销售单有客户、价格、打印、历史成交价，业务语义比普通库存单据复杂 | 保留 `sales_order` + `sales_order_item`，同时写 `inventory_ledger` |
| 库存余额 + 库存流水 | 必须分开 | 余额用于快速查询，流水用于查账和回滚，两者职责不同 | `inventory_balance` 存当前数，`inventory_ledger` 存每次变化 |
| 商品分类关系表 | 可以先合并 | 当前更关心“SKU 属于哪些分类”，没有必要一开始绕关系表 | 在 `product_sku` 放 `primary_category_id` 和 `category_ids`；未来分类排序/多端展示复杂时再拆 `product_category_map` |
| 商品图片表 + 图片资源表 | 保留 `product_media`，暂不另建通用 `media_asset` | 后续图片上传插件、图片管理页面、源图/缩略图/替换历史都会用到 | 商品图片统一进 `product_media`；`product_sku.main_image_url/detail_image_urls` 只做快捷缓存 |
| 商品上下架表 | 可以先合并 | 如果只有一个小程序/商城渠道，独立 listing 表会偏重 | `product_sku` 先放 `is_listed`、`display_title`、`display_images`；多渠道时拆表 |
| 打印任务 + 销售单 | 建议分开 | 打印有重试、队列、完成时间，和销售单状态不是一回事 | 保留 `print_task` |
| 旧系统映射表 | 单独放，不进业务主表 | 迁移初期主要是 ERP product id、ShopXO goods id 映射 | 建迁移对照表或迁移报告，商品/分类/单位主表不放 `legacy_*` |
| 用户账号 + 客户资料 | 不要合并 | 登录用户可能是员工、小程序用户、管理员；客户是业务对象，但手机号绑定后要能自动识别客户 | `auth_user` 单独放，用 `auth_identity(provider=phone)` + `party.phone_normalized` 匹配后写 `linked_party_id` |
| 工作流订单 + 销售单 | 不要合并 | 工作流订单是设计稿/生产/交付过程，很多时候还没开销售单 | 保留 `workflow_order`，开单后关联 `sales_order_id` |

## 12. 收敛后的推荐核心表

这个版本比完整蓝图更轻，适合第一轮真实落地。

| 序号 | 表名 | 是否第一轮必需 | 说明 |
|---:|---|---|---|
| 1 | `product_spu` | 是 | 商品组/款式 |
| 2 | `product_sku` | 是 | 可开单、可库存商品，合并旧 ERP product/base |
| 3 | `product_category` | 是 | 分类 |
| 4 | `product_unit` | 是 | 套、捆、个、斤、张 |
| 5 | `product_media` | 是 | 商品图片资产，给上传插件和图片管理页用 |
| 6 | `warehouse` | 是 | 自己店里、百鑫仓库 |
| 7 | `party` | 是 | 客户/供应商统一表 |
| 8 | `auth_user` | 是 | 自有登录用户 |
| 9 | `auth_identity` | 是 | 微信、ShopXO、飞书等外部身份绑定 |
| 10 | `auth_session` | 是 | token/session |
| 11 | `inventory_balance` | 是 | 当前库存 |
| 12 | `inventory_ledger` | 是 | 库存流水 |
| 13 | `stock_document` | 是 | 普通入库/出库单据头 |
| 14 | `stock_document_item` | 是 | 普通入库/出库明细 |
| 15 | `stocktake_order` | 是 | 盘点单据头 |
| 16 | `stocktake_item` | 是 | 盘点明细 |
| 17 | `transfer_order` | 是 | 调拨单据头 |
| 18 | `transfer_order_item` | 是 | 调拨明细 |
| 19 | `sales_order` | 是 | 销售单 |
| 20 | `sales_order_item` | 是 | 销售单明细和价格快照 |
| 21 | `workflow_order` | 是 | 设计稿/生产/交付订单 |
| 22 | `workflow_order_log` | 是 | 订单流状态日志 |
| 23 | `print_task` | 后置 | 打印队列 |

第一轮可以先不建 `product_category_map`、`product_channel_listing`、`external_ref` 这几类独立表；图片资产表 `product_media` 保留。分类先收在 `product_sku`，旧系统 ID 和乱编号只放迁移对照表或迁移报告，不进入商品、分类、单位这些业务主表。

## 13. 商品中心已执行导入

2026-05-20 已先落地商品中心，执行脚本：

```powershell
python scripts\migrate_product_catalog.py --target-db sjagent_core
```

当前正式商品中心表已导入新库 `sjagent_core`。新库账号只允许服务器本机访问；本地执行时通过临时 SSH 隧道连接目标库，源库仍使用旧 ShopXO/ERP 账号只读。旧 ShopXO/ERP 表未删除、未覆盖。

迁移脚本支持目标库独立账号，使用这些环境变量覆盖目标库连接：`SJAGENT_CORE_DB_HOST`、`SJAGENT_CORE_DB_PORT`、`SJAGENT_CORE_DB_NAME`、`SJAGENT_CORE_DB_USER`、`SJAGENT_CORE_DB_PASSWORD`。

| 表 | 导入数量 | 说明 |
|---|---:|---|
| `product_unit` | 6 | 套、捆、个、斤、张、件 |
| `product_category` | 22 | 原分类 ID 保留 |
| `product_spu` | 552 | 按旧 `group_key` 聚合 |
| `product_sku` | 927 | `sku_no` 唯一，无重复 |
| `product_alias` | 3590 | 搜索/OCR/口语别名 |
| `product_media` | 6403 | 主图、详情图图片资产 |
| `migration_product_ref` | 1479 | 旧系统映射，只用于迁移查账 |

导入报告：`data/migration/product_import_report.json`。

## 14. 业务核心已执行导入

2026-05-20 已建业务核心表并导入第一批旧 ERP/ShopXO 数据到 `sjagent_core`，执行脚本：

```powershell
python scripts\migrate_business_core.py --target-db sjagent_core
```

| 表 | 导入数量 | 说明 |
|---|---:|---|
| `warehouse` | 2 | 自己店里、百鑫仓库 |
| `party` | 63 | 客户/供应商统一表 |
| `auth_user` | 60 | Web 用户 2 + ShopXO 用户 58 |
| `auth_identity` | 104 | 手机号、Web、ShopXO、微信身份 |
| `inventory_balance` | 260 | 当前库存余额 |
| `inventory_ledger` | 260 | 初始库存流水 `migration_init` |
| `sales_order` | 149 | 销售历史主表 |
| `sales_order_item` | 214 | 可映射到新 SKU 的销售明细 |
| `workflow_order` | 108 | 设计稿/生产/交付订单 |
| `workflow_order_log` | 108 | 迁移导入日志 |
| `stock_document` | 266 | 普通入库/出库单据 |
| `stock_document_item` | 318 | 普通入库/出库明细 |
| `stocktake_order` | 145 | 盘点单 |
| `stocktake_item` | 258 | 盘点明细 |
| `transfer_order` | 19 | 调拨单 |
| `transfer_order_item` | 19 | 调拨明细 |

跳过项：旧 `product_id=877` 无商品映射，跳过 1 条库存余额、1 条销售明细、1 条普通入库明细；另有 80 条旧销售明细引用已不存在销售单，暂不迁入主业务表。

导入报告：`data/migration/business_core_import_report.json`。
