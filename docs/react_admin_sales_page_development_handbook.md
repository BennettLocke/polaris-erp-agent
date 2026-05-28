# React 后台销售单页开发手册

版本：v0.1  
日期：2026-05-24  
范围：`/admin/sales` 销售单列表、销售单详情、打印、删除  
当前状态：旧 `/web` 页面已下线，销售单页只维护 `/admin/sales` React 后台入口。

## 1. 这张页要解决什么

销售单页不是展示卡片的页面，本质是对账、查单、补打、看明细、删除错误单子的工作台。

这张页必须让用户快速回答几个问题：

- 这张单是谁的。
- 单号是什么，什么时候开的。
- 付款状态是什么，是已付、月结还是未付。
- 总数量和总金额是多少。
- 谁开的单。
- 这张单里有哪些商品、颜色、数量、单价、金额。
- 是否已删除；如果删除，谁删的、什么时候删的、回滚了什么。
- 能不能打印、预览、查看详情、删除。

前端只展示和触发动作，不重写业务规则。销售单创建、删除回滚、库存影响、余额影响、打印任务都必须走服务层。

## 2. 当前页面问题

当前 `/admin/sales` 已经接入了基础组件和服务层，但还不是最终形态。

- `SalesPage`、销售单详情、删除确认不能继续全部写在 `App.tsx`，页面职责太重。
- 主列表使用大卡片网格，扫描效率低，商品多时卡片高度不齐，不适合对账。
- 详情使用旧式 `Dialog` 加 `drawer-content`，语义不对；销售单完整详情现在改为使用居中的 shadcn/Radix `Dialog`。
- 加载态用 `Empty`，不符合真实加载语义；应使用 `Skeleton`。
- 搜索只有关键词，没有清晰的当前筛选状态、重置入口和日期/付款筛选。
- 主要动作和危险动作都铺在卡片底部，页面会显得重；删除应进入明确的 `AlertDialog`。
- 打印、预览、详情、删除的视觉层级需要重新分配。
- 没有把“已删除单默认隐藏”写成前端和 API 的共同约束。

## 3. 推荐页面形态

### 3.1 桌面端

桌面端主形态使用 `Table + Dialog`，不是大卡片网格。

```text
PageHeader
  标题：销售单
  描述：查询销售单、查看账单明细、补打和删除错误单。
  主按钮：新建开单

Toolbar
  搜索框：客户 / 商品 / 单号
  状态筛选：全部、已完成、已删除
  付款筛选：全部、已付、月结、未付
  日期筛选：今天、本月、自定义日期
  重置按钮

Content
  Table
    客户
    单号
    商品摘要
    数量
    金额
    付款
    开单人
    时间
    操作

Footer
  Pagination

Dialog
  销售单完整详情

AlertDialog
  删除销售单确认
```

选择表格的原因：

- 销售单是高频查询和对账数据，表格比卡片更容易扫。
- 卡片适合移动端，不适合桌面端一次看几十张单。
- 表格可以把金额、付款状态、时间、开单人对齐，减少误读。
- 详情不塞在主列表里，点击行或“详情”进入居中的 `Dialog`。

### 3.2 移动端

移动端使用紧凑卡片，不照搬桌面表格。

每张卡片只显示：

- 客户名 + 状态徽章。
- 单号。
- 最多 2 行商品摘要。
- 总数量、金额、付款状态。
- 时间。
- 一个“详情”按钮和一个“更多”菜单。

移动端删除仍然必须进入 `AlertDialog`。

## 4. shadcn/Radix 组件映射

| 页面需求 | 组件 | 使用规则 |
| --- | --- | --- |
| 页面标题和主按钮 | `PageHeader`, `Button` | 主按钮为“新建开单”，跳转 `/admin/sales-new` |
| 搜索与筛选 | `Toolbar`, `Input`, `Select`, `Popover`, `Tabs` | 搜索必须显式触发，不做假的自动空结果 |
| 日期筛选 | `Popover + Calendar + Button` | 不使用原生 `input[type=date]` |
| 付款状态筛选 | `Select` 或紧凑 `Tabs` | 文案必须是中文 |
| 销售单列表 | `Table`, `Badge`, `DropdownMenu`, `Pagination` | 桌面端默认表格 |
| 移动端列表 | `Card`, `Badge`, `DropdownMenu` | 只在窄屏显示 |
| 详情 | `Dialog`, `Tabs`, `Table`, `Badge` | 完整账单明细进入居中弹窗 |
| 删除确认 | `AlertDialog` | 必须说明软删除和回滚后果 |
| 加载态 | `Skeleton` | 列表加载不使用 Empty |
| 空状态 | `Empty` | 只在加载结束且没有数据时显示 |
| 成功反馈 | 当前页提示或后续 `Toast` | 打印任务、删除成功给明确反馈 |

