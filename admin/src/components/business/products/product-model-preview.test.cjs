const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { before, test } = require("node:test");
const { pathToFileURL } = require("node:url");
const ts = require("typescript");
let THREE;
before(async () => {
  THREE = await import(pathToFileURL(path.join(path.dirname(require.resolve("three")), "three.module.js")).href);
});

function helpers() {
  const filename = path.join(__dirname, "product-model-preview.helpers.ts");
  assert.ok(fs.existsSync(filename), "Missing preview helper implementation");
  const source = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
  }).outputText;
  const exports = {};
  vm.runInNewContext(source, {
    exports, require: (id) => id === "three" ? THREE : require(id), ArrayBuffer, DataView, TextDecoder, URL
  }, { filename });
  return exports;
}

function setup() {
  const root = new THREE.Group();
  const hinge = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial());
  hinge.name = "Hinge";
  const cover = new THREE.Object3D();
  cover.name = "Cover";
  root.add(hinge, cover);
  const clips = [
    new THREE.AnimationClip("hinge", 1.25, [new THREE.NumberKeyframeTrack("Hinge.position[x]", [0, 1.25], [10, 0])]),
    new THREE.AnimationClip("cover", 2.5, [new THREE.NumberKeyframeTrack("Cover.position[y]", [0, 2.5], [20, 0])])
  ];
  return { root, hinge, cover, clips, animation: helpers().createBoxAnimation(root, clips) };
}

test("starts closed with every clip at its own final time", () => {
  const { hinge, cover, animation } = setup();
  assert.equal(animation.getState().pose, "closed");
  assert.equal(animation.getState().time, 2.5);
  assert.equal(animation.getState().clipCount, 2);
  assert.equal(hinge.position.x, 0);
  assert.equal(cover.position.y, 0);
});

test("reverse opens and forward closes on one timeline; short clips hold their end", () => {
  const { hinge, cover, animation } = setup();
  animation.toggle();
  animation.update(1);
  assert.equal(animation.getState().time, 1.5);
  assert.equal(hinge.position.x, 0);
  assert.ok(Math.abs(cover.position.y - 8) < 1e-5);
  animation.update(10);
  assert.equal(animation.getState().pose, "open");
  assert.equal(hinge.position.x, 10);
  assert.equal(cover.position.y, 20);
  animation.toggle();
  animation.update(10);
  assert.equal(animation.getState().pose, "closed");
});

test("mid-motion toggles reverse without jumping or duplicating actions", () => {
  const { animation } = setup();
  animation.toggle();
  animation.update(0.6);
  const time = animation.getState().time;
  animation.toggle();
  assert.equal(animation.getState().time, time);
  assert.equal(animation.getState().pose, "closing");
  animation.update(0.2);
  assert.ok(Math.abs(animation.getState().time - time - 0.2) < 1e-6);
});

test("seeking clamps, pauses and ignores invalid frame deltas", () => {
  const { animation } = setup();
  animation.toggle();
  for (const delta of [-1, 0, NaN, Infinity]) animation.update(delta);
  assert.equal(animation.getState().time, 2.5);
  animation.seek(0.5);
  animation.update(1);
  assert.equal(animation.getState().time, 0.5);
  animation.seek(-10);
  assert.equal(animation.getState().pose, "open");
  animation.seek(Infinity);
  assert.equal(animation.getState().pose, "closed");
});

test("static and invalid clips have no animation controls; disposal is idempotent", () => {
  const { createBoxAnimation } = helpers();
  assert.equal(createBoxAnimation(new THREE.Group(), []), null);
  assert.equal(createBoxAnimation(new THREE.Group(), [new THREE.AnimationClip("bad", Infinity, [])]), null);
  const { animation, cover } = setup();
  animation.dispose();
  animation.dispose();
  animation.toggle();
  animation.seek(0);
  assert.equal(animation.update(1), false);
  assert.equal(cover.position.y, 0);
});

test("animation envelope includes off-center motion and brief keyframe excursions, restores closed pose", () => {
  const { root, hinge, clips, animation } = setup();
  const bounds = helpers().animationEnvelope(root, clips, animation);
  assert.ok(bounds.min.x <= -0.5);
  assert.ok(bounds.max.x >= 10.5);
  assert.equal(hinge.position.x, 0);
  assert.equal(animation.getState().pose, "closed");
  animation.dispose();
  const spike = new THREE.AnimationClip("spike", 2, [
    new THREE.NumberKeyframeTrack("Hinge.position[x]", [0, 0.001, 0.002, 2], [0, 100, 0, 0])
  ]);
  const next = helpers().createBoxAnimation(root, [spike]);
  const full = helpers().animationEnvelope(root, [spike], next);
  assert.ok(full.max.x >= 100.5);
  assert.equal(hinge.position.x, 0);
  next.dispose();
});

