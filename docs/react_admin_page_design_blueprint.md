# React 后台页面级设计蓝图

版本：v0.1  
日期：2026-05-24  
范围：`/admin` React 后台  
保护范围：旧后台 `/web` 不在本轮视觉重构中修改

## 1. 目的

这份文档解决的是“页面怎么设计”的问题，不是单纯列组件。

后续 `/admin` 不能再按“看到哪里丑就改哪里”的方式推进。每个页面都必须先明确：

- 主流程是什么。
- 列表、详情、编辑、确认、上传、删除分别放在哪里。
- 哪些信息在主页面显示，哪些信息进弹窗或侧边详情。
- 哪些动作是轻操作，哪些动作是风险操作。
- 哪些业务逻辑只展示结果，不能在前端重写。
- 空状态、加载态、错误态、成功反馈怎么处理。

执行顺序先从“开单”开始，然后依次补：销售单、客户、商品、图片资产、库存、工作流、设置。

## 2. 官方组件依据

本轮页面设计以 shadcn/Radix 官方组件结构和示例作为第一参考，再套入肆计包装自己的业务数据。

已对照的官方组件：

- Card: https://ui.shadcn.com/docs/components/radix/card
- Field: https://ui.shadcn.com/docs/components/radix/field
- Button: https://ui.shadcn.com/docs/components/radix/button
- Badge: https://ui.shadcn.com/docs/components/radix/badge
- Table: https://ui.shadcn.com/docs/components/radix/table
- Dialog: https://ui.shadcn.com/docs/components/radix/dialog
- Alert Dialog: https://ui.shadcn.com/docs/components/radix/alert-dialog
- Sheet: https://ui.shadcn.com/docs/components/radix/sheet
- Popover: https://ui.shadcn.com/docs/components/radix/popover
- Select: https://ui.shadcn.com/docs/components/radix/select
- Combobox: https://ui.shadcn.com/docs/components/radix/combobox
- Calendar: https://ui.shadcn.com/docs/components/radix/calendar
- Dropdown Menu: https://ui.shadcn.com/docs/components/radix/dropdown-menu
- Empty: https://ui.shadcn.com/docs/components/radix/empty
- Skeleton: https://ui.shadcn.com/docs/components/radix/skeleton
- Sonner: https://ui.shadcn.com/docs/components/radix/sonner

## 3. 全局页面结构

每个业务页面统一按下面结构设计：

```text
PageHeader
  标题
  简短说明
  主动作/次动作

PageToolbar
  搜索
  筛选
  日期/月筛选
  批量动作

PageContent
  Table / Card grid / Tabs
  Empty
  Skeleton

PageSide
  Dialog 详情
  Dialog 编辑
  AlertDialog 风险确认

PageFooter
  Pagination
  汇总
```

页面本身只承担“编排”，复杂业务 UI 必须逐步拆成业务组件：

- `SalesCreateForm`
- `SalesLineTable`
- `SalesSummaryCard`
- `SalesOrderCard`
- `CustomerCard`
- `ProductCard`
- `MediaAssetCard`
- `InventoryTable`
- `WorkflowOrderCard`

## 4. 弹层使用规则

### 4.1 Dialog

用于短流程、必须聚焦完成的操作。

适合：

- 创建客户。
- 编辑客户基础资料。
- 收款、充值、结款、调整余额。
- 上传图片。
- 选择图片资产。
- 新建/编辑商品的小表单版本。
- 打印设置预览。

不适合：

- 查看销售单完整明细。
- 查看客户所有销售单和余额流水。
- 商品复杂编辑。
- 库存日志长列表。

### 4.2 Sheet

用于“详情页”和“长内容编辑”，不打断主列表上下文。

适合：

- 销售单详情。
- 客户详情。
- 商品详情/复杂编辑。
- 库存单据详情。
- 工作流订单详情。

原则：

- Sheet 顶部显示对象名称、状态、关键金额或数量。
- Sheet 内部可以使用 `Tabs` 分为“明细 / 操作记录 / 关联数据”。
- 主页面不塞完整明细，主页面只给入口。

