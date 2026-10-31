import { lazy, Suspense, useEffect, useId, useRef, useState } from "react";
import { Box, Eye, Loader2, Pipette, Trash2, Upload, X } from "lucide-react";

import { api } from "@/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { ProductModelAsset, ProductModelConfig } from "@/types";
import "./product-model-editor.css";

const ProductModelPreview = lazy(() => import("./product-model-preview"));
const MAX_MODEL_BYTES = 50 * 1024 * 1024;

export function isProductModelHex(value: string) {
  return /^#[0-9a-f]{6}$/i.test(value);
}

export function reconcileProductModelConfig(config: ProductModelConfig | null, colors: Array<{ key: string; name: string }>): ProductModelConfig | null {
  if (!config) return null;
  const sku_colors = Object.fromEntries(colors.filter(({ key }) => Object.prototype.hasOwnProperty.call(config.sku_colors, key)).map(({ key }) => [key, config.sku_colors[key]]));
  const configuredKeys = colors.filter(({ key }) => isProductModelHex(sku_colors[key] || "")).map(({ key }) => key);
  return {
    ...config,
    sku_colors,
    default_sku_key: config.default_sku_key && configuredKeys.includes(config.default_sku_key) ? config.default_sku_key : configuredKeys[0] ?? null,
  };
}

export function replaceProductModelConfig(config: ProductModelConfig | null, assetId: number): ProductModelConfig {
  return {
    version: 1,
    asset_id: assetId,
    material_index: null,
    sku_colors: { ...config?.sku_colors },
    default_sku_key: config?.default_sku_key ?? null,
    camera_direction: null,
    default_pose: "open",
  };
}

export function updateProductModelColor(config: ProductModelConfig, key: string, value: string, colors?: Array<{ key: string; name: string }>): ProductModelConfig {
  const sku_colors = { ...config.sku_colors };
  if (value === "") delete sku_colors[key];
  else sku_colors[key] = value;
  return reconcileProductModelConfig({ ...config, sku_colors }, colors ?? Object.keys(sku_colors).map((key) => ({ key, name: key })))!;
}

export function isProductModelConfigValid(config: ProductModelConfig | null) {
  if (!config) return true;
  const values = Object.values(config.sku_colors);
  return values.every(isProductModelHex) && (!values.length || config.material_index !== null);
}

