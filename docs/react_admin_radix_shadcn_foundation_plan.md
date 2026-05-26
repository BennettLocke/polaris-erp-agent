# React Admin Radix/shadcn 底座重做项目计划书

版本：V1.0  
日期：2026-05-24  
适用范围：新后台 `/admin`  
保护范围：旧后台 `/web` 在新后台验收前必须保持可用

## 1. 结论

新后台不能继续按“缺什么补什么”的方式做 UI。正确方向是：

```text
React + TypeScript + Vite
  -> shadcn/Radix 组件底座
    -> 北极星 layout 组件
      -> 北极星业务组件
        -> 开单、客户、销售单、商品、图片资产、库存、设置、工作流页面
```

这次重做的重点不是把旧页面的按钮改好看，而是先建立一个可长期扩展的后台组件体系。以后新增功能必须从统一组件和业务组件里组合出来，不允许每个页面单独写一套按钮、卡片、状态、弹窗和表格。

## 2. 当前问题

当前 `/admin` 已经是 React 工程，但还不是完整的 shadcn/Radix 体系：

| 问题 | 当前表现 | 影响 |
| --- | --- | --- |
| shadcn 项目底座不完整 | 没有 `components.json`，没有 `src/lib/utils.ts`，没有统一 `cn()` | 组件不能按官方调用方式稳定生成和维护 |
| Radix 只接了部分依赖 | 目前主要有 Dialog、Tabs、Tooltip | Select、Popover、Dropdown、Checkbox、Switch 等还没有统一来源 |
| UI 组件目录不统一 | `badge.tsx`、`combobox.tsx` 还在 `components/` 根部 | 后续页面会继续乱 import |
| 页面仍有旧 class | `primary-action`、`ghost-action`、`status-badge`、`panel` 等 | 新组件无法统一全站风格 |
| 业务组件层缺失 | 客户卡、销售单卡、商品卡、媒体卡没有固定组件 | 页面越做越大，未来维护困难 |

## 3. 官方依据

后续以 shadcn 官方文档和源码调用方式为准：

- Vite 安装：`https://ui.shadcn.com/docs/installation/vite`
- Sidebar：`https://ui.shadcn.com/docs/components/radix/sidebar`
- Button：`https://ui.shadcn.com/docs/components/radix/button`
- Card：`https://ui.shadcn.com/docs/components/radix/card`
- 其他组件按 `https://ui.shadcn.com/docs/components/radix/<component>` 查询

执行原则：

- 能用 shadcn CLI 添加的组件，优先用 CLI 或官方源码结构。
- 组件调用方式优先保持官方习惯，例如 `Button variant size`、`CardHeader/CardContent/CardFooter`、`SidebarProvider/SidebarInset`。
- 本项目只在 token、业务尺寸、黑白灰主题和业务组件层做定制。
- 不再把 shadcn 当视觉参考图，而是作为 `/admin` 的组件体系。

## 4. 目标技术栈

| 层 | 目标 |
| --- | --- |
| 框架 | React + TypeScript |
| 构建 | Vite |
| UI 底座 | shadcn/ui source components |
| 交互底层 | Radix primitives |
| 样式基础 | shadcn 兼容 CSS/Tailwind token + 北极星黑白灰业务 token |
| 工具函数 | `src/lib/utils.ts` 中统一 `cn()` |
| 图标 | lucide-react |
| 业务 API | 继续调用现有 `/admin/api` 与服务层，不影响 `/web` |

## 5. 目录目标

```text
admin/
  components.json
  src/
    lib/
      utils.ts
    components/
      ui/
        button.tsx
        badge.tsx
        card.tsx
        input.tsx
        field.tsx
        textarea.tsx
        select.tsx
        combobox.tsx
        checkbox.tsx
        switch.tsx
        table.tsx
        pagination.tsx
        dialog.tsx
        alert-dialog.tsx
        sheet.tsx
        tabs.tsx
        dropdown-menu.tsx
        tooltip.tsx
        popover.tsx
        calendar.tsx
        date-time-picker.tsx
        separator.tsx
        skeleton.tsx
        empty.tsx
        scroll-area.tsx
        sidebar.tsx
      layout/
        app-shell.tsx
        app-sidebar.tsx
        page-header.tsx
        toolbar.tsx
      business/
        customer-card.tsx
        sales-order-card.tsx
        product-card.tsx
        media-card.tsx
        inventory-table.tsx
        workflow-card.tsx
```

页面目录后续再分：

```text
admin/src/pages/
  sales-new.tsx
  sales-list.tsx
  customers.tsx
  products.tsx
  media-library.tsx
  inventory.tsx
  settings.tsx
  workflow.tsx
```

