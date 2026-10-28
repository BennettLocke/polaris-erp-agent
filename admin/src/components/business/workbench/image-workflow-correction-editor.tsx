import { useEffect, useRef, useState } from "react";
import { Check, ImageIcon, Loader2, Search, X } from "lucide-react";

import { api } from "@/api";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import type { SalesProduct } from "@/types";
import { productDisplaySpec, productDisplayTitle, productVariants } from "../sales-create/utils";

type CorrectionRow = Record<string, unknown> & {
  correction_id: string;
  original_goods_name: string;
  original_color: string;
};

function text(value: unknown) {
  return value == null ? "" : String(value);
}

function positive(value: unknown) {
  return Number.isFinite(Number(value)) && Number(value) > 0;
}

function sellable(product: SalesProduct) {
  const candidate = product as SalesProduct & { is_sellable?: boolean | number; native_status?: string; status?: string | number };
  const value = candidate.is_sellable;
  const status = String(candidate.native_status ?? candidate.status ?? "active").toLowerCase();
  return value !== false && value !== 0 && ["active", "normal", "enabled", "0"].includes(status);
}

export function imageCorrectionMessage(value: unknown, fallback: string) {
  const message = text(value).trim();
  return !message || /traceback|\bsql\b|exception|stack trace|internal server error|bad gateway|service unavailable|failed to fetch|https?:\/\/|\/internal\/|[A-Z]:\\|\b(?:TypeError|ValueError|RuntimeError)\b/i.test(message)
    ? fallback
    : message;
}

function initializeState(state: Record<string, unknown>) {
  const rows = Array.isArray(state.parsed_list) ? state.parsed_list : [];
  return {
    ...state,
    customer_name: text(state.customer_name ?? state.customer),
    parsed_list: rows.map((value, index): CorrectionRow => {
      const row = value && typeof value === "object" ? value as Record<string, unknown> : {};
      return {
        ...row,
        correction_id: text(row.correction_id || `image-correction-${index + 1}`),
        original_goods_name: text(row.original_goods_name ?? row.goods_name),
        original_color: text(row.original_color ?? row.color),
        raw_quantity: row.raw_quantity ?? row.quantity ?? "",
        raw_unit: row.raw_unit ?? row.unit ?? ""
      };
    })
  };
}

