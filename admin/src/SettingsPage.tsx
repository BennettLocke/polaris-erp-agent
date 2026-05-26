import { useEffect, useMemo, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { Check, Plus, RefreshCw, Save, Search, X } from "lucide-react";
import { api } from "./api";
import type {
  MediaSummary,
  NumberSequenceSettings,
  PrintSettings,
  ProductCategory,
  SystemSetting,
  UserListItem,
  Warehouse
} from "./types";

type SettingKey = "product_basic" | "inventory_rules" | "payment_rules" | "image_rules";

const settingTabs: Array<{ key: string; label: string }> = [
  { key: "number", label: "编号" },
  { key: "product", label: "商品基础" },
  { key: "inventory", label: "库存规则" },
  { key: "payment", label: "收款结款" },
  { key: "image", label: "图片 OSS" },
  { key: "users", label: "用户权限" },
  { key: "print", label: "打印" }
];

const roleOptions = [
  { value: "admin", label: "管理员" },
  { value: "staff", label: "员工" },
  { value: "customer", label: "客户" },
  { value: "guest", label: "访客" }
];

function asArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item || "").trim()).filter(Boolean) : [];
}

function fieldValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

function policyText(policy?: string) {
  if (policy === "none") return "不扣库存";
  if (policy === "weak") return "弱库存";
  return "扣库存";
}

function policyClass(policy?: string) {
  if (policy === "none") return "muted";
  if (policy === "weak") return "warn";
  return "ok";
}

function ListEditor({
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
    <div className="setting-field">
      <label>{label}</label>
      <div className="chip-editor">
        {values.map((item) => (
          <button key={item} type="button" className="chip removable" onClick={() => onChange(values.filter((value) => value !== item))}>
            <span>{item}</span>
            <X size={14} />
          </button>
        ))}
      </div>
      <div className="inline-form">
        <input value={draft} placeholder={placeholder} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            addItem();
          }
        }} />
        <button type="button" className="ghost-action compact" onClick={addItem}>
          <Plus size={16} />
          添加
        </button>
      </div>
    </div>
  );
}

function SwitchField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="switch-row">
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}

function SaveBar({ text, onSave }: { text: string; onSave: () => void }) {
  return (
    <div className="settings-savebar">
      <span>{text}</span>
      <button type="button" className="primary-action" onClick={onSave}>
        <Save size={17} />
        保存
      </button>
    </div>
  );
}

function CategoryRows({ categories }: { categories: ProductCategory[] }) {
  if (!categories.length) return <div className="empty-state">还没有分类数据</div>;
  return (
    <div className="setting-table">
      {categories.map((category) => (
        <div className="setting-table-row" key={category.id || category.name}>
          <div>
            <strong>{category.name}</strong>
            <span>{category.total ?? 0} 个商品</span>
          </div>
          <span className={`status-badge ${policyClass(category.inventory_policy)}`}>{policyText(category.inventory_policy)}</span>
        </div>
      ))}
    </div>
  );
}

