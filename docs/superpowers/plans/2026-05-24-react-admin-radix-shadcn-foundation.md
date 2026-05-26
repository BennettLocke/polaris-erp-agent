# React Admin Radix/shadcn Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real shadcn/Radix foundation for `/admin` before migrating more business pages.

**Architecture:** `/admin` becomes a Vite React TypeScript app with a shadcn-compatible component layer in `admin/src/components/ui`, layout components in `admin/src/components/layout`, and business components in `admin/src/components/business`. Pages must compose these components instead of writing temporary styles.

**Tech Stack:** React, TypeScript, Vite, shadcn/ui source components, Radix primitives, lucide-react, black/white/gray design tokens, existing Flask/admin APIs.

---

## Files

Create:

- `admin/components.json`
- `admin/src/lib/utils.ts`
- `admin/src/components/ui/button.tsx`
- `admin/src/components/ui/badge.tsx`
- `admin/src/components/ui/card.tsx`
- `admin/src/components/ui/input.tsx`
- `admin/src/components/ui/field.tsx`
- `admin/src/components/ui/textarea.tsx`
- `admin/src/components/layout/app-shell.tsx`
- `admin/src/components/layout/app-sidebar.tsx`
- `admin/src/components/layout/page-header.tsx`
- `admin/src/components/layout/toolbar.tsx`
- `tests/test_admin_shadcn_foundation_contract.py`

Modify:

- `admin/package.json`
- `admin/tsconfig.json`
- `admin/vite.config.ts`
- `admin/src/App.tsx`
- `admin/src/styles.css`
- `docs/react_admin_ui_component_plan.md`
- `docs/react_admin_ui_development_handbook.md`
- `docs/react_radix_admin_rearchitecture_plan.md`

Do not modify:

- `src/channels/http_api/webui_api.js` unless a smoke failure proves `/web` broke.
- `src/channels/http_api/webui_template.html` unless a smoke failure proves `/web` broke.

## Task 1: Add shadcn Project Contract

- [x] **Step 1: Write failing contract test**

Create `tests/test_admin_shadcn_foundation_contract.py` with checks for `components.json`, `src/lib/utils.ts`, UI component files, and forbidden legacy class additions in migrated pages.

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_admin_shadcn_foundation_contract -v
```

Expected: fail because `admin/components.json` and `admin/src/lib/utils.ts` do not exist yet.

- [x] **Step 3: Add shadcn config**

Create `admin/components.json` with aliases for `@/components`, `@/lib/utils`, and `@/components/ui`.

- [x] **Step 4: Add `cn()` utility**

Create `admin/src/lib/utils.ts` exporting `cn(...inputs)` using `clsx` and `tailwind-merge`.

- [x] **Step 5: Install required dependencies**

Run in `Z:\sjagent\admin`:

```powershell
npm.cmd install clsx tailwind-merge class-variance-authority @radix-ui/react-slot
```

Expected: `package.json` and `package-lock.json` update.

- [x] **Step 6: Configure path alias**

Update `admin/tsconfig.json` and `admin/vite.config.ts` so `@/` resolves to `admin/src`.

- [x] **Step 7: Run test and build**

Run:

```powershell
python -m unittest tests.test_admin_shadcn_foundation_contract -v
cd Z:\sjagent\admin
npm.cmd run build
```

Expected: contract passes and build succeeds.

## Task 2: Install Core UI Components

- [x] **Step 1: Write failing UI component contract**

Extend `tests/test_admin_shadcn_foundation_contract.py` to require:

```text
admin/src/components/ui/button.tsx
admin/src/components/ui/badge.tsx
admin/src/components/ui/card.tsx
admin/src/components/ui/input.tsx
admin/src/components/ui/field.tsx
admin/src/components/ui/textarea.tsx
```

The test must check that `Button` supports `variant` and `size`, `Card` exports `CardHeader/CardContent/CardFooter`, and `Field` exports `FieldGroup`.

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_admin_shadcn_foundation_contract -v
```

Expected: fail because the component files are missing.

- [x] **Step 3: Add components from shadcn style**

Add `button`, `badge`, `card`, `input`, `field`, and `textarea` under `admin/src/components/ui/`. Prefer official shadcn source structure and adapt only token names and compact sizing.

- [x] **Step 4: Remove old duplicate component locations**

Move old `admin/src/components/badge.tsx` into `admin/src/components/ui/badge.tsx`. Keep compatibility imports only if a page still imports the old path, and remove them once pages migrate.

- [x] **Step 5: Run tests and build**

Run:

```powershell
python -m unittest tests.test_admin_shadcn_foundation_contract tests.test_admin_visual_tokens_contract -v
cd Z:\sjagent\admin
npm.cmd run build
```

Expected: tests pass and build succeeds.

### Task 2 Progress Addendum

