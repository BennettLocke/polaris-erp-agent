import assert from "node:assert/strict";
import test from "node:test";

import { createSalesDraftSession, salesDraftStorageKey } from "../admin/src/components/business/sales-create/sales-draft-state.ts";

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key)
  };
}

const defaults = () => ({
  selectedCustomer: null, customerKeyword: "", productKeyword: "", lines: [],
  defaultWarehouseId: 2, lineQty: 1, createTime: "2026-10-27T10:00",
  payStatus: "paid", payType: "wechat"
});
const line = { product_id: 1046, spu_id: 100, unit_id: 1, title: "喜悦半斤", spec: "红色", buy_number: 24, price: 20, warehouse_id: 1, price_source: "manual_override" };
const session = (storage, account = 7) => createSalesDraftSession(account, defaults, () => storage);

test("restores customer, lines, manual prices, warehouse and payment after refresh", () => {
  const storage = memoryStorage();
  const first = session(storage);
  first.setField("selectedCustomer", { id: 3, name: "齐唯" });
  first.setField("customerKeyword", "齐唯");
  first.setField("lines", [line, { ...line, product_id: 1047, spec: "黄色", buy_number: 6 }]);
  first.setField("productKeyword", "喜悦");
  first.setField("defaultWarehouseId", 1);
  first.setField("lineQty", 2.5);
  first.setField("payStatus", "monthly");
  first.setField("payType", "monthly");
  assert.deepEqual(session(storage).getSnapshot().draft, first.getSnapshot().draft);
  assert.equal(session(storage).getSnapshot().hasDraft, true);
});

test("a saved draft and user edits win over late default customer and warehouse responses", () => {
  const storage = memoryStorage();
  const first = session(storage);
  const revision = first.getRevision();
  first.setField("lines", [line]);
  first.setField("selectedCustomer", { id: 3, name: "齐唯" });
  first.initialize({ selectedCustomer: { id: 1, name: "散客" }, defaultWarehouseId: 2 }, revision);
  const restored = session(storage);
  restored.initialize({ defaultWarehouseId: 2 }, restored.getRevision());
  assert.equal(restored.getSnapshot().draft.selectedCustomer.id, 3);
  assert.equal(restored.getSnapshot().draft.lines[0].price, 20);
  assert.equal(restored.getSnapshot().draft.lines[0].warehouse_id, 1);
});

test("defaults do not create a persisted draft; clear invalidates in-flight defaults", () => {
  const storage = memoryStorage();
  const current = session(storage);
  current.initialize({ defaultWarehouseId: 1 }, current.getRevision());
  assert.equal(storage.getItem(salesDraftStorageKey(7)), null);
  const oldRevision = current.getRevision();
  current.reset();
  current.initialize({ selectedCustomer: { id: 1, name: "散客" } }, oldRevision);
  assert.equal(current.getSnapshot().draft.selectedCustomer, null);
});

test("submission failure keeps the draft; successful reset clears it even while page is away", () => {
  const storage = memoryStorage();
  const current = session(storage);
  current.setField("lines", [line]);
  current.setSubmitting(true);
  current.setSubmitting(false);
  assert.equal(session(storage).getSnapshot().draft.lines.length, 1);
  current.setSubmitting(true);
  current.reset({ ...current.getSnapshot().draft, lines: [] });
  current.setSubmitting(false);
  assert.equal(storage.getItem(salesDraftStorageKey(7)), null);
  assert.equal(session(storage).getSnapshot().draft.lines.length, 0);
});

test("submitting locks edits so an old request cannot clear newer form contents", () => {
  const current = session(memoryStorage());
  current.setField("lines", [line]);
  current.setSubmitting(true);
  current.setField("lines", []);
  assert.equal(current.getSnapshot().draft.lines.length, 1);
  assert.equal(current.getSnapshot().submitting, true);
});

