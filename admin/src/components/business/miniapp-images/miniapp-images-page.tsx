import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Image, Images, Layers, Navigation, RefreshCw, Upload } from "lucide-react";

import { api } from "@/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  MiniappAssetImageItem,
  MiniappImageConfig,
  MiniappImageUpdatePayload,
  ProductCategory,
  ProductUploadResult
} from "@/types";

type MiniappImageField = MiniappImageUpdatePayload["field"];
type MiniappImageTarget = MiniappImageUpdatePayload["target_type"];
type MiniappAssetScene = "home_banner" | "bottom_tab";

type ImageFieldConfig<T> = {
  field: MiniappImageField;
  label: string;
  desc: string;
  value: (item: T) => string;
};

const visibleAssetScenes: MiniappAssetScene[] = ["home_banner", "bottom_tab"];

const bannerFields: Array<ImageFieldConfig<MiniappAssetImageItem>> = [
  { field: "asset_url", label: "轮播图片", desc: "首页顶部轮播使用", value: (asset) => asset.asset_url || "" }
];

const bottomTabFields: Array<ImageFieldConfig<MiniappAssetImageItem>> = [
  { field: "asset_url", label: "未选中图标", desc: "底部导航默认状态", value: (asset) => asset.asset_url || "" },
  { field: "active_asset_url", label: "选中图标", desc: "底部导航当前页面状态", value: (asset) => asset.active_asset_url || "" }
];

const categoryImageFields: Array<ImageFieldConfig<ProductCategory>> = [
  { field: "icon", label: "未选中图标", desc: "首页分类入口和分类页默认状态共用", value: (category) => category.icon || "" },
  { field: "icon_active", label: "选中图标", desc: "分类页选中状态使用", value: (category) => category.icon_active || "" }
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

function assetMeta(asset: MiniappAssetImageItem) {
  return [asset.link_type, asset.link_value].filter(Boolean).join(" / ") || "小程序图片";
}

function categoryMeta(category: ProductCategory) {
  return `${category.total || 0} 款产品`;
}

function ImageUploadCell({
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
  return (
    <div className="miniapp-image-cell">
      <div className="miniapp-image-preview">
        {cleanUrl ? <img src={previewUrl(cleanUrl)} alt={label} loading="lazy" /> : <Image aria-hidden="true" />}
      </div>
      <div className="miniapp-image-slot-copy">
        <strong>{label}</strong>
        <span>{desc}</span>
        {cleanUrl ? <code>{cleanUrl}</code> : <em>暂未配置图片</em>}
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

function ImageConfigTable<T>({
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
    <section className="miniapp-image-panel">
      <div className="miniapp-image-panel-head">
        <div>
          {icon}
          <div>
            <h2>{title}</h2>
            <p>{desc}</p>
          </div>
        </div>
        <Badge variant="outline">{countText}</Badge>
      </div>

      {items.length ? (
        <div className={`miniapp-image-table miniapp-image-table--${fields.length}-fields`}>
          <div className="miniapp-image-table-head">
            <span>名称</span>
            {fields.map((field) => <span key={field.field}>{field.label}</span>)}
          </div>
          {items.map((item) => {
            const id = getId(item);
            return (
              <div className="miniapp-image-row" key={`${targetType}-${id}-${getName(item)}`}>
                <div className="miniapp-image-name">
                  <strong>{getName(item)}</strong>
                  <span>{getMeta(item)}</span>
                </div>
                {fields.map((field) => (
                  <ImageUploadCell
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
        <div className="empty-state">{emptyText}</div>
      )}
    </section>
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

  const assetsByScene = useMemo(() => {
    const groups = new Map<MiniappAssetScene, MiniappAssetImageItem[]>();
    for (const scene of visibleAssetScenes) groups.set(scene, []);
    for (const asset of config.assets) {
      if (!visibleAssetScenes.includes(asset.scene as MiniappAssetScene)) continue;
      const scene = asset.scene as MiniappAssetScene;
      groups.set(scene, [...(groups.get(scene) || []), asset]);
    }
    return groups;
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
          <p>首页分类和分类页共用商品分类图标，后台只维护未选中和选中两种状态。</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw aria-hidden="true" />
          {loading ? "刷新中" : "刷新"}
        </Button>
      </div>

      {notice ? <div className="form-success">{notice}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}
      {loading && !config.assets.length && !config.categories.length ? <div className="empty-state">小程序图片配置加载中</div> : null}

      <ImageConfigTable
        icon={<Images aria-hidden="true" />}
        title="首页轮播图"
        desc="只维护轮播图片本身，尺寸和裁切由小程序前端控制。"
        countText={`${assetsByScene.get("home_banner")?.length || 0} 张`}
        emptyText="暂无首页轮播图配置"
        targetType="miniapp_asset"
        items={assetsByScene.get("home_banner") || []}
        fields={bannerFields}
        busyKey={busyKey}
        getId={(asset) => Number(asset.id || 0)}
        getName={(asset) => asset.title || asset.name || "首页轮播图"}
        getMeta={assetMeta}
        onUpload={uploadAndSave}
      />

      <ImageConfigTable
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
        onUpload={uploadAndSave}
      />

      <ImageConfigTable
        icon={<Navigation aria-hidden="true" />}
        title="底部导航图标"
        desc="底部导航保留未选中和选中两种状态，和分类图标规则一致。"
        countText={`${assetsByScene.get("bottom_tab")?.length || 0} 个入口`}
        emptyText="暂无底部导航图标配置"
        targetType="miniapp_asset"
        items={assetsByScene.get("bottom_tab") || []}
        fields={bottomTabFields}
        busyKey={busyKey}
        getId={(asset) => Number(asset.id || 0)}
        getName={(asset) => asset.title || asset.name || "导航入口"}
        getMeta={assetMeta}
        onUpload={uploadAndSave}
      />
    </section>
  );
}
