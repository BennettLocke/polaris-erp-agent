# React 后台库存页开发手册

版本：v0.4  
日期：2026-05-26  
适用入口：`/admin/inventory`  
关联入口：`/admin/products` 商品资料、`/admin/sales-new` 开单扣库存、`/admin/settings` 仓库和库存规则
当前状态：旧 `/web` 页面已下线，库存页只维护 `/admin/inventory` React 后台入口。

v0.4 修订重点：

- 第一屏改为“库存总览矩阵”：商品为卡片，颜色/SKU 为行，仓库为列，不放商品图，优先看数量。
- 库存余额查询必须从“扣库存 SKU × 启用仓库”出发左连接余额表，0 库存也返回，保证能直接进货、调拨、盘点。
- 总览卡片使用瀑布式列布局，短卡片自然往上补位，避免等高网格留下大块空白。
- 明细表保留为第二个 Tab，用于查账、分页和精确行操作；单据 Tab 先做只读追溯。
- 库存动作必须定位到 SKU/颜色/编号，不能只选 SPU 商品。
- `不扣库存` 商品不进入库存页余额列表和库存动作搜索；要看这类商品，回到商品页按库存规则筛选。
- 库存动作接口返回给 React 前必须归一，不能让前端处理双层 `code/data`。
- 顶部统计先允许按当前查询结果估算，正式版应由后端返回全量 summary。

## 1. 页面定位

库存页不是一个“库存数字列表”，也不应该做成旧 ERP 那种很长很散的明细页。它应该是库存工作台：先让人快速判断某个商品在哪个仓还有多少，再让常用动作可以就地完成。

库存页必须回答这些问题：

- 某个商品、颜色、编号当前在哪些仓有库存。
- 哪些商品已经没库存、负库存或库存异常。
- 这条库存数字是怎么来的，最近由哪张单据改变过。
- 进货、盘点、调拨后库存有没有即时刷新。
- 泡袋、标签、服务类等不扣库存商品为什么不显示为可调库存。
- 开单扣库存、删除销售单回滚库存、调拨、盘点和入库是不是都能追溯到流水。
- 操作人是谁，发生时间是什么，来源单据是什么。
- 进货、调拨、盘点操作的是哪一个 SKU、颜色和编号，而不是模糊的 SPU 商品。

库存页只负责展示、输入和触发动作。库存增减、负库存限制、是否扣库存、流水写入、仓库间调拨事务，都必须走 `InventoryService` 和后端统一 API，不能在 React 页面里自己拼库存规则。

库存页的所有写动作必须是 SKU 级。页面可以显示 SPU 商品名，但提交动作时必须能明确传入当前行对应的 `sku_id` 或服务层可解析的 SKU `product_id`，同时在 UI 上展示 `sku_no`、颜色、单位和仓库，避免多颜色商品调错库存。

## 2. 当前代码现状

当前 `/admin/inventory` 还是占位页：

- `admin/src/App.tsx` 已有 `inventory` 路由和侧边栏入口。
- `pageMap.inventory` 仍显示“后续迁移库存明细、日志、出入库、盘点、调拨”。
- `api.ts` 目前只接了 `api.warehouses()`，还没有库存余额、流水、出入库、盘点、调拨等前端方法。
- 后端 `InventoryService` 已经具备库存查询、库存明细、库存日志、进货、调拨、盘点、仓库列表能力。
- `/api/inventory/purchase`、`/api/inventory/transfer`、`/api/inventory/stocktaking` 当前是单商品动作接口；服务层内部支持 `products` 列表，后续可以扩展批量。
- 库存动作路由当前可能把服务层结果再次包进 `data`，React 接入前需要把返回格式归一，避免前端写双层 `data.code/data.data` 兼容逻辑。

当前可直接复用的后端入口：

