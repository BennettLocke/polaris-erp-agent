const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test, before } = require('node:test');
const { pathToFileURL } = require('node:url');
const ts = require('typescript');
let THREE;
before(async () => { THREE = await import(pathToFileURL(path.join(path.dirname(require.resolve('three')), 'three.module.js')).href); });
function helpers() {
  const file = path.join(__dirname, 'product-model-color-config.helpers.ts');
  assert.ok(fs.existsSync(file), 'Persistent model color helpers are not implemented');
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText,
    { exports, require: id => id === 'three' ? THREE : require(id) });
  return exports;
}
test('GLB material indices control every clone without changing lining, maps or physical properties', () => {
  const { createModelColorController } = helpers();
  const shell = new THREE.MeshPhysicalMaterial({ color: '#eeeeee', roughness: .72, clearcoat: .6 });
  shell.normalMap = new THREE.Texture();
  const shellClone = shell.clone();
  const lining = new THREE.MeshStandardMaterial({ color: '#c09863' });
  const root = new THREE.Group();
  root.add(new THREE.Mesh(new THREE.BoxGeometry(), shell), new THREE.Mesh(new THREE.BoxGeometry(), shellClone), new THREE.Mesh(new THREE.BoxGeometry(), lining));
  const original = shell.color.clone();
  const liningOriginal = lining.color.clone();
  const associations = new Map([[shell, { materials: 0 }], [shellClone, { materials: 0 }], [lining, { materials: 1 }]]);
  const controller = createModelColorController(root, associations);
  assert.equal(controller.apply(0, '#2B67C8'), true);
  assert.equal(shell.color.getHexString(), '2b67c8');
  assert.equal(shellClone.color.getHexString(), '2b67c8');
  assert.ok(lining.color.equals(liningOriginal));
  assert.equal(shell.normalMap, shellClone.normalMap);
  assert.equal(shell.roughness, .72);
  assert.equal(shell.clearcoat, .6);
  controller.apply(1, '#ffffff');
  assert.ok(shell.color.equals(original), 'switching target restores the old target');
  assert.equal(lining.color.getHexString(), 'ffffff');
  controller.apply(null, undefined);
  assert.ok(lining.color.equals(liningOriginal));
  assert.equal(controller.apply(99, '#123456'), false);
  assert.equal(controller.apply(0, 'red'), false);
});
test('material runtime UUIDs cannot be persisted as GLB material indices', () => {
  const { createModelColorController } = helpers();
  const material = new THREE.MeshStandardMaterial();
  const root = new THREE.Mesh(new THREE.BoxGeometry(), material);
  const controller = createModelColorController(root, new Map());
  assert.equal(controller.apply(0, '#123456'), false);
  assert.equal(material.color.getHexString(), 'ffffff');
});
test('actual GLTFLoader line and point material conversions retain the original GLB color scope', async () => {
  const { createModelColorController } = helpers();
  const loaderPath = path.join(path.dirname(require.resolve('three')), '../examples/jsm/loaders/GLTFLoader.js');
  const { GLTFLoader } = await import(pathToFileURL(loaderPath).href);
  const bin = Buffer.from(new Float32Array([-1,-1,0,1,-1,0,0,1,0]).buffer);
  const doc = { asset:{version:'2.0'}, scene:0, scenes:[{nodes:[0]}], nodes:[{mesh:0}],
    materials:[{name:'Shell'},{name:'Lining',pbrMetallicRoughness:{baseColorFactor:[.4,.2,.1,1]}}],
    meshes:[{primitives:[{attributes:{POSITION:0},material:0,mode:4},{attributes:{POSITION:1},material:0,mode:1},{attributes:{POSITION:0},material:0,mode:0},{attributes:{POSITION:0},material:1,mode:4}]}],
    buffers:[{byteLength:bin.length}],bufferViews:[{buffer:0,byteLength:bin.length}],
    accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3',min:[-1,-1,0],max:[1,1,0]},
      {bufferView:0,componentType:5126,count:2,type:'VEC3',min:[-1,-1,0],max:[1,-1,0]}] };
  const json = Buffer.from(JSON.stringify(doc));
  const padded = Buffer.alloc(Math.ceil(json.length/4)*4,32);json.copy(padded);
  const header = Buffer.alloc(20);header.writeUInt32LE(0x46546c67);header.writeUInt32LE(2,4);
  header.writeUInt32LE(28+padded.length+bin.length,8);header.writeUInt32LE(padded.length,12);header.writeUInt32LE(0x4e4f534a,16);
  const bh=Buffer.alloc(8);bh.writeUInt32LE(bin.length);bh.writeUInt32LE(0x004e4942,4);
  const bytes=Buffer.concat([header,padded,bh,bin]);
  const gltf=await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.length),'');
  const primitives=gltf.scene.children[0].children;
  const lining=primitives[3].material.color.clone();
  const controller=createModelColorController(gltf.scene,gltf.parser.associations,gltf.parser.json);
  assert.equal(controller.apply(0,'#2B67C8'),true);
  for(const node of primitives.slice(0,3))assert.equal(node.material.color.getHexString(),'2b67c8');
  assert.ok(primitives[3].material.color.equals(lining));
  controller.apply(null);
  for(const node of primitives.slice(0,3))assert.equal(node.material.color.getHexString(),'ffffff');
});
test('calibrated directions are normalized and camera movement never mutates geometry', () => {
  const { modelViewDirection, captureModelViewDirection } = helpers();
  const original = [0, .5, -2];
  const view = modelViewDirection(original);
  assert.ok(Math.abs(view.length() - 1) < 1e-12);
  assert.ok(view.z < 0);
  assert.deepEqual(original, [0, .5, -2]);
  const camera = new THREE.Vector3(12, 4, -3), target = new THREE.Vector3(10, 1, 0);
  const captured = captureModelViewDirection(camera, target);
  assert.ok(Math.abs(Math.hypot(...captured) - 1) < 1e-12);
  assert.ok(captured[2] < 0);
  for (const invalid of [null, [], [0, 0, 0], [NaN, 1, 0], [0, Infinity, 0]]) {
    assert.ok(modelViewDirection(invalid).equals(modelViewDirection(null)));
  }
});
