// Run against the local Vite server with Playwright available in NODE_PATH.
const assert = require("node:assert/strict");
const { before, after, test } = require("node:test");
const { chromium } = require("playwright");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const base = process.env.IMAGE_CORRECTION_TEST_URL || "http://127.0.0.1:5183/admin/";
const row = (id, extra = {}) => ({ correction_id: id, goods_name: "识别错名", original_goods_name: "原始错名", original_color: "原始红", color: "红", quantity: 40, unit: "套", raw_quantity: 2, raw_unit: "件", remark: "保留备注", order_date: "2026-10-28", source_filename: `${id}.jpg`, recognition_error: "未找到商品", ...extra });
const initial = () => ({ correction_batch_id: "immutable-batch-token", pending_action: "confirm_image_workflow_correction", customer_name: "原客户", parsed_list: [row("row-a"), row("row-b", { product_id: 91, goods_name: "已识别商品", recognition_error: "" })] });
const snapshot = (state) => ({ has_pending: true, pending_intent: "workflow", pending_action: state.pending_action || "confirm_image_workflow_correction", state });
const products = (keyword) => [{ id: 101, title: `商品${keyword}`, piece_text: "20套/件", is_listed: 0, native_status: "inactive", product_group_data: [
  { id: 101, title: `商品${keyword}`, spec: "蓝色", sku_no: "SJ101", is_sellable: 1, is_listed: 0 },
  { id: 102, title: `商品${keyword}`, spec: "停用色", sku_no: "SJ102", is_sellable: false },
  { id: 103, title: `商品${keyword}`, spec: "停用色2", sku_no: "SJ103", is_sellable: 0 },
  { id: 104, title: `商品${keyword}`, spec: "停用色3", sku_no: "SJ104", is_sellable: 1, native_status: "inactive" }
] }];
let browser;
before(async () => { browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }); });
after(async () => { await browser?.close(); });

async function fixture(state = initial()) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  const requests = { search: [], pending: [], chat: [], gate: null, fail: false, remain: false, searchFail: false };
  context.on("page", (page) => page.on("pageerror", (e) => errors.push(e.message)));
  await context.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    let data = { list: [], total: 0 };
    let status = 200;
    if (url.pathname === "/api/web-auth/me") {
      data = { user: { id: 7, username: "correction-test", role: "admin", is_admin: 1, is_active: 1, approval_status: "approved", permissions: [] } };
    } else if (url.pathname === "/api/agent/history") {
      data = { history: [], session: snapshot(state) };
    } else if (url.pathname === "/api/product/list") {
      const keyword = url.searchParams.get("keyword");
      requests.search.push({ keyword, listedOnly: url.searchParams.get("listed_only") });
      await new Promise((resolve) => setTimeout(resolve, keyword === "slow" ? 700 : 30));
      data = { list: products(keyword), total: 1 };
      if (requests.searchFail) status = 500;
    } else if (url.pathname === "/api/session/pending") {
      const body = route.request().postDataJSON();
      requests.pending.push(body);
      if (requests.gate) await requests.gate;
      if (requests.fail) status = 409;
      data = { session_id: body.session_id, response: requests.remain ? "请核对第二张设计稿" : "本批已处理", session: requests.remain ? snapshot(body.state) : { has_pending: body.execute !== "cancel", pending_action: body.execute === "cancel" ? "" : "confirm_image_sales", state: body.state } };
    } else if (url.pathname === "/api/agent/chat") {
      requests.chat.push(route.request().postDataJSON());
      data = { response: "取消", session: { has_pending: false } };
    }
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify({ code: status === 200 ? 0 : status, msg: status === 200 ? undefined : "SQL traceback /internal/private/path", data }) }).catch(() => {});
  });
  const page = await context.newPage();
  page.setDefaultTimeout(6000);
  await page.goto(base);
  await page.getByRole("dialog").waitFor();
  return { context, page, requests, rows: page.locator(".image-correction-row"), async close() { await context.close(); assert.deepEqual(errors, []); } };
}

async function select(row, keyword) {
  await row.getByRole("textbox", { name: "搜索替换商品" }).fill(keyword);
  await row.getByRole("button", { name: /蓝色.*SJ101/ }).click();
}

