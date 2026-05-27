import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  Boxes,
  Hash,
  Image,
  Images,
  Layers,
  Navigation,
  Package,
  Plus,
  Printer,
  RefreshCw,
  Save,
  Search,
  Settings as SettingsIcon,
  Smartphone,
  Trash2,
  Upload,
  Users,
  WalletCards,
  X
} from "lucide-react";

import { api } from "@/api";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
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
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious
} from "@/components/ui/pagination";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type {
  MediaSummary,
  MiniappAssetImageItem,
  MiniappImageConfig,
  MiniappImageUpdatePayload,
  NumberSequenceSettings,
  PrintSettings,
  ProductCategory,
  ProductCategorySavePayload,
  ProductMediaAsset,
  ProductUploadResult,
  SystemSetting,
  UserListItem,
  Warehouse
} from "@/types";

type SettingsSectionKey =
  | "number"
  | "product"
  | "inventory"
  | "payment"
  | "media"
  | "miniapp"
  | "users"
  | "print";

type SettingKey = "product_basic" | "inventory_rules" | "payment_rules" | "image_rules";
type MiniappImageField = MiniappImageUpdatePayload["field"];
type MiniappImageTarget = MiniappImageUpdatePayload["target_type"];
type MiniappAssetScene = "home_banner" | "bottom_tab";

type PanelCallbacks = {
  markDirty: () => void;
  onSaved: (message: string) => void;
  onError: (message: string) => void;
  registerSave: (section: SettingsSectionKey, handler: () => Promise<boolean>) => void;
};

type ImageFieldConfig<T> = {
  field: MiniappImageField;
  label: string;
  desc: string;
  value: (item: T) => string;
};

const sectionItems: Array<{
  key: SettingsSectionKey;
  label: string;
  desc: string;
  icon: typeof SettingsIcon;
}> = [
  { key: "number", label: "编号", desc: "SKU 编号规则", icon: Hash },
  { key: "product", label: "商品基础", desc: "分类、单位、件规", icon: Package },
  { key: "inventory", label: "库存规则", desc: "扣库存和仓库", icon: Boxes },
  { key: "payment", label: "收款结款", desc: "付款状态和余额", icon: WalletCards },
  { key: "media", label: "图片资产", desc: "商品图资产库", icon: Images },
  { key: "miniapp", label: "小程序设置", desc: "轮播、分类、导航", icon: Smartphone },
  { key: "users", label: "用户权限", desc: "账号角色和启用", icon: Users },
  { key: "print", label: "打印", desc: "销售单打印模板", icon: Printer }
];

const sectionKeySet = new Set(sectionItems.map((item) => item.key));

const roleOptions = [
  { value: "admin", label: "管理员" },
  { value: "staff", label: "员工" },
  { value: "customer", label: "客户" },
  { value: "guest", label: "访客" }
];

const mediaTypeTabs = [
  { key: "all", value: "", label: "全部" },
  { key: "pending", value: "pending", label: "未绑定" },
  { key: "main_image", value: "main_image", label: "主图" },
  { key: "detail_image", value: "detail_image", label: "详情图" },
  { key: "color_image", value: "color_image", label: "颜色规格图" }
];

const visibleMiniappScenes: MiniappAssetScene[] = ["home_banner", "bottom_tab"];

const bannerFields: Array<ImageFieldConfig<MiniappAssetImageItem>> = [
  { field: "asset_url", label: "轮播图片", desc: "首页顶部轮播使用", value: (asset) => asset.asset_url || "" }
];

const bottomTabFields: Array<ImageFieldConfig<MiniappAssetImageItem>> = [
  { field: "asset_url", label: "未选中图标", desc: "底部导航默认状态", value: (asset) => asset.asset_url || "" },
  { field: "active_asset_url", label: "选中图标", desc: "底部导航当前页状态", value: (asset) => asset.active_asset_url || "" }
];

const categoryImageFields: Array<ImageFieldConfig<ProductCategory>> = [
  { field: "icon", label: "未选中图标", desc: "首页分类入口和分类页默认状态共用", value: (category) => category.icon || "" },
  { field: "icon_active", label: "选中图标", desc: "分类页选中状态使用", value: (category) => category.icon_active || "" }
];

const inventoryPolicyOptions = [
  { value: "strict", label: "扣库存", desc: "销售和调拨都会走库存流水" },
  { value: "none", label: "不扣库存", desc: "服务、辅料、纸箱等不进库存页" },
  { value: "weak", label: "弱库存", desc: "保留库存记录，允许业务灵活处理" }
];

const productTypeOptions = [
  { value: "gift_box", label: "礼盒" },
  { value: "bag", label: "泡袋" },
  { value: "accessory", label: "辅料" },
  { value: "service", label: "服务" },
  { value: "other", label: "其他" }
];

function sectionFromLocation(): SettingsSectionKey {
  const params = new URLSearchParams(window.location.search);
  const querySection = params.get("section");
  if (querySection && sectionKeySet.has(querySection as SettingsSectionKey)) {
    return querySection as SettingsSectionKey;
  }
  const segment = window.location.pathname.replace(/^\/admin\/?/, "").split("/")[0];
  if (segment === "media") return "media";
  if (segment === "miniapp-images") return "miniapp";
  return "number";
}

function sectionUrl(section: SettingsSectionKey) {
  if (section === "number") return "/admin/settings";
  return `/admin/settings?section=${section}`;
}

function uploadResultUrl(result: ProductUploadResult) {
  return result.url || result.full_url || result.images || result.path || "";
}

function thumbnailUrl(url = "") {
  const clean = String(url || "").trim();
  if (!clean || !clean.includes("img.513sjbz.com") || clean.includes("x-oss-process=")) return clean;
  const joiner = clean.includes("?") ? "&" : "?";
  return `${clean}${joiner}x-oss-process=image/resize,m_lfit,w_360,h_360/quality,q_85`;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item || "").trim()).filter(Boolean) : [];
}

function stringValue(value: unknown) {
  if (value === null || value === undefined) return "";
  return String(value);
}

function numberValue(value: unknown, fallback = 0) {
  const num = Number(value ?? fallback);
  return Number.isFinite(num) ? num : fallback;
}

function policyText(policy?: string) {
  if (policy === "none") return "不扣库存";
  if (policy === "weak") return "弱库存";
  return "扣库存";
}

function policyBadgeVariant(policy?: string) {
  if (policy === "none") return "secondary" as const;
  if (policy === "weak") return "outline" as const;
  return "default" as const;
}

function productTypeText(productType?: string) {
  return productTypeOptions.find((item) => item.value === productType)?.label || "其他";
}

function assetMeta(asset: MiniappAssetImageItem) {
  return [asset.link_type, asset.link_value].filter(Boolean).join(" / ") || "小程序图片";
}

function categoryMeta(category: ProductCategory) {
  return `${category.total || 0} 款商品`;
}

