import {
  AnimationMixer, Box3, LoopOnce, Vector3,
  type AnimationClip, type BufferGeometry, type InstancedMesh, type Material, type Mesh, type Object3D, type Skeleton, type Texture
} from "three";

export function createBoxAnimation(root: Object3D, clips: AnimationClip[], initialPose: "open" | "closed" = "open") {
  const usable = clips.filter((clip) => Number.isFinite(clip.duration) && clip.duration > 0 && clip.tracks.length);
  if (!usable.length) return null;
  const mixer = new AnimationMixer(root);
  const actions = usable.map((clip) => {
    const action = mixer.clipAction(clip);
    action.setLoop(LoopOnce, 1);
    action.clampWhenFinished = true;
    action.play();
    action.paused = true;
    return action;
  });
  const duration = Math.max(...usable.map((clip) => clip.duration));
  let time = initialPose === "closed" ? duration : 0;
  let target = time;
  let disposed = false;
  const clamp = (value: number) => Math.min(duration, Math.max(0, Number.isFinite(value) ? value : duration));

  function sample(value: number) {
    if (disposed) return;
    for (const action of actions) {
      action.enabled = true;
      action.paused = true;
      action.time = Math.min(clamp(value), action.getClip().duration);
    }
    mixer.update(0);
    root.updateMatrixWorld(true);
  }

  sample(time);
  return {
    sample,
    getState() {
      const moving = Math.abs(target - time) > 1e-6;
      return {
        time, duration, clipCount: actions.length, moving,
        openness: 1 - time / duration,
        pose: moving ? (target === 0 ? "opening" : "closing") : time === 0 ? "open" : time === duration ? "closed" : "paused",
        nextAction: moving ? (target === 0 ? "close" : "open") : time === 0 ? "close" : "open"
      };
    },
    toggle() {
      if (disposed) return;
      target = Math.abs(target - time) > 1e-6 ? (target === 0 ? duration : 0) : time === 0 ? duration : 0;
    },
    seek(value: number) {
      if (disposed) return;
      time = target = clamp(value);
      sample(time);
    },
    update(delta: number) {
      if (disposed || time === target || !Number.isFinite(delta) || delta <= 0) return false;
      const direction = Math.sign(target - time);
      time = direction > 0 ? Math.min(target, time + delta) : Math.max(target, time - delta);
      if (Math.abs(target - time) < 1e-6) time = target;
      sample(time);
      return true;
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      mixer.stopAllAction();
      mixer.uncacheRoot(root);
    }
  };
}

export type BoxAnimation = NonNullable<ReturnType<typeof createBoxAnimation>>;
export type BoxAnimationState = ReturnType<BoxAnimation["getState"]>;

export function animationEnvelope(root: Object3D, clips: AnimationClip[], animation: BoxAnimation | null) {
  const bounds = new Box3();
  if (!animation) return bounds.setFromObject(root, true);
  const local = new Box3();
  const vertex = new Vector3();
  function includePose() {
    root.traverse((node) => {
      const mesh = node as Mesh & { isSkinnedMesh?: boolean; isInstancedMesh?: boolean };
      const geometry = mesh.geometry;
      if (!geometry) return;
      // Rigid parts need eight transformed bounds corners, not a vertex scan per sample.
      if (mesh.isMesh && (mesh.isSkinnedMesh || mesh.morphTargetInfluences?.length)) {
        const positions = geometry.getAttribute("position");
        if (!positions) return;
        for (let index = 0; index < positions.count; index++) {
          mesh.getVertexPosition(index, vertex).applyMatrix4(mesh.matrixWorld);
          bounds.expandByPoint(vertex);
        }
      } else if (mesh.isInstancedMesh) {
        const instanced = mesh as InstancedMesh;
        if (!instanced.boundingBox) instanced.computeBoundingBox();
        if (instanced.boundingBox) bounds.union(local.copy(instanced.boundingBox).applyMatrix4(mesh.matrixWorld));
      } else {
        if (!geometry.boundingBox) geometry.computeBoundingBox();
        if (geometry.boundingBox) bounds.union(local.copy(geometry.boundingBox).applyMatrix4(mesh.matrixWorld));
      }
    });
  }
  const { duration, time } = animation.getState();
  const times = new Set<number>([0, duration]);
  const samples = Math.min(240, Math.max(24, Math.ceil(duration * 60)));
  for (let frame = 0; frame <= samples; frame++) times.add(duration * frame / samples);
  // Key times catch short excursions that uniform samples can miss.
  for (const clip of clips) {
    for (const track of clip.tracks) {
      for (let index = 0; index < track.times.length; index++) {
        const key = track.times[index];
        if (Number.isFinite(key) && key >= 0 && key <= duration) times.add(key);
        if (index > 0) {
          const previous = track.times[index - 1];
          for (const fraction of [0.25, 0.5, 0.75]) {
            const between = previous + (key - previous) * fraction;
            if (between >= 0 && between <= duration) times.add(between);
          }
        }
      }
    }
  }
  try {
    for (const sample of times) {
      animation.sample(sample);
      includePose();
    }
  } finally {
    animation.sample(time);
  }
  return bounds;
}

