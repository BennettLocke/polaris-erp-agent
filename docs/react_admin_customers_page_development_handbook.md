# React 后台客户页开发手册

版本：v0.1  
日期：2026-05-25  
适用入口：`/admin/customers`  
当前状态：旧 `/web` 页面已下线，客户页只维护 `/admin/customers` React 后台入口。

## 1. 页面定位

客户页不是单纯的客户名单，而是客户账务工作台。

它要在一个页面里回答这些问题：

- 这个客户是谁，电话是否绑定。
- 这个客户是不是月结客户。
- 最近一次下单是什么时候、多少钱。
- 近 1 年消费多少钱。
- 当前余额是多少，余额为负时代表还有欠款。
- 这个客户有哪些销售单，某个月合计多少。
- 收款、充值、结款、调余额这些钱账动作怎么走。
- 操作是谁做的，后续能不能从余额流水和销售单里查回来。

客户页只负责展示、输入和触发动作。余额、欠款、月结、销售单改状态、操作人写入，都必须走服务层，不能在 React 页面里自己重写规则。

## 2. 当前代码现状

当前客户页仍在 `admin/src/App.tsx` 内：

- `CustomersPage`
- `CustomerDetailDialog`
- `CustomerBalanceActionDialog`
- `balanceActionLabels`
- `payTypeOptions`
- `monthOptions`

当前已接入的前端 API 在 `admin/src/api.ts`：

| 动作 | 前端方法 | 后端入口 |
| --- | --- | --- |
| 客户列表 | `api.customers(keyword, limit)` | `GET /api/customers` |
| 快速客户搜索 | `api.quickCustomers(keyword)` | `GET /api/customer/list` |
| 创建客户 | `api.createCustomer(payload)` | `POST /api/customer/create` |
| 月结开关 | `api.updateCustomerMonthly(id, value)` | `PATCH /api/customers/<id>` |
| 客户销售单 | `api.customerSales(id, options)` | `GET /api/customers/<id>/sales` |
| 余额流水 | `api.customerBalanceLedger(id, page, pageSize)` | `GET /api/customers/<id>/balance-ledger` |
| 收款/充值/结款/调余额 | `api.applyCustomerBalance(id, payload)` | `POST /api/customers/<id>/balance` |

当前后端服务层：

| 服务 | 文件 | 职责 |
| --- | --- | --- |
| `CustomerService` | `src/services/business/customers.py` | 客户列表、创建客户、月结设置、手机号同步、客户销售单 |
| `CustomerBalanceService` | `src/services/business/customers.py` | 余额流水、收款、充值、结款、调余额 |
| `IdentityLinkService` | `src/services/business/identity.py` | 手机号、微信身份、后台账号和客户资料绑定 |

当前主要问题：

- 客户页仍混在 `App.tsx`，后续维护困难。
- 仍有旧 class：`panel`、`data-panel`、`ghost-action`、`primary-action`、`drawer-content`。
- 仍有原生 `input`、`select`、`textarea`、`button`。
- 客户详情当前像抽屉，但用户更倾向中间弹窗。
- 余额动作弹窗没有足够的业务预览，例如结款前没有显示本月未结金额和收款差额。
- 客户列表只用 `limit`，没有真正分页；现在客户少还能用，后续应该补分页。
- 客户详情的销售单和余额流水都是固定取前 20 条，缺少分页。
- 页面没有明确拆成业务组件，无法复用到后续 Agent 工作台或小程序管理页。

## 3. shadcn/Radix 对齐标准

本页必须使用当前已安装的 shadcn/Radix 组件，项目上下文如下：

- Framework：Vite + React + TypeScript
- shadcn style：`new-york`
- base：`radix`
- import alias：`@`
- UI 目录：`admin/src/components/ui`

本页参考组件：

| 页面需求 | 组件 |
| --- | --- |
| 页面标题 | `PageHeader` |
| 搜索和筛选 | `Toolbar`、`Input`、`Button`、`Tabs`、`Badge` |
| 客户卡片 | `Card`、`Badge`、`Button`、`DropdownMenu` |
| 客户详情 | `Dialog`、`Tabs`、`Table`、`Pagination` |
| 月份选择 | `Popover` + 12 个月按钮组，或封装 `MonthPicker` |
| 收款/充值/结款/调余额 | `Dialog`、`Field`、`Input`、`Select`、`Textarea` |
| 危险确认 | `AlertDialog` |
| 空状态 | `Empty` |
| 加载状态 | `Skeleton` |
| 分割线 | `Separator` |

官方组件参考：

