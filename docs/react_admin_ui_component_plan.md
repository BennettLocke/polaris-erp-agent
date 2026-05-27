# React 后台 UI 组件匹配方案书

版本：V1.0  
日期：2026-05-24  
适用范围：`/admin` React 后台，不影响旧 `/web`

> 2026-05-24 修正：后续 `/admin` UI 开发以 [React Admin Radix/shadcn 底座重做项目计划书](react_admin_radix_shadcn_foundation_plan.md) 为上层计划。本文保留组件匹配表，但执行顺序必须先完成 shadcn/Radix 底座，再逐页迁移。

> 2026-05-24 补充：页面级设计以 [React 后台页面级设计蓝图](react_admin_page_design_blueprint.md) 为准。每个页面必须先明确主流程、弹窗、详情 Sheet、风险确认、空状态和服务层边界，再开始改 UI。

## 1. 目标

这份方案书解决一个问题：React 后台不能再“想到哪个组件就补哪个组件”。后续所有页面、弹窗、表格、筛选、状态、分页、日期、复选框、侧边栏，都必须先匹配组件，再开发页面。

目标是：

- 以 `Z:/肆计包装小程序/组件库全新重做` 为本地视觉标准。
- 以 shadcn/Radix 官方组件为结构参考。
- React 后台页面不再散写临时 UI。
- 每个业务页面都有明确组件组合。
- 每个组件都有统一尺寸、字号、边框、圆角和黑白灰色彩规则。
- 大列表必须分页，日期必须统一日期选择器，布尔状态必须统一 Checkbox/Switch，状态标签必须统一 Badge。

## 2. 官方组件依据

本次先确认这些官方组件作为后台基础组件池：

| 组件 | 官方用途 | 本项目用途 |
| --- | --- | --- |
| Sidebar | 可组合、可主题化、可折叠的侧边栏 | 后台主导航、分组导航、数量徽章、移动端抽屉导航 |
| Card | Header / Content / Footer 卡片结构 | 客户卡片、商品卡片、销售单卡片、工作台指标 |
| Badge | 状态、计数、短标签 | 已付款/月结/库存状态/数量/分类 |
| Table / Data Table | 数据表格、复杂表格可结合 TanStack Table | 库存、流水、销售明细、用户、设置日志 |
| Pagination | 页码、上一页、下一页 | 商品、客户、销售单、图片资产、库存日志 |
| Calendar / Date Picker | 日期选择和范围选择 | 开单日期、销售筛选、结款月份、库存流水日期 |
| Checkbox | 勾选、多选、表单布尔值 | 批量选择、显示字段、权限勾选 |
| Switch | 单个开关 | 启用、月结客户、是否扣库存、是否 1 件起 |
| Select / Native Select | 固定选项选择 | 仓库、付款方式、状态、单位、分类 |
| Combobox | 可搜索选择 | 客户搜索、商品搜索、仓库/用户长列表搜索 |
| Dialog / Alert Dialog | 弹窗和危险确认 | 上传、编辑、删除确认、结款、收款 |
| Sheet / Drawer | 侧边详情 | 客户详情、销售单详情、商品详情、库存单详情 |
| Tabs | 同一页面内分组 | 设置页、库存页、图片资产页、商品详情 |
| Dropdown Menu | 更多操作菜单 | 卡片右上角操作、表格行操作 |
| Tooltip | 图标按钮解释 | 侧边栏折叠后、图标按钮 |
| Skeleton / Empty | 加载和空状态 | 列表加载、图片加载、无数据 |
| Separator | 分隔线 | 详情区块、表单分组 |
| Avatar | 用户头像/占位 | 登录用户、小程序用户、操作人 |
| Breadcrumb | 页面层级 | 复杂详情页、设置子页 |
| Scroll Area | 固定区域滚动 | 侧边栏内容、弹窗列表、图片选择器 |
| Command | 命令式搜索/快捷操作 | 后续 Agent 工作台、全局搜索 |

