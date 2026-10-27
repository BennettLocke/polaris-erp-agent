// Run against the local Vite server with Playwright available in NODE_PATH.
const assert = require("node:assert/strict");
const { before, after, test } = require("node:test");
const { chromium } = require("playwright");
const fs = require("node:fs/promises");
const path = require("node:path");

const base = process.env.SALES_DRAFT_TEST_URL || "http://127.0.0.1:5183/admin/sales-new";
const key = "polaris:sales-draft:v1:7";
const customer = { id: 3, name: "齐唯茶业", is_monthly_customer: 1 };
const rows = [
  { product_id: 1046, spu_id: 100, unit_id: 1, title: "【喜悦】半斤", spec: "红色", coding: "SJ1046", buy_number: 24, price: 20, warehouse_id: 1, price_source: "manual_override", is_stock_item: 1 },
  { product_id: 1047, spu_id: 100, unit_id: 1, title: "【喜悦】半斤", spec: "蓝色", coding: "SJ1047", buy_number: 6, price: 20, warehouse_id: 2, price_source: "manual_override", is_stock_item: 1 }
];
const draft = { selectedCustomer: customer, customerKeyword: customer.name, productKeyword: "喜悦", lines: rows, defaultWarehouseId: 1, lineQty: 3.5, createTime: "2026-10-27T10:00", payStatus: "paid", payType: "cash" };
let browser;
before(async () => { browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }); });
after(async () => { await browser?.close(); });

async function fixture({ seed = true, blocked = false } = {}) {
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const state = { salesRequests: 0, purchases: 0, retailRequests: 0, available: 1000, fail: false, priceFail: false, saleGate: null, inventoryGate: null, priceGate: null, loggedOut: false };
  const errors = [];
  context.on("page", (page) => page.on("pageerror", (e) => errors.push(e.message)));
  await context.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let data = { list: [], total: 0, page: 1, page_size: 20 };
    let status = 200;
    let msg;
    if (url.pathname === "/api/web-auth/me") {
      data = { user: { id: 7, username: "draft-test", display_name: "测试账号", role: "admin", role_text: "管理员", permissions: [], is_admin: 1, is_active: 1, approval_status: "approved" } };
    } else if (url.pathname === "/api/web-auth/logout") {
      state.loggedOut = true;
      data = {};
    } else if (url.pathname === "/api/warehouses") {
      data = { list: [{ id: 1, name: "自己店里" }, { id: 2, name: "百鑫仓库", is_default_sales: 1 }] };
    } else if (url.pathname === "/api/customer/list") {
      await new Promise((resolve) => setTimeout(resolve, 100));
      data = url.searchParams.get("keyword") === "散客" ? [{ id: 1, name: "散客" }] : [customer];
    } else if (url.pathname === "/api/product/list") {
      data = { list: [{ id: 1046, spu_id: 100, title: "【喜悦】半斤", spec: "红色", price: 22, unit_id: 1, is_stock_item: 1 }], total: 1 };
    } else if (url.pathname === "/api/sales/price-preview") {
      if (state.priceGate) await state.priceGate;
      data = { price: 22, source: "retail_price", effective_policy: "off", sku: { spu_id: 100 } };
      if (state.priceFail) { status = 400; msg = "测试：查询失败"; }
    } else if (url.pathname === "/api/product/retail-price") {
      state.retailRequests++;
      data = { price: 22 };
    } else if (url.pathname === "/api/inventory/balances") {
      if (state.inventoryGate) await state.inventoryGate;
      data = { list: [{ product_id: Number(url.searchParams.get("sku_id")), warehouse_id: Number(url.searchParams.get("warehouse_id")), quantity: state.available }], total: 1 };
    } else if (url.pathname === "/api/sales/add") {
      state.salesRequests++;
      if (state.saleGate) await state.saleGate;
      data = { id: 999, sales_id: 999, sales_no: "SO-DRAFT-TEST" };
      if (state.fail) { status = 400; msg = "测试：客户已失效，请重新选择客户"; }
    } else if (url.pathname === "/api/inventory/purchase") {
      state.purchases++;
      data = { id: 888 };
    }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ code: status === 200 ? 0 : status, data, msg }) });
  });
  const page = await context.newPage();
  if (blocked) {
    await page.addInitScript(() => Object.defineProperty(window, "sessionStorage", { get() { throw new Error("Storage disabled"); } }));
  } else if (seed) {
    await page.addInitScript(({ key, draft }) => {
      if (location.origin === "null") return;
      if (!sessionStorage.getItem("draft-test-seeded")) {
        sessionStorage.setItem(key, JSON.stringify({ version: 1, accountId: 7, draft }));
        sessionStorage.setItem("draft-test-seeded", "yes");
      }
    }, { key, draft });
  }
  await page.goto(base);
  await page.locator(".sales-create-page").waitFor();
  return { context, page, state, errors, async close() { await context.close(); assert.deepEqual(errors, []); } };
}