## 6. 第一阶段组件清单

第一阶段先做后台最常用组件，不做花架子：

| 类别 | 组件 |
| --- | --- |
| 基础 | Button、Badge、Card、Input、Field、Textarea、Separator |
| 表单 | Select、Combobox、Checkbox、Switch |
| 数据 | Table、Pagination |
| 弹层 | Dialog、AlertDialog、Sheet、Popover、DropdownMenu、Tooltip |
| 状态 | Skeleton、Empty |
| 布局 | Sidebar、PageHeader、Toolbar、AppShell、ScrollArea |
| 日期时间 | Calendar、DateTimePicker |

这些组件必须先接入至少一个真实页面，不能只创建空文件。

## 7. 业务组件清单

业务组件是为了防止页面继续变成大文件：

| 业务组件 | 用途 | 内部只能使用 |
| --- | --- | --- |
| CustomerCard | 客户列表、客户详情入口 | Card、Badge、Button |
| SalesOrderCard | 销售单列表、客户销售单 | Card、Badge、Button、DropdownMenu |
| ProductCard | 商品列表 | Card、Badge、Button |
| MediaCard | 图片资产 | Card、Badge、Button、Dialog |
| InventoryTable | 库存明细、日志 | Table、Pagination、Badge |
| WorkflowCard | 工作流订单 | Card、Badge、Button、Checkbox |

页面只能组合业务组件，不直接写复杂 DOM 和临时 CSS。

## 8. 开发阶段

### 阶段 0：冻结规则和验收

目标：防止继续补丁式开发。

交付：

- 新增或更新 UI 合同测试。
- 明确旧 class 禁用清单。
- 明确 `/web` smoke 验收。

验收：

- `tests/test_admin_*` 能检查基础结构。
- 迁移后的页面不再新增 `primary-action`、`ghost-action`、`status-badge`、`panel` 这类旧样式。

### 阶段 1：shadcn 项目底座

目标：让 `/admin` 成为真正可用 shadcn 组件工程。

交付：

- `admin/components.json`
- `admin/src/lib/utils.ts`
- 必要 Radix 依赖、class 合并依赖、图标依赖
- 路径别名 `@/`
- 全局 token 和基础 CSS 入口整理

验收：

- `npx shadcn@latest info --json` 能识别项目。
- `admin/src/components/ui/button.tsx` 等组件能按 `@/components/ui/button` import。
- `cd Z:\sjagent\admin && npm.cmd run build` 成功。

### 阶段 2：UI 基础组件包

目标：一次性补好后台常用组件底座。

交付：

- Button、Badge、Card、Input、Field、Textarea
- Select、Combobox、Checkbox、Switch
- Table、Pagination
- Dialog、AlertDialog、Sheet、DropdownMenu、Tooltip、Popover
- Separator、Skeleton、Empty、ScrollArea

验收：

- 每个组件有统一导出。
- 每个组件使用 shadcn/Radix 官方结构。
- 每个组件使用黑白灰 token，不引入旧绿色、大红、浅绿业务色。
- 新增 `tests/test_admin_shadcn_foundation_contract.py` 检查核心文件存在和 import 规则。

### 阶段 3：布局底座

目标：把 Sidebar 第一版纳入正式 AppShell。

交付：

- `AppShell`
- `AppSidebar`
- `PageHeader`
- `Toolbar`
- 主内容区宽度、间距、滚动规则

验收：

- `/admin` 首页、开单页共用 AppShell。
- Sidebar、Header、Toolbar 不在页面里重复写。
- 桌面和窄屏不横向撑爆。

### 阶段 4：开单页样板

目标：先把开单页做成新 UI 的标准样板。

交付：

- 开单基础信息区使用 Card、Field、Input、Combobox、Select。
- 开单时间使用 `DateTimePicker`，不得回退到原生 `datetime-local`。
- 销售明细使用 Table 或紧凑 Card 结构。
- 金额区使用 Card 和 Badge。
- 操作区使用 Button，不再使用旧按钮 class。

验收：

- `/admin/sales-new` 打开正常。
- 客户搜索、商品搜索、数量、提交开单功能不被破坏。
- `20套` 不被当成 `20件` 这类业务规则由后端继续保障。
- 浏览器截图确认风格接近 shadcn 后台，而不是旧 WebUI。

### 阶段 5：客户和销售单

目标：把最常用经营页面迁到业务组件。

交付：

- CustomerCard
- SalesOrderCard
- 客户详情销售单表格
- 删除确认走 AlertDialog
- 分页走 Pagination

