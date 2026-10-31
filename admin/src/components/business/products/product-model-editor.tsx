import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Box, Eye, Loader2, Trash2, Upload } from "lucide-react";

import { api } from "@/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import type { ProductModelAsset } from "@/types";
import "./product-model-editor.css";

const ProductModelPreview = lazy(() => import("./product-model-preview"));
const MAX_MODEL_BYTES = 50 * 1024 * 1024;

type Props = {
  model: ProductModelAsset | null;
  disabled: boolean;
  onChange: (model: ProductModelAsset | null) => void;
  onUploaded: (model: ProductModelAsset) => void;
  onBusyChange: (busy: boolean) => void;
};

export function ProductModelEditor({ model, disabled, onChange, onUploaded, onBusyChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const uploadLock = useRef(false);
  const active = useRef(true);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);

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
            <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={() => { setError(""); onChange(null); }}><Trash2 data-icon="inline-start" />解除绑定</Button>
          </div>
        </div>
      ) : (
        <Empty>
          <EmptyHeader><Box aria-hidden="true" /><EmptyTitle>未绑定模型</EmptyTitle></EmptyHeader>
          <EmptyContent><Button type="button" variant="outline" disabled={busy} onClick={() => inputRef.current?.click()}><Upload data-icon="inline-start" />上传 GLB 模型</Button></EmptyContent>
        </Empty>
      )}
      {uploading ? (
        <div className="product-model-progress" role="status">
          <span><Loader2 className="product-model-spinner" />{progress < 100 ? `正在上传文件 ${progress}%` : "正在保存模型…"}</span>
          <progress max={100} value={progress} aria-label="模型文件上传进度" />
        </div>
      ) : null}
      {error ? <div className="form-error" role="alert">{error}</div> : null}
      {previewOpen && model ? <Suspense fallback={<div role="status">正在加载预览…</div>}><ProductModelPreview open={previewOpen} onOpenChange={setPreviewOpen} model={model} /></Suspense> : null}
    </section>
  );
}