| 动作 | 后端入口 | 服务层 |
| --- | --- | --- |
| 库存卡片/快速查询 | `GET /api/inventory/cards` | `InventoryService.search()` |
| 单品/仓库库存 | `GET /api/inventory/query` | `InventoryService.product_inventory()` / `warehouse_inventory()` |
| 库存余额明细 | `GET /api/inventory/balances` | `InventoryService.balances()` |
| 库存流水 | `GET /api/inventory/ledger` | `InventoryService.ledger()` |
| 出入库单列表 | `GET /api/stock-documents` | `InventoryService.stock_documents()` |
| 进货入库 | `POST /api/inventory/purchase` | `InventoryService.create_stock_in()` |
| 盘点单列表 | `GET /api/stocktakes` | `InventoryService.stocktakes()` |
| 盘点修正 | `POST /api/inventory/stocktaking` | `InventoryService.create_stocktake()` |
| 调拨单列表 | `GET /api/transfers` | `InventoryService.transfers()` |
| 仓库列表 | `GET /api/warehouses` | `InventoryService.warehouse_list()` |

本轮库存页先做 React 版第一阶段：当前库存表、单 SKU 流水抽屉、进货、盘点、调拨。出入库单、盘点单、调拨单先做只读列表，不在第一阶段承诺完整单据明细展开。普通出库、报损出库先只在出入库单列表里展示历史，等后端动作接口补齐后再加操作入口。

第一阶段明确不做：

- 批量进货、批量盘点、批量调拨。
- 普通出库、报损出库新增动作。
- 单据明细完整展开和编辑。
- 低库存预警配置。
- 不扣库存商品的全量清单管理。

## 3. 库存数据边界

库存页以自有数据库为准，不依赖 ShopXO 或旧 ERP 页面逻辑。

核心表：

| 表 | 用途 |
| --- | --- |
| `warehouse` | 仓库，包含自己店里、百鑫仓库等 |
| `inventory_balance` | 当前库存余额，给查询和开单校验使用 |
| `inventory_ledger` | 库存流水，只追加，不修改，不删除 |
| `stock_document` | 普通出入库单，当前 React 第一阶段只新增入库 |
| `stock_document_item` | 普通出入库明细 |
| `stocktake_order` | 盘点单 |
| `stocktake_item` | 盘点明细，记录账面数、实盘数、差异 |
| `transfer_order` | 调拨单 |
| `transfer_order_item` | 调拨明细 |
| `product_spu` / `product_sku` | 商品、颜色、编号、是否扣库存 |
| `product_unit` | 单位 |

关键业务约束：

- `inventory_balance` 只表示当前数，不是查账依据；查账必须看 `inventory_ledger`。
- 所有库存变化必须先写业务单据，再写 `inventory_ledger`，再更新 `inventory_balance`。
- 调拨必须同一事务完成，调出仓扣库存，调入仓加库存，不能只扣不加。
- 盘点是把系统库存修正为实盘库存，流水写差异数。
- 销售单创建和删除库存回滚归 `SalesService`，库存页只展示结果和流水。
- 泡袋、小程序、标签、服务类等不扣库存规则来自商品和设置服务层，不允许前端临时硬编码。
- 不扣库存商品不一定存在 `inventory_balance` 记录，不能把“不扣库存”当成库存余额筛选来做。
- 当前库存写动作必须定位到 SKU。接口还使用 `product_id` 字段时，前端也要保证传入的是服务层能解析到具体 SKU 的行 ID。
- 负库存、低库存、无库存必须清楚显示，不能因为数字不好看就隐藏。

## 4. shadcn/Radix 组件映射

库存页必须沿用当前 React 后台的 shadcn/Radix 风格，组件来源以 `admin/src/components/ui` 为准。