官方参考链接：

- Sidebar: https://ui.shadcn.com/docs/components/radix/sidebar
- Badge: https://ui.shadcn.com/docs/components/radix/badge
- Card: https://ui.shadcn.com/docs/components/radix/card
- Table: https://ui.shadcn.com/docs/components/radix/table
- Pagination: https://ui.shadcn.com/docs/components/radix/pagination
- Calendar: https://ui.shadcn.com/docs/components/radix/calendar
- Date Picker: https://ui.shadcn.com/docs/components/radix/date-picker
- Checkbox: https://ui.shadcn.com/docs/components/radix/checkbox
- Select: https://ui.shadcn.com/docs/components/radix/select
- Dialog: https://ui.shadcn.com/docs/components/radix/dialog

## 3. UI 基础规则

### 3.1 视觉规则

| 项目 | 标准 |
| --- | --- |
| 颜色 | 后台基础 UI 只用黑、白、灰。业务状态也优先用灰阶 Badge，不用一堆彩色标签。 |
| 字体 | `PingFang SC`, `PingFang TC`, `Microsoft YaHei UI`, `Microsoft YaHei`, system-ui, -apple-system, BlinkMacSystemFont, `Segoe UI`, sans-serif |
| 字号 | 后台普通内容 13px；页面标题 20px；卡片标题 14-15px；徽章 12px。 |
| 按钮 | 默认 32px，紧凑按钮 28px，图标按钮按对应尺寸。 |
| 输入框 | 36px 高，6px 圆角。 |
| 卡片 | 常规 14px 圆角；业务列表卡片允许紧凑但不得超过 14px。 |
| 间距 | 业务后台以紧凑扫描为主，避免大块营销式留白。 |

### 3.2 组件使用规则

| 场景 | 必须使用 |
| --- | --- |
| 状态、计数、短标签 | `Badge` |
| 主要动作、次要动作、危险动作 | `Button` |
| 固定选项 | `Select` 或 `Native Select` |
| 可搜索选项 | `Combobox` |
| 布尔开关 | 单个用 `Switch`，多选用 `Checkbox` |
| 多个互斥选项 | `Toggle Group` 或 `Radio Group` |
| 大列表 | `Table` 或业务 `Card + Pagination` |
| 危险删除 | `Alert Dialog` |
| 编辑表单 | `Dialog`，复杂详情用 `Sheet` |
| 日期/月份 | `Date Picker` / `Calendar`，月份用统一 MonthPicker |
| 图片比例 | `Aspect Ratio` |
| 加载 | `Skeleton` |
| 空状态 | `Empty` |

## 4. 全局布局目标

### 4.1 Sidebar

当前侧边栏是手写 `nav button`。目标改成 shadcn Sidebar 结构：

```text
SidebarProvider
  Sidebar
    SidebarHeader      品牌：肆计包装 / 北极星
    SidebarContent
      SidebarGroup     主业务：工作台、开单、销售单、客户
      SidebarGroup     资产：商品、图片资产、库存、订单
      SidebarGroup     系统：设置
    SidebarFooter      当前账号、登录状态、退出
    SidebarRail        折叠侧边栏
  SidebarInset         页面主体
```

目标：

- 支持折叠到图标。
- 主导航右侧数量使用 `SidebarMenuBadge` 或 `Badge`。
- 库存未来有子导航：库存明细、库存日志、出入库、盘点、调拨、仓库设置。
- 移动端使用 offcanvas，不挤压内容。

### 4.2 页面骨架

每个页面统一：

```text
PageHeader
  Breadcrumb 可选
  标题
  描述
  顶部动作
PageToolbar
  搜索
  筛选
  日期
  批量操作
PageContent
  Card / Table / Tabs
PageFooter
  Pagination / 汇总
```

## 5. 页面与组件匹配表

### 5.1 工作台