### 4.3 AlertDialog

只用于风险动作。

必须使用：

- 删除销售单。
- 删除商品。
- 删除图片资产。
- 清空开单草稿且已有明细。
- 回滚库存或余额相关动作。
- 覆盖会影响历史数据的设置。

文案必须明确动作后果，例如“销售单会软删除，库存和余额按服务层规则回滚”。

### 4.4 Popover

用于轻量、短暂、附着在某个字段上的选择。

适合：

- 日期时间选择。
- 快捷月份筛选。
- 小范围状态筛选。
- 小提示或小型二级选择。

不适合：

- 大量商品选择。
- 大量图片选择。
- 长表单编辑。

### 4.5 DropdownMenu

用于卡片或表格行上的“更多操作”。

适合：

- 销售单：复制单号、打印、查看详情、删除。
- 商品：编辑、复制编号、查看图片、下架/上架。
- 图片资产：绑定、设为主图、删除。

主动作不要藏进更多菜单，例如开单页的“提交开单”必须始终可见。

商品页更多菜单只放次要动作，例如复制编号、查看图片、上架/下架、删除。编辑商品是高频动作，应在卡片上直接可见。

### 4.6 Sonner / Toast

用于非阻断反馈。

适合：

- 开单成功。
- 已创建打印任务。
- 保存设置成功。
- 图片上传成功。

错误要优先在当前表单区域展示明确原因；Toast 只能补充提示，不替代表单错误。

## 5. 开单页完整设计

### 5.1 页面目标

开单页的目标是快速、稳定地创建销售单。

它不是商品展示页，也不是客户详情页。主页面只保留开单必须的信息：

- 客户是谁。
- 是否月结。
- 开单时间。
- 付款状态。
- 从哪个仓库出。
- 买了哪些商品、颜色、数量、价格。
- 合计金额。
- 提交后能打印、查看、继续开下一单。

库存扣减、余额扣减、月结欠款、取消/删除回滚，都由服务层负责。前端只调用统一 API，不在页面里复制库存和余额规则。

### 5.2 推荐布局

桌面端使用两栏：

```text
左侧 70%
  Card: 基础信息
  Card: 销售明细
  Card: 商品搜索结果

右侧 30%
  Sticky Card: 本单摘要
  Card: 最近开单结果
```

移动端使用单栏：

```text
基础信息
销售明细
商品搜索
本单摘要折叠区
提交按钮固定在底部或摘要区底部
```

视觉目标：

- 信息密度比现在更紧凑。
- 一张业务卡只做一件事。
- 不做大块绿色按钮。
- 表格优先，不用一堆大卡片堆明细。

### 5.3 Header

组件：

- `PageHeader`
- `Button`
- `Badge`

内容：

- 标题：`开单`
- 描述：`选择客户、商品和结款状态，提交后生成销售单。`
- 右侧动作：
  - `清空`
  - `最近一张销售单`，如果有上次结果就显示单号。

清空规则：

- 没有客户、没有商品明细：直接清空。
- 已有客户或商品明细：用 `AlertDialog` 确认。
- 确认文案：`会清空当前未提交的开单内容，不会影响已经创建的销售单。`

### 5.4 基础信息区

组件：

- `Card`
- `CardHeader`
- `CardContent`
- `FieldGroup`
- `Field`
- `Combobox`
- `Dialog`
- `DateTimePicker`
- `Select`
- `Badge`

字段设计：

| 字段 | 组件 | 显示规则 |
| --- | --- | --- |
| 客户 | `Combobox` | 搜索客户名、电话；选中后展示客户名、电话、普通/月结 `Badge` |
| 创建客户 | `Dialog` | 只录客户名、联系人、手机号；默认不是月结客户 |
| 开单时间 | `DateTimePicker` | 不允许使用原生 `datetime-local` |
| 结款状态 | `Select` | 已付、月结、未付 |
| 已付方式 | `Select` | 只在结款状态为已付时显示：微信、现金、余额、转账 |
| 默认仓库 | `Select` | 默认读取设置里的默认出库仓库 |