| 页面需求 | 组件 | 使用规则 |
| --- | --- | --- |
| 页面标题和主动作 | `PageHeader`, `Button` | 右侧放刷新、进货、调拨、盘点 |
| 顶部查询 | `Input`, `Button`, `Select`, `Tabs` | 搜索商品名、颜色、编号；仓库用 `Select` |
| 状态筛选 | `Tabs`, `Badge` | 全部、有库存、零库存、负库存；不扣库存作为规则提示或独立入口 |
| 总览数字 | `Card`, `Badge` | 只做一行紧凑统计，不做大卡片墙 |
| 库存主列表 | `Table`, `Badge`, `DropdownMenu` | 库存默认表格优先，数字右对齐 |
| 移动端/窄屏 | `Card` | 仅窄屏降级为紧凑卡片，不做桌面图片墙 |
| 单 SKU 流水 | `Sheet`, `Table` | 从库存行打开，默认显示该 SKU 最近流水 |
| 全部库存流水 | `Tabs`, `Table` | 作为独立 Tab 展示全量流水 |
| 进货/调拨/盘点 | `Dialog`, `Field`, `Input`, `Select`, `Combobox`, `Textarea` | 表单必须分组，不能一条长旧表单 |
| 风险确认 | `AlertDialog` | 盘点差异大、调拨导致负库存时必须二次确认 |
| 加载态 | `Skeleton` | 不用文字“加载中”占位 |
| 空状态 | `Empty` | 加载完成且无数据时展示 |
| 分页 | `Pagination` | 页码和每页数量变化都实时刷新 |
| 提示 | `sonner` 或当前项目通知方式 | 成功、失败、权限错误都用中文 |

禁止继续新增：

- 原生 `<button>` 做业务按钮。
- 原生 `<select>` 做仓库/状态选择。
- 页面内手写大块 `span` 状态标签。
- 复杂库存表单里复制旧版后台的长表格。
- 在前端直接计算库存余额并当成最终结果保存。

## 5. 库存页整体结构

推荐结构：

```text
PageHeader
  标题：库存
  右侧：刷新、进货、调拨、盘点

InventoryToolbar
  搜索商品、颜色、编号
  仓库筛选
  搜索按钮
  重置按钮

InventoryStatusFilter
  全部
  有库存
  零库存
  负库存

InventorySummaryStrip
  SKU 数
  有库存
  零库存
  负库存
  当前仓库

InventoryRuleNotice
  不扣库存规则提醒
  需要全量查看时跳转商品页规则筛选

InventoryTabs
  库存总览
  明细表
  库存流水
  出入库单
  盘点单
  调拨单

InventoryOverviewMatrix
  ProductCard
    商品名
    合计库存
    颜色/SKU 行
    仓库库存列

InventoryBalanceTable
InventoryLedgerTable
StockDocumentTable
StocktakeTable
TransferTable

Pagination

InventoryActionDialog
InventoryLedgerDrawer
InventoryRiskConfirmDialog
```

桌面端默认使用库存总览矩阵，因为日常查库存最常见的问题是“这款盒子某个颜色在百鑫多少、自己店多少”。商品缩略图不进入库存页第一屏，避免挤占库存数字。

第一屏优先级：

1. 当前库存表必须先可用。
2. 每一行必须能直接进货、调拨、盘点、看流水。
3. 流水抽屉必须先能查单 SKU 最近变化。
4. 单据 Tab 第一阶段只读，作为追溯入口。

## 6. 查询和筛选设计

### 6.1 搜索

搜索支持：

- 商品名，比如“喜悦”“颜序”“茶礼”。
- 颜色，比如“红色”“橙色”“默认颜色”。
- SKU 编号，比如 `SJ1570`。
- 仓库名，比如“自己店里”“百鑫仓库”。

规则：

- 按 Enter 或点击“搜索”请求列表。
- 搜索后页码重置为第 1 页。
- 点击“重置”清空关键词、仓库、状态和页码。
- 搜索结果只出现在当前 Tab 列表里，不在输入框下面额外弹一套结果。
- 关键词在库存余额、流水、出入库单、盘点单、调拨单里按各自接口能力过滤。

### 6.2 仓库筛选

仓库来自 `GET /api/warehouses`。

规则：

- 默认“全部仓库”。
- 选择仓库后，当前库存 Tab 调 `GET /api/inventory/balances?warehouse_id=...`。
- 进货默认入库仓可以取设置里的默认仓；第一阶段没有设置接口时，默认选择第一个仓库并允许用户改。
- 调拨必须选择调出仓和调入仓，两个仓库不能相同。
- 盘点必须选择被盘点仓库。