| 功能 | 目标组件 |
| --- | --- |
| 今日指标 | `Card size="sm"` + `Badge` |
| 最近销售单 | `Card` 或 `Table`，根据数量决定 |
| 最近订单 | `Card` + `Badge` |
| AI 对话入口 | `Command` 或独立 Agent Panel |
| 加载 | `Skeleton` |

目标：工作台是“扫一眼知道今天情况”，不要大卡片堆满。

### 5.2 开单

| 功能 | 目标组件 |
| --- | --- |
| 客户搜索 | `Combobox` |
| 创建客户 | `Dialog` + `Field` + `Input` |
| 开单日期 | `Date Picker` |
| 结款状态 | `Select` |
| 已付方式 | `Radio Group` 或 `Select` |
| 商品搜索 | `Combobox` |
| 商品颜色/规格选择 | `Toggle Group` 或紧凑 `Card` |
| 明细行 | `Table` |
| 数量/价格 | `Input`，数字输入禁用滚轮 |
| 提交结果 | `Alert` / `Toast` |

目标：开单页面以表格效率为主，不做大卡片式商品堆叠。开单日期已经改为 `DateTimePicker`，后续不得再使用原生 `datetime-local`。

### 5.3 销售单

| 功能 | 目标组件 |
| --- | --- |
| 销售单列表 | 紧凑 `Card` 或 `Table` 两种视图 |
| 状态 | `Badge` |
| 付款状态 | `Badge` |
| 日期筛选 | `Date Picker` / MonthPicker |
| 详情 | `Sheet` |
| 账单明细 | `Table` |
| 打印 | `Button` + `Dropdown Menu` |
| 删除 | `Alert Dialog` |
| 分页 | `Pagination` |

目标：默认列表不要显示过多视觉噪音；单号、客户、金额、付款、开单人、时间必须清晰。

销售单卡片下一版方案：

- 参考 shadcn `Card` 示例：每张单只保留一个外层 `Card`，不再在卡片内套多个大圆角信息块。
- `CardHeader` 左侧放客户名和单号，右侧放订单状态 `Badge`；付款状态用第二个小 `Badge`，不要用大块标签。
- `CardContent` 用紧凑明细列表，最多展示 2-3 行商品；超出显示“还有 X 行”，点“详情”进入 `Sheet` 看完整账单。
- 商品明细行按 `商品名 / 颜色 / 数量 / 金额` 四列扫描，不把每一行再做成厚卡片。
- 汇总区改成一行 `总数量 / 总价 / 付款 / 开单人 / 时间`，使用小号 label + value，不做四个大指标卡。
- 操作区放在 `CardFooter`：`详情`、`打印`、更多操作 `DropdownMenu`；删除仍然走 `AlertDialog`，避免红色按钮长期占主视觉。
- 列表页保留分页 `Pagination`；后续可以增加“紧凑卡片视图 / 表格视图”两个视图，默认用紧凑卡片。
- 验收时必须和 shadcn Card、Badge、Dropdown Menu、Sheet、Table 示例并排对照；如果看起来还是旧 WebUI 大卡片，只算未完成。

### 5.4 客户

| 功能 | 目标组件 |
| --- | --- |
| 客户列表 | `Card size="sm"` |
| 普通/月结 | `Badge` |
| 单数 | `Badge ghost` |
| 最近下单/金额/年消费/余额 | 紧凑指标行 |
| 详情 | `Sheet` |
| 收款/充值/结款/调余额 | `Dialog` |
| 月份销售单 | MonthPicker + `Table` |
| 余额明细 | `Table` + `Pagination` |

目标：客户页用于快速扫描，不再用大号卡片；详情里的销售单和余额流水改表格。

### 5.5 商品

| 功能 | 目标组件 |
| --- | --- |
| 商品列表 | `Card size="sm"` + 商品主图 |
| 分类筛选 | 一级/二级 `Tabs` 或 `Toggle Group`，不横向滚动 |
| 状态/分类/库存规则 | `Badge` |
| 商品编辑 | `Dialog`，后续复杂时升级 `Sheet` |
| 分类/单位 | `Select` |
| 1 件起、扣库存 | `Switch` |
| 颜色/规格 | `Table` 或紧凑规格卡 |
| 图片选择 | `Dialog` + `Tabs` + `Pagination` |
| 图片预览 | `Aspect Ratio` |

