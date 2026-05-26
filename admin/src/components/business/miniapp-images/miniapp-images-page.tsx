import { useEffect, useMemo, useState } from "react";
import { Image, Images, Layers, RefreshCw, Upload } from "lucide-react";

import { api } from "@/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle
} from "@/components/ui/card";
import type {
  MiniappAssetImageItem,
  MiniappImageConfig,
  MiniappImageUpdatePayload,
  ProductCategory,
  ProductUploadResult
} from "@/types";

type MiniappImageField = MiniappImageUpdatePayload["field"];
type MiniappImageTarget = MiniappImageUpdatePayload["target_type"];

const sceneLabels: Record<string, string> = {
  home_banner: "首页轮播图",
  home_category: "首页分类入口",
  home_quick: "首页快捷导航",
  bottom_tab: "底部导航"
};

const categoryImageFields: Array<{ field: MiniappImageField; label: string; desc: string }> = [
  { field: "icon", label: "默认图标", desc: "分类页、首页分类入口共用" },
  { field: "icon_active", label: "选中图标", desc: "分类页选中状态使用" },
  { field: "realistic_images", label: "写实图", desc: "后续需要写实预览时使用" },
  { field: "big_images", label: "高清大图", desc: "首页大图标或后续大尺寸场景使用" }
];

function uploadResultUrl(result: ProductUploadResult) {
  return result.url || result.full_url || result.images || result.path || "";
}

function previewUrl(url = "") {
  const clean = String(url || "").trim();
  if (!clean || !clean.includes("img.513sjbz.com") || clean.includes("x-oss-process=")) return clean;
  const joiner = clean.includes("?") ? "&" : "?";
  return `${clean}${joiner}x-oss-process=image/resize,m_lfit,w_360,h_260/quality,q_85`;
}

function sceneLabel(scene: string) {
  return sceneLabels[scene] || scene || "未分组";
}

function assetFields(asset: MiniappAssetImageItem): Array<{ field: MiniappImageField; label: string; desc: string }> {
  const fields: Array<{ field: MiniappImageField; label: string; desc: string }> = [
    { field: "asset_url", label: asset.scene === "home_banner" ? "图片" : "默认图", desc: "小程序默认展示图片" }
  ];
  if (asset.scene === "bottom_tab" || asset.active_asset_url) {
    fields.push({ field: "active_asset_url", label: "选中图", desc: "底部导航或选中状态图片" });
  }
  return fields;
}

function ImageSlot({
  url,
  label,
  desc,
  busy,
  onUpload
}: {
  url?: string;
  label: string;
  desc?: string;
  busy: boolean;
  onUpload: (file: File) => void;
}) {
  return (
    <div className="miniapp-image-slot">
      <div className="miniapp-image-preview">
        {url ? <img src={previewUrl(url)} alt={label} loading="lazy" /> : <Image aria-hidden="true" />}
      </div>
      <div className="miniapp-image-slot-copy">
        <strong>{label}</strong>
        {desc ? <span>{desc}</span> : null}
        {url ? <code>{url}</code> : <em>暂未配置图片</em>}
      </div>
      <label className={busy ? "miniapp-upload-button disabled" : "miniapp-upload-button"}>
        <Upload aria-hidden="true" />
        {busy ? "上传中" : "替换"}
        <input
          type="file"
          accept="image/*"
          disabled={busy}
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = "";
            if (file) onUpload(file);
          }}
        />
      </label>
    </div>
  );
}

function AssetCard({
  asset,
  busyKey,
  onUpload
}: {
  asset: MiniappAssetImageItem;
  busyKey: string;
  onUpload: (targetType: MiniappImageTarget, id: number, field: MiniappImageField, file: File) => void;
}) {
  return (
    <Card className="miniapp-image-card">
      <CardHeader>
        <div className="miniapp-image-card-title">
          <CardTitle>{asset.title || asset.name}</CardTitle>
          <Badge variant={asset.enabled ? "secondary" : "outline"}>{sceneLabel(asset.scene)}</Badge>
        </div>
        <CardDescription>
          {[asset.link_type, asset.link_value].filter(Boolean).join(" / ") || "小程序配置图片"}
        </CardDescription>
      </CardHeader>
      <CardContent className="miniapp-image-card-content">
        {assetFields(asset).map((item) => (
          <ImageSlot
            key={item.field}
            label={item.label}
            desc={item.desc}
            url={String(asset[item.field as keyof MiniappAssetImageItem] || "")}
            busy={busyKey === `miniapp_asset:${asset.id}:${item.field}`}
            onUpload={(file) => onUpload("miniapp_asset", asset.id, item.field, file)}
          />
        ))}
      </CardContent>
    </Card>
  );
}

