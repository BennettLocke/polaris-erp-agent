// Run against local Vite only; every API request is intercepted.
const assert = require("node:assert/strict");
const { before, after, test } = require("node:test");
const { chromium } = require("playwright");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const base = process.env.SALES_PURCHASE_RESULT_TEST_URL || "http://127.0.0.1:5183/admin/sales-new";
const key = "polaris:sales-draft:v1:7";
const customer = { id: 3, name: "齐唯茶业", is_monthly_customer: 1 };
const rows = [
  { product_id: 1046, spu_id: 100, unit_id: 1, unit_name: "套", title: "【喜悦】半斤", spec: "红色", coding: "SJ1046", buy_number: 48, price: 20, warehouse_id: 1, price_source: "manual_override", is_stock_item: 1, purchase_policy: "one_case", case_pack_qty: 48 },
  { product_id: 1047, spu_id: 101, unit_id: 2, unit_name: "捆", title: "【墨香】一斤", spec: "蓝色", coding: "SJ1047", buy_number: 6, price: 20, warehouse_id: 2, price_source: "manual_override", is_stock_item: 1, purchase_policy: "order_qty" }
];
let browser;
before(async () => { browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }); });
after(async () => { await browser?.close(); });

async function fixture({ lines = rows, available = 0, clipboardFails = false, balanceUnitMissing = false } = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, serviceWorkers: "block" });
  const state = { purchases: [], sales: [], inventory: [], balances: new Map(), available, purchaseOutcomes: [], saleOutcome: "success", purchaseGate: null, saleGate: null, purchaseCompleted: 0, salesCompleted: 0, loggedOut: false, unexpectedWrites: [] };
  const errors = [];
  context.on("page", (page) => page.on("pageerror", (error) => errors.push(error.message)));
  await context.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) {
      if (url.origin === new URL(base).origin) return route.continue();
      return route.abort();
    }
    let data = { list: [], total: 0, page: 1, page_size: 20 };
    let status = 200;
    let msg;
    if (url.pathname === "/api/web-auth/me") {
      data = { user: { id: 7, username: "purchase-result-test", display_name: "测试账号", role: "admin", role_text: "管理员", permissions: [], is_admin: 1, is_active: 1, approval_status: "approved" } };
    } else if (url.pathname === "/api/web-auth/logout") {
      state.loggedOut = true;
      data = {};
    } else if (url.pathname === "/api/warehouses") {
      data = { list: [{ id: 1, name: "自己店里" }, { id: 2, name: "百鑫仓库", is_default_sales: 1 }] };
    } else if (url.pathname === "/api/customer/list") {
      data = [customer];
    } else if (url.pathname === "/api/product/options") {
      data = { unit_list: [{ id: 1, name: "套" }, { id: 2, name: "捆" }] };
    } else if (url.pathname === "/api/inventory/balances") {
      const productId = Number(url.searchParams.get("sku_id"));
      const warehouseId = Number(url.searchParams.get("warehouse_id"));
      const balanceKey = `${productId}:${warehouseId}`;
      state.inventory.push(balanceKey);
      data = { list: [{ product_id: productId, warehouse_id: warehouseId, quantity: state.balances.get(balanceKey) ?? state.available, unit_name: balanceUnitMissing ? undefined : lines.find((line) => line.product_id === productId)?.unit_name || "套" }], total: 1 };
    } else if (url.pathname === "/api/inventory/purchase") {
      const payload = request.postDataJSON();
      state.purchases.push(payload);
      const outcome = state.purchaseOutcomes.shift() || "success";
      if (state.purchaseGate) await state.purchaseGate;
      if (outcome === "abort") {
        await route.abort("failed");
        state.purchaseCompleted++;
        return;
      }
      const balanceKey = `${payload.product_id}:${payload.warehouse_id}`;
      if (outcome === "400" || outcome === "500") {
        status = Number(outcome);
        msg = "测试：第二项进货失败";
      } else {
        state.balances.set(balanceKey, (state.balances.get(balanceKey) ?? state.available) + Number(payload.quantity));
        data = outcome === "no_receipt" ? {} : { id: 888 + state.purchases.length };
      }
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ code: status === 200 ? 0 : status, data, msg }) });
      state.purchaseCompleted++;
      return;
    } else if (url.pathname === "/api/sales/add") {
      state.sales.push(request.postDataJSON());
      if (state.saleGate) await state.saleGate;
      if (state.saleOutcome === "abort") {
        await route.abort("failed");
        state.salesCompleted++;
        return;
      }
      if (state.saleOutcome === "400") {
        status = 400;
        msg = "测试：销售单创建失败";
      }
      data = { id: 999, sales_id: 999, sales_no: "SO-PURCHASE-TEST" };
      await route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ code: status === 200 ? 0 : status, data, msg }) });
      state.salesCompleted++;
      return;
    } else if (!["GET", "HEAD"].includes(request.method())) {
      state.unexpectedWrites.push(`${request.method()} ${url.pathname}`);
    }
    return route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ code: status === 200 ? 0 : status, data, msg }) });
  });
  const page = await context.newPage();
  page.setDefaultTimeout(4000);
  await page.addInitScript(({ key, customer, lines, clipboardFails }) => {
    window.__copiedText = [];
    Object.defineProperty(window.navigator, "clipboard", { configurable: true, value: { async writeText(value) {
      if (clipboardFails) throw new Error("Clipboard denied for regression test");
      window.__copiedText.push(value);
    } } });
    if (clipboardFails) document.execCommand = () => false;
    if (location.origin === "null" || sessionStorage.getItem("purchase-result-seeded")) return;
    sessionStorage.setItem(key, JSON.stringify({ version: 1, accountId: 7, draft: { selectedCustomer: customer, customerKeyword: customer.name, productKeyword: "", lines, defaultWarehouseId: 1, lineQty: 1, createTime: "2026-10-28T10:00", payStatus: "paid", payType: "cash" } }));
    sessionStorage.setItem("purchase-result-seeded", "yes");
  }, { key, customer, lines, clipboardFails });
  await page.goto(base);
  await page.locator(".sales-create-line-table tbody tr").nth(lines.length - 1).waitFor();
  return { context, page, state, async close() { await context.close(); assert.deepEqual(errors, []); assert.deepEqual(state.unexpectedWrites, []); } };
}