const lineTable = (page) => page.locator(".sales-create-line-table tbody tr");
const saved = (page) => page.evaluate((key) => JSON.parse(sessionStorage.getItem(key)), key);
async function awayAndBack(page) {
  await page.getByRole("button", { name: "销售单", exact: true }).click();
  await page.locator(".sales-create-page").waitFor({ state: "hidden" });
  await page.getByRole("button", { name: "开单", exact: true }).click();
  await page.locator(".sales-create-page").waitFor({ state: "visible" });
}

test("edits survive navigation and refresh without late defaults overriding them", async () => {
  const f = await fixture();
  try {
    const { page } = f;
    await lineTable(page).nth(1).waitFor();
    await page.getByPlaceholder("输入礼盒名称，回车搜索").fill("墨香");
    const qty = lineTable(page).first().getByRole("spinbutton").first();
    await qty.fill("");
    assert.equal((await saved(page)).draft.lines[0].buy_number, 24);
    await qty.fill("24.5");
    await qty.blur();
    await lineTable(page).first().getByRole("spinbutton").nth(1).fill("21");
    await awayAndBack(page);
    assert.equal(await qty.inputValue(), "24.5");
    assert.equal(await lineTable(page).nth(1).getByRole("spinbutton").nth(1).inputValue(), "21");
    const before = (await saved(page)).draft;
    await page.reload();
    await lineTable(page).nth(1).waitFor();
    await page.getByText("自己店里", { exact: true }).first().waitFor();
    assert.deepEqual((await saved(page)).draft, before);
    assert.equal(await page.getByPlaceholder("输入礼盒名称，回车搜索").inputValue(), "墨香");
    assert.equal(f.state.salesRequests, 0);
    assert.equal(f.state.purchases, 0);
    const dir = path.resolve(__dirname, "../.tmp/sales-draft");
    await fs.mkdir(dir, { recursive: true });
    for (const width of [1280, 1920, 2560, 390]) {
      await page.setViewportSize({ width, height: 1080 });
      await page.screenshot({ path: path.join(dir, `draft-${width}.png`), fullPage: true });
    }
  } finally { await f.close(); }
});

test("clear requires confirmation and cancel preserves the draft", async () => {
  const f = await fixture();
  try {
    await lineTable(f.page).nth(1).waitFor();
    await f.page.getByRole("button", { name: "清空", exact: true }).click();
    await f.page.getByRole("alertdialog").waitFor();
    await f.page.getByRole("button", { name: "保留草稿" }).click();
    assert.equal(await lineTable(f.page).count(), 2);
    await f.page.getByRole("button", { name: "清空", exact: true }).click();
    await f.page.getByRole("button", { name: "确认清空" }).click();
    await f.page.waitForFunction((key) => sessionStorage.getItem(key) === null, key);
    assert.equal(await lineTable(f.page).count(), 0);
  } finally { await f.close(); }
});

test("successful submission while on another page clears the saved and visible draft", async () => {
  const f = await fixture();
  let release;
  f.state.saleGate = new Promise((resolve) => { release = resolve; });
  try {
    await lineTable(f.page).nth(1).waitFor();
    const submitted = f.page.waitForRequest((r) => r.url().includes("/api/sales/add"));
    await f.page.getByRole("button", { name: "提交开单", exact: true }).click();
    await submitted;
    assert.equal(await lineTable(f.page).first().getByRole("spinbutton").first().isDisabled(), true);
    await f.page.getByRole("button", { name: "销售单", exact: true }).click();
    release();
    await f.page.waitForFunction((key) => sessionStorage.getItem(key) === null, key);
    await f.page.getByRole("button", { name: "新建开单", exact: true }).click();
    assert.equal(await lineTable(f.page).count(), 0);
    assert.equal(f.state.salesRequests, 1);
    await f.page.reload();
    await f.page.locator(".sales-create-page").waitFor();
    assert.equal(await lineTable(f.page).count(), 0);
  } finally { release?.(); await f.close(); }
});

test("failure and cancelled stock replenishment keep the draft without creating orders", async () => {
  const f = await fixture();
  try {
    f.state.fail = true;
    await f.page.getByRole("button", { name: "提交开单", exact: true }).click();
    await f.page.getByText("测试：客户已失效，请重新选择客户").waitFor();
    assert.equal((await saved(f.page)).draft.lines.length, 2);
    f.state.available = 0;
    await f.page.getByRole("button", { name: "提交开单", exact: true }).click();
    await f.page.getByRole("alertdialog").waitFor();
    await f.page.getByRole("button", { name: "取消", exact: true }).click();
    assert.equal((await saved(f.page)).draft.lines.length, 2);
    assert.equal(f.state.salesRequests, 1);
    assert.equal(f.state.purchases, 0);
  } finally { await f.close(); }
});

test("another tab starts blank and logout clears this account draft", async () => {
  const f = await fixture();
  try {
    await lineTable(f.page).nth(1).waitFor();
    const other = await f.context.newPage();
    await other.goto(base);
    await other.locator(".sales-create-page").waitFor();
    assert.equal(await lineTable(other).count(), 0);
    assert.equal(await lineTable(f.page).count(), 2);
    await other.close();
    await f.page.getByRole("button", { name: "退出", exact: true }).click();
    await f.page.waitForURL("**/admin/login");
    assert.equal(await saved(f.page), null);
  } finally { await f.close(); }
});