2026-05-24 已额外补齐第二批通用组件：

- `admin/src/components/ui/select.tsx`
- `admin/src/components/ui/combobox.tsx`
- `admin/src/components/ui/checkbox.tsx`
- `admin/src/components/ui/switch.tsx`
- `admin/src/components/ui/table.tsx`
- `admin/src/components/ui/pagination.tsx`
- `admin/src/components/ui/dialog.tsx`
- `admin/src/components/ui/alert-dialog.tsx`
- `admin/src/components/ui/sheet.tsx`
- `admin/src/components/ui/tabs.tsx`
- `admin/src/components/ui/dropdown-menu.tsx`
- `admin/src/components/ui/tooltip.tsx`
- `admin/src/components/ui/popover.tsx`
- `admin/src/components/ui/separator.tsx`
- `admin/src/components/ui/skeleton.tsx`
- `admin/src/components/ui/empty.tsx`
- `admin/src/components/ui/scroll-area.tsx`

Verified:

- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- Browser smoke for `/admin` and `/web`

## Task 3: Build Layout Components

- [x] **Step 1: Write failing layout contract**

Extend `tests/test_admin_sidebar_contract.py` or add a new assertion requiring `AppShell`, `AppSidebar`, `PageHeader`, and `Toolbar` imports from `admin/src/components/layout`.

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_admin_sidebar_contract -v
```

Expected: fail because layout components are not extracted yet.

- [x] **Step 3: Extract layout**

Move current shell/sidebar composition out of `App.tsx` into:

```text
admin/src/components/layout/app-shell.tsx
admin/src/components/layout/app-sidebar.tsx
admin/src/components/layout/page-header.tsx
admin/src/components/layout/toolbar.tsx
```

`App.tsx` should route and pass page content; it should not own sidebar internals.

- [x] **Step 4: Run tests and build**

Run:

```powershell
python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract -v
cd Z:\sjagent\admin
npm.cmd run build
```

Expected: tests pass and build succeeds.

### Task 3 Progress Addendum

2026-05-24 已完成布局层抽离：

- `admin/src/components/layout/app-shell.tsx`
- `admin/src/components/layout/app-sidebar.tsx`
- `admin/src/components/layout/page-header.tsx`
- `admin/src/components/layout/toolbar.tsx`

`App.tsx` 已改为通过 `AppShell`、`PageHeader` 组合页面内容，不再持有 sidebar 内部结构。

Verified:

- `python -m unittest tests.test_admin_sidebar_contract -v`
- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`

## Task 4: Migrate Sales-New as the Sample Page

- [x] **Step 1: Write page contract**

Update `tests/test_admin_sales_new_contract.py` to require:

```text
from "./components/ui/button"
from "./components/ui/card"
from "./components/ui/input"
from "./components/ui/field"
```

The test must reject new usage of `primary-action`, `ghost-action`, and raw `status-badge` in the sales-new page section.

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_admin_sales_new_contract -v
```

Expected: fail until the page uses the component layer.

- [x] **Step 3: Replace sales-new UI primitives**

In `admin/src/App.tsx` or extracted `admin/src/pages/sales-new.tsx`, replace buttons, inputs, cards, and field groups with UI components. Preserve API calls and business behavior.

- [x] **Step 4: Browser check**

Open:

```text
http://127.0.0.1:8081/admin/sales-new
```

Check: compact shadcn-like gray/white layout, no oversized legacy green buttons, customer/product search still usable.

- [x] **Step 5: Run build and smoke**

Run:

```powershell
python -m unittest tests.test_admin_sales_new_contract tests.test_admin_shadcn_foundation_contract -v
cd Z:\sjagent\admin
npm.cmd run build
```

Also smoke `/web` locally or through the existing Flask server route.

### Task 4 Progress Addendum

2026-05-24 已完成开单页样板迁移：

- `tests/test_admin_sales_new_contract.py` 已补组件层契约。
- `admin/src/App.tsx` 的 `SalesNewPage` 已使用 `Button/Card/Input/Field/Select/Combobox/Dialog/Empty/Toolbar`。
- 开单页业务函数和 API 调用保持不变：`selectCustomer`、`addSalesLine`、`submitSalesOrder` 仍走原服务层。
- 小屏 sidebar 自动收窄，避免开单表单被挤压。

Verified:

- `python -m unittest tests.test_admin_sales_new_contract -v`
- `python -m unittest tests.test_admin_sales_new_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- Browser smoke: `/admin/sales-new` 正常、旧 `/web` 正常、控制台无 error。

## Task 5: Document Progress

- [x] **Step 1: Update component plan**

Update `docs/react_admin_ui_component_plan.md` with:

- shadcn foundation status
- installed components
- migrated sample page
- remaining components

- [x] **Step 2: Update handbook**

