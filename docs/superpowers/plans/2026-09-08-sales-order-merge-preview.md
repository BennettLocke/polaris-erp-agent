# Sales Order Merge Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only workflow that selects one customer's valid sales orders from the base order's seven-day window, renders all original lines in one continuous preview, and supports printing and PNG download.

**Architecture:** A new read-only sales service method returns the complete candidate set in one query flow and enforces customer/date/status boundaries. The React sales detail opens a selection dialog, then a dedicated authenticated preview route reloads the same candidate payload and filters it by selected order IDs; no merged record is persisted. `html-to-image` captures only the document surface for a clear long PNG, while print CSS hides all controls.

**Tech Stack:** Python/Flask, `NativeDBClient`, React 19, TypeScript, Radix Dialog/Checkbox, TanStack Query, `html-to-image`, unittest, Vite.

---

### Task 1: Lock the read-only merge contract

**Files:**
- Create: `tests/test_sales_merge_preview_contract.py`
- Modify: `src/services/business/sales.py`
- Modify: `src/channels/http_api/__init__.py`

- [ ] **Step 1: Write failing service and route tests**

Add tests that require `SalesService.merge_candidates(sales_id)` to delegate to `db.sales_merge_candidates`, require `GET /api/sales/<int:sales_id>/merge-candidates`, and require the route permission to be `打印`.

```python
def test_sales_service_delegates_merge_candidates(self):
    result = SalesService(self.db).merge_candidates(12)
    self.assertEqual(result, self.db.sales_merge_candidates.return_value)
    self.db.sales_merge_candidates.assert_called_once_with(12)

def test_merge_candidate_route_is_read_only_and_print_scoped(self):
    source = Path("src/channels/http_api/__init__.py").read_text(encoding="utf-8")
    self.assertIn('@app.route("/api/sales/<int:sales_id>/merge-candidates", methods=["GET"])', source)
    self.assertRegex(source, r'\{\"GET\"\}.*merge-candidates.*\"打印\"')
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m unittest tests.test_sales_merge_preview_contract`

Expected: failures for the missing service method and route.

- [ ] **Step 3: Add the service boundary and route**

Add the service delegate:

```python
def merge_candidates(self, sales_id: int) -> dict:
    return self.db.sales_merge_candidates(sales_id)
```

Add a GET route that validates a positive ID, calls the service, maps `DBError` through `_api_exception_response`, and never accepts customer/date overrides. Add the matching permission regex beside the existing sales print routes.

- [ ] **Step 4: Re-run the contract tests**

Run: `python -m unittest tests.test_sales_merge_preview_contract`

Expected: route/service assertions pass; the database behavior test remains pending until Task 2.

- [ ] **Step 5: Commit the boundary**

```bash
git add tests/test_sales_merge_preview_contract.py src/services/business/sales.py src/channels/http_api/__init__.py
git commit -m "feat: add sales merge candidate endpoint"
```

### Task 2: Implement candidate selection and validation in the database layer

**Files:**
- Modify: `src/engine/native_db.py`
- Modify: `tests/test_sales_merge_preview_contract.py`

- [ ] **Step 1: Add failing behavior tests**

Use a mocked `NativeDBClient.query` to verify:

```python
def test_merge_candidates_uses_base_order_customer_and_date(self):
    result = self.client.sales_merge_candidates(10)
    data = result["data"]
    self.assertEqual(data["base_sales_id"], 10)
    self.assertEqual(data["customer"]["id"], 3)
    self.assertEqual(data["date_from"], "2026-09-01")
    self.assertEqual(data["date_to"], "2026-09-07")
    self.assertEqual([row["id"] for row in data["orders"]], [10, 9])

def test_merge_candidates_preserves_duplicate_product_lines(self):
    items = self.client.sales_merge_candidates(10)["data"]["orders"][0]["items"]
    self.assertEqual(len(items), 2)
    self.assertEqual(items[0]["title"], items[1]["title"])

def test_merge_candidates_rejects_deleted_base_order(self):
    with self.assertRaisesRegex(DBError, "已删除或已取消"):
        self.client.sales_merge_candidates(10)
```

Also cover missing customer and more than 200 orders.

- [ ] **Step 2: Run the focused behavior tests**

Run: `python -m unittest tests.test_sales_merge_preview_contract`

Expected: failures because `NativeDBClient.sales_merge_candidates` is missing.

- [ ] **Step 3: Implement `sales_merge_candidates`**

The method must:

1. Read the base order and reject missing, canceled, deleted, or customerless orders.
2. Derive `date_to = DATE(base.sales_at)` and `date_from = date_to - 6 days` inside SQL/Python without accepting request overrides.
3. Count active orders for the same `customer_id` and inclusive date range; raise `DBError("7天内销售单超过200张，暂不能合并预览")` above 200.
4. Query all candidate orders ordered by `sales_at ASC, id ASC` and all `sales_order_item` rows ordered by order/date and `line_no ASC`.
5. Return customer snapshot/contact fields, date range, base ID, and each order's payment/status/totals/note plus an unmodified `items` list containing `item_id`, `title`, `color`, `quantity`, `unit_price`, and `amount`.

Return shape:

```python
{
    "code": 0,
    "data": {
        "base_sales_id": 10,
        "customer": {"id": 3, "name": "齐唯茶业", "phone": "", "address": ""},
        "date_from": "2026-09-01",
        "date_to": "2026-09-07",
        "orders": [{
            "id": 10,
            "sales_no": "SO...",
            "sales_at": "2026-09-07 10:00:00",
            "pay_status_text": "月结",
            "pay_type_text": "月结",
            "total_quantity": "5",
            "goods_amount": "100.00",
            "discount_amount": "0.00",
            "receivable_amount": "100.00",
            "note": "",
            "items": [],
        }],
    },
}
```

- [ ] **Step 4: Run backend regression tests**

Run: `python -m unittest tests.test_sales_merge_preview_contract tests.test_native_db_client tests.test_business_services`

Expected: all tests pass.

- [ ] **Step 5: Commit database behavior**

```bash
git add src/engine/native_db.py tests/test_sales_merge_preview_contract.py
git commit -m "feat: return seven day sales merge candidates"
```

### Task 3: Add frontend types, API, and selection dialog

**Files:**
- Modify: `admin/src/types.ts`
- Modify: `admin/src/api.ts`
- Modify: `admin/src/components/business/sales-list/types.ts`
- Create: `admin/src/components/business/sales-list/sales-merge-dialog.tsx`
- Modify: `admin/src/components/business/sales-list/sales-order-detail-dialog.tsx`
- Modify: `admin/src/components/business/sales-list/index.ts`
- Modify: `admin/src/App.tsx`
- Modify: `admin/src/styles.css`
- Modify: `tests/test_admin_sales_actions_contract.py`

- [ ] **Step 1: Write failing frontend contract assertions**

Require the sales detail action label, candidate endpoint, checked base order, all-select action, selected totals, and preview URL construction.

```python
self.assertIn("合并预览", detail_source)
self.assertIn("merge-candidates", api_source)
self.assertIn("base_sales_id", merge_dialog_source)
self.assertIn("生成合并预览", merge_dialog_source)
self.assertIn("sales-merge-preview", app_source)
```

- [ ] **Step 2: Run the frontend contract test**

Run: `python -m unittest tests.test_admin_sales_actions_contract`

Expected: new assertions fail.

- [ ] **Step 3: Add the data types and API call**

Define `SalesMergeItem`, `SalesMergeOrder`, and `SalesMergeCandidates`, then add:

```ts
salesMergeCandidates: (id: number, options?: ApiRequestOptions) =>
  request<SalesMergeCandidates>(
    `/api/sales/${id}/merge-candidates`,
    withRequestOptions(undefined, options)
  )
```

- [ ] **Step 4: Build the centered selection dialog**

`SalesMergeDialog` receives `open`, `loading`, candidate data, and callbacks. It initializes selection to `base_sales_id`, uses square `Checkbox` controls, supports per-row selection and current-page all/none, disables generation when empty, and computes totals from selected orders using decimal-safe numeric conversion.

Each row displays date, order number, payment, product summary, quantity, and amount. The footer displays `已选 X 单 / X 件 / ¥X` and actions `取消` and `生成合并预览`.

- [ ] **Step 5: Wire the detail action and data flow**

Add `onMergePreview` to the sales detail action props and place the button beside existing print actions. In `SalesPage`, fetch candidates with query key `queryKeys.sales.mergeCandidates(id)`, open the dialog, and generate:

```ts
const params = new URLSearchParams({
  base: String(data.base_sales_id),
  ids: selectedIds.join(",")
});
window.open(`/admin/sales-merge-preview?${params}`, "_blank", "noopener");
```

The same action remains unavailable for canceled/deleted preview cards.

- [ ] **Step 6: Run contract tests and TypeScript build**

Run: `python -m unittest tests.test_admin_sales_actions_contract`

Run: `cd admin && npm run build`

Expected: tests and build pass.

- [ ] **Step 7: Commit selection UI**

```bash
git add admin/src tests/test_admin_sales_actions_contract.py src/channels/http_api/admin_dist
git commit -m "feat: add sales merge selection dialog"
```

### Task 4: Build the dedicated preview, print, and PNG download