目标：商品页以 SPU 为主，不显示 SKU 噪音；规格只在编辑/详情里展开。

### 5.6 图片资产

| 功能 | 目标组件 |
| --- | --- |
| 图片列表 | `Card` + `Aspect Ratio` |
| 类型筛选 | `Tabs` |
| 商品/分类筛选 | `Combobox` / `Select` |
| 删除误传 | `Alert Dialog` |
| 上传 | `Dialog` |
| 批量清理 | `Checkbox` + `Toolbar` |
| 分页 | `Pagination` |

目标：默认按 SPU/大类聚合，进入后再看主图、详情页、颜色图，不一次渲染大量图片。

### 5.7 库存

| 功能 | 目标组件 |
| --- | --- |
| 子导航 | `Tabs`：库存明细、库存日志、出入库、盘点、调拨、仓库设置 |
| 库存明细 | `Table` |
| 库存日志 | `Table` + `Date Picker` |
| 出入库单 | `Table` + `Sheet` |
| 盘点单 | `Table` + `Dialog` |
| 调拨单 | `Table` + `Dialog` |
| 仓库选择 | `Select` |
| 是否允许负库存 | `Switch`，按规则只读或可配置 |
| 分页 | `Pagination` |

目标：库存模块不要用大卡片堆数据，主显示必须是表格。

### 5.8 设置

| 功能 | 目标组件 |
| --- | --- |
| 设置分类 | `Tabs` |
| 编号设置 | `Card` + `Field` + `Input` + `Table` |
| 商品基础 | `Table` + `Dialog` |
| 库存规则 | `Table` + `Switch`，固定规则只读 |
| 收款/结款 | `Table` + `Badge` |
| 图片/OSS | `Field` + `Input` + `Checkbox` |
| 用户权限 | `Table` + `Checkbox` + `Switch` |
| 打印设置 | `Card` + `Select` + `Checkbox` |

目标：设置页不能是 textarea 手动输入规则，必须结构化。

### 5.9 订单

| 功能 | 目标组件 |
| --- | --- |
| 订单看板 | `Card size="sm"` + `Badge` |
| 订单明细 | `Table` |
| 制作/发货/丝印状态 | `Badge` |
| 状态更新 | `Button Group` |
| 图片/设计稿 | `Aspect Ratio` + `Dialog` |
| 删除 | `Alert Dialog` |
| 分页 | `Pagination` |

目标：订单页要能快速看到待制作、待发货、丝印状态；后端仍复用 `workflow_order` 过程订单接口，不和正式销售单混用。

### 5.10 Agent 工作台

| 功能 | 目标组件 |
| --- | --- |
| 对话区 | `Scroll Area` |
| 输入区 | `Textarea` + `Button` |
| 快捷指令 | `Command` |
| 执行结果 | `Card` + `Badge` |
| 错误提示 | `Alert` |
| 历史记录 | `Table` 或 `Card` |

目标：Agent 工作台要和后台业务组件一致，不做另一个风格。

## 6. 组件落地顺序

| 顺序 | 组件 | 原因 |
| --- | --- | --- |
| 1 | Sidebar | 全局入口先统一，避免每页导航不一致。 |
| 2 | Button / Badge / Card / Input / Field | 基础密度和风格先稳定。 |
| 3 | Table / Pagination | 销售、库存、客户详情、图片资产都需要。 |
| 4 | Select / Combobox / Checkbox / Switch | 表单和设置页必须统一。 |
| 5 | Dialog / Alert Dialog / Sheet | 编辑、详情、删除确认统一。 |
| 6 | Calendar / Date Picker / MonthPicker | 开单、筛选、结款月份统一。 |
| 7 | Tabs / Dropdown Menu / Tooltip / Skeleton / Empty | 页面体验补齐。 |
| 8 | Command / Resizable / Scroll Area | Agent 工作台和复杂页面。 |

