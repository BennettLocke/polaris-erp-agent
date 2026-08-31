const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const ts = require("typescript");

function loadTypeScript(filename, globals = {}) {
  assert.ok(fs.existsSync(filename), `Missing implementation: ${filename}`);
  const source = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  }).outputText;
  const exports = {};
  vm.runInNewContext(source, { exports, ...globals }, { filename });
  return exports;
}

function helpers() {
  return loadTypeScript(path.join(__dirname, "bag-upload-dialog.helpers.ts"));
}

function componentFunction(filename, component, name, globals) {
  const source = ts.createSourceFile(filename, fs.readFileSync(path.join(__dirname, filename), "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const parent = source.statements.find((node) => ts.isFunctionDeclaration(node) && node.name?.text === component);
  const declaration = parent?.body?.statements.find((node) => ts.isFunctionDeclaration(node) && node.name?.text === name);
  assert.ok(declaration, `Missing ${component}.${name}`);
  const printed = ts.createPrinter().printNode(ts.EmitHint.Unspecified, declaration, source);
  const code = ts.transpileModule(`${printed}\nexports.extracted = ${name};`, {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS }
  }).outputText;
  const exports = {};
  vm.runInNewContext(code, { exports, ...globals });
  return exports.extracted;
}

test("both bag shortcuts preserve pending and composer state without sending chat", () => {
  const pending = { pending_action: "confirm_sales", state: { customer: "existing", qty: 2 } };
  const originalPending = JSON.stringify(pending);
  let input = "existing draft";
  let opens = 0;
  class HTMLElement {}
  const trigger = new HTMLElement();
  const forbidden = () => assert.fail("Bag upload must not touch server or pending state");
  const insert = componentFunction("workbench-page.tsx", "WorkbenchPage", "insertCommand", {
    HTMLElement, document: { activeElement: trigger }, bagUploadTriggerRef: { current: null },
    setBagUploadOpen: (open) => { assert.equal(open, true); opens += 1; },
    setInput: (update) => { input = update(input); },
    sessionSnapshot: pending, setSessionSnapshot: forbidden, setFiles: forbidden,
    sendMessage: forbidden, api: { agentChat: forbidden, updateSessionPending: forbidden }
  });
  insert("上传泡袋");
  insert("泡袋上传");
  assert.equal(opens, 2);
  assert.equal(input, "existing draft");
  assert.equal(JSON.stringify(pending), originalPending);
  insert("开单");
  assert.equal(input, "开单 existing draft");
  assert.equal(opens, 2);
});

test("completion appends only a local summary and leaves pending untouched", () => {
  const messages = [];
  const history = [];
  const forbidden = () => assert.fail("Completion must not refresh or mutate the session");
  const complete = componentFunction("workbench-page.tsx", "WorkbenchPage", "completeBagUpload", {
    appendMessage: (...args) => messages.push(args), pushBusinessHistory: (...args) => history.push(args),
    sendMessage: forbidden, setSessionSnapshot: forbidden, setInput: forbidden, setFiles: forbidden,
    api: { agentChat: forbidden, agentHistory: forbidden, updateSessionPending: forbidden }
  });
  complete({ summary: "one success", total: 1, success: [{}], failures: [] }, "design.zip");
  assert.deepEqual(messages, [["assistant", "泡袋上传：design.zip\none success", undefined, "bag-upload"]]);
  assert.deepEqual(history, [["泡袋上传：design.zip\none success"]]);
});

test("each bag type resets the edited price to its own default", () => {
  const { changeBagType, initialBagUploadForm } = helpers();
  let form = initialBagUploadForm();
  assert.equal(form.bagType, "岩茶");
  assert.equal(form.price, "18");
  assert.equal(form.isListed, true);
  for (const [bagType, price] of [["红茶", "10"], ["宽版", "18"], ["岩茶", "18"]]) {
    form = changeBagType({ ...form, price: "25.50", isListed: false }, bagType);
    assert.equal(form.bagType, bagType);
    assert.equal(form.price, price);
    assert.equal(form.isListed, false);
  }
  assert.equal(changeBagType(form, ""), form);
  assert.equal(changeBagType(form, "unknown"), form);
});

test("price must be a positive decimal with at most two decimal places", () => {
  const { isValidBagPrice } = helpers();
  for (const value of ["18", "10.5", "0.01", "18.00", "001.20", "9999999999.99"]) assert.equal(isValidBagPrice(value), true, value);
  for (const value of ["", "0", "0.00", "-1", "+1", "1.234", "1e2", "Infinity", "NaN", ".5", "18.", " 18 ", "1,000", "10000000000", "9999999999.999", "00000000001", "9".repeat(400)]) {
    assert.equal(isValidBagPrice(value), false, value);
  }
});

test("ZIP validation requires one nonempty zip filename within the server limit", () => {
  const { validateBagArchive } = helpers();
  assert.equal(validateBagArchive({ name: "design.ZIP", size: 1024, type: "" }, 1024), "");
  assert.equal(validateBagArchive({ name: "design.zip", size: 1, type: "application/octet-stream" }, 1024), "");
  for (const file of [null, { name: "design.rar", size: 1 }, { name: "fake.png", size: 1, type: "application/zip" }, { name: "empty.zip", size: 0 }, { name: "large.zip", size: 1025 }]) {
    assert.ok(validateBagArchive(file, 1024));
  }
  for (const limit of [null, 0, -1, NaN]) assert.ok(validateBagArchive({ name: "a.zip", size: 1 }, limit));
});

test("synchronous submission lock rejects double clicks and terminal batches", () => {
  const { canStartBagUpload, claimBagUpload } = helpers();
  const valid = { phase: "idle", price: "18", archive: { name: "a.zip", size: 1 }, archiveBytes: 1024 };
  assert.equal(canStartBagUpload(valid), true);
  const lock = { current: false };
  assert.equal(claimBagUpload(lock, valid), true);
  assert.equal(claimBagUpload(lock, valid), false);
  for (const phase of ["uploading", "complete", "uncertain"]) {
    assert.equal(canStartBagUpload({ ...valid, phase }), false);
    assert.equal(claimBagUpload({ current: false }, { ...valid, phase }), false);
  }
  for (const changes of [{ price: "0" }, { archive: null }, { archiveBytes: null }]) {
    assert.equal(claimBagUpload({ current: false }, { ...valid, ...changes }), false);
  }
});

test("resolved batches cannot resubmit even after the busy lock is released", () => {
  const { claimBagUpload } = helpers();
  const lock = { current: false };
  const submission = { phase: "idle", price: "18", archive: { name: "a.zip", size: 1 }, archiveBytes: 1024 };
  assert.equal(claimBagUpload(lock, submission), true);
  for (const phase of ["complete", "uncertain"]) {
    lock.current = false;
    assert.equal(claimBagUpload(lock, { ...submission, phase }), false);
  }
});

function loadApi(response, thrown) {
  const requests = [];
  class FormData {
    constructor() { this.entries = []; }
    append(...args) { this.entries.push(args); }
  }
  const { api, ApiError } = loadTypeScript(path.resolve(__dirname, "../../../api.ts"), {
    FormData,
    fetch: async (url, init) => {
      requests.push({ url, init });
      if (thrown) throw thrown;
      return response;
    }
  });
  return { api, ApiError, requests };
}

function uploadHarness(uploadBags, ApiError = class extends Error {}) {
  const phaseRef = { current: "idle" };
  const submitLock = { current: false };
  const phases = [];
  const errors = [];
  const results = [];
  let completions = 0;
  let closes = 0;
  const globals = {
    phaseRef, submitLock, ApiError, archive: { name: "a.zip", size: 1 },
    submission: { phase: "idle", price: "18", archive: { name: "a.zip", size: 1 }, archiveBytes: 1024 },
    form: { bagType: "岩茶", price: "18", isListed: true }, claimBagUpload: helpers().claimBagUpload,
    api: { uploadBags }, queryClient: { invalidateQueries: async () => {} }, queryKeys: { products: { root: ["products"] } },
    setError: (value) => errors.push(value), setPhase: (value) => phases.push(value), setResult: (value) => results.push(value),
    onComplete: () => { completions += 1; }, onClose: () => { closes += 1; }
  };
  return {
    start: componentFunction("bag-upload-dialog.tsx", "BagUploadDialog", "startUpload", globals),
    close: componentFunction("bag-upload-dialog.tsx", "BagUploadDialog", "changeOpen", globals),
    phaseRef, submitLock, phases, errors, results,
    completions: () => completions, closes: () => closes
  };
}

test("in-flight requests block close and duplicates; settled success is terminal", async () => {
  let resolve;
  let calls = 0;
  const result = { success: [], failures: [], summary: "done" };
  const harness = uploadHarness(() => { calls += 1; return new Promise((done) => { resolve = done; }); });
  const pending = harness.start();
  assert.equal(harness.submitLock.current, true);
  harness.close(false);
  assert.equal(harness.closes(), 0);
  await harness.start();
  assert.equal(calls, 1);
  resolve(result);
  await pending;
  assert.equal(harness.phaseRef.current, "complete");
  assert.equal(harness.completions(), 1);
  assert.equal(harness.results[0], result);
  await harness.start();
  assert.equal(calls, 1);
  harness.close(false);
  assert.equal(harness.closes(), 1);
});

test("network and 5xx outcomes cannot resend; HTTP 400 can be corrected explicitly", async () => {
  const { ApiError } = loadApi(null);
  for (const error of [new TypeError("connection lost"), new ApiError("failure", 500), new ApiError("gateway timeout", 504)]) {
    let calls = 0;
    const harness = uploadHarness(async () => { calls += 1; throw error; }, ApiError);
    await harness.start();
    assert.equal(harness.phaseRef.current, "uncertain");
    assert.match(harness.errors.at(-1), /先核对商品库/);
    assert.equal(harness.completions(), 0);
    await harness.start();
    assert.equal(calls, 1);
    harness.close(false);
    assert.equal(harness.closes(), 1);
  }
  let calls = 0;
  const rejected = uploadHarness(async () => { calls += 1; throw new ApiError("invalid ZIP", 400); }, ApiError);
  await rejected.start();
  assert.equal(rejected.phaseRef.current, "idle");
  assert.equal(calls, 1);
  await rejected.start();
  assert.equal(calls, 2);
});

test("upload API sends one multipart request with decimal string and listing flags", async () => {
  const data = { bag_type: "红茶", price: 10.25, is_listed: true, total: 0, success: [], failures: [], summary: "done" };
  const { api, requests } = loadApi({ ok: true, status: 200, json: async () => ({ code: 0, data }) });
  const archive = { name: "design.zip", size: 10 };
  assert.equal(await api.uploadBags(archive, { bag_type: "红茶", price: "10.25", is_listed: true }), data);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, "/api/product/bag-upload");
  assert.equal(requests[0].init.method, "POST");
  assert.equal(requests[0].init.credentials, "include");
  assert.equal(requests[0].init.headers, undefined);
  assert.equal(JSON.stringify(requests[0].init.body.entries), JSON.stringify([
    ["archive", archive, "design.zip"], ["bag_type", "红茶"], ["price", "10.25"], ["is_listed", "1"]
  ]));
  await api.uploadBags(archive, { bag_type: "岩茶", price: "18.00", is_listed: false });
  assert.equal(requests[1].init.body.entries.find(([key]) => key === "is_listed")[1], "0");
});

test("HTTP errors and nonzero result codes fail without automatic retries", async () => {
  for (const [status, code] of [[200, 1], [400, 0], [413, -1], [500, 0], [502, -1]]) {
    const { api, ApiError, requests } = loadApi({ ok: status < 400, status, json: async () => ({ code, msg: "failure" }) });
    await assert.rejects(api.uploadBags({ name: "a.zip" }, { bag_type: "岩茶", price: "18", is_listed: false }), (error) => error instanceof ApiError && error.status === status);
    assert.equal(requests.length, 1);
  }
  const error = new TypeError("network lost");
  const { api, requests } = loadApi(null, error);
  await assert.rejects(api.uploadBags({ name: "a.zip" }, { bag_type: "岩茶", price: "18", is_listed: true }), (caught) => caught === error);
  assert.equal(requests.length, 1);
});