- Card: https://ui.shadcn.com/docs/components/radix/card
- Dialog: https://ui.shadcn.com/docs/components/radix/dialog
- Tabs: https://ui.shadcn.com/docs/components/radix/tabs
- Table: https://ui.shadcn.com/docs/components/radix/table
- Badge: https://ui.shadcn.com/docs/components/radix/badge
- Button: https://ui.shadcn.com/docs/components/radix/button
- Input: https://ui.shadcn.com/docs/components/radix/input
- Select: https://ui.shadcn.com/docs/components/radix/select
- Field: https://ui.shadcn.com/docs/components/radix/field
- Pagination: https://ui.shadcn.com/docs/components/radix/pagination
- Empty: https://ui.shadcn.com/docs/components/radix/empty
- Skeleton: https://ui.shadcn.com/docs/components/radix/skeleton
- AlertDialog: https://ui.shadcn.com/docs/components/radix/alert-dialog

禁止继续新增：

- `primary-action`
- `ghost-action`
- `status-badge`
- `panel`
- 页面内手写大块按钮样式
- 页面内原生 `select` 表单
- 页面内直接拼钱账规则

## 4. 数据和业务逻辑

### 4.1 客户数据来源

客户基础资料来自 `party`：

- `party.kind='customer'`
- `party.name`：客户名称。
- `party.phone` / `party.phone_normalized`：客户电话和标准化手机号。
- `party.is_monthly_customer`：是否月结客户。
- `party.deleted_at`：软删除标记。

客户页展示的数据由 `CustomerService.list()` 返回，不能直接从前端拼 SQL。

### 4.2 手机号和用户同步

手机号是客户、后台用户、小程序用户之间的关键连接。

规则：

- 客户创建时填写手机号，后端走 `CustomerService.create()`，再走 `IdentityLinkService.sync_customer_phone()`。
- 客户详情里修改手机号，前端调用 `PATCH /api/customers/<id>`，后端走 `CustomerService.sync_phone()`。
- 如果小程序用户先用手机号登录，后面客户资料才补手机号，也应该通过 `IdentityLinkService` 自动建立绑定。
- 前端只显示绑定结果，不直接写 `auth_identity`。

客户详情后续需要加一个“资料/绑定”页签，用来展示：

- 客户手机号。
- 是否已绑定微信身份。
- 关联的后台账号或小程序账号。
- 最后同步时间和操作人。

第一版如果后端还没有完整返回绑定列表，页面先保留入口和手机号编辑，不展示假的绑定结果。

### 4.3 月结客户规则

规则：

- 新建客户默认不是月结客户。
- 客户详情可以切换“月结客户”。
- 开单页面和 Agent 开单都必须读取 `is_monthly_customer`。
- 如果客户是月结客户，开单默认结款状态为“月结”。
- 如果客户不是月结客户，开单默认“已付 + 微信”。
- 用户手动改开单结款状态后，只要不重新换客户，页面不再自动覆盖。

客户页只负责调用 `api.updateCustomerMonthly()`，不在前端保存其他副本。

### 4.4 余额定义

客户余额不是单独一个可以随便写的字段，而是由流水和未结销售单计算：

```text
余额 = 钱包余额 - 未结欠款

钱包余额 = customer_balance_ledger.balance_delta 汇总
未结欠款 = sales_order 中 pay_status 为 unpaid/monthly/partial 的 receivable_amount 汇总
```

展示含义：

- `余额 > 0`：客户有余额或预存款。
- `余额 = 0`：当前无余额、无欠款。
- `余额 < 0`：客户还有欠款。

前端不能用销售单列表自己算余额，必须展示 API 返回的 `balance_amount`。

### 4.5 收款、充值、结款、调余额

所有钱账动作统一调用：

```text
POST /api/customers/<id>/balance
```

请求字段：

| 字段 | 说明 |
| --- | --- |
| `action` | `receipt`、`recharge`、`settlement`、`adjust` |
| `amount` | 金额；调余额允许正负，其他动作必须大于 0 |
| `pay_type` | 微信、现金、余额、转账等 |
| `month` | 结款动作必填，格式 `YYYY-MM` |
| `note` | 备注；调余额必须填写原因 |

动作解释：

| 动作 | 业务含义 | 服务层行为 |
| --- | --- | --- |
| 收款 | 收到客户一笔钱，但不指定某个月全部结清 | 新增正向余额流水，余额上升 |
| 充值 | 客户预存或充值 | 新增正向余额流水，余额上升 |
| 结款 | 选择某个月，把这个月未结销售单结掉 | 查询该月未结销售单，更新为已付，写结款流水 |
| 调余额 | 人工修正余额 | 写一条正负调整流水，必须有原因 |

结款差额规则：

```text
结款差额 = 实收金额 - 本月未结销售单应收金额
```

- 差额为 0：本月刚好结清。
- 差额大于 0：多收部分进入客户余额。
- 差额小于 0：本月销售单仍会被置为已付，差额变成新的负余额。

因此结款弹窗必须在提交前显示：

