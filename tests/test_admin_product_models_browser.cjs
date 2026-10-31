// Runs against the isolated model_demo environment, never a production login.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require(process.env.SJAGENT_PLAYWRIGHT_PATH || 'playwright');
const root = path.resolve(__dirname, '..');
const url = 'http://127.0.0.1:5179';

function triangle() {
  const binary = Buffer.from(new Float32Array([-1, -1, 0, 1, -1, 0, 0, 1, 0]).buffer);
  const doc = { asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [0] }], nodes: [{ mesh: 0 }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0 } }] }], buffers: [{ byteLength: binary.length }],
    bufferViews: [{ buffer: 0, byteLength: binary.length }],
    accessors: [{ bufferView: 0, componentType: 5126, count: 3, type: 'VEC3', min: [-1, -1, 0], max: [1, 1, 0] }] };
  const json = Buffer.from(JSON.stringify(doc));
  const padded = Buffer.alloc(Math.ceil(json.length / 4) * 4, 32); json.copy(padded);
  const header = Buffer.alloc(20); header.writeUInt32LE(0x46546c67); header.writeUInt32LE(2, 4);
  header.writeUInt32LE(28 + padded.length + binary.length, 8); header.writeUInt32LE(padded.length, 12); header.writeUInt32LE(0x4e4f534a, 16);
  const binHeader = Buffer.alloc(8); binHeader.writeUInt32LE(binary.length); binHeader.writeUInt32LE(0x004e4942, 4);
  return Buffer.concat([header, padded, binHeader, binary]);
}

async function pixels(page) {
  return page.locator('.product-model-preview-dialog canvas').evaluate((canvas) => new Promise((resolve) => requestAnimationFrame(() => {
    const copy = document.createElement('canvas'); copy.width = canvas.width; copy.height = canvas.height;
    const ctx = copy.getContext('2d'); ctx.drawImage(canvas, 0, 0);
    const data = ctx.getImageData(0, 0, copy.width, copy.height).data;
    let count = 0, minX = copy.width, minY = copy.height, maxX = 0, maxY = 0, hash = 2166136261;
    for (let y = 0; y < copy.height; y += 3) for (let x = 0; x < copy.width; x += 3) {
      const i = (y * copy.width + x) * 4;
      hash = Math.imul(hash ^ data[i], 16777619);
      if (data[i + 3] > 128 && data[i] > data[i + 1] * 1.2 && data[i] > data[i + 2] * 1.2 && data[i] > 40) {
        count++; minX = Math.min(minX, x); minY = Math.min(minY, y); maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
      }
    }
    resolve({ count, minX, minY, maxX, maxY, hash, width: copy.width, height: copy.height });
  })));
}

async function editor(page) {
  const card = page.locator('.product-spu-card').filter({ hasText: '【模型测试】三小盒' }).first();
  await card.getByRole('button', { name: '编辑', exact: true }).click();
  await page.getByRole('tab', { name: '3D 模型', exact: true }).click();
  await page.locator('.product-editor-dialog').getByRole('button', { name: '保存商品', exact: true }).waitFor();
  await page.waitForFunction(() => !document.querySelector('.product-editor-dialog button:last-child')?.disabled);
}

async function readyPreview(page) {
  for (let attempt = 0; attempt < 2; attempt++) {
    await page.waitForFunction(() => ['ready', 'error'].includes(document.querySelector('.product-model-preview-stage')?.dataset.state));
    if (await page.locator('.product-model-preview-stage').getAttribute('data-state') === 'ready') return;
    const message = await page.locator('.product-model-preview-stage').innerText();
    if (attempt || !/fetch|network|读取模型失败/i.test(message)) throw Error(`Model preview failed: ${message}`);
    console.log('retrying a transient model network failure');
    await page.locator('.product-model-preview-stage').getByRole('button', { name: '重试', exact: true }).click();
  }
}

