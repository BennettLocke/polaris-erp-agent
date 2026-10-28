const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const ts = require("../admin/node_modules/typescript");

const root = path.join(__dirname, "../admin/src/components/business/purchase-result");
function load(name, dependencies = {}, globals = {}) {
  const filename = path.join(root, name);
  assert.ok(fs.existsSync(filename), `Missing implementation: ${filename}`);
  const code = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX }
  }).outputText;
  const exports = {};
  const jsx = (type, props) => ({ type, props });
  vm.runInNewContext(code, {
    exports, require: (id) => id === "react/jsx-runtime" ? { jsx, jsxs: jsx } : dependencies[id] || {}, ...globals
  }, { filename });
  return exports;
}

const item = { productId: 1, productName: " 【墨香】 半斤\t", color: "黄色", quantity: 24, unitName: "套", caseCount: 1, warehouseId: 2, warehouseName: "百鑫仓库", docNo: "IN-123" };

test("formats successful purchases without brackets, whitespace, headers or document numbers", () => {
  const { formatPurchaseResult } = load("purchase-result.ts");
  assert.equal(formatPurchaseResult([item]), "商品：墨香半斤\n颜色：黄色\n进货：1件\n备注：送至百鑫");
  assert.equal(item.productName, " 【墨香】 半斤\t");
});

test("preserves input order, actual units, fractional cases and warehouse names without suffixes", () => {
  const { formatPurchaseResult } = load("purchase-result.ts");
  for (const caseCount of [undefined, 0, -1]) {
    const text = formatPurchaseResult([{ ...item, caseCount, quantity: 2.5, unitName: "捆", warehouseName: "自己店里" }]);
    assert.ok(text.includes("进货：2.5捆\n备注：送至自己店里"));
  }
  assert.equal(formatPurchaseResult([]), "");
  const text = formatPurchaseResult([item, { ...item, caseCount: 0.5, warehouseName: "仓库配货仓库" }]);
  assert.equal(text.split("\n\n").length, 2);
  assert.ok(text.endsWith("进货：0.5件\n备注：送至仓库配货"));
});

function copyFixture({ clipboard, fallback = true, onError } = {}) {
  const states = [];
  const refs = [];
  const effects = [];
  const timers = new Map();
  let cursor = 0;
  let refCursor = 0;
  let fallbackCalls = 0;
  let removed = 0;
  const react = {
    useState(initial) { const i = cursor++; if (!(i in states)) states[i] = initial; return [states[i], (value) => { states[i] = value; }]; },
    useRef(initial) { const i = refCursor++; return refs[i] ||= { current: initial }; },
    useEffect(effect) { effects.push(effect); }
  };
  const textarea = { value: "", style: {}, setAttribute() {}, select() {}, remove() { removed++; } };
  const document = {
    activeElement: { focus() {}, closest() { return null; } },
    body: { appendChild() {} }, createElement() { return textarea; },
    execCommand() { fallbackCalls++; return fallback; }
  };
  const { PurchaseResultCopyButton } = load("purchase-result-copy-button.tsx", { react }, {
    document, navigator: { clipboard }, window: { setTimeout(fn) { timers.set(1, fn); return 1; }, clearTimeout(id) { timers.delete(id); } }
  });
  const render = (props = {}) => { cursor = refCursor = 0; return PurchaseResultCopyButton({ text: "confirmed only", onError, ...props }); };
  const first = render();
  const cleanups = effects.map((effect) => effect());
  return { render, first, timers, cleanup: () => cleanups.forEach((fn) => fn?.()), fallbackCalls: () => fallbackCalls, removed: () => removed };
}

function nodes(tree) {
  if (!tree || typeof tree !== "object") return [];
  return [tree, ...[tree.props?.children].flat(Infinity).flatMap(nodes)];
}
function copyButton(tree) { return nodes(tree).find((node) => node.props?.onClick); }

test("clipboard success reports copied and clears its timer on unmount", async () => {
  const copied = [];
  const fixture = copyFixture({ clipboard: { writeText: async (text) => copied.push(text) } });
  await copyButton(fixture.first).props.onClick();
  assert.deepEqual(copied, ["confirmed only"]);
  assert.ok(nodes(fixture.render()).some((node) => node.props?.children === "已复制" || node.props?.children?.includes?.("已复制")));
  assert.equal(fixture.timers.size, 1);
  fixture.cleanup();
  assert.equal(fixture.timers.size, 0);
});

