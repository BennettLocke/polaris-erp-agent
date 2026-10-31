const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function functions(file, names, context = {}) {
  const filename = path.join(__dirname, file);
  const source = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const declarations = new Map();
  function visit(node) {
    if (ts.isFunctionDeclaration(node) && node.name) declarations.set(node.name.text, node);
    ts.forEachChild(node, visit);
  }
  visit(source);
  const printer = ts.createPrinter();
  const code = names.map((name) => {
    assert.ok(declarations.has(name), `${name} is missing`);
    return printer.printNode(ts.EmitHint.Unspecified, declarations.get(name), source).replace(/^export /, '');
  }).join('\n');
  const exports = {};
  vm.runInNewContext(ts.transpileModule(`${code}\nObject.assign(exports, { ${names.join(',')} });`, {
    fileName: 'editor-test.tsx',
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText, { exports, ...context });
  return exports;
}

const editorFunctions = ['isProductModelHex', 'reconcileProductModelConfig', 'replaceProductModelConfig', 'updateProductModelColor', 'isProductModelConfigValid'];
const editor = () => functions('product-model-editor.tsx', editorFunctions);
const config = (patch = {}) => ({ version: 1, asset_id: 9, material_index: 3, sku_colors: { '10': '#AABBCC', new_1: '#123456' }, default_sku_key: '10', camera_direction: [1, 0, 0], default_pose: 'open', ...patch });
const plain = (value) => JSON.parse(JSON.stringify(value));

test('model replacement retains SKU colors but resets asset-specific calibration and target', () => {
  const original = config();
  const next = editor().replaceProductModelConfig(original, 22);
  assert.deepEqual(plain(next), { ...original, asset_id: 22, material_index: null, camera_direction: null });
  assert.notEqual(next.sku_colors, original.sku_colors);
  assert.deepEqual(plain(editor().replaceProductModelConfig(null, 22).sku_colors), {});
});

test('reconciliation prunes deleted SKUs and defaults only to configured valid colors', () => {
  const { reconcileProductModelConfig } = editor();
  const choices = [{ key: 'new_1', name: 'Renamed' }, { key: 'new_2', name: 'Unset' }];
  const next = reconcileProductModelConfig(config(), choices);
  assert.deepEqual(plain(next.sku_colors), { new_1: '#123456' });
  assert.equal(next.default_sku_key, 'new_1');
  assert.equal(reconcileProductModelConfig(config({ sku_colors: { new_1: '#12' } }), choices).default_sku_key, null);
  assert.equal(reconcileProductModelConfig(null, choices), null);
});

test('partial HEX stays in the draft and blocks saving instead of retaining a stale color', () => {
  const { updateProductModelColor, isProductModelConfigValid } = editor();
  const next = updateProductModelColor(config(), '10', '#AA');
  assert.equal(next.sku_colors['10'], '#AA');
  assert.equal(isProductModelConfigValid(next), false);
  assert.equal(isProductModelConfigValid(updateProductModelColor(next, '10', '#abcdef')), true);
  assert.equal(isProductModelConfigValid(config({ material_index: null })), false);
  assert.equal(isProductModelConfigValid(null), true);
});

test('clearing a color leaves it unset and chooses the next configured default', () => {
  const next = editor().updateProductModelColor(config(), '10', '');
  assert.equal(Object.hasOwn(next.sku_colors, '10'), false);
  assert.equal(next.default_sku_key, 'new_1');
  const empty = editor().updateProductModelColor(next, 'new_1', '');
  assert.deepEqual(plain(empty.sku_colors), {});
  assert.equal(empty.default_sku_key, null);
});

test('default color fallback follows current SKU order rather than numeric object key order', () => {
  const choices = [{ key: '99', name: 'First' }, { key: '10', name: 'Second' }];
  const next = editor().updateProductModelColor(config({ sku_colors: { '99': '#999999', '10': '#111111', '1': '#000000' }, default_sku_key: '1' }), '1', '', choices);
  assert.equal(next.default_sku_key, '99');
});

test('finishing an upload preserves the latest SKU draft rather than the upload-start snapshot', async () => {
  let emitted;
  const current = config({ sku_colors: { '10': '#12' }, default_sku_key: null });
  const { upload } = functions('product-model-editor.tsx', ['upload'], {
    ...editor(), file: undefined, disabled: false, uploadLock: { current: false }, active: { current: true },
    MAX_MODEL_BYTES: 50 * 1024 * 1024, config: config(), colors: [{ key: '10', name: 'Old' }, { key: 'new_1', name: 'Deleted' }],
    latestDraft: { current: { config: current, colors: [{ key: '10', name: 'Renamed' }] } },
    onBusyChange() {}, setUploading() {}, setProgress() {}, setError() {}, onUploaded() {}, onChange() {},
    onConfigChange: (value) => { emitted = value; }, api: { uploadProductModel: async () => ({ id: 22 }) },
  });
  await upload({ name: 'replacement.glb', size: 1024 });
  assert.deepEqual(plain(emitted.sku_colors), { '10': '#12' });
  assert.equal(emitted.material_index, null);
});

test('HEX validation accepts only complete six-digit colors, with no color guessing', () => {
  const { isProductModelHex } = editor();
  for (const value of ['#000000', '#abcdef', '#ABC123']) assert.equal(isProductModelHex(value), true);
  for (const value of ['', '#FFF', 'red', 'ABCDEF', '#12345G', '#12345678']) assert.equal(isProductModelHex(value), false);
});

function page(context = {}) {
  return functions('products-page.tsx', ['productModelColorChoices', 'productModelConfigForSave'], { ...editor(), ...context });
}

test('unsaved SKU identity survives rename, delete and reorder while save keys match base indices', () => {
  const { productModelColorChoices, productModelConfigForSave } = page();
  const first = { id: '', model_key: 'new_0', spec: 'First' };
  const second = { id: '', model_key: 'new_1', spec: 'Second' };
  const third = { id: '99', spec: '' };
  const reordered = [third, { ...second, spec: 'Renamed' }];
  assert.deepEqual(plain(productModelColorChoices([first, second])), [{ key: 'new_0', name: 'First' }, { key: 'new_1', name: 'Second' }]);
  assert.deepEqual(plain(productModelColorChoices(reordered)), [{ key: '99', name: '默认颜色' }, { key: 'new_1', name: 'Renamed' }]);
  const draft = config({ sku_colors: { new_0: '#111111', new_1: '#222222', '99': '#999999' }, default_sku_key: 'new_1' });
  const submitted = productModelConfigForSave(draft, [second, third]);
  assert.deepEqual(plain(submitted.sku_colors), { new_0: '#222222', '99': '#999999' });
  assert.equal(submitted.default_sku_key, 'new_0');
  assert.equal(draft.sku_colors.new_1, '#222222');
});

test('product payload includes config-only edits atomically and omits untouched config', () => {
  const ctx = {
    specs: [], effectiveStockItem: true, modelChanged: false, model: { id: 9 }, modelConfig: config(), modelConfigChanged: true,
    isCreate: false, productId: 7, title: 'Product', productType: 'gift_box', categoryIds: [1], manufacturerId: '0', status: 0,
    oneCase: false, casePackQty: '', detailImages: [], mainImages: [], detailImagesToHtml: () => '', ...page(),
  };
  const build = () => functions('products-page.tsx', ['buildPayload'], ctx).buildPayload();
  const dirty = build();
  assert.ok(Object.hasOwn(dirty, 'model_config'));
  assert.equal(Object.hasOwn(dirty, 'model_asset_id'), false);
  ctx.modelConfigChanged = false;
  assert.equal(Object.hasOwn(build(), 'model_config'), false);
  ctx.modelConfigChanged = true; ctx.modelChanged = true; ctx.model = null; ctx.modelConfig = null;
  assert.equal(build().model_config, null);
  assert.equal(build().model_asset_id, null);
});

test('save rejects incomplete HEX before calling the product API', async () => {
  let saves = 0, message = '';
  const { save } = functions('products-page.tsx', ['save'], {
    ...editor(), modelConfig: config({ sku_colors: { '10': '#12' } }), modelUploading: false, saving: false, loading: false,
    title: 'Product', categoryIds: [1], setError: (value) => { message = value; },
    setSaving: () => {}, api: { saveProduct: async () => { saves++; } }, buildPayload: () => ({}),
    releaseStagedModels: () => {}, model: null, queryClient: { invalidateQueries() {} }, queryKeys: { products: { root: [] } },
    onSaved() {}, onClose() {}, isCreate: false,
  });
  await save();
  assert.equal(saves, 0);
  assert.ok(message);
});

function renderEditor(props) {
  const context = { require, MAX_MODEL_BYTES: 50 * 1024 * 1024, useEffect() {}, useState: (value) => [value, () => {}], useRef: (value) => ({ current: value }) };
  let id = 0;
  context.useId = () => `field-${id++}`;
  for (const name of ['Box', 'Eye', 'Loader2', 'Pipette', 'Trash2', 'Upload', 'X', 'Badge', 'Button', 'Empty', 'EmptyContent', 'EmptyHeader', 'EmptyTitle', 'Field', 'FieldGroup', 'FieldLabel', 'Input', 'Select', 'SelectContent', 'SelectGroup', 'SelectItem', 'SelectTrigger', 'SelectValue', 'Suspense', 'ProductModelPreview']) context[name] = name;
  const loaded = functions('product-model-editor.tsx', [...editorFunctions, 'ModelSkuColor', 'ProductModelEditor'], context);
  const tree = loaded.ProductModelEditor(props);
  const nodes = [];
  function visit(value) {
    if (Array.isArray(value)) return value.forEach(visit);
    if (!value || typeof value !== 'object') return;
    if (typeof value.type === 'function') return visit(value.type(value.props));
    nodes.push(value);
    visit(value.props?.children);
  }
  visit(tree);
  return nodes;
}

test('editor controls keep original material indices and expose associated select labels', () => {
  const nodes = renderEditor({
    model: { id: 9, file_name: 'box.glb', byte_size: 1024, animation_count: 0, materials: [{ index: 4, name: '' }, { index: 7, name: 'Body' }, { index: 12, name: 'Body' }] },
    config: config(), colors: [{ key: '10', name: '红色' }, { key: 'new_1', name: '蓝色' }, { key: 'new_2', name: 'Unset' }], disabled: false,
    onChange() {}, onUploaded() {}, onBusyChange() {}, onConfigChange() {},
  });
  const labels = nodes.filter((node) => node.type === 'FieldLabel');
  for (const name of ['换色材质', '默认颜色']) {
    const label = labels.find((node) => node.props.children === name);
    assert.ok(label?.props.htmlFor);
    assert.ok(nodes.some((node) => node.type === 'SelectTrigger' && node.props.id === label.props.htmlFor));
  }
  const options = nodes.filter((node) => node.type === 'SelectItem');
  for (const index of [4, 7, 12]) {
    const option = options.find((node) => node.props.value === String(index));
    assert.ok(option);
    assert.ok(JSON.stringify(option.props.children).includes(String(index)));
  }
  assert.equal(options.filter((node) => node.props.value === 'new_2').length, 0);
  assert.equal(nodes.find((node) => node.props?.['aria-label'] === '红色 HEX 色值').props.value, '#AABBCC');
  assert.ok(nodes.find((node) => node.type === 'Button' && node.props['aria-label'] === '红色模型颜色'));
  assert.equal(nodes.find((node) => node.props?.['aria-label'] === 'Unset HEX 色值').props.value, '');
});

test('typing incomplete HEX emits the partial draft and unbinding clears config', () => {
  let draft, model;
  const nodes = renderEditor({
    model: { id: 9, file_name: 'box.glb', byte_size: 1024, animation_count: 0, materials: [] }, config: config(),
    colors: [{ key: '10', name: '红色' }, { key: 'new_1', name: '蓝色' }], disabled: false,
    onChange: (value) => { model = value; }, onConfigChange: (value) => { draft = value; }, onUploaded() {}, onBusyChange() {},
  });
  nodes.find((node) => node.props?.['aria-label'] === '红色 HEX 色值').props.onChange({ currentTarget: { value: '#12' } });
  assert.equal(draft.sku_colors['10'], '#12');
  assert.equal(editor().isProductModelConfigValid(draft), false);
  const unbind = nodes.find((node) => node.type === 'Button' && JSON.stringify(node.props.children).includes('解除绑定'));
  unbind.props.onClick();
  assert.equal(model, null);
  assert.equal(draft, null);
});

test('applying a different product resets config draft, dirty flag and temporary SKU identities', () => {
  const events = [], nextModelSkuKey = { current: 100 };
  const ctx = {
    ...page(), ...editor(), units: [], nextModelSkuKey,
    productCategoryIds: () => [], casePackQtyFromProduct: () => '', productImageUrl: () => '', detailImagesFromProduct: () => [],
    productSpecRows: () => [{ id: '10', spec: 'Existing' }, { id: '', spec: 'New' }],
    setModelConfig: (value) => events.push(['config', value]), setModelConfigChanged: (value) => events.push(['dirty', value]),
    setSpecs: (value) => events.push(['specs', value]),
  };
  for (const name of ['setTitle', 'setProductType', 'setCategoryIds', 'setManufacturerId', 'setManufacturerLabel', 'setManufacturerStatus', 'setStatus', 'setCasePackQty', 'setOneCase', 'setStockItem', 'setMainImages', 'setDetailImages', 'setMediaAssets', 'setModel', 'setModelChanged']) ctx[name] = () => {};
  const { applyProduct } = functions('products-page.tsx', ['applyProduct'], ctx);
  applyProduct({ model_config: config() });
  assert.equal(events.find(([name]) => name === 'dirty')[1], false);
  assert.equal(nextModelSkuKey.current, 2);
  assert.equal(events.find(([name]) => name === 'specs')[1][1].model_key, 'new_1');
  events.length = 0;
  applyProduct({});
  assert.equal(events.find(([name]) => name === 'config')[1], null);
});