(async () => {
  await fs.mkdir(path.join(root, '.tmp'), { recursive: true });
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    args: ['--enable-webgl', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const errors = [], modelRequests = [], failedRequests = [];
  let lastPage;
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const login = await context.request.post(`${url}/api/web-auth/login`, { data: { username: 'model_demo', password: 'ModelPreview123!' } });
    assert.equal((await login.json()).code, 0, 'isolated demo login');
    const me = await (await context.request.get(`${url}/api/web-auth/me`)).json();
    assert.equal(me.data.user.username, 'model_demo', 'refuse to run against a real business account');
    const page = await context.newPage();
    lastPage = page;
    page.setDefaultTimeout(90000);
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('requestfailed', (request) => failedRequests.push({ url: request.url(), error: request.failure()?.errorText }));
    page.on('request', (request) => { if (/\.glb(?:\?|$)/.test(request.url())) modelRequests.push(request.url()); });
    await page.goto(`${url}/admin/products`);
    await editor(page);
    assert.equal(modelRequests.length, 0, 'model is not downloaded by list or editor');
    await page.locator('input[aria-label="选择 GLB 模型"]').setInputFiles({ name: 'wrong.blend', buffer: Buffer.from('x') });
    await page.getByRole('alert').filter({ hasText: '只支持' }).waitFor();
    const response = page.waitForResponse((response) => response.url().endsWith('/api/product/models/upload') && response.request().method() === 'POST');
    await page.locator('input[aria-label="选择 GLB 模型"]').setInputFiles('C:/Users/chuji/Desktop/测试.glb');
    const asset = (await (await response).json()).data;
    assert.ok(asset?.id && asset.url, 'real OSS upload and DB registration succeeded');
    await page.locator('.product-model-file').getByText('测试.glb', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(root, '.tmp/product-model-editor-desktop.png') });
    await page.getByRole('button', { name: '预览', exact: true }).click();
    await readyPreview(page);
    assert.equal(await page.locator('.product-model-preview-canvas').getAttribute('data-animation-count'), '4');
    const closed = await pixels(page);
    assert.ok(closed.count > 1000, 'closed model renders actual pixels');
    await page.screenshot({ path: path.join(root, '.tmp/product-model-preview-desktop-closed.png') });
    await page.getByRole('button', { name: '打开礼盒', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('.product-model-preview-canvas')?.dataset.pose === 'open');
    const opened = await pixels(page);
    assert.notEqual(opened.hash, closed.hash, 'opening animation changes real geometry');
    assert.ok(opened.minX > 5 && opened.maxX < opened.width - 5 && opened.minY > 5 && opened.maxY < opened.height - 5, 'open model fits');
    await page.screenshot({ path: path.join(root, '.tmp/product-model-preview-desktop-open.png') });
    const canvas = page.locator('.product-model-preview-dialog canvas');
    const bounds = await canvas.boundingBox();
    await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
    await page.mouse.down(); await page.mouse.move(bounds.x + bounds.width / 2 + 100, bounds.y + bounds.height / 2 + 30, { steps: 10 }); await page.mouse.up();
    await page.waitForTimeout(400);
    assert.notEqual((await pixels(page)).hash, opened.hash, 'orbit remains interactive');
    await page.getByRole('button', { name: '重置视角', exact: true }).click();
    await page.locator('.product-model-preview-dialog .sj-dialog-close').click();
    const save = page.waitForResponse((response) => response.url().endsWith('/api/product/save'));
    await page.getByRole('button', { name: '保存商品', exact: true }).click();
    const product = (await (await save).json()).data;
    for (const sku of product.sku_ids) {
      const detail = await (await context.request.get(`${url}/api/product/${sku}`)).json();
      assert.equal(detail.data.model.id, asset.id, 'every SKU color shares the SPU model');
    }
    console.log('real OSS rendering, animation, save and shared-color binding verified');

    await editor(page);
    await page.getByRole('button', { name: '解除绑定', exact: true }).click();
    await page.getByRole('button', { name: '取消', exact: true }).click();
    let detail = await (await context.request.get(`${url}/api/product/${product.id}`)).json();
    assert.equal(detail.data.model.id, asset.id, 'cancelled unbind does not affect the saved model');
    await editor(page);
    const replacement = page.waitForResponse((response) => response.url().endsWith('/api/product/models/upload'));
    await page.locator('input[aria-label="选择 GLB 模型"]').setInputFiles({ name: 'static.glb', buffer: triangle() });
    const staged = (await (await replacement).json()).data;
    await page.getByRole('button', { name: '预览', exact: true }).click();
    await readyPreview(page);
    assert.equal(await page.getByRole('button', { name: '打开礼盒', exact: true }).count(), 0, 'static model has no fake animation');
    await page.locator('.product-model-preview-dialog .sj-dialog-close').click();
    const clean = page.waitForResponse((response) => response.url().endsWith(`/models/${staged.id}/pending`) && response.request().method() === 'DELETE');
    await page.getByRole('button', { name: '取消', exact: true }).click();
    assert.equal((await (await clean).json()).data.storage_deleted, true, 'cancel reclaims the staged OSS object');
    detail = await (await context.request.get(`${url}/api/product/${product.id}`)).json();
    assert.equal(detail.data.model.id, asset.id, 'cancelled replacement preserves the saved model');

    await page.setViewportSize({ width: 390, height: 844 });
    await editor(page);
    await page.screenshot({ path: path.join(root, '.tmp/product-model-editor-mobile.png') });
    await page.getByRole('button', { name: '预览', exact: true }).click();
    await readyPreview(page);
    await page.getByRole('slider', { name: '礼盒打开程度' }).fill('100');
    const mobile = await pixels(page);
    assert.ok(mobile.count > 400, 'mobile model is nonblank');
    assert.ok(mobile.minX > 2 && mobile.maxX < mobile.width - 2 && mobile.minY > 2 && mobile.maxY < mobile.height - 2, 'mobile framing fits');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: path.join(root, '.tmp/product-model-preview-mobile.png') });
    await page.locator('.product-model-preview-dialog .sj-dialog-close').click();
    await page.getByRole('button', { name: '取消', exact: true }).click();
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ assetId: asset.id, productId: product.id, closed, opened, mobile,
      checks: ['no-eager-glb', 'upload', 'OSS-CORS', 'materials', 'animation', 'orbit', 'same-spu-colors', 'cancel-unbind', 'cancel-replacement', 'cleanup', 'static', 'mobile'], errors }, null, 2));
  } catch (error) {
    if (lastPage) {
      console.error('preview diagnostics', await lastPage.locator('.product-model-preview-stage').innerText().catch(() => ''), failedRequests.slice(-4));
      await lastPage.screenshot({ path: path.join(root, '.tmp/product-model-browser-failure.png') }).catch(() => undefined);
    }
    throw error;
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