test("correction uses explicit SKU selection, immutable OCR and full atomic payload", async () => {
  const f = await fixture();
  try {
    const submit = f.page.getByRole("button", { name: "确认校正并继续" });
    assert.equal(await submit.isDisabled(), true);
    await select(f.rows.first(), "新款");
    assert.equal(await f.rows.first().getByText("原始错名", { exact: true }).count(), 1);
    assert.match(await f.rows.first().innerText(), /替换为.*商品新款.*蓝色/s);
    assert.equal(await f.rows.first().getByRole("button", { name: /SJ102|SJ103|SJ104/ }).count(), 0);
    await f.rows.first().getByRole("spinbutton", { name: "数量" }).fill("3.5");
    await f.rows.first().getByRole("textbox", { name: "单位", exact: true }).fill("件");
    await f.page.getByRole("textbox", { name: "本批客户" }).fill("");
    assert.equal(await submit.isDisabled(), true);
    await f.page.getByRole("textbox", { name: "本批客户" }).fill("新客户");
    await select(f.rows.nth(1), "第二款");
    await submit.click();
    await f.page.waitForFunction(() => !document.querySelector(".image-correction-dialog"));
    assert.equal(f.requests.pending.length, 1);
    assert.equal(f.requests.pending[0].execute, "confirm");
    const sent = f.requests.pending[0].state;
    assert.equal(sent.correction_batch_id, "immutable-batch-token");
    assert.equal(sent.customer_name, "新客户");
    assert.deepEqual(sent.parsed_list.map((r) => r.correction_id), ["row-a", "row-b"]);
    assert.equal(sent.parsed_list[0].selected_sku_id, 101);
    assert.equal(sent.parsed_list[0].product_id, 101);
    assert.equal(sent.parsed_list[0].goods_name, "商品新款");
    assert.equal(sent.parsed_list[0].color, "蓝色");
    assert.equal(sent.parsed_list[0].raw_quantity, 3.5);
    assert.equal(sent.parsed_list[0].quantity, 40);
    assert.equal(sent.parsed_list[0].raw_unit, "件");
    assert.equal(sent.parsed_list[0].original_goods_name, "原始错名");
    assert.equal(sent.parsed_list[0].original_color, "原始红");
    assert.equal(sent.parsed_list[0].remark, "保留备注");
    assert.equal(sent.parsed_list[0].order_date, "2026-10-28");
    assert.equal(f.requests.chat.length, 0);
    assert.ok(f.requests.search.every((r) => r.listedOnly !== "1"));
  } finally { await f.close(); }
});

test("row debounce, cancellation and late responses do not cross rows or erase a selection", async () => {
  const f = await fixture();
  try {
    const first = f.rows.first().getByRole("textbox", { name: "搜索替换商品" });
    await first.fill("s");
    await first.fill("sl");
    await first.fill("slow");
    await f.page.waitForRequest((r) => r.url().includes("keyword=slow"));
    await first.fill("fast");
    await select(f.rows.nth(1), "独立");
    await f.rows.first().getByRole("button", { name: /蓝色.*SJ101/ }).click();
    await f.page.waitForTimeout(800);
    assert.match(await f.rows.first().innerText(), /替换为.*商品fast/s);
    assert.match(await f.rows.nth(1).innerText(), /替换为.*商品独立/s);
    assert.ok(!f.requests.search.some((r) => ["s", "sl"].includes(r.keyword)));
    assert.equal(await f.rows.first().getByText("商品slow", { exact: true }).count(), 0);
    await first.fill("后续搜索");
    await f.rows.first().getByText("商品后续搜索", { exact: true }).waitFor();
    assert.match(await f.rows.first().innerText(), /替换为.*商品fast/s);
  } finally { await f.close(); }
});

test("empty and nonpositive raw quantities block submission and legacy raw fields get fallbacks", async () => {
  const state = initial();
  state.parsed_list = [row("fallback", { raw_quantity: undefined, raw_unit: undefined, product_id: 55, original_goods_name: undefined })];
  const f = await fixture(state);
  try {
    const qty = f.rows.first().getByRole("spinbutton", { name: "数量" });
    assert.equal(await qty.inputValue(), "40");
    assert.equal(await f.rows.first().getByRole("textbox", { name: "单位", exact: true }).inputValue(), "套");
    for (const value of ["", "0", "-1"]) {
      await qty.fill(value);
      assert.equal(await f.page.getByRole("button", { name: "确认校正并继续" }).isDisabled(), true);
    }
    await qty.fill("0.5");
    assert.equal(await f.page.getByRole("button", { name: "确认校正并继续" }).isDisabled(), false);
  } finally { await f.close(); }
});