## 5. 销售单列表设计

### 5.1 表格列

桌面端表格建议列：

| 列 | 显示内容 | 说明 |
| --- | --- | --- |
| 客户 | 客户名称 | 没有客户名时显示“未记录客户”，不显示英文或空白 |
| 单号 | `sales_no` | 可复制，点击行打开详情 |
| 商品 | 商品摘要 | 最多 2 行：商品名、颜色、数量；更多显示 `+N` |
| 数量 | 总数量 | 使用 `total_quantity` 或 `buy_number_count` |
| 金额 | 应收金额 | 使用 `receivable_amount` 优先，其次 `total_price` |
| 付款 | 付款状态 + 付款方式 | 例如 `已付款 / 微信`、`月结`、`未付款` |
| 开单人 | `created_by_name` | 没有时显示“未记录” |
| 时间 | `sales_at` | 显示到分钟，宽度固定 |
| 操作 | 详情、打印、更多 | 删除放在更多菜单或危险区 |

状态徽章：

- 已完成：普通 outline 徽章。
- 已删除：灰色/次级徽章，默认不出现在主列表，只有筛选“已删除”才出现。
- 打印中：按钮 disabled，显示“提交中”。

### 5.2 商品摘要

商品摘要不能把整单明细都塞进列表。

规则：

- 一行格式：`【系列】规格 颜色 x数量`。
- 桌面端最多显示 2 行，多余显示 `+N 个商品`。
- 金额不在商品摘要里重复显示，金额列统一显示整单金额。
- 点击行进入详情 Dialog 看完整商品明细。

### 5.3 操作区

每行操作分三层：

- 直接可见：详情、打印。
- 更多菜单：打印预览、复制单号。
- 危险动作：删除，放在菜单末尾或单独危险按钮，必须二次确认。

删除文案：

```text
确认删除这张销售单？
系统会软删除销售单，并按服务层规则回滚这单扣过的库存和余额。
不扣库存的商品不会恢复库存。
```

前端不能自行判断哪些商品回滚库存，只能展示服务层结果。

## 6. 筛选与搜索规则

### 6.1 搜索

搜索框支持：

- 客户名。
- 商品名。
- 颜色/规格。
- 销售单号。

规则：

- 输入时不弹假结果。
- 按 Enter 或点“搜索”才请求接口。
- 搜索后显示当前筛选摘要，例如：`关键词：齐唯茶业`。
- 点击清除后恢复第一页和默认筛选。
- 搜索请求必须重置到第 1 页。

### 6.2 付款筛选

付款筛选建议值：

- 全部。
- 已付。
- 月结。
- 未付。

接口字段建议为 `pay_status`：

- `paid`
- `monthly`
- `unpaid`

页面展示必须用中文，不显示 `paid`、`monthly`、`unpaid`。

### 6.3 日期筛选

第一版只做三个入口：

- 今天。
- 本月。
- 自定义日期范围。

后续再补快捷月份，比如选择 2026 年 5 月。

日期筛选必须使用 `Popover + Calendar` 或已有日期组件，不使用浏览器原生日期输入。

### 6.4 删除单筛选

默认列表不显示已删除销售单。

可选筛选：

- 正常销售单。
- 已删除销售单。

已删除单只用于追溯，不参与默认对账列表。

## 7. 详情 Dialog 设计

销售单详情使用居中的 shadcn/Radix `Dialog`。这次用户明确更喜欢中间弹窗，因此销售单详情不再使用右侧 `Sheet`。

Dialog 顶部：

- 客户名。
- 单号。
- 状态徽章。
- 付款状态。
- 总金额。
- 开单时间。
- 开单人。

Dialog 主体使用 `Tabs`：

| Tab | 内容 |
| --- | --- |
| 明细 | 商品、颜色、数量、单价、金额、仓库、是否扣库存 |
| 付款 | 付款状态、付款方式、余额影响、月结说明 |
| 操作记录 | 创建人、删除人、删除时间、打印任务、回滚说明 |

明细表格字段：

- 商品。
- 颜色/规格。
- 数量。
- 单位。
- 仓库。
- 单价。
- 金额。
- 库存规则：扣库存 / 不扣库存。

如果服务层暂时没有库存影响明细，前端第一版可显示“由服务层处理”，但不能假造回滚结果。

