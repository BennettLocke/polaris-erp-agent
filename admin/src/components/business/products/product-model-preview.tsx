import { useEffect, useId, useRef, useState, type ComponentProps } from "react";
import { AlertCircle, Loader2, Package, PackageOpen, RefreshCw, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { BoxAnimationState } from "./product-model-preview.helpers";
import "./product-model-preview.css";

export interface ProductModelPreviewProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  model: { url: string; file_name: string; animation_count: number } | null;
}

export function ProductModelPreview({ open, onOpenChange, model }: ProductModelPreviewProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? <DialogContent className="product-model-preview-dialog" aria-describedby={undefined}>
        <DialogHeader className="product-model-preview-header">
          <DialogTitle>3D 模型预览</DialogTitle>
          {model ? <span className="product-model-preview-filename" title={model.file_name}>{model.file_name}</span> : null}
        </DialogHeader>
        {model ? <ModelViewport key={`${model.url}\0${model.file_name}\0${model.animation_count}`} model={model} /> :
          <div className="product-model-preview-empty" role="status">暂无模型</div>}
      </DialogContent> : null}
    </Dialog>
  );
}

export default ProductModelPreview;

type ViewerCommands = { reset: () => void; toggle: () => void; seek: (openness: number) => void };

function ModelViewport({ model }: { model: NonNullable<ProductModelPreviewProps["model"]> }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const commands = useRef<ViewerCommands | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [animationState, setAnimationState] = useState<BoxAnimationState | null>(null);
  const opennessId = useId();

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let cancelled = false;
    const abort = new AbortController();
    const disposers: (() => void)[] = [];
    let frame = 0;
    setPhase("loading");
    setError("");
    setAnimationState(null);

    function disposeViewer() {
      cancelAnimationFrame(frame);
      commands.current = null;
      while (disposers.length) {
        try { disposers.pop()!(); } catch { /* Continue releasing the remaining GPU resources. */ }
      }
    }

    function fail(reason: unknown) {
      disposeViewer();
      if (cancelled) return;
      setAnimationState(null);
      setError(reason instanceof Error ? reason.message : "模型读取失败，请重试。");
      setPhase("error");
    }

    async function start() {
      // Keep Three and its loaders out of the unopened product editor's bundle path.
      const [THREE, { GLTFLoader }, { OrbitControls }, { RoomEnvironment }, { MeshoptDecoder }, helpers] = await Promise.all([
        import("three"),
        import("three/addons/loaders/GLTFLoader.js"),
        import("three/addons/controls/OrbitControls.js"),
        import("three/addons/environments/RoomEnvironment.js"),
        import("three/addons/libs/meshopt_decoder.module.js"),
        import("./product-model-preview.helpers")
      ]);
      if (cancelled) return;
      const development = (import.meta as ImportMeta & { env: { DEV: boolean } }).env.DEV;
      const request = helpers.modelFetchRequest(model.url, window.location.href, development);
      const response = await fetch(request.url, { signal: abort.signal, credentials: request.credentials, redirect: "error" });
      if (!response.ok) throw new Error(`读取模型失败（${response.status}）。`);
      const buffer = await response.arrayBuffer();
      if (cancelled) return;
      helpers.validateEmbeddedGlb(buffer);

      const resources = helpers.createModelResources();
      // Parser dependencies may finish after cancellation or after another dependency fails.
      disposers.push(() => resources.dispose());
      const manager = new THREE.LoadingManager();
      manager.setURLModifier(helpers.embeddedResourceUrl);
      let resourceFailed = false;
      manager.onError = () => { resourceFailed = true; };
      const loader = new GLTFLoader(manager).setMeshoptDecoder(MeshoptDecoder);
      loader.register((parser) => {
        const getDependency = parser.getDependency.bind(parser);
        parser.getDependency = (type, index) => getDependency(type, index).then((value: unknown) => {
          resources.track(value);
          return value;
        });
        const loadGeometries = parser.loadGeometries.bind(parser);
        parser.loadGeometries = (primitives) => loadGeometries(primitives).then((geometries) => {
          resources.track(geometries);
          return geometries;
        });
        const loadImageSource = parser.loadImageSource.bind(parser);
        parser.loadImageSource = (index, imageLoader) => loadImageSource(index, imageLoader).then((texture) => {
          resources.track(texture);
          return texture;
        });
        return { name: "SJ_product_model_resources" };
      });
      const gltf = await loader.parseAsync(buffer, "");
      resources.track(gltf.scenes);
      if (cancelled) { resources.dispose(); return; }
      if (resourceFailed) throw new Error("模型内嵌资源读取失败，请重新导出 GLB 文件。");
      const animation = helpers.createBoxAnimation(gltf.scene, gltf.animations);
      disposers.push(() => animation?.dispose());
      const bounds = helpers.animationEnvelope(gltf.scene, gltf.animations, animation);
      const size = bounds.getSize(new THREE.Vector3());
      const largest = Math.max(size.x, size.y, size.z);
      if (bounds.isEmpty() || ![...bounds.min.toArray(), ...bounds.max.toArray(), largest].every(Number.isFinite) || largest <= 0) {
        throw new Error("模型没有可显示的几何体。");
      }
      const center = bounds.getCenter(new THREE.Vector3());
      const scale = 4 / largest;
      const radius = bounds.getBoundingSphere(new THREE.Sphere()).radius * scale;
      const pivot = new THREE.Group();
      pivot.position.copy(center).negate();
      pivot.add(gltf.scene);
      const normalized = new THREE.Group();
      normalized.scale.setScalar(scale);
      normalized.add(pivot);
      const scene = new THREE.Scene();
      scene.background = new THREE.Color("#edf0f2");
      scene.add(normalized);
      disposers.push(() => scene.clear());

      let renderer: import("three").WebGLRenderer;
      try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false }); }
      catch { throw new Error("浏览器无法启用 3D 渲染，请开启硬件加速后重试。"); }
      // Release model resources before the renderer, even on partial setup failure.
      disposers.unshift(() => {
        renderer.renderLists.dispose();
        renderer.dispose();
        renderer.forceContextLoss();
        renderer.domElement.remove();
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 0.85;
      const canvas = renderer.domElement;
      canvas.tabIndex = 0;
      canvas.setAttribute("aria-label", "3D 模型");
      canvas.setAttribute("role", "img");
      host!.appendChild(canvas);
      const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 200);
      const controls = new OrbitControls(camera, canvas);
      disposers.push(() => controls.dispose());
      controls.enableDamping = true;
      controls.dampingFactor = 0.09;
      controls.screenSpacePanning = true;
      controls.minPolarAngle = 0.03;
      controls.maxPolarAngle = Math.PI * 0.97;

      const pmrem = new THREE.PMREMGenerator(renderer);
      const room = new RoomEnvironment();
      try {
        const environment = pmrem.fromScene(room, 0.04);
        scene.environment = environment.texture;
        disposers.push(() => { scene.environment = null; environment.dispose(); });
      } finally { room.dispose(); pmrem.dispose(); }
      const keyLight = new THREE.DirectionalLight(0xffffff, 1.6);
      keyLight.position.set(5, 8, 5);
      scene.add(keyLight, new THREE.HemisphereLight(0xffffff, 0xd4dce0, 0.5));

      function syncAnimation() {
        const state = animation?.getState() ?? null;
        setAnimationState(state);
        host!.dataset.animationCount = String(state?.clipCount ?? 0);
        if (state) {
          host!.dataset.pose = state.pose;
          host!.dataset.animationTime = state.time.toFixed(4);
        }
      }

      function reset() {
        // Clear pending orbit/pan damping before establishing the new reset position.
        controls.enableDamping = false;
        controls.update(0);
        controls.reset();
        const view = helpers.frameSphere(radius, camera.aspect, camera.fov);
        camera.position.copy(new THREE.Vector3(1.15, 0.8, 1.45).normalize().multiplyScalar(view.distance));
        camera.near = view.near;
        camera.far = view.far;
        camera.updateProjectionMatrix();
        controls.target.set(0, 0, 0);
        controls.minDistance = radius * 0.22;
        controls.maxDistance = view.distance * 8;
        controls.update(0);
        controls.enableDamping = true;
        controls.saveState();
      }

      function resize() {
        const width = host!.clientWidth;
        const height = host!.clientHeight;
        if (width <= 0 || height <= 0) return;
        const aspect = width / height;
        const reframe = Math.abs(camera.aspect - aspect) > 0.01;
        camera.aspect = aspect;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height, false);
        if (reframe) reset();
      }

      const observer = new ResizeObserver(resize);
      observer.observe(host!);
      disposers.push(() => observer.disconnect());
      resize();
      reset();
      commands.current = {
        reset,
        toggle: () => { animation?.toggle(); syncAnimation(); },
        seek: (openness) => { if (animation) animation.seek(animation.getState().duration * (1 - openness)); syncAnimation(); }
      };

      function onKeyDown(event: KeyboardEvent) {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        if (event.key.toLowerCase() === "r" || event.key === "Home") {
          event.preventDefault(); reset();
        } else if ((event.key === " " || event.key === "Enter") && animation) {
          event.preventDefault(); commands.current?.toggle();
        } else if (event.key === "+" || event.key === "=" || event.key === "-") {
          event.preventDefault();
          const offset = camera.position.clone().sub(controls.target);
          const distance = THREE.MathUtils.clamp(offset.length() * (event.key === "-" ? 1.15 : 1 / 1.15), controls.minDistance, controls.maxDistance);
          camera.position.copy(controls.target).add(offset.setLength(distance));
          controls.update(0);
        }
      }
      canvas.addEventListener("keydown", onKeyDown);
      controls.listenToKeyEvents(canvas);
      disposers.push(() => canvas.removeEventListener("keydown", onKeyDown));
      function onContextLost(event: Event) {
        event.preventDefault();
        fail(new Error("3D 渲染已中断，请重试。"));
      }
      canvas.addEventListener("webglcontextlost", onContextLost);
      disposers.push(() => canvas.removeEventListener("webglcontextlost", onContextLost));
      syncAnimation();
      let previousTime: number | null = null;
      function render(time: number) {
        if (cancelled) return;
        try {
          const delta = previousTime === null ? 0 : Math.min((time - previousTime) / 1000, 0.1);
          previousTime = time;
          if (animation?.update(delta)) syncAnimation();
          controls.update(delta);
          renderer.render(scene, camera);
          frame = requestAnimationFrame(render);
        } catch (reason) { fail(reason); }
      }
      renderer.render(scene, camera);
      setPhase("ready");
      frame = requestAnimationFrame(render);
    }

    void start().catch((reason: unknown) => { if (!cancelled) fail(reason); });
    return () => { cancelled = true; abort.abort(); disposeViewer(); };
  }, [model.url, attempt]);

  const toggleLabel = animationState?.nextAction === "close" ? "合上礼盒" : "打开礼盒";
  const poseLabel = animationState ? ({ open: "已打开", closed: "已合上", opening: "正在打开", closing: "正在合上", paused: "已暂停" }[animationState.pose]) : "";

  return (
    <TooltipProvider>
      <div className="product-model-preview-body">
        <div className="product-model-preview-stage" data-state={phase} aria-busy={phase === "loading"}>
          <div ref={hostRef} className="product-model-preview-canvas" />
          {phase === "loading" ? <div className="product-model-preview-status" role="status"><Loader2 className="product-model-preview-spin" aria-hidden="true" /><span>正在加载模型…</span></div> : null}
          {phase === "error" ? <div className="product-model-preview-status" role="alert">
            <AlertCircle aria-hidden="true" /><span>{error}</span>
            <Button variant="outline" size="sm" onClick={() => setAttempt((value) => value + 1)}><RefreshCw data-icon="inline-start" />重试</Button>
          </div> : null}
        </div>
        <div className="product-model-preview-toolbar">
          <PreviewIconButton label="重置视角" disabled={phase !== "ready"} onClick={() => commands.current?.reset()}><RotateCcw /></PreviewIconButton>
          {phase === "ready" && animationState ? <>
            <PreviewIconButton label={toggleLabel} aria-pressed={animationState.openness > 0.5} onClick={() => commands.current?.toggle()}>
              {animationState.nextAction === "close" ? <Package /> : <PackageOpen />}
            </PreviewIconButton>
            <label className="sj-sr-only" htmlFor={opennessId}>礼盒打开程度</label>
            <input id={opennessId} className="product-model-preview-range" type="range" min="0" max="100" step="0.1"
              value={animationState.openness * 100} aria-valuetext={`${Math.round(animationState.openness * 100)}%`}
              onChange={(event) => commands.current?.seek(Number(event.target.value) / 100)} />
            <span className="product-model-preview-pose" role="status" aria-live="polite">{poseLabel}</span>
          </> : null}
        </div>
      </div>
    </TooltipProvider>
  );
}

function PreviewIconButton({ label, ...props }: ComponentProps<typeof Button> & { label: string }) {
  return <Tooltip><TooltipTrigger asChild><Button variant="outline" size="icon" aria-label={label} {...props} /></TooltipTrigger><TooltipContent>{label}</TooltipContent></Tooltip>;
}
