import assert from "node:assert/strict";
import test from "node:test";

import {
  commitSalesNumberDraft,
  parseSalesNumberDraft
} from "../admin/src/components/business/sales-create/sales-number-input-state.ts";

test("an empty quantity draft stays temporary and does not replace the valid value", () => {
  assert.equal(parseSalesNumberDraft("", 1), null);
  assert.equal(commitSalesNumberDraft("", 24, 1), 24);
});

test("a newly typed positive quantity becomes the committed value", () => {
  assert.equal(parseSalesNumberDraft("24", 1), 24);
  assert.equal(commitSalesNumberDraft("24", 3, 1), 24);
  assert.equal(commitSalesNumberDraft("10.5", 3, 1), 10.5);
});

test("zero, negative, and invalid quantity drafts restore the previous valid value", () => {
  assert.equal(parseSalesNumberDraft("0", 1), null);
  assert.equal(parseSalesNumberDraft("-3", 1), null);
  assert.equal(parseSalesNumberDraft("abc", 1), null);
  assert.equal(commitSalesNumberDraft("0", 6, 1), 6);
  assert.equal(commitSalesNumberDraft("-3", 6, 1), 6);
  assert.equal(commitSalesNumberDraft("abc", 6, 1), 6);
});