test("blocked session storage still retains edited items across navigation", async () => {
  const f = await fixture({ seed: false, blocked: true });
  try {
    await f.page.getByRole("status").filter({ hasText: "刷新后可能丢失" }).waitFor();
    await f.page.getByPlaceholder("输入礼盒名称，回车搜索").fill("喜悦");
    await f.page.getByRole("button", { name: "搜索商品", exact: true }).click();
    await f.page.locator(".sales-create-variant").first().click();
    await lineTable(f.page).first().waitFor();
    await awayAndBack(f.page);
    assert.equal(await lineTable(f.page).count(), 1);
  } finally { await f.close(); }
});

test("a pending product addition disables submit and cannot resurrect a cleared draft", async () => {
  const f = await fixture();
  let release;
  f.state.priceGate = new Promise((resolve) => { release = resolve; });
  try {
    await lineTable(f.page).nth(1).waitFor();
    await f.page.getByRole("button", { name: "搜索商品", exact: true }).click();
    const pricing = f.page.waitForRequest((request) => request.url().includes("/api/sales/price-preview"));
    await f.page.locator(".sales-create-variant").first().click();
    await pricing;
    assert.equal(await f.page.getByRole("button", { name: "提交开单", exact: true }).isDisabled(), true);
    await f.page.getByRole("button", { name: "清空", exact: true }).click();
    await f.page.getByRole("button", { name: "确认清空" }).click();
    const completed = f.page.waitForResponse((response) => response.url().includes("/api/sales/price-preview"));
    release();
    await completed;
    await f.page.getByRole("button", { name: "提交开单", exact: true }).waitFor();
    assert.equal(await lineTable(f.page).count(), 0);
    assert.equal(await saved(f.page), null);
    assert.equal(f.state.salesRequests, 0);
  } finally { release?.(); await f.close(); }
});

test("logging out during stock lookup stops the later sales request", async () => {
  const f = await fixture();
  let release;
  f.state.inventoryGate = new Promise((resolve) => { release = resolve; });
  try {
    await lineTable(f.page).nth(1).waitFor();
    const checking = f.page.waitForRequest((request) => request.url().includes("/api/inventory/balances"));
    await f.page.getByRole("button", { name: "提交开单", exact: true }).click();
    await checking;
    await f.page.getByRole("button", { name: "退出", exact: true }).click();
    await f.page.waitForURL("**/admin/login");
    const completed = f.page.waitForResponse((response) => response.url().includes("/api/inventory/balances"));
    release();
    await completed;
    assert.equal(await saved(f.page), null);
    assert.equal(f.state.salesRequests, 0);
    assert.equal(f.state.purchases, 0);
  } finally { release?.(); await f.close(); }
});

test("an interrupted submission restores a locked draft until the user has checked orders", async () => {
  const f = await fixture();
  try {
    await lineTable(f.page).nth(1).waitFor();
    await f.page.evaluate((key) => {
      const value = JSON.parse(sessionStorage.getItem(key));
      sessionStorage.setItem(key, JSON.stringify({ ...value, submissionPending: true }));
    }, key);
    await f.page.reload();
    await f.page.getByText("上次提交被中断，销售单可能已创建，请先核对再继续。").waitFor();
    assert.equal(await f.page.getByRole("button", { name: "提交开单", exact: true }).isDisabled(), true);
    assert.equal(await lineTable(f.page).first().getByRole("spinbutton").first().isDisabled(), true);
    await f.page.getByRole("button", { name: "核对销售单", exact: true }).click();
    await f.page.getByRole("button", { name: "新建开单", exact: true }).click();
    await f.page.getByRole("button", { name: "已核对，继续编辑", exact: true }).click();
    assert.equal(await f.page.getByRole("button", { name: "提交开单", exact: true }).isDisabled(), false);
    assert.equal(f.state.salesRequests, 0);
  } finally { await f.close(); }
});

test("logout during price lookup also stops its fallback lookup and late draft edits", async () => {
  const f = await fixture();
  let release;
  f.state.priceFail = true;
  f.state.priceGate = new Promise((resolve) => { release = resolve; });
  try {
    await lineTable(f.page).nth(1).waitFor();
    await f.page.getByRole("button", { name: "搜索商品", exact: true }).click();
    const pricing = f.page.waitForRequest((request) => request.url().includes("/api/sales/price-preview"));
    await f.page.locator(".sales-create-variant").first().click();
    await pricing;
    await f.page.getByRole("button", { name: "退出", exact: true }).click();
    await f.page.waitForURL("**/admin/login");
    const completed = f.page.waitForResponse((response) => response.url().includes("/api/sales/price-preview"));
    release();
    await completed;
    await f.page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(f.state.retailRequests, 0);
    assert.equal(await saved(f.page), null);
  } finally { release?.(); await f.close(); }
});