## 7. 文件目标结构

React 后台组件建议逐步整理成：

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
  date-picker.tsx
  month-picker.tsx
  dropdown-menu.tsx
  tooltip.tsx
  skeleton.tsx
  empty.tsx
```

业务组件放：

```text
admin/src/components/business/
  customer-card.tsx
  sales-order-card.tsx
  product-card.tsx
  media-card.tsx
  inventory-table.tsx
  workflow-card.tsx
```

页面只负责组合，不直接写大段 UI 细节。

## 8. 验收标准

每做一个页面或组件，必须符合：

- 页面里不再散写 `status-badge` 这类临时状态样式，统一 `Badge`。
- 有分页需求的接口，页面必须显示 `Pagination`。
- 日期、月份不能手写普通 input，统一日期/月选择组件。
- 复选框、开关不能用原生 input 直接裸露，统一 `Checkbox` / `Switch`。
- 列表超过 20 条必须分页或虚拟化。
- 表格行操作必须使用 `Dropdown Menu` 或统一按钮组。
- 删除、清理、危险修改必须走 `Alert Dialog`。
- 弹窗必须有标题和说明。
- 加载必须有 `Skeleton` 或明确加载状态。
- 空数据必须有 `Empty`。
- 移动端不能横向撑爆。
- 旧 `/web` 不受影响。

## 9. 下一步执行目标

下一步不直接继续堆页面，先做组件底座：

1. 重构 Sidebar，把当前手写侧边栏换成组件化结构。`已完成基础版`
2. 把 `Badge`、`Card`、`Button`、`Input` 抽到 `components/ui`。
3. 做 `Pagination` 组件，先接商品、图片资产、销售单。
4. 做 `Table` 组件，先接库存计划页和客户详情销售单。
5. 做 `DatePicker` / `MonthPicker`，替换开单日期和客户月份筛选。
6. 做 `Checkbox` / `Switch`，替换设置页和商品编辑里的原生控件。

这一步完成后，再继续迁移库存模块，避免后面所有页面返工。

## 10. 当前落地记录

### 2026-05-24 Sidebar 基础版

已新增 `admin/src/components/ui/sidebar.tsx`，按 shadcn Sidebar 的组合结构落地：

```text
SidebarProvider
  Sidebar
    SidebarHeader
    SidebarContent
      SidebarGroup
        SidebarGroupLabel
        SidebarMenu
          SidebarMenuItem
            SidebarMenuButton
            SidebarMenuBadge
    SidebarFooter
    SidebarRail
  SidebarInset
```

当前效果：

- 主导航按“主业务 / 资产 / 系统”分组。
- 激活页面使用 `data-active`，样式走黑白灰 token。
- 支持桌面侧边栏折叠到 64px 图标栏。
- 展开状态下，侧边栏头部有折叠按钮；折叠状态下，页头显示展开按钮。
- 后续库存子导航可继续放进 SidebarGroup 或页面内 Tabs。

### 2026-05-24 UI 开发手册补充

已新增 `docs/react_admin_ui_development_handbook.md`，后续 `/admin` UI 开发以该手册为准。

重要修正：

- shadcn 不只是组件结构参考，也是视觉风格参考。
- 先对齐 shadcn 官方示例的底色、间距、按钮、字号、激活态，再接肆计包装业务数据。
- 不允许再做“旧 UI 外观 + Radix 组件壳子”。
- Sidebar 需要先按官方示例视觉返工，通过浏览器截图对比后，再继续 Button / Card / Input / Field。

### 2026-05-24 Sidebar 视觉返工

已按 shadcn Radix Sidebar 官方示例返工侧边导航第一版：

- Sidebar 宽度 `256px`，折叠宽度 `48px`。
- 侧栏背景 `#fafafa`，菜单激活态 `#f4f4f5`。
- Header 改成 workspace switcher 风格，不再使用旧的大品牌块。
- 菜单行高 `32px`，图标 `16px`。
- Footer 改成紧凑账号区。
- 组件补齐 `data-slot` / `data-sidebar` 属性。