export function frameSphere(radius: number, aspect: number, verticalDegrees = 40) {
  if (![radius, aspect, verticalDegrees].every(Number.isFinite)
    || radius <= 0 || aspect <= 0 || verticalDegrees <= 0 || verticalDegrees >= 180) {
    throw new Error("Invalid camera bounds");
  }
  const vertical = verticalDegrees * Math.PI / 180;
  const horizontal = 2 * Math.atan(Math.tan(vertical / 2) * aspect);
  const distance = radius * 1.14 / Math.sin(Math.min(vertical, horizontal) / 2);
  return { distance, near: Math.max(radius / 1000, 0.00001), far: distance + radius * 100 };
}

export function modelFetchRequest(source: string, pageUrl: string, allowDevelopmentHttp = false) {
  const page = new URL(pageUrl);
  const url = new URL(source, page);
  const sameOrigin = url.origin === page.origin;
  const allowed = url.protocol === "https:"
    || (url.protocol === "http:" && sameOrigin && allowDevelopmentHttp)
    || url.protocol === "data:" || url.protocol === "blob:";
  if (!allowed || url.username || url.password) throw new Error("模型地址必须使用 HTTPS。");
  return { url: url.href, credentials: (sameOrigin ? "same-origin" : "omit") as RequestCredentials };
}

export function embeddedResourceUrl(url: string) {
  if (!/^(data:|blob:)/i.test(url)) throw new Error("模型含外部资源，请使用贴图内嵌的 GLB 文件。");
  return url;
}

export function validateEmbeddedGlb(buffer: ArrayBuffer) {
  if (buffer.byteLength < 20) throw new Error("请选择有效的 GLB 模型文件。");
  const header = new DataView(buffer);
  if (header.getUint32(0, true) !== 0x46546c67 || header.getUint32(4, true) !== 2) {
    throw new Error("请选择 GLB 2.0 模型文件。");
  }
  if (header.getUint32(8, true) !== buffer.byteLength) throw new Error("模型文件不完整。");
  const jsonLength = header.getUint32(12, true);
  if (header.getUint32(16, true) !== 0x4e4f534a || jsonLength % 4 || jsonLength > buffer.byteLength - 20) {
    throw new Error("模型文件结构无效。");
  }
  const json: unknown = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 20, jsonLength)));
  function inspect(value: unknown) {
    if (!value || typeof value !== "object") return;
    for (const [key, child] of Object.entries(value)) {
      if (key === "uri" && typeof child === "string") embeddedResourceUrl(child);
      else inspect(child);
    }
  }
  inspect(json);
}

export function createModelResources() {
  let released = false;
  const known = new WeakSet<object>();
  const pending = new Set<() => void>();
  function own(value: object, dispose: () => void) {
    if (known.has(value)) return;
    known.add(value);
    if (released) dispose();
    else pending.add(dispose);
  }
  function closeImages(value: unknown) {
    if (Array.isArray(value)) { value.forEach(closeImages); return; }
    if (value && typeof value === "object" && "close" in value && typeof value.close === "function") {
      const image = value as { close: () => void };
      own(image, () => image.close());
    }
  }
  function trackTexture(texture: Texture) {
    own(texture, () => { closeImages(texture.source?.data); texture.dispose(); });
  }
  function findTextures(value: unknown, visited = new WeakSet<object>()) {
    if (!value || typeof value !== "object" || visited.has(value)) return;
    visited.add(value);
    if ((value as Texture).isTexture) { trackTexture(value as Texture); return; }
    if (Array.isArray(value)) value.forEach((item) => findTextures(item, visited));
    else Object.values(value).forEach((item) => findTextures(item, visited));
  }
  function track(value: unknown) {
    if (!value || typeof value !== "object") return;
    if (Array.isArray(value)) { value.forEach(track); return; }
    if ((value as Texture).isTexture) { trackTexture(value as Texture); return; }
    if ((value as BufferGeometry).isBufferGeometry) {
      const geometry = value as BufferGeometry;
      own(geometry, () => geometry.dispose());
      return;
    }
    if ((value as Material).isMaterial) {
      const material = value as Material;
      Object.values(material).forEach((item) => findTextures(item));
      own(material, () => material.dispose());
      return;
    }
    if ((value as Object3D).isObject3D) {
      (value as Object3D).traverse((node) => {
        const renderable = node as Object3D & { geometry?: BufferGeometry; material?: Material | Material[]; skeleton?: Skeleton };
        if (renderable.geometry) own(renderable.geometry, () => renderable.geometry!.dispose());
        track(renderable.material);
        if (renderable.skeleton) {
          const skeleton = renderable.skeleton;
          // Skeleton.dispose owns the bone texture, which is not a material texture.
          own(skeleton, () => skeleton.dispose());
        }
      });
    }
  }
  return {
    track,
    dispose() {
      if (released) return;
      released = true;
      for (const dispose of pending) dispose();
      pending.clear();
    }
  };
}