客户选择逻辑：

- 选中客户后，如果 `is_monthly_customer=1`，自动切到 `月结`。
- 选中客户后，如果 `is_monthly_customer=0`，自动切到 `已付 + 微信`。
- 用户手动改过结款状态后，再切换商品不影响结款状态。
- 用户重新换客户时，按新客户月结规则重新判断一次。
- 新创建客户默认 `is_monthly_customer=0`，所以默认 `已付 + 微信`。

创建客户 Dialog：

```text
DialogTitle: 创建客户
DialogDescription: 新客户默认不是月结客户，后续可在客户详情里设置。

Field: 客户名称 必填
Field: 联系人 可选
Field: 手机号 可选

Footer:
  取消
  创建并选中
```

校验：

- 客户名为空不能提交。
- 手机号如果填写，格式不强拦，但要保留给后续手机号绑定逻辑。
- 创建成功后 Dialog 关闭，客户自动选中。

### 5.5 商品搜索区

组件：

- `Combobox`
- `Popover` 或 `Command` 后续可升级
- `Badge`
- `Button`
- `Skeleton`
- `Empty`

主流程：

1. 输入商品名称、系列、颜色、编号。
2. 回车或点击搜索。
3. 结果按 SPU 聚合展示。
4. 每个 SPU 下展示可选颜色/规格。
5. 点颜色/规格加入销售明细。

显示规则：

- 主结果以商品名为主，例如 `【喜悦】半斤`。
- 标题下显示分类、件规、是否 1 件起。
- 颜色用小 `Badge` 或紧凑按钮，不使用大色块。
- 泡袋、标签这类不扣库存商品要显示 `不扣库存` Badge。
- 库存不足时显示提示，但能否开单由服务层规则决定。

加入明细规则：

- 默认数量取页面当前数量输入。
- 数量最小为 1。
- 如果商品设置为 `1件起`，数量输入仍是“套”，但可以提示“件规：1件 X 套”；是否拦截按服务层规则统一。
- 价格优先客户历史价，其次零售价，其次商品默认价。
- 相同商品、相同仓库再次加入时，合并数量。

### 5.6 销售明细区

组件：

- `Card`
- `Table`
- `Input`
- `Select`
- `Button`
- `Badge`
- `Empty`

表格列：

| 列 | 内容 |
| --- | --- |
| 商品 | 商品名 + 编号小字 |
| 颜色/规格 | 标准颜色；默认颜色也显示为 1 个颜色 |
| 数量 | `Input` 数字输入，禁用滚轮改变数值 |
| 仓库 | `Select` |
| 单价 | `Input` 数字输入，禁用滚轮 |
| 金额 | 自动计算 |
| 规则 | 1件起、不扣库存、库存不足等 `Badge` |
| 操作 | 删除行 |

交互规则：

- 数量和单价修改后立即更新合计。
- 数量不能小于 1。
- 单价不能小于 0。
- 数字输入必须 `onWheel` blur，防止滚轮误改。
- 删除单行不需要 AlertDialog，因为还没有提交，不影响库存和余额。
- 清空全部明细需要 AlertDialog。

空状态：

```text
EmptyTitle: 还没有销售明细
EmptyDescription: 先搜索商品并选择颜色。
```

### 5.7 本单摘要区

组件：

- `Card`
- `Badge`
- `Separator`
- `Button`

固定在右侧，显示：

| 信息 | 说明 |
| --- | --- |
| 客户 | 未选择/客户名 |
| 付款 | 已付方式 / 月结 / 未付 |
| 商品行 | 明细行数 |
| 总数量 | 合计套数 |
| 应收金额 | 合计金额 |
| 预计余额影响 | 只有付款方式为余额或月结时显示 |

按钮：

