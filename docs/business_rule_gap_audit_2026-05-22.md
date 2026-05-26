# 业务规则差异检查

日期：2026-05-22  
范围：本地代码 `Z:\sjagent`、服务器 `/opt/sjagent`、服务器 `sjagent_core` 数据库。  
目的：对照《React + Radix 后台重构项目书》的业务规则冻结表，确认当前实现哪里已经符合，哪里还需要改。

## 1. 检查结论

当前系统已经不是主要依赖旧 ERP API 开单。销售单、客户、库存、工作流、图片、设置大部分已经走 `sjagent_core` 自有数据库。

但是还不能说已经完成新架构，因为核心业务仍集中在 `NativeDBClient` 和部分 WebUI/Agent 代码里，没有拆成明确服务层。下一步应该先补服务层和迁移脚本，而不是直接写 React 页面。

## 2. 已经符合的规则

| 规则 | 当前情况 | 证据 |
| --- | --- | --- |
| 自有数据库 | 已符合 | 服务器库为 `sjagent_core`，包含商品、客户、销售单、库存、余额、工作流、用户、设置等表。 |
| 客户月结字段 | 已符合 | 服务器 `party` 表已有 `is_monthly_customer`，齐唯茶业为 `1`。 |
| 普通客户默认已付 | 基本符合 | `NativeDBClient.create_sales_order()` 在客户非月结且未显式传付款状态时默认 `paid + wechat`。 |
| 月结客户默认月结 | 已符合 | `create_sales_order()` 读取 `party.is_monthly_customer`，月结客户默认 `monthly + monthly`。 |
| 销售单软删除 | 已符合 | `sales_order` 有 `deleted_at/deleted_by_user_id/delete_reason`，删除时 `status='deleted'`。 |
| 礼盒扣库存 | 已符合 | `create_sales_order()` 对 `is_stock_item=1` 商品写 `inventory_ledger.sales_out`。 |
| 删除礼盒单回滚库存 | 已符合 | `delete_sales_order()` 根据 `sales_out` 反写 `sales_delete`。 |
| 泡袋不扣库存 | 已符合 | `_sku_tracks_inventory()` 对 `product_type in {'bag','bubble_bag'}` 返回不扣库存；服务器设置里泡袋类也在不扣库存分类中。 |
| 标签/辅料不扣库存 | 基本符合 | `product_basic` 中辅料为不扣库存，`inventory_rules.non_stock_category_keywords` 包含标签、服务、设计、制版、辅料。 |
| 余额付款扣余额 | 已符合 | `paid + balance` 会写 `customer_balance_ledger.balance_pay`。 |
| 删除余额付款单退余额 | 已符合 | `delete_sales_order()` 对余额付款单写 `balance_refund`。 |
| 月结结款 | 已有实现 | `customer_month_settlement()` 会把月结/未付单改为已付，并写余额流水。 |
| 小程序工作流不扣库存 | 已符合 | `/api/mini/workflow-order/save` 只调用 `save_workflow_order()`，没有销售出库逻辑。 |
| 商品颜色汇总 | 已符合 | `product_spu.available_colors` 存颜色列表，商品列表会显示颜色数和颜色文本。 |
| 商品件规 | 已符合 | `product_spu.case_pack_qty` 已存在，前端显示 `件规：1件X套`。 |
| 1件起订 | 基本符合 | `purchase_policy='one_case'` 已存在，商品编辑页已有 `1件起订` 开关。 |
| 图片资产表 | 已符合 | `product_media` 已有 `spu_id/sku_id/media_type`，图片资产可按 SPU 聚合。 |
| 操作人字段 | 部分符合 | 销售单、库存流水、工作流、余额流水都有操作人字段。 |

## 3. 不符合或需要补强的地方

| 问题 | 当前情况 | 风险 | 建议 |
| --- | --- | --- | --- |
| 没有独立服务层 | 核心逻辑主要在 `src/engine/native_db.py`，API 和 Agent 直接调用它。 | 以后 React、WebUI、Agent、小程序容易各自加逻辑。 | 新建 `src/services/business/`，先拆 `SalesService`、`InventoryService`、`CustomerBalanceService`、`PaymentService`。 |
| schema 文件落后实际库 | 已补 `database/schema/002_business_core.sql`，新库建表会带 `party.is_monthly_customer`。旧库仍由 `_ensure_party_columns()` 兜底。 | 老环境重复部署需要兼容 MySQL 5.7，不能直接写 `ADD COLUMN IF NOT EXISTS`。 | 第一阶段保留运行时兜底，后续如做迁移版本表再收敛。 |
| 删除销售单仍叫 cancel 字段 | 删除时同时写 `canceled_at/canceled_by_user_id/cancel_reason`。 | 业务口径上用户已经决定“不要取消，只要删除”，字段会让对账理解变乱。 | 第一阶段可保留字段兼容，但 UI/API 文案统一为删除；后续服务层只暴露删除。 |
| 付款状态字段还叫 `pay_status/pay_type` | 与项目书里的 `payment_status/paid_method` 不一致。 | 名称不统一，React/API 合同容易混乱。 | 第一阶段先保留 DB 字段，服务层输出统一字段名。以后是否迁移字段再决定。 |
| 付款设置没有落库 | 已补 `database/schema/003_system_settings.sql` 默认 `payment_rules`，服务器 `sjagent_core.system_setting` 也已写入。 | 业务默认仍主要由后端开单逻辑兜底。 | 后续服务层统一读取设置或明确哪些规则固定不可改。 |
| 操作人不是所有入口都显式传 | HTTP 通过 request context 记录，Agent 通过上下文不一定明确。 | AI 对话开单可能出现开单人为空或来源不清楚。 | 服务层强制接收 `operator_user_id/operator_source`，没有就标记为 `agent_system` 或阻止写操作。 |
| 历史销售单开单人为空 | 服务器最近历史迁移单多数 `created_by_user_id` 为 `NULL`。 | 对历史单可接受，但新单不能再空。 | 历史保留“未记录”，新写入必须有操作人。 |
| Agent 文案和文件名仍有 ERP 遗留 | `erp_tools.py` 名称保留；若干注释仍写 ERP。 | 容易误解为还在调用旧 ERP。 | 先不急改工具名，先在项目书和代码注释标明“兼容旧工具名，实际走 native DB”。 |
| 旧 `api_client.py/db_client.py` 仍存在 | 仍有旧 ERP API/旧表查询类。 | 后续误调用风险。 | 标记为迁移只读/废弃；服务层禁止调用。 |
| 泡袋上传技能还有 ERP 文案 | `bag_upload` 文案仍写 ERP 自动编号、上传 ERP。 | 用户理解会混乱。 | 后续改成“写入 sjagent_core 商品库和图片资产”。 |
| 本地数据库未启动 | 本地 `127.0.0.1:3306` 拒绝连接。 | 本地无法做完整数据库测试。 | 本地测试前先启动 MySQL 或改 `.env` 指向可测试库。 |

