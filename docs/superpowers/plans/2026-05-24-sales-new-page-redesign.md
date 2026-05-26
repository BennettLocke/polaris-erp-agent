# Sales New Page Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `/admin/sales-new` into a shadcn/Radix-style page with focused business components, cleaner layout, explicit submit result actions, and clear service-layer boundaries.

**Architecture:** Keep API calls and business behavior in `SalesNewPage`, but move UI sections into `admin/src/components/business/sales-create/`. The page coordinates state; business components render customer selection, payment fields, product search, line table, summary, result card, customer creation dialog, and sales detail sheet.

**Tech Stack:** React, TypeScript, Vite, shadcn-compatible local components, Radix primitives, lucide-react, existing `/api/*` service-layer endpoints.

---

## Files

Create:

- `admin/src/components/business/sales-create/types.ts`
- `admin/src/components/business/sales-create/utils.ts`
- `admin/src/components/business/sales-create/sales-customer-field.tsx`
- `admin/src/components/business/sales-create/sales-payment-fields.tsx`
- `admin/src/components/business/sales-create/sales-product-search.tsx`
- `admin/src/components/business/sales-create/sales-line-table.tsx`
- `admin/src/components/business/sales-create/sales-summary-card.tsx`
- `admin/src/components/business/sales-create/sales-result-card.tsx`
- `admin/src/components/business/sales-create/create-customer-dialog.tsx`
- `admin/src/components/business/sales-create/sales-order-detail-sheet.tsx`
- `admin/src/components/business/sales-create/index.ts`
- `tests/test_admin_sales_new_redesign_contract.py`

Modify:

- `admin/src/App.tsx`
- `admin/src/styles.css`
- `tests/test_admin_sales_new_contract.py`
- `docs/react_admin_page_design_blueprint.md`

Do not modify:

- Old `/web` template or routes.
- Backend inventory or balance rules.

## Task 1: Add Sales-New Redesign Contract

- [x] **Step 1: Write the failing test**

Create `tests/test_admin_sales_new_redesign_contract.py` requiring the business component files and `SalesNewPage` imports.

- [x] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m unittest tests.test_admin_sales_new_redesign_contract -v
```

Expected: fails because the business component files do not exist yet.

## Task 2: Add Sales-Create Business Components

- [x] **Step 1: Create shared types and utilities**

Add `SalesFormLine`, money/date/customer/product helpers, and reusable props types.

- [x] **Step 2: Add customer and payment components**

Add `SalesCustomerField`, `SalesPaymentFields`, and `CreateCustomerDialog`.

- [x] **Step 3: Add product search and line table components**

Add `SalesProductSearch` and `SalesLineTable`, including non-stock warehouse display.

- [x] **Step 4: Add summary, result, and detail components**

Add `SalesSummaryCard`, `SalesResultCard`, and `SalesOrderDetailSheet`.

- [x] **Step 5: Export components**

Add `index.ts` exports for all sales-create components.

## Task 3: Refactor SalesNewPage

- [x] **Step 1: Import business components**

Update `admin/src/App.tsx` imports.

- [x] **Step 2: Replace inline JSX**

Keep state and API functions in `SalesNewPage`; replace large JSX blocks with business components.

- [x] **Step 3: Update clear and continue behavior**

Keep direct row delete. Add explicit result actions: print, preview, continue same customer, start new customer order.

- [x] **Step 4: Preserve service-layer boundaries**

Do not move stock, balance, or monthly settlement rules into frontend components.

## Task 4: Style the New Layout

- [x] **Step 1: Add layout CSS**

Add compact sales-create layout classes using existing black/white/gray tokens.

- [x] **Step 2: Add responsive behavior**

Use fixed-width summary on desktop and single-column layout on small screens.

## Task 5: Verify

- [x] **Step 1: Run contract tests**

Run:

```powershell
python -m unittest tests.test_admin_sales_new_redesign_contract tests.test_admin_sales_new_contract tests.test_admin_shadcn_foundation_contract -v
```

- [x] **Step 2: Run broader admin tests**

Run:

```powershell
python -m unittest tests.test_admin_sales_new_redesign_contract tests.test_admin_sales_new_contract tests.test_admin_sales_actions_contract tests.test_admin_sidebar_contract tests.test_admin_visual_tokens_contract tests.test_admin_shadcn_foundation_contract -v
```

- [x] **Step 3: Build admin**

Run:

```powershell
cd Z:\sjagent\admin
npm.cmd run build
```

- [x] **Step 4: Browser smoke**

Open:

```text
http://127.0.0.1:8081/admin/sales-new
http://127.0.0.1:8081/web
```

Confirm the admin page has no native `datetime-local`, still loads, and `/web` remains available.

## Completion Notes

- Implemented `admin/src/components/business/sales-create/*` and refactored `/admin/sales-new` to use those components.
- Fixed `DateTimePicker` mojibake and verified the custom Popover/Calendar/Select picker renders readable Chinese labels.
- Browser smoke covered monthly customer auto-switch, product search, adding one line, table display, enabled submit state, and console errors.
- Verified old `/web` was not modified by this step; admin build output was regenerated under `src/channels/http_api/admin_dist`.

## Follow-Up UI Fixes

- Product search now has only one result surface: the inline card grid below the search row. The input no longer opens a second Combobox dropdown.
- Variant buttons remain visible after a line is added and show `已加入` for selected SKUs.
- Product result cards no longer stretch single-variant buttons to match taller neighboring cards.
- The right summary card no longer inserts a separator between metric boxes and the disabled-state hint.
- Product search input, quantity input, and search button now share the same height and spacing.
- Customer search no longer opens an empty Combobox dropdown on focus/input; empty hint appears only after an explicit search returns no customers.