for (const method of ["button", "close", "escape"]) test(`${method} cancels atomically, only closing after success`, async () => {
  const f = await fixture();
  let release;
  f.requests.gate = new Promise((resolve) => { release = resolve; });
  try {
    const pending = f.page.waitForRequest((r) => r.url().includes("/api/session/pending"));
    if (method === "button") await f.page.getByRole("button", { name: "取消", exact: true }).click();
    if (method === "close") await f.page.getByRole("button", { name: "关闭校正" }).click();
    if (method === "escape") await f.page.keyboard.press("Escape");
    await pending;
    assert.equal(await f.page.getByRole("dialog").count(), 1);
    assert.equal(f.requests.pending[0].execute, "cancel");
    assert.equal(await f.page.getByRole("button", { name: "关闭校正" }).isDisabled(), true);
    release();
    await f.page.getByRole("dialog").waitFor({ state: "hidden" });
    assert.equal(f.requests.chat.length, 0);
  } finally { release?.(); await f.close(); }
});

test("failed cancellation and confirmation retain edits and hide technical errors", async () => {
  const f = await fixture();
  try {
    await select(f.rows.first(), "保留款");
    f.requests.fail = true;
    await f.page.getByRole("button", { name: "取消", exact: true }).click();
    await f.page.getByRole("alert").filter({ hasText: "取消未成功" }).waitFor();
    assert.match(await f.rows.first().innerText(), /替换为.*商品保留款/s);
    await f.page.getByRole("button", { name: "确认校正并继续" }).click();
    await f.page.getByRole("alert").filter({ hasText: "校正未提交" }).waitFor();
    assert.ok(!(await f.page.getByRole("dialog").innerText()).includes("SQL"));
    f.requests.fail = false;
    f.requests.remain = true;
    await f.page.getByRole("button", { name: "确认校正并继续" }).click();
    await f.page.getByRole("alert").filter({ hasText: "请核对第二张设计稿" }).waitFor();
    assert.match(await f.rows.first().innerText(), /替换为.*商品保留款/s);
    assert.equal(f.requests.chat.length, 0);
  } finally { await f.close(); }
});

test("confirmation locks every edit and dismissal while its request is pending", async () => {
  const f = await fixture();
  let release;
  try {
    await select(f.rows.first(), "锁定款");
    f.requests.gate = new Promise((resolve) => { release = resolve; });
    const pending = f.page.waitForRequest((r) => r.url().includes("/api/session/pending"));
    await f.page.getByRole("button", { name: "确认校正并继续" }).click();
    await pending;
    const inputs = f.page.getByRole("dialog").locator("input, button");
    for (const input of await inputs.all()) assert.equal(await input.isDisabled(), true);
    await f.page.keyboard.press("Escape");
    assert.equal(await f.page.getByRole("dialog").count(), 1);
    release();
    await f.page.locator(".image-correction-dialog").waitFor({ state: "hidden" });
  } finally { release?.(); await f.close(); }
});

test("search failures are inline and mobile correction content fits its dialog", async () => {
  const f = await fixture();
  try {
    f.requests.searchFail = true;
    await f.rows.first().getByRole("textbox", { name: "搜索替换商品" }).fill("失败");
    await f.rows.first().getByRole("alert").waitFor();
    assert.ok(!(await f.rows.first().innerText()).includes("SQL"));
    const dir = path.join(os.tmpdir(), "sjagent-image-correction-frontend");
    await fs.mkdir(dir, { recursive: true });
    for (const width of [1280, 390]) {
      await f.page.setViewportSize({ width, height: 844 });
      assert.equal(await f.page.getByRole("dialog").evaluate((el) => el.scrollWidth <= el.clientWidth), true);
      const bounds = await f.page.getByRole("dialog").boundingBox();
      assert.ok(bounds.x >= 0 && bounds.y >= 0 && bounds.x + bounds.width <= width && bounds.y + bounds.height <= 845);
      await f.page.screenshot({ path: path.join(dir, `correction-${width}.png`) });
    }
  } finally { await f.close(); }
});

test("non-correction dialogs keep hide-only dismissal and the existing two-step confirmation", async () => {
  const f = await fixture({ pending_action: "confirm_workflow_order", customer_name: "客户", goods_name: "商品", quantity: 10 });
  try {
    await f.page.keyboard.press("Escape");
    await f.page.getByRole("dialog").waitFor({ state: "hidden" });
    assert.equal(f.requests.pending.length, 0);
    assert.equal(f.requests.chat.length, 0);
    await f.page.reload();
    await f.page.getByRole("dialog").waitFor();
    const confirmed = f.page.waitForRequest((r) => r.url().includes("/api/agent/chat"));
    await f.page.getByRole("button", { name: "确认执行", exact: true }).click();
    const confirmRequest = await confirmed;
    assert.equal(f.requests.pending.length, 1);
    assert.equal(f.requests.pending[0].execute, undefined);
    assert.equal(confirmRequest.postDataJSON().message, "确认");
  } finally { await f.close(); }
});