test("clipboard rejection and missing API both attempt the fallback and remove its textarea", async () => {
  for (const clipboard of [undefined, { writeText: async () => { throw new Error("denied"); } }]) {
    const fixture = copyFixture({ clipboard });
    await copyButton(fixture.first).props.onClick();
    assert.equal(fixture.fallbackCalls(), 1);
    assert.equal(fixture.removed(), 1);
    fixture.cleanup();
  }
});

test("copy failure reports an explicit error and keeps the original text selectable", async () => {
  const errors = [];
  const fixture = copyFixture({ fallback: false, onError: (message) => errors.push(message) });
  await copyButton(fixture.first).props.onClick();
  assert.match(errors[0], /复制失败/);
  const tree = nodes(fixture.render());
  assert.ok(tree.some((node) => node.props?.role === "alert"));
  assert.ok(tree.some((node) => node.type === "textarea" && node.props?.readOnly && node.props?.value === "confirmed only"));
  assert.equal(fixture.removed(), 1);
  fixture.cleanup();
});

test("copy button honors disabled and empty text", () => {
  const fixture = copyFixture();
  assert.equal(copyButton(fixture.render({ disabled: true })).props.disabled, true);
  assert.equal(copyButton(fixture.render({ text: "" })).props.disabled, true);
  fixture.cleanup();
});

test("copied confirmation expires before the next copy", async () => {
  const fixture = copyFixture({ clipboard: { writeText: async () => {} } });
  await copyButton(fixture.first).props.onClick();
  fixture.timers.get(1)();
  assert.equal(copyButton(fixture.render()).props.title, "复制进货信息");
  fixture.cleanup();
});

test("clipboard completion after unmount does not create a timer or start a fallback", async () => {
  let resolve;
  const fixture = copyFixture({ clipboard: { writeText: () => new Promise((done) => { resolve = done; }) } });
  const pending = copyButton(fixture.first).props.onClick();
  fixture.cleanup();
  resolve();
  await pending;
  assert.equal(fixture.timers.size, 0);
  assert.equal(fixture.fallbackCalls(), 0);
});

test("dialog copies only successes, shows document numbers separately and distinguishes sales states", () => {
  const helpers = load("purchase-result.ts");
  const Copy = () => null;
  const { PurchaseResultDialog } = load("purchase-result-dialog.tsx", {
    "./purchase-result": helpers, "./purchase-result-copy-button": { PurchaseResultCopyButton: Copy }
  });
  const result = { items: [item], failedItems: [{ productName: "失败商品", color: "黑色", warehouseName: "百鑫仓库", message: "连接中断", uncertain: true }], unprocessedCount: 2, salesStatus: "created", salesNo: "SO-1" };
  for (const [salesStatus, expected] of [["created", "销售单已创建"], ["failed", "销售单创建失败"], ["not_created", "销售单未创建"], ["uncertain", "销售单结果待核实"]]) {
    const tree = PurchaseResultDialog({ result: { ...result, salesStatus }, onClose() {} });
    const entries = nodes(tree);
    assert.ok(entries.some((node) => node.props?.children === "进货结果"));
    assert.equal(JSON.stringify(tree).includes("【进货结果】"), false);
    assert.equal(entries.some((node) => node.props?.children === "重试"), false);
    assert.equal(entries.find((node) => node.type === Copy).props.text, helpers.formatPurchaseResult([item]));
    assert.ok(JSON.stringify(tree).includes(expected));
    assert.ok(JSON.stringify(tree).includes("IN-123"));
    assert.ok(JSON.stringify(tree).includes("连接中断"));
    assert.ok(entries.some((node) => node.type === "pre" && node.props.children === helpers.formatPurchaseResult([item])));
  }
  const empty = PurchaseResultDialog({ result: { ...result, items: [] }, onClose() {} });
  assert.equal(nodes(empty).some((node) => node.type === Copy), false);
  assert.equal(nodes(PurchaseResultDialog({ result: null, onClose() {} })).some((node) => node.type === Copy), false);
});