验收：

- 客户余额、最近下单、近一年消费、结款入口都保留。
- 销售单打印、删除、详情弹窗不被破坏。
- 不再显示英文状态字段。

### 阶段 6：商品和图片资产

目标：解决商品、图片资产页面一致性和性能。

交付：

- ProductCard
- MediaCard
- 图片选择器 Dialog
- 商品编辑表单统一 Field/Select/Combobox
- 图片资产分页、分组、懒加载

验收：

- 商品列表显示颜色、件规、主图一致。
- 图片资产按 SPU 展示，不回到 SKU 重复主图。
- 图片选择器支持未绑定、本产品图片、全部图片。

### 阶段 7：设置、库存、工作流

目标：把复杂后台页面统一到组件体系。

交付：

- 设置页使用 Field、Switch、Checkbox、Tabs。
- 库存页使用 InventoryTable、Pagination、Badge。
- 工作流页使用 WorkflowCard。

验收：

- 固定业务规则不能被错误改动，例如泡袋不扣库存。
- 用户权限调整和用户列表对齐。
- 盘点、调拨、出入库、库存日志都有统一表格或卡片结构。

## 9. 禁止事项

后续 `/admin` 新代码禁止：

- 页面里新增 `.primary-action`、`.ghost-action`、`.status-badge`、`.panel`。
- 直接裸写原生 checkbox/switch。
- 日期、月份使用普通文本框。
- 删除操作不用 AlertDialog。
- 空列表自己写一段灰字，必须用 Empty。
- 加载状态空白等待，必须用 Skeleton 或明确状态。
- 页面里写大段临时 CSS。
- 为了赶进度绕过组件层。

## 10. 验收命令

每个阶段至少执行：

```powershell
cd Z:\sjagent\admin
npm.cmd run build
```

```powershell
python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract -v
```

涉及新合同测试时追加：

```powershell
python -m unittest tests.test_admin_shadcn_foundation_contract -v
```

浏览器验收：

- `/admin`
- 当前改动页面
- `/web`

## 11. 当前进度

### 2026-05-24 阶段 1 和第一批 UI 组件

已完成：

- `admin/components.json`
- `admin/src/lib/utils.ts`
- `@/` 路径别名
- `clsx`、`tailwind-merge`、`class-variance-authority`、`@radix-ui/react-slot`
- `Button`、`Badge`、`Card`、`Input`、`Field`、`Textarea`
- `Select`、`Combobox`、`Checkbox`、`Switch`
- `Calendar`、`DateTimePicker`
- `Table`、`Pagination`
- `Dialog`、`AlertDialog`、`Sheet`、`Popover`
- `Tabs`、`DropdownMenu`、`Tooltip`
- `Separator`、`Skeleton`、`Empty`、`ScrollArea`
- 侧边栏组件 `SidebarProvider/Sidebar/SidebarInset/...`
- 布局组件 `AppShell`、`AppSidebar`、`PageHeader`、`Toolbar`
- 开单页 `/admin/sales-new` 样板迁移
- 销售单列表页 `/admin/sales` 组件迁移
- 旧 `Badge` 兼容导出
- 旧 `Combobox` 兼容导出

已验证：

- `python -m unittest tests.test_admin_shadcn_foundation_contract -v`
- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `python -m unittest tests.test_admin_sales_new_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `python -m unittest tests.test_admin_sales_actions_contract tests.test_admin_sales_new_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- 浏览器 smoke：`/admin`、`/admin/sales-new`、`/admin/sales`、`/web` 正常。

阶段 3 布局层已完成。`App.tsx` 已改成只负责路由、页面选择和数据传递，sidebar/header 内部结构迁到 `components/layout`。

阶段 4 已完成第一张样板页：开单页。按钮、输入、卡片、字段、空状态、搜索区、弹窗已从 `components/ui` 与 `components/layout` 组合出来，业务调用链路保持不变。

阶段 5 已开始：销售单列表页完成迁移。销售单卡片、搜索、分页、详情弹窗、删除确认都已接入组件底座，打印/预览/删除服务层逻辑保持不变。

## 12. 当前下一步

从现在开始，下一步不是继续改某个页面，而是执行：

1. 迁移客户页：客户卡片、余额动作、月结切换、月份筛选、详情弹窗。
2. 商品、图片资产、库存、设置、工作流按业务风险顺序迁移。
3. 每迁一个页面都补契约测试、构建、浏览器 smoke，并确认旧 `/web` 不受影响。

只有这样，后面新增功能才会自然保持一致，而不是每次都重新讨论按钮、卡片、弹窗和页面风格。
