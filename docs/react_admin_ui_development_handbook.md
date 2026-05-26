# React 后台 UI 开发手册

版本：v1.0  
日期：2026-05-24  
适用范围：`/admin` React 后台  
保护范围：旧后台 `/web` 在新后台验收前必须保持可用

> 2026-05-24 修正：后续开发先执行 `docs/react_admin_radix_shadcn_foundation_plan.md`。没有完成 shadcn/Radix 底座前，不继续堆业务页面。

> 2026-05-24 补充：页面改造前先写页面级设计，见 `docs/react_admin_page_design_blueprint.md`。不能只把旧页面套成 shadcn 组件壳子，必须重新设计主流程、弹窗、详情、风险确认和验收标准。

## 1. 这份手册解决什么问题

这份手册不是组件清单，而是后续开发 `/admin` 的执行规则。

这次 Sidebar 做错的根因是：只把 shadcn 当成“组件结构参考”，没有把 shadcn 当成“视觉风格标准”。后续必须改成：

```text
先对齐 shadcn 官方示例的视觉风格
  -> 再替换成肆计包装自己的业务导航和数据
    -> 最后补业务交互和接口
```

不允许再出现“旧 UI 外观 + Radix 组件壳子”的做法。

更准确地说，后续不是“仿照 Radix 风格补组件”，而是让 `/admin` 成为 shadcn-compatible 工程：

- 有 `components.json`。
- 有 `src/lib/utils.ts` 和统一 `cn()`。
- 基础组件集中在 `admin/src/components/ui/`。
- 业务组件集中在 `admin/src/components/business/`。
- 页面只组合 layout、ui、business 组件。
- 页面迁移完成前，不允许新增 `primary-action`、`ghost-action`、`status-badge`、`panel` 这类旧样式。

## 2. 设计源优先级

后续每个组件、页面、弹窗、表格、侧边栏都按下面优先级执行：

| 优先级 | 来源 | 用法 |
| --- | --- | --- |
| 1 | shadcn 官方示例页面 | 作为视觉、结构、交互状态的第一参考 |
| 2 | shadcn 官方源码 | 可以直接照着组件结构和 class 组织方式做 |
| 3 | `Z:/肆计包装小程序/组件库全新重做` | 作为本地字体、字号、按钮高度、边框、圆角的补充标准 |
| 4 | 当前 `/admin` 已落地组件 | 只作为兼容参考，不能反过来覆盖 shadcn 风格 |
| 5 | 旧 `/web` | 只参考业务功能和字段，不参考视觉风格 |

官方参考入口：

- Sidebar: https://ui.shadcn.com/docs/components/radix/sidebar
- Button: https://ui.shadcn.com/docs/components/radix/button
- Card: https://ui.shadcn.com/docs/components/radix/card
- Input: https://ui.shadcn.com/docs/components/radix/input
- Field: https://ui.shadcn.com/docs/components/radix/field
- Badge: https://ui.shadcn.com/docs/components/radix/badge
- Table: https://ui.shadcn.com/docs/components/radix/table
- Dialog: https://ui.shadcn.com/docs/components/radix/dialog
- Sheet: https://ui.shadcn.com/docs/components/radix/sheet
- Tabs: https://ui.shadcn.com/docs/components/radix/tabs
- Pagination: https://ui.shadcn.com/docs/components/radix/pagination
- Select: https://ui.shadcn.com/docs/components/radix/select
- Combobox: https://ui.shadcn.com/docs/components/radix/combobox
- Calendar: https://ui.shadcn.com/docs/components/radix/calendar
- Date Picker: https://ui.shadcn.com/docs/components/radix/date-picker

## 3. 开发前必须做的事

每做一个 UI 区块，先完成这 5 件事：

1. 打开对应 shadcn 官方示例。
2. 看官方示例的实际视觉：背景、间距、按钮、字号、圆角、激活态。
3. 看官方源码：组件层级、命名、组合方式。
4. 写下本次要复刻的视觉标准。
5. 再开始写代码。

