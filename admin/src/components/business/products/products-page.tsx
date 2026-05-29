import { useCallback, useEffect, useRef, useState, type PointerEvent, type WheelEvent } from "react";
import { ImagePlus, MoreHorizontal, Pencil, Plus, RefreshCw, Search, Trash2, Upload, X } from "lucide-react";

import { ApiError, api } from "@/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from "@/components/ui/alert-dialog";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldContent, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger
} from "@/components/ui/dropdown-menu";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious
} from "@/components/ui/pagination";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import type {
  ProductCategory,
  ProductItem,
  ProductMediaAsset,
  ProductSavePayload,
  ProductStatusOption,
  ProductUnit
} from "@/types";

function money(value?: string | number) {
  const raw = value === undefined || value === null || value === "" ? "0" : String(value);
  const num = Number(raw);
  return Number.isFinite(num) ? `\u00a5${num.toFixed(2)}` : `\u00a5${raw}`;
}

function inputNoWheel(event: WheelEvent<HTMLInputElement>) {
  event.currentTarget.blur();
}

const PRODUCT_TYPE_META: Record<string, { label: string; order: number }> = {
  gift_box: { label: "礼盒", order: 10 },
  box: { label: "礼盒", order: 10 },
  bag: { label: "泡袋", order: 20 },
  bubble_bag: { label: "泡袋", order: 20 },
  accessory: { label: "辅料", order: 30 },
  material: { label: "辅料", order: 30 },
  shipping: { label: "纸箱", order: 40 },
  carton: { label: "纸箱", order: 40 },
  other: { label: "其他", order: 90 }
};

type ProductTypeTab = {
  key: string;
  label: string;
  total: number;
  order: number;
};

type ProductFilterOption = {
  value: string;
  label: string;
};

const LISTED_FILTERS: ProductFilterOption[] = [
  { value: "", label: "全部状态" },
  { value: "listed", label: "已上架" },
  { value: "unlisted", label: "未上架" }
];

const STOCK_FILTERS: ProductFilterOption[] = [
  { value: "", label: "全部库存" },
  { value: "stock", label: "扣库存" },
  { value: "non_stock", label: "不扣库存" }
];

const QUALITY_FILTERS: ProductFilterOption[] = [
  { value: "", label: "全部资料" },
  { value: "missing_image", label: "无主图" },
  { value: "missing_case_pack", label: "缺件规" },
  { value: "missing_price", label: "缺价格" }
];

const PRODUCT_CARD_MIN_WIDTH = 208;
const PRODUCT_GRID_GAP = 10;
const PRODUCT_PAGE_SIZE_MIN = 20;
const PRODUCT_PAGE_SIZE_MAX = 60;
const PRODUCT_PAGE_SIZE_BUFFER_ROWS = 1;
const PRODUCT_CARD_ESTIMATED_HEIGHT = 400;
const PRODUCT_GRID_TOP_FALLBACK = 520;
const PRODUCT_PAGE_SIZE_RESIZE_DELAY = 160;

type ProductPageSizeMetrics = {
  gridWidth: number;
  viewportHeight: number;
  gridTop: number;
  cardHeight?: number;
};

function clampProductPageSize(value: number) {
  return Math.min(PRODUCT_PAGE_SIZE_MAX, Math.max(PRODUCT_PAGE_SIZE_MIN, value));
}

function calculateProductPageSize({
  gridWidth,
  viewportHeight,
  gridTop,
  cardHeight = PRODUCT_CARD_ESTIMATED_HEIGHT
}: ProductPageSizeMetrics) {
  const safeCardHeight = Math.max(280, cardHeight);
  const columns = Math.max(
    1,
    Math.floor((Math.max(1, gridWidth) + PRODUCT_GRID_GAP) / (PRODUCT_CARD_MIN_WIDTH + PRODUCT_GRID_GAP))
  );
  const availableHeight = Math.max(safeCardHeight, viewportHeight - gridTop - 72);
  const visibleRows = Math.max(2, Math.ceil(availableHeight / safeCardHeight));
  return clampProductPageSize(columns * (visibleRows + PRODUCT_PAGE_SIZE_BUFFER_ROWS));
}

function initialProductPageSize() {
  if (typeof window === "undefined") return PRODUCT_PAGE_SIZE_MIN;
  return calculateProductPageSize({
    gridWidth: Math.max(PRODUCT_CARD_MIN_WIDTH, window.innerWidth - 320),
    viewportHeight: window.innerHeight,
    gridTop: PRODUCT_GRID_TOP_FALLBACK
  });
}

function measuredProductPageSize(gridElement: HTMLDivElement | null) {
  if (typeof window === "undefined" || !gridElement) return PRODUCT_PAGE_SIZE_MIN;
  const gridRect = gridElement.getBoundingClientRect();
  const firstCard = gridElement.querySelector(".product-spu-card:not(.product-spu-card--loading)") as HTMLElement | null;
  const cardHeight = firstCard?.getBoundingClientRect().height || PRODUCT_CARD_ESTIMATED_HEIGHT;
  return calculateProductPageSize({
    gridWidth: gridRect.width,
    viewportHeight: window.innerHeight,
    gridTop: gridRect.top,
    cardHeight
  });
}

function productPageRangeText(page: number, pageSize: number, total: number) {
  if (!total) return "共 0 个商品";
  const safePage = Math.max(1, page);
  const safePageSize = Math.max(1, pageSize);
  const start = Math.min(total, (safePage - 1) * safePageSize + 1);
  const end = Math.min(total, safePage * safePageSize);
  return `第 ${start}-${end} 件 / 共 ${total} 件`;
}

function categoryProductType(category: ProductCategory) {
  const rawType = String(category.product_type || "").trim().toLowerCase();
  if (rawType === "box") return "gift_box";
  if (rawType === "bubble_bag") return "bag";
  if (rawType === "material") return "accessory";
  if (rawType === "carton") return "shipping";
  if (rawType) return rawType;
  const name = category.name || "";
  if (name.includes("泡袋")) return "bag";
  if (name.includes("纸箱")) return "shipping";
  if (name.includes("标签") || name.includes("辅料") || name.includes("内衬")) return "accessory";
  if (name.includes("礼盒") || name.includes("小盒") || name.includes("盒")) return "gift_box";
  return "other";
}

function productTypeQueryValue(type: string) {
  if (type === "bag") return "bag,bubble_bag";
  if (type === "gift_box") return "gift_box";
  if (type === "shipping") return "shipping";
  if (type === "accessory") return "accessory";
  if (type === "other") return "other,service,virtual";
  return type;
}

function productTypeLabel(type: string) {
  return PRODUCT_TYPE_META[type]?.label || type || "其他";
}

function productTypeOrder(type: string) {
  return PRODUCT_TYPE_META[type]?.order ?? 80;
}

function productTypeTabs(categories: ProductCategory[], total: number): ProductTypeTab[] {
  const groups = new Map<string, ProductTypeTab>();
  categories
    .filter((category) => category.id)
    .forEach((category) => {
      const key = categoryProductType(category);
      const current = groups.get(key) || {
        key,
        label: productTypeLabel(key),
        total: 0,
        order: productTypeOrder(key)
      };
      current.total += Number(category.total || 0);
      groups.set(key, current);
    });
  return [
    { key: "", label: "全部", total, order: 0 },
    ...Array.from(groups.values()).sort((a, b) => a.order - b.order || a.label.localeCompare(b.label, "zh-Hans-CN"))
  ];
}

function visibleProductCategories(categories: ProductCategory[], productType: string) {
  return categories
    .filter((category) => category.id)
    .filter((category) => !productType || categoryProductType(category) === productType);
}

function groupedEditorCategories(categories: ProductCategory[]) {
  const groups = new Map<string, { key: string; label: string; order: number; items: ProductCategory[] }>();
  categories
    .filter((category) => category.id)
    .forEach((category) => {
      const key = categoryProductType(category);
      const current = groups.get(key) || {
        key,
        label: productTypeLabel(key),
        order: productTypeOrder(key),
        items: []
      };
      current.items.push(category);
      groups.set(key, current);
    });
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      items: group.items.sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), "zh-Hans-CN"))
    }))
    .sort((a, b) => a.order - b.order || a.label.localeCompare(b.label, "zh-Hans-CN"));
}

function productImageUrl(product: ProductItem) {
  return product.images || product.main_images || product.spu_main_image_url || product.spec_image_url || product.image || "";
}

function productActionId(product: ProductItem) {
  return Number(product.id || product.product_id || product.spu_id || 0);
}

function productSkuIds(product: ProductItem) {
  const rows = Array.isArray(product.product_group_data) && product.product_group_data.length
    ? product.product_group_data
    : [product];
  return rows
    .map((row) => Number(row.id || row.product_id || 0))
    .filter((id) => id > 0);
}

function productColorsText(product: ProductItem) {
  const names = product.color_names || product.available_colors || [];
  if (product.color_text) return product.color_text;
  if (names.length) return names.join(" / ");
  return "默认颜色";
}