## 4. 服务器实际数据库情况

| 表 | 数量 |
| --- | ---: |
| `party` | 65 |
| `auth_user` | 60 |
| `product_spu` | 558 |
| `product_sku` | 934 |
| `sales_order` | 160 |
| `sales_order_item` | 232 |
| `workflow_order` | 120 |
| `inventory_balance` | 262 |
| `inventory_ledger` | 268 |
| `customer_balance_ledger` | 17 |
| `system_setting` | 2 |
| `number_sequence_setting` | 1 |

## 5. 服务器销售单状态

| 状态 | 付款状态 | 付款方式 | 单数 | 金额 |
| --- | --- | --- | ---: | ---: |
| `completed` | `paid` | `cash` | 142 | 74188.50 |
| `completed` | `monthly` | `monthly` | 16 | 4836.50 |
| `confirmed` | `paid` | `wechat` | 1 | 1680.00 |
| `deleted` | `monthly` | `monthly` | 1 | 4.00 |

判断：线上不是“全部欠款”。当前只有齐唯茶业有月结欠款，普通客户债务金额为 0。

## 6. 最近销售单抽查

| ID | 客户 | 状态 | 付款 | 金额 | 开单人 |
| ---: | --- | --- | --- | ---: | --- |
| 309 | 源袍 | confirmed | 已付/微信 | 1680.00 | 叶 |
| 308 | 齐唯茶业 | deleted | 月结/月结 | 4.00 | 彬 |
| 283 | 九壶寨 | completed | 已付/现金 | 250.00 | 未记录 |
| 282 | 越客人家 | completed | 已付/现金 | 260.00 | 未记录 |
| 281 | 古越茗风 | completed | 已付/现金 | 138.00 | 未记录 |
| 277 | 藏茗聚仙 | completed | 已付/现金 | 144.00 | 未记录 |

判断：新开 native 单已经能记录开单人；历史迁移单多数没有开单人。

## 7. 设置审计

服务器已有：

- `inventory_rules`
- `product_basic`
- `payment_rules`

服务器暂未正式落库：

- `image_oss_rules`
- `permission_rules`
- `print_rules` 如果打印模板完全走 `print_template`，可以不用这个 key。

判断：付款默认设置已经补齐；图片、权限和打印可以等对应模块服务层化时再决定是否落成设置项。

## 8. 下一步执行顺序

### 第一步：补正式数据库迁移

- 已补：`party.is_monthly_customer` 写入正式 schema。
- 已补：初始化 `payment_rules`。
- 确认 `product_basic`、`inventory_rules` 默认值可重复部署。

### 第二步：建服务层骨架

- `SalesService.create_order()`
- `SalesService.delete_order()`
- `InventoryService.apply_sales_out()`
- `InventoryService.rollback_sales_out()`
- `CustomerBalanceService.apply_payment()`
- `CustomerBalanceService.rollback_payment()`
- `SettingsService.get/set()`

### 第三步：把 API 和 Agent 切到服务层

- `/api/sales/add`
- `/api/sales/<id>` DELETE
- `sales_add` Agent tool
- `sales_delete` Agent tool

### 第四步：补测试

- 普通客户默认已付微信。
- 月结客户默认月结。
- 泡袋不扣库存。
- 礼盒扣库存。
- 删除礼盒单回滚库存。
- 删除泡袋单不回滚库存。
- 余额付款扣余额，删除恢复余额。
- 月结单删除减少欠款。
- 小程序工作流不扣库存。
- 新单必须记录操作人。

## 9. 当前不建议马上做的事

- 不建议直接开始 React 页面。
- 不建议继续在 `webui_api.js` 里堆业务判断。
- 不建议先改历史字段名。
- 不建议删除旧 ERP 文件；先标记禁止运行时调用，等服务层稳定后再清理。