- 选择月份。
- 本月未结销售单数量。
- 本月应结金额。
- 本次实收金额。
- 结款后余额影响。

如果实收金额和本月应结金额不一致，弹窗要显示明确提示，但是否允许提交由服务层规则决定。

### 4.6 操作人

后端当前会从登录态读取当前用户：

```text
_current_web_user()
operator_user_id = native_user_id or id
```

客户页要展示操作人：

- 销售单列表显示 `created_by_name`。
- 余额流水显示 `created_by_name`。
- 结款、收款、充值、调余额提交后，刷新余额流水。

前端不能让用户手填操作人。

## 5. 页面结构设计

### 5.1 总体布局

客户页使用紧凑工作台布局：

```text
PageHeader
  标题：客户
  说明：查看客户余额、销售记录和月结处理。
  右侧：刷新、创建客户

Toolbar
  搜索客户/电话
  筛选：全部、月结、普通、有欠款、有余额、未绑定电话

CustomerSummaryStrip
  客户数
  月结客户数
  欠款客户数
  余额合计

CustomerCardGrid
  客户卡片

Pagination

CustomerDetailDialog
CustomerBalanceActionDialog
CreateCustomerDialog
```

第一版可以只接现有接口的 `limit`，但页面结构必须为分页预留。第二版补 `page/page_size/filter` 后，不需要再改 UI。

### 5.2 客户卡片

客户卡片要小而密，不做现在那种大面积空白。

卡片内容：

| 区域 | 显示 |
| --- | --- |
| 头部 | 客户名、月结/普通 Badge |
| 副标题 | 电话；无电话显示“未绑定电话” |
| 指标 1 | 最近下单时间 |
| 指标 2 | 最近下单金额 |
| 指标 3 | 近 1 年消费 |
| 指标 4 | 余额 |
| 操作区 | 详情、收款、结款、更多 |

操作区规则：

- 桌面端一行展示：`详情`、`收款`、`结款`、`更多`。
- `更多` 里放：充值、调余额、余额明细、设为月结/取消月结、编辑资料。
- 小屏幕可以折叠为：`详情` + `更多`。
- 不再把按钮竖着堆在客户名下面。

余额颜色规则：

- 负数可以用 `destructive` 风格或语义色提示。
- 正数和 0 不用夸张绿色。
- 颜色只做提示，不能让卡片读起来像报警页面。

### 5.3 客户详情弹窗

用户更喜欢中间弹窗，所以客户详情第一版使用 `Dialog`，不使用 `Sheet`。

弹窗宽度：

- 桌面：最大 980px 到 1120px。
- 小屏：宽度接近全屏，但仍保持 Dialog 结构。

弹窗结构：

```text
DialogHeader
  客户名
  电话 + 月结状态 + 当前余额

Tabs
  概览
  销售单
  余额明细
  资料/绑定
```

#### 概览页签

显示：

- 最近下单时间。
- 最近下单金额。
- 近 1 年消费。
- 当前余额。
- 钱包余额。
- 未结欠款。

按钮：

- 收款。
- 充值。
- 结款。
- 调余额。
- 月结开关。

#### 销售单页签

筛选：

- 全部。
- 近 1 个月。
- 近 3 个月。
- 当前年份 1 月到 12 月按钮。
- 年份默认当前年，后续可加年份选择。

表格列：

| 列 | 内容 |
| --- | --- |
| 单号 | `sales_no` |
| 时间 | `sales_at` |
| 商品摘要 | `items_preview` |
| 数量 | `total_quantity` |
| 金额 | `receivable_amount` |
| 付款 | `pay_status_text` + `pay_type_text` |
| 开单人 | `created_by_name` |
| 操作 | 详情、打印 |

点击销售单详情：

- 使用中间 Dialog。
- 可以复用销售单列表页的 `SalesOrderDetailDialog`。
- 不在客户详情里把完整账单塞成一长串。

#### 余额明细页签

顶部显示：

- 钱包余额。
- 未结欠款。
- 当前余额。

表格列：

| 列 | 内容 |
| --- | --- |
| 时间 | `created_at` |
| 类型 | 收款、充值、结款、调余额 |
| 金额 | `amount` |
| 抵扣金额 | `applied_amount` |
| 余额影响 | `balance_delta` |
| 月份 | `related_month` |
| 方式 | `pay_type_text` |
| 操作人 | `created_by_name` |
| 备注 | `note` |

余额明细必须分页。不能只拿前 20 条然后让用户误以为没有更多。

#### 资料/绑定页签

第一版显示和维护：

- 客户名称。
- 联系人。
- 手机号。
- 月结客户开关。

手机号保存后：

- 调用 `PATCH /api/customers/<id>`。
- 后端写客户手机号并调用 `IdentityLinkService`。
- 页面刷新客户详情和客户列表。