test("rigid envelope caches local bounds instead of scanning vertices every frame; preserves materials/normals", () => {
  const { createBoxAnimation, animationEnvelope } = helpers();
  const geometry = new THREE.BoxGeometry(1, 1, 1, 16, 16, 16);
  const normalMap = new THREE.Texture();
  const material = new THREE.MeshStandardMaterial({ normalMap });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = "Rigid";
  const normals = Array.from(geometry.attributes.normal.array);
  let vertexReads = 0;
  const getVertexPosition = mesh.getVertexPosition.bind(mesh);
  mesh.getVertexPosition = (...args) => { vertexReads++; return getVertexPosition(...args); };
  const clips = [new THREE.AnimationClip("move", 4, [new THREE.NumberKeyframeTrack("Rigid.position[x]", [0, 4], [10, 0])])];
  const animation = createBoxAnimation(mesh, clips);
  const bounds = animationEnvelope(mesh, clips, animation);
  assert.ok(bounds.max.x >= 10.5);
  assert.ok(vertexReads <= geometry.attributes.position.count * 2, `too many vertex reads: ${vertexReads}`);
  assert.equal(mesh.material, material);
  assert.equal(material.normalMap, normalMap);
  assert.deepEqual(Array.from(geometry.attributes.normal.array), normals);
  animation.dispose();
});

test("morph envelope uses actual deformed vertices even for weights outside zero to one", () => {
  const { createBoxAnimation, animationEnvelope } = helpers();
  const geometry = new THREE.BoxGeometry();
  const target = geometry.attributes.position.clone();
  for (let index = 0; index < target.count; index++) target.setX(index, target.getX(index) + 20);
  geometry.morphAttributes.position = [target];
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial());
  mesh.name = "Morph";
  const clips = [new THREE.AnimationClip("morph", 1, [new THREE.NumberKeyframeTrack("Morph.morphTargetInfluences[0]", [0, 1], [2, 0])])];
  const animation = createBoxAnimation(mesh, clips);
  const bounds = animationEnvelope(mesh, clips, animation);
  assert.ok(bounds.max.x >= 40.5);
  assert.equal(mesh.morphTargetInfluences[0], 0);
  animation.dispose();
});

test("skinned envelope updates bone transforms rather than reusing a stale skin bound", () => {
  const { createBoxAnimation, animationEnvelope } = helpers();
  const geometry = new THREE.BoxGeometry();
  const count = geometry.attributes.position.count;
  const indices = new Uint16Array(count * 4);
  const weights = new Float32Array(count * 4);
  for (let index = 0; index < count; index++) weights[index * 4] = 1;
  geometry.setAttribute("skinIndex", new THREE.Uint16BufferAttribute(indices, 4));
  geometry.setAttribute("skinWeight", new THREE.Float32BufferAttribute(weights, 4));
  const mesh = new THREE.SkinnedMesh(geometry, new THREE.MeshStandardMaterial());
  const bone = new THREE.Bone();
  bone.name = "MovingBone";
  mesh.add(bone);
  mesh.bind(new THREE.Skeleton([bone]));
  mesh.computeBoundingBox();
  const clips = [new THREE.AnimationClip("skin", 1, [new THREE.NumberKeyframeTrack("MovingBone.position[x]", [0, 1], [10, 0])])];
  const animation = createBoxAnimation(mesh, clips);
  const bounds = animationEnvelope(mesh, clips, animation);
  assert.ok(bounds.max.x >= 10.5);
  assert.equal(bone.position.x, 0);
  animation.dispose();
});

for (const aspect of [0.35, 1, 16 / 9, 3]) {
  test(`camera contains entire animation sphere at aspect ${aspect}`, () => {
    const { distance, near, far } = helpers().frameSphere(3, aspect, 40);
    const vertical = 40 * Math.PI / 180;
    const horizontal = 2 * Math.atan(Math.tan(vertical / 2) * aspect);
    assert.ok(distance * Math.sin(Math.min(vertical, horizontal) / 2) >= 3 * 1.1);
    assert.ok(near > 0 && near < distance - 3 && far > distance + 3);
  });
}

test("invalid camera bounds fail explicitly", () => {
  for (const args of [[0, 1, 40], [NaN, 1, 40], [1, 0, 40], [1, 1, 180]]) {
    assert.throws(() => helpers().frameSphere(...args));
  }
});

function glb(json) {
  const data = Buffer.from(JSON.stringify(json));
  const padded = Math.ceil(data.byteLength / 4) * 4;
  const buffer = new ArrayBuffer(20 + padded);
  const header = new DataView(buffer);
  header.setUint32(0, 0x46546c67, true);
  header.setUint32(4, 2, true);
  header.setUint32(8, buffer.byteLength, true);
  header.setUint32(12, padded, true);
  header.setUint32(16, 0x4e4f534a, true);
  new Uint8Array(buffer, 20).fill(32);
  new Uint8Array(buffer, 20, data.length).set(data);
  return buffer;
}

test("top-level trusted OSS HTTPS URL is allowed with credentials omitted", () => {
  const { modelFetchRequest } = helpers();
  const source = "https://models.oss-cn-hangzhou.aliyuncs.com/products/box.glb?signature=trusted";
  const request = modelFetchRequest(source, "https://admin.example.test/products");
  assert.equal(request.url, source);
  assert.equal(request.credentials, "omit");
  assert.equal(modelFetchRequest("/models/box.glb", "https://admin.example.test/products").credentials, "same-origin");
});