function SettingsPage() {
  const [activeSection, setActiveSection] = useState<SettingsSectionKey>(sectionFromLocation);
  const [pendingSection, setPendingSection] = useState<SettingsSectionKey | null>(null);
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [continuing, setContinuing] = useState(false);
  const saveHandlersRef = useRef<Partial<Record<SettingsSectionKey, () => Promise<boolean>>>>({});

  useEffect(() => {
    const handlePopState = () => setActiveSection(sectionFromLocation());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function switchSection(section: SettingsSectionKey, replace = false) {
    setActiveSection(section);
    setDirty(false);
    setMessage("");
    setError("");
    const nextUrl = sectionUrl(section);
    const currentUrl = `${window.location.pathname}${window.location.search}`;
    if (nextUrl !== currentUrl) {
      const method = replace ? "replaceState" : "pushState";
      window.history[method]({}, "", nextUrl);
    }
  }

  function requestSection(section: SettingsSectionKey) {
    if (section === activeSection) return;
    if (dirty) {
      setPendingSection(section);
      return;
    }
    switchSection(section);
  }

  const callbacks: PanelCallbacks = {
    markDirty: () => setDirty(true),
    onSaved: (nextMessage) => {
      setDirty(false);
      setMessage(nextMessage);
      setError("");
    },
    onError: (nextError) => {
      setError(nextError);
      setMessage("");
    },
    registerSave: (section, handler) => {
      saveHandlersRef.current[section] = handler;
    }
  };

  async function savePendingAndContinue() {
    if (!pendingSection) return;
    const handler = saveHandlersRef.current[activeSection];
    if (!handler) {
      switchSection(pendingSection);
      setPendingSection(null);
      return;
    }
    setContinuing(true);
    try {
      const saved = await handler();
      if (saved) {
        switchSection(pendingSection);
        setPendingSection(null);
      }
    } finally {
      setContinuing(false);
    }
  }

  const activeMeta = sectionItems.find((item) => item.key === activeSection) || sectionItems[0];

  return (
    <SettingsShell activeSection={activeSection} onSectionChange={requestSection}>
      <SettingsSectionHeader
        title={activeMeta.label}
        desc={activeMeta.desc}
        dirty={dirty}
        action={(
          <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
            <RefreshCw data-icon="inline-start" />
            刷新
          </Button>
        )}
      />
      {message ? <div className="form-success">{message}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}
      {activeSection === "number" ? <NumberSettingsPanel {...callbacks} /> : null}
      {activeSection === "product" ? <ProductBasicPanel {...callbacks} /> : null}
      {activeSection === "inventory" ? <InventoryRulesPanel {...callbacks} /> : null}
      {activeSection === "payment" ? <PaymentRulesPanel {...callbacks} /> : null}
      {activeSection === "media" ? <MediaSettingsPanel {...callbacks} /> : null}
      {activeSection === "miniapp" ? <MiniappSettingsPanel {...callbacks} /> : null}
      {activeSection === "users" ? <UserPermissionsPanel {...callbacks} /> : null}
      {activeSection === "print" ? <PrintSettingsPanel {...callbacks} /> : null}

      <AlertDialog open={Boolean(pendingSection)} onOpenChange={(open) => {
        if (!open) setPendingSection(null);
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>当前设置还没有保存</AlertDialogTitle>
            <AlertDialogDescription>
              切换前可以先保存并继续，也可以放弃修改后进入新的设置面板。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingSection(null)}>取消</AlertDialogCancel>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (pendingSection) switchSection(pendingSection);
                setPendingSection(null);
              }}
            >
              放弃修改
            </Button>
            <Button type="button" disabled={continuing} onClick={() => void savePendingAndContinue()}>
              {continuing ? "保存中" : "保存并继续"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsShell>
  );
}

function SettingsShell({
  activeSection,
  onSectionChange,
  children
}: {
  activeSection: SettingsSectionKey;
  onSectionChange: (section: SettingsSectionKey) => void;
  children: ReactNode;
}) {
  return (
    <section className="settings-workspace">
      <SettingsNav activeSection={activeSection} onSectionChange={onSectionChange} />
      <div className="settings-workspace-main">
        {children}
      </div>
    </section>
  );
}

function SettingsNav({
  activeSection,
  onSectionChange
}: {
  activeSection: SettingsSectionKey;
  onSectionChange: (section: SettingsSectionKey) => void;
}) {
  return (
    <Card className="settings-nav-card">
      <CardHeader>
        <CardTitle>设置</CardTitle>
        <CardDescription>按业务域分组管理。</CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs value={activeSection} onValueChange={(value) => onSectionChange(value as SettingsSectionKey)} className="settings-section-tabs">
          <TabsList>
            {sectionItems.map((item) => {
              const Icon = item.icon;
              return (
                <TabsTrigger value={item.key} key={item.key}>
                  <Icon data-icon="inline-start" />
                  {item.label}
                </TabsTrigger>
              );
            })}
          </TabsList>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function SettingsSectionHeader({
  title,
  desc,
  dirty,
  action
}: {
  title: string;
  desc: string;
  dirty: boolean;
  action?: ReactNode;
}) {
  return (
    <Card className="settings-section-header">
      <CardHeader>
        <div>
          <Badge variant={dirty ? "default" : "outline"}>{dirty ? "有未保存修改" : "已同步"}</Badge>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{desc}</CardDescription>
        </div>
        {action ? <CardAction>{action}</CardAction> : null}
      </CardHeader>
    </Card>
  );
}

function SettingsSaveBar({
  text,
  saving,
  onSave,
  onReset
}: {
  text: string;
  saving?: boolean;
  onSave: () => void;
  onReset?: () => void;
}) {
  return (
    <div className="settings-savebar">
      <span>{text}</span>
      <div className="settings-savebar-actions">
        {onReset ? (
          <Button type="button" variant="outline" size="sm" disabled={saving} onClick={onReset}>
            重置
          </Button>
        ) : null}
        <Button type="button" size="sm" disabled={saving} onClick={onSave}>
          <Save data-icon="inline-start" />
          {saving ? "保存中" : "保存"}
        </Button>
      </div>
    </div>
  );
}

function SettingListEditor({
  label,
  values,
  placeholder,
  onChange
}: {
  label: string;
  values: string[];
  placeholder: string;
  onChange: (next: string[]) => void;
}) {
  const [draft, setDraft] = useState("");

  function addItem() {
    const text = draft.trim();
    if (!text || values.includes(text)) return;
    onChange([...values, text]);
    setDraft("");
  }

  return (
    <Field className="setting-list-editor">
      <FieldLabel>{label}</FieldLabel>
      <div className="chip-editor">
        {values.map((item) => (
          <Button
            key={item}
            type="button"
            variant="outline"
            size="sm"
            className="settings-chip-button"
            onClick={() => onChange(values.filter((value) => value !== item))}
          >
            {item}
            <X data-icon="inline-end" />
          </Button>
        ))}
      </div>
      <div className="inline-form">
        <Input
          value={draft}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              addItem();
            }
          }}
        />
        <Button type="button" variant="outline" onClick={addItem}>
          <Plus data-icon="inline-start" />
          添加
        </Button>
      </div>
    </Field>
  );
}

function SettingsLoading({ rows = 3 }: { rows?: number }) {
  return (
    <Card>
      <CardContent className="settings-loading">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} />
        ))}
      </CardContent>
    </Card>
  );
}