function CorrectionRowEditor({ row, index, disabled, onChange }: {
  row: CorrectionRow;
  index: number;
  disabled: boolean;
  onChange: (patch: Record<string, unknown>) => void;
}) {
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<SalesProduct[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");
  const requestRef = useRef<{ version: number; controller?: AbortController }>({ version: 0 });

  function changeKeyword(value: string) {
    // Invalidate immediately, before the next effect, including APIs ignoring abort.
    requestRef.current.version += 1;
    requestRef.current.controller?.abort();
    setKeyword(value);
    setResults([]);
    setError("");
    setSearched(false);
    setLoading(Boolean(value.trim()));
  }

  useEffect(() => {
    const query = keyword.trim();
    if (!query || disabled) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    const version = ++requestRef.current.version;
    requestRef.current.controller = controller;
    const current = () => !controller.signal.aborted && version === requestRef.current.version;
    setLoading(true);
    const timer = window.setTimeout(() => {
      // Sales search intentionally has no listed-only filter: unlisted SKUs can sell.
      api.searchProductsForSales(query, 20, { signal: controller.signal })
        .then((data) => { if (current()) { setResults(data.list || []); setSearched(true); } })
        .catch(() => { if (current()) setError("商品搜索暂时不可用，请稍后重新搜索。"); })
        .finally(() => { if (current()) setLoading(false); });
    }, 300);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [keyword, disabled]);

  const groups = results.map((product) => ({
    product,
    variants: productVariants(product).filter((variant) => sellable(variant) && positive(variant.id || variant.product_id))
  })).filter((group) => group.variants.length);
  const selected = positive(row.selected_sku_id) || positive(row.product_id);
  const prefix = `image-correction-${index}`;

  function choose(product: SalesProduct, variant: SalesProduct) {
    if (disabled || !sellable(variant)) return;
    const id = Number(variant.id || variant.product_id);
    if (!positive(id)) return;
    onChange({
      selected_sku_id: id,
      product_id: id,
      goods_name: variant.title || variant.name || productDisplayTitle(product),
      color: variant.spec || variant.color || "",
      sku_no: variant.sku_no || variant.coding || "",
      piece_text: variant.piece_text || product.piece_text || ""
    });
  }

  return (
    <article className="image-correction-row" aria-label={`设计稿 ${index + 1}`}>
      <div className="image-correction-source">
        {row.preview_url ? <img src={text(row.preview_url)} alt={`设计稿 ${index + 1} 原图`} /> : <div className="image-correction-no-preview"><ImageIcon aria-hidden="true" /></div>}
        <div>
          <strong>设计稿 {index + 1}</strong>
          <p className="image-correction-filename">{text(row.source_filename) || "未命名设计稿"}</p>
          <dl><dt>原始识别</dt><dd>{row.original_goods_name || "未识别商品"}</dd><dt>原始颜色</dt><dd>{row.original_color || "未识别颜色"}</dd></dl>
          {row.recognition_error ? <p className="image-correction-recognition-error">{imageCorrectionMessage(row.recognition_error, "识别未完成，请重新选择商品。")}</p> : null}
        </div>
      </div>
      <div className="image-correction-replacement" role="status">
        <strong>替换为</strong>
        <span>{selected ? `${text(row.goods_name)} · ${text(row.color) || "默认颜色"}${row.sku_no ? ` · ${text(row.sku_no)}` : ""}${row.piece_text ? ` · ${text(row.piece_text)}` : ""}` : "尚未选择商品"}</span>
      </div>
      <Field>
        <FieldLabel htmlFor={`${prefix}-search`}>搜索替换商品</FieldLabel>
        <div className="image-correction-search">
          <Search aria-hidden="true" />
          <Input id={`${prefix}-search`} value={keyword} placeholder="商品名称、颜色或 SKU" disabled={disabled} onChange={(event) => changeKeyword(event.target.value)} />
          {loading ? <Loader2 className="workbench-spin" aria-label="搜索中" /> : null}
        </div>
      </Field>
      {error ? <p className="image-correction-error" role="alert">{error}</p> : null}
      {groups.length ? <div className="image-correction-results" aria-label="商品搜索结果">
        {groups.map(({ product, variants }, groupIndex) => <section key={`${product.id || product.product_id}-${groupIndex}`}>
          <header><strong>{productDisplayTitle(product)}</strong>{product.piece_text ? <span>件规：{product.piece_text}</span> : null}</header>
          <div className="image-correction-skus">
            {variants.map((variant) => {
              const id = Number(variant.id || variant.product_id);
              const active = Number(row.selected_sku_id || row.product_id) === id;
              return <Button key={id} variant={active ? "secondary" : "outline"} aria-pressed={active} disabled={disabled} onClick={() => choose(product, variant)}>
                <strong>{productDisplaySpec(variant)}</strong>
                <span>{variant.sku_no || variant.coding || `SKU ${id}`}{variant.piece_text || product.piece_text ? ` · ${variant.piece_text || product.piece_text}` : ""}</span>
              </Button>;
            })}
          </div>
        </section>)}
      </div> : searched && !loading && !error ? <p className="image-correction-empty">未找到可销售商品</p> : null}
      <div className="image-correction-fields">
        <Field><FieldLabel htmlFor={`${prefix}-quantity`}>数量</FieldLabel><Input id={`${prefix}-quantity`} type="number" inputMode="decimal" min="0" step="any" disabled={disabled} value={text(row.raw_quantity)} onChange={(event) => onChange({ raw_quantity: event.target.value === "" ? "" : Number(event.target.value) })} /></Field>
        <Field><FieldLabel htmlFor={`${prefix}-unit`}>单位</FieldLabel><Input id={`${prefix}-unit`} disabled={disabled} value={text(row.raw_unit)} onChange={(event) => onChange({ raw_unit: event.target.value })} /></Field>
        <Field className="image-correction-remark"><FieldLabel htmlFor={`${prefix}-remark`}>备注</FieldLabel><Input id={`${prefix}-remark`} disabled={disabled} value={text(row.remark ?? row.note)} onChange={(event) => onChange({ remark: event.target.value })} /></Field>
      </div>
    </article>
  );
}

export function ImageWorkflowCorrectionEditor({ state, confirming, error, onConfirm, onCancel }: {
  state: Record<string, unknown>;
  confirming: boolean;
  error: string;
  onConfirm: (state: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(() => initializeState(state));
  const valid = Boolean(draft.customer_name.trim()) && draft.parsed_list.length > 0
    && draft.parsed_list.every((row) => (positive(row.selected_sku_id) || positive(row.product_id)) && positive(row.raw_quantity)
      && ["件", "套", "个", "只", "盒", "张", "捆"].includes(text(row.raw_unit).trim()));
  const cancel = () => { if (!confirming) onCancel(); };

  return (
    <Dialog open onOpenChange={(open) => { if (!open) cancel(); }}>
      <DialogContent
        className="image-correction-dialog"
        showCloseButton={false}
        onEscapeKeyDown={(event) => { event.preventDefault(); cancel(); }}
        onInteractOutside={(event) => event.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>设计稿识别校准</DialogTitle>
          <DialogDescription>本批尚未创建订单</DialogDescription>
        </DialogHeader>
        <Button
          className="image-correction-close"
          size="icon-sm"
          variant="ghost"
          aria-label="关闭校正"
          title="关闭校正"
          disabled={confirming}
          onClick={cancel}
        >
          <X />
        </Button>
        {error ? (
          <div className="image-correction-error" role="alert">
            {imageCorrectionMessage(error, "校正未提交，请稍后重试。")}
          </div>
        ) : null}
        <Field>
          <FieldLabel htmlFor="image-correction-customer">本批客户</FieldLabel>
          <Input
            id="image-correction-customer"
            value={draft.customer_name}
            disabled={confirming}
            onChange={(event) => setDraft((current) => ({ ...current, customer_name: event.target.value }))}
          />
        </Field>
        <div className="image-correction-rows">
          {draft.parsed_list.map((row, index) => (
            <CorrectionRowEditor
              key={row.correction_id}
              row={row}
              index={index}
              disabled={confirming}
              onChange={(patch) => {
                if (confirming) return;
                setDraft((current) => ({
                  ...current,
                  parsed_list: current.parsed_list.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item)
                }));
              }}
            />
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" disabled={confirming} onClick={cancel}>取消</Button>
          <Button disabled={confirming || !valid} onClick={() => { if (!confirming && valid) onConfirm(draft); }}>
            {confirming ? <Loader2 className="workbench-spin" /> : <Check />}
            确认校正并继续
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