test("top-level model protocols reject javascript and cross-origin HTTP even during development", () => {
  const { modelFetchRequest } = helpers();
  for (const source of ["javascript:alert(1)", "file:///box.glb", "ftp://models.example.test/box.glb", "http://oss.example.test/box.glb"]) {
    assert.throws(() => modelFetchRequest(source, "http://localhost:5179/products", true));
  }
  assert.throws(() => modelFetchRequest("/box.glb", "http://localhost:5179/products"));
  assert.throws(() => modelFetchRequest("https://user:secret@oss.example.test/box.glb", "https://admin.example.test"));
  const local = modelFetchRequest("/box.glb", "http://localhost:5179/products", true);
  assert.equal(local.url, "http://localhost:5179/box.glb");
  assert.equal(local.credentials, "same-origin");
  assert.equal(modelFetchRequest("blob:http://localhost:5179/id", "http://localhost:5179/products", true).url, "blob:http://localhost:5179/id");
  assert.equal(modelFetchRequest("data:model/gltf-binary;base64,AAAA", "https://admin.example.test").credentials, "omit");
});

test("allowing the top-level OSS model does not allow OSS URLs inside the GLB", () => {
  const { modelFetchRequest, validateEmbeddedGlb, embeddedResourceUrl } = helpers();
  const source = "https://models.oss-cn-hangzhou.aliyuncs.com/texture.png";
  assert.equal(modelFetchRequest(source, "https://admin.example.test").credentials, "omit");
  assert.throws(() => validateEmbeddedGlb(glb({ images: [{ uri: source }] })), /内嵌/);
  assert.throws(() => embeddedResourceUrl(source), /内嵌/);
});

test("accepts embedded GLB and data/blob resources, rejects external refs before parsing", () => {
  const { validateEmbeddedGlb, embeddedResourceUrl } = helpers();
  validateEmbeddedGlb(glb({ asset: { version: "2.0" }, buffers: [{ byteLength: 4 }], images: [{ bufferView: 0 }] }));
  for (const uri of ["https://evil.test/a.png", "/same-origin.png", "../a.bin", "//evil.test/a.bin", "file:///a"]) {
    assert.throws(() => validateEmbeddedGlb(glb({ buffers: [{ uri }] })), /内嵌/);
    assert.throws(() => embeddedResourceUrl(uri), /内嵌/);
  }
  for (const uri of ["data:image/png;base64,AAAA", "blob:http://localhost/id"]) {
    assert.equal(embeddedResourceUrl(uri), uri);
    validateEmbeddedGlb(glb({ images: [{ uri }] }));
  }
});

test("rejects malformed, wrong-version and truncated GLB", () => {
  const { validateEmbeddedGlb } = helpers();
  assert.throws(() => validateEmbeddedGlb(new ArrayBuffer(12)));
  const buffer = glb({});
  new DataView(buffer).setUint32(8, 1000, true);
  assert.throws(() => validateEmbeddedGlb(buffer));
  const wrong = glb({});
  new DataView(wrong).setUint32(4, 1, true);
  assert.throws(() => validateEmbeddedGlb(wrong));
});

test("disposes shared geometry/material/texture/bitmap once and late resources immediately", () => {
  const { createModelResources } = helpers();
  const resources = createModelResources();
  const counts = { geometry: 0, material: 0, texture: 0, bitmap: 0 };
  const bitmap = { close: () => { counts.bitmap++; } };
  const texture = new THREE.Texture(bitmap);
  texture.addEventListener("dispose", () => { counts.texture++; });
  const material = new THREE.MeshStandardMaterial({ map: texture, normalMap: texture });
  material.addEventListener("dispose", () => { counts.material++; });
  const geometry = new THREE.BoxGeometry();
  geometry.addEventListener("dispose", () => { counts.geometry++; });
  const root = new THREE.Group();
  root.add(new THREE.Mesh(geometry, material), new THREE.Mesh(geometry, material));
  resources.track(root);
  resources.track(texture);
  resources.dispose();
  resources.dispose();
  assert.deepEqual(counts, { geometry: 1, material: 1, texture: 1, bitmap: 1 });
  const late = new THREE.Texture({ close: () => { counts.bitmap++; } });
  late.addEventListener("dispose", () => { counts.texture++; });
  resources.track(late);
  resources.track(late);
  assert.equal(counts.texture, 2);
  assert.equal(counts.bitmap, 2);
});

test("partial parser geometry and nested shader textures are released without a completed scene", () => {
  const resources = helpers().createModelResources();
  let geometries = 0;
  let textures = 0;
  let bitmaps = 0;
  const geometry = new THREE.BoxGeometry();
  geometry.addEventListener("dispose", () => { geometries++; });
  const texture = new THREE.Texture([{ close: () => { bitmaps++; } }]);
  texture.addEventListener("dispose", () => { textures++; });
  const material = new THREE.ShaderMaterial({ uniforms: { nested: { value: [texture] } } });
  resources.track([geometry, material]);
  resources.dispose();
  assert.equal(geometries, 1);
  assert.equal(textures, 1);
  assert.equal(bitmaps, 1);
});