function CategoryCard({
  category,
  busyKey,
  onUpload
}: {
  category: ProductCategory;
  busyKey: string;
  onUpload: (targetType: MiniappImageTarget, id: number, field: MiniappImageField, file: File) => void;
}) {
  const categoryId = Number(category.id || 0);
  return (
    <Card className="miniapp-image-card">
      <CardHeader>
        <div className="miniapp-image-card-title">
          <CardTitle>{category.name}</CardTitle>
          <Badge variant="outline">{category.total || 0} 款产品</Badge>
        </div>
        <CardDescription>
          {category.product_type || "商品分类"} · {category.inventory_policy || "默认库存策略"}
        </CardDescription>
      </CardHeader>
      <CardContent className="miniapp-image-card-content">
        {categoryImageFields.map((item) => (
          <ImageSlot
            key={item.field}
            label={item.label}
            desc={item.desc}
            url={String(category[item.field as keyof ProductCategory] || "")}
            busy={busyKey === `category:${categoryId}:${item.field}`}
            onUpload={(file) => onUpload("category", categoryId, item.field, file)}
          />
        ))}
      </CardContent>
    </Card>
  );
}

export function MiniappImagesPage() {
  const [config, setConfig] = useState<MiniappImageConfig>({ assets: [], categories: [] });
  const [loading, setLoading] = useState(false);
  const [busyKey, setBusyKey] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await api.miniappImageConfig();
      setConfig({
        assets: Array.isArray(data.assets) ? data.assets : [],
        categories: Array.isArray(data.categories) ? data.categories : []
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "小程序图片配置加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const groupedAssets = useMemo(() => {
    const groups = new Map<string, MiniappAssetImageItem[]>();
    for (const asset of config.assets) {
      const key = asset.scene || "other";
      groups.set(key, [...(groups.get(key) || []), asset]);
    }
    return Array.from(groups.entries()).sort(([left], [right]) => {
      const order = ["home_banner", "home_category", "home_quick", "bottom_tab"];
      const leftIndex = order.indexOf(left);
      const rightIndex = order.indexOf(right);
      return (leftIndex === -1 ? order.length : leftIndex) - (rightIndex === -1 ? order.length : rightIndex);
    });
  }, [config.assets]);

  async function uploadAndSave(targetType: MiniappImageTarget, id: number, field: MiniappImageField, file: File) {
    if (!id) return;
    const key = `${targetType}:${id}:${field}`;
    setBusyKey(key);
    setError("");
    setNotice("");
    try {
      const uploaded = await api.uploadMiniappImage(file);
      const url = uploadResultUrl(uploaded);
      if (!url) throw new Error("OSS 没有返回图片地址");
      await api.updateMiniappImage({ target_type: targetType, id, field, url });
      setNotice("图片已更新，小程序重新请求配置后会使用新地址。");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "图片上传或保存失败");
    } finally {
      setBusyKey("");
    }
  }

  return (
    <section className="miniapp-images-page">
      <div className="settings-head miniapp-images-head">
        <div>
          <span className="pill">小程序图片配置</span>
          <h1>小程序图片</h1>
          <p>维护首页图、底部导航图标、分类图标和后续大尺寸图片。</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw aria-hidden="true" />
          {loading ? "刷新中" : "刷新"}
        </Button>
      </div>

      {notice ? <div className="form-success">{notice}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}

      <div className="miniapp-image-section-head">
        <div>
          <Images aria-hidden="true" />
          <h2>小程序配置图</h2>
        </div>
        <span>{config.assets.length} 项</span>
      </div>

      {loading && !config.assets.length ? <div className="empty-state">小程序图片配置加载中</div> : null}
      {groupedAssets.map(([scene, assets]) => (
        <div className="miniapp-image-group" key={scene}>
          <div className="miniapp-image-group-title">
            <strong>{sceneLabel(scene)}</strong>
            <span>{assets.length} 张配置</span>
          </div>
          <div className="miniapp-image-grid">
            {assets.map((asset) => (
              <AssetCard key={asset.id} asset={asset} busyKey={busyKey} onUpload={uploadAndSave} />
            ))}
          </div>
        </div>
      ))}

      <div className="miniapp-image-section-head">
        <div>
          <Layers aria-hidden="true" />
          <h2>商品分类图标</h2>
        </div>
        <span>{config.categories.length} 个分类</span>
      </div>

      <div className="miniapp-image-grid">
        {config.categories.map((category) => (
          <CategoryCard
            key={category.id || category.name}
            category={category}
            busyKey={busyKey}
            onUpload={uploadAndSave}
          />
        ))}
      </div>
      {!loading && !config.categories.length ? <div className="empty-state">暂无商品分类</div> : null}
    </section>
  );
}