后续扩展：

- 展示绑定的小程序用户。
- 展示绑定的后台用户。
- 解除错误绑定。

## 6. 收款动作弹窗设计

### 6.1 共用结构

所有钱账动作使用一个 `CustomerBalanceActionDialog`，但文案和字段根据动作变化。

通用字段：

- 客户名。
- 当前余额。
- 金额。
- 收款方式。
- 备注。
- 提交按钮。

组件：

- `Dialog`
- `Field`
- `Input`
- `Select`
- `Textarea`
- `Button`
- `Alert`

### 6.2 收款

文案：

```text
收到客户一笔款项。此动作会增加客户余额，但不会自动把某个月销售单改为已付。
如果要把某个月销售单全部结清，请使用“结款”。
```

字段：

- 金额，必须大于 0。
- 收款方式：微信、现金、转账、其他。
- 备注可选。

### 6.3 充值

文案：

```text
客户预存金额。充值后客户余额增加，后续开单选择余额付款时可抵扣。
```

字段同收款。

### 6.4 结款

结款是最重要的动作，不能只是一个金额输入框。

字段：

- 年份，默认当前年。
- 月份，12 个按钮选择，不允许手写。
- 本月未结销售单数量。
- 本月应结金额。
- 实收金额，默认填本月应结金额。
- 收款方式。
- 备注。

提交前展示：

```text
本月应结：¥X
本次实收：¥Y
余额影响：¥Y - ¥X
```

提交后：

- 服务层把该月未结销售单更新为已付。
- 服务层写一条结款流水。
- 页面刷新客户卡片、客户详情销售单、余额明细。

### 6.5 调余额

调余额是风险动作。

规则：

- 金额允许正负。
- 金额不能为 0。
- 必须填写原因。
- 提交前用 `AlertDialog` 或弹窗内醒目提示确认。
- 后端写 `customer_balance_ledger`，不能直接改客户表。

推荐原因：

- 手动调整。
- 对账修正。
- 售后退回。
- 历史余额修正。

## 7. 后端接口改进计划

### 7.1 客户列表分页

当前：

```text
GET /api/customers?keyword=&limit=80
```

建议兼容升级：

```text
GET /api/customers?keyword=&page=1&page_size=24&filter=debt
```

返回：

```json
{
  "list": [],
  "total": 58,
  "page": 1,
  "page_size": 24,
  "summary": {
    "customer_count": 58,
    "monthly_count": 4,
    "debt_count": 12,
    "credit_count": 3,
    "balance_amount": "-4195.00"
  },
  "source": "native"
}
```

筛选值：

| filter | 含义 |
| --- | --- |
| 空 | 全部 |
| `monthly` | 月结客户 |
| `normal` | 普通客户 |
| `debt` | 余额为负 |
| `credit` | 余额为正 |
| `unbound_phone` | 未绑定电话 |

### 7.2 结款预览

当前结款前需要页面自己调用 `customerSales(month)` 获得本月未结金额，但这个接口返回的是销售单合计，不够专门。

建议新增：

```text
GET /api/customers/<id>/settlement-preview?month=YYYY-MM
```

返回：

```json
{
  "month": "2026-05",
  "order_count": 3,
  "receivable_amount": "1580.00",
  "orders": []
}
```

第一版可以先复用 `customerSales(id, { month })`，但前端必须只把它当显示预览；真正结款仍以服务层 `customer_month_settlement()` 的结果为准。

### 7.3 客户资料更新

当前 `PATCH /api/customers/<id>` 支持：

- `is_monthly_customer`
- `phone` / `contacts_tel` / `mobile`

建议扩展：

- `name`
- `contacts_name`
- `address`
- `note`

扩展后仍走 `CustomerService`，不要在路由里直接写 SQL。

### 7.4 客户重复和手机号冲突检查

客户模块后续必须补“重复客户”和“手机号冲突”能力。

原因：

- 开单、Agent 对话、小程序手机号登录都可能创建或绑定客户。
- 如果同一个手机号对应多个客户，后续余额、月结和销售单归属会乱。
- 如果客户先用小程序手机号登录，后台后补手机号时也必须能发现并绑定。

建议新增：

```text
GET /api/customers/duplicates?keyword=&phone=
```

用途：

- 创建客户前检查同名、近似名、同手机号。
- 编辑手机号前检查该手机号是否已经绑定其他客户或用户。
- 页面只提示和引导，不自动合并客户。

第一版规则：

- 同手机号已有客户：弹窗提示“该手机号已绑定客户 X”，让用户选择打开已有客户或取消。
- 同名但不同手机号：仅提示“可能重复”，允许继续创建。
- 无手机号的新客户：允许创建，但卡片显示“未绑定电话”。

后续再做客户合并工具：

```text
POST /api/customers/<source_id>/merge
```