如果没有做第 1-4 步，不允许直接凭感觉改 UI。

## 4. 风格硬标准

### 4.1 总体观感

`/admin` 的目标不是“传统后台”，而是 shadcn 那种干净、克制、紧凑的后台应用。

必须符合：

- 灰白底色，不做大面积纯白空板。
- 黑、白、灰为主，不把业务绿色当成主视觉。
- 小字号、紧凑行高、细边框。
- 按钮克制，不做大块厚重按钮。
- 卡片轻，不做厚阴影。
- 页面密度适合扫数据，不做营销页式大留白。
- 图标尺寸和文字比例接近 shadcn 示例。

### 4.2 禁止项

后续新 UI 禁止：

- 直接沿用旧 `/web` 的大按钮、大卡片、大间距。
- 只把旧结构换成 `<Button>`、`<Card>`，但视觉还是旧风格。
- 每个页面单独写一套颜色、圆角、按钮高度。
- 用临时 `status-badge`、`ghost-action`、`primary-action` 继续扩散。
- 用 textarea 手动配置商业规则。
- 用英文状态值直接显示给用户。
- 横向长滚动分类条。
- 没有浏览器截图就说 UI 已经完成。
- 日期、时间、月份直接使用原生 `input[type="datetime-local"]`、`input[type="date"]`、`input[type="month"]`。

## 5. Sidebar 执行标准

Sidebar 是第一优先级，必须先返工到接近 shadcn 官方示例。

### 5.1 结构标准

必须使用类似官方结构：

```text
SidebarProvider
  Sidebar
    SidebarHeader
      workspace / brand switcher style area
    SidebarContent
      SidebarGroup
        SidebarGroupLabel
        SidebarMenu
          SidebarMenuItem
            SidebarMenuButton
            SidebarMenuBadge
    SidebarFooter
      current user area
    SidebarRail
  SidebarInset
```

### 5.2 视觉标准

Sidebar 要对齐官方示例：

- 整体背景是浅灰，不是大片纯白。
- 品牌区像 workspace switcher，不是厚重大 logo 卡。
- 菜单项高度接近 32px。
- 图标尺寸接近 16px。
- 分组标题小、轻、灰。
- 激活项使用浅灰底 + 黑色文字。
- 折叠后只保留图标列，不挤压业务页面。
- Footer 是账号区域，不做两个大卡片。

### 5.3 验收方法

必须浏览器截图对比：

1. 左边打开本地 `/admin`。
2. 右边打开 shadcn Sidebar 示例。
3. 对比 sidebar 的背景、宽度、菜单高度、图标尺寸、激活态、footer。
4. 明显不像时不算完成。

## 6. 基础组件执行标准

基础组件先做这些：

```text
admin/src/components/ui/
  button.tsx
  badge.tsx
  card.tsx
  input.tsx
  field.tsx
  sidebar.tsx
  table.tsx
  pagination.tsx
  select.tsx
  combobox.tsx
  checkbox.tsx
  switch.tsx
  dialog.tsx
  alert-dialog.tsx
  sheet.tsx
  tabs.tsx
  calendar.tsx
  date-time-picker.tsx
```

每个组件必须满足：

- 结构参考 shadcn 官方源码。
- 视觉参考 shadcn 官方示例。
- 命名统一用 `sj-*` token 或组件内部 class。
- 页面只组合组件，不在页面里临时堆样式。
- 必须至少接入一个真实业务页面，不允许只建空组件。

## 7. 页面改造顺序

UI 改造顺序调整为：

1. Sidebar 视觉返工。
2. Button / Badge / Card / Input / Field 视觉底座。
3. 开单页基础区和销售明细区。
4. 客户列表和客户详情。
5. 销售单列表和销售单详情。
6. 商品列表、商品编辑、图片选择器。
7. 图片资产管理。
8. 设置页。
9. 库存页。
10. 工作流页。
11. Agent 工作台。

每一步只改 `/admin`，不影响 `/web`。

## 8. 每个页面的固定开发流程

每个页面都按这个流程：