### 6.3 状态筛选

第一版建议支持：

| 筛选 | 含义 |
| --- | --- |
| 全部 | 当前接口返回的全部库存余额 |
| 有库存 | `quantity > 0` |
| 零库存 | `quantity = 0` |
| 负库存 | `quantity < 0` |

如果后端第一阶段只支持 `keyword` 和 `warehouse_id`，状态筛选可以先在前端展示计数和本页过滤，但保存、调拨、盘点仍必须走后端。后续补服务层参数时再改为后端筛选。

`不扣库存` 不属于库存余额状态，也不应该混进库存工作台。第一阶段接口层按 `is_stock_item=1` 过滤，前端再兜底过滤返回行；如果要看全部不扣库存商品，应跳转或复用 `/admin/products` 的库存规则筛选，因为这类商品可能没有库存余额行。

### 6.4 统计口径

顶部统计要避免“分页数字冒充全量数字”。

第一阶段允许两种口径：

- 当前页统计：基于当前返回列表计算，标题必须写清楚“本页”。
- 当前查询统计：后端在列表接口返回 `summary` 时使用，标题写“当前筛选”。

正式版建议由 `GET /api/inventory/balances` 返回 summary：

```json
{
  "total_sku": 260,
  "in_stock": 210,
  "zero_stock": 45,
  "negative_stock": 5,
  "warehouse_id": 2
}
```

没有后端 summary 前，不要在 UI 上写“全部库存 260”这种容易误导的全局数字。

## 7. 库存总览和明细表设计

默认第一屏是库存总览矩阵：

| 区域 | 显示 |
| --- | --- |
| 商品卡片 | 商品名、当前页合计库存、颜色/SKU 数量 |
| 颜色/SKU 行 | 颜色、SKU 编号 |
| 仓库列 | 百鑫、自己店、其他仓库等动态列 |
| 库存数字 | 每个颜色/SKU 在对应仓库的 `quantity` |
| 操作 | 流水、进货、调拨、盘点 |

总览显示规则：

- 不放图片，第一视觉只服务库存数字。
- 仓库列固定按仓库列表生成；选择单仓库时只看该仓库。
- 没有库存余额记录的 SKU/仓库组合也要显示为 0，不能因为没有 `inventory_balance` 行就隐藏。
- 商品卡片使用瀑布列布局，按自身高度排列，不做等高网格。
- 数字右对齐并使用等宽数字，0 用弱化样式，负库存用危险色。
- 点击某个仓库库存数字打开该 SKU 的流水；更多操作放在行末 `DropdownMenu`。
- 商品卡片只做数据容器，卡片高度由颜色/SKU 行决定，避免商品页那种大图卡片占空间。

明细表作为第二个 Tab，保留逐仓库逐 SKU 的精确行：

默认列：

| 列 | 显示 |
| --- | --- |
| 商品/SKU | 商品名、颜色、SKU 编号 |
| 仓库 | 仓库名称 |
| 当前库存 | `quantity`，右对齐 |
| 可用库存 | `available_qty`，没有占用时同当前库存 |
| 已占用 | `reserved_qty`，第一版多为 0 |
| 单位 | 套、个、张等 |
| 库存规则 | 仅展示扣库存 SKU；不扣库存商品不进入当前库存表 |
| 最近变动 | 最近流水时间或最近来源 |
| 操作 | 进货、调拨、盘点、流水 |

显示规则：

- 库存数字统一保留必要小数，整数不要显示成很长的小数。
- 负库存用危险色 `Badge`，零库存用次要色 `Badge`，有库存保持普通文本。
- 不扣库存商品不显示在当前库存表，也不出现在进货、调拨、盘点的 SKU 搜索结果中。
- 商品名过长时单行截断，悬停可用 `Tooltip` 显示完整名称。
- 表格行高控制在紧凑范围，避免一屏只看到几条。
- 数字列右对齐，文本列左对齐，操作列固定在右侧。
- 桌面表格行高建议控制在 44 到 52 px，顶部筛选和统计不要挤占过多首屏高度。
- 每页数量按可视高度实时换算，默认至少 20 条，宽高足够时增加到 40 或 60 条，避免右侧和下方出现大空白。
- 操作列优先显示“流水”和一个主要动作，进货、调拨、盘点可放入 `DropdownMenu`，避免表格过宽。