合并必须是高风险动作，要用 `AlertDialog`，并且服务层负责迁移销售单、余额流水、身份绑定和历史价格，不允许前端自己拼。

### 7.5 客户对账单

客户详情需要补一个“对账单”能力，尤其服务月结客户。

建议新增：

```text
GET /api/customers/<id>/statement?month=YYYY-MM
GET /api/customers/<id>/statement?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
```

用于页面预览。

返回内容：

```json
{
  "customer": {},
  "month": "2026-05",
  "date_from": "2026-05-01",
  "date_to": "2026-05-31",
  "opening_balance": "-120.00",
  "sales_amount": "1580.00",
  "receipt_amount": "1000.00",
  "settlement_amount": "1580.00",
  "adjust_amount": "0.00",
  "ending_balance": "0.00",
  "sales": [],
  "ledger": []
}
```

同时新增 PDF 下载：

```text
GET /api/customers/<id>/statement.pdf?month=YYYY-MM
GET /api/customers/<id>/statement.pdf?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
```

或如果需要传模板配置：

```text
POST /api/customers/<id>/statement/export
```

返回文件：

```text
Content-Type: application/pdf
Content-Disposition: attachment; filename="齐唯茶业-2026-04-对账单.pdf"
```

自选时间段文件名示例：

```text
Content-Disposition: attachment; filename="齐唯茶业-2026-04-10至2026-05-20-对账单.pdf"
```

页面用途：

- 客户详情里增加“对账”页签。
- 支持快捷月份：当前年份 1 月到 12 月。
- 支持自选时间段：开始日期、结束日期。
- 选择月份或时间段后显示：期初余额、本期销售、本期收款/充值/结款/调整、期末余额。
- 可以直接下载 PDF 对账单。

时间筛选规则：

- 快捷月份和自选时间段二选一。
- 如果传了 `month`，后端按该月自然月计算。
- 如果传了 `date_from/date_to`，后端按闭区间日期计算，页面文案显示“自选区间”。
- `date_from` 不能晚于 `date_to`。
- 自选时间段默认最多允许 366 天，避免一次导出过大。
- 期初余额按 `date_from` 之前的余额计算，期末余额按 `date_to` 结束后的余额计算。

PDF 内容必须包含：

| 区块 | 内容 |
| --- | --- |
| 抬头 | 肆计包装·设计对账单、客户名、月份或自选时间段、生成时间 |
| 汇总 | 期初余额、本期销售、本期收款、本期结款、本期调整、期末余额 |
| 销售明细 | 日期、销售单号、商品、颜色/规格、数量、单价、金额、付款状态 |
| 收款/余额流水 | 日期、类型、收款方式、金额、抵扣金额、余额影响、操作人、备注 |
| 合计 | 商品总数量、销售合计、实收合计、未结金额、最终余额 |
| 页脚 | 公司名称和联系方式，后续可从设置读取 |

商品明细要求：

- 不能只写销售单摘要。
- 每个销售单下要展开到 `sales_order_item`。
- 商品名、颜色、数量、单价、金额必须清楚。
- 泡袋、不扣库存商品也照常显示在账单里，因为账单是交易记录，不是库存单。

第一版实现顺序：

1. 先做页面对账预览。
2. 再做 PDF 下载。
3. PDF 先用固定模板，后续再接设置页的对账单模板。

### 7.6 应收账龄

仅显示一个余额还不够，月结客户需要知道欠款压了多久。

建议后端返回：

```json
{
  "receivable_aging": {
    "current_month": "455.00",
    "last_month": "0.00",
    "over_60_days": "0.00",
    "over_90_days": "0.00"
  }
}
```

客户页显示：

- 客户卡片只显示“余额”。
- 客户详情概览显示账龄分布。
- 筛选里增加“有逾期欠款”。

第一版不用做复杂催收，只做展示和筛选。

### 7.7 从客户直接开单

客户卡片和客户详情都应该有“开单”入口。

交互规则：

- 点击后进入 `/admin/sales-new?customer_id=<id>`。
- 开单页自动选中该客户。
- 如果该客户是月结客户，开单页自动切换为月结。
- 如果该客户不是月结客户，开单页默认已付 + 微信。

这能减少从客户列表跳回开单页再搜索客户的重复操作。

### 7.8 客户异常检查

客户页需要能发现数据异常，不然以后排查会很慢。

建议新增筛选：

| 筛选 | 说明 |
| --- | --- |
| 未绑定电话 | 没有手机号，无法和小程序用户自动同步 |
| 可能重复 | 同名或同手机号冲突 |
| 有欠款 | `balance_amount < 0` |
| 有余额 | `balance_amount > 0` |
| 月结客户 | `is_monthly_customer=1` |
| 普通客户异常欠款 | 非月结客户存在未付/月结销售单 |
| 名称异常 | 客户名像 `客户64`、`客户65` 这种占位名 |

