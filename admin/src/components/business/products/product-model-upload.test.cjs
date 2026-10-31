const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load() {
  let last;
  class XHR {
    constructor() { last = this; this.upload = {}; }
    open(method, url) { this.method = method; this.url = url; }
    send(form) { this.form = form; }
  }
  class FormData { append(key, value) { this[key] = value; } }
  const exports = {};
  const source = ts.transpileModule(fs.readFileSync(path.resolve(__dirname, '../../../api.ts'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  vm.runInNewContext(source, { exports, XMLHttpRequest: XHR, FormData, Number, Error, JSON });
  return { api: exports.api, xhr: () => last };
}

test('model uploads use real transport progress and retain credentials', async () => {
  const { api, xhr } = load();
  assert.equal(typeof api.uploadProductModel, 'function', 'model upload API is missing');
  const progress = [];
  const promise = api.uploadProductModel({ name: 'box.glb', size: 100 }, (value) => progress.push(value));
  const request = xhr();
  assert.equal(request.method, 'POST');
  assert.equal(request.url, '/api/product/models/upload');
  assert.equal(request.withCredentials, true);
  assert.equal(request.form.model.name, 'box.glb');
  request.upload.onprogress({ lengthComputable: true, loaded: 25, total: 100 });
  request.upload.onprogress({ lengthComputable: false });
  assert.deepEqual(progress, [25]);
  request.status = 200; request.responseText = JSON.stringify({ code: 0, data: { id: 9, url: 'https://assets/box.glb' } });
  request.onload();
  assert.equal((await promise).id, 9);
});

test('model upload errors cannot be mistaken for a successful asset', async () => {
  for (const mode of ['http', 'body', 'network', 'timeout']) {
    const { api, xhr } = load();
    assert.equal(typeof api.uploadProductModel, 'function');
    const promise = api.uploadProductModel({ name: 'box.glb', size: 100 });
    const check = assert.rejects(promise);
    const request = xhr();
    if (mode === 'network') request.onerror();
    else if (mode === 'timeout') request.ontimeout();
    else { request.status = mode === 'http' ? 413 : 200; request.responseText = mode === 'http' ? '{"code":413,"msg":"too large"}' : '{"code":0,"data":{}}'; request.onload(); }
    await check;
  }
});