```text
确认 shadcn 对应示例
  -> 写页面视觉目标
    -> 抽/补基础组件
      -> 接真实业务数据
        -> 浏览器截图验证
          -> 跑构建和接口 smoke
            -> 更新开发文档
```

不能反过来先堆页面，再说后续统一样式。

## 9. 验收标准

### 9.1 视觉验收

每个 UI 阶段完成后必须检查：

- 和 shadcn 官方示例是否明显同一种风格。
- 是否仍然残留旧 WebUI 的大按钮、大卡片、大间距。
- 字号是否过大。
- 边框是否过重。
- 背景是否过白。
- 激活态、hover、disabled 是否统一。
- 按钮、输入框、徽章是否来自统一组件。

### 9.2 功能验收

每个页面必须检查：

- 页面能打开。
- API 返回正常。
- 登录态正常。
- `/web` 还能打开。
- 关键业务动作没有被 UI 重构破坏。

### 9.3 技术验收

每次提交前至少执行：

```powershell
cd Z:\sjagent\admin
npm.cmd run build
```

以及对应 Python 测试和 smoke。涉及 `/web`、服务层或 API 时，还必须验证 `/web`。

### 9.4 浏览器验收

不能只看代码。必须用浏览器实际打开：

- `/admin`
- 当前改动页面
- `/web`

涉及响应式或侧边栏时，还要测试折叠状态。

## 10. 文档维护规则

每次 UI 阶段完成后，必须更新：

- `docs/react_admin_ui_development_handbook.md`：如果标准变化。
- `docs/react_admin_ui_component_plan.md`：如果组件状态变化。
- `docs/react_radix_admin_rearchitecture_plan.md`：如果阶段进度变化。

文档里不能只写“已完成”，必须写：

- 做了什么。
- 对齐哪个 shadcn 示例。
- 接入了哪些业务页面。
- 验证了什么。
- 还剩什么。

## 11. 下一步执行目标

Sidebar 视觉返工已经完成第一版。下一步可以继续做基础组件底座：

1. Button / Badge / Card / Input / Field。
2. 先接开单页和顶部操作区。
3. 浏览器截图确认按钮、输入框和卡片已经进入 shadcn 风格。
4. 再迁移 Table / Pagination。

## 12. 当前落地记录

### 2026-05-24 shadcn/Radix 底座组件

已完成 `/admin` 的 shadcn-compatible 基础：

- `components.json` 已建立，别名固定为 `@/components`、`@/components/ui`、`@/lib/utils`。
- `src/lib/utils.ts` 已提供统一 `cn()`。
- `Button`、`Badge`、`Card`、`Input`、`Field`、`Textarea` 已进入 `admin/src/components/ui/`。
- 旧 `components/badge.tsx` 只保留兼容导出，页面后续应改为从 `@/components/ui/badge` 引入。

新的硬性规则：

- 新页面或迁移页面不得继续新增 `primary-action`、`ghost-action`、`status-badge`、`panel` 这类旧样式。
- 页面里的按钮、徽章、卡片、输入框、字段布局必须优先从 `components/ui` 引入。
- 日期时间必须用 `DateTimePicker`；月份和日期范围后续也要从 `Calendar/Popover/Select` 组合，不再直接使用浏览器原生日期控件。
- 如果一个页面只是换了组件名，但视觉和旧 WebUI 一样，不算迁移完成。
- 每完成一个页面迁移，必须补对应契约测试和浏览器截图检查。

已验证：