“名称异常”是为了处理迁移或测试数据里出现的占位客户名，例如销售单能关联到客户 ID，但展示名不是真实客户名。

### 7.9 客户历史价格

客户详情后续可以补“历史价格”页签。

显示：

- 客户买过哪些商品。
- 最近一次成交价。
- 最低成交价。
- 最高成交价。
- 最近成交时间。

用途：

- 开单时更容易判断价格是否合理。
- Agent 对话开单时可以引用客户历史价。

第一版不阻塞客户页迁移；等开单、客户、销售单页面都稳定后再做。

## 8. 前端文件拆分计划

新增目录：

```text
admin/src/components/business/customers/
  index.ts
  types.ts
  utils.ts
  customer-page.tsx
  customer-toolbar.tsx
  customer-summary-strip.tsx
  customer-card-grid.tsx
  customer-card.tsx
  customer-detail-dialog.tsx
  customer-overview-tab.tsx
  customer-sales-tab.tsx
  customer-balance-ledger-tab.tsx
  customer-profile-tab.tsx
  customer-balance-action-dialog.tsx
  customer-month-picker.tsx
  create-customer-dialog.tsx
```

职责：

| 文件 | 职责 |
| --- | --- |
| `customer-page.tsx` | 页面状态编排，调用 API，打开弹窗 |
| `customer-toolbar.tsx` | 搜索、筛选、刷新、创建客户 |
| `customer-summary-strip.tsx` | 顶部客户汇总数字 |
| `customer-card-grid.tsx` | 卡片网格和空/加载状态 |
| `customer-card.tsx` | 单个客户卡片 |
| `customer-detail-dialog.tsx` | 中间详情弹窗和页签容器 |
| `customer-overview-tab.tsx` | 概览指标和快捷动作 |
| `customer-sales-tab.tsx` | 客户销售单筛选、表格、分页 |
| `customer-balance-ledger-tab.tsx` | 余额流水表格、分页 |
| `customer-profile-tab.tsx` | 客户资料、手机号、月结设置 |
| `customer-balance-action-dialog.tsx` | 收款、充值、结款、调余额 |
| `customer-month-picker.tsx` | 年份和月份选择 |
| `create-customer-dialog.tsx` | 新增客户 |

`App.tsx` 只保留路由和页面挂载：

```tsx
import { CustomersPage } from "@/components/business/customers";
```

## 9. 前端状态流

页面状态：

```text
keyword
filter
page
pageSize
customers
summary
selectedCustomer
detailTab
balanceAction
loading
error
```

加载流程：

```text
进入页面
  -> loadCustomers(page=1)
  -> 显示 Skeleton
  -> 成功后显示 CustomerCardGrid

搜索
  -> keyword 改变不立即请求
  -> 点击搜索或回车
  -> page 重置为 1
  -> loadCustomers()

筛选
  -> filter 改变
  -> page 重置为 1
  -> loadCustomers()

打开详情
  -> selectedCustomer = customer
  -> Dialog 打开
  -> 并行加载销售单第一页 + 余额流水第一页

余额动作保存成功
  -> 刷新客户详情
  -> 刷新客户列表当前页
  -> 关闭动作弹窗
```

错误处理：

- 列表加载失败：显示 `Alert` 或当前区域错误，不清空旧列表。
- 动作提交失败：显示在弹窗内，不只 toast。
- 401：统一走登录态处理。
- 403：显示权限提示。

## 10. 验收标准

### 10.1 视觉验收

- 客户页看起来和 shadcn 官方后台示例同一风格。
- 主色只使用黑、白、灰，状态色克制使用。
- 客户卡片不再是旧版后台的大按钮、大空白。
- 客户操作按钮在信息下面横向排列或进入更多菜单，不竖着堆。
- 详情使用中间 Dialog，不再使用旧抽屉样式。
- 表格使用 `Table`，分页使用 `Pagination`。
- 空状态使用 `Empty`，加载使用 `Skeleton`。
- 没有新增 `primary-action`、`ghost-action`、`status-badge`、`panel`。

### 10.2 功能验收

- 搜索客户名称和电话都能得到结果。
- 客户卡片显示最近下单时间、最近下单金额、近 1 年消费、余额。
- 月结客户显示月结 Badge。
- 点击详情能看到概览、销售单、余额明细、资料/绑定。
- 销售单页签可以筛全部、近 1 个月、近 3 个月、某一年某个月。
- 某个月筛选显示该月单数和合计金额，不会所有月份都显示同一个合计。
- 余额明细能分页。
- 收款成功后余额刷新，流水新增。
- 充值成功后余额刷新，流水新增。
- 结款选择月份后显示本月应结金额，提交后该月未结销售单变为已付，余额刷新。
- 调余额必须填写原因，提交后流水新增。
- 月结开关保存后，开单页面和 Agent 开单能按新规则识别。
- 修改客户手机号后，走 `IdentityLinkService` 同步绑定。
- 页面刷新后数据仍来自后端，不依赖前端缓存。