## 8. 库存流水设计

流水是库存页的查账核心。

入口：

- 顶部 Tab “库存流水”。
- 当前库存表每行的“流水”按钮。
- 进货、调拨、盘点成功后，可直接跳到对应流水或单据。

显示列：

| 列 | 显示 |
| --- | --- |
| 时间 | `occurred_at` |
| 商品 | 商品名、颜色、SKU 快照 |
| 仓库 | 仓库 |
| 变化 | `change_qty`，入库为正，出库为负 |
| 变化前 | `before_qty` |
| 变化后 | `after_qty` |
| 来源 | `biz_type` 中文化 |
| 单据 | `biz_id` 或单据号 |
| 操作人 | `operator_name` / `operator_username` |
| 备注 | `note` |

`biz_type` 中文映射建议：

| biz_type | 文案 |
| --- | --- |
| `sales_out` | 销售出库 |
| `sales_delete` | 删除销售单回滚 |
| `stock_in` | 入库 |
| `stock_out` | 出库 |
| `stocktake` / `stocktake_adjust` | 盘点修正 |
| `transfer_out` | 调拨出库 |
| `transfer_in` | 调拨入库 |
| `migration_init` | 迁移初始库存 |

未知类型不要显示英文原样，至少显示“其他变动”，详情里保留原字段。

## 9. 进货、调拨、盘点动作

三个动作都必须是 SKU 级动作。用户从库存行进入时，表单顶部显示只读的商品名、颜色、SKU 编号、单位和当前仓库；用户从页面右上角进入时，必须通过商品搜索选择到具体 SKU 后才能提交。

前端提交时可以继续使用当前接口字段 `product_id`，但语义上它必须指向可解析到具体 SKU 的 ID。后续如果接口增加 `sku_id`，前端应优先传 `sku_id`，保留 `product_id` 兼容旧入口。

### 9.1 进货入库

入口：

- 页面右上角“进货”。
- 库存表行内“进货”。

字段：

| 字段 | 组件 | 规则 |
| --- | --- | --- |
| 商品/SKU | `Combobox` 或从行带入只读 | 必填，必须选择到 SKU、颜色、编号 |
| 仓库 | `Select` | 必填 |
| 数量 | `Input` | 必须大于 0 |
| 备注 | `Textarea` | 可选，默认不要写“小程序进货” |

保存：

```json
POST /api/inventory/purchase
{
  "product_id": 123,
  "unit_id": 1,
  "warehouse_id": 2,
  "quantity": 10,
  "note": "补货"
}
```

成功后刷新当前库存和出入库单列表，保留当前搜索和仓库筛选。

### 9.2 调拨

入口：

- 页面右上角“调拨”。
- 库存表行内“调拨”。

字段：

| 字段 | 组件 | 规则 |
| --- | --- | --- |
| 商品/SKU | `Combobox` 或从行带入只读 | 必填，必须选择到 SKU、颜色、编号 |
| 调出仓 | `Select` | 必填 |
| 调入仓 | `Select` | 必填，不能和调出仓相同 |
| 数量 | `Input` | 必须大于 0 |
| 备注 | `Textarea` | 可选 |

保存：

```json
POST /api/inventory/transfer
{
  "product_id": 123,
  "unit_id": 1,
  "out_warehouse_id": 2,
  "enter_warehouse_id": 1,
  "quantity": 5,
  "note": "从百鑫调回店里"
}
```

交互规则：

- 调出仓和调入仓相同时立即阻止提交。
- 如果当前库存不足，先让后端决定是否允许；前端只做提示和二次确认。
- 成功后刷新当前库存、流水和调拨单列表。

### 9.3 盘点修正

入口：

- 页面右上角“盘点”。
- 库存表行内“盘点”。

字段：