function productColorCount(product: ProductItem) {
  const count = Number(product.color_count || 0);
  if (count > 0) return count;
  const names = product.color_names || product.available_colors || [];
  return Math.max(1, names.length || Number(product.product_group_data?.length || 0));
}

function productPieceText(product: ProductItem) {
  if (product.piece_text) return product.piece_text.startsWith("1件") ? product.piece_text : `1件${product.piece_text}套`;
  if (product.case_pack_qty) return `1件${product.case_pack_qty}套`;
  return "未设置";
}

function productPriceText(product: ProductItem) {
  const min = product.min_price || product.price || 0;
  const max = product.max_price || product.price || min;
  if (String(min) && String(max) && Number(min) > 0 && Number(max) > 0 && Number(min) !== Number(max)) {
    return `${money(min)} - ${money(max)}`;
  }
  return money(product.price || product.min_price || 0);
}

function productStockText(product: ProductItem) {
  return Number(product.is_stock_item ?? 1) ? `库存 ${product.inventory || "0"}` : "不扣库存";
}

function productEditorForcedNonStock(productType: string, categories: ProductCategory[], categoryIds: number[]) {
  const type = String(productType || "").trim().toLowerCase();
  if (["bag", "bubble_bag", "service", "virtual"].includes(type)) return true;
  const fixedWords = ["泡袋", "茶袋", "标签", "服务", "设计", "制版", "辅料"];
  return categories
    .filter((category) => categoryIds.includes(Number(category.id || 0)))
    .some((category) => fixedWords.some((word) => String(category.name || "").includes(word)));
}

function productColorNames(product: ProductItem) {
  const text = product.color_text || "";
  const names = product.color_names || product.available_colors || [];
  if (names.length) return names.map(String).filter(Boolean);
  if (text) return text.split(/[\/、,，]/).map((item) => item.trim()).filter(Boolean);
  return ["默认颜色"];
}

function productColorsInline(colors: string[]) {
  const visible = colors.filter(Boolean).slice(0, 3);
  const extra = Math.max(0, colors.length - visible.length);
  return [visible.join(" / "), extra ? `+${extra}` : ""].filter(Boolean).join(" / ");
}

type ProductSpecForm = {
  local_key: string;
  id: string;
  base_id: string;
  image: string;
  spec: string;
  unit_id: string | number;
  coding: string;
  barcode: string;
  price: string | number;
  cost_price: string | number;
  is_stock_item: number;
};

type ImagePickerTarget = {
  type: "main" | "detail" | "spec";
  specIndex?: number;
};

type ImageCropTarget = {
  url: string;
  target: ImagePickerTarget;
};

type SquareCropResult = {
  file?: File;
  sourceUrl: string;
  sourceX: number;
  sourceY: number;
  sourceSize: number;
  outputSize: number;
};

type CropOffset = {
  x: number;
  y: number;
};

const SQUARE_CROP_OUTPUT_SIZE = 1200;
const SQUARE_CROP_STAGE_SIZE = 360;
const SQUARE_CROP_MAX_ZOOM = 3;

function clampValue(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function squareCropFileName(sourceUrl: string) {
  const rawName = sourceUrl.split("?")[0].split("/").filter(Boolean).pop() || "product-image";
  const name = rawName.replace(/\.[a-z0-9]+$/i, "").replace(/[^a-zA-Z0-9_-]+/g, "_") || "product-image";
  return `${name}_1x1_${Date.now()}.jpg`;
}

function localProductKey() {
  return `${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function htmlToImageUrls(value?: string) {
  const html = String(value || "");
  const urls: string[] = [];
  const pattern = /<img[^>]+src=["']([^"']+)["']/gi;
  let match = pattern.exec(html);
  while (match) {
    if (match[1]) urls.push(match[1]);
    match = pattern.exec(html);
  }
  return urls;
}

function detailImagesFromProduct(product: ProductItem | null) {
  if (!product) return [];
  const raw = product.detail_image_urls;
  if (Array.isArray(raw)) return raw.filter(Boolean);
  if (typeof raw === "string" && raw.trim()) {
    try {
      const parsed = JSON.parse(raw) as unknown;
      if (Array.isArray(parsed)) return parsed.map(String).filter(Boolean);
    } catch {
      if (/^https?:\/\//i.test(raw)) return [raw];
    }
  }
  return htmlToImageUrls(product.content || product.content_html);
}

function detailImagesToHtml(images: string[]) {
  return images.filter(Boolean).map((url) => `<img src="${String(url).replace(/"/g, "&quot;")}">`).join("");
}

function casePackQtyFromProduct(product: ProductItem | null) {
  if (!product) return "";
  if (product.case_pack_qty) return String(product.case_pack_qty);
  const match = String(product.simple_desc || "").match(/([0-9.]+)/);
  return match ? match[1] : "";
}

function productCategoryIds(product: ProductItem | null) {
  if (!product) return [];
  if (Array.isArray(product.product_category_ids)) return product.product_category_ids.map(Number).filter(Boolean);
  const primary = Number(product.primary_category_id || 0);
  return primary ? [primary] : [];
}

function productUnitOptions(units: ProductUnit[]) {
  return units.length ? units : [{ id: 1, name: "套" }];
}

function productStatusOptions(statuses: ProductStatusOption[]) {
  return statuses.length ? statuses : [
    { value: 0, name: "启用" },
    { value: 1, name: "停用" }
  ];
}

const EDITOR_PRODUCT_TYPE_OPTIONS = [
  { value: "gift_box", label: "礼盒" },
  { value: "bag", label: "泡袋" },
  { value: "bubble_bag", label: "泡袋" },
  { value: "accessory", label: "辅料" },
  { value: "shipping", label: "纸箱" },
  { value: "other", label: "其他" }
];

function editorProductTypeOptions(currentType: string) {
  if (!currentType || EDITOR_PRODUCT_TYPE_OPTIONS.some((item) => item.value === currentType)) {
    return EDITOR_PRODUCT_TYPE_OPTIONS;
  }
  return EDITOR_PRODUCT_TYPE_OPTIONS.concat({ value: currentType, label: productTypeLabel(currentType) });
}

function productStatusName(statuses: ProductStatusOption[], value: string | number) {
  return productStatusOptions(statuses).find((item) => String(item.value) === String(value))?.name || "启用";
}

function categorySummary(categories: ProductCategory[], categoryIds: number[]) {
  const names = categories
    .filter((category) => categoryIds.includes(Number(category.id || 0)))
    .map((category) => category.name)
    .filter(Boolean);
  return names.length ? names.join(" / ") : "未选择分类";
}

function productDataFromOptions(options: unknown) {
  const data = options as ProductOptionsRecord;
  if (!data || typeof data !== "object") return {};
  const nested = data.data && typeof data.data === "object" ? data.data : null;
  if (nested && nested.data && typeof nested.data === "object") {
    return {
      ...nested.data,
      product_group_data: nested.product_group_data || nested.data.product_group_data || [],
      media_assets: nested.data.media_assets || nested.media_assets || data.media_assets || []
    } as ProductItem;
  }
  if (nested) {
    return {
      ...nested,
      media_assets: nested.media_assets || data.media_assets || []
    } as ProductItem;
  }
  return {};
}

type ProductOptionsRecord = {
  data?: (ProductItem & { data?: ProductItem }) | null;
  media_assets?: ProductMediaAsset[];
};

function productSpecRows(product: ProductItem | null, units: ProductUnit[]) {
  const defaultUnit = productUnitOptions(units)[0]?.id || 1;
  const rows = product?.product_group_data?.length ? product.product_group_data : product ? [product] : [];
  const list = rows.map((row) => {
    const base = Array.isArray(row.base) && row.base.length ? row.base[0] : {};
    const image = row.spec_image_url || row.image || base.images || "";
    return {
      local_key: localProductKey(),
      id: String(row.id || row.product_id || ""),
      base_id: String(base.id || ""),
      image,
      spec: row.spec || row.color || "默认颜色",
      unit_id: base.unit_id || row.unit_id || defaultUnit,
      coding: row.sku_no || row.coding || base.coding || "",
      barcode: base.barcode || "",
      price: base.price || row.price || row.min_price || "",
      cost_price: base.cost_price || "",
      is_stock_item: Number(row.is_stock_item ?? base.is_stock_item ?? 1)
    };
  });
  return list.length ? list : [{
    local_key: localProductKey(),
    id: "",
    base_id: "",
    image: "",
    spec: "默认颜色",
    unit_id: defaultUnit,
    coding: "",
    barcode: "",
    price: "",
    cost_price: "",
    is_stock_item: 1
  }];
}

function createProductDraft(
  categories: ProductCategory[],
  productType: string,
  categoryId: string | number
): ProductItem {
  const cleanCategoryId = Number(categoryId || 0);
  const selectedCategory = categories.find((category) => Number(category.id || 0) === cleanCategoryId);
  const draftType = productType || (selectedCategory ? categoryProductType(selectedCategory) : "gift_box");
  return {
    title: "",
    name: "",
    product_type: draftType,
    product_category_ids: cleanCategoryId ? [cleanCategoryId] : [],
    is_stock_item: 1,
    is_listed: 0,
    system_goods_is_shelves: 0,
    product_group_data: [
      {
        spec: "默认颜色",
        color: "默认颜色",
        is_stock_item: 1,
        unit_id: 1
      }
    ]
  } as ProductItem;
}