- `python -m unittest tests.test_admin_shadcn_foundation_contract -v`
- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`

### 2026-05-24 通用组件补齐

已补齐第二批通用组件：

- `Select`、`Combobox`、`Checkbox`、`Switch`
- `Table`、`Pagination`
- `Dialog`、`AlertDialog`、`Sheet`、`Popover`
- `Tabs`、`DropdownMenu`、`Tooltip`
- `Separator`、`Skeleton`、`Empty`、`ScrollArea`

后续页面迁移规则更新：

- 固定选项不得继续手写 `<select>` 样式，优先使用 `Select`。
- 可搜索客户、商品、用户等长列表，优先使用 `Combobox`。
- 删除、清理、危险修改必须使用 `AlertDialog`。
- 详情侧滑必须使用 `Sheet`。
- 列表数据优先使用 `Table + Pagination`，空列表使用 `Empty`，加载中使用 `Skeleton`。
- 页面内分类切换优先使用 `Tabs`，不要再做横向长滚动分类条。

已验证：

- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- 浏览器 smoke：`/admin` 和 `/web` 都正常。

### 2026-05-24 布局层抽离

已完成：

- `admin/src/components/layout/app-shell.tsx`
- `admin/src/components/layout/app-sidebar.tsx`
- `admin/src/components/layout/page-header.tsx`
- `admin/src/components/layout/toolbar.tsx`

后续页面迁移规则更新：

- 页面不再直接写 sidebar/header 内部结构。
- 顶部标题和说明入口统一用 `PageHeader`。
- 页面筛选、搜索、批量操作区统一优先用 `Toolbar`。
- `App.tsx` 只保留路由、页面选择和全局数据传递。

已验证：

- `python -m unittest tests.test_admin_sidebar_contract -v`
- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`

### 2026-05-24 开单页样板迁移

`/admin/sales-new` 已作为第一个完整样板页完成迁移。

执行标准已落地：

- 页面区块仍可保留业务布局 class，但不能再使用旧动作和状态 class：`primary-action`、`ghost-action`、`status-badge`、`panel`。
- 原生 `<button>`、`<input>`、`<select>` 不再直接写在开单页业务 JSX 里，统一走 `Button`、`Input`、`Select`。
- 客户和商品搜索从 `components/ui/combobox` 引入，不再走旧兼容路径。
- 创建客户弹窗从 `components/ui/dialog` 组合，后续页面弹窗按同样方式迁移。
- 小屏下 sidebar 自动收窄为 48px，避免挤压开单表单。

已验证：

- `python -m unittest tests.test_admin_sales_new_contract -v`
- `python -m unittest tests.test_admin_sales_new_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- 浏览器 smoke：`/admin/sales-new` 和 `/web` 都正常，控制台无 error。

### 2026-05-24 销售单列表页迁移

`/admin/sales` 已完成组件层迁移。

执行标准已落地：

- 搜索、打印、删除、详情按钮统一走 `Button`。
- 销售单卡片统一走 `Card`，状态统一走 `Badge`。
- 删除确认统一走 `AlertDialog`，不能回退到自写危险弹窗。
- 分页统一走 `Pagination`。
- 加载和空列表统一走 `Empty`。
- 销售单详情弹窗使用 `components/ui/dialog`，不再直接写 Radix 结构。
- 页面内旧动作/状态/容器 class：`primary-action`、`ghost-action`、`status-badge`、`panel` 必须为 0。

已验证：

- `python -m unittest tests.test_admin_sales_actions_contract -v`
- `python -m unittest tests.test_admin_sales_actions_contract tests.test_admin_sales_new_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- 浏览器 smoke：`/admin/sales` 和 `/web` 都正常，控制台无 error。

### 2026-05-24 开单日期时间组件修正

本次修正的是开单页日期控件：之前 `/admin/sales-new` 仍然使用浏览器原生 `datetime-local`，实际弹出的不是 shadcn/Radix 风格组件。

已落地：

- 新增 `admin/src/components/ui/calendar.tsx`，基于 `react-day-picker` 和 shadcn Calendar 结构。
- 新增 `admin/src/components/ui/date-time-picker.tsx`，组合 `Calendar + Popover + Select + Button`。
- `/admin/sales-new` 的“开单时间”改为 `DateTimePicker`。
- `tests/test_admin_sales_new_contract.py` 明确禁止 `SalesNewPage` 使用 `datetime-local`。

后续规则：

- 所有日期/时间选择都必须先匹配 shadcn Calendar / Date Picker 示例，再做本地业务封装。
- 不允许为了快而回退到浏览器原生日期控件。
- 日期控件完成后必须浏览器点击验证，不只看构建结果。