export function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [sku, setSku] = useState<NumberSequenceSettings | null>(null);
  const [print, setPrint] = useState<PrintSettings | null>(null);
  const [settings, setSettings] = useState<Partial<Record<SettingKey, SystemSetting>>>({});
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [userKeyword, setUserKeyword] = useState("");

  const productValue = settings.product_basic?.value || {};
  const inventoryValue = settings.inventory_rules?.value || {};
  const paymentValue = settings.payment_rules?.value || {};
  const imageValue = settings.image_rules?.value || {};
  const productCategories = settings.product_basic?.categories || [];
  const inventoryCategories = settings.inventory_rules?.categories || [];
  const imageSummary = settings.image_rules?.media_summary;
  const allWarehouses = settings.inventory_rules?.warehouses || warehouses;

  async function loadAll(keyword = userKeyword) {
    setLoading(true);
    setError("");
    try {
      const [skuData, productData, inventoryData, paymentData, imageData, printData, userData, warehouseData] = await Promise.all([
        api.skuNumberSettings(),
        api.systemSetting("product_basic"),
        api.systemSetting("inventory_rules"),
        api.systemSetting("payment_rules"),
        api.systemSetting("image_rules"),
        api.salesPrintSettings(),
        api.users(keyword, 1, 20),
        api.warehouses()
      ]);
      setSku(skuData);
      setSettings({
        product_basic: productData,
        inventory_rules: inventoryData,
        payment_rules: paymentData,
        image_rules: imageData
      });
      setPrint(printData);
      setUsers(userData.list || []);
      setWarehouses(warehouseData.list || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "设置加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll("");
  }, []);

  function patchSetting(key: SettingKey, patch: Record<string, unknown>) {
    setSettings((current) => {
      const existing = current[key] || { key, value: {} };
      return {
        ...current,
        [key]: {
          ...existing,
          value: {
            ...(existing.value || {}),
            ...patch
          }
        }
      };
    });
  }

  async function saveSystem(key: SettingKey) {
    const item = settings[key];
    if (!item) return;
    setMessage("");
    setError("");
    try {
      const saved = await api.saveSystemSetting(key, { value: item.value || {} });
      setSettings((current) => ({ ...current, [key]: saved }));
      setMessage("设置已保存");
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    }
  }

  async function saveSku() {
    if (!sku) return;
    setMessage("");
    setError("");
    try {
      setSku(await api.saveSkuNumberSettings(sku));
      setMessage("编号设置已保存");
    } catch (err) {
      setError(err instanceof Error ? err.message : "编号保存失败");
    }
  }

  async function savePrint() {
    if (!print) return;
    setMessage("");
    setError("");
    try {
      setPrint(await api.saveSalesPrintSettings(print));
      setMessage("打印设置已保存");
    } catch (err) {
      setError(err instanceof Error ? err.message : "打印设置保存失败");
    }
  }

  async function updateUser(user: UserListItem, patch: Partial<UserListItem>) {
    setMessage("");
    setError("");
    try {
      await api.updateUser(user.id, patch);
      await loadAll(userKeyword);
      setMessage("用户已更新");
    } catch (err) {
      setError(err instanceof Error ? err.message : "用户更新失败");
    }
  }

  const fixedRuleGroups = useMemo(() => {
    const stock = inventoryCategories.filter((item) => item.inventory_policy !== "none");
    const nonStock = inventoryCategories.filter((item) => item.inventory_policy === "none");
    return { stock, nonStock };
  }, [inventoryCategories]);

  if (loading) return <section className="panel placeholder-panel">设置加载中</section>;

  return (
    <section className="panel settings-panel">
      <div className="settings-head">
        <div>
          <span className="pill">服务层设置</span>
          <h1>设置</h1>
          <p>编号、商品基础、库存规则、收款结款、图片 OSS、用户和打印都走 sjagent_core。</p>
        </div>
        <button type="button" className="ghost-action" onClick={() => loadAll(userKeyword)}>
          <RefreshCw size={17} />
          刷新
        </button>
      </div>
      {message ? <div className="form-success">{message}</div> : null}
      {error ? <div className="form-error">{error}</div> : null}

      <Tabs.Root defaultValue="number" className="tabs settings-tabs">
        <Tabs.List className="tabs-list wrap">
          {settingTabs.map((item) => (
            <Tabs.Trigger value={item.key} key={item.key}>{item.label}</Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="number" className="tab-content settings-content">
          {sku ? (
            <>
              <div className="metric-grid four">
                <div className="metric-card compact-card"><span>当前下一编号</span><strong>{sku.next_code}</strong></div>
                <div className="metric-card compact-card"><span>配置起点</span><strong>{sku.configured_code}</strong></div>
                <div className="metric-card compact-card"><span>已用 SJ 编号</span><strong>{sku.numeric_used_count}</strong></div>
                <div className="metric-card compact-card"><span>商品数量</span><strong>{sku.total_sku_count}</strong></div>
              </div>
              <div className="settings-grid">
                <label className="setting-field">
                  编号前缀
                  <input value={sku.prefix} onChange={(event) => setSku({ ...sku, prefix: event.target.value })} />
                </label>
                <label className="setting-field">
                  手动调整下一号
                  <input value={sku.next_code} onChange={(event) => setSku({ ...sku, next_code: event.target.value })} />
                </label>
                <label className="setting-field">
                  补零位数
                  <input type="number" value={sku.pad_width} onChange={(event) => setSku({ ...sku, pad_width: Number(event.target.value || 4) })} />
                </label>
                <label className="setting-field">
                  备注
                  <input value={sku.note || ""} onChange={(event) => setSku({ ...sku, note: event.target.value })} />
                </label>
              </div>
              <section className="sub-panel">
                <h3>编号变更记录</h3>
                <div className="setting-table">
                  {(sku.change_logs || []).map((log) => (
                    <div className="setting-table-row" key={log.id}>
                      <div>
                        <strong>{`${log.old_code} -> ${log.new_code}`}</strong>
                        <span>{log.note || "无备注"}</span>
                      </div>
                      <span>{log.created_at}</span>
                    </div>
                  ))}
                </div>
              </section>
              <SaveBar text="只控制后续新建商品和泡袋上传脚本的自动编号，不改历史 SKU。" onSave={saveSku} />
            </>
          ) : null}
        </Tabs.Content>

        <Tabs.Content value="product" className="tab-content settings-content">
          <div className="split-grid">
            <section className="sub-panel">
              <h3>分类管理</h3>
              <CategoryRows categories={productCategories} />
            </section>
            <section className="sub-panel">
              <h3>基础选项</h3>
              <ListEditor
                label="单位"
                values={asArray(productValue.units)}
                placeholder="例如：套"
                onChange={(values) => patchSetting("product_basic", { units: values })}
              />
              <ListEditor
                label="泡袋版型"
                values={asArray(productValue.bag_types)}
                placeholder="例如：短泡袋"
                onChange={(values) => patchSetting("product_basic", { bag_types: values })}
              />
              <div className="settings-grid two">
                <label className="setting-field">
                  默认件规
                  <input value={fieldValue(productValue.default_case_pack_qty)} placeholder="例如 20" onChange={(event) => patchSetting("product_basic", { default_case_pack_qty: event.target.value })} />
                </label>
                <label className="setting-field">
                  默认单位
                  <select value={fieldValue(productValue.default_unit) || "套"} onChange={(event) => patchSetting("product_basic", { default_unit: event.target.value })}>
                    {asArray(productValue.units).map((unit) => <option key={unit} value={unit}>{unit}</option>)}
                  </select>
                </label>
              </div>
            </section>
          </div>
          <SaveBar text="分类是否扣库存按后端规则和商品分类保存，泡袋固定不扣库存。" onSave={() => saveSystem("product_basic")} />
        </Tabs.Content>

        <Tabs.Content value="inventory" className="tab-content settings-content">
          <div className="split-grid">
            <section className="sub-panel">
              <h3>固定库存规则</h3>
              <div className="rule-box">
                <strong>泡袋、茶袋、标签、服务、设计、制版、辅料固定不扣库存。</strong>
                <span>这条规则由服务层保护，设置页不提供反向开关。</span>
              </div>
              <h4>扣库存分类</h4>
              <CategoryRows categories={fixedRuleGroups.stock} />
              <h4>不扣库存分类</h4>
              <CategoryRows categories={fixedRuleGroups.nonStock} />
            </section>
            <section className="sub-panel">
              <h3>出库默认项</h3>
              <label className="setting-field">
                默认出库仓库
                <select
                  value={Number(inventoryValue.default_out_warehouse_id || 0)}
                  onChange={(event) => patchSetting("inventory_rules", { default_out_warehouse_id: Number(event.target.value) })}
                >
                  {allWarehouses.map((warehouse) => (
                    <option value={warehouse.id} key={warehouse.id}>{warehouse.name}</option>
                  ))}
                </select>
              </label>
              <SwitchField
                label="允许负库存开单"
                checked={Number(inventoryValue.allow_negative_stock || 0) === 1}
                onChange={(checked) => patchSetting("inventory_rules", { allow_negative_stock: checked ? 1 : 0 })}
              />
            </section>
          </div>
          <SaveBar text="保存后只更新默认仓库和负库存规则，固定不扣库存关键词由服务层兜住。" onSave={() => saveSystem("inventory_rules")} />
        </Tabs.Content>

        <Tabs.Content value="payment" className="tab-content settings-content">
          <div className="settings-grid two">
            <ListEditor
              label="付款状态"
              values={asArray(paymentValue.payment_statuses)}
              placeholder="例如：已付"
              onChange={(values) => patchSetting("payment_rules", { payment_statuses: values })}
            />
            <ListEditor
              label="已付方式"
              values={asArray(paymentValue.paid_methods)}
              placeholder="例如：微信"
              onChange={(values) => patchSetting("payment_rules", { paid_methods: values })}
            />
            <label className="setting-field">
              默认结款状态
              <select value={fieldValue(paymentValue.default_payment_status)} onChange={(event) => patchSetting("payment_rules", { default_payment_status: event.target.value })}>
                {asArray(paymentValue.payment_statuses).map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="setting-field">
              默认已付方式
              <select value={fieldValue(paymentValue.default_paid_method)} onChange={(event) => patchSetting("payment_rules", { default_paid_method: event.target.value })}>
                {asArray(paymentValue.paid_methods).map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
          </div>
          <ListEditor
            label="余额调整原因"
            values={asArray(paymentValue.balance_adjust_reasons)}
            placeholder="例如：对账修正"
            onChange={(values) => patchSetting("payment_rules", { balance_adjust_reasons: values })}
          />
          <label className="setting-field">
            月结说明
            <input value={fieldValue(paymentValue.monthly_customer_rule)} onChange={(event) => patchSetting("payment_rules", { monthly_customer_rule: event.target.value })} />
          </label>
          <SaveBar text="普通客户默认已付；月结客户由客户资料开关自动识别。" onSave={() => saveSystem("payment_rules")} />
        </Tabs.Content>

        <Tabs.Content value="image" className="tab-content settings-content">
          <MediaSummaryCards summary={imageSummary} />
          <div className="settings-grid two">
            <label className="setting-field">
              OSS 上传路径
              <input value={fieldValue(imageValue.oss_path)} onChange={(event) => patchSetting("image_rules", { oss_path: event.target.value })} />
            </label>
            <label className="setting-field">
              缩略图规则
              <input value={fieldValue(imageValue.thumbnail_rule)} onChange={(event) => patchSetting("image_rules", { thumbnail_rule: event.target.value })} />
            </label>
            <label className="setting-field">
              待绑定清理天数
              <input type="number" value={Number(imageValue.pending_cleanup_days || 30)} onChange={(event) => patchSetting("image_rules", { pending_cleanup_days: Number(event.target.value || 30) })} />
            </label>
            <SwitchField
              label="上传后自动压缩"
              checked={Number(imageValue.auto_compress || 0) === 1}
              onChange={(checked) => patchSetting("image_rules", { auto_compress: checked ? 1 : 0 })}
            />
          </div>
          <label className="setting-field">
            图片资产分类规则
            <input value={fieldValue(imageValue.asset_category_rule)} onChange={(event) => patchSetting("image_rules", { asset_category_rule: event.target.value })} />
          </label>
          <SaveBar text="图片资产页继续按 SPU、大分类、角色分组；这里只设置上传和缩略图规则。" onSave={() => saveSystem("image_rules")} />
        </Tabs.Content>

        <Tabs.Content value="users" className="tab-content settings-content">
          <div className="inline-form user-search">
            <input value={userKeyword} placeholder="搜索账号、姓名、电话" onChange={(event) => setUserKeyword(event.target.value)} />
            <button type="button" className="ghost-action compact" onClick={() => loadAll(userKeyword)}>
              <Search size={16} />
              搜索
            </button>
          </div>
          <div className="user-list">
            {users.map((user) => (
              <div className="user-row" key={user.id}>
                <div>
                  <strong>{user.display_name || user.account_display || user.username}</strong>
                  <span>{[user.account_display || user.username, user.phone, user.party_name].filter(Boolean).join(" · ") || `ID ${user.id}`}</span>
                </div>
                <div className="role-buttons">
                  {roleOptions.map((role) => (
                    <button key={role.value} type="button" className={user.role === role.value ? "active" : ""} onClick={() => updateUser(user, { role: role.value })}>
                      {role.label}
                    </button>
                  ))}
                </div>
                <button type="button" className={`status-toggle ${Number(user.is_active || 0) ? "active" : ""}`} onClick={() => updateUser(user, { is_active: Number(user.is_active || 0) ? 0 : 1 })}>
                  {Number(user.is_active || 0) ? <Check size={16} /> : <X size={16} />}
                  {Number(user.is_active || 0) ? "已启用" : "已停用"}
                </button>
              </div>
            ))}
          </div>
        </Tabs.Content>

        <Tabs.Content value="print" className="tab-content settings-content">
          {print ? (
            <>
              <div className="settings-grid two">
                <label className="setting-field">
                  模板名称
                  <input value={print.name || ""} onChange={(event) => setPrint({ ...print, name: event.target.value })} />
                </label>
                <label className="setting-field">
                  标题
                  <input value={print.header_text || ""} onChange={(event) => setPrint({ ...print, header_text: event.target.value })} />
                </label>
                <label className="setting-field">
                  纸张
                  <select value={print.paper_size || "A5"} onChange={(event) => setPrint({ ...print, paper_size: event.target.value })}>
                    <option value="A5">A5</option>
                    <option value="A4">A4</option>
                    <option value="80MM">80mm</option>
                  </select>
                </label>
                <label className="setting-field">
                  方向
                  <select value={print.orientation || "landscape"} onChange={(event) => setPrint({ ...print, orientation: event.target.value })}>
                    <option value="landscape">横向</option>
                    <option value="portrait">竖向</option>
                  </select>
                </label>
                <label className="setting-field">
                  字号
                  <input type="number" value={print.font_size || 12} onChange={(event) => setPrint({ ...print, font_size: Number(event.target.value || 12) })} />
                </label>
                <label className="setting-field">
                  份数
                  <input type="number" value={print.copies || 1} onChange={(event) => setPrint({ ...print, copies: Number(event.target.value || 1) })} />
                </label>
              </div>
              <div className="toggle-grid">
                <SwitchField label="显示开单人" checked={Number(print.show_operator || 0) === 1} onChange={(checked) => setPrint({ ...print, show_operator: checked ? 1 : 0 })} />
                <SwitchField label="显示客户电话" checked={Number(print.show_customer_phone || 0) === 1} onChange={(checked) => setPrint({ ...print, show_customer_phone: checked ? 1 : 0 })} />
                <SwitchField label="显示付款状态" checked={Number(print.show_payment || 0) === 1} onChange={(checked) => setPrint({ ...print, show_payment: checked ? 1 : 0 })} />
                <SwitchField label="显示备注" checked={Number(print.show_note || 0) === 1} onChange={(checked) => setPrint({ ...print, show_note: checked ? 1 : 0 })} />
              </div>
              <label className="setting-field">
                底部文字
                <input value={print.footer_text || ""} onChange={(event) => setPrint({ ...print, footer_text: event.target.value })} />
              </label>
              <SaveBar text={print.latest_sales_no ? `可预览最近销售单：${print.latest_sales_no}` : "还没有可预览的销售单"} onSave={savePrint} />
            </>
          ) : null}
        </Tabs.Content>
      </Tabs.Root>
    </section>
  );
}

function MediaSummaryCards({ summary }: { summary?: MediaSummary }) {
  const items = [
    ["全部图片", summary?.total ?? "-"],
    ["待绑定", summary?.pending ?? "-"],
    ["主图", summary?.main ?? "-"],
    ["详情页", summary?.detail ?? "-"],
    ["颜色图", summary?.color ?? "-"]
  ];
  return (
    <div className="metric-grid five">
      {items.map(([label, value]) => (
        <div className="metric-card compact-card" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}