Update `docs/react_admin_ui_development_handbook.md` with the new rule:

```text
No page migration is complete until it imports UI primitives from admin/src/components/ui and no longer adds legacy action/status/card classes.
```

- [x] **Step 3: Update rearchitecture plan**

Update `docs/react_radix_admin_rearchitecture_plan.md` to point to `docs/react_admin_radix_shadcn_foundation_plan.md`.

- [x] **Step 4: Final verification**

Run:

```powershell
python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract tests.test_admin_sales_new_contract -v
cd Z:\sjagent\admin
npm.cmd run build
```

Expected: all tests pass and build succeeds.

### Task 5 Progress Addendum

2026-05-24 已更新：

- `docs/react_admin_ui_component_plan.md`
- `docs/react_admin_ui_development_handbook.md`
- `docs/react_admin_radix_shadcn_foundation_plan.md`
- `docs/react_radix_admin_rearchitecture_plan.md`

Verified:

- `python -m unittest tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract tests.test_admin_sales_new_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- `git diff --check -- admin tests docs`

## Task 6: Migrate Sales List Page

- [x] **Step 1: Write sales page component contract**

Updated `tests/test_admin_sales_actions_contract.py` to require the sales list, detail dialog, delete confirmation, search and pagination to use the component layer.

- [x] **Step 2: Verify contract fails**

Ran:

```powershell
python -m unittest tests.test_admin_sales_actions_contract -v
```

Expected failure occurred because `/admin/sales` still used legacy `panel`、`ghost-action`、`status-badge` and raw Radix dialog markup.

- [x] **Step 3: Migrate sales UI primitives**

`admin/src/App.tsx` now uses:

- `Button`
- `Card`
- `Badge`
- `Input`
- `Pagination`
- `Dialog`
- `AlertDialog`
- `Empty`
- `Toolbar`

Preserved behavior:

- print task creation
- print preview
- sales delete via service-layer API
- inventory and balance rollback handled by backend service

- [x] **Step 4: Verify tests, build and browser smoke**

Verified:

- `python -m unittest tests.test_admin_sales_actions_contract -v`
- `python -m unittest tests.test_admin_sales_actions_contract tests.test_admin_sales_new_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v`
- `cd Z:\sjagent\admin && npm.cmd run build`
- Browser smoke: `/admin/sales` 正常加载销售单列表，旧 `/web` 正常，控制台无 error。

## Task 7: Fix Date Picker and Prepare Sales Card Redesign

- [x] **Step 1: Add failing date picker contract**

Updated `tests/test_admin_sales_new_contract.py` so `SalesNewPage` must import `DateTimePicker` and must not contain `datetime-local`.

- [x] **Step 2: Verify contract fails**

Ran:

```powershell
python -m unittest tests.test_admin_sales_new_contract -v
```

Expected failure occurred because the page still used native `Input type="datetime-local"`.

- [x] **Step 3: Add Calendar and DateTimePicker components**

Added:

- `admin/src/components/ui/calendar.tsx`
- `admin/src/components/ui/date-time-picker.tsx`

The date-time picker composes `Calendar + Popover + Select + Button`, following the shadcn Calendar/Date Picker pattern instead of the browser native picker.

- [x] **Step 4: Replace sales-new open time field**

`/admin/sales-new` now uses `<DateTimePicker value={createTime} onChange={setCreateTime} />`.

- [x] **Step 5: Verify tests, build and browser behavior**

Verified:

```powershell
python -m unittest tests.test_admin_sales_new_contract tests.test_admin_shadcn_foundation_contract tests.test_admin_sales_actions_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract -v
cd Z:\sjagent\admin
npm.cmd run build
```

Browser smoke:

- `/admin/sales-new` has no `input[type="datetime-local"]`.
- Clicking open time shows `date-time-picker-content`.
- Calendar and hour/minute Select controls render.

- [ ] **Step 6: SalesOrderCard visual redesign plan**

Before changing `/admin/sales` again, compare shadcn official examples for Card, Badge, Dropdown Menu, Sheet, Table and Alert Dialog. The next implementation should:

- Use one outer `Card` per order.
- Remove big nested item cards inside the sales card.
- Move full bill lines to `Sheet + Table`.
- Keep card content compact: customer, order number, status badges, 2-3 preview lines, total, payment, opener and time.
- Move actions to `CardFooter` and `DropdownMenu`; delete remains `AlertDialog`.
- Add a browser screenshot comparison before calling it done.

## Execution Notes

- Keep `/web` untouched and smoke it after UI work.
- Do not migrate customers/products/settings until sales-new proves the foundation.
- Do not create page-specific button/card/badge styles.
- If a shadcn component exists, use it before writing custom markup.
- If a business UI pattern repeats twice, extract a business component before the third copy.