function ModelSkuColor({ name, value, disabled, onChange }: { name: string; value: string; disabled: boolean; onChange: (value: string) => void }) {
  const id = useId();
  const picker = useRef<HTMLInputElement>(null);
  const valid = isProductModelHex(value);
  const invalid = Boolean(value) && !valid;
  return (
    <Field className="product-model-color-row" data-invalid={invalid || undefined}>
      <FieldLabel htmlFor={id} className="product-model-color-name">{name}</FieldLabel>
      <div className="product-model-color-inputs">
        <input ref={picker} type="color" hidden value={valid ? value : "#000000"} disabled={disabled} aria-label={`${name}模型颜色取色器`} onChange={(event) => onChange(event.currentTarget.value)} />
        <Button type="button" variant="outline" size="icon-sm" disabled={disabled} aria-label={`${name}模型颜色`} title={`${name}模型颜色`} onClick={() => picker.current?.click()}>
          {valid ? <span className="product-model-color-chip" style={{ backgroundColor: value }} /> : <Pipette />}
        </Button>
        <Input id={id} className="product-model-hex" value={value} placeholder="未设置" aria-label={`${name} HEX 色值`} aria-invalid={invalid} disabled={disabled} spellCheck={false} autoComplete="off" onChange={(event) => onChange(event.currentTarget.value)} />
        <Button type="button" variant="ghost" size="icon-sm" disabled={disabled || !value} aria-label={`清除${name}颜色`} title={`清除${name}颜色`} onClick={() => onChange("")}><X /></Button>
      </div>
      {invalid ? <span className="form-error" role="alert">请输入完整的 #RRGGBB 颜色</span> : null}
    </Field>
  );
}

type Props = {
  model: ProductModelAsset | null;
  config: ProductModelConfig | null;
  colors: Array<{ key: string; name: string }>;
  onConfigChange: (config: ProductModelConfig | null) => void;
  disabled: boolean;
  onChange: (model: ProductModelAsset | null) => void;
  onUploaded: (model: ProductModelAsset) => void;
  onBusyChange: (busy: boolean) => void;
};

export function ProductModelEditor({ model, config, colors, disabled, onChange, onConfigChange, onUploaded, onBusyChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadLock = useRef(false);
  const active = useRef(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);
  const latestDraft = useRef({ config, colors });
  latestDraft.current = { config, colors };
  const materialId = useId();
  const defaultId = useId();

  useEffect(() => {
    active.current = true;
    return () => { active.current = false; };
  }, []);

  async function upload(file?: File) {
    if (!file || disabled || uploadLock.current) return;
    if (!/\.glb$/i.test(file.name)) { setError("只支持贴图内嵌的 GLB 模型"); return; }
    if (!file.size || file.size > MAX_MODEL_BYTES) { setError("请选择不超过 50MB 的非空 GLB 文件"); return; }
    uploadLock.current = true;
    onBusyChange(true);
    setUploading(true);
    setProgress(0);
    setError("");
    try {
      const asset = await api.uploadProductModel(file, (value) => { if (active.current) setProgress(value); });
      if (!active.current) {
        await api.deletePendingProductModel(asset.id).catch(() => undefined);
        return;
      }
      onUploaded(asset);
      onChange(asset);
      onConfigChange(reconcileProductModelConfig(replaceProductModelConfig(latestDraft.current.config, asset.id), latestDraft.current.colors));
    } catch (err) {
      if (active.current) setError(err instanceof Error ? err.message : "模型上传失败");
    } finally {
      uploadLock.current = false;
      if (active.current) {
        setUploading(false);
        onBusyChange(false);
      }
    }
  }

  const busy = disabled || uploading;
  const draft = model ? config ?? replaceProductModelConfig(null, model.id) : null;
  const configuredColors = colors.filter(({ key }) => isProductModelHex(draft?.sku_colors[key] || ""));
  const defaultKey = configuredColors.some(({ key }) => key === draft?.default_sku_key) ? draft!.default_sku_key! : configuredColors[0]?.key;
  return (
    <section className="product-model-editor" aria-label="商品 3D 模型">
      <input ref={inputRef} type="file" accept=".glb,model/gltf-binary" aria-label="选择 GLB 模型" hidden disabled={busy} onChange={(event) => {
        const file = event.currentTarget.files?.[0];
        event.currentTarget.value = "";
        void upload(file);
      }} />
      {model ? (
        <div className="product-model-file">
          <Box aria-hidden="true" />
          <div className="product-model-meta">
            <strong>{model.file_name}</strong>
            <span>{(model.byte_size / 1024 / 1024).toFixed(2)} MB <Badge variant="secondary">{model.animation_count ? `${model.animation_count} 段动画` : "静态模型"}</Badge></span>
          </div>
          <div className="product-model-actions">
            <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => setPreviewOpen(true)}><Eye data-icon="inline-start" />预览</Button>
            <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => inputRef.current?.click()}><Upload data-icon="inline-start" />更换</Button>
            <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={() => { setError(""); setPreviewOpen(false); onChange(null); onConfigChange(null); }}><Trash2 data-icon="inline-start" />解除绑定</Button>
          </div>
        </div>
      ) : (
        <Empty>
          <EmptyHeader><Box aria-hidden="true" /><EmptyTitle>未绑定模型</EmptyTitle></EmptyHeader>
          <EmptyContent><Button type="button" variant="outline" disabled={busy} onClick={() => inputRef.current?.click()}><Upload data-icon="inline-start" />上传 GLB 模型</Button></EmptyContent>
        </Empty>
      )}
      {model && draft ? (
        <FieldGroup className="product-model-config">
          <Field>
            <FieldLabel htmlFor={materialId}>换色材质</FieldLabel>
            <Select value={draft.material_index === null ? "unset" : String(draft.material_index)} disabled={busy} onValueChange={(value) => onConfigChange({ ...draft, material_index: value === "unset" ? null : Number(value) })}>
              <SelectTrigger id={materialId}><SelectValue placeholder="选择材质" /></SelectTrigger>
              <SelectContent><SelectGroup>
                <SelectItem value="unset">未选择</SelectItem>
                {model.materials.map((material) => <SelectItem key={material.index} value={String(material.index)}>{material.name.trim() || "未命名材质"} · #{material.index}</SelectItem>)}
              </SelectGroup></SelectContent>
            </Select>
          </Field>
          {colors.map(({ key, name }) => <ModelSkuColor key={key} name={name} value={draft.sku_colors[key] ?? ""} disabled={busy} onChange={(value) => onConfigChange(updateProductModelColor(draft, key, value, colors))} />)}
          <Field>
            <FieldLabel htmlFor={defaultId}>默认颜色</FieldLabel>
            <Select value={defaultKey ?? ""} disabled={busy || !configuredColors.length} onValueChange={(key) => onConfigChange({ ...draft, default_sku_key: key })}>
              <SelectTrigger id={defaultId}><SelectValue placeholder="未设置" /></SelectTrigger>
              <SelectContent><SelectGroup>{configuredColors.map(({ key, name }) => <SelectItem key={key} value={key}>{name}</SelectItem>)}</SelectGroup></SelectContent>
            </Select>
          </Field>
          {Object.keys(draft.sku_colors).length > 0 && draft.material_index === null ? <div className="form-error" role="alert">请选择换色材质</div> : null}
        </FieldGroup>
      ) : null}
      {uploading ? (
        <div className="product-model-progress" role="status">
          <span><Loader2 className="product-model-spinner" />{progress < 100 ? `正在上传文件 ${progress}%` : "正在保存模型…"}</span>
          <progress max={100} value={progress} aria-label="模型文件上传进度" />
        </div>
      ) : null}
      {error ? <div className="form-error" role="alert">{error}</div> : null}
      {previewOpen && model ? <Suspense fallback={<div role="status">正在加载预览…</div>}><ProductModelPreview open={previewOpen} onOpenChange={setPreviewOpen} model={model} config={draft} colors={colors} onConfigChange={onConfigChange} /></Suspense> : null}
    </section>
  );
}
