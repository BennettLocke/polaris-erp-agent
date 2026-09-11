import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import ts from '../admin/node_modules/typescript/lib/typescript.js';
import { build } from '../admin/node_modules/esbuild/lib/main.js';

const bundled = await build({
  entryPoints: [fileURLToPath(new URL('../admin/src/api.ts', import.meta.url))],
  bundle: true, write: false, format: 'esm', platform: 'node',
});
const { api } = await import(`data:text/javascript;base64,${Buffer.from(bundled.outputFiles[0].text).toString('base64')}`);
const limits = { image_bytes: 25 * 1024 * 1024, archive_bytes: 100 * 1024 * 1024 };

test('oversized ZIP is rejected before an upload request', async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return Response.json({ code: 0, data: limits });
  };
  const file = new File(['x'], 'too-large.zip', { type: 'application/zip' });
  Object.defineProperty(file, 'size', { value: 101 * 1024 * 1024 });
  await assert.rejects(api.uploadAgentImage(file, 'test'), /100MB/);
  assert.deepEqual(calls, ['/api/images/upload-limits']);
});

test('ZIP above 25MB is sent but an image of that size is rejected', async () => {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return Response.json({ code: 0, data: url.endsWith('upload-limits') ? limits : { response: 'done' } });
  };
  const zip = new File(['x'], 'batch.ZIP');
  Object.defineProperty(zip, 'size', { value: 56 * 1024 * 1024 });
  await api.uploadAgentImage(zip, 'test');
  assert.ok(calls.includes('/api/images/upload'));
  calls.length = 0;
  const png = new File(['x'], 'large.png', { type: 'image/png' });
  Object.defineProperty(png, 'size', { value: 26 * 1024 * 1024 });
  await assert.rejects(api.uploadAgentImage(png, 'test'), /25MB/);
  assert.ok(!calls.includes('/api/images/upload'));
});

test('proxy HTML 413 is translated into a readable error', async () => {
  globalThis.fetch = async (url) => url.endsWith('upload-limits')
    ? Response.json({ code: 0, data: limits })
    : new Response('<html>Request Entity Too Large</html>', { status: 413, statusText: 'Request Entity Too Large' });
  await assert.rejects(api.uploadAgentImage(new File(['x'], 'batch.zip'), 'test'), /文件过大|大小限制/);
});

test('multiple design images are sent in one batch request', async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    return Response.json({
      code: 0,
      data: url.endsWith('upload-limits') ? limits : { response: 'done', batch: { total_files: 2, files: [] } },
    });
  };
  const files = [new File(['a'], 'first.png'), new File(['b'], 'second.jpg')];

  await api.uploadAgentImages(files, 'test-session', 'batch-123');

  assert.equal(calls[1].url, '/api/images/upload-batch');
  assert.deepEqual(calls[1].init.body.getAll('images').map(file => file.name), ['first.png', 'second.jpg']);
  assert.equal(calls[1].init.body.get('session_id'), 'test-session');
  assert.equal(calls[1].init.body.get('batch_id'), 'batch-123');
});

test('design image batch rejects ZIP files and totals above 100MB', async () => {
  globalThis.fetch = async () => Response.json({ code: 0, data: limits });
  await assert.rejects(api.uploadAgentImages([new File(['x'], 'bags.zip')], 'test', 'zip-batch'), /ZIP/);

  const largeBatch = Array.from({ length: 5 }, (_, index) => {
    const file = new File(['x'], `design-${index}.png`);
    Object.defineProperty(file, 'size', { value: 21 * 1024 * 1024 });
    return file;
  });
  await assert.rejects(api.uploadAgentImages(largeBatch, 'test', 'large-batch'), /100MB/);
});