function uploadedImageUrl(result: { url?: string; full_url?: string; images?: string; path?: string } | string) {
  if (typeof result === "string") return result;
  return result.url || result.full_url || result.images || result.path || "";
}

function imageAssetKeyword(asset: ProductMediaAsset) {
  return [
    asset.product_name,
    asset.binding_text,
    asset.asset_group_text,
    asset.category_name,
    asset.sku_color,
    asset.sku_no,
    asset.media_type_text,
    asset.source_text,
    asset.url
  ].join(" ").toLowerCase();
}

function assetTitle(asset: ProductMediaAsset) {
  return asset.product_name || asset.binding_text || (asset.media_type === "pending" ? "待绑定" : "图片资产");
}

function uniqueAssets(list: ProductMediaAsset[]) {
  const seen = new Set<string>();
  return list.filter((asset) => {
    const key = asset.url || "";
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function currentEditorAssets(
  title: string,
  mainImages: string[],
  detailImages: string[],
  specs: ProductSpecForm[],
  mediaAssets: ProductMediaAsset[]
) {
  const current: ProductMediaAsset[] = [];
  mainImages.forEach((url) => current.push({
    media_type: "main_image",
    media_type_text: "主图",
    url,
    product_name: title,
    binding_text: `${title} / 主图`,
    asset_group_text: "本产品图片",
    source_text: "当前主图"
  }));
  detailImages.forEach((url) => current.push({
    media_type: "detail_image",
    media_type_text: "详情页",
    url,
    product_name: title,
    binding_text: `${title} / 详情图`,
    asset_group_text: "本产品图片",
    source_text: "当前详情页"
  }));
  specs.forEach((spec) => {
    if (!spec.image) return;
    current.push({
      media_type: "color_image",
      media_type_text: "颜色图",
      url: spec.image,
      product_name: title,
      binding_text: `${title} / ${spec.spec || "默认颜色"}`,
      asset_group_text: "本产品图片",
      sku_color: spec.spec || "默认颜色",
      source_text: "当前颜色图"
    });
  });
  return uniqueAssets(current.concat(mediaAssets.filter((asset) => String(asset.media_type || "") !== "pending")));
}

function ImageTile({ url, label, onRemove }: { url: string; label?: string; onRemove: () => void }) {
  return (
    <div className="edit-image-tile">
      <img src={url} alt={label || "商品图片"} loading="lazy" />
      <Button variant="secondary" size="icon-xs" aria-label="移除图片" onClick={onRemove}>
        <X data-icon="inline-start" />
      </Button>
      {label ? <span>{label}</span> : null}
    </div>
  );
}

function ImageAssetPickerDialog({
  open,
  productId,
  currentAssets,
  onClose,
  onSelect
}: {
  open: boolean;
  productId: number;
  currentAssets: ProductMediaAsset[];
  onClose: () => void;
  onSelect: (url: string) => void;
}) {
  const [tab, setTab] = useState<"pending" | "product_assets" | "all">("pending");
  const [keyword, setKeyword] = useState("");
  const [assets, setAssets] = useState<ProductMediaAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadAssets(nextTab = tab) {
    setLoading(true);
    setError("");
    try {
      const data = await api.productMedia({
        page: 1,
        pageSize: 80,
        mediaType: nextTab === "pending" ? "pending" : "",
        productId: nextTab === "product_assets" && productId ? productId : undefined
      });
      setAssets(data.list || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "图片资产加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    setTab(productId || currentAssets.length ? "product_assets" : "pending");
    setKeyword("");
  }, [open, productId, currentAssets.length]);

  useEffect(() => {
    if (!open) return;
    void loadAssets(tab);
  }, [open, tab, productId]);

  function pick(url: string) {
    if (!url) return;
    onSelect(url);
    onClose();
  }

  function upload() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
    input.addEventListener("change", async () => {
      const file = input.files?.[0];
      input.remove();
      if (!file) return;
      setLoading(true);
      setError("");
      try {
        const result = await api.uploadProductImage(file);
        const url = uploadedImageUrl(result);
        if (!url) throw new Error("上传成功但没有返回图片地址");
        pick(url);
      } catch (err) {
        setError(err instanceof Error ? err.message : "图片上传失败");
      } finally {
        setLoading(false);
      }
    }, { once: true });
    document.body.appendChild(input);
    input.click();
  }

  const source = tab === "product_assets" ? uniqueAssets(currentAssets.concat(assets)) : assets;
  const filtered = keyword.trim()
    ? source.filter((asset) => imageAssetKeyword(asset).includes(keyword.trim().toLowerCase()))
    : source;

  return (
      <Dialog open={open} onOpenChange={(nextOpen) => {
        if (!nextOpen) onClose();
      }}>
        <DialogContent className="asset-picker-dialog">
          <DialogHeader>
            <DialogTitle>选择图片资产</DialogTitle>
            <DialogDescription className="sj-sr-only">从本产品和未绑定图片中选择主图、详情图或规格图。</DialogDescription>
          </DialogHeader>

        <div className="asset-picker-tools">
          <Tabs value={tab} onValueChange={(value) => setTab(value as "pending" | "product_assets" | "all")}>
            <TabsList>
              <TabsTrigger value="pending">未绑定</TabsTrigger>
              <TabsTrigger value="product_assets">本产品图片</TabsTrigger>
              <TabsTrigger value="all">全部图片</TabsTrigger>
            </TabsList>
          </Tabs>
          <div className="asset-picker-search">
            <Input value={keyword} placeholder="搜索产品、分类、颜色、来源" onChange={(event) => setKeyword(event.target.value)} />
            <Button type="button" onClick={upload} disabled={loading}>
              <Upload data-icon="inline-start" />
              上传新图片
            </Button>
          </div>
        </div>

        {error ? <div className="form-error">{error}</div> : null}
        {loading ? (
          <div className="asset-picker-grid">
            {Array.from({ length: 8 }).map((_, index) => (
              <Card className="asset-picker-card asset-picker-card--loading" size="sm" key={index}>
                <Skeleton className="asset-picker-card-image" />
                <Skeleton />
                <Skeleton />
              </Card>
            ))}
          </div>
        ) : null}

        {!loading && filtered.length ? (
          <ScrollArea className="asset-picker-scroll">
            <div className="asset-picker-grid">
              {filtered.slice(0, 80).map((asset, index) => (
                <Button
                  className="asset-picker-card"
                  variant="outline"
                  key={`${asset.url}-${index}`}
                  onClick={() => pick(asset.url)}
                >
                  <img src={asset.url} alt={assetTitle(asset)} loading="lazy" />
                  <strong>{assetTitle(asset)}</strong>
                  <span>{asset.asset_group_text || asset.category_name || "其他分类"}</span>
                  <em>{[asset.media_type_text, asset.sku_color, asset.source_text].filter(Boolean).join(" · ") || asset.media_type}</em>
                </Button>
              ))}
            </div>
          </ScrollArea>
        ) : null}

        {!loading && !filtered.length ? (
          <Empty className="products-empty">
            <EmptyHeader>
              <EmptyTitle>暂无可选图片</EmptyTitle>
              <EmptyDescription>可以切换分组，或者上传新图片后直接选择。</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function SquareImageCropDialog({
  cropTarget,
  saving,
  error,
  onCancel,
  onConfirm
}: {
  cropTarget: ImageCropTarget | null;
  saving: boolean;
  error: string;
  onCancel: () => void;
  onConfirm: (crop: SquareCropResult) => void;
}) {
  const stageRef = useRef<HTMLDivElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const dragRef = useRef<{ x: number; y: number; offset: CropOffset } | null>(null);
  const imageSizeRef = useRef({ width: 0, height: 0 });
  const zoomRef = useRef(1);
  const offsetRef = useRef<CropOffset>({ x: 0, y: 0 });
  const stageSizeRef = useRef(SQUARE_CROP_STAGE_SIZE);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState<CropOffset>({ x: 0, y: 0 });
  const [stageSize, setStageSize] = useState(SQUARE_CROP_STAGE_SIZE);
  const [localError, setLocalError] = useState("");

  const imageUrl = cropTarget?.url || "";
  const baseScale = imageSize.width && imageSize.height
    ? Math.max(stageSize / imageSize.width, stageSize / imageSize.height)
    : 1;
  const cropScale = baseScale * zoom;
  const displayWidth = imageSize.width * cropScale;
  const displayHeight = imageSize.height * cropScale;

  function setCropZoom(nextZoom: number) {
    zoomRef.current = nextZoom;
    setZoom(nextZoom);
  }

  function setCropOffset(nextOffset: CropOffset) {
    offsetRef.current = nextOffset;
    setOffset(nextOffset);
  }

  function setCropImageSize(nextSize: { width: number; height: number }) {
    imageSizeRef.current = nextSize;
    setImageSize(nextSize);
  }

  function setCropStageSize(nextSize: number) {
    stageSizeRef.current = nextSize;
    setStageSize(nextSize);
  }

  function clampOffset(
    nextOffset: CropOffset,
    nextZoom = zoomRef.current,
    nextSize = imageSizeRef.current,
    nextStageSize = stageSizeRef.current
  ) {
    if (!nextSize.width || !nextSize.height) return { x: 0, y: 0 };
    const nextBaseScale = Math.max(nextStageSize / nextSize.width, nextStageSize / nextSize.height);
    const nextScale = nextBaseScale * nextZoom;
    const maxX = Math.max(0, (nextSize.width * nextScale - nextStageSize) / 2);
    const maxY = Math.max(0, (nextSize.height * nextScale - nextStageSize) / 2);
    return {
      x: clampValue(nextOffset.x, -maxX, maxX),
      y: clampValue(nextOffset.y, -maxY, maxY)
    };
  }

  useEffect(() => {
    setCropZoom(1);
    setCropOffset({ x: 0, y: 0 });
    setCropImageSize({ width: 0, height: 0 });
    setLocalError("");
  }, [imageUrl]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || !cropTarget) return;
    const updateStageSize = () => {
      const rect = stage.getBoundingClientRect();
      const nextSize = Math.max(1, Math.round(Math.min(rect.width || SQUARE_CROP_STAGE_SIZE, rect.height || SQUARE_CROP_STAGE_SIZE)));
      setCropStageSize(nextSize);
    };
    updateStageSize();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(updateStageSize);
    observer.observe(stage);
    return () => observer.disconnect();
  }, [cropTarget]);

  useEffect(() => {
    setCropOffset(clampOffset(offsetRef.current));
  }, [zoom, imageSize.width, imageSize.height, stageSize]);

  function startDrag(event: PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    if (!imageSize.width || saving) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { x: event.clientX, y: event.clientY, offset: offsetRef.current };
  }

  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    if (!dragRef.current || saving) return;
    event.preventDefault();
    const nextOffset = {
      x: dragRef.current.offset.x + event.clientX - dragRef.current.x,
      y: dragRef.current.offset.y + event.clientY - dragRef.current.y
    };
    setCropOffset(clampOffset(nextOffset, zoomRef.current));
  }

  function stopDrag(event: PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function zoomCropWithWheel(event: WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    if (!imageSizeRef.current.width || saving || event.deltaY === 0) return;
    const currentZoom = zoomRef.current;
    const nextZoom = clampValue(currentZoom * Math.exp(-event.deltaY * 0.0015), 1, SQUARE_CROP_MAX_ZOOM);
    if (Math.abs(nextZoom - currentZoom) < 0.001) return;

    const rect = stageRef.current?.getBoundingClientRect();
    const point = rect
      ? { x: event.clientX - rect.left - rect.width / 2, y: event.clientY - rect.top - rect.height / 2 }
      : { x: 0, y: 0 };
    const size = imageSizeRef.current;
    const side = stageSizeRef.current;
    const nextBaseScale = Math.max(side / size.width, side / size.height);
    const currentScale = nextBaseScale * currentZoom;
    const nextScale = nextBaseScale * nextZoom;
    const currentOffset = offsetRef.current;
    const sourceFromCenter = {
      x: (point.x - currentOffset.x) / currentScale,
      y: (point.y - currentOffset.y) / currentScale
    };
    const nextOffset = clampOffset({
      x: point.x - sourceFromCenter.x * nextScale,
      y: point.y - sourceFromCenter.y * nextScale
    }, nextZoom, size, side);

    setCropZoom(nextZoom);
    setCropOffset(nextOffset);
  }

  function currentCropResult(): SquareCropResult | null {
    if (!imageUrl || !imageSize.width || !imageSize.height) {
      return null;
    }
    const imageLeft = stageSize / 2 + offset.x - displayWidth / 2;
    const imageTop = stageSize / 2 + offset.y - displayHeight / 2;
    const rawSourceSize = stageSize / cropScale;
    const sourceX = clampValue(-imageLeft / cropScale, 0, Math.max(0, imageSize.width - rawSourceSize));
    const sourceY = clampValue(-imageTop / cropScale, 0, Math.max(0, imageSize.height - rawSourceSize));
    const sourceSize = Math.min(rawSourceSize, imageSize.width - sourceX, imageSize.height - sourceY);
    return {
      sourceUrl: imageUrl,
      sourceX,
      sourceY,
      sourceSize,
      outputSize: SQUARE_CROP_OUTPUT_SIZE
    };
  }

  async function createCropFile() {
    const image = imageRef.current;
    const crop = currentCropResult();
    if (!image || !crop) {
      setLocalError("图片还没有加载完成");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = SQUARE_CROP_OUTPUT_SIZE;
    canvas.height = SQUARE_CROP_OUTPUT_SIZE;
    const context = canvas.getContext("2d");
    if (!context) {
      setLocalError("浏览器无法创建裁剪画布");
      return;
    }
    try {
      context.fillStyle = "#ffffff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(
        image,
        crop.sourceX,
        crop.sourceY,
        crop.sourceSize,
        crop.sourceSize,
        0,
        0,
        crop.outputSize,
        crop.outputSize
      );
      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((nextBlob) => {
          if (nextBlob) resolve(nextBlob);
          else reject(new Error("图片裁剪失败"));
        }, "image/jpeg", 0.92);
      });
      onConfirm({ ...crop, file: new File([blob], squareCropFileName(imageUrl), { type: "image/jpeg" }) });
    } catch {
      onConfirm(crop);
    }
  }

  return (
    <Dialog open={Boolean(cropTarget)} onOpenChange={(nextOpen) => {
      if (!nextOpen && !saving) onCancel();
    }}>
      <DialogContent className="square-crop-dialog">
        <DialogHeader>
          <DialogTitle>调整为 1:1 图片</DialogTitle>
          <DialogDescription>
            主图和颜色规格图会保存为新的正方形图片，原图仍保留在图片资产里。
          </DialogDescription>
        </DialogHeader>
        {(error || localError) ? <div className="form-error">{error || localError}</div> : null}
        <div
          ref={stageRef}
          className="square-crop-stage"
          data-disabled={saving || !imageSize.width ? "true" : undefined}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={stopDrag}
          onPointerCancel={stopDrag}
          onWheel={zoomCropWithWheel}
        >
          {imageUrl ? (
            <div
              className="square-crop-image-layer"
              style={{
                width: displayWidth || stageSize,
                height: displayHeight || stageSize,
                transform: `translate(${offset.x}px, ${offset.y}px)`
              }}
            >
              <img
                ref={imageRef}
                src={imageUrl}
                alt="待裁剪图片"
                draggable={false}
                onLoad={(event) => {
                  const image = event.currentTarget;
                  setCropImageSize({ width: image.naturalWidth, height: image.naturalHeight });
                }}
                onError={() => setLocalError("图片加载失败")}
              />
            </div>
          ) : null}
          <div className="square-crop-frame" aria-hidden="true" />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" disabled={saving} onClick={() => {
            setCropZoom(1);
            setCropOffset({ x: 0, y: 0 });
          }}>
            重置
          </Button>
          <Button type="button" variant="outline" disabled={saving} onClick={onCancel}>取消</Button>
          <Button type="button" disabled={saving || !imageSize.width} onClick={createCropFile}>
            {saving ? "生成中" : "确认使用 1:1 图"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ProductEditorDialog({
  product,
  availableCategories,
  onClose,
  onSaved
}: {
  product: ProductItem | null;
  availableCategories: ProductCategory[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const open = Boolean(product);
  const [title, setTitle] = useState("");
  const [productType, setProductType] = useState("gift_box");
  const [categoryIds, setCategoryIds] = useState<number[]>([]);
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [units, setUnits] = useState<ProductUnit[]>([]);
  const [statuses, setStatuses] = useState<ProductStatusOption[]>([]);
  const [status, setStatus] = useState<string | number>(0);
  const [casePackQty, setCasePackQty] = useState("");
  const [oneCase, setOneCase] = useState(false);
  const [stockItem, setStockItem] = useState(true);
  const [mainImages, setMainImages] = useState<string[]>([]);
  const [detailImages, setDetailImages] = useState<string[]>([]);
  const [specs, setSpecs] = useState<ProductSpecForm[]>([]);
  const [mediaAssets, setMediaAssets] = useState<ProductMediaAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [pickerTarget, setPickerTarget] = useState<ImagePickerTarget | null>(null);
  const [pendingSquareCrop, setPendingSquareCrop] = useState<ImageCropTarget | null>(null);
  const [cropSaving, setCropSaving] = useState(false);
  const [cropError, setCropError] = useState("");
  const productId = Number(product?.id || product?.product_id || 0);
  const isCreate = open && !productId;
  const forcedNonStock = productEditorForcedNonStock(productType, categories, categoryIds);
  const effectiveStockItem = forcedNonStock ? false : stockItem;

  function applyProduct(productData: ProductItem, nextUnits = units) {
    setTitle(productData.title || productData.name || "");
    setProductType(productData.product_type || "gift_box");
    setCategoryIds(productCategoryIds(productData));
    setStatus(productData.status_text === "停用" ? 1 : 0);
    setCasePackQty(casePackQtyFromProduct(productData));
    setOneCase((productData.purchase_policy || (Number(productData.is_one_case_purchase || 0) ? "one_case" : "order_qty")) === "one_case");
    setStockItem(Number(productData.is_stock_item ?? 1) !== 0);
    setMainImages(productData.main_images_list?.length ? productData.main_images_list : productImageUrl(productData) ? [productImageUrl(productData)] : []);
    setDetailImages(detailImagesFromProduct(productData));
    setSpecs(productSpecRows(productData, nextUnits));
    setMediaAssets(Array.isArray(productData.media_assets) ? productData.media_assets : []);
  }

  useEffect(() => {
    if (!product) return;
    setError("");
    setCropError("");
    setPendingSquareCrop(null);
    if (availableCategories.length) setCategories(availableCategories);
    applyProduct(product);
    const id = Number(product.id || product.product_id || 0);
    setLoading(true);
    Promise.all([
      id ? api.productDetail(id).catch(() => null) : Promise.resolve(null),
      api.productOptions(id || undefined)
    ])
      .then(([detail, options]) => {
        const optionProduct = productDataFromOptions(options);
        const nextCategories = options.product_category?.length ? options.product_category : availableCategories;
        const nextUnits = productUnitOptions(options.unit_list || []);
        setCategories(nextCategories);
        setUnits(nextUnits);
        setStatuses(productStatusOptions(options.product_status_list || []));
        const merged = { ...product, ...(detail || {}), ...optionProduct };
        applyProduct(merged, nextUnits);
        setMediaAssets(Array.isArray(merged.media_assets) ? merged.media_assets : options.media_assets || []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "商品详情加载失败"))
      .finally(() => setLoading(false));
  }, [product, availableCategories]);

  useEffect(() => {
    if (forcedNonStock && stockItem) setStockItem(false);
  }, [forcedNonStock, stockItem]);

  function toggleCategory(id: number) {
    setCategoryIds((prev) => prev.includes(id) ? prev.filter((item) => item !== id) : prev.concat(id));
  }

  function updateSpec(index: number, patch: Partial<ProductSpecForm>) {
    setSpecs((prev) => prev.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  }

  function addSpec() {
    const nextSpec = productSpecRows(null, units)[0];
    setSpecs((prev) => prev.concat({ ...nextSpec, is_stock_item: effectiveStockItem ? 1 : 0 }));
  }

  function removeSpec(index: number) {
    setSpecs((prev) => prev.length <= 1 ? prev : prev.filter((_, itemIndex) => itemIndex !== index));
  }

  function applySelectedImage(target: ImagePickerTarget, url: string) {
    if (target.type === "main") {
      setMainImages(url ? [url] : []);
    } else if (target.type === "detail") {
      setDetailImages((prev) => prev.concat(url));
    } else {
      updateSpec(target.specIndex || 0, { image: url });
    }
  }

  function selectImage(url: string) {
    if (!pickerTarget) return;
    if (pickerTarget.type !== "detail") {
      setCropError("");
      setPendingSquareCrop({ url, target: pickerTarget });
      return;
    }
    applySelectedImage(pickerTarget, url);
  }

  async function confirmSquareCrop(crop: SquareCropResult) {
    if (!pendingSquareCrop) return;
    setCropSaving(true);
    setCropError("");
    try {
      const result = crop.file ? await api.uploadProductImage(crop.file) : await api.cropProductImageSquare(crop);
      const url = uploadedImageUrl(result);
      if (!url) throw new Error("裁剪图上传成功但没有返回图片地址");
      applySelectedImage(pendingSquareCrop.target, url);
      setPendingSquareCrop(null);
    } catch (err) {
      setCropError(
        err instanceof ApiError && err.status === 404
          ? "后台裁切接口还没生效，请重启后台服务后再试"
          : err instanceof Error
            ? err.message
            : "1:1 图片生成失败"
      );
    } finally {
      setCropSaving(false);
    }
  }

  function buildPayload(): ProductSavePayload {
    const base: ProductSavePayload["base"] = {};
    const stockValue = effectiveStockItem ? 1 : 0;
    specs.forEach((spec, index) => {
      const productKey = spec.id ? String(spec.id) : `new_${index}`;
      const unitKey = spec.base_id ? String(spec.base_id) : "new_0";
      base[productKey] = {
        images: spec.image || mainImages[0] || "",
        spec: spec.spec || "默认颜色",
        coding: spec.coding || "",
        is_stock_item: stockValue,
        unit: {
          [unitKey]: {
            unit_id: spec.unit_id || 1,
            unit_number: 1,
            coding: spec.coding || "",
            barcode: spec.barcode || "",
            weight: 0,
            volume: 0,
            price: spec.price || 0,
            cost_price: spec.cost_price || 0,
            extends: ""
          }
        }
      };
    });
    return {
      id: isCreate ? undefined : productId || undefined,
      title: title.trim(),
      product_type: productType,
      product_category_id: categoryIds,
      status,
      purchase_policy: oneCase ? "one_case" : "order_qty",
      simple_desc: casePackQty ? `规格${casePackQty}套/件` : "",
      content: detailImagesToHtml(detailImages),
      main_images: mainImages,
      base
    };
  }

  async function save() {
    if (!title.trim()) {
      setError("请输入商品名称");
      return;
    }
    if (!categoryIds.length) {
      setError("请选择分类");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await api.saveProduct(buildPayload());
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "商品保存失败");
    } finally {
      setSaving(false);
    }
  }

  const currentAssets = currentEditorAssets(title || "当前产品", mainImages, detailImages, specs, mediaAssets);

  return (
    <>
      <Dialog open={open} onOpenChange={(nextOpen) => {
        if (!nextOpen && !saving) onClose();
      }}>
        <DialogContent className="product-editor-dialog">
          <DialogHeader>
            <div className="product-editor-header">
              <div>
                <DialogTitle>{isCreate ? "新增商品" : "编辑商品"}</DialogTitle>
                <DialogDescription className="sj-sr-only">维护商品基础资料、分类、规格颜色、图片和上架起订规则。</DialogDescription>
                <div className="product-editor-subtitle">
                  <Badge variant="secondary">{productStatusName(statuses, status)}</Badge>
                  <span>{title || "未命名商品"}</span>
                </div>
              </div>
            </div>
          </DialogHeader>

          {error ? <div className="form-error">{error}</div> : null}
          <Tabs defaultValue="basic" className="product-editor-tabs">
            <TabsList>
              <TabsTrigger value="basic">基础信息</TabsTrigger>
              <TabsTrigger value="specs">规格/颜色</TabsTrigger>
              <TabsTrigger value="images">图片</TabsTrigger>
              <TabsTrigger value="rules">上架/起订</TabsTrigger>
              <TabsTrigger value="records">记录</TabsTrigger>
            </TabsList>
            <ScrollArea className="product-editor-scroll">
              <TabsContent value="basic" className="product-editor-tab-panel">
                <Card size="sm">
                  <CardHeader>
                    <CardTitle>商品资料</CardTitle>
                    <CardDescription>{categorySummary(categories, categoryIds)}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <FieldGroup className="product-editor-fields">
                      <Field className="product-editor-field--wide">
                        <FieldLabel htmlFor="product-title">商品名称</FieldLabel>
                        <Input id="product-title" value={title} onChange={(event) => setTitle(event.target.value)} />
                      </Field>
                      <Field>
                        <FieldLabel>商品类型</FieldLabel>
                        <Select value={productType} onValueChange={setProductType}>
                          <SelectTrigger>
                            <SelectValue placeholder="选择商品类型" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              {editorProductTypeOptions(productType).map((item) => (
                                <SelectItem value={item.value} key={item.value}>{item.label}</SelectItem>
                              ))}
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                      </Field>
                      <Field>
                        <FieldLabel>状态</FieldLabel>
                        <Select value={String(status)} onValueChange={setStatus}>
                          <SelectTrigger>
                            <SelectValue placeholder="选择状态" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              {productStatusOptions(statuses).map((item) => (
                                <SelectItem value={String(item.value)} key={String(item.value)}>{item.name}</SelectItem>
                              ))}
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                      </Field>
                      <Field>
                        <FieldLabel htmlFor="product-case-pack">件规</FieldLabel>
                        <Input
                          id="product-case-pack"
                          type="number"
                          min="0"
                          step="1"
                          value={casePackQty}
                          onWheel={inputNoWheel}
                          placeholder="例如 20"
                          onChange={(event) => setCasePackQty(event.target.value)}
                        />
                      </Field>
                      <Field>
                        <FieldLabel>库存规则</FieldLabel>
                        <FieldContent>
                          <div className={cn("product-editor-switch-row", forcedNonStock && "is-disabled")}>
                            <Switch checked={effectiveStockItem} disabled={forcedNonStock} onCheckedChange={setStockItem} />
                            <span>{forcedNonStock ? "固定不扣库存" : effectiveStockItem ? "扣库存" : "不扣库存"}</span>
                          </div>
                        </FieldContent>
                      </Field>
                    </FieldGroup>
                  </CardContent>
                </Card>

                <Card size="sm">
                  <CardHeader>
                    <CardTitle>分类</CardTitle>
                    <CardAction>
                      <Badge variant={categoryIds.length ? "secondary" : "outline"}>
                        {categoryIds.length ? `${categoryIds.length} 个分类` : "未选择"}
                      </Badge>
                    </CardAction>
                  </CardHeader>
                  <CardContent>
                    <div className="product-editor-category-groups">
                      {groupedEditorCategories(categories).map((group) => (
                        <div className="product-editor-category-group" key={group.key}>
                          <div className="product-editor-category-heading">
                            <span>{group.label}</span>
                            <Badge variant="outline">{group.items.length}</Badge>
                          </div>
                          <div className="product-editor-category-grid">
                            {group.items.map((category) => {
                              const id = Number(category.id || 0);
                              const active = categoryIds.includes(id);
                              return (
                                <Button
                                  variant={active ? "default" : "outline"}
                                  size="xs"
                                  key={category.id || category.name}
                                  onClick={() => toggleCategory(id)}
                                >
                                  {category.name}
                                </Button>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="specs" className="product-editor-tab-panel">
                <Card size="sm">
                  <CardHeader>
                    <CardTitle>规格 / 颜色</CardTitle>
                    <CardDescription>{specs.length} 个颜色规格</CardDescription>
                    <CardAction>
                      <Button type="button" variant="outline" size="sm" onClick={addSpec}>
                        <Plus data-icon="inline-start" />
                        添加规格
                      </Button>
                    </CardAction>
                  </CardHeader>
                  <CardContent>
                    <Table className="product-spec-table">
                      <TableHeader>
                        <TableRow>
                          <TableHead>图片</TableHead>
                          <TableHead>颜色/规格</TableHead>
                          <TableHead>商品编码</TableHead>
                          <TableHead>条码</TableHead>
                          <TableHead>单位</TableHead>
                          <TableHead>售价</TableHead>
                          <TableHead>成本价</TableHead>
                          <TableHead>操作</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {specs.map((spec, index) => (
                          <TableRow key={spec.local_key}>
                            <TableCell>
                              <div className="spec-table-image">
                                {spec.image ? <ImageTile url={spec.image} onRemove={() => updateSpec(index, { image: "" })} /> : null}
                                <Button variant="outline" className="edit-upload-tile edit-upload-tile--small" onClick={() => setPickerTarget({ type: "spec", specIndex: index })}>
                                  <ImagePlus data-icon="inline-start" />
                                  {spec.image ? "换图" : "选图"}
                                </Button>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Input value={spec.spec} onChange={(event) => updateSpec(index, { spec: event.target.value })} />
                            </TableCell>
                            <TableCell>
                              <Input value={spec.coding} onChange={(event) => updateSpec(index, { coding: event.target.value })} />
                            </TableCell>
                            <TableCell>
                              <Input value={spec.barcode} onChange={(event) => updateSpec(index, { barcode: event.target.value })} />
                            </TableCell>
                            <TableCell>
                              <Select value={String(spec.unit_id || 1)} onValueChange={(value) => updateSpec(index, { unit_id: value })}>
                                <SelectTrigger>
                                  <SelectValue placeholder="单位" />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectGroup>
                                    {productUnitOptions(units).map((unit) => (
                                      <SelectItem value={String(unit.id || 1)} key={String(unit.id || unit.name)}>{unit.name}</SelectItem>
                                    ))}
                                  </SelectGroup>
                                </SelectContent>
                              </Select>
                            </TableCell>
                            <TableCell>
                              <Input type="number" min="0" step="0.01" value={spec.price} onWheel={inputNoWheel} onChange={(event) => updateSpec(index, { price: event.target.value })} />
                            </TableCell>
                            <TableCell>
                              <Input type="number" min="0" step="0.01" value={spec.cost_price} onWheel={inputNoWheel} onChange={(event) => updateSpec(index, { cost_price: event.target.value })} />
                            </TableCell>
                            <TableCell>
                              <Button
                                variant="ghost"
                                size="icon-sm"
                                disabled={specs.length <= 1}
                                aria-label="删除规格"
                                onClick={() => removeSpec(index)}
                              >
                                <Trash2 data-icon="inline-start" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="images" className="product-editor-tab-panel">
                <Card size="sm">
                  <CardHeader>
                    <CardTitle>主图</CardTitle>
                    <CardAction><Badge variant="outline">{mainImages.length} 张</Badge></CardAction>
                  </CardHeader>
                  <CardContent>
                    <div className="edit-image-row">
                      {mainImages.map((url) => (
                        <ImageTile key={url} url={url} onRemove={() => setMainImages([])} />
                      ))}
                      <Button variant="outline" className="edit-upload-tile" onClick={() => setPickerTarget({ type: "main" })}>
                        <ImagePlus data-icon="inline-start" />
                        <strong>上传/选择</strong>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
                <Card size="sm">
                  <CardHeader>
                    <CardTitle>详情页</CardTitle>
                    <CardAction><Badge variant="outline">{detailImages.length} 张</Badge></CardAction>
                  </CardHeader>
                  <CardContent>
                    <div className="edit-image-row detail-images">
                      {detailImages.map((url, index) => (
                        <ImageTile key={`${url}-${index}`} url={url} onRemove={() => setDetailImages((prev) => prev.filter((_, itemIndex) => itemIndex !== index))} />
                      ))}
                      <Button variant="outline" className="edit-upload-tile" onClick={() => setPickerTarget({ type: "detail" })}>
                        <ImagePlus data-icon="inline-start" />
                        <strong>上传/选择</strong>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="rules" className="product-editor-tab-panel">
                <Card size="sm">
                  <CardHeader>
                    <CardTitle>上架 / 起订</CardTitle>
                    <CardDescription>{oneCase ? "1件起订" : "按数量开单"}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <FieldGroup className="product-editor-fields">
                      <Field>
                        <FieldLabel>商品状态</FieldLabel>
                        <Select value={String(status)} onValueChange={setStatus}>
                          <SelectTrigger>
                            <SelectValue placeholder="选择状态" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectGroup>
                              {productStatusOptions(statuses).map((item) => (
                                <SelectItem value={String(item.value)} key={String(item.value)}>{item.name}</SelectItem>
                              ))}
                            </SelectGroup>
                          </SelectContent>
                        </Select>
                      </Field>
                      <Field>
                        <FieldLabel>1件起订</FieldLabel>
                        <FieldContent>
                          <div className="product-editor-switch-row">
                            <Switch checked={oneCase} onCheckedChange={setOneCase} />
                            <span>{oneCase ? "开启" : "关闭"}</span>
                          </div>
                        </FieldContent>
                      </Field>
                    </FieldGroup>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="records" className="product-editor-tab-panel">
                <Empty>
                  <EmptyHeader>
                    <EmptyTitle>暂无操作记录</EmptyTitle>
                    <EmptyDescription>后续接入商品日志后在这里查看修改记录。</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              </TabsContent>
            </ScrollArea>
          </Tabs>

          <DialogFooter>
            <Button type="button" variant="outline" disabled={saving} onClick={onClose}>取消</Button>
            <Button type="button" disabled={saving} onClick={save}>{saving ? "保存中" : "保存商品"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <ImageAssetPickerDialog
        open={Boolean(pickerTarget)}
        productId={productId}
        currentAssets={currentAssets}
        onClose={() => setPickerTarget(null)}
        onSelect={selectImage}
      />
      <SquareImageCropDialog
        cropTarget={pendingSquareCrop}
        saving={cropSaving}
        error={cropError}
        onCancel={() => {
          if (!cropSaving) setPendingSquareCrop(null);
        }}
        onConfirm={confirmSquareCrop}
      />
    </>
  );
}

function ProductToolbar({
  keyword,
  page,
  pageCount,
  pageSize,
  total,
  loading,
  onKeywordChange,
  onSearch,
  onReset,
  onCreate
}: {
  keyword: string;
  page: number;
  pageCount: number;
  pageSize: number;
  total: number;
  loading: boolean;
  onKeywordChange: (value: string) => void;
  onSearch: () => void;
  onReset: () => void;
  onCreate: () => void;
}) {
  return (
    <div className="products-toolbar">
      <div className="products-title-block">
        <Badge variant="outline">{productPageRangeText(page, pageSize, total)} · 第 {page}/{pageCount} 页 · 每页 {pageSize}</Badge>
        <div className="products-toolbar-copy">
          <strong>商品资料工作台</strong>
          <CardDescription>按 SPU 管商品，快速查看颜色、件规、价格和库存规则。</CardDescription>
        </div>
      </div>
      <form className="products-search-form" onSubmit={(event) => {
        event.preventDefault();
        onSearch();
      }}>
        <Input value={keyword} placeholder="搜索商品、颜色、编号" onChange={(event) => onKeywordChange(event.target.value)} />
        <Button type="submit" variant="outline" disabled={loading}>
          <Search data-icon="inline-start" />
          搜索
        </Button>
        <Button type="button" variant="ghost" disabled={loading} onClick={onReset}>
          <RefreshCw data-icon="inline-start" />
          重置
        </Button>
        <Button type="button" disabled={loading} onClick={onCreate}>
          <Plus data-icon="inline-start" />
          新增商品
        </Button>
      </form>
    </div>
  );
}

function ProductQuickFilters({
  listedState,
  stockMode,
  quality,
  onListedStateChange,
  onStockModeChange,
  onQualityChange
}: {
  listedState: string;
  stockMode: string;
  quality: string;
  onListedStateChange: (value: string) => void;
  onStockModeChange: (value: string) => void;
  onQualityChange: (value: string) => void;
}) {
  const groups = [
    { label: "上架", value: listedState, options: LISTED_FILTERS, onChange: onListedStateChange },
    { label: "库存", value: stockMode, options: STOCK_FILTERS, onChange: onStockModeChange },
    { label: "资料", value: quality, options: QUALITY_FILTERS, onChange: onQualityChange }
  ];
  return (
    <div className="products-quick-filters">
      {groups.map((group) => (
        <div className="products-filter-group" key={group.label}>
          <span className="products-filter-label">{group.label}</span>
          {group.options.map((option) => (
            <Button
              type="button"
              size="sm"
              variant={group.value === option.value ? "default" : "outline"}
              key={option.value || `${group.label}-all`}
              onClick={() => group.onChange(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>
      ))}
    </div>
  );
}

function ProductCategoryTabs({
  categories,
  productType,
  total,
  onTypeSelect
}: {
  categories: ProductCategory[];
  productType: string;
  total: number;
  onTypeSelect: (type: string) => void;
}) {
  const tabs = productTypeTabs(categories, total);
  return (
    <Tabs value={productType} onValueChange={onTypeSelect} className="products-type-tabs">
      <TabsList>
        {tabs.map((tab) => (
          <TabsTrigger value={tab.key} key={tab.key || "all"}>
            {tab.label}
            <span>{tab.total}</span>
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}

function ProductCategoryFilter({
  categories,
  productType,
  categoryId,
  onSelect
}: {
  categories: ProductCategory[];
  productType: string;
  categoryId: string | number;
  onSelect: (id: string | number) => void;
}) {
  const visible = visibleProductCategories(categories, productType);
  const allLabel = productType ? `全部${productTypeLabel(productType)}` : "全部分类";
  return (
    <div className="products-category-filter">
      <Button
        size="sm"
        variant={String(categoryId || "") === "" ? "default" : "outline"}
        onClick={() => onSelect("")}
      >
        {allLabel}
      </Button>
      {visible.map((category) => {
        const id = category.id ?? "";
        return (
          <Button
            key={String(id || "all")}
            size="sm"
            variant={String(categoryId || "") === String(id || "") ? "default" : "outline"}
            onClick={() => onSelect(id || "")}
          >
            {category.name}{category.total !== undefined ? ` ${category.total}` : ""}
          </Button>
        );
      })}
    </div>
  );
}

type ProductCardProps = {
  product: ProductItem;
  actionBusy: boolean;
  onEdit: (product: ProductItem) => void;
  onToggleShelves: (product: ProductItem, state: number) => void;
  onDelete: (product: ProductItem) => void;
};

function ProductCard({ product, actionBusy, onEdit, onToggleShelves, onDelete }: ProductCardProps) {
  const image = productImageUrl(product);
  const colors = productColorNames(product);
  const isListed = Number(product.system_goods_is_shelves ?? product.is_listed ?? 0) === 1;
  const nextShelfState = isListed ? 0 : 1;
  const productName = product.title || product.name || "商品";
  const colorText = productColorsInline(colors);
  const [confirmAction, setConfirmAction] = useState<"shelf" | "delete" | null>(null);
  return (
    <>
      <Card size="sm" className="product-spu-card">
        <div className="product-spu-thumb">
          {image ? <img src={image} alt={productName} loading="lazy" /> : <span>无图</span>}
        </div>
        <CardHeader>
          <div className="product-spu-title-copy">
            <CardTitle>{productName}</CardTitle>
            <CardDescription>{product.product_category_text || "未分类"}</CardDescription>
          </div>
          <CardAction className="product-spu-status-slot">
            <Badge
              variant="outline"
              className={cn(
                "product-spu-status",
                isListed ? "product-spu-status--listed" : "product-spu-status--unlisted"
              )}
            >
              {isListed ? "已上架" : "未上架"}
            </Badge>
          </CardAction>
        </CardHeader>
        <CardContent>
          <div className="product-spu-summary-row">
            <strong className="product-spu-price">{productPriceText(product)}</strong>
            <span className="product-spu-stock">{productStockText(product)}</span>
          </div>
          <div className="product-spu-detail-row" aria-label={`件规：${productPieceText(product)}`}>
            <span className="product-spu-meta-label">件规</span>
            <span className="product-spu-meta-value">{productPieceText(product)}</span>
            {Number(product.is_one_case_purchase || 0) ? <span className="product-spu-mini-note">1件起订</span> : null}
          </div>
          <div className="product-spu-color-text" aria-label={`颜色：${productColorsText(product)}`}>
            <span className="product-spu-meta-label">颜色</span>
            <span className="product-spu-meta-value">{colorText}</span>
          </div>
        </CardContent>
        <CardFooter className="product-spu-actions">
          <div className="product-spu-actions--primary">
            <Button type="button" variant="outline" size="sm" onClick={() => onEdit(product)} disabled={actionBusy}>
              <Pencil data-icon="inline-start" />
              编辑
            </Button>
            <Button type="button" variant="outline" size="sm" disabled={actionBusy} onClick={() => setConfirmAction("shelf")}>
              {isListed ? "下架" : "上架"}
            </Button>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="ghost" size="icon-sm" disabled={actionBusy} aria-label="更多操作">
                <MoreHorizontal data-icon="only" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuGroup>
                <DropdownMenuItem className="product-menu-danger" onSelect={(event) => {
                  event.preventDefault();
                  setConfirmAction("delete");
                }}>
                  删除商品
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardFooter>
      </Card>
      <AlertDialog open={confirmAction === "shelf"} onOpenChange={(open) => {
        if (!open) setConfirmAction(null);
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{isListed ? "确认下架商品？" : "确认上架商品？"}</AlertDialogTitle>
            <AlertDialogDescription>
              {productName} 会按整个商品同步处理，包含这个商品下面的所有颜色规格。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => {
              setConfirmAction(null);
              onToggleShelves(product, nextShelfState);
            }}>
              {isListed ? "确认下架" : "确认上架"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AlertDialog open={confirmAction === "delete"} onOpenChange={(open) => {
        if (!open) setConfirmAction(null);
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除商品？</AlertDialogTitle>
            <AlertDialogDescription>
              {productName} 会软删除整个商品和全部颜色规格，历史销售单不会被删除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => {
              setConfirmAction(null);
              onDelete(product);
            }}>
              确认删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function ProductListSkeleton() {
  return (
    <div className="products-grid">
      {Array.from({ length: 8 }).map((_, index) => (
        <Card size="sm" className="product-spu-card product-spu-card--loading" key={index}>
          <Skeleton className="product-spu-thumb" />
          <CardHeader>
            <div className="product-skeleton-title">
              <Skeleton />
              <Skeleton />
            </div>
            <CardAction><Skeleton /></CardAction>
          </CardHeader>
          <CardContent>
            <div className="product-spu-skeleton-lines">
              <Skeleton />
              <Skeleton />
              <Skeleton />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ProductEmptyState({ onReset }: { onReset: () => void }) {
  return (
    <Empty className="products-empty">
      <EmptyHeader>
        <EmptyTitle>没有商品</EmptyTitle>
        <EmptyDescription>换个关键词或分类再查。</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button variant="outline" onClick={onReset}>
          <RefreshCw data-icon="inline-start" />
          重置筛选
        </Button>
      </EmptyContent>
    </Empty>
  );
}

function ProductNotice({ message, tone = "neutral" }: { message: string; tone?: "neutral" | "error" | "success" }) {
  if (!message) return null;
  return (
    <div className={cn("products-notice", `products-notice--${tone}`)}>
      {message}
    </div>
  );
}

function ProductSummaryStrip({ total, items, loading }: { total: number; items: ProductItem[]; loading: boolean }) {
  const listedCount = items.filter((item) => Number(item.is_listed || 0)).length;
  const nonStockCount = items.filter((item) => Number(item.is_stock_item ?? 1) === 0).length;
  const colorCount = items.reduce((sum, item) => sum + productColorCount(item), 0);
  return (
    <div className="products-summary-strip">
      <div><span>商品</span><strong>{loading ? "-" : total}</strong></div>
      <div><span>本页上架</span><strong>{loading ? "-" : listedCount}</strong></div>
      <div><span>本页颜色</span><strong>{loading ? "-" : colorCount}</strong></div>
      <div><span>不扣库存</span><strong>{loading ? "-" : nonStockCount}</strong></div>
    </div>
  );
}

function ProductCardGrid({
  items,
  loading,
  actionProductId,
  gridRef,
  onEdit,
  onReset,
  onToggleShelves,
  onDelete
}: {
  items: ProductItem[];
  loading: boolean;
  actionProductId: number;
  gridRef?: (node: HTMLDivElement | null) => void;
  onEdit: (product: ProductItem) => void;
  onReset: () => void;
  onToggleShelves: (product: ProductItem, state: number) => void;
  onDelete: (product: ProductItem) => void;
}) {
  if (loading) return <ProductListSkeleton />;
  if (!items.length) return <ProductEmptyState onReset={onReset} />;
  return (
    <div className="products-grid" ref={gridRef}>
      {items.map((product) => (
        <ProductCard
          key={product.spu_id || product.id || product.product_id}
          product={product}
          actionBusy={actionProductId === productActionId(product)}
          onEdit={onEdit}
          onToggleShelves={onToggleShelves}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}

function ProductPager({
  page,
  pageCount,
  pageSize,
  total,
  loading,
  onPrevious,
  onNext
}: {
  page: number;
  pageCount: number;
  pageSize: number;
  total: number;
  loading: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <Pagination className="products-pagination">
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious disabled={page <= 1 || loading} onClick={onPrevious} />
        </PaginationItem>
        <PaginationItem>
          <Badge variant="outline">{productPageRangeText(page, pageSize, total)}</Badge>
        </PaginationItem>
        <PaginationItem>
          <PaginationNext disabled={page >= pageCount || loading} onClick={onNext} />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
}

export function ProductsPage() {
  const [keyword, setKeyword] = useState("");
  const [productType, setProductType] = useState("");
  const [categoryId, setCategoryId] = useState<string | number>("");
  const [listedState, setListedState] = useState("");
  const [stockMode, setStockMode] = useState("");
  const [quality, setQuality] = useState("");
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [items, setItems] = useState<ProductItem[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editingProduct, setEditingProduct] = useState<ProductItem | null>(null);
  const [actionProductId, setActionProductId] = useState(0);
  const [pageSize, setPageSize] = useState(initialProductPageSize);
  const [gridElement, setGridElement] = useState<HTMLDivElement | null>(null);
  const gridRef = useCallback((node: HTMLDivElement | null) => {
    setGridElement(node);
  }, []);

  async function loadProducts(
    nextPage = page,
    nextKeyword = keyword,
    nextCategory = categoryId,
    nextProductType = productType,
    nextListedState = listedState,
    nextStockMode = stockMode,
    nextQuality = quality,
    nextPageSize = pageSize
  ) {
    setLoading(true);
    setError("");
    try {
      const data = await api.productList({
        keyword: nextKeyword,
        page: nextPage,
        pageSize: nextPageSize,
        categoryId: nextCategory,
        productType: productTypeQueryValue(nextProductType),
        listedState: nextListedState,
        stockMode: nextStockMode,
        quality: nextQuality
      });
      setItems(data.list || []);
      setTotal(data.total || 0);
      setPage(nextPage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "商品加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function afterProductSaved() {
    setNotice("商品已保存");
    await loadProducts(page, keyword, categoryId, productType, listedState, stockMode, quality);
  }

  function resetFilters() {
    setKeyword("");
    setCategoryId("");
    setProductType("");
    setListedState("");
    setStockMode("");
    setQuality("");
    void loadProducts(1, "", "", "", "", "", "");
  }

  async function toggleProductShelves(product: ProductItem, state: number) {
    const id = productActionId(product);
    if (!id) return;
    setActionProductId(id);
    setError("");
    setNotice("");
    try {
      await api.updateProductShelves(id, state, {
        spuId: Number(product.spu_id || 0) || undefined,
        skuIds: productSkuIds(product)
      });
      setNotice(`${product.title || product.name || "商品"} 已${state ? "上架" : "下架"}`);
      await loadProducts(page, keyword, categoryId, productType, listedState, stockMode, quality);
    } catch (err) {
      setError(err instanceof Error ? err.message : "商品上下架失败");
    } finally {
      setActionProductId(0);
    }
  }

  async function deleteProduct(product: ProductItem) {
    const id = productActionId(product);
    if (!id) return;
    setActionProductId(id);
    setError("");
    setNotice("");
    try {
      await api.deleteProduct([id]);
      setNotice(`${product.title || product.name || "商品"} 已删除`);
      const nextPage = items.length <= 1 && page > 1 ? page - 1 : page;
      await loadProducts(nextPage, keyword, categoryId, productType, listedState, stockMode, quality);
    } catch (err) {
      setError(err instanceof Error ? err.message : "商品删除失败");
    } finally {
      setActionProductId(0);
    }
  }

  useEffect(() => {
    api.productCategories()
      .then((data) => setCategories(data.list || []))
      .catch(() => undefined);
    void loadProducts(1, "", "", "");
  }, []);

  useEffect(() => {
    if (!gridElement) return undefined;

    let resizeTimer = 0;
    const syncPageSize = () => {
      const nextPageSize = measuredProductPageSize(gridElement);
      setPageSize((currentPageSize) => {
        if (currentPageSize === nextPageSize) return currentPageSize;
        const firstItemIndex = Math.max(1, (page - 1) * currentPageSize + 1);
        const nextPage = Math.max(1, Math.ceil(firstItemIndex / nextPageSize));
        void loadProducts(nextPage, keyword, categoryId, productType, listedState, stockMode, quality, nextPageSize);
        return nextPageSize;
      });
    };
    const scheduleSync = () => {
      window.clearTimeout(resizeTimer);
      resizeTimer = window.setTimeout(syncPageSize, PRODUCT_PAGE_SIZE_RESIZE_DELAY);
    };

    scheduleSync();
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(scheduleSync);
    observer?.observe(gridElement);
    window.addEventListener("resize", scheduleSync);
    return () => {
      window.clearTimeout(resizeTimer);
      observer?.disconnect();
      window.removeEventListener("resize", scheduleSync);
    };
  }, [gridElement, items.length, page, keyword, categoryId, productType, listedState, stockMode, quality]);

  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const allProductsTotal = Number(categories.find((category) => !category.id)?.total || total);

  return (
    <section className="products-page">
      <ProductToolbar
        keyword={keyword}
        page={page}
        pageCount={pageCount}
        pageSize={pageSize}
        total={total}
        loading={loading}
        onKeywordChange={setKeyword}
        onSearch={() => void loadProducts(1, keyword, categoryId, productType, listedState, stockMode, quality)}
        onReset={resetFilters}
        onCreate={() => {
          setNotice("");
          setEditingProduct(createProductDraft(categories, productType, categoryId));
        }}
      />
      <ProductCategoryTabs
        categories={categories}
        productType={productType}
        total={allProductsTotal}
        onTypeSelect={(type) => {
          setProductType(type);
          setCategoryId("");
          void loadProducts(1, keyword, "", type, listedState, stockMode, quality);
        }}
      />
      <ProductCategoryFilter
        categories={categories}
        productType={productType}
        categoryId={categoryId}
        onSelect={(id) => {
          setCategoryId(id);
          void loadProducts(1, keyword, id, productType, listedState, stockMode, quality);
        }}
      />
      <ProductQuickFilters
        listedState={listedState}
        stockMode={stockMode}
        quality={quality}
        onListedStateChange={(value) => {
          setListedState(value);
          void loadProducts(1, keyword, categoryId, productType, value, stockMode, quality);
        }}
        onStockModeChange={(value) => {
          setStockMode(value);
          void loadProducts(1, keyword, categoryId, productType, listedState, value, quality);
        }}
        onQualityChange={(value) => {
          setQuality(value);
          void loadProducts(1, keyword, categoryId, productType, listedState, stockMode, value);
        }}
      />
      <ProductSummaryStrip total={total} items={items} loading={loading} />
      <ProductNotice message={error} tone="error" />
      <ProductNotice message={notice} tone="success" />
      <ProductCardGrid
        items={items}
        loading={loading}
        actionProductId={actionProductId}
        gridRef={gridRef}
        onReset={resetFilters}
        onEdit={(product) => {
          setNotice("");
          setEditingProduct(product);
        }}
        onToggleShelves={(product, state) => void toggleProductShelves(product, state)}
        onDelete={(product) => void deleteProduct(product)}
      />
      <ProductPager
        page={page}
        pageCount={pageCount}
        pageSize={pageSize}
        total={total}
        loading={loading}
        onPrevious={() => void loadProducts(page - 1, keyword, categoryId, productType, listedState, stockMode, quality)}
        onNext={() => void loadProducts(page + 1, keyword, categoryId, productType, listedState, stockMode, quality)}
      />
      <ProductEditorDialog
        product={editingProduct}
        availableCategories={categories}
        onClose={() => setEditingProduct(null)}
        onSaved={afterProductSaved}
      />
    </section>
  );
}