function SettingsEmpty({ title, desc }: { title: string; desc: string }) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle>{title}</EmptyTitle>
        <EmptyDescription>{desc}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent />
    </Empty>
  );
}

function NumberSettingsPanel({ markDirty, onSaved, onError, registerSave }: PanelCallbacks) {
  const [sku, setSku] = useState<NumberSequenceSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setSku(await api.skuNumberSettings());
    } catch (err) {
      onError(err instanceof Error ? err.message : "编号设置加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function patch(patchValue: Partial<NumberSequenceSettings>) {
    setSku((current) => current ? { ...current, ...patchValue } : current);
    markDirty();
  }

  async function saveSkuNumberSettings() {
    if (!sku) return false;
    setSaving(true);
    try {
      setSku(await api.saveSkuNumberSettings(sku));
      onSaved("编号设置已保存");
      return true;
    } catch (err) {
      onError(err instanceof Error ? err.message : "编号保存失败");
      return false;
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    registerSave("number", saveSkuNumberSettings);
  });

  if (loading) return <SettingsLoading rows={4} />;
  if (!sku) return <SettingsEmpty title="没有编号配置" desc="后端还没有返回 SKU 编号规则。" />;

  return (
    <>
      <div className="settings-metric-grid">
        <Card>
          <CardContent><span>下一个编号</span><strong>{sku.next_code}</strong></CardContent>
        </Card>
        <Card>
          <CardContent><span>配置起点</span><strong>{sku.configured_code}</strong></CardContent>
        </Card>
        <Card>
          <CardContent><span>已用 SJ 编号</span><strong>{sku.numeric_used_count}</strong></CardContent>
        </Card>
        <Card>
          <CardContent><span>商品数量</span><strong>{sku.total_sku_count}</strong></CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>SKU 自动编号</CardTitle>
          <CardDescription>只影响后续新增商品和批量导入，历史 SKU 不会被重写。</CardDescription>
        </CardHeader>
        <CardContent>
          <FieldGroup className="settings-form-grid">
            <Field>
              <FieldLabel>编号前缀</FieldLabel>
              <Input value={sku.prefix} onChange={(event) => patch({ prefix: event.target.value })} />
            </Field>
            <Field>
              <FieldLabel>手动调整下一号</FieldLabel>
              <Input value={sku.next_code} onChange={(event) => patch({ next_code: event.target.value })} />
            </Field>
            <Field>
              <FieldLabel>补零位数</FieldLabel>
              <Input
                type="number"
                value={sku.pad_width}
                onChange={(event) => patch({ pad_width: Number(event.target.value || 4) })}
              />
            </Field>
            <Field>
              <FieldLabel>备注</FieldLabel>
              <Input value={sku.note || ""} onChange={(event) => patch({ note: event.target.value })} />
            </Field>
          </FieldGroup>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>编号变更记录</CardTitle>
          <CardDescription>最近的人工调整会记录在这里。</CardDescription>
        </CardHeader>
        <CardContent>
          {(sku.change_logs || []).length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>变更</TableHead>
                  <TableHead>备注</TableHead>
                  <TableHead>时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(sku.change_logs || []).map((log) => (
                  <TableRow key={log.id}>
                    <TableCell>{`${log.old_code} -> ${log.new_code}`}</TableCell>
                    <TableCell>{log.note || "无备注"}</TableCell>
                    <TableCell>{log.created_at || "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <SettingsEmpty title="暂无变更记录" desc="有人工调整编号后这里会显示记录。" />
          )}
        </CardContent>
      </Card>
      <SettingsSaveBar
        text="保存后只影响后续自动编号，不会修改已存在的商品编码。"
        saving={saving}
        onSave={() => void saveSkuNumberSettings()}
      />
    </>
  );
}

function ProductBasicPanel({ markDirty, onSaved, onError, registerSave }: PanelCallbacks) {
  const [setting, setSetting] = useState<SystemSetting | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [categoryDraft, setCategoryDraft] = useState<ProductCategorySavePayload | null>(null);
  const [categorySaving, setCategorySaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setSetting(await api.systemSetting("product_basic"));
    } catch (err) {
      onError(err instanceof Error ? err.message : "商品基础设置加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function patchSetting(patch: Record<string, unknown>) {
    setSetting((current) => {
      const existing = current || { key: "product_basic", value: {} };
      return { ...existing, value: { ...(existing.value || {}), ...patch } };
    });
    markDirty();
  }

  async function saveSystemSetting() {
    if (!setting) return false;
    setSaving(true);
    try {
      setSetting(await api.saveSystemSetting("product_basic", { value: setting.value || {} }));
      onSaved("商品基础设置已保存");
      return true;
    } catch (err) {
      onError(err instanceof Error ? err.message : "商品基础设置保存失败");
      return false;
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    registerSave("product", saveSystemSetting);
  });

  function openCategoryDialog(category?: ProductCategory) {
    setCategoryDraft({
      id: category?.id,
      parent_id: category?.parent_id || category?.pid || 0,
      name: category?.name || "",
      product_type: category?.product_type || "other",
      inventory_policy: category?.inventory_policy || "strict",
      sort_order: Number(category?.sort_order || 0),
      is_enabled: Number(category?.is_enabled ?? 1)
    });
  }

  async function saveCategory() {
    if (!categoryDraft) return;
    const name = String(categoryDraft.name || "").trim();
    if (!name) {
      onError("分类名称不能为空");
      return;
    }
    setCategorySaving(true);
    try {
      const result = await api.saveProductCategory({ ...categoryDraft, name });
      await load();
      const synced = result.synced || {};
      const total = Number(synced.sku || 0) + Number(synced.spu || 0);
      onSaved(total > 0 ? `分类已保存，已同步 ${total} 条商品库存规则` : "分类已保存");
      setCategoryDraft(null);
    } catch (err) {
      onError(err instanceof Error ? err.message : "分类保存失败");
    } finally {
      setCategorySaving(false);
    }
  }

  if (loading) return <SettingsLoading rows={3} />;
  if (!setting) return <SettingsEmpty title="没有商品基础设置" desc="后端还没有返回商品基础配置。" />;

  const value = setting.value || {};
  const units = asStringArray(value.units);

  return (
    <>
      <div className="settings-two-column">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>分类管理</CardTitle>
              <CardDescription>新增分类后可以直接用于商品编辑，小程序分类图标也会读取这里。</CardDescription>
            </div>
            <CardAction>
              <Button type="button" size="sm" onClick={() => openCategoryDialog()}>
                <Plus data-icon="inline-start" />
                新增分类
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            {(setting.categories || []).length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>分类</TableHead>
                    <TableHead>类型</TableHead>
                    <TableHead>商品</TableHead>
                    <TableHead>库存规则</TableHead>
                    <TableHead>操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(setting.categories || []).map((category) => (
                    <TableRow key={category.id || category.name}>
                      <TableCell>{category.name}</TableCell>
                      <TableCell>{productTypeText(category.product_type)}</TableCell>
                      <TableCell>{category.total ?? 0}</TableCell>
                      <TableCell>
                        <Badge variant={policyBadgeVariant(category.inventory_policy)}>
                          {policyText(category.inventory_policy)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button type="button" variant="outline" size="sm" onClick={() => openCategoryDialog(category)}>
                          编辑分类
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <SettingsEmpty title="暂无分类" desc="商品分类还没有同步到 React 后台。" />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>基础选项</CardTitle>
            <CardDescription>这里维护开商品时常用的单位和默认件规。</CardDescription>
          </CardHeader>
          <CardContent className="settings-stack">
            <SettingListEditor
              label="单位"
              values={units}
              placeholder="例如：套"
              onChange={(values) => patchSetting({ units: values })}
            />
            <SettingListEditor
              label="泡袋版型"
              values={asStringArray(value.bag_types)}
              placeholder="例如：短泡袋"
              onChange={(values) => patchSetting({ bag_types: values })}
            />
            <FieldGroup className="settings-form-grid settings-form-grid--two">
              <Field>
                <FieldLabel>默认件规</FieldLabel>
                <Input
                  value={stringValue(value.default_case_pack_qty)}
                  placeholder="例如 20"
                  onChange={(event) => patchSetting({ default_case_pack_qty: event.target.value })}
                />
              </Field>
              <Field>
                <FieldLabel>默认单位</FieldLabel>
                <Select
                  value={stringValue(value.default_unit) || units[0] || "套"}
                  onValueChange={(next) => patchSetting({ default_unit: next })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="选择单位" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {(units.length ? units : ["套"]).map((unit) => (
                        <SelectItem value={unit} key={unit}>{unit}</SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
            </FieldGroup>
          </CardContent>
        </Card>
      </div>
      <SettingsSaveBar
        text="泡袋、茶袋、标签、服务、设计、制版、辅料、快递纸箱、PVC礼盒固定不扣库存，具体判断由服务层保护。"
        saving={saving}
        onSave={() => void saveSystemSetting()}
      />
      <Dialog open={Boolean(categoryDraft)} onOpenChange={(open) => {
        if (!open && !categorySaving) setCategoryDraft(null);
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{categoryDraft?.id ? "编辑分类" : "新增分类"}</DialogTitle>
            <DialogDescription>
              分类库存策略保存后会同步这个分类下商品的 SKU 规则。
            </DialogDescription>
          </DialogHeader>
          {categoryDraft ? (
            <FieldGroup>
              <Field>
                <FieldLabel>分类名称</FieldLabel>
                <Input
                  value={categoryDraft.name}
                  placeholder="例如：PVC礼盒"
                  onChange={(event) => setCategoryDraft({ ...categoryDraft, name: event.target.value })}
                />
              </Field>
              <FieldGroup className="settings-form-grid settings-form-grid--two">
                <Field>
                  <FieldLabel>商品类型</FieldLabel>
                  <Select
                    value={categoryDraft.product_type || "other"}
                    onValueChange={(next) => setCategoryDraft({ ...categoryDraft, product_type: next })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="选择商品类型" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {productTypeOptions.map((item) => (
                          <SelectItem value={item.value} key={item.value}>{item.label}</SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
                <Field>
                  <FieldLabel>分类库存策略</FieldLabel>
                  <Select
                    value={categoryDraft.inventory_policy || "strict"}
                    onValueChange={(next) => setCategoryDraft({ ...categoryDraft, inventory_policy: next })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="选择库存策略" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        {inventoryPolicyOptions.map((item) => (
                          <SelectItem value={item.value} key={item.value}>{item.label}</SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </Field>
              </FieldGroup>
              <Field>
                <FieldLabel>排序</FieldLabel>
                <Input
                  type="number"
                  value={categoryDraft.sort_order || 0}
                  onChange={(event) => setCategoryDraft({ ...categoryDraft, sort_order: Number(event.target.value || 0) })}
                />
              </Field>
            </FieldGroup>
          ) : null}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={categorySaving} onClick={() => setCategoryDraft(null)}>
              取消
            </Button>
            <Button type="button" disabled={categorySaving || !String(categoryDraft?.name || "").trim()} onClick={() => void saveCategory()}>
              <Save data-icon="inline-start" />
              {categorySaving ? "保存中" : "保存分类"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function InventoryRulesPanel({ markDirty, onSaved, onError, registerSave }: PanelCallbacks) {
  const [setting, setSetting] = useState<SystemSetting | null>(null);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [categorySavingId, setCategorySavingId] = useState<number | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [inventorySetting, warehouseData] = await Promise.all([
        api.systemSetting("inventory_rules"),
        api.warehouses()
      ]);
      setSetting(inventorySetting);
      setWarehouses(warehouseData.list || []);
    } catch (err) {
      onError(err instanceof Error ? err.message : "库存规则加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function patchSetting(patch: Record<string, unknown>) {
    setSetting((current) => {
      const existing = current || { key: "inventory_rules", value: {} };
      return { ...existing, value: { ...(existing.value || {}), ...patch } };
    });
    markDirty();
  }

  async function saveSystemSetting() {
    if (!setting) return false;
    setSaving(true);
    try {
      setSetting(await api.saveSystemSetting("inventory_rules", { value: setting.value || {} }));
      onSaved("库存规则已保存");
      return true;
    } catch (err) {
      onError(err instanceof Error ? err.message : "库存规则保存失败");
      return false;
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    registerSave("inventory", saveSystemSetting);
  });

  async function updateCategoryPolicy(category: ProductCategory, inventoryPolicy: string) {
    if (!category.id) return;
    setCategorySavingId(category.id);
    try {
      const result = await api.saveProductCategory({
        id: category.id,
        parent_id: category.parent_id || category.pid || 0,
        name: category.name,
        product_type: category.product_type || "other",
        inventory_policy: inventoryPolicy,
        sort_order: Number(category.sort_order || 0),
        is_enabled: Number(category.is_enabled ?? 1)
      });
      await load();
      const synced = result.synced || {};
      const total = Number(synced.sku || 0) + Number(synced.spu || 0);
      onSaved(total > 0 ? `分类库存策略已保存，已同步 ${total} 条商品规则` : "分类库存策略已保存");
    } catch (err) {
      onError(err instanceof Error ? err.message : "分类库存策略保存失败");
    } finally {
      setCategorySavingId(null);
    }
  }

  if (loading) return <SettingsLoading rows={4} />;
  if (!setting) return <SettingsEmpty title="没有库存规则" desc="后端还没有返回库存规则配置。" />;

  const value = setting.value || {};
  const allWarehouses = setting.warehouses || warehouses;
  const stockCategories = (setting.categories || []).filter((item) => item.inventory_policy !== "none");
  const nonStockCategories = (setting.categories || []).filter((item) => item.inventory_policy === "none");
  const stockKeywords = asStringArray(value.stock_category_keywords);
  const nonStockKeywords = asStringArray(value.non_stock_category_keywords);
  const selectedWarehouseId = String(numberValue(value.default_out_warehouse_id, Number(allWarehouses[0]?.id || 0)));

  return (
    <>
      <div className="settings-two-column">
        <Card>
          <CardHeader>
            <CardTitle>分类库存策略</CardTitle>
            <CardDescription>这里直接控制分类下商品是否进库存页，保存后服务层同步 SKU。</CardDescription>
          </CardHeader>
          <CardContent className="settings-stack">
            <div className="settings-rule-callout">
              <strong>分类优先，关键词兜底</strong>
              <span>分类有明确库存策略时按分类执行；没有明确策略时，再按下面关键词判断。</span>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>分类</TableHead>
                  <TableHead>商品</TableHead>
                  <TableHead>策略</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(setting.categories || []).map((category) => (
                  <TableRow key={category.id || category.name}>
                    <TableCell>
                      <div className="settings-table-title">
                        <strong>{category.name}</strong>
                        <span>{productTypeText(category.product_type)}</span>
                      </div>
                    </TableCell>
                    <TableCell>{category.total ?? 0}</TableCell>
                    <TableCell>
                      <Select
                        value={category.inventory_policy || "strict"}
                        disabled={categorySavingId === category.id}
                        onValueChange={(next) => void updateCategoryPolicy(category, next)}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="选择策略" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            {inventoryPolicyOptions.map((item) => (
                              <SelectItem value={item.value} key={item.value}>{item.label}</SelectItem>
                            ))}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <section className="settings-rule-list">
              <h3>扣库存分类</h3>
              <div className="settings-badge-list">
                {stockCategories.map((category) => (
                  <Badge variant="outline" key={category.id || category.name}>{category.name}</Badge>
                ))}
              </div>
            </section>
            <section className="settings-rule-list">
              <h3>不扣库存分类</h3>
              <div className="settings-badge-list">
                {nonStockCategories.map((category) => (
                  <Badge variant="secondary" key={category.id || category.name}>{category.name}</Badge>
                ))}
              </div>
            </section>
            <div className="settings-two-column">
              <SettingListEditor
                label="扣库存关键词"
                values={stockKeywords}
                placeholder="例如：礼盒"
                onChange={(values) => patchSetting({ stock_category_keywords: values })}
              />
              <SettingListEditor
                label="不扣库存关键词"
                values={nonStockKeywords}
                placeholder="例如：泡袋"
                onChange={(values) => patchSetting({ non_stock_category_keywords: values })}
              />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>出库默认项</CardTitle>
            <CardDescription>开单和库存调整默认使用的仓库规则。</CardDescription>
          </CardHeader>
          <CardContent>
            <FieldGroup>
              <Field>
                <FieldLabel>默认出库仓库</FieldLabel>
                <Select value={selectedWarehouseId || "0"} onValueChange={(next) => patchSetting({ default_out_warehouse_id: Number(next) })}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择仓库" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {allWarehouses.map((warehouse) => (
                        <SelectItem value={String(warehouse.id)} key={warehouse.id}>{warehouse.name}</SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Field orientation="horizontal">
                <FieldContent>
                  <FieldLabel>允许负库存开单</FieldLabel>
                  <FieldDescription>关闭后服务层会阻止库存不足的销售出库。</FieldDescription>
                </FieldContent>
                <Switch
                  checked={Number(value.allow_negative_stock || 0) === 1}
                  onCheckedChange={(checked) => patchSetting({ allow_negative_stock: checked ? 1 : 0 })}
                />
              </Field>
            </FieldGroup>
          </CardContent>
        </Card>
      </div>
      <SettingsSaveBar
        text="保存后更新默认仓库、负库存和关键词规则；分类策略会在选择后立即同步。"
        saving={saving}
        onSave={() => void saveSystemSetting()}
      />
    </>
  );
}

function PaymentRulesPanel({ markDirty, onSaved, onError, registerSave }: PanelCallbacks) {
  const [setting, setSetting] = useState<SystemSetting | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setSetting(await api.systemSetting("payment_rules"));
    } catch (err) {
      onError(err instanceof Error ? err.message : "收款结款设置加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function patchSetting(patch: Record<string, unknown>) {
    setSetting((current) => {
      const existing = current || { key: "payment_rules", value: {} };
      return { ...existing, value: { ...(existing.value || {}), ...patch } };
    });
    markDirty();
  }

  async function saveSystemSetting() {
    if (!setting) return false;
    setSaving(true);
    try {
      setSetting(await api.saveSystemSetting("payment_rules", { value: setting.value || {} }));
      onSaved("收款结款设置已保存");
      return true;
    } catch (err) {
      onError(err instanceof Error ? err.message : "收款结款设置保存失败");
      return false;
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    registerSave("payment", saveSystemSetting);
  });

  if (loading) return <SettingsLoading rows={3} />;
  if (!setting) return <SettingsEmpty title="没有收款结款设置" desc="后端还没有返回付款规则。" />;

  const value = setting.value || {};
  const statuses = asStringArray(value.payment_statuses);
  const methods = asStringArray(value.paid_methods);

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>付款规则</CardTitle>
          <CardDescription>普通客户和月结客户的开单默认项会按这里的配置进入开单页。</CardDescription>
        </CardHeader>
        <CardContent className="settings-stack">
          <div className="settings-two-column">
            <SettingListEditor
              label="付款状态"
              values={statuses}
              placeholder="例如：已付"
              onChange={(values) => patchSetting({ payment_statuses: values })}
            />
            <SettingListEditor
              label="已付方式"
              values={methods}
              placeholder="例如：微信"
              onChange={(values) => patchSetting({ paid_methods: values })}
            />
          </div>
          <FieldGroup className="settings-form-grid settings-form-grid--two">
            <Field>
              <FieldLabel>默认结款状态</FieldLabel>
              <Select
                value={stringValue(value.default_payment_status) || statuses[0] || "已付"}
                onValueChange={(next) => patchSetting({ default_payment_status: next })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择状态" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {(statuses.length ? statuses : ["已付"]).map((item) => (
                      <SelectItem value={item} key={item}>{item}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel>默认已付方式</FieldLabel>
              <Select
                value={stringValue(value.default_paid_method) || methods[0] || "微信"}
                onValueChange={(next) => patchSetting({ default_paid_method: next })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择方式" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {(methods.length ? methods : ["微信"]).map((item) => (
                      <SelectItem value={item} key={item}>{item}</SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
          </FieldGroup>
          <SettingListEditor
            label="余额调整原因"
            values={asStringArray(value.balance_adjust_reasons)}
            placeholder="例如：对账修正"
            onChange={(values) => patchSetting({ balance_adjust_reasons: values })}
          />
          <Field>
            <FieldLabel>月结说明</FieldLabel>
            <Input
              value={stringValue(value.monthly_customer_rule)}
              onChange={(event) => patchSetting({ monthly_customer_rule: event.target.value })}
            />
          </Field>
        </CardContent>
      </Card>
      <SettingsSaveBar
        text="普通客户默认已付，月结客户由客户资料开关自动识别。"
        saving={saving}
        onSave={() => void saveSystemSetting()}
      />
    </>
  );
}

function MediaSummaryCards({ summary }: { summary?: MediaSummary }) {
  const items = [
    ["全部图片", summary?.total ?? "-"],
    ["未绑定", summary?.pending ?? "-"],
    ["主图", summary?.main ?? "-"],
    ["详情图", summary?.detail ?? "-"],
    ["颜色图", summary?.color ?? "-"]
  ];
  return (
    <div className="settings-metric-grid settings-metric-grid--five">
      {items.map(([label, value]) => (
        <Card key={label}>
          <CardContent><span>{label}</span><strong>{value}</strong></CardContent>
        </Card>
      ))}
    </div>
  );
}

function MediaSettingsPanel({ onSaved, onError }: PanelCallbacks) {
  const [setting, setSetting] = useState<SystemSetting | null>(null);
  const [mediaType, setMediaType] = useState("");
  const [items, setItems] = useState<ProductMediaAsset[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProductMediaAsset | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pageSize = 24;
  const mediaThumbRule = "x-oss-process";

  async function loadMedia(nextPage = page, nextType = mediaType) {
    setLoading(true);
    try {
      const [imageSetting, mediaData] = await Promise.all([
        api.systemSetting("image_rules"),
        api.productMedia({ page: nextPage, pageSize, mediaType: nextType })
      ]);
      setSetting(imageSetting);
      setItems(mediaData.list || []);
      setTotal(mediaData.total || 0);
      setPage(nextPage);
    } catch (err) {
      onError(err instanceof Error ? err.message : "图片资产加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadMedia(1, "");
  }, []);

  async function uploadPendingImage(file: File) {
    setUploading(true);
    try {
      const result = await api.uploadProductImage(file);
      const url = uploadResultUrl(result);
      if (!url) throw new Error("OSS 没有返回图片地址");
      setMediaType("pending");
      await loadMedia(1, "pending");
      onSaved("上传待绑定图片成功，已进入未绑定图片列表");
    } catch (err) {
      onError(err instanceof Error ? err.message : "待绑定图片上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function deleteProductMedia() {
    if (!deleteTarget?.id) return;
    setDeleting(true);
    try {
      await api.deleteProductMedia(Number(deleteTarget.id));
      setDeleteTarget(null);
      await loadMedia(page, mediaType);
      onSaved("图片资产已删除");
    } catch (err) {
      onError(err instanceof Error ? err.message : "图片删除失败");
    } finally {
      setDeleting(false);
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <>
      <MediaSummaryCards summary={setting?.media_summary} />
      <Card>
        <CardHeader>
          <div>
            <CardTitle>图片资产</CardTitle>
            <CardDescription>这里是商品图资产库，未绑定图片上传后不会自动写入小程序设置。</CardDescription>
          </div>
          <CardAction>
            <input
              ref={fileInputRef}
              className="settings-file-input"
              type="file"
              accept="image/*"
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                event.currentTarget.value = "";
                if (file) void uploadPendingImage(file);
              }}
            />
            <Button type="button" size="sm" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
              <Upload data-icon="inline-start" />
              {uploading ? "上传中" : "上传待绑定图片"}
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent className="settings-stack">
          <Tabs
            value={mediaType || "all"}
            onValueChange={(value) => {
              const nextType = mediaTypeTabs.find((tab) => tab.key === value)?.value || "";
              setMediaType(nextType);
              void loadMedia(1, nextType);
            }}
            className="settings-media-tabs"
          >
            <TabsList>
              {mediaTypeTabs.map((tab) => (
                <TabsTrigger value={tab.key} key={tab.key}>{tab.label}</TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <div className="settings-media-meta">
            <Badge variant="outline">第 {page} / {pageCount} 页</Badge>
            <span>共 {total} 张，缩略图规则使用 {mediaThumbRule}</span>
          </div>
          {loading ? (
            <div className="settings-media-grid">
              {Array.from({ length: 8 }).map((_, index) => <Skeleton className="settings-media-skeleton" key={index} />)}
            </div>
          ) : items.length ? (
            <div className="settings-media-grid">
              {items.map((asset, index) => (
                <article className="settings-media-card" key={`${asset.id || asset.url}-${index}`}>
                  <div className="settings-media-thumb">
                    <img src={thumbnailUrl(asset.url)} alt={asset.binding_text || asset.product_name || "图片资产"} loading="lazy" />
                    {asset.id ? (
                      <Button
                        type="button"
                        size="icon-xs"
                        variant="secondary"
                        className="settings-media-delete"
                        aria-label="删除图片"
                        onClick={() => setDeleteTarget(asset)}
                      >
                        <Trash2 />
                      </Button>
                    ) : null}
                  </div>
                  <div className="settings-media-info">
                    <strong>{asset.product_name || asset.binding_text || "未绑定图片"}</strong>
                    <span>{asset.asset_group_text || asset.category_name || "其他分类"}</span>
                    <span>{[asset.media_type_text, asset.sku_color, asset.source_text].filter(Boolean).join(" / ") || asset.media_type}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <SettingsEmpty title="没有图片资产" desc="当前筛选下没有可展示的商品图片。" />
          )}
          <Pagination>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious disabled={page <= 1 || loading} onClick={() => void loadMedia(page - 1)}>上一页</PaginationPrevious>
              </PaginationItem>
              <PaginationItem>
                <Badge variant="outline">{page} / {pageCount}</Badge>
              </PaginationItem>
              <PaginationItem>
                <PaginationNext disabled={page >= pageCount || loading} onClick={() => void loadMedia(page + 1)}>下一页</PaginationNext>
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </CardContent>
      </Card>
      <AlertDialog open={Boolean(deleteTarget)} onOpenChange={(open) => {
        if (!open) setDeleteTarget(null);
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除这张图片资产？</AlertDialogTitle>
            <AlertDialogDescription>
              删除后只移除图片资产记录，已绑定到商品或小程序配置的地址不会自动清空。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
            <AlertDialogAction disabled={deleting} onClick={() => void deleteProductMedia()}>
              {deleting ? "删除中" : "确认删除"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function MiniappSettingsPanel({ onSaved, onError }: PanelCallbacks) {
  const [config, setConfig] = useState<MiniappImageConfig>({ assets: [], categories: [] });
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data = await api.miniappImageConfig();
      setConfig({
        assets: Array.isArray(data.assets) ? data.assets : [],
        categories: Array.isArray(data.categories) ? data.categories : []
      });
    } catch (err) {
      onError(err instanceof Error ? err.message : "小程序设置加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const assetsByScene = useMemo(() => {
    const groups = new Map<MiniappAssetScene, MiniappAssetImageItem[]>();
    for (const scene of visibleMiniappScenes) groups.set(scene, []);
    for (const asset of config.assets) {
      if (!visibleMiniappScenes.includes(asset.scene as MiniappAssetScene)) continue;
      const scene = asset.scene as MiniappAssetScene;
      groups.set(scene, [...(groups.get(scene) || []), asset]);
    }
    return groups;
  }, [config.assets]);

  async function uploadMiniappImage(targetType: MiniappImageTarget, id: number, field: MiniappImageField, file: File) {
    if (!id) return;
    const key = `${targetType}:${id}:${field}`;
    setBusyKey(key);
    try {
      const uploaded = await api.uploadMiniappImage(file);
      const url = uploadResultUrl(uploaded);
      if (!url) throw new Error("OSS 没有返回图片地址");
      await api.updateMiniappImage({ target_type: targetType, id, field, url });
      await load();
      onSaved("小程序设置图片已更新");
    } catch (err) {
      onError(err instanceof Error ? err.message : "小程序图片上传或保存失败");
    } finally {
      setBusyKey("");
    }
  }

  if (loading) return <SettingsLoading rows={4} />;

  return (
    <div className="settings-stack">
      <Card>
        <CardHeader>
          <CardTitle>小程序设置</CardTitle>
          <CardDescription>这里维护小程序首页轮播、商品分类图标和底部导航图标，和商品图片资产独立保存。</CardDescription>
        </CardHeader>
      </Card>
      <MiniappImageConfigTable
        icon={<Images aria-hidden="true" />}
        title="首页轮播"
        desc="只维护轮播图片地址，尺寸裁切由小程序前端按页面规则处理。"
        countText={`${assetsByScene.get("home_banner")?.length || 0} 张`}
        emptyText="暂无首页轮播配置"
        targetType="miniapp_asset"
        items={assetsByScene.get("home_banner") || []}
        fields={bannerFields}
        busyKey={busyKey}
        getId={(asset) => Number(asset.id || 0)}
        getName={(asset) => asset.title || asset.name || "首页轮播"}
        getMeta={assetMeta}
        onUpload={uploadMiniappImage}
      />
      <MiniappImageConfigTable
        icon={<Layers aria-hidden="true" />}
        title="商品分类图标"
        desc="首页分类入口和分类页共用这一套图标，只区分未选中和选中。"
        countText={`${config.categories.length} 个分类`}
        emptyText="暂无商品分类"
        targetType="category"
        items={config.categories}
        fields={categoryImageFields}
        busyKey={busyKey}
        getId={(category) => Number(category.id || 0)}
        getName={(category) => category.name}
        getMeta={categoryMeta}
        onUpload={uploadMiniappImage}
      />
      <MiniappImageConfigTable
        icon={<Navigation aria-hidden="true" />}
        title="底部导航图标"
        desc="底部导航保留未选中和选中两种状态，规则和分类图标一致。"
        countText={`${assetsByScene.get("bottom_tab")?.length || 0} 个入口`}
        emptyText="暂无底部导航图标配置"
        targetType="miniapp_asset"
        items={assetsByScene.get("bottom_tab") || []}
        fields={bottomTabFields}
        busyKey={busyKey}
        getId={(asset) => Number(asset.id || 0)}
        getName={(asset) => asset.title || asset.name || "导航入口"}
        getMeta={assetMeta}
        onUpload={uploadMiniappImage}
      />
    </div>
  );
}

function UserPermissionsPanel({ onSaved, onError }: PanelCallbacks) {
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyUserId, setBusyUserId] = useState<number | null>(null);
  const [disableTarget, setDisableTarget] = useState<UserListItem | null>(null);

  async function load(nextKeyword = keyword) {
    setLoading(true);
    try {
      const data = await api.users(nextKeyword, 1, 50);
      setUsers(data.list || []);
    } catch (err) {
      onError(err instanceof Error ? err.message : "用户列表加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load("");
  }, []);

  async function updateUser(user: UserListItem, patch: Partial<Pick<UserListItem, "role" | "is_active">>) {
    setBusyUserId(user.id);
    try {
      await api.updateUser(user.id, patch);
      await load(keyword);
      onSaved("用户权限已更新");
    } catch (err) {
      onError(err instanceof Error ? err.message : "用户更新失败");
    } finally {
      setBusyUserId(null);
      setDisableTarget(null);
    }
  }

  return (
    <>
      <Card>
        <CardHeader>
          <div>
            <CardTitle>用户权限</CardTitle>
            <CardDescription>管理后台账号角色、启用状态和客户绑定关系。</CardDescription>
          </div>
          <CardAction>
            <form className="settings-search-form" onSubmit={(event) => {
              event.preventDefault();
              void load(keyword);
            }}>
              <Input value={keyword} placeholder="搜索账号、姓名、电话" onChange={(event) => setKeyword(event.target.value)} />
              <Button type="submit" variant="outline" disabled={loading}>
                <Search data-icon="inline-start" />
                搜索
              </Button>
            </form>
          </CardAction>
        </CardHeader>
        <CardContent>
          {loading ? (
            <SettingsLoading rows={4} />
          ) : users.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>用户</TableHead>
                  <TableHead>角色</TableHead>
                  <TableHead>绑定客户</TableHead>
                  <TableHead>启用</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <div className="settings-table-title">
                        <strong>{user.display_name || user.account_display || user.username}</strong>
                        <span>{[user.account_display || user.username, user.phone].filter(Boolean).join(" / ") || `ID ${user.id}`}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Select
                        value={user.role || "staff"}
                        disabled={busyUserId === user.id}
                        onValueChange={(next) => void updateUser(user, { role: next })}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="选择角色" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectGroup>
                            {roleOptions.map((role) => (
                              <SelectItem value={role.value} key={role.value}>{role.label}</SelectItem>
                            ))}
                          </SelectGroup>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>{user.party_name || "-"}</TableCell>
                    <TableCell>
                      <Switch
                        checked={Number(user.is_active || 0) === 1}
                        disabled={busyUserId === user.id}
                        onCheckedChange={(checked) => {
                          if (!checked) setDisableTarget(user);
                          else void updateUser(user, { is_active: 1 });
                        }}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <SettingsEmpty title="没有找到用户" desc="换一个关键词再搜索。" />
          )}
        </CardContent>
      </Card>
      <AlertDialog open={Boolean(disableTarget)} onOpenChange={(open) => {
        if (!open) setDisableTarget(null);
      }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>停用这个用户？</AlertDialogTitle>
            <AlertDialogDescription>
              停用后该账号不能继续登录后台，但历史单据和操作记录会保留。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={Boolean(busyUserId)}>取消</AlertDialogCancel>
            <AlertDialogAction
              disabled={Boolean(busyUserId)}
              onClick={() => {
                if (disableTarget) void updateUser(disableTarget, { is_active: 0 });
              }}
            >
              确认停用
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function PrintSettingsPanel({ markDirty, onSaved, onError, registerSave }: PanelCallbacks) {
  const [print, setPrint] = useState<PrintSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setPrint(await api.salesPrintSettings());
    } catch (err) {
      onError(err instanceof Error ? err.message : "打印设置加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function patch(patchValue: Partial<PrintSettings>) {
    setPrint((current) => current ? { ...current, ...patchValue } : current);
    markDirty();
  }

  async function saveSalesPrintSettings() {
    if (!print) return false;
    setSaving(true);
    try {
      setPrint(await api.saveSalesPrintSettings(print));
      onSaved("打印设置已保存");
      return true;
    } catch (err) {
      onError(err instanceof Error ? err.message : "打印设置保存失败");
      return false;
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    registerSave("print", saveSalesPrintSettings);
  });

  if (loading) return <SettingsLoading rows={3} />;
  if (!print) return <SettingsEmpty title="没有打印设置" desc="后端还没有返回销售单打印模板。" />;

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>销售单打印模板</CardTitle>
          <CardDescription>这里控制销售单打印标题、纸张和字段显示。</CardDescription>
        </CardHeader>
        <CardContent className="settings-stack">
          <FieldGroup className="settings-form-grid settings-form-grid--two">
            <Field>
              <FieldLabel>模板名称</FieldLabel>
              <Input value={print.name || ""} onChange={(event) => patch({ name: event.target.value })} />
            </Field>
            <Field>
              <FieldLabel>标题</FieldLabel>
              <Input value={print.header_text || ""} onChange={(event) => patch({ header_text: event.target.value })} />
            </Field>
            <Field>
              <FieldLabel>纸张</FieldLabel>
              <Select value={print.paper_size || "A5"} onValueChange={(next) => patch({ paper_size: next })}>
                <SelectTrigger>
                  <SelectValue placeholder="选择纸张" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="A5">A5</SelectItem>
                    <SelectItem value="A4">A4</SelectItem>
                    <SelectItem value="80MM">80mm</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel>方向</FieldLabel>
              <Select value={print.orientation || "landscape"} onValueChange={(next) => patch({ orientation: next })}>
                <SelectTrigger>
                  <SelectValue placeholder="选择方向" />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="landscape">横向</SelectItem>
                    <SelectItem value="portrait">竖向</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>
            <Field>
              <FieldLabel>字号</FieldLabel>
              <Input
                type="number"
                value={print.font_size || 12}
                onChange={(event) => patch({ font_size: Number(event.target.value || 12) })}
              />
            </Field>
            <Field>
              <FieldLabel>份数</FieldLabel>
              <Input
                type="number"
                value={print.copies || 1}
                onChange={(event) => patch({ copies: Number(event.target.value || 1) })}
              />
            </Field>
          </FieldGroup>
          <div className="settings-switch-grid">
            {[
              ["显示开单人", "show_operator"],
              ["显示客户电话", "show_customer_phone"],
              ["显示付款状态", "show_payment"],
              ["显示备注", "show_note"],
              ["显示 Logo", "show_logo"]
            ].map(([label, key]) => (
              <Field orientation="horizontal" key={key}>
                <FieldLabel>{label}</FieldLabel>
                <Switch
                  checked={Number(print[key as keyof PrintSettings] || 0) === 1}
                  onCheckedChange={(checked) => patch({ [key]: checked ? 1 : 0 } as Partial<PrintSettings>)}
                />
              </Field>
            ))}
          </div>
          <Field>
            <FieldLabel>底部文字</FieldLabel>
            <Input value={print.footer_text || ""} onChange={(event) => patch({ footer_text: event.target.value })} />
          </Field>
        </CardContent>
      </Card>
      <SettingsSaveBar
        text={print.latest_sales_no ? `可预览最近销售单：${print.latest_sales_no}` : "还没有可预览的销售单"}
        saving={saving}
        onSave={() => void saveSalesPrintSettings()}
      />
    </>
  );
}

function MiniappImageConfigTable<T>({
  icon,
  title,
  desc,
  countText,
  emptyText,
  targetType,
  items,
  fields,
  busyKey,
  getId,
  getName,
  getMeta,
  onUpload
}: {
  icon: ReactNode;
  title: string;
  desc: string;
  countText: string;
  emptyText: string;
  targetType: MiniappImageTarget;
  items: T[];
  fields: Array<ImageFieldConfig<T>>;
  busyKey: string;
  getId: (item: T) => number;
  getName: (item: T) => string;
  getMeta: (item: T) => string;
  onUpload: (targetType: MiniappImageTarget, id: number, field: MiniappImageField, file: File) => void;
}) {
  return (
    <Card className="settings-miniapp-panel">
      <CardHeader>
        <div className="settings-card-title-row">
          {icon}
          <div>
            <CardTitle>{title}</CardTitle>
            <CardDescription>{desc}</CardDescription>
          </div>
        </div>
        <CardAction><Badge variant="outline">{countText}</Badge></CardAction>
      </CardHeader>
      <CardContent>
        {items.length ? (
          <div className={`settings-miniapp-table settings-miniapp-table--${fields.length}-fields`}>
            <div className="settings-miniapp-table-head">
              <span>名称</span>
              {fields.map((field) => <span key={field.field}>{field.label}</span>)}
            </div>
            {items.map((item) => {
              const id = getId(item);
              return (
                <div className="settings-miniapp-row" key={`${targetType}-${id}-${getName(item)}`}>
                  <div className="settings-miniapp-name">
                    <strong>{getName(item)}</strong>
                    <span>{getMeta(item)}</span>
                  </div>
                  {fields.map((field) => (
                    <MiniappImageUploadCell
                      key={field.field}
                      label={field.label}
                      desc={field.desc}
                      url={field.value(item)}
                      busy={busyKey === `${targetType}:${id}:${field.field}`}
                      onUpload={(file) => onUpload(targetType, id, field.field, file)}
                    />
                  ))}
                </div>
              );
            })}
          </div>
        ) : (
          <SettingsEmpty title={emptyText} desc="配置同步后会显示在这里。" />
        )}
      </CardContent>
    </Card>
  );
}

function MiniappImageUploadCell({
  url,
  label,
  desc,
  busy,
  onUpload
}: {
  url?: string;
  label: string;
  desc: string;
  busy: boolean;
  onUpload: (file: File) => void;
}) {
  const cleanUrl = String(url || "").trim();
  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <div className="settings-miniapp-cell">
      <div className="settings-miniapp-preview">
        {cleanUrl ? <img src={thumbnailUrl(cleanUrl)} alt={label} loading="lazy" /> : <Image aria-hidden="true" />}
      </div>
      <div className="settings-miniapp-copy">
        <strong>{label}</strong>
        <span>{desc}</span>
        {cleanUrl ? <code>{cleanUrl}</code> : <em>暂未配置图片</em>}
      </div>
      <input
        ref={inputRef}
        className="settings-file-input"
        type="file"
        accept="image/*"
        disabled={busy}
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = "";
          if (file) onUpload(file);
        }}
      />
      <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => inputRef.current?.click()}>
        <Upload data-icon="inline-start" />
        {busy ? "上传中" : "替换"}
      </Button>
    </div>
  );
}

export { SettingsPage };
