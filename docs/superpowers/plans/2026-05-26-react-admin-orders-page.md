# React Admin Orders Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the React 后台“订单” page for `workflow_order` process orders while keeping old workflow APIs and entries compatible.

**Architecture:** Add a focused `components/business/orders` page that owns order UI state and calls API helpers from `admin/src/api.ts`. Keep backend route names as `/api/workflow/orders`, normalize raw workflow fields into process-order UI fields, and route both `/admin/orders` and `/admin/workflow` to the new page.

**Tech Stack:** React, TypeScript, Vite, local shadcn/Radix-compatible UI components, lucide-react, existing Flask workflow APIs.

---

### Task 1: Contract Test

**Files:**
- Create: `tests/test_admin_order_page_contract.py`

- [x] Write a failing contract test for the orders page route, API methods, types, components, and compatibility constraints.
- [x] Run the test and verify it fails because the orders page is not implemented yet.

### Task 2: Types And API

**Files:**
- Modify: `admin/src/types.ts`
- Modify: `admin/src/api.ts`

- [x] Add `ProcessOrder`, `ProcessOrderRaw`, `ProcessOrderListResult`, `ProcessOrderPayload`, and `ProcessOrderStatusPayload`.
- [x] Add `workflowOrders`, `saveWorkflowOrder`, `updateWorkflowOrderStatus`, and `deleteWorkflowOrder` API methods using the existing `/api/workflow/orders` endpoints and `filter` query parameter.

### Task 3: Orders Page

**Files:**
- Create: `admin/src/components/business/orders/orders-page.tsx`
- Create: `admin/src/components/business/orders/index.ts`

- [x] Implement data normalization, status grouping, search/filter tabs, summary strip, board view, table view, create/edit dialog, detail sheet, status updates, and delete confirmation.
- [x] Use existing local shadcn/Radix components only.

### Task 4: Routing And Navigation

**Files:**
- Modify: `admin/src/App.tsx`

- [x] Rename the nav item to “订单”.
- [x] Add `/admin/orders` as the main route and map legacy `/admin/workflow` to the same page.
- [x] Update dashboard wording from 工作流 to 订单 where user-visible.

### Task 5: Styling

**Files:**
- Modify: `admin/src/styles.css`

- [x] Add compact orders-page styles matching product, customer, and inventory density.

### Task 6: Verification

**Files:**
- Existing tests and build config.

- [ ] Run the new contract test.
- [ ] Run related admin contract tests.
- [ ] Run `npm.cmd run build` in `admin`.
- [ ] Open `/admin/orders` and inspect the page in browser automation.