## 8. API 和服务层边界

### 8.1 当前可用接口

| 动作 | 接口 | 用途 |
| --- | --- | --- |
| 销售单列表 | `GET /api/sales/cards` | 列表、搜索、分页 |
| 销售单详情 | `GET /api/sales/<id>/detail` | Dialog 详情 |
| 创建打印任务 | `POST /api/sales/<id>/print-task` | 本地打印程序队列 |
| 打印预览 | `GET /api/sales/<id>/print-html?auto=0` | 打开预览页 |
| 删除销售单 | `DELETE /api/sales/<id>` | 软删除并回滚 |

### 8.2 列表接口下一步建议

`api.salesCards` 应改成 options 参数：

```ts
type SalesListQuery = {
  keyword?: string;
  page?: number;
  pageSize?: number;
  payStatus?: "paid" | "monthly" | "unpaid" | "";
  status?: "active" | "deleted" | "";
  dateFrom?: string;
  dateTo?: string;
};
```

前端调用：

```ts
api.salesCards({
  keyword,
  page,
  pageSize: 20,
  payStatus,
  status,
  dateFrom,
  dateTo
});
```

后端 `/api/sales/cards` 可以逐步支持这些参数。前端第一阶段可先只接 `keyword/page/page_size`，但类型要按未来筛选预留。

### 8.3 删除逻辑边界

销售单删除按钮只调用：

```http
DELETE /api/sales/<id>
```

服务层负责：

- 软删除销售单。
- 记录删除人。
- 回滚扣库存商品。
- 不回滚不扣库存商品。
- 回滚已付余额扣减。
- 月结单删除后取消对应欠款影响。

前端负责：

- 二次确认。
- 显示服务层返回结果。
- 删除成功后刷新当前页。
- 如果详情 Dialog 打开的是被删除单，则关闭或刷新为已删除状态。

## 9. 文件拆分方案

下一步实现时不继续扩大 `App.tsx`。

建议新增目录：

```text
admin/src/components/business/sales-list/
  index.ts
  types.ts
  sales-list-toolbar.tsx
  sales-list-table.tsx
  sales-mobile-card-list.tsx
  sales-order-detail-dialog.tsx
  sales-delete-dialog.tsx
  sales-list-empty.tsx
  utils.ts
```

职责：

| 文件 | 职责 |
| --- | --- |
| `types.ts` | 销售单页查询条件、加载状态、组件 props |
| `utils.ts` | 金额、日期、状态文案、商品摘要格式化 |
| `sales-list-toolbar.tsx` | 搜索、付款筛选、日期筛选、重置 |
| `sales-list-table.tsx` | 桌面端表格 |
| `sales-mobile-card-list.tsx` | 移动端卡片 |
| `sales-order-detail-dialog.tsx` | 销售单详情 |
| `sales-delete-dialog.tsx` | 删除确认 |
| `sales-list-empty.tsx` | 空状态 |
| `index.ts` | 统一导出 |

`App.tsx` 只保留：

- 路由选择。
- 页面状态编排。
- API 调用。
- 把数据传给业务组件。

后续如果页面继续变复杂，再拆 `admin/src/pages/sales-page.tsx`。

## 10. 视觉标准

销售单页必须延续 shadcn/Radix 风格：

- 主色仍以黑、白、灰为主，不用大面积绿色。
- 按钮不做大块厚重样式。
- 表格行高紧凑，适合扫单。
- 卡片只给移动端或摘要区使用。
- 徽章使用 `Badge`，不手写状态块。
- 图标使用 `lucide-react`，按钮内图标加 `data-icon`。
- 详情 Dialog 的内容分区清楚，但不要用卡片套卡片。
- 加载时使用 `Skeleton` 行，不显示“加载中”的空卡。

## 11. 验收标准

### 11.1 功能验收

- 打开 `/admin/sales` 能加载销售单。
- 默认不显示已删除销售单。
- 搜索客户名、商品名、单号可以返回结果。
- 搜索不会出现两个结果区或假空结果。
- 分页可用，换页不丢筛选条件。
- 点击销售单行或详情按钮打开 Dialog。
- Dialog 显示客户、单号、付款、开单人、时间、商品明细。
- 打印按钮会创建打印任务。
- 打印预览会打开 `print-html?auto=0`。
- 删除必须弹 `AlertDialog`。
- 删除成功后列表刷新，库存和余额回滚只由服务层处理。
- `/admin/sales` 仍可正常打开。

### 11.2 UI 验收