| 字段 | 组件 | 规则 |
| --- | --- | --- |
| 商品/SKU | `Combobox` 或从行带入只读 | 必填，必须选择到 SKU、颜色、编号 |
| 仓库 | `Select` | 必填 |
| 账面库存 | 只读文本 | 从当前行带入 |
| 实盘库存 | `Input` | 必须大于等于 0 |
| 差异 | 只读文本 | 前端可显示预估差异，但保存结果以服务层为准 |
| 原因/备注 | `Textarea` | 建议必填，方便查账 |

保存：

```json
POST /api/inventory/stocktaking
{
  "product_id": 123,
  "unit_id": 1,
  "warehouse_id": 2,
  "quantity": 39,
  "note": "实盘修正"
}
```

交互规则：

- 差异为 0 也可以保存，但应提示“库存未发生变化”。
- 差异较大时用 `AlertDialog` 二次确认。
- 成功后刷新当前库存、流水和盘点单列表。

### 9.4 动作接口返回格式

React 接入前，库存动作路由要把服务层结果归一成稳定数据，不让页面处理双层 `code/data`。

建议返回：

```json
{
  "code": 0,
  "data": {
    "id": 1001,
    "doc_no": "IN202605260001"
  }
}
```

调拨返回：

```json
{
  "code": 0,
  "data": {
    "id": 2001,
    "transfer_no": "TR202605260001"
  }
}
```

盘点返回：

```json
{
  "code": 0,
  "data": {
    "id": 3001,
    "stocktake_no": "ST202605260001"
  }
}
```

如果服务层返回 `{ "code": 0, "data": {...} }`，路由应展开后再返回，不要包成 `{ "code": 0, "data": { "code": 0, "data": {...} } }`。

## 10. 出入库单、盘点单、调拨单

这三个 Tab 第一版以只读追溯为主。

### 10.1 出入库单

接口：`GET /api/stock-documents`

列：

- 单号
- 类型
- 方向
- 仓库
- 总数量
- 状态
- 创建人
- 创建时间
- 备注

### 10.2 盘点单

接口：`GET /api/stocktakes`

列：

- 盘点单号
- 仓库
- 差异数量
- 状态
- 创建人
- 创建时间
- 备注

### 10.3 调拨单

接口：`GET /api/transfers`

列：

- 调拨单号
- 调出仓
- 调入仓
- 总数量
- 状态
- 创建人
- 创建时间
- 备注

第一版不展开单据明细，因为当前列表接口只返回主单信息。后续如果补充单据详情接口，再用 `Sheet` 或行展开，不跳旧页面。

## 11. 前端 API 和类型计划

需要在 `admin/src/types.ts` 增加：

```ts
export type InventoryBalance = {
  id?: number;
  sku_id?: number;
  product_id?: number;
  sku_no?: string;
  title?: string;
  color?: string;
  warehouse_id?: number;
  warehouse_name?: string;
  unit_id?: number;
  unit_name?: string;
  quantity?: string | number;
  available_qty?: string | number;
  reserved_qty?: string | number;
  is_stock_item?: number;
  last_ledger_at?: string;
  last_biz_type?: string;
};

export type InventoryLedgerItem = {
  id: number;
  ledger_no?: string;
  title?: string;
  color?: string;
  sku_no_snapshot?: string;
  warehouse_name?: string;
  change_qty?: string | number;
  before_qty?: string | number;
  after_qty?: string | number;
  biz_type?: string;
  biz_id?: number;
  operator_name?: string;
  operator_username?: string;
  occurred_at?: string;
  note?: string;
};
```

还需要补：

- `StockDocumentItem`
- `StocktakeItem`
- `TransferItem`
- `InventoryActionPayload`
- `InventoryActionResult`
- `InventorySummary`

需要在 `admin/src/api.ts` 增加：