const resultDialog = (page) => page.getByRole("dialog", { name: "进货结果", exact: true });
const lineTable = (page) => page.locator(".sales-create-line-table tbody tr");
const saved = (page) => page.evaluate((key) => JSON.parse(sessionStorage.getItem(key)), key);
const copied = (page) => page.evaluate(() => window.__copiedText);
const closeResult = (page) => resultDialog(page).getByRole("button", { name: "关闭", exact: true }).click();
const productName = (line) => line.title.replace(/[【】\s]/g, "");

function deferred() {
  let release;
  const promise = new Promise((resolve) => { release = resolve; });
  return { promise, release };
}

async function eventually(predicate, message) {
  const deadline = Date.now() + 4000;
  while (Date.now() < deadline) {
    if (await predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  assert.fail(message);
}

async function rendered(page) {
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function assertDraftPreserved(page, lines = rows) {
  assert.deepEqual((await saved(page)).draft.lines, lines);
  assert.equal(await lineTable(page).count(), lines.length);
}

async function confirmShortage(page) {
  await page.getByRole("button", { name: "提交开单", exact: true }).click();
  const confirmation = page.getByRole("alertdialog");
  await confirmation.waitFor();
  await confirmation.getByRole("button", { name: "先进货并开单", exact: true }).click();
}

test("successful purchases automatically open the purchase result dialog after creating the sale", async () => {
  const f = await fixture();
  try {
    await confirmShortage(f.page);
    const dialog = resultDialog(f.page);
    await dialog.waitFor();
    assert.equal(f.state.purchases.length, 2);
    assert.equal(f.state.sales.length, 1);
    assert.match(await dialog.innerText(), /销售单已创建|开单成功/);
    const blocks = dialog.getByRole("region", { name: "已确认入库", exact: true }).locator(".sales-purchase-result-item");
    assert.equal(await blocks.count(), rows.length);
    for (const line of rows) {
      const block = blocks.filter({ hasText: productName(line) });
      assert.equal(await block.count(), 1);
      assert.ok((await block.innerText()).includes(line.spec));
    }
    assert.match(await blocks.first().innerText(), /1\s*件/);
    assert.doesNotMatch(await blocks.first().innerText(), /48\s*(套|包)|1\s*包/);
    assert.match(await blocks.nth(1).innerText(), /6\s*捆/);
    const copy = dialog.getByRole("button", { name: /^(复制进货信息|已复制)$/ });
    const close = dialog.getByRole("button", { name: "关闭", exact: true });
    const copyBox = await copy.boundingBox();
    const closeBox = await close.boundingBox();
    assert.ok(copyBox && closeBox && Math.abs(copyBox.y - closeBox.y) < 8, "copy and close buttons share a footer row");
    await copy.click();
    await eventually(async () => (await copied(f.page)).length === 1, "clipboard receives purchase text");
    const text = (await copied(f.page))[0];
    for (const line of rows) assert.ok(text.includes(productName(line)), `copy contains ${line.title}`);
    assert.match(text, /1\s*件/);
    assert.doesNotMatch(text, /48\s*(套|包)|1\s*包/);
    assert.match(text, /6\s*捆/);
    assert.match(text, /送至自己店里/);
    assert.match(text, /送至百鑫/);
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "sales-purchase-result-"));
    for (const width of [1280, 390]) {
      await f.page.setViewportSize({ width, height: 900 });
      await rendered(f.page);
      const box = await dialog.boundingBox();
      assert.ok(box && box.x >= 0 && box.x + box.width <= width + 1, `dialog fits ${width}px viewport`);
      assert.equal(await copy.isVisible(), true);
      assert.equal(await close.isVisible(), true);
      const screenshot = path.join(dir, `result-${width}.png`);
      await f.page.screenshot({ path: screenshot, fullPage: true });
      console.log(`Screenshot: ${screenshot}`);
    }
    await close.click();
    await dialog.waitFor({ state: "hidden" });
    await f.page.getByRole("button", { name: "查看进货信息", exact: true }).click();
    await dialog.waitFor();
    assert.equal(f.state.purchases.length, 2);
    assert.equal(f.state.sales.length, 1);
    assert.equal(await saved(f.page), null);
  } finally { await f.close(); }
});

test("normal sales create no purchase result dialog or reopen button", async () => {
  const f = await fixture({ available: 1000 });
  try {
    await f.page.getByRole("button", { name: "提交开单", exact: true }).click();
    await f.page.getByText(/开单成功/).first().waitFor();
    assert.equal(f.state.sales.length, 1);
    assert.equal(f.state.purchases.length, 0);
    assert.equal(await resultDialog(f.page).count(), 0);
    assert.equal(await f.page.getByRole("button", { name: "查看进货信息", exact: true }).count(), 0);
  } finally { await f.close(); }
});

test("cancelling the shortage confirmation preserves the draft without purchases or sales", async () => {
  const f = await fixture();
  try {
    await f.page.getByRole("button", { name: "提交开单", exact: true }).click();
    const confirmation = f.page.getByRole("alertdialog");
    await confirmation.waitFor();
    assert.equal(f.state.purchases.length, 0);
    await confirmation.getByRole("button", { name: "取消", exact: true }).click();
    await confirmation.waitFor({ state: "hidden" });
    await assertDraftPreserved(f.page);
    assert.equal(f.state.purchases.length, 0);
    assert.equal(f.state.sales.length, 0);
    assert.equal(await resultDialog(f.page).count(), 0);
  } finally { await f.close(); }
});

test("order_qty purchases display actual units rather than case packaging", async () => {
  const lines = [{ ...rows[0], purchase_policy: "order_qty", unit_name: "个", buy_number: 5, case_pack_qty: 48 }];
  const f = await fixture({ lines });
  try {
    await confirmShortage(f.page);
    const dialog = resultDialog(f.page);
    await dialog.waitFor();
    assert.equal(f.state.purchases[0].quantity, 5);
    assert.match(await dialog.innerText(), /5\s*个/);
    await dialog.getByRole("button", { name: "复制进货信息", exact: true }).click();
    await eventually(async () => (await copied(f.page)).length === 1, "copy completes");
    assert.match((await copied(f.page))[0], /5\s*个/);
    assert.doesNotMatch((await copied(f.page))[0], /件|包/);
  } finally { await f.close(); }
});

test("old drafts without unit names resolve the actual unit from product metadata", async () => {
  const lines = [{ ...rows[1], unit_name: undefined }];
  const f = await fixture({ lines, balanceUnitMissing: true });
  try {
    await confirmShortage(f.page);
    const dialog = resultDialog(f.page);
    await dialog.waitFor();
    assert.match(await dialog.innerText(), /6\s*捆/);
    assert.equal(f.state.purchases[0].unit_id, 2);
  } finally { await f.close(); }
});

for (const outcome of ["500", "no_receipt"]) test(`${outcome} purchase outcome cannot become a successful receipt or trigger a sale`, async () => {
  const f = await fixture();
  f.state.purchaseOutcomes = [outcome];
  try {
    await confirmShortage(f.page);
    const dialog = resultDialog(f.page);
    await dialog.waitFor();
    assert.match(await dialog.innerText(), /待核对|待核实/);
    assert.equal(await dialog.getByRole("button", { name: "复制进货信息", exact: true }).count(), 0);
    assert.equal(f.state.sales.length, 0);
    assert.equal(f.state.purchases.length, 1);
    await closeResult(f.page);
    assert.equal(await f.page.getByRole("button", { name: "提交开单", exact: true }).isDisabled(), true);
  } finally { await f.close(); }
});

test("a second purchase 400 shows partial success and retry rechecks stock without repurchasing the first", async () => {
  const lines = [...rows, { ...rows[1], product_id: 1048, title: "【清雅】二两", spec: "绿色" }];
  const f = await fixture({ lines });
  f.state.purchaseOutcomes = ["success", "400"];
  try {
    await confirmShortage(f.page);
    const dialog = resultDialog(f.page);
    await dialog.waitFor();
    const text = await dialog.innerText();
    assert.ok(text.includes(productName(rows[0])));
    assert.ok(text.includes(rows[1].title));
    assert.match(text, /测试：第二项进货失败/);
    assert.match(text, /尚?未处理\s*[:：]?\s*1|1\s*(项|个|种).*未处理/);
    assert.match(text, /未创建|未开单/);
    assert.equal(f.state.sales.length, 0);
    assert.equal(f.state.purchases.length, 2);
    assert.equal(await f.page.getByRole("alertdialog").count(), 0);
    await dialog.getByRole("button", { name: "复制进货信息", exact: true }).click();
    await eventually(async () => (await copied(f.page)).length === 1, "partial success can be copied");
    const purchaseText = (await copied(f.page))[0];
    assert.ok(purchaseText.includes(productName(rows[0])));
    assert.ok(!purchaseText.includes(productName(rows[1])));
    assert.ok(!purchaseText.includes(productName(lines[2])));
    await closeResult(f.page);
    await assertDraftPreserved(f.page, lines);
    const checksBeforeRetry = f.state.inventory.length;
    await confirmShortage(f.page);
    await resultDialog(f.page).waitFor();
    assert.equal(f.state.sales.length, 1);
    assert.ok(f.state.inventory.length >= checksBeforeRetry + lines.length, "retry rechecks all inventory balances");
    assert.equal(f.state.purchases.filter((item) => item.product_id === 1046).length, 1);
    assert.deepEqual(f.state.purchases.map((item) => item.product_id), [1046, 1047, 1047, 1048]);
  } finally { await f.close(); }
});

test("a sales 400 preserves the draft and retry creates the sale without repeating purchases", async () => {
  const f = await fixture();
  f.state.saleOutcome = "400";
  try {
    await confirmShortage(f.page);
    const dialog = resultDialog(f.page);
    await dialog.waitFor();
    assert.match(await dialog.innerText(), /测试：销售单创建失败/);
    assert.match(await dialog.innerText(), /销售单.*失败|开单失败/);
    assert.equal(f.state.purchases.length, 2);
    assert.equal(f.state.sales.length, 1);
    assert.equal(await f.page.getByRole("alertdialog").count(), 0);
    await closeResult(f.page);
    await assertDraftPreserved(f.page);
    f.state.saleOutcome = "success";
    const checksBeforeRetry = f.state.inventory.length;
    await f.page.getByRole("button", { name: "提交开单", exact: true }).click();
    await f.page.getByText(/开单成功/).first().waitFor();
    assert.equal(f.state.sales.length, 2);
    assert.equal(f.state.purchases.length, 2);
    assert.ok(f.state.inventory.length >= checksBeforeRetry + rows.length);
    assert.equal(await saved(f.page), null);
  } finally { await f.close(); }
});

test("an aborted purchase is uncertain, excluded from copied successes, and locks the draft until inventory review", async () => {
  const f = await fixture();
  f.state.purchaseOutcomes = ["success", "abort"];
  try {
    await confirmShortage(f.page);
    const dialog = resultDialog(f.page);
    await dialog.waitFor();
    assert.match(await dialog.innerText(), /待核对|待核实/);
    assert.ok((await dialog.innerText()).includes(rows[1].title));
    assert.equal(f.state.purchases.length, 2);
    assert.equal(f.state.sales.length, 0);
    await dialog.getByRole("button", { name: "复制进货信息", exact: true }).click();
    await eventually(async () => (await copied(f.page)).length === 1, "only confirmed success is copied");
    assert.ok((await copied(f.page))[0].includes(productName(rows[0])));
    assert.ok(!(await copied(f.page))[0].includes(productName(rows[1])));
    await closeResult(f.page);
    await assertDraftPreserved(f.page);
    assert.equal(await f.page.getByRole("button", { name: "提交开单", exact: true }).isDisabled(), true);
    assert.equal(await lineTable(f.page).first().getByRole("spinbutton").first().isDisabled(), true);
    await f.page.getByRole("button", { name: "核对库存", exact: true }).waitFor();
    await f.page.getByRole("button", { name: "已核对，继续编辑", exact: true }).click();
    assert.equal(await f.page.getByRole("button", { name: "提交开单", exact: true }).isDisabled(), false);
    assert.equal(f.state.purchases.length, 2);
    assert.equal(f.state.sales.length, 0);
  } finally { await f.close(); }
});

test("an aborted first purchase has no confirmed success to copy and creates no sale", async () => {
  const f = await fixture();
  f.state.purchaseOutcomes = ["abort"];
  try {
    await confirmShortage(f.page);
    const dialog = resultDialog(f.page);
    await dialog.waitFor();
    assert.match(await dialog.innerText(), /待核对|待核实/);
    assert.equal(f.state.purchases.length, 1);
    assert.equal(f.state.sales.length, 0);
    const copy = dialog.getByRole("button", { name: "复制进货信息", exact: true });
    assert.ok((await copy.count()) === 0 || await copy.isDisabled(), "uncertain purchases cannot be copied as successes");
    assert.deepEqual(await copied(f.page), []);
    await closeResult(f.page);
    await assertDraftPreserved(f.page);
    assert.equal(await f.page.getByRole("button", { name: "提交开单", exact: true }).isDisabled(), true);
  } finally { await f.close(); }
});

test("an aborted sales request marks the sale uncertain and locks the purchased draft until sales review", async () => {
  const f = await fixture();
  f.state.saleOutcome = "abort";
  try {
    await confirmShortage(f.page);
    const dialog = resultDialog(f.page);
    await dialog.waitFor();
    assert.match(await dialog.innerText(), /销售单.*(待核对|待核实)|开单.*(待核对|待核实)/);
    assert.equal(f.state.purchases.length, 2);
    assert.equal(f.state.sales.length, 1);
    await closeResult(f.page);
    await assertDraftPreserved(f.page);
    assert.equal(await f.page.getByRole("button", { name: "提交开单", exact: true }).isDisabled(), true);
    assert.equal(await lineTable(f.page).first().getByRole("spinbutton").first().isDisabled(), true);
    await f.page.getByRole("button", { name: "核对销售单", exact: true }).waitFor();
    await f.page.getByRole("button", { name: "已核对，继续编辑", exact: true }).click();
    assert.equal(await f.page.getByRole("button", { name: "提交开单", exact: true }).isDisabled(), false);
    assert.equal(f.state.purchases.length, 2);
    assert.equal(f.state.sales.length, 1);
  } finally { await f.close(); }
});

test("navigating away during a purchase preserves the automatic result on return", async () => {
  const f = await fixture();
  const gate = deferred();
  f.state.purchaseGate = gate.promise;
  try {
    await confirmShortage(f.page);
    await eventually(() => f.state.purchases.length === 1, "first purchase starts");
    await f.page.getByRole("button", { name: "销售单", exact: true }).click();
    await f.page.locator(".sales-create-page").waitFor({ state: "hidden" });
    gate.release();
    await eventually(() => f.state.salesCompleted === 1, "sale completes while away");
    await f.page.getByRole("button", { name: "新建开单", exact: true }).click();
    await resultDialog(f.page).waitFor();
    assert.equal(f.state.purchases.length, 2);
    assert.equal(f.state.sales.length, 1);
    assert.equal(await lineTable(f.page).count(), 0);
  } finally { gate.release(); await f.close(); }
});

test("logging out during a purchase stops subsequent purchases and the sales request", async () => {
  const f = await fixture();
  const gate = deferred();
  f.state.purchaseGate = gate.promise;
  try {
    await confirmShortage(f.page);
    await eventually(() => f.state.purchases.length === 1, "first purchase starts");
    await f.page.getByRole("button", { name: "退出", exact: true }).click();
    await f.page.waitForURL("**/admin/login");
    gate.release();
    await eventually(() => f.state.purchaseCompleted === 1, "in-flight purchase response is released");
    await rendered(f.page);
    assert.equal(f.state.loggedOut, true);
    assert.equal(f.state.purchases.length, 1);
    assert.equal(f.state.sales.length, 0);
    assert.equal(await saved(f.page), null);
    assert.equal(await resultDialog(f.page).count(), 0);
  } finally { gate.release(); await f.close(); }
});

test("double-clicking purchase confirmation does not duplicate purchases or the sale", async () => {
  const f = await fixture();
  const gate = deferred();
  f.state.purchaseGate = gate.promise;
  try {
    await f.page.getByRole("button", { name: "提交开单", exact: true }).click();
    const confirm = f.page.getByRole("alertdialog").getByRole("button", { name: "先进货并开单", exact: true });
    await confirm.dblclick();
    await eventually(() => f.state.purchases.length === 1, "one purchase starts");
    gate.release();
    await resultDialog(f.page).waitFor();
    assert.deepEqual(f.state.purchases.map((item) => item.product_id), [1046, 1047]);
    assert.equal(f.state.sales.length, 1);
  } finally { gate.release(); await f.close(); }
});

test("clipboard denial displays an explicit copy failure without claiming success", async () => {
  const f = await fixture({ clipboardFails: true });
  try {
    await confirmShortage(f.page);
    const dialog = resultDialog(f.page);
    await dialog.waitFor();
    await dialog.getByRole("button", { name: "复制进货信息", exact: true }).click();
    await dialog.getByText(/复制失败|无法复制|未能复制/).waitFor();
    assert.deepEqual(await copied(f.page), []);
    assert.doesNotMatch(await dialog.innerText(), /复制成功|已复制/);
    assert.equal(f.state.purchases.length, 2);
    assert.equal(f.state.sales.length, 1);
  } finally { await f.close(); }
});