### 10.3 服务层验收

- React 页面不直接写余额、欠款、月结计算。
- React 页面不直接调用 `NativeDBClient`。
- 钱账动作只走 `CustomerBalanceService.apply_action()`。
- 月结开关只走 `CustomerService.update_monthly()`。
- 手机号绑定只走 `CustomerService.sync_phone()` -> `IdentityLinkService.sync_customer_phone()`。
- 余额流水必须写入操作人。

### 10.4 回归验收

必须执行：

```powershell
cd Z:\sjagent
python -m unittest tests.test_admin_customer_cards_contract -v
python -m unittest tests.test_admin_sales_new_contract tests.test_admin_sales_actions_contract tests.test_admin_shadcn_foundation_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract -v
cd Z:\sjagent\admin
npm.cmd run build
```

如果改到后端客户服务，还必须补充：

```powershell
cd Z:\sjagent
python -m unittest tests.test_business_services -v
```

浏览器验收：

- 打开 `/admin/customers`。
- 打开 `/admin/sales-new`，确认月结客户自动切换仍可用。
- 打开 `/admin/customers`，确认客户页刷新后仍可用。

## 11. 测试文件计划

新增：

```text
tests/test_admin_customers_page_redesign_contract.py
```

测试内容：

- `admin/src/components/business/customers/` 目录存在。
- `App.tsx` 从 `@/components/business/customers` 引入客户页。
- 客户业务组件使用 `Button`、`Badge`、`Card`、`Dialog`、`Tabs`、`Table`、`Pagination`、`Empty`、`Skeleton`。
- 客户业务组件不包含旧 class：`primary-action`、`ghost-action`、`status-badge`、`panel`。
- 客户业务组件不直接使用原生 `select`。
- `CustomerBalanceActionDialog` 包含 `settlement`、`receipt`、`recharge`、`adjust` 四种动作。
- `CustomerMonthPicker` 只允许选择月份，不允许手写月份。
- 客户详情使用中间 Dialog，不使用旧 `drawer-content`。

保留并升级：

```text
tests/test_admin_customer_cards_contract.py
```

升级方向：

- 从检查旧 CSS class 改为检查业务组件结构。
- 保留“客户卡片必须显示最近下单、最近金额、近 1 年消费、余额”的合同。

## 12. 开发阶段计划

### 阶段 1：写合同测试

- 新增 `tests/test_admin_customers_page_redesign_contract.py`。
- 先让测试失败，证明当前客户页还没迁移。
- 不修改业务逻辑。

### 阶段 2：拆客户业务组件

- 新建 `admin/src/components/business/customers/`。
- 从 `App.tsx` 移出客户页相关组件。
- 保持现有 API 调用不变。
- 页面功能先保持现状可用。

### 阶段 3：迁移客户列表视觉

- 用 `PageHeader`、`Toolbar`、`Card`、`Badge`、`Button` 重做客户列表。
- 卡片信息顺序按本手册固定。
- 操作区改为横向按钮 + 更多菜单。
- 加 `Empty` 和 `Skeleton`。

### 阶段 4：迁移客户详情弹窗

- 用 `Dialog + Tabs` 重做详情。
- 销售单和余额明细改 `Table`。
- 月份筛选封装为 `CustomerMonthPicker`。
- 保留现有 `api.customerSales()` 和 `api.customerBalanceLedger()`。

### 阶段 5：迁移钱账动作弹窗

- 用 `Dialog + Field + Input + Select + Textarea` 重做收款、充值、结款、调余额。
- 结款弹窗增加本月应结金额和差额预览。
- 调余额要求备注。
- 动作成功后刷新列表、详情、流水。

### 阶段 6：补分页和筛选接口

- 后端扩展 `/api/customers` 支持 `page`、`page_size`、`filter`。
- 前端客户列表改成真正分页。
- 详情销售单和余额流水启用分页。

### 阶段 6.5：补客户业务增强

- 增加客户重复和手机号冲突检查。
- 增加结款预览接口或复用销售单月筛选做结款预览。
- 客户卡片和详情增加“开单”入口，跳转时带 `customer_id`。
- 客户详情增加“对账”入口，第一版支持快捷月份和自选时间段预览，第二步支持 PDF 下载。
- 客户详情概览显示账龄分布。
- 增加“未绑定电话、可能重复、普通客户异常欠款、名称异常”等筛选。

### 阶段 7：浏览器验收和文档回填