| 前端方法 | 后端入口 |
| --- | --- |
| `inventoryBalances(query)` | `GET /api/inventory/balances` |
| `inventoryLedger(query)` | `GET /api/inventory/ledger` |
| `stockDocuments(query)` | `GET /api/stock-documents` |
| `stocktakes(query)` | `GET /api/stocktakes` |
| `transfers(query)` | `GET /api/transfers` |
| `createInventoryPurchase(payload)` | `POST /api/inventory/purchase` |
| `createInventoryTransfer(payload)` | `POST /api/inventory/transfer` |
| `createInventoryStocktake(payload)` | `POST /api/inventory/stocktaking` |

`warehouses()` 已存在，继续复用。

动作 payload 必须包含 SKU 语义：

```ts
export type InventoryActionPayload = {
  product_id: number;
  sku_id?: number;
  unit_id?: number;
  warehouse_id?: number;
  out_warehouse_id?: number;
  enter_warehouse_id?: number;
  quantity: string | number;
  note?: string;
};
```

其中 `product_id` 兼容当前接口；有 `sku_id` 时以后端支持为准优先使用。

## 12. 文件拆分计划

建议新增目录：

```text
admin/src/components/business/inventory/
  index.ts
  inventory-page.tsx
  inventory-toolbar.tsx
  inventory-summary-strip.tsx
  inventory-tabs.tsx
  inventory-balance-table.tsx
  inventory-ledger-table.tsx
  inventory-document-tables.tsx
  inventory-action-dialog.tsx
  inventory-ledger-drawer.tsx
  inventory-utils.ts
```

职责：

| 文件 | 职责 |
| --- | --- |
| `inventory-page.tsx` | 状态、请求、分页、动作调度 |
| `inventory-toolbar.tsx` | 搜索、仓库、重置 |
| `inventory-summary-strip.tsx` | 总览数字 |
| `inventory-tabs.tsx` | 当前库存、流水、单据切换 |
| `inventory-balance-table.tsx` | 当前库存表格 |
| `inventory-ledger-table.tsx` | 流水表格 |
| `inventory-document-tables.tsx` | 出入库、盘点、调拨列表 |
| `inventory-action-dialog.tsx` | 进货、调拨、盘点共用动作弹窗 |
| `inventory-ledger-drawer.tsx` | 单 SKU 流水详情 |
| `inventory-utils.ts` | 数字格式、类型文案、状态判断 |

`App.tsx` 只保留路由导入，不继续堆库存业务组件。

## 13. 交互细节

- 页码、每页数量、仓库、状态改变后立即刷新。
- 每页数量要按窗口宽度做合理默认，避免右侧出现大空白。
- 刷新按钮只刷新当前 Tab，不重置用户筛选。
- 操作成功后保留筛选条件和当前 Tab。
- 表格没有数据时显示 `Empty`，不要显示空白大区域。
- 请求失败时显示中文错误，不把英文异常直接扔给用户。
- `401` 走全局登录处理，`403` 显示无权限。
- 数字输入禁止滚轮误改数量。
- 提交中按钮禁用，并用组件内 `Spinner` 或当前项目的加载反馈。
- 进货、调拨、盘点动作必须记录当前登录用户，后端已从 session 取 `operator_user_id`。
- 行内动作打开弹窗时必须锁定当前 SKU，不能让用户只看到商品名却看不到颜色和编号。
- 页面右上角动作打开弹窗时，商品搜索必须选中 SKU 后才能启用提交按钮。

## 14. 权限和风险动作

库存页涉及真实库存，权限要比普通查看更严格。

| 动作 | 权限 |
| --- | --- |
| 查看库存 | `查看库存` |
| 进货入库 | `调库存` |
| 调拨 | `调拨` |
| 盘点 | `盘点` |
| 查看流水 | `查看库存` |

前端可以按当前用户权限隐藏或禁用按钮，但最终必须以后端权限拦截为准。

当前 `AuthUser` 未必已经带精确权限明细。第一阶段前端可以按 `role` 做粗略禁用，真正是否允许执行以 API 返回 `403` 为准。后续 `/api/web-auth/me` 应补 `permissions` 字段，前端再按权限精确显示按钮。

风险动作：

