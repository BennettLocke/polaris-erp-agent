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

test('a failed batch keeps only failed and unsent files and releases sending state', async () => {
  const original = ['first.zip', 'failed.zip', 'unsent.zip'];
  let files = original;
  let input = 'next message';
  let sending = false;
  const sent = [];
  const send = workbenchFunction('sendMessage', {
    isSending: false, input, files,
    setError: () => {}, setInput: (value) => { input = value; },
    setFiles: (value) => { files = typeof value === 'function' ? value(files) : value; },
    setIsSending: (value) => { sending = value; },
    uploadImageFile: async (file) => { sent.push(file); return file !== 'failed.zip'; },
    sendTextMessage: () => { throw new Error('must not send text after failed upload'); },
    appendMessage: () => {}, Error,
  });
  await send();
  assert.deepEqual(sent, ['first.zip', 'failed.zip']);
  assert.deepEqual(Array.from(files), ['failed.zip', 'unsent.zip']);
  assert.equal(input, 'next message');
  assert.equal(sending, false);
});