- 浏览器打开 `/admin/customers` 检查真实数据。
- 搜索客户、打开详情、切换月份。
- 不直接在生产数据上乱点收款；钱账动作先用本地测试客户或测试库验证。
- 打开 `/admin/customers` 确认当前后台正常。
- 更新本项目书和 `docs/react_admin_api_contract.md` 的进度记录。

## 13. 功能优化优先级

### P0：本轮客户页迁移必须保证

- 客户卡片显示最近下单、最近金额、近 1 年消费、余额。
- 客户详情用中间弹窗。
- 销售单、余额明细、资料/绑定分页签展示。
- 收款、充值、结款、调余额入口清楚。
- 结款必须按月份，不能手写月份。
- 月结开关保存后，开单页和 Agent 开单都按新规则识别。
- 手机号保存必须走 `IdentityLinkService`。

### P1：客户页迁移后优先补

- 客户列表分页和筛选。
- 结款预览。
- 从客户直接开单。
- 余额流水分页。
- 客户重复和手机号冲突提示。
- 普通客户异常欠款、名称异常、未绑定电话筛选。

### P2：稳定后再扩展

- 客户合并工具。
- 客户历史价格页签。
- 应收账龄图表。
- 对账单打印和导出。
- 客户信用额度。
- 批量结款。

## 14. 后续拓展

客户页后续可以继续扩展：

- 客户标签：批发客户、月结客户、设计客户、黑名单等。
- 客户信用额度：月结客户可设置额度提醒。
- 客户价格档案：查看历史成交价和客户专属价。
- 客户销售趋势：近 12 个月消费图表。
- 客户绑定关系：小程序用户、后台用户、微信身份统一展示。
- 客户对账单导出：按月份生成对账单。
- 批量结款：多个客户同一月份快速结款，但必须走服务层。

这些拓展都不能绕过 `CustomerService`、`CustomerBalanceService` 和 `IdentityLinkService`。

## 15. 2026-05-25 实施记录

本轮已完成客户页第一版 React/shadcn 迁移：

- 新增 `admin/src/components/business/customers/`。
- `CustomersPage` 从 `App.tsx` 拆出，`App.tsx` 只保留路由入口。
- 客户列表改为 `Toolbar + Card + Badge + Button + DropdownMenu + Empty + Skeleton + Pagination`。
- 客户页头部计数对齐销售单页，计数放在右侧动作区，不再把“共 N 个客户”当成页面主标题徽章。
- 客户卡片已改为服务层分页，每页 12 个客户；搜索和筛选会回到第一页，避免一次性把客户全部铺满页面。
- 客户页已启用创建客户弹窗，不再借用开单页创建入口。
- 客户详情改为中间 `Dialog + Tabs`，包含概览、销售单、余额明细、资料。
- 客户详情资料页增加编辑入口，可改客户名、联系人、电话和地址；电话保存继续走 `IdentityLinkService`，避免前端直接写身份绑定。
- 销售单页签保留全部、近 1 个月、近 3 个月和当前年份 12 个月按钮筛选。
- 销售单行可点开销售单详情 Dialog，并可打印、预览和删除，删除仍走销售单服务层回滚库存和余额。
- 余额动作弹窗改为 `Dialog + Field + Input + Select + Textarea`，支持收款、充值、结款、调余额。
- 结款弹窗会按月份读取客户销售单汇总，展示本月单数、应结金额和实收差额。
- 余额和月结开关仍走现有服务层 API，不在前端重写业务规则。
- 客户详情新增“对账单”页签，第一版支持当前年份月份快捷选择、自选日期区间预览。
- 新增 `/api/customers/<id>/statement` 和 `/api/customers/<id>/statement.pdf`，对账单数据由 `CustomerService.statement()` 从自有数据库生成。
- PDF 对账单第一版使用固定模板，包含汇总、销售明细和收款/余额流水；后续再接设置页模板。
- `requirements.txt` 已加入 `reportlab`，本地也已安装用于 PDF 生成。
- 客户列表翻页改为真实重新请求服务层，不再只改本地页码。
- 客户顶部增加异常提醒：普通客户欠款、未绑定电话、月结未结；点击后进入对应筛选。
- 后端客户列表 summary 增加 `normal_debt`、`monthly_debt`、`no_phone`，异常提醒不再从当前页临时估算。
- 客户详情余额明细增加分页，每页 12 条，分页读取 `/api/customers/<id>/balance-ledger`。

本轮保留的后续项：

- 客户列表后端排序和统计口径继续校验，必要时增加更多筛选项。
- 手机号绑定冲突的前端提示还要继续细化，例如明确显示“多个账号同手机号，需要人工处理”。
- 客户重复和手机号冲突提醒。

验证：

```powershell
cd Z:\sjagent\admin
npm.cmd run build
```

构建已通过。浏览器验收后再补视觉细节和合同测试。