- 主按钮：`提交开单`
- 次按钮：`打印最近单`，只有开单成功后显示
- 次按钮：`查看最近单`，只有开单成功后显示

提交按钮状态：

- 未选客户：disabled，并提示“请选择客户”。
- 没有明细：disabled，并提示“请加入商品”。
- 正在提交：显示 loading 状态。
- 提交失败：按钮恢复可点，错误显示在摘要卡顶部或表单顶部。

### 5.8 提交成功后的反馈

组件：

- `Sonner` 或页面内 `Alert`
- `Card`
- `Button`
- `Dialog`

成功后不应该只出现一行文字。右侧摘要区替换为“最近开单结果”：

```text
开单成功
销售单号：S20260524174547319
客户：齐唯茶业
金额：¥455.00
付款：月结

按钮：
  打印
  查看详情
  继续开下一单
```

规则：

- 提交成功后清空商品明细。
- 保留客户与否建议：默认保留客户 3 秒内可继续给同客户开单；点“继续开下一单”时可以选择保留客户或清空全部。
- 打印只创建打印任务，不直接假设本机打印成功。
- 查看详情打开 `SalesOrderDetailDialog`。

### 5.9 销售单详情 Dialog

开单成功后点击“查看详情”，或者销售单列表点击详情，销售单列表页使用居中的 `SalesOrderDetailDialog`。

组件：

- `Dialog`
- `Badge`
- `Table`
- `Separator`
- `Button`

内容：

- 顶部：客户、单号、状态、付款状态、开单人、时间。
- 明细：商品、颜色、数量、单价、金额、仓库、是否扣库存。
- 汇总：总数量、应收、实收/欠款。
- 操作记录：创建、打印任务、删除/回滚记录。
- 操作：打印、删除。

删除从 Dialog 内触发时，仍然必须走 `AlertDialog`。

### 5.10 删除/取消/回滚的前端边界

前端不写库存回滚算法，只显示后端服务层返回的结果。

删除销售单时：

1. 弹出 `AlertDialog`。
2. 文案说明：`删除后销售单会从列表隐藏，库存和余额按服务层规则回滚。`
3. 点击确认后调用统一销售单删除 API。
4. 成功后 Toast：`销售单已删除，库存和余额已按规则处理。`
5. 失败时展示服务层错误，不自行猜测。

要在详情里展示删除结果：

- 哪些商品恢复库存。
- 哪些商品不扣库存所以没有恢复。
- 如果用余额付款，余额是否恢复。
- 如果月结，欠款是否取消。

### 5.11 错误、加载、空状态

加载：

- 客户搜索：输入框本身只负责输入；点“搜索”后才展示结果或空结果提示，不能在未搜索时弹“没有匹配”。
- 商品搜索：结果区使用 `Skeleton`。
- 提交开单：提交按钮进入 loading，整页不锁死。

错误：

- 客户创建失败：Dialog 内显示错误。
- 商品搜索失败：商品结果区显示错误。
- 提交失败：摘要卡和表单顶部同时显示短错误。
- 库存/余额服务层失败：显示后端原始中文业务错误。

空状态：

- 无客户结果：只在点“搜索”且 API 返回空列表后显示 `没有找到客户，可以点创建新客户。`，不使用 Combobox 空结果弹层。
- 无商品结果：`没有匹配商品，请换关键词或检查商品是否上架。`
- 无销售明细：`先搜索商品并选择颜色。`

### 5.12 需要的业务组件

第一阶段拆这些：

```text
admin/src/components/business/sales-create/
  sales-customer-field.tsx
  sales-payment-fields.tsx
  sales-product-search.tsx
  sales-line-table.tsx
  sales-summary-card.tsx
  create-customer-dialog.tsx
  sales-result-card.tsx
  sales-order-detail-dialog.tsx
```

页面 `sales-new.tsx` 只做状态编排和 API 调用，不直接堆复杂 JSX。

### 5.13 API 和服务层边界

开单页只允许调用服务层 API：