已验证：

- `python -m unittest tests.test_admin_sales_new_contract tests.test_admin_shadcn_foundation_contract tests.test_admin_sales_actions_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- 浏览器 smoke：`/admin/sales-new` 无 `input[type="datetime-local"]`，点击后出现 `DateTimePicker` 弹层。

### 2026-05-24 Sidebar 视觉返工

对齐来源：shadcn Radix Sidebar 官方示例。

已完成：

- Sidebar 宽度调整为 `256px`，折叠宽度调整为 `48px`。
- Sidebar 背景改为 `#fafafa` 浅灰底，不再是纯白侧栏。
- Header 改成 workspace switcher 风格：左侧品牌图标，中间品牌和说明，右侧上下切换图标。
- 菜单行高固定为 `32px`，图标为 `16px`。
- 激活项使用浅灰背景，不再使用厚边框。
- Footer 改成紧凑账号区，不再使用旧的大卡片。
- 折叠状态只保留图标列和账号首字。
- `admin/src/components/ui/sidebar.tsx` 已补 `data-slot` / `data-sidebar` 属性，方便后续对齐 shadcn 结构和测试。

已验证：

- `python -m unittest tests.test_admin_sidebar_contract -v`
- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- 本地 smoke：`/admin` 200，`/web` 200
- 浏览器检查：`/admin/sales-new` 展开宽度 256px，折叠宽度 48px，导航行高 32px，图标 16px。

### 2026-05-24 销售单页二次设计手册

已新增 `docs/react_admin_sales_page_development_handbook.md`，作为 `/admin/sales` 下一轮重构的执行标准。

关键调整：
- 销售单页桌面端主形态改为 `Table + Dialog`，不继续使用大卡片网格作为主列表。
- 详情使用居中 `Dialog`，删除使用 `AlertDialog`，加载使用 `Skeleton`，空状态使用 `Empty`。
- 搜索必须显式触发，不能出现未搜索就显示“没有匹配”的假空结果。
- 删除、库存回滚、余额回滚、月结欠款取消全部由服务层负责，前端只调用接口和展示结果。
- 实现前必须先补 `tests/test_admin_sales_page_redesign_contract.py`，再拆 `components/business/sales-list/`。

### 2026-05-24 销售单页二次落地

`/admin/sales` 已按二次设计手册完成第一轮落地，旧 `/web` 不在本次改造范围内。

已落地：

- 新增 `admin/src/components/business/sales-list/`，拆出列表工具栏、桌面表格、移动卡片、详情 Dialog、删除确认和空/加载态。
- 桌面端销售单主列表改为 `Table`，移动端保留紧凑 `Card`。
- 详情改为居中 `Dialog + Tabs + Table`，不再用旧式销售单详情弹窗。
- 删除改为 `AlertDialog`，前端只调用 `DELETE /api/sales/<id>`，库存、余额和月结影响继续由服务层处理。
- `api.salesCards` 改为结构化参数，支持 `keyword`、`page`、`pageSize`、`payStatus`、`status`、`dateFrom`、`dateTo`。
- 后端 `/api/sales/cards` 已支持正常/已删除、付款状态和日期范围筛选。

已验证：

- `python -m unittest tests.test_admin_sales_page_redesign_contract tests.test_admin_sales_actions_contract tests.test_business_services -v`
- `python -m py_compile src\services\business\sales.py src\engine\native_db.py src\channels\http_api\__init__.py`
- `cd Z:\sjagent\admin && npm.cmd run build`

### 2026-05-25 销售单页头部和详情弹窗调整

根据实际查看反馈，`/admin/sales` 做了两处修正：

- 页头去掉大号页码徽章，改成轻量标题和右侧页码/总数文本。
- 销售单详情从右侧 `Sheet` 改为居中 `Dialog`，保留 `Tabs + Table` 的账单结构。

已验证：

- `python -m unittest tests.test_admin_sales_page_redesign_contract tests.test_admin_sales_actions_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
