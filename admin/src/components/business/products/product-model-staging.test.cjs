const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load() {
  const filename = path.join(__dirname, 'product-model-staging.ts');
  assert.ok(fs.existsSync(filename), 'staged cleanup retry helper is missing');
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports, Promise });
  return exports;
}
function release() { return load().releaseStagedModelUploads; }

test('failed requests and incomplete OSS deletion retain their IDs for retry', async () => {
  const cleanup = release();
  const staged = new Set([1, 2, 3]);
  await cleanup(staged, async (id) => {
    if (id === 1) throw Error('network');
    return { storage_deleted: id === 3 };
  });
  assert.deepEqual([...staged], [1, 2]);
  const retried = [];
  await cleanup(staged, async (id) => { retried.push(id); return { storage_deleted: true }; });
  assert.deepEqual(retried, [1, 2]);
  assert.equal(staged.size, 0);
});

test('the committed model is removed from cleanup without deletion, newly staged IDs are retained', async () => {
  const cleanup = release();
  const staged = new Set([1, 2]);
  const deleted = [];
  await cleanup(staged, async (id) => { deleted.push(id); staged.add(3); return { storage_deleted: true }; }, 2);
  assert.deepEqual(deleted, [1]);
  assert.deepEqual([...staged], [3]);
});

test('cleanup retries never claim a new upload from a reopened editor', async () => {
  const { queueStagedModelUploads, releaseStagedModelUploads } = load();
  assert.equal(typeof queueStagedModelUploads, 'function');
  const staged = new Set([1, 2]), queue = new Set();
  queueStagedModelUploads(staged, queue, 2);
  assert.equal(staged.size, 0);
  assert.deepEqual([...queue], [1]);
  await releaseStagedModelUploads(queue, async () => ({ storage_deleted: false }));
  staged.add(3);
  const deleted = [];
  await releaseStagedModelUploads(queue, async (id) => { deleted.push(id); return { storage_deleted: true }; });
  assert.deepEqual(deleted, [1]);
  assert.deepEqual([...staged], [3]);
});