- 桌面端主列表是表格，不再是大卡片网格。
- 移动端使用紧凑卡片。
- 页面密度接近 shadcn 后台示例，不出现旧版后台的大按钮、大边距。
- 加载态使用 `Skeleton`。
- 空状态使用 `Empty`。
- 详情使用 `Dialog`。
- 删除使用 `AlertDialog`。
- 付款状态、单据状态、库存规则全部显示中文。

### 11.3 技术验收

必须补测试：

- 销售页业务组件存在。
- `SalesPage` 使用 `components/business/sales-list`。
- 销售页不再直接使用旧类名：`primary-action`、`ghost-action`、`status-badge`、裸 `panel`。
- 销售详情使用标准 `Dialog`，不是旧式 `Dialog + drawer-content`。
- 删除确认使用 `AlertDialog`。
- 列表使用 `Table + Pagination`。
- 加载态使用 `Skeleton`。
- 搜索只有一个结果/列表出口。

推荐命令：

```powershell
python -m unittest tests.test_admin_sales_actions_contract tests.test_admin_sales_page_redesign_contract -v
cd Z:\sjagent\admin
npm.cmd run build
```

浏览器 smoke：

```text
打开 http://127.0.0.1:8081/admin/sales
搜索一个真实客户
打开销售单详情
打开打印预览
点删除但不确认，确认 AlertDialog 文案
打开 http://127.0.0.1:8081/admin/sales 确认销售单页未受影响
```

## 12. 分阶段计划

### 阶段 1：文档和测试先行

- 写本开发手册。
- 新增 `tests/test_admin_sales_page_redesign_contract.py`。
- 测试先描述目标结构，不急着改 UI。

### 阶段 2：组件拆分

- 创建 `components/business/sales-list/`。
- 把销售列表、详情、删除确认从 `App.tsx` 拆出去。
- 暂时保持现有 API 和业务行为不变。

### 阶段 3：桌面表格重构

- 用 `Table` 替换桌面大卡片网格。
- 商品摘要只显示前 2 行。
- 行点击打开 Dialog。
- 操作区改为“详情 / 打印 / 更多”。

### 阶段 4：详情 Dialog

- 用标准 `Dialog` 替换当前旧式销售详情弹窗。
- 详情内使用 `Tabs` 分明细、付款、操作记录。
- 保留打印、预览、删除入口。

### 阶段 5：筛选和加载态

- 补付款状态筛选。
- 补日期快捷筛选。
- 加载态改成 `Skeleton`。
- 空状态只在加载完成后显示。

### 阶段 6：验证和文档更新

- 跑合同测试。
- 跑 admin build。
- 浏览器检查 `/admin/sales`。
- 浏览器检查 `/admin/sales` 刷新后仍可用。
- 更新总 UI 开发手册和阶段计划。

## 13. 不能再犯的错误

- 不允许一个搜索框既弹下拉空结果，又在页面底部显示结果。
- 不允许未点击搜索就显示“没有匹配”。
- 不允许把旧页面大卡片套进新组件就算完成。
- 不允许用 Dialog 冒充右侧详情页。
- 不允许用 Empty 冒充加载态。
- 不允许前端自行写库存回滚、余额回滚判断。
- 不允许英文状态值直接显示给用户。
- 不允许完成后不跑测试、不构建、不看页面。

## 14. 执行记录

### 2026-05-24 第一轮落地

已完成：

- 新增 `admin/src/components/business/sales-list/` 业务组件目录。
- `SalesPage` 已改为组合业务组件，不再把销售列表、详情和删除确认都塞在 `App.tsx`。
- 桌面端列表使用 `Table`，移动端使用紧凑 `Card`。
- 详情使用 `Dialog + Tabs + Table`。
- 删除确认使用 `AlertDialog`。
- 加载态使用 `Skeleton`，空状态使用 `Empty`。
- `api.salesCards` 已改成结构化查询参数。
- `/api/sales/cards` 已支持正常/已删除、付款状态和日期范围筛选。

已验证：

```powershell
python -m unittest tests.test_admin_sales_page_redesign_contract tests.test_admin_sales_actions_contract tests.test_business_services -v
python -m py_compile src\services\business\sales.py src\engine\native_db.py src\channels\http_api\__init__.py
cd Z:\sjagent\admin
npm.cmd run build
```

剩余人工确认：

- 在浏览器打开 `/admin/sales`，确认列表密度、详情 Dialog、删除确认和筛选手感。
- 打开 `/admin/sales`，确认销售单页不受影响。