function workbenchFunction(name, context) {
  const source = ts.createSourceFile('page.tsx', readFileSync(
    new URL('../admin/src/components/business/workbench/workbench-page.tsx', import.meta.url), 'utf8'
  ), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let found;
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name?.text === name) found = node;
    ts.forEachChild(node, visit);
  }
  visit(source);
  assert.ok(found, `${name} must exist`);
  const compiled = ts.transpileModule(found.getText(source), {
    compilerOptions: { target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return runInNewContext(`${compiled}\n${name}`, context);
}

test('failed upload replaces the pending message instead of leaving it spinning', async () => {
  const messages = [];
  let error;
  const upload = workbenchFunction('uploadImageFile', {
    api: { uploadAgentImage: async () => { throw new Error('too large'); } },
    Error, sessionId: 'test', uploadFileLabel: () => 'ZIP', isZipUploadFile: () => true,
    appendMessage: (role, content, status) => { messages.push({ role, content, status }); return messages.length - 1; },
    updateMessage: (id, content, status) => { messages[id] = { ...messages[id], content, status }; },
    setError: (text) => { error = text; },
  });
  assert.equal(await upload(new File(['x'], 'test.zip')), false);
  assert.equal(messages[1].status, 'error');
  assert.ok(!messages.some(message => message.status === 'sending'));
  assert.equal(error, 'too large');
});

test('a failed image batch restores the whole batch and releases sending state', async () => {
  const original = ['first.png', 'second.png'];
  let files = original;
  let input = 'next message';
  let sending = false;
  let sent;
  const send = workbenchFunction('sendMessage', {
    isSending: false, sendLockRef: { current: false }, input, files,
    setError: () => {}, setInput: (value) => { input = value; },
    setFiles: (value) => { files = typeof value === 'function' ? value(files) : value; },
    setIsSending: (value) => { sending = value; },
    isZipUploadFile: () => false,
    uploadImageBatch: async (batch) => { sent = batch; return false; },
    uploadImageFile: () => { throw new Error('image files must use the batch endpoint'); },
    sendTextMessage: () => { throw new Error('must not send text after failed upload'); },
    appendMessage: () => {}, Error,
  });
  await send();
  assert.deepEqual(Array.from(sent), original);
  assert.deepEqual(Array.from(files), original);
  assert.equal(input, 'next message');
  assert.equal(sending, false);
});

test('sendMessage submits selected images as one batch', async () => {
  const original = ['first.png', 'second.png', 'third.png'];
  let calls = 0;
  const send = workbenchFunction('sendMessage', {
    isSending: false, sendLockRef: { current: false }, input: '', files: original,
    setError: () => {}, setInput: () => {}, setFiles: () => {}, setIsSending: () => {},
    isZipUploadFile: () => false,
    uploadImageBatch: async (batch) => { calls += 1; assert.deepEqual(Array.from(batch), original); return true; },
    uploadImageFile: () => { throw new Error('must not upload images one by one'); },
    sendTextMessage: () => {}, appendMessage: () => {}, Error,
  });

  await send();

  assert.equal(calls, 1);
});

test('sendMessage rejects mixed ZIP and image attachments before upload', async () => {
  const original = [
    { name: 'design.png', type: 'image/png' },
    { name: 'bags.zip', type: 'application/zip' },
  ];
  let files = original;
  let error = '';
  let uploads = 0;
  const send = workbenchFunction('sendMessage', {
    isSending: false, sendLockRef: { current: false }, input: '', files,
    setError: (value) => { error = value; }, setInput: () => {},
    setFiles: (value) => { files = typeof value === 'function' ? value(files) : value; },
    setIsSending: () => {},
    isZipUploadFile: (file) => file.name.endsWith('.zip'),
    uploadImageBatch: async () => { uploads += 1; return true; },
    uploadImageFile: async () => { uploads += 1; return true; },
    sendTextMessage: () => {}, appendMessage: () => {}, Error,
  });

  await send();

  assert.equal(uploads, 0);
  assert.match(error, /不能.*混合/);
  assert.deepEqual(Array.from(files), original);
});

test('rapid duplicate send clicks only submit one image batch', async () => {
  let releaseUpload;
  const waitingUpload = new Promise((resolve) => { releaseUpload = resolve; });
  let uploads = 0;
  const sendLockRef = { current: false };
  const send = workbenchFunction('sendMessage', {
    isSending: false, sendLockRef, input: '', files: [{ name: 'design.png' }],
    setError: () => {}, setInput: () => {}, setFiles: () => {}, setIsSending: () => {},
    isZipUploadFile: () => false,
    uploadImageBatch: async () => { uploads += 1; return waitingUpload; },
    uploadImageFile: async () => true,
    sendTextMessage: () => {}, appendMessage: () => {}, Error,
  });

  const first = send();
  const second = send();
  assert.equal(uploads, 1);
  releaseUpload(true);
  await Promise.all([first, second]);
  assert.equal(uploads, 1);
  assert.equal(sendLockRef.current, false);
});

test('image batch ids belong to the exact file group and are released after success', () => {
  const imageBatchKey = workbenchFunction('imageBatchKey', {});
  const ids = new Map();
  let now = 123456;
  const context = {
    IMAGE_BATCH_IDS: ids,
    imageBatchKey,
    Date: { now: () => now++ },
    Math: { ...Math, random: () => 0.25 },
  };
  const imageBatchId = workbenchFunction('imageBatchId', context);
  const releaseImageBatchId = workbenchFunction('releaseImageBatchId', { IMAGE_BATCH_IDS: ids, imageBatchKey });
  const first = { name: 'a.png', size: 10, lastModified: 1, type: 'image/png' };
  const second = { name: 'b.png', size: 20, lastModified: 2, type: 'image/png' };
  const third = { name: 'c.png', size: 30, lastModified: 3, type: 'image/png' };

  const firstBatch = imageBatchId([first, second]);
  assert.equal(imageBatchId([first, second]), firstBatch);
  assert.notEqual(imageBatchId([first, third]), firstBatch);

  releaseImageBatchId([first, second]);
  assert.notEqual(imageBatchId([first, second]), firstBatch);
});
