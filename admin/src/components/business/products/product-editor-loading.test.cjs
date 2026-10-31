const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function pending() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function effect(id, queries, events) {
  const filename = path.join(__dirname, 'products-page.tsx');
  const source = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const parent = source.statements.find((node) => ts.isFunctionDeclaration(node) && node.name?.text === 'ProductEditorDialog');
  const call = parent.body.statements.map((node) => ts.isExpressionStatement(node) && node.expression)
    .find((node) => node && ts.isCallExpression(node) && node.expression.getText(source) === 'useEffect' && node.arguments[0].getText(source).includes('if (!product) return;'));
  const printed = ts.createPrinter().printNode(ts.EmitHint.Unspecified, call.arguments[0], source);
  const exports = {};
  const ignored = () => {};
  vm.runInNewContext(ts.transpileModule(`exports.effect = ${printed};`, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText, { exports, Promise,
    product: { id, title: `product${id}` }, availableCategories: [],
    setError: (value) => events.push(['error', id, value]), setCropError: ignored, setPendingSquareCrop: ignored,
    setDetailPreviewIndex: ignored, setCategories: ignored, setManufacturers: ignored, setUnits: ignored, setStatuses: ignored, setMediaAssets: ignored,
    setLoading: (value) => events.push(['loading', id, value]), applyProduct: (value) => events.push(['product', value.id]),
    queryKeys: { products: { detail: (id) => ['detail', id], options: (id) => ['options', id] } },
    queryClient: { fetchQuery: ({ queryKey }) => queries[queryKey[0]].promise },
    productDataFromOptions: (options) => options.data || {}, productUnitOptions: (value) => value, productStatusOptions: (value) => value,
  });
  return exports.effect();
}

const flush = () => new Promise((resolve) => setImmediate(resolve));

test('cancel A, open B: late A detail cannot replace B or finalize its loading', async () => {
  const events = [], a = { detail: pending(), options: pending() }, b = { detail: pending(), options: pending() };
  const cancel = effect(1, a, events);
  assert.equal(typeof cancel, 'function', 'editor load effect must invalidate its asynchronous owner');
  cancel();
  effect(2, b, events);
  a.detail.resolve({ id: 1 }); a.options.resolve({});
  await flush();
  assert.equal(events.filter((event) => event[0] === 'product' && event[1] === 1).length, 1, 'only initial A may render');
  assert.equal(events.filter((event) => event[0] === 'loading' && event[1] === 1 && event[2] === false).length, 0);
  b.detail.resolve({ id: 2 }); b.options.resolve({});
  await flush();
  assert.equal(events.filter((event) => event[0] === 'product').at(-1)[1], 2);
});

test('stale rejected queries cannot display errors in the new editor', async () => {
  const events = [], a = { detail: pending(), options: pending() };
  const cancel = effect(1, a, events);
  assert.equal(typeof cancel, 'function');
  cancel();
  a.detail.resolve({ id: 1 }); a.options.reject(new Error('stale failure'));
  await flush();
  assert.equal(events.some((event) => event[0] === 'error' && event[2]), false);
});
