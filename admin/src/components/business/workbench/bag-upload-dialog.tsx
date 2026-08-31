import { useEffect, useRef, useState, type ComponentProps } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Check, FileArchive, Loader2, RefreshCw, Upload } from "lucide-react";

import { api, ApiError } from "@/api";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { queryKeys } from "@/lib/admin-query";
import type { BagUploadResult } from "@/types";
import {
  BAG_TYPES,
  canStartBagUpload,
  changeBagType,
  claimBagUpload,
  formatBagFileSize,
  initialBagUploadForm,
  isValidBagPrice,
  validateBagArchive,
  type BagUploadPhase
} from "./bag-upload-dialog.helpers";
import "./bag-upload-dialog.css";

type BagUploadDialogProps = {
  onClose: () => void;
  onComplete: (result: BagUploadResult, filename: string) => void;
  returnFocus: HTMLElement | null;
};

export function BagUploadDialog({ onClose, onComplete, returnFocus }: BagUploadDialogProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(initialBagUploadForm);
  const [archive, setArchive] = useState<File | null>(null);
  const [archiveBytes, setArchiveBytes] = useState<number | null>(null);
  const [limitsError, setLimitsError] = useState("");
  const [limitsAttempt, setLimitsAttempt] = useState(0);
  const [phase, setPhase] = useState<BagUploadPhase>("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<BagUploadResult | null>(null);
  const submitLock = useRef(false);
  const phaseRef = useRef<BagUploadPhase>("idle");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const statusRef = useRef<HTMLDivElement>(null);
  const isUploading = phase === "uploading";
  const fieldsDisabled = phase !== "idle";
  const priceInvalid = !isValidBagPrice(form.price);
  const archiveError = archive ? validateBagArchive(archive, archiveBytes) : "";
  const submission = { phase, price: form.price, archive, archiveBytes };

  useEffect(() => {
    let active = true;
    setLimitsError("");
    api.agentUploadLimits()
      .then((limits) => {
        if (!Number.isFinite(limits.archive_bytes) || limits.archive_bytes <= 0) throw new Error("上传大小限制无效");
        if (active) setArchiveBytes(limits.archive_bytes);
      })
      .catch((err) => {
        if (active) setLimitsError(err instanceof Error ? err.message : "无法获取上传大小限制");
      });
    return () => { active = false; };
  }, [limitsAttempt]);

  useEffect(() => {
    if (phase !== "idle" || error) statusRef.current?.focus();
  }, [phase, error]);

  function changeOpen(open: boolean) {
    if (submitLock.current) return;
    if (!open) onClose();
  }

  async function startUpload() {
    if (!archive || !claimBagUpload(submitLock, { ...submission, phase: phaseRef.current })) return;
    phaseRef.current = "uploading";
    setError("");
    setPhase("uploading");
    let data: BagUploadResult;
    try {
      data = await api.uploadBags(archive, {
        bag_type: form.bagType,
        price: form.price,
        is_listed: form.isListed
      });
      if (!data || !Array.isArray(data.success) || !Array.isArray(data.failures)) {
        throw new Error("服务器未返回完整处理结果");
      }
    } catch (err) {
      const uncertain = !(err instanceof ApiError) || err.status >= 500 || err.status === 408 || (err.status < 400 && err.code === -1);
      setError(uncertain ? "处理结果未知，请先核对商品库，确认已完成的商品后再操作。请勿直接重传整包。" : (err instanceof Error ? err.message : "上传失败"));
      phaseRef.current = uncertain ? "uncertain" : "idle";
      setPhase(uncertain ? "uncertain" : "idle");
      submitLock.current = false;
      if (uncertain) void queryClient.invalidateQueries({ queryKey: queryKeys.products.root }).catch(() => undefined);
      return;
    }
    setResult(data);
    phaseRef.current = "complete";
    setPhase("complete");
    submitLock.current = false;
    void queryClient.invalidateQueries({ queryKey: queryKeys.products.root }).catch(() => undefined);
    onComplete(data, archive.name);
  }

  return (
    <Dialog open onOpenChange={changeOpen}>
      <DialogContent
        className="bag-upload-dialog"
        showCloseButton={!isUploading}
        aria-describedby={undefined}
        onEscapeKeyDown={(event) => { if (submitLock.current) event.preventDefault(); }}
        onInteractOutside={(event) => { if (submitLock.current) event.preventDefault(); }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          returnFocus?.focus();
        }}
        onDragOver={(event) => { event.preventDefault(); event.stopPropagation(); }}
        onDrop={(event) => { event.preventDefault(); event.stopPropagation(); }}
      >
        <DialogHeader>
          <DialogTitle>泡袋上传</DialogTitle>
        </DialogHeader>
        <form className="bag-upload-form" onSubmit={(event) => { event.preventDefault(); void startUpload(); }} aria-busy={isUploading}>
          <FieldGroup>
            <Field data-disabled={fieldsDisabled || undefined}>
              <FieldLabel id="bag-upload-type-label">泡袋类型</FieldLabel>
              <Tabs value={form.bagType} onValueChange={(value) => setForm((current) => changeBagType(current, value))} activationMode="automatic">
                <TabsList className="bag-upload-type-tabs" aria-labelledby="bag-upload-type-label">
                  {BAG_TYPES.map((bagType) => (
                    <TabsTrigger key={bagType} value={bagType} disabled={fieldsDisabled}>{bagType}</TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            </Field>
            <Field data-invalid={priceInvalid || undefined} data-disabled={fieldsDisabled || undefined}>
              <FieldLabel htmlFor="bag-upload-price">售价（元/捆）</FieldLabel>
              <Input
                id="bag-upload-price"
                inputMode="decimal"
                value={form.price}
                disabled={fieldsDisabled}
                aria-invalid={priceInvalid}
                aria-describedby={priceInvalid ? "bag-upload-price-error" : undefined}
                onChange={(event) => setForm((current) => ({ ...current, price: event.target.value }))}
              />
              {priceInvalid ? <FieldError id="bag-upload-price-error">请输入不超过 9999999999.99 的正数，最多 10 位整数、2 位小数</FieldError> : null}
            </Field>
            <Field orientation="horizontal" className="bag-upload-listed" data-disabled={fieldsDisabled || undefined}>
              <Checkbox id="bag-upload-listed" checked={form.isListed} disabled={fieldsDisabled} onCheckedChange={(checked) => setForm((current) => ({ ...current, isListed: checked === true }))} />
              <FieldLabel htmlFor="bag-upload-listed">上传完成后上架</FieldLabel>
            </Field>
            <Field data-invalid={Boolean(archiveError) || undefined} data-disabled={fieldsDisabled || undefined}>
              <FieldLabel htmlFor="bag-upload-file">ZIP 文件</FieldLabel>
              <Input
                id="bag-upload-file"
                ref={fileInputRef}
                type="file"
                accept=".zip,application/zip,application/x-zip-compressed"
                hidden
                disabled={fieldsDisabled}
                aria-invalid={Boolean(archiveError)}
                onChange={(event) => {
                  if (submitLock.current) return;
                  const next = event.target.files?.[0];
                  if (next) { setArchive(next); setError(""); }
                  event.target.value = "";
                }}
              />
              <div className="bag-upload-file-row">
                {archive ? <div id="bag-upload-file-info" className="bag-upload-file-info"><FileArchive aria-hidden="true" /><span>{archive.name}</span><small>{formatBagFileSize(archive.size)}</small></div> : null}
                <Button variant="outline" disabled={fieldsDisabled} onClick={() => fileInputRef.current?.click()} aria-describedby={archive ? "bag-upload-file-info" : undefined}>
                  <Upload data-icon="inline-start" />{archive ? "更换文件" : "选择压缩包"}
                </Button>
              </div>
              {archiveError ? <FieldError>{archiveError}</FieldError> : null}
            </Field>
          </FieldGroup>
          {limitsError ? <Alert variant="destructive"><AlertCircle /><AlertTitle>无法获取上传限制</AlertTitle><AlertDescription>{limitsError}<Button variant="outline" size="sm" onClick={() => setLimitsAttempt((attempt) => attempt + 1)}><RefreshCw data-icon="inline-start" />重新获取</Button></AlertDescription></Alert> : null}
          {!archiveBytes && !limitsError ? <div className="bag-upload-status" role="status"><Loader2 className="workbench-spin" />正在获取上传限制</div> : null}
          {isUploading ? <div className="bag-upload-status" role="status" tabIndex={-1} ref={statusRef}><Loader2 className="workbench-spin" />正在上传并处理…</div> : null}
          {error ? <Alert variant="destructive" tabIndex={-1} ref={statusRef}><AlertCircle /><AlertTitle>{phase === "uncertain" ? "处理结果未知" : "上传失败"}</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}
          {result ? <div className="bag-upload-results" tabIndex={-1} ref={statusRef}>
            <Alert role="status"><Check /><AlertTitle>{result.failures.length ? "处理完成，存在失败文件" : "上传完成"}</AlertTitle><AlertDescription>共 {result.total} 个，成功 {result.success.length} 个，失败 {result.failures.length} 个</AlertDescription></Alert>
            {result.success.length ? <section aria-labelledby="bag-upload-success-title"><h3 id="bag-upload-success-title">成功商品（{result.success.length}）</h3><Table className="bag-upload-success-table"><TableHeader><TableRow><TableHead>商品名</TableHead><TableHead>编号</TableHead><TableHead>分类</TableHead><TableHead>售价</TableHead><TableHead>上架</TableHead></TableRow></TableHeader><TableBody>
              {result.success.map((item) => <TableRow key={item.index}><TableCell>{item.title}</TableCell><TableCell>{item.code}</TableCell><TableCell>{item.category_name}</TableCell><TableCell>{item.price.toFixed(2)}</TableCell><TableCell>{item.is_listed ? "已上架" : "未上架"}</TableCell></TableRow>)}
            </TableBody></Table></section> : null}
            {result.failures.length ? <section aria-labelledby="bag-upload-failures-title"><h3 id="bag-upload-failures-title">失败文件（{result.failures.length}）</h3><Table className="bag-upload-failure-table"><TableHeader><TableRow><TableHead>文件名</TableHead><TableHead>原因</TableHead></TableRow></TableHeader><TableBody>
              {result.failures.map((item) => <TableRow key={item.index}><TableCell>{item.filename || item.title}</TableCell><TableCell>{item.error}</TableCell></TableRow>)}
            </TableBody></Table></section> : null}
          </div> : null}
          <DialogFooter>
            <Button variant="outline" disabled={isUploading} onClick={() => changeOpen(false)}>{phase === "uncertain" ? "关闭核对" : result ? "关闭" : "取消"}</Button>
            {phase === "idle" || isUploading ? <Button type="submit" disabled={!canStartBagUpload(submission)}>{isUploading ? <Loader2 className="workbench-spin" data-icon="inline-start" /> : <Upload data-icon="inline-start" />}{isUploading ? "处理中" : "开始上传"}</Button> : null}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Alert({ variant = "default", ...props }: ComponentProps<"div"> & { variant?: "default" | "destructive" }) {
  return <div role="alert" data-slot="alert" data-variant={variant} className="bag-upload-alert" {...props} />;
}

function AlertTitle(props: ComponentProps<"div">) {
  return <div data-slot="alert-title" {...props} />;
}

function AlertDescription(props: ComponentProps<"div">) {
  return <div data-slot="alert-description" {...props} />;
}