验收已通过：

- `python -m unittest tests.test_admin_sidebar_contract -v`
- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- `/admin` 和 `/web` smoke 均为 200。

下一步：开始 Button / Badge / Card / Input / Field，先接开单页和顶部操作区。

### 2026-05-24 shadcn/Radix 底座第一批组件

已完成第一批底座文件：

- `admin/components.json`
- `admin/src/lib/utils.ts`
- `admin/src/components/ui/button.tsx`
- `admin/src/components/ui/badge.tsx`
- `admin/src/components/ui/card.tsx`
- `admin/src/components/ui/input.tsx`
- `admin/src/components/ui/field.tsx`
- `admin/src/components/ui/textarea.tsx`

这批组件的执行标准：

- 组件入口统一在 `admin/src/components/ui/`。
- 组件调用方式按 shadcn 习惯保留，例如 `Button variant size asChild`、`CardHeader/CardContent/CardFooter`、`FieldGroup/FieldLabel/FieldDescription`。
- 视觉 token 统一走 `admin/src/styles.css` 里的黑白灰变量，不再在组件里写页面级临时样式。
- 旧 `admin/src/components/badge.tsx` 只保留兼容导出，后续页面迁移完成后再移除。

已验证：

- `python -m unittest tests.test_admin_shadcn_foundation_contract -v`
- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`

下一步不是直接重做所有页面，而是先抽出 `components/layout`：`AppShell`、`AppSidebar`、`PageHeader`、`Toolbar`。布局层完成后，再用开单页作为第一个完整迁移样板。

### 2026-05-24 shadcn/Radix 扩展通用组件

已继续补齐后台会高频使用的通用组件：

- 表单选择：`Select`、`Combobox`、`Checkbox`、`Switch`
- 数据展示：`Table`、`Pagination`
- 弹层：`Dialog`、`AlertDialog`、`Sheet`、`Popover`
- 导航与菜单：`Tabs`、`DropdownMenu`、`Tooltip`
- 基础状态：`Separator`、`Skeleton`、`Empty`、`ScrollArea`

实现方式：

- Radix 交互组件使用对应 `@radix-ui/react-*` 包。
- shadcn 的导出命名和组合方式保留，例如 `SelectTrigger/SelectContent/SelectItem`、`DialogTitle/DialogContent`、`TableHeader/TableRow/TableCell`。
- 因为当前 `/admin` 还没有完整 Tailwind 编译链，组件样式没有直接复制 Tailwind class，而是落到 `sj-*` CSS token，保证现有 Vite 构建可用。
- 旧 `components/combobox.tsx` 已改成兼容导出，后续页面迁移统一从 `components/ui/combobox` 引入。

已验证：

- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- 浏览器 smoke：`/admin` 正常，`/web` 正常，控制台无 error。

### 2026-05-24 布局组件抽离

已把 `/admin` 的通用布局从 `App.tsx` 抽到 `admin/src/components/layout/`：

- `AppShell`：负责 `SidebarProvider`、`AppSidebar` 和页面内容区域。
- `AppSidebar`：负责工作区头部、分组导航、账号底部和折叠栏。
- `PageHeader`：负责顶部标题、说明弹窗和退出按钮。
- `Toolbar`：提供后续页面统一使用的工具栏容器。

执行标准：

- `App.tsx` 只负责路由、数据和页面切换，不再写 sidebar 内部结构。
- 后续页面顶部、工具栏、侧边导航都复用 layout 组件，不再各页面临时拼。
- 旧 `/web` 不参与这次改造，仍然保持原有入口。

已验证：

- `python -m unittest tests.test_admin_sidebar_contract -v`
- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`