test("different accounts and different tab storage do not overwrite each other", () => {
  const tab = memoryStorage();
  session(tab, 7).setField("lines", [line]);
  assert.equal(session(tab, 8).getSnapshot().draft.lines.length, 0);
  assert.equal(session(memoryStorage(), 7).getSnapshot().draft.lines.length, 0);
  session(tab, 8).setField("productKeyword", "墨香");
  session(tab, 7).reset();
  assert.equal(session(tab, 8).getSnapshot().draft.productKeyword, "墨香");
});

test("corrupt, mismatched account, obsolete version and invalid numeric data reset safely", () => {
  for (const corrupt of ["{broken", "null", JSON.stringify({ version: 99 }),
    JSON.stringify({ version: 1, accountId: 8, draft: defaults() }),
    JSON.stringify({ version: 1, accountId: 7, draft: { ...defaults(), lines: [{ ...line, buy_number: -1 }] } })]) {
    const storage = memoryStorage();
    storage.setItem(salesDraftStorageKey(7), corrupt);
    assert.deepEqual(session(storage).getSnapshot().draft, defaults());
    assert.equal(storage.getItem(salesDraftStorageKey(7)), null);
  }
});

test("blocked storage keeps a working in-memory draft and exposes a warning", () => {
  const current = createSalesDraftSession(7, defaults, () => { throw new Error("blocked"); });
  current.setField("lines", [line]);
  assert.equal(current.getSnapshot().draft.lines.length, 1);
  assert.equal(current.getSnapshot().storageAvailable, false);
  assert.doesNotThrow(() => current.reset());
});

test("quota failures do not break editing or overwrite the latest valid quantity", () => {
  const storage = memoryStorage();
  storage.setItem = () => { throw new Error("quota"); };
  const current = session(storage);
  current.setField("lines", [line]);
  current.setField("lineQty", 24);
  assert.equal(current.getSnapshot().draft.lineQty, 24);
  assert.equal(current.getSnapshot().storageAvailable, false);
});

test("subscriptions see the latest snapshot and can unsubscribe", () => {
  const current = session(memoryStorage());
  let changes = 0;
  const stop = current.subscribe(() => changes++);
  current.setField("lines", [line]);
  stop();
  current.setField("lineQty", 2);
  assert.equal(changes, 1);
  assert.equal(current.getSnapshot().draft.lineQty, 2);
});

test("logout clears only this account and late callbacks cannot rewrite a new login's draft", () => {
  const storage = memoryStorage();
  const old = session(storage);
  old.setField("lines", [line]);
  old.endSession();
  assert.equal(storage.getItem(salesDraftStorageKey(7)), null);
  const nextLogin = session(storage);
  nextLogin.setField("productKeyword", "墨香");
  old.setField("lines", [line]);
  old.reset();
  old.initialize({ selectedCustomer: { id: 1, name: "散客" } }, old.getRevision());
  assert.equal(session(storage).getSnapshot().draft.productKeyword, "墨香");
  assert.equal(session(storage).getSnapshot().draft.lines.length, 0);
});

test("clearing or logout invalidates asynchronous work from the old draft", () => {
  const current = session(memoryStorage());
  const before = current.getGeneration();
  assert.equal(current.isCurrent(before), true);
  current.reset();
  assert.equal(current.isCurrent(before), false);
  const afterClear = current.getGeneration();
  current.endSession();
  assert.equal(current.isCurrent(afterClear), false);
});

test("refresh during submission requires review instead of silently enabling another order", () => {
  const storage = memoryStorage();
  const current = session(storage);
  current.setField("lines", [line]);
  current.setSubmitting(true);
  const refreshed = session(storage);
  assert.equal(refreshed.getSnapshot().submitting, false);
  assert.equal(refreshed.getSnapshot().needsSubmissionReview, true);
  refreshed.setField("lines", []);
  assert.equal(refreshed.getSnapshot().draft.lines.length, 1);
  refreshed.acknowledgeSubmissionReview();
  refreshed.setField("lineQty", 2);
  assert.equal(session(storage).getSnapshot().needsSubmissionReview, false);
  assert.equal(session(storage).getSnapshot().draft.lineQty, 2);
});