- 盘点会直接修正库存，必须显示账面数、实盘数和差异。
- 调拨会同时影响两个仓库，必须清楚显示方向。
- 负库存相关提示不能只靠颜色，要有文字。
- 不扣库存商品不能进货、调拨、盘点，也不进入库存页操作入口；如果确实要改规则，回到商品页或设置页处理。

## 15. 验收清单

开发完成后至少验证：

- [ ] `/admin/inventory` 不再显示占位页。
- [ ] `/admin/inventory` 刷新后仍能打开。
- [ ] 库存总览默认打开，能按关键词和仓库筛选。
- [ ] 商品以数据卡片展示，颜色/SKU 为行，百鑫、自己店等仓库为列。
- [ ] 0 库存 SKU/仓库组合也显示出来，并能作为进货、调拨、盘点入口。
- [ ] 商品卡片按瀑布布局排列，短卡片下面不出现大块空白。
- [ ] 总览不放商品图，库存数字右对齐，商品文本左对齐，无明显大空白。
- [ ] 明细表 Tab 保留逐仓库逐 SKU 表格。
- [ ] 有库存、零库存、负库存状态显示清楚。
- [ ] 不扣库存商品不混入库存余额列表，也不出现在库存动作 SKU 搜索结果中。
- [ ] 行内进货、调拨、盘点都明确显示 SKU 编号、颜色和单位。
- [ ] 进货成功后库存增加，并出现库存流水和出入库单。
- [ ] 调拨成功后调出仓减少、调入仓增加，并出现两条流水。
- [ ] 盘点成功后库存变为实盘数，并出现盘点流水。
- [ ] 动作接口返回给前端的是归一后的 `{ id, doc_no/transfer_no/stocktake_no }`，没有双层 `code/data`。
- [ ] 调出仓和调入仓相同无法提交。
- [ ] 数量为空、0、负数时有中文错误提示。
- [ ] 没有权限时不能执行调库存、盘点、调拨动作。
- [ ] 加载态使用 `Skeleton`，空状态使用 `Empty`。
- [ ] 桌面和窄屏都没有文字挤压、重叠或横向乱滚动。
- [ ] `npm.cmd run build` 通过。

## 16. 建议测试

新增或补充：

| 测试 | 目的 |
| --- | --- |
| `tests/test_admin_inventory_page_contract.py` | 检查 `/admin/inventory` 已接入 React 库存组件、API 方法和 shadcn 组件 |
| `tests/test_inventory_service_contract.py` | 检查进货、调拨、盘点服务层写余额和流水 |
| 浏览器 smoke | 登录后打开 `/admin/inventory`，验证列表、筛选和三个动作弹窗 |

合同测试重点：

- `App.tsx` 导入 `InventoryPage`，不再走 `PlaceholderPage`。
- `api.ts` 有库存相关方法。
- 库存动作 payload 保留 SKU 语义，不允许只显示 SPU 商品名就提交。
- 库存页使用 `Table`、`Tabs`、`Dialog`、`Select`、`Badge`、`Pagination`、`Skeleton`、`Empty`。
- 不出现 `window.confirm` 处理盘点、调拨、进货风险确认。
- 不在前端直接写库存余额计算保存逻辑。

## 17. 第一阶段实施顺序

1. 增加库存相关 TypeScript 类型和 `api.ts` 方法。
2. 新建 `components/business/inventory` 目录和 `InventoryPage`。
3. 归一库存动作接口返回格式，避免前端兼容双层 `code/data`。
4. 接入仓库列表、库存余额列表、分页和搜索。
5. 做库存表格、状态徽章和总览条，统计口径先标清“本页”或“当前筛选”。
6. 做行内单 SKU 流水抽屉。
7. 做进货、调拨、盘点共用动作弹窗，确保提交前锁定 SKU。
8. 接入出入库单、盘点单、调拨单只读 Tab。
9. 加权限、错误提示、加载态、空状态。
10. 加合同测试和浏览器 smoke。

第一阶段完成后，库存页应该能覆盖日常最常用的四件事：查库存、看单 SKU 流水、进货、调拨和盘点。后续再补普通出库、报损、低库存预警、批量操作和完整单据明细。