下一步：用开单页 `sales-new` 做第一个完整迁移样板，把按钮、输入、卡片、字段、空状态和搜索区统一切到 `components/ui`。

### 2026-05-24 开单页样板迁移

已把 `/admin/sales-new` 作为第一张样板页迁到组件底座：

- 按钮统一使用 `Button`。
- 卡片统一使用 `Card/CardHeader/CardContent/CardFooter`。
- 输入框统一使用 `Input`。
- 字段布局统一使用 `Field/FieldGroup/FieldLabel/FieldContent`。
- 结款、付款方式、仓库统一使用 `Select`。
- 客户和商品搜索统一从 `components/ui/combobox` 引入。
- 空状态统一使用 `Empty`。
- 页面顶部操作区使用 `Toolbar`。
- 创建客户弹窗使用 `components/ui/dialog`。

保留不变：

- `selectCustomer` 月结客户自动切换规则。
- `addSalesLine` 客户历史价、零售价和颜色规格选择逻辑。
- `submitSalesOrder` 仍调用 `/api/sales/add`，不改业务链路。

已验证：

- `python -m unittest tests.test_admin_sales_new_contract -v`
- `python -m unittest tests.test_admin_sales_new_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- 浏览器 smoke：`/admin/sales-new` 正常，页面内旧 `primary-action/ghost-action/status-badge/panel` 数量为 0；`/web` 正常。

下一步：按同一标准迁移销售单列表页或客户页，优先选择业务风险低但复用组件多的页面。

### 2026-05-24 销售单列表页迁移

已把 `/admin/sales` 按开单页样板继续迁到组件底座：

- 列表页外层使用 `Card`，顶部筛选使用 `Toolbar`。
- 搜索框使用 `Input`，搜索、详情、打印、删除使用 `Button`。
- 状态使用 `Badge`，不再使用 `status-badge`。
- 分页使用 `Pagination/PaginationPrevious/PaginationNext`。
- 加载和空列表使用 `Empty`。
- 销售单详情弹窗使用 `components/ui/dialog`。
- 删除确认使用 `AlertDialog`，仍保留服务层删除和库存/余额回滚流程。

保留不变：

- `handlePrint` 仍创建销售单打印任务。
- `handlePreview` 仍打开销售单打印预览。
- `handleDelete/confirmDeleteSales` 仍调用 `/api/sales/<id>` 删除接口，由服务层做软删除、库存回滚和余额回滚。

已验证：

- `python -m unittest tests.test_admin_sales_actions_contract -v`
- `python -m unittest tests.test_admin_sales_actions_contract tests.test_admin_sales_new_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- 浏览器 smoke：`/admin/sales` 正常加载 163 单，页面内旧 `primary-action/ghost-action/status-badge/panel` 数量为 0；`/web` 正常。

下一步：迁移客户页。客户页业务更多，重点检查余额按钮、月结切换、月份筛选和详情弹窗不能变逻辑。

### 2026-05-24 Radix/shadcn 底座重做计划

已新增 `docs/react_admin_radix_shadcn_foundation_plan.md` 和执行清单 `docs/superpowers/plans/2026-05-24-react-admin-radix-shadcn-foundation.md`。

这次修正后，下一步不再是单独补 Button，而是：

1. 先让 `/admin` 成为 shadcn-compatible 工程：补 `components.json`、`src/lib/utils.ts`、`@/` alias 和基础依赖。
2. 再集中建立 `components/ui`：Button、Badge、Card、Input、Field、Textarea、Select、Combobox、Checkbox、Switch、Table、Pagination、Dialog、Sheet、Tooltip、Empty、Skeleton。
3. 然后抽 `components/layout`：AppShell、AppSidebar、PageHeader、Toolbar。
4. 最后用开单页作为第一个样板页，验证所有按钮、输入、卡片、状态和操作区都来自统一组件。

验收口径改为：页面只要还在新增旧 class，例如 `primary-action`、`ghost-action`、`status-badge`、`panel`，就不算完成新 UI 迁移。