**Files:**
- Modify: `admin/package.json`
- Modify: `admin/package-lock.json`
- Create: `admin/src/components/business/sales-list/sales-merge-preview-page.tsx`
- Modify: `admin/src/components/business/sales-list/index.ts`
- Modify: `admin/src/App.tsx`
- Modify: `admin/src/styles.css`
- Modify: `tests/test_admin_sales_actions_contract.py`

- [ ] **Step 1: Add failing preview assertions**

Require a continuous table with source date/order columns, unchanged item iteration, payment summary logic, `toPng`, and print action.

```python
self.assertIn("原单号", preview_source)
self.assertIn("包含多种付款方式", preview_source)
self.assertIn("toPng", preview_source)
self.assertIn("window.print()", preview_source)
self.assertNotIn("reduceMergedItems", preview_source)
```

- [ ] **Step 2: Install the DOM capture dependency**

Run: `cd admin && npm install html-to-image`

Expected: `package.json` and lockfile include `html-to-image`.

- [ ] **Step 3: Implement the authenticated preview route**

Extend `RouteKey` with `sales-merge-preview`. Parse `base` and `ids`, fetch the candidate endpoint with `staleTime: 0` to revalidate statuses, reject IDs absent from the returned candidate set, and render the preview without the normal sidebar/navigation shell.

The document must:

- flatten selected orders with `flatMap(order => order.items.map(...))`, never group equal products;
- show columns `# / 日期 / 原单号 / 商品 / 颜色/规格 / 数量 / 单价 / 金额`;
- show the concrete shared payment text when all selected orders match, otherwise `包含多种付款方式`;
- show separate source-labeled notes only when non-empty;
- sum selected order `total_quantity` and `receivable_amount` for the footer;
- keep black text, white background, and solid black table borders.

- [ ] **Step 4: Add long PNG download**

Capture only the document ref:

```ts
const dataUrl = await toPng(documentRef.current, {
  cacheBust: true,
  pixelRatio: 2,
  backgroundColor: "#ffffff",
  width: 1200,
  style: { width: "1200px", maxWidth: "1200px" }
});
```

Download as `<客户>_<开始日期>-<结束日期>_销售单合并.png`. Disable the button while rendering and surface a retryable error without closing the page.

- [ ] **Step 5: Add print layout and responsive behavior**

Use `@page { size: A5 landscape; margin: 6mm; }`, repeat `<thead>` naturally on page breaks, hide `.sales-merge-preview-actions` in print, and prevent table rows from splitting where supported. At narrow screen widths keep the document horizontally inspectable without shrinking text below readable size.

- [ ] **Step 6: Run frontend tests and build**

Run: `python -m unittest tests.test_admin_sales_actions_contract`

Run: `cd admin && npm run build`

Expected: tests pass and Vite emits production assets.

- [ ] **Step 7: Commit preview functionality**

```bash
git add admin/package.json admin/package-lock.json admin/src tests/test_admin_sales_actions_contract.py src/channels/http_api/admin_dist
git commit -m "feat: add printable sales merge preview"
```

### Task 5: End-to-end verification and deployment readiness

**Files:**
- Modify only if verification reveals defects in files already listed above.

- [ ] **Step 1: Run the focused regression suite**

Run:

```bash
python -m unittest \
  tests.test_sales_merge_preview_contract \
  tests.test_admin_sales_actions_contract \
  tests.test_native_db_client \
  tests.test_business_services
```

Expected: all tests pass.

- [ ] **Step 2: Run compile and production checks**

Run: `python -m compileall -q src tests/test_sales_merge_preview_contract.py`

Run: `cd admin && npm run build`

Run: `git diff --check`

Expected: all commands exit successfully; only the existing Vite chunk-size warning may remain.

- [ ] **Step 3: Browser acceptance check**

Verify at desktop and narrow widths:

1. Open a normal sale, launch merge preview, and confirm only same-customer orders from the inclusive seven-day range appear.
2. Confirm the base order is selected and all/none controls work.
3. Select two orders containing duplicate product/color lines and confirm every original row remains separate.
4. Confirm same/mixed payment summaries, totals, notes, and invalid-order revalidation.
5. Download the PNG and inspect full height, black text, sharp borders, filename, and absence of controls.
6. Print preview and confirm A5 landscape pagination, repeated headers, and no action bar.

- [ ] **Step 4: Confirm no business writes**

Compare sales order count, inventory ledger count, balance ledger count, customer price memory count, and print job count before and after candidate selection, preview, PNG download, and browser printing. All counts must remain unchanged.

- [ ] **Step 5: Create final focused commit if verification required fixes**

```bash
git add <only-files-touched-by-verification>
git commit -m "fix: harden sales merge preview"
```