- 客户搜索。
- 创建客户。
- 商品搜索。
- 客户历史价/零售价。
- 仓库列表。
- 创建销售单。
- 创建打印任务。
- 查看销售单详情。

前端不允许直接：

- 操作库存表。
- 操作余额流水表。
- 判断泡袋是否扣库存。
- 判断标签是否恢复库存。
- 直接修改销售单状态。

这些都必须在服务层里统一。

### 5.14 验收标准

视觉验收：

- 和 shadcn Card / Field / Table / Dialog / Sheet 示例保持同一种干净、克制、紧凑的后台风格。
- 没有大块旧式绿色按钮。
- 没有卡片套卡片造成的视觉噪音。
- 开单表格行高紧凑，能快速扫商品、颜色、数量和金额。
- 日期使用 `DateTimePicker`，不是浏览器原生控件。

功能验收：

- 搜索客户可用。
- 创建客户后自动选中。
- 月结客户自动切到月结。
- 普通客户默认已付 + 微信。
- 搜索商品可用。
- 选择颜色加入明细。
- 数量和单价可改，滚轮不会误改数字。
- 提交开单成功后能打印、查看详情、继续开单。
- 提交失败有明确错误。
- 删除销售单走服务层，库存和余额回滚由服务层返回结果。

技术验收：

```powershell
python -m unittest tests.test_admin_sales_new_contract tests.test_admin_sales_actions_contract tests.test_admin_shadcn_foundation_contract -v
cd Z:\sjagent\admin
npm.cmd run build
```

浏览器验收：

- 打开 `http://127.0.0.1:8081/admin/sales-new`。
- 点击开单时间，确认出现自定义日期时间弹层。
- 搜索一个客户。
- 搜索一个商品。
- 加入明细。
- 不提交真实单时，至少验证表单状态和合计。
- 打开 `http://127.0.0.1:8081/web`，确认旧后台仍可用。

## 6. 后续页面设计顺序

后续逐个补全，每个页面都按本文件的深度写。

| 顺序 | 页面 | 重点 |
| --- | --- | --- |
| 1 | 开单 | 快速开单、客户选择、商品明细、提交结果、详情弹窗 |
| 2 | 销售单 | 紧凑列表、详情 Dialog、打印、删除回滚展示 |
| 3 | 客户 | 客户卡片、余额、月结、收款/充值/结款、客户详情 |
| 4 | 商品 | SPU 列表、颜色、件规、1 件起、中间编辑弹窗、图片选择 |
| 5 | 图片资产 | SPU 聚合、分类、绑定、上传、删除、分页和懒加载 |
| 6 | 库存 | 明细、日志、出入库、盘点、调拨、仓库设置 |
| 7 | 工作流 | 设计稿/制作/配送/丝印状态、操作人、订单关联 |
| 8 | 设置 | 编号、商品基础、库存规则、收款结款、图片/OSS、用户权限、打印 |

销售单页详细执行标准见：`docs/react_admin_sales_page_development_handbook.md`。  
客户页详细执行标准见：`docs/react_admin_customers_page_development_handbook.md`。  
商品页详细执行标准见：`docs/react_admin_products_page_development_handbook.md`。

商品页专项标准：

- 商品按 SPU 管理，SKU 只作为颜色、编号、价格和库存规则明细。
- 列表默认用紧凑商品卡片，因为商品需要看主图，但卡片不能做成图片墙。
- 分类必须做一级/二级，不允许再出现横向长滚动分类条。
- 编辑使用中间 `Dialog + Tabs`，不把基础信息、规格、图片、库存全部堆成一条长滚动。
- 规格/颜色用 `Table`，不是一个颜色一张大卡片。
- 主图、详情页、颜色图统一通过图片资产选择器处理。
- 上架、下架、删除、图片删除都必须走服务层和确认弹窗。
- 商品页要能筛出无主图、无详情图、缺件规、缺价格、编号异常这些资料问题。
- 资料状态、开单可用、小程序上架必须分开显示，不能都混成一个“状态”。
