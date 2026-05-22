const $ = (id) => document.getElementById(id);

const LIST_LIMITS = {
  sales: 80,
  workflow: 100,
  inventory: 160,
  products: 120,
  customers: 200,
  choice: 20,
  context: 1
};

const state = {
  sessionId: localStorage.getItem("sj_web_session_id") || newSessionId(),
  pendingFile: null,
  isSending: false,
  session: {},
  lastSalesCards: [],
  salesPage: 1,
  salesPageSize: 15,
  salesTotal: 0,
  salesLoadedAt: 0,
  lastWorkflowCards: [],
  workflowPage: 1,
  workflowPageSize: 15,
  workflowTotal: 0,
  workflowLoadedAt: 0,
  workflowFilter: "active",
  lastInventoryCards: [],
  inventoryTab: "cards",
  lastInventoryRows: [],
  inventoryPage: 1,
  inventoryPageSize: 8,
  inventoryTotal: 0,
  customerTab: "customers",
  lastCustomers: [],
  customerPage: 1,
  customerPageSize: 50,
  customerTotal: 0,
  contextInventory: null,
  businessHistory: [],
  lastProducts: [],
  productPage: 1,
  productPageSize: 20,
  productTotal: 0,
  productCategoryId: "",
  productCategoryGroupKey: "",
  productCategories: [],
  productUnits: [],
  productMediaAssets: [],
  productAssets: [],
  productAssetView: "products",
  productAssetTab: "",
  productAssetGroup: "",
  productAssetProductGroups: [],
  productAssetDetailKey: "",
  productAssetPage: 1,
  productAssetPageSize: 80,
  productAssetTotal: 0,
  productAssetLastFilter: "",
  productAssetPickerTarget: null,
  productAssetPickerTab: "",
  productAssetPickerKeyword: "",
  productStatuses: [
    { value: 0, name: "正常" },
    { value: 1, name: "下架" },
    { value: 2, name: "停售" },
    { value: 3, name: "停产" }
  ],
  productUploadTarget: null,
  settingsTab: "number",
  printSettings: null,
  numberSettings: null,
  miniappDesignSettings: null,
  miniappDesignDraft: null,
  miniappSelectedIndex: 0,
  saleCustomer: null,
  saleProduct: null,
  saleProductGroups: [],
  saleProductResults: [],
  saleLines: [],
  lastSaleResult: null,
  saleSubmitting: false,
  moveProduct: null,
  moveProductResults: [],
  currentUser: null,
  drawerMode: null,
  lightboxImages: [],
  lightboxIndex: 0
};
localStorage.setItem("sj_web_session_id", state.sessionId);

function newSessionId() {
  return `web_${Date.now()}`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (m) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[m]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

function imageThumbUrl(url, width = 240) {
  const clean = String(url || "").trim();
  if (!clean || !/^https?:\/\//i.test(clean) || clean.includes("x-oss-process=")) return clean;
  let parsed;
  try {
    parsed = new URL(clean);
  } catch {
    return clean;
  }
  const host = parsed.hostname.toLowerCase();
  if (!host.includes("513sjbz.com") && !host.includes("aliyuncs.com")) return clean;
  const safeWidth = Math.max(80, Math.min(Number(width || 240), 1200));
  return `${clean}${clean.includes("?") ? "&" : "?"}x-oss-process=image/resize,w_${safeWidth}/quality,q_80`;
}

function lazyImageHtml(url, width = 240, alt = "") {
  const raw = String(url || "").trim();
  const src = imageThumbUrl(raw, width);
  return `<img src="${escapeAttr(src)}" data-full-src="${escapeAttr(raw)}" loading="lazy" decoding="async" alt="${escapeAttr(alt)}" onerror="this.onerror=null;this.src=this.dataset.fullSrc||this.src;">`;
}

function money(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? number.toFixed(2) : String(value || "0");
}

function quantityNumber(value) {
  const number = Number(value ?? 0);
  return Number.isFinite(number) ? number : 0;
}

function quantityText(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) return String(value ?? "0");
  return Number.isInteger(number) ? String(number) : String(Number(number.toFixed(3)));
}

function normalizeProducts(value) {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object") return [value];
  return [];
}

function normalizeList(res) {
  const data = res && res.data;
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.list)) return data.list;
  if (data && data.data && Array.isArray(data.data.list)) return data.data.list;
  if (res && Array.isArray(res.list)) return res.list;
  return [];
}

function query(params) {
  return Object.keys(params)
    .filter((key) => params[key] !== undefined && params[key] !== null && params[key] !== "")
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join("&");
}

function api(path, options = {}) {
  return fetch(path, {
    method: options.method || "GET",
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    body: options.body instanceof FormData ? options.body : (options.body ? JSON.stringify(options.body) : undefined)
  }).then(async (res) => {
    const text = await res.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { code: res.status, msg: text };
    }
    if (!res.ok || (data.code && Number(data.code) !== 0)) {
      if (res.status === 401 || Number(data.code) === 401) {
        window.location.href = "/login";
      }
      throw new Error(data.msg || `HTTP ${res.status}`);
    }
    return data;
  });
}

function toast(text, danger = false) {
  const el = $("toast");
  if (!el) return;
  el.textContent = text;
  el.style.background = danger ? "#d3544a" : "#17231f";
  el.classList.add("show");
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
}

function localKey() {
  return `new_${Date.now()}_${Math.floor(Math.random() * 10000)}`;
}

function htmlToImages(content) {
  const images = [];
  String(content || "").replace(/<img[^>]+src=["']([^"']+)["'][^>]*>/gi, (match, src) => {
    if (src && !images.includes(src)) images.push(src);
    return match;
  });
  return images;
}

function detailImagesToHtml(images) {
  return (images || []).filter(Boolean).map((url) => `<p><img src="${url}" /></p>`).join("");
}

function confirmDialog({ title = "确认操作", message = "", confirmText = "确认" } = {}) {
  return new Promise((resolve) => {
    let mask = $("confirmMask");
    if (!mask) {
      mask = document.createElement("div");
      mask.id = "confirmMask";
      mask.className = "confirm-mask";
      mask.innerHTML = `
        <div class="confirm-box" role="dialog" aria-modal="true">
          <h3 class="confirm-title" id="confirmTitle"></h3>
          <p class="confirm-message" id="confirmMessage"></p>
          <div class="confirm-actions">
            <button id="confirmCancel">取消</button>
            <button class="danger-confirm" id="confirmOk">确认</button>
          </div>
        </div>`;
      document.body.appendChild(mask);
    }
    $("confirmTitle").textContent = title;
    $("confirmMessage").textContent = message;
    $("confirmOk").textContent = confirmText;
    const cleanup = (value) => {
      mask.classList.remove("open");
      $("confirmCancel").onclick = null;
      $("confirmOk").onclick = null;
      mask.onclick = null;
      document.removeEventListener("keydown", onKey);
      resolve(value);
    };
    const onKey = (event) => {
      if (event.key === "Escape") cleanup(false);
    };
    $("confirmCancel").onclick = () => cleanup(false);
    $("confirmOk").onclick = () => cleanup(true);
    mask.onclick = (event) => {
      if (event.target === mask) cleanup(false);
    };
    document.addEventListener("keydown", onKey);
    requestAnimationFrame(() => mask.classList.add("open"));
  });
}

function setStatus(text) {
  const dot = document.querySelector(".status-dot");
  if (dot) dot.textContent = text;
  const status = $("lastAction");
  if (status) status.textContent = text;
}

function setupDom() {
  const messages = $("messages");
  if (messages) messages.innerHTML = "";

  const salesGrid = document.querySelector("#sales .section-grid");
  if (salesGrid) salesGrid.id = "salesList";

  const inventoryGrid = document.querySelector("#inventory .section-grid");
  if (inventoryGrid) inventoryGrid.id = "inventoryList";
  const inventoryHead = document.querySelector("#inventory .section-head");
  if (inventoryHead && !$("inventoryPager")) {
    const addButton = inventoryHead.querySelector("button.primary");
    if (addButton) {
      const group = document.createElement("div");
      group.style.display = "flex";
      group.style.alignItems = "center";
      group.style.gap = "12px";
      addButton.insertAdjacentElement("beforebegin", group);
      group.appendChild(document.createRange().createContextualFragment('<div id="inventoryPager" class="pager"></div>'));
      group.appendChild(addButton);
    } else {
      inventoryHead.insertAdjacentHTML("beforeend", '<div style="display:flex;align-items:center;gap:12px;"><div id="inventoryPager" class="pager"></div></div>');
    }
  }

  const productGrid = document.querySelector("#products .section-grid");
  if (productGrid) productGrid.id = "productList";
  const productHead = document.querySelector("#products .section-head");
  if (productHead && !$("productPager")) {
    const addButton = $("newProductButton") || productHead.querySelector("button.primary");
    if (addButton) {
      const group = document.createElement("div");
      group.style.display = "flex";
      group.style.alignItems = "center";
      group.style.gap = "12px";
      addButton.insertAdjacentElement("beforebegin", group);
      group.appendChild(document.createRange().createContextualFragment('<div id="productPager" class="pager"></div>'));
      group.appendChild(addButton);
    }
  }

  const ordersView = $("orders");
  if (ordersView && !$("workflowList")) {
    ordersView.querySelectorAll(".order-row").forEach((node) => node.remove());
    const grid = document.createElement("div");
    grid.id = "workflowList";
    grid.className = "section-grid";
    ordersView.appendChild(grid);
  }

  const customerGrid = document.querySelector("#customers .section-grid");
  if (customerGrid) customerGrid.id = "customerList";

  insertToolbar("sales", "salesKeyword", "搜索客户 / 商品 / 订单号", "salesSearchBtn");
  insertToolbar("orders", "workflowKeyword", "搜索客户 / 商品 / 电话", "workflowSearchBtn");
  insertToolbar("customers", "customerKeyword", "搜索客户 / 用户 / 电话", "customerSearchBtn");
  insertToolbar("inventory", "inventoryKeyword", "搜索礼盒 / 颜色", "inventorySearchBtn");
  insertToolbar("products", "productKeyword", "搜索商品关键词", "productSearchBtn");
  insertToolbar("product-assets", "assetKeyword", "搜索分类 / 产品 / 图片地址", "assetSearchBtn");

  setBadge("sales", "-");
  setBadge("orders", "-");
  setBadge("customers", "-");
  setBadge("inventory", "-");
  setBadge("products", "-");
  setBadge("product-assets", "-");
  setBadge("settings", "设");
}

function insertToolbar(viewId, inputId, placeholder, buttonId) {
  if ($(inputId)) return;
  const view = $(viewId);
  const head = view && view.querySelector(".section-head");
  if (!head) return;
  const toolbar = document.createElement("div");
  toolbar.className = "toolbar";
  toolbar.style.marginBottom = "14px";
  toolbar.innerHTML = `
    <input id="${inputId}" placeholder="${placeholder}">
    <button id="${buttonId}">搜索</button>
  `;
  head.insertAdjacentElement("afterend", toolbar);
  if (viewId === "orders" && !$("workflowFilterBar")) {
    toolbar.insertAdjacentHTML("beforeend", `
      <div class="segmented workflow-filter" id="workflowFilterBar">
        <button class="active" data-workflow-filter="active">默认</button>
        <button data-workflow-filter="unmade">未制作</button>
        <button data-workflow-filter="pending">未完成</button>
        <button data-workflow-filter="all">全部</button>
      </div>
    `);
  }
  if (viewId === "products" && !$("productCategoryBar")) {
    toolbar.insertAdjacentHTML("afterend", '<div id="productCategoryBar"></div>');
  }
}

function setBadge(view, value) {
  const button = document.querySelector(`[data-view="${view}"] .badge`);
  if (button) button.textContent = value;
}

function setView(name) {
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  document.querySelectorAll(".nav button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === name);
  });
  if (name === "sale-create") {
    setDefaultSaleCreateTime();
    if (state.saleCustomer) {
      refreshSaleCustomerMonthlyRule(state.saleCustomer.id, state.saleCustomer.name).catch((err) => console.warn("月结客户校验失败", err));
    }
    syncSalePaymentUi();
    renderSaleLines();
  }
  if (name === "sales" && !state.lastSalesCards.length) loadSales();
  if (name === "orders" && !state.lastWorkflowCards.length) loadWorkflow();
  if (name === "customers" && !state.lastCustomers.length) loadCustomers(1);
  if (name === "inventory" && !state.lastInventoryCards.length) loadInventory();
  if (name === "products" && !state.lastProducts.length) loadProducts();
  if (name === "product-assets") loadProductAssets();
  if (name === "settings") loadSettings();
  scheduleActiveListRefresh(name);
}

function checkedAttr(value) {
  return Number(value || 0) ? "checked" : "";
}

function setSettingsTab(tab = "print") {
  const validTabs = new Set(["number", "product", "inventory", "payment", "images", "miniapp", "users", "print"]);
  const clean = validTabs.has(tab) ? tab : "number";
  state.settingsTab = clean;
  document.querySelectorAll("[data-settings-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.settingsTab === clean);
  });
  const panelMap = {
    number: "numberSettingsPanel",
    product: "productSettingsPanel",
    inventory: "inventorySettingsPanel",
    payment: "paymentSettingsPanel",
    images: "imageSettingsPanel",
    miniapp: "miniappSettingsPanel",
    users: "userSettingsPanel",
    print: "printSettingsPanel"
  };
  Object.entries(panelMap).forEach(([key, id]) => {
    const panel = $(id);
    if (panel) panel.hidden = key !== clean;
  });
  if (clean === "number") loadNumberSettings();
  else if (clean === "product") loadProductBasicSettings();
  else if (clean === "inventory") loadInventoryRuleSettings();
  else if (clean === "payment") loadPaymentRuleSettings();
  else if (clean === "miniapp") loadMiniappDesignSettings();
  else if (clean === "users") loadPermissionSettings();
  else if (clean === "images") loadImageSettings();
  else loadPrintSettings();
}

function loadSettings() {
  setSettingsTab(state.settingsTab || "number");
}

async function loadPrintSettings() {
  const panel = $("printSettingsPanel");
  if (!panel) return;
  if (!state.printSettings) panel.innerHTML = '<div class="empty">正在加载打印设置</div>';
  try {
    const res = await api("/api/settings/print/sales");
    state.printSettings = (res && res.data) || {};
    renderPrintSettings(state.printSettings);
  } catch (err) {
    panel.innerHTML = `<div class="empty">打印设置加载失败：${escapeHtml(err.message)}</div>`;
  }
}

function renderPrintSettings(settings = {}) {
  const panel = $("printSettingsPanel");
  if (!panel) return;
  const latestText = settings.latest_sales_no
    ? `最近一张销售单：${escapeHtml(settings.latest_sales_no)}`
    : "还没有可预览的销售单";
  panel.innerHTML = `
    <section class="settings-panel">
      <div class="settings-panel-head">
        <div>
          <h3>销售单打印模板</h3>
          <p>这里只设置销售单打印，进货单、采购单这些先不做。</p>
        </div>
        <span class="tag green-outline">${latestText}</span>
      </div>
      <div class="settings-grid">
        <label class="setting-field">模板名称
          <input id="printTemplateName" value="${escapeAttr(settings.name || "默认销售单模板")}">
        </label>
        <label class="setting-field">标题
          <input id="printHeaderText" value="${escapeAttr(settings.header_text || "肆计包装销售单")}">
        </label>
        <label class="setting-field">纸张
          <select id="printPaperSize">
            <option value="A4" ${settings.paper_size === "A4" ? "selected" : ""}>A4</option>
            <option value="A5" ${settings.paper_size === "A5" ? "selected" : ""}>A5</option>
            <option value="80mm" ${settings.paper_size === "80mm" ? "selected" : ""}>80mm 小票</option>
          </select>
        </label>
        <label class="setting-field">方向
          <select id="printOrientation">
            <option value="portrait" ${settings.orientation !== "landscape" ? "selected" : ""}>竖向</option>
            <option value="landscape" ${settings.orientation === "landscape" ? "selected" : ""}>横向</option>
          </select>
        </label>
        <label class="setting-field">字号
          <input id="printFontSize" type="number" min="10" max="18" value="${escapeAttr(settings.font_size || 12)}">
        </label>
        <label class="setting-field">打印份数
          <input id="printCopies" type="number" min="1" max="5" value="${escapeAttr(settings.copies || 1)}">
        </label>
        <div class="setting-field full">
          <span>显示内容</span>
          <div class="print-toggle-grid">
            <label class="print-toggle"><input id="printShowOperator" type="checkbox" ${checkedAttr(settings.show_operator)}> 开单人</label>
            <label class="print-toggle"><input id="printShowCustomerPhone" type="checkbox" ${checkedAttr(settings.show_customer_phone)}> 客户电话</label>
            <label class="print-toggle"><input id="printShowPayment" type="checkbox" ${checkedAttr(settings.show_payment)}> 付款状态</label>
            <label class="print-toggle"><input id="printShowNote" type="checkbox" ${checkedAttr(settings.show_note)}> 备注</label>
          </div>
        </div>
        <label class="setting-field full">底部文字
          <textarea id="printFooterText">${escapeHtml(settings.footer_text || "")}</textarea>
        </label>
        <label class="setting-field full">模板样式
          <textarea id="printCustomCss" placeholder="可选：写一点打印页 CSS">${escapeHtml(settings.custom_css || "")}</textarea>
        </label>
      </div>
      <div class="print-template-note">销售单打印页现在由 sjagent_core 数据生成。点销售单上的“打印”只创建打印任务，AI 打印也走同一条队列；预览按钮才会打开页面。</div>
      <div class="print-settings-actions">
        <button id="previewPrintSettings" type="button">预览最近销售单</button>
        <button class="primary" id="savePrintSettings" type="button">保存设置</button>
      </div>
    </section>`;
}

function collectPrintSettings() {
  return {
    name: $("printTemplateName") ? $("printTemplateName").value : "",
    header_text: $("printHeaderText") ? $("printHeaderText").value : "",
    paper_size: $("printPaperSize") ? $("printPaperSize").value : "A4",
    orientation: $("printOrientation") ? $("printOrientation").value : "portrait",
    font_size: $("printFontSize") ? Number($("printFontSize").value || 12) : 12,
    copies: $("printCopies") ? Number($("printCopies").value || 1) : 1,
    show_operator: $("printShowOperator") && $("printShowOperator").checked ? 1 : 0,
    show_customer_phone: $("printShowCustomerPhone") && $("printShowCustomerPhone").checked ? 1 : 0,
    show_payment: $("printShowPayment") && $("printShowPayment").checked ? 1 : 0,
    show_note: $("printShowNote") && $("printShowNote").checked ? 1 : 0,
    footer_text: $("printFooterText") ? $("printFooterText").value : "",
    custom_css: $("printCustomCss") ? $("printCustomCss").value : ""
  };
}

async function savePrintSettings() {
  const button = $("savePrintSettings");
  if (button) { button.classList.add("loading"); button.textContent = "保存中"; }
  try {
    const res = await api("/api/settings/print/sales", { method: "POST", body: collectPrintSettings() });
    state.printSettings = (res && res.data) || {};
    renderPrintSettings(state.printSettings);
    toast("打印设置已保存");
  } finally {
    const nextButton = $("savePrintSettings");
    if (nextButton) { nextButton.classList.remove("loading"); nextButton.textContent = "保存设置"; }
  }
}

function previewPrintSettings() {
  const salesId = state.printSettings && state.printSettings.latest_sales_id;
  if (!salesId) return toast("还没有可预览的销售单", true);
  window.open(`/api/sales/${encodeURIComponent(salesId)}/print-html?auto=0`, "_blank", "noopener");
}

function settingListText(value) {
  if (Array.isArray(value)) return value.join("\n");
  return String(value || "");
}

function settingListValue(id) {
  const el = $(id);
  return String(el ? el.value : "")
    .split(/[\n,，、]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function checkedValue(id) {
  const el = $(id);
  return el && el.checked ? 1 : 0;
}

function settingRowValue(row, selector = "input") {
  const el = row.querySelector(selector);
  return el ? String(el.value || "").trim() : "";
}

function settingTextRowHtml(kind, value = "", { placeholder = "名称", removable = true, meta = "" } = {}) {
  return `<div class="setting-row two" data-setting-row="${escapeAttr(kind)}">
    <input value="${escapeAttr(value)}" placeholder="${escapeAttr(placeholder)}">
    ${meta ? `<span class="tag">${escapeHtml(meta)}</span>` : ""}
    ${removable ? `<button type="button" class="setting-delete" data-remove-setting-row title="删除">×</button>` : ""}
  </div>`;
}

function settingCategoryRowHtml(item = {}, index = 0) {
  const name = String(item.name || item.key || "");
  const type = String(item.product_type || item.key || "").toLowerCase();
  const fixedNoStock = type === "bag" || /泡袋|茶袋/.test(name);
  const stock = fixedNoStock ? false : Number(item.is_stock_item ?? item.stock ?? 1) === 1;
  return `<div class="setting-row" data-setting-row="product-category">
    <input class="setting-category-name" value="${escapeAttr(name)}" placeholder="分类名称">
    ${fixedNoStock ? '<span class="tag green-outline">固定不扣库存</span>' : `<div class="setting-segment" data-stock-toggle>
      <button type="button" class="${stock ? "active" : ""}" data-stock-value="1">扣库存</button>
      <button type="button" class="${!stock ? "active" : ""}" data-stock-value="0">不扣库存</button>
    </div>`}
    <button type="button" class="setting-delete" data-remove-setting-row title="删除">×</button>
  </div>`;
}

function settingPaymentRowHtml(kind, value = "", currentDefault = "") {
  const safeValue = String(value || "").trim();
  return `<div class="setting-row" data-setting-row="${escapeAttr(kind)}">
    <input value="${escapeAttr(safeValue)}" placeholder="选项名称">
    <label class="setting-radio"><input type="radio" name="${escapeAttr(kind)}Default" ${safeValue === currentDefault ? "checked" : ""}>默认</label>
    <button type="button" class="setting-delete" data-remove-setting-row title="删除">×</button>
  </div>`;
}

function settingRowsValues(containerId) {
  const container = $(containerId);
  if (!container) return [];
  return Array.from(container.querySelectorAll("[data-setting-row]"))
    .map((row) => settingRowValue(row))
    .filter(Boolean);
}

function appendSettingRow(containerId, html) {
  const container = $(containerId);
  if (!container) return;
  container.insertAdjacentHTML("beforeend", html);
  const input = container.querySelector("[data-setting-row]:last-child input");
  if (input) input.focus();
}

function addSettingRow(kind) {
  const map = {
    "product-category": ["productCategorySettingRows", settingCategoryRowHtml({ name: "", is_stock_item: 1 })],
    "product-unit": ["productUnitSettingRows", settingTextRowHtml("product-unit", "", { placeholder: "单位名称" })],
    "bag-type": ["bagTypeSettingRows", settingTextRowHtml("bag-type", "", { placeholder: "版型名称" })],
    "payment-status": ["paymentStatusRows", settingPaymentRowHtml("payment-status", "")],
    "payment-method": ["paymentMethodRows", settingPaymentRowHtml("payment-method", "")],
    "balance-reason": ["balanceReasonRows", settingTextRowHtml("balance-reason", "", { placeholder: "原因名称" })]
  };
  const target = map[kind];
  if (!target) return;
  appendSettingRow(target[0], target[1]);
}

function toggleSettingSegment(button) {
  const segment = button.closest("[data-stock-toggle]");
  if (!segment) return;
  segment.querySelectorAll("[data-stock-value]").forEach((item) => item.classList.toggle("active", item === button));
}

async function loadSystemSetting(key, panelId, renderer, force = false) {
  const panel = $(panelId);
  if (!panel) return;
  if (force || !panel.dataset.loaded) panel.innerHTML = `<div class="empty">正在加载设置</div>`;
  try {
    const res = await api(`/api/settings/system/${encodeURIComponent(key)}`);
    panel.dataset.loaded = "1";
    renderer((res && res.data) || {});
  } catch (err) {
    panel.innerHTML = `<div class="empty">设置加载失败：${escapeHtml(err.message)}</div>`;
  }
}

async function saveSystemSetting(key, body, reload) {
  await api(`/api/settings/system/${encodeURIComponent(key)}`, { method: "POST", body });
  toast("设置已保存");
  if (typeof reload === "function") await reload(true);
}

async function loadNumberSettings(force = false) {
  const panel = $("numberSettingsPanel");
  if (!panel) return;
  if (!state.numberSettings || force) panel.innerHTML = '<div class="empty">正在加载编号设置</div>';
  try {
    const res = await api("/api/settings/number/sku");
    state.numberSettings = (res && res.data) || {};
    renderNumberSettings(state.numberSettings);
  } catch (err) {
    panel.innerHTML = `<div class="empty">编号设置加载失败：${escapeHtml(err.message)}</div>`;
  }
}

function renderSettingsLogRows(rows = [], emptyText = "暂无记录") {
  if (!rows.length) return `<div class="empty">${emptyText}</div>`;
  return rows.map((row) => {
    const title = row.batch_no
      ? `${escapeHtml(row.batch_no)} · ${Number(row.changed_count || 0)} 个商品`
      : `${escapeHtml(row.old_code || "-")} → ${escapeHtml(row.new_code || "-")}`;
    const detail = row.batch_no
      ? `${escapeHtml(row.first_new_code || "-")} 到 ${escapeHtml(row.last_new_code || "-")} · ${escapeHtml(row.finished_at || "")}`
      : `${escapeHtml(row.note || "手动调整")} · ${escapeHtml(row.created_at || "")}`;
    return `
      <div class="settings-log-row">
        <div><strong>${title}</strong><small>${detail}</small></div>
        <span class="tag">${row.batch_no ? "重编码" : "设置"}</span>
      </div>`;
  }).join("");
}

function renderNumberSettings(settings = {}) {
  const panel = $("numberSettingsPanel");
  if (!panel) return;
  const nextCode = settings.next_code || settings.configured_code || "SJ1001";
  panel.innerHTML = `
    <section class="settings-panel">
      <div class="settings-panel-head">
        <div>
          <h3>商品编号设置</h3>
          <p>只控制后续新建商品、泡袋上传脚本的自动编号，不改历史 SKU。</p>
        </div>
        <span class="tag green-outline">下一个可用：${escapeHtml(nextCode)}</span>
      </div>
      <div class="settings-summary-grid">
        <div class="setting-stat"><span>下一个可用编号</span><strong>${escapeHtml(nextCode)}</strong></div>
        <div class="setting-stat"><span>起始编号</span><strong>${escapeHtml(settings.start_code || "SJ1001")}</strong></div>
        <div class="setting-stat"><span>手动下一号</span><strong>${escapeHtml(settings.configured_code || "SJ1570")}</strong></div>
        <div class="setting-stat"><span>当前已用 SJ 编号</span><strong>${Number(settings.numeric_used_count || settings.used_count || 0)}</strong></div>
        <div class="setting-stat"><span>已用最大编号</span><strong>${escapeHtml(settings.used_max_code || "-")}</strong></div>
      </div>
      <div class="settings-grid">
        <label class="setting-field">编号前缀
          <input id="skuNumberPrefix" value="${escapeAttr(settings.prefix || "SJ")}">
        </label>
        <label class="setting-field">起始号
          <input id="skuStartNumber" type="number" min="1" value="${escapeAttr(settings.start_number || 1001)}">
        </label>
        <label class="setting-field">手动调整下一号
          <input id="skuNextCode" value="${escapeAttr(settings.next_code || settings.configured_code || "SJ1001")}" placeholder="SJ1570">
        </label>
        <label class="setting-field">补零位数
          <input id="skuPadWidth" type="number" min="1" max="10" value="${escapeAttr(settings.pad_width || 4)}">
        </label>
        <label class="setting-field">数据库商品数
          <input value="${escapeAttr(settings.total_sku_count || 0)}" disabled>
        </label>
        <label class="setting-field full">跳过号
          <textarea id="skuSkippedNumbers" placeholder="一行一个，例如 SJ0999 或 999">${escapeHtml(settings.skipped_numbers_text || "")}</textarea>
        </label>
        <label class="setting-field full">备注
          <textarea id="skuNumberNote" placeholder="例如：泡袋和礼盒统一从 SJ1570 往后走">${escapeHtml(settings.note || "")}</textarea>
        </label>
      </div>
      <div class="print-template-note">手动下一号是后续新商品的最低起点；跳过号会永远避开。保存不会重排旧商品。</div>
      <div class="print-settings-actions">
        <button id="refreshNumberSettings" type="button">刷新</button>
        <button class="primary" id="saveNumberSettings" type="button">保存编号设置</button>
      </div>
    </section>
    <section class="settings-panel">
      <div class="settings-panel-head">
        <div>
          <h3>编号记录</h3>
          <p>这里看最近的手动调整和上次重编码迁移记录。</p>
        </div>
      </div>
      <div class="settings-log-list">
        ${renderSettingsLogRows(settings.change_logs || [], "暂无手动调整记录")}
      </div>
      <div class="print-template-note">最近重编码批次</div>
      <div class="settings-log-list">
        ${renderSettingsLogRows(settings.recode_batches || [], "暂无重编码记录")}
      </div>
    </section>`;
}

function collectNumberSettings() {
  const nextCodeValue = $("skuNextCode") ? $("skuNextCode").value : "";
  const prefixValue = $("skuNumberPrefix") ? $("skuNumberPrefix").value : "SJ";
  return {
    prefix: prefixValue,
    next_code: nextCodeValue,
    start_number: $("skuStartNumber") ? Number($("skuStartNumber").value || 1001) : 1001,
    skipped_numbers: settingListValue("skuSkippedNumbers"),
    pad_width: $("skuPadWidth") ? Number($("skuPadWidth").value || 4) : 4,
    note: $("skuNumberNote") ? $("skuNumberNote").value : ""
  };
}

async function saveNumberSettings() {
  const button = $("saveNumberSettings");
  if (button) { button.classList.add("loading"); button.textContent = "保存中"; }
  try {
    const res = await api("/api/settings/number/sku", { method: "POST", body: collectNumberSettings() });
    state.numberSettings = (res && res.data) || {};
    renderNumberSettings(state.numberSettings);
    toast("编号设置已保存");
  } finally {
    const nextButton = $("saveNumberSettings");
    if (nextButton) { nextButton.classList.remove("loading"); nextButton.textContent = "保存编号设置"; }
  }
}

async function loadProductBasicSettings(force = false) {
  return loadSystemSetting("product_basic", "productSettingsPanel", renderProductBasicSettings, force);
}

function renderProductBasicSettings(data = {}) {
  const panel = $("productSettingsPanel");
  if (!panel) return;
  const value = data.value || {};
  const categories = value.categories || [];
  const units = value.units || [];
  const bagTypes = value.bag_types || [];
  panel.innerHTML = `
    <section class="settings-panel">
      <div class="settings-panel-head">
        <div>
          <h3>商品基础设置</h3>
          <p>分类、单位、泡袋版型和新建商品默认规则。</p>
        </div>
        <span class="tag green-outline">商品中心</span>
      </div>
      <div class="settings-summary-grid">
        <div class="setting-stat"><span>分类</span><strong>${categories.length}</strong></div>
        <div class="setting-stat"><span>单位</span><strong>${units.length}</strong></div>
        <div class="setting-stat"><span>泡袋版型</span><strong>${bagTypes.length}</strong></div>
      </div>
      <div class="settings-grid">
        <div class="setting-block full">
          <div class="setting-block-title"><span>分类管理</span><button type="button" data-add-setting-row="product-category">新增分类</button></div>
          <div class="setting-list" id="productCategorySettingRows">
            ${categories.map((item, index) => settingCategoryRowHtml(item, index)).join("")}
          </div>
        </div>
        <div class="setting-block">
          <div class="setting-block-title"><span>单位管理</span><button type="button" data-add-setting-row="product-unit">新增单位</button></div>
          <div class="setting-list" id="productUnitSettingRows">
            ${units.map((unit) => settingTextRowHtml("product-unit", unit, { placeholder: "单位名称" })).join("")}
          </div>
        </div>
        <div class="setting-block">
          <div class="setting-block-title"><span>泡袋版型</span><button type="button" data-add-setting-row="bag-type">新增版型</button></div>
          <div class="setting-list" id="bagTypeSettingRows">
            ${bagTypes.map((type) => settingTextRowHtml("bag-type", type, { placeholder: "版型名称" })).join("")}
          </div>
        </div>
        <label class="setting-field">默认件规
          <input id="productDefaultCasePack" value="${escapeAttr(value.default_case_pack_qty || "")}" placeholder="例如 20">
        </label>
        <label class="setting-field">默认单位
          <input id="productDefaultUnit" value="${escapeAttr(value.default_unit || "套")}">
        </label>
        <label class="print-toggle"><input id="productDefaultStockItem" type="checkbox" ${checkedAttr(value.default_is_stock_item)}> 新建商品默认扣库存</label>
      </div>
      <div class="print-template-note">分类的扣库存开关会影响后续新建商品默认库存规则，不需要手写格式。</div>
      <div class="print-settings-actions">
        <button class="primary" id="saveProductBasicSettings" type="button">保存商品基础设置</button>
      </div>
    </section>`;
}

function collectProductBasicSettings() {
  const categories = Array.from(document.querySelectorAll("#productCategorySettingRows [data-setting-row='product-category']"))
    .map((row, index) => {
      const name = settingRowValue(row, ".setting-category-name");
      if (!name) return null;
      const active = row.querySelector("[data-stock-value].active");
      const fixedNoStock = /泡袋|茶袋/.test(name);
      return { key: name, name, sort_order: index + 1, is_stock_item: fixedNoStock ? 0 : Number(active ? active.dataset.stockValue : 1) };
    })
    .filter(Boolean);
  return {
    categories,
    units: settingRowsValues("productUnitSettingRows"),
    bag_types: settingRowsValues("bagTypeSettingRows"),
    default_case_pack_qty: $("productDefaultCasePack") ? $("productDefaultCasePack").value : "",
    default_unit: $("productDefaultUnit") ? $("productDefaultUnit").value : "套",
    default_is_stock_item: checkedValue("productDefaultStockItem")
  };
}

async function loadInventoryRuleSettings(force = false) {
  return loadSystemSetting("inventory_rules", "inventorySettingsPanel", renderInventoryRuleSettings, force);
}

function warehouseOptions(warehouses = [], selected = "") {
  return warehouses.map((warehouse) => `<option value="${Number(warehouse.id || 0)}" ${Number(warehouse.id || 0) === Number(selected || 0) ? "selected" : ""}>${escapeHtml(warehouse.name || `仓库${warehouse.id}`)}</option>`).join("");
}

function fixedNoStockCategoryReason(category = {}) {
  const name = String(category.name || "");
  const type = String(category.product_type || "").toLowerCase();
  if (type === "bag" || /泡袋|茶袋/.test(name)) return "泡袋固定不扣库存";
  return "";
}

function renderInventoryRuleSettings(data = {}) {
  const panel = $("inventorySettingsPanel");
  if (!panel) return;
  const value = data.value || {};
  const warehouses = data.warehouses || [];
  const categories = (data.categories || []).filter((category) => Number(category.id || 0) > 0);
  const nonStockIds = new Set((value.non_stock_category_ids || []).map((id) => Number(id)));
  const stockIds = new Set((value.stock_category_ids || []).map((id) => Number(id)));
  const nonStockKeywords = value.non_stock_category_keywords || [];
  const categoryRows = categories.map((category) => {
    const id = Number(category.id || 0);
    const name = category.name || `分类${id}`;
    const fixedReason = fixedNoStockCategoryReason(category);
    const keywordNoStock = nonStockKeywords.some((word) => word && name.includes(word));
    const tracksStock = fixedReason ? false : (stockIds.has(id) ? true : (nonStockIds.has(id) || keywordNoStock ? false : true));
    return `<div class="setting-row" data-inventory-category-id="${id}" data-inventory-category-name="${escapeAttr(name)}" ${fixedReason ? 'data-fixed-non-stock="1"' : ""}>
      <div class="setting-row-name"><strong>${escapeHtml(name)}</strong><span>${Number(category.total || 0)} 个商品</span></div>
      ${fixedReason ? `<span class="tag green-outline">${escapeHtml(fixedReason)}</span>` : `<div class="setting-segment" data-stock-toggle>
        <button type="button" class="${tracksStock ? "active" : ""}" data-stock-value="1">扣库存</button>
        <button type="button" class="${!tracksStock ? "active" : ""}" data-stock-value="0">不扣库存</button>
      </div>`}
    </div>`;
  }).join("");
  panel.innerHTML = `
    <section class="settings-panel">
      <div class="settings-panel-head">
        <div>
          <h3>库存规则设置</h3>
          <p>礼盒、纸箱等按库存扣减；泡袋按业务规则固定不扣库存。</p>
        </div>
        <span class="tag green-outline">${Number(value.allow_negative_stock || 0) ? "允许负库存" : "不允许负库存"}</span>
      </div>
      <div class="settings-grid">
        <div class="setting-block full">
          <div class="setting-block-title"><span>分类库存规则</span><span>泡袋不提供开关，固定不扣库存</span></div>
          <div class="setting-list" id="inventoryCategoryRuleRows">${categoryRows || '<div class="empty">暂无分类</div>'}</div>
        </div>
        <label class="setting-field">默认出库仓库
          <select id="inventoryDefaultWarehouse">${warehouseOptions(warehouses, value.default_out_warehouse_id)}</select>
        </label>
        <label class="print-toggle"><input id="inventoryAllowNegative" type="checkbox" ${checkedAttr(value.allow_negative_stock)}> 允许负库存开单</label>
      </div>
      <div class="print-template-note">保存后，新建商品会按分类默认是否扣库存；销售开单会使用默认出库仓库和负库存规则。</div>
      <div class="print-settings-actions">
        <button class="primary" id="saveInventoryRuleSettings" type="button">保存库存规则</button>
      </div>
    </section>`;
}

function collectInventoryRuleSettings() {
  const rows = Array.from(document.querySelectorAll("#inventoryCategoryRuleRows [data-inventory-category-id]"));
  const stockIds = [];
  const nonStockIds = [];
  const stockNames = [];
  const nonStockNames = [];
  rows.forEach((row) => {
    const id = Number(row.dataset.inventoryCategoryId || 0);
    const name = row.dataset.inventoryCategoryName || "";
    const active = row.querySelector("[data-stock-value].active");
    const stock = row.dataset.fixedNonStock === "1" ? false : Number(active ? active.dataset.stockValue : 1) === 1;
    if (stock) {
      stockIds.push(id);
      if (name) stockNames.push(name);
    } else {
      nonStockIds.push(id);
      if (name) nonStockNames.push(name);
    }
  });
  return {
    stock_category_ids: stockIds,
    non_stock_category_ids: nonStockIds,
    stock_category_keywords: stockNames,
    non_stock_category_keywords: nonStockNames,
    default_out_warehouse_id: $("inventoryDefaultWarehouse") ? Number($("inventoryDefaultWarehouse").value || 0) : 0,
    allow_negative_stock: checkedValue("inventoryAllowNegative")
  };
}

async function loadPaymentRuleSettings(force = false) {
  return loadSystemSetting("payment_rules", "paymentSettingsPanel", renderPaymentRuleSettings, force);
}

function renderPaymentRuleSettings(data = {}) {
  const panel = $("paymentSettingsPanel");
  if (!panel) return;
  const value = data.value || {};
  const statuses = value.payment_statuses || [];
  const methods = value.paid_methods || [];
  const reasons = value.balance_adjust_reasons || [];
  const monthlyRule = value.monthly_customer_rule || "客户选择月结时销售单计入欠款，结款后改为已付。";
  panel.innerHTML = `
    <section class="settings-panel">
      <div class="settings-panel-head">
        <div>
          <h3>收款 / 结款设置</h3>
          <p>付款状态、默认收款方式、余额调整原因和月结说明。</p>
        </div>
        <span class="tag green-outline">${escapeHtml(value.default_payment_status || "已付")}</span>
      </div>
      <div class="settings-grid">
        <div class="setting-block">
          <div class="setting-block-title"><span>付款状态</span><button type="button" data-add-setting-row="payment-status">新增状态</button></div>
          <div class="setting-list" id="paymentStatusRows">
            ${statuses.map((item) => settingPaymentRowHtml("payment-status", item, value.default_payment_status || "已付")).join("")}
          </div>
        </div>
        <div class="setting-block">
          <div class="setting-block-title"><span>已付方式</span><button type="button" data-add-setting-row="payment-method">新增方式</button></div>
          <div class="setting-list" id="paymentMethodRows">
            ${methods.map((item) => settingPaymentRowHtml("payment-method", item, value.default_paid_method || "微信")).join("")}
          </div>
        </div>
        <div class="setting-block full">
          <div class="setting-block-title"><span>余额调整原因模板</span><button type="button" data-add-setting-row="balance-reason">新增原因</button></div>
          <div class="setting-list" id="balanceReasonRows">
            ${reasons.map((item) => settingTextRowHtml("balance-reason", item, { placeholder: "原因名称" })).join("")}
          </div>
        </div>
        <div class="setting-block full">
          <div class="setting-block-title"><span>月结客户规则</span><span>固定业务流程</span></div>
          <div class="setting-rule-card">
            <strong>月结销售单计入客户欠款</strong>
            <span>${escapeHtml(monthlyRule)}</span>
            <input id="paymentMonthlyRule" type="hidden" value="${escapeAttr(monthlyRule)}">
          </div>
        </div>
      </div>
      <div class="print-settings-actions">
        <button class="primary" id="savePaymentRuleSettings" type="button">保存收款结款设置</button>
      </div>
    </section>`;
}

function collectPaymentRuleSettings() {
  const statuses = settingRowsValues("paymentStatusRows");
  const methods = settingRowsValues("paymentMethodRows");
  const defaultStatusRow = document.querySelector("#paymentStatusRows input[type='radio']:checked");
  const defaultMethodRow = document.querySelector("#paymentMethodRows input[type='radio']:checked");
  return {
    payment_statuses: statuses,
    paid_methods: methods,
    default_payment_status: defaultStatusRow ? settingRowValue(defaultStatusRow.closest("[data-setting-row]")) : (statuses[0] || "已付"),
    default_paid_method: defaultMethodRow ? settingRowValue(defaultMethodRow.closest("[data-setting-row]")) : (methods[0] || "微信"),
    balance_adjust_reasons: settingRowsValues("balanceReasonRows"),
    monthly_customer_rule: $("paymentMonthlyRule") ? $("paymentMonthlyRule").value : ""
  };
}

async function loadPermissionSettings(force = false) {
  const panel = $("userSettingsPanel");
  if (!panel) return;
  if (force || !panel.dataset.loaded) panel.innerHTML = '<div class="empty">正在加载用户权限</div>';
  try {
    const res = await api(`/api/users?${query({ page: 1, page_size: 200 })}`);
    const list = normalizeList(res);
    panel.dataset.loaded = "1";
    renderPermissionSettings(list, (res.data && res.data.total) || list.length);
  } catch (err) {
    panel.innerHTML = `<div class="empty">用户权限加载失败：${escapeHtml(err.message)}</div>`;
  }
}

const roleCodeByLabel = {
  "管理员": "admin",
  "老板": "admin",
  "员工": "staff",
  "客户": "customer",
  "访客": "guest"
};
const roleLabelByCode = {
  admin: "管理员",
  staff: "员工",
  warehouse: "员工",
  designer: "员工",
  readonly: "访客",
  customer: "客户",
  guest: "访客"
};

function roleCode(labelOrCode) {
  const value = String(labelOrCode || "").trim();
  return roleCodeByLabel[value] || value;
}

function roleLabel(value) {
  const clean = String(value || "").trim();
  return roleLabelByCode[clean] || clean || "未设置";
}

function userRoleOptionsFromRules() {
  return [
    ["admin", "管理员"],
    ["staff", "员工"],
    ["customer", "客户"],
    ["guest", "访客"]
  ];
}

function renderPermissionSettings(list = [], total = 0) {
  const panel = $("userSettingsPanel");
  if (!panel) return;
  const activeCount = list.filter((user) => Number(user.is_active || 0) === 1).length;
  const adminCount = list.filter((user) => String(user.role || "") === "admin" || Number(user.is_admin || 0) === 1).length;
  panel.innerHTML = `
    <section class="settings-panel">
      <div class="settings-panel-head">
        <div>
          <h3>用户权限</h3>
          <p>直接维护账号当前角色和启用状态，权限拦截由后端按角色处理。</p>
        </div>
        <span class="tag green-outline">共 ${Number(total || list.length)} 个账号</span>
      </div>
      <div class="settings-summary-grid">
        <div class="setting-stat"><span>启用账号</span><strong>${activeCount}</strong></div>
        <div class="setting-stat"><span>管理员</span><strong>${adminCount}</strong></div>
        <div class="setting-stat"><span>待处理账号</span><strong>${Math.max(0, Number(total || list.length) - activeCount)}</strong></div>
      </div>
      ${renderUserList(list)}
      <div class="print-settings-actions">
        <button type="button" onclick="setCustomerTab('users');setView('customers');">打开用户管理</button>
        <button class="primary" type="button" onclick="loadPermissionSettings(true)">刷新</button>
      </div>
    </section>`;
}

async function loadImageSettings(force = false) {
  return loadSystemSetting("image_rules", "imageSettingsPanel", renderImageSettings, force);
}

function renderImageSettings(data = {}) {
  const panel = $("imageSettingsPanel");
  if (!panel) return;
  const value = data.value || {};
  const summary = data.media_summary || {};
  const assetRules = [
    "按商品 SPU + 大分类归档，未绑定图片单独展示。",
    "按图片类型归档：主图、详情页、颜色图、待绑定。",
    "按上传时间归档，绑定后再进入商品分组。"
  ];
  const currentAssetRule = value.asset_category_rule || assetRules[0];
  const assetRuleOptions = assetRules.map((rule) => `<option value="${escapeAttr(rule)}" ${rule === currentAssetRule ? "selected" : ""}>${escapeHtml(rule)}</option>`).join("");
  panel.innerHTML = `
    <section class="settings-panel">
      <div class="settings-panel-head">
        <div>
          <h3>图片 / OSS 设置</h3>
          <p>商品图上传后进入图片资产表，主图、详情页、颜色图都从这里绑定。</p>
        </div>
        <span class="tag green-outline">OSS / 图片资产</span>
      </div>
      <div class="settings-summary-grid">
        <div class="setting-stat"><span>全部图片</span><strong>${Number(summary.total || 0)}</strong></div>
        <div class="setting-stat"><span>主图</span><strong>${Number(summary.main || 0)}</strong></div>
        <div class="setting-stat"><span>详情页</span><strong>${Number(summary.detail || 0)}</strong></div>
        <div class="setting-stat"><span>颜色图</span><strong>${Number(summary.color || 0)}</strong></div>
        <div class="setting-stat"><span>待绑定</span><strong>${Number(summary.pending || 0)}</strong></div>
      </div>
      <div class="settings-grid">
        <label class="setting-field">OSS 上传路径
          <input id="imageOssPath" value="${escapeAttr(value.oss_path || "")}">
        </label>
        <label class="setting-field">缩略图规则
          <input id="imageThumbRule" value="${escapeAttr(value.thumbnail_rule || "")}">
        </label>
        <label class="setting-field">未绑定图片清理天数
          <input id="imagePendingCleanupDays" type="number" min="1" value="${escapeAttr(value.pending_cleanup_days || 30)}">
        </label>
        <label class="print-toggle"><input id="imageAutoCompress" type="checkbox" ${checkedAttr(value.auto_compress)}> 上传后压缩/缩略图</label>
        <label class="setting-field full">图片资产分类规则
          <select id="imageAssetRule">
            ${assetRules.includes(currentAssetRule) ? "" : `<option value="${escapeAttr(currentAssetRule)}" selected>${escapeHtml(currentAssetRule)}</option>`}
            ${assetRuleOptions}
          </select>
        </label>
      </div>
      <div class="print-template-note">上传插件继续使用现有 OSS 配置；图片绑定关系写在 product_media，不依赖 ShopXO 图片表。</div>
      <div class="print-settings-actions">
        <button type="button" onclick="setView('product-assets')">打开图片资产</button>
        <button type="button" onclick="chooseProductUpload('asset')">上传图片</button>
        <button class="primary" id="saveImageSettings" type="button">保存图片设置</button>
        <button class="primary" type="button" onclick="loadImageSettings(true)">刷新</button>
      </div>
    </section>`;
}

function collectImageSettings() {
  return {
    oss_path: $("imageOssPath") ? $("imageOssPath").value : "",
    thumbnail_rule: $("imageThumbRule") ? $("imageThumbRule").value : "",
    pending_cleanup_days: $("imagePendingCleanupDays") ? Number($("imagePendingCleanupDays").value || 30) : 30,
    auto_compress: checkedValue("imageAutoCompress"),
    asset_category_rule: $("imageAssetRule") ? $("imageAssetRule").value : ""
  };
}

const MINIAPP_MODULE_TYPES = [
  { type: "banner", label: "轮播", desc: "顶部轮播图" },
  { type: "nav", label: "导航", desc: "快捷入口" },
  { type: "image", label: "图片", desc: "单图广告" },
  { type: "hot_zone", label: "热区", desc: "图片热区" },
  { type: "product_shelf", label: "商品区", desc: "商品列表" }
];

async function loadMiniappDesignSettings(force = false) {
  return loadSystemSetting("miniapp_design", "miniappSettingsPanel", renderMiniappDesignSettings, force);
}

function miniappModuleTypeLabel(type) {
  const row = MINIAPP_MODULE_TYPES.find((item) => item.type === type);
  return row ? row.label : "模块";
}

function miniappModuleTypeOptions(current = "nav") {
  return MINIAPP_MODULE_TYPES.map((item) => (
    `<option value="${escapeAttr(item.type)}" ${item.type === current ? "selected" : ""}>${escapeHtml(item.label)}</option>`
  )).join("");
}

function miniappDraft() {
  if (!state.miniappDesignDraft) {
    state.miniappDesignDraft = {
      version: 1,
      home: { title: "肆计包装", subtitle: "茶包装产品展示", modules: [] }
    };
  }
  const home = state.miniappDesignDraft.home || {};
  if (!Array.isArray(home.modules)) home.modules = [];
  state.miniappDesignDraft.home = home;
  return state.miniappDesignDraft;
}

function miniappHome() {
  return miniappDraft().home;
}

function miniappModules() {
  return miniappHome().modules || [];
}

function defaultMiniappModule(type = "nav") {
  const id = `${type}_${Date.now()}`;
  if (type === "banner") {
    return { id, type, enabled: 1, title: "首页轮播", items: [{ title: "肆计包装", url: "/pages/goods-category/goods-category", image: "" }] };
  }
  if (type === "product_shelf") {
    return { id, type, enabled: 1, title: "推荐产品", keywords: "", category_id: "", limit: 8 };
  }
  if (type === "image" || type === "hot_zone") {
    return { id, type, enabled: 1, title: miniappModuleTypeLabel(type), items: [{ title: "肆计包装", url: "/pages/goods-category/goods-category", image: "" }] };
  }
  return {
    id,
    type: "nav",
    enabled: 1,
    title: "快捷导航",
    items: [
      { title: "分类", url: "/pages/goods-category/goods-category", image: "" },
      { title: "订单", url: "/pages/order/order", image: "" },
      { title: "我的", url: "/pages/user/user", image: "" }
    ]
  };
}

function miniappItemIcon(item = {}, fallback = "") {
  const title = String(item.title || fallback || "项").trim();
  return escapeHtml(title.slice(0, 1) || "项");
}

function miniappPreviewModule(module = {}, index = 0) {
  const type = module.type || "nav";
  const active = Number(state.miniappSelectedIndex || 0) === index ? "active" : "";
  const disabled = Number(module.enabled ?? 1) ? "" : "disabled";
  const title = module.title || miniappModuleTypeLabel(type);
  if (type === "banner") {
    const items = Array.isArray(module.items) && module.items.length ? module.items : [{ title: "轮播图" }];
    return `<button type="button" class="miniapp-preview-module ${active} ${disabled} banner" data-miniapp-select-module="${index}">
      <div class="miniapp-preview-banner">
        <strong>${escapeHtml(items[0].title || title || "首页轮播")}</strong>
        <span>${escapeHtml(items.length)} 张轮播</span>
      </div>
    </button>`;
  }
  if (type === "nav") {
    const items = Array.isArray(module.items) ? module.items : [];
    return `<button type="button" class="miniapp-preview-module ${active} ${disabled}" data-miniapp-select-module="${index}">
      <div class="miniapp-preview-nav">
        ${items.slice(0, 8).map((item) => `<span><i>${miniappItemIcon(item)}</i>${escapeHtml(item.title || "导航")}</span>`).join("") || "<em>暂无导航</em>"}
      </div>
    </button>`;
  }
  if (type === "product_shelf") {
    const products = Array.isArray(module.products) ? module.products : [];
    return `<button type="button" class="miniapp-preview-module ${active} ${disabled}" data-miniapp-select-module="${index}">
      <div class="miniapp-preview-title">${escapeHtml(title || "商品区")}</div>
      <div class="miniapp-preview-products">
        ${(products.length ? products.slice(0, 4) : [{ title: "商品卡片" }, { title: "商品卡片" }, { title: "商品卡片" }, { title: "商品卡片" }]).map((item) => `
          <span><b></b><i>${escapeHtml(item.title || item.name || "商品卡片")}</i></span>
        `).join("")}
      </div>
    </button>`;
  }
  const item = Array.isArray(module.items) && module.items.length ? module.items[0] : {};
  return `<button type="button" class="miniapp-preview-module ${active} ${disabled}" data-miniapp-select-module="${index}">
    <div class="miniapp-preview-image ${type === "hot_zone" ? "hot" : ""}">
      <strong>${escapeHtml(item.title || title || miniappModuleTypeLabel(type))}</strong>
      <span>${escapeHtml(miniappModuleTypeLabel(type))}</span>
    </div>
  </button>`;
}

function miniappOutlineRow(module = {}, index = 0, total = 0) {
  const active = Number(state.miniappSelectedIndex || 0) === index ? "active" : "";
  const off = Number(module.enabled ?? 1) ? "" : "off";
  return `<div class="miniapp-outline-row ${active} ${off}" data-miniapp-select-module="${index}">
    <button type="button" class="miniapp-outline-main" data-miniapp-select-module="${index}">
      <strong>${escapeHtml(module.title || miniappModuleTypeLabel(module.type))}</strong>
      <span>${escapeHtml(miniappModuleTypeLabel(module.type))}${off ? " / 已隐藏" : ""}</span>
    </button>
    <button type="button" data-miniapp-module-move="-1" data-miniapp-index="${index}" ${index <= 0 ? "disabled" : ""}>↑</button>
    <button type="button" data-miniapp-module-move="1" data-miniapp-index="${index}" ${index >= total - 1 ? "disabled" : ""}>↓</button>
    <button type="button" class="setting-delete" data-miniapp-module-remove data-miniapp-index="${index}" title="删除">×</button>
  </div>`;
}

function miniappItemsEditor(module = {}) {
  const type = module.type || "nav";
  const items = Array.isArray(module.items) ? module.items : [];
  const label = type === "banner" ? "轮播项" : type === "nav" ? "导航项" : "图片入口";
  return `<div class="setting-block full">
    <div class="setting-block-title"><span>${escapeHtml(label)}</span><button type="button" data-miniapp-add-item>新增一项</button></div>
    <div class="miniapp-item-editor">
      ${items.map((item, index) => `
        <div class="miniapp-item-row" data-miniapp-item-index="${index}">
          <input data-miniapp-item-field="title" value="${escapeAttr(item.title || "")}" placeholder="标题">
          <input data-miniapp-item-field="url" value="${escapeAttr(item.url || "")}" placeholder="跳转路径">
          <input data-miniapp-item-field="image" value="${escapeAttr(item.image || "")}" placeholder="图片地址">
          <button type="button" class="setting-delete" data-miniapp-remove-item="${index}" title="删除">×</button>
        </div>
      `).join("") || '<div class="empty">还没有内容项</div>'}
    </div>
  </div>`;
}

function miniappInspectorHtml() {
  const modules = miniappModules();
  const selected = modules[Number(state.miniappSelectedIndex || 0)];
  if (!selected) {
    return `<div class="miniapp-inspector-empty">从左侧新增模块，或在中间预览里选择一个模块。</div>`;
  }
  const type = selected.type || "nav";
  return `
    <div class="miniapp-inspector-head">
      <strong>${escapeHtml(selected.title || miniappModuleTypeLabel(type))}</strong>
      <span>${escapeHtml(miniappModuleTypeLabel(type))}设置</span>
    </div>
    <div class="settings-grid miniapp-inspector-grid">
      <label class="setting-field">模块类型
        <select data-miniapp-module-field="type">${miniappModuleTypeOptions(type)}</select>
      </label>
      <label class="print-toggle"><input type="checkbox" data-miniapp-module-field="enabled" ${checkedAttr(selected.enabled ?? 1)}> 显示模块</label>
      <label class="setting-field full">模块标题
        <input data-miniapp-module-field="title" value="${escapeAttr(selected.title || "")}" placeholder="例如：推荐产品">
      </label>
      ${type === "product_shelf" ? `
        <label class="setting-field">搜索关键词
          <input data-miniapp-module-field="keywords" value="${escapeAttr(selected.keywords || "")}" placeholder="例如：半斤礼盒">
        </label>
        <label class="setting-field">分类 ID
          <input data-miniapp-module-field="category_id" value="${escapeAttr(selected.category_id || "")}" placeholder="留空为全部">
        </label>
        <label class="setting-field">展示数量
          <input type="number" min="1" max="30" data-miniapp-module-field="limit" value="${escapeAttr(selected.limit || 8)}">
        </label>
      ` : miniappItemsEditor(selected)}
    </div>`;
}

function renderMiniappDesignSettings(data = {}) {
  const panel = $("miniappSettingsPanel");
  if (!panel) return;
  state.miniappDesignSettings = data;
  const value = data.value || {};
  const home = value.home || {};
  state.miniappDesignDraft = {
    version: Number(value.version || 1),
    home: {
      title: home.title || "肆计包装",
      subtitle: home.subtitle || "茶包装产品展示",
      modules: Array.isArray(home.modules) ? JSON.parse(JSON.stringify(home.modules)) : []
    }
  };
  if (state.miniappSelectedIndex === undefined || state.miniappSelectedIndex >= miniappModules().length) {
    state.miniappSelectedIndex = 0;
  }
  renderMiniappDesigner();
}

function renderMiniappDesigner() {
  const panel = $("miniappSettingsPanel");
  if (!panel) return;
  const home = miniappHome();
  const modules = miniappModules();
  panel.innerHTML = `
    <section class="settings-panel miniapp-design-panel">
      <div class="settings-panel-head">
        <div>
          <h3>小程序首页设计</h3>
          <p>左侧选组件，中间看手机预览，右侧改属性。保存后小程序首页接口直接读取这份设计。</p>
        </div>
        <span class="tag green-outline">${Number(modules.length || 0)} 个模块</span>
      </div>
      <div class="miniapp-designer">
        <aside class="miniapp-palette">
          <div class="miniapp-pane-title"><strong>组件库</strong><span>添加到首页</span></div>
          <div class="miniapp-palette-grid">
            ${MINIAPP_MODULE_TYPES.map((item) => `<button type="button" data-miniapp-add-module="${escapeAttr(item.type)}"><strong>${escapeHtml(item.label)}</strong><span>${escapeHtml(item.desc)}</span></button>`).join("")}
          </div>
          <div class="miniapp-pane-title"><strong>页面结构</strong><span>点击选择</span></div>
          <div class="miniapp-outline">
            ${modules.map((module, index) => miniappOutlineRow(module, index, modules.length)).join("") || '<div class="empty">还没有模块</div>'}
          </div>
        </aside>
        <main class="miniapp-canvas-wrap">
          <div class="miniapp-phone">
            <div class="miniapp-phone-bar"></div>
            <div class="miniapp-phone-nav">
              <strong>${escapeHtml(home.title || "肆计包装")}</strong>
              <span>${escapeHtml(home.subtitle || "茶包装产品展示")}</span>
            </div>
            <div class="miniapp-phone-scroll">
              ${modules.map((module, index) => miniappPreviewModule(module, index)).join("") || '<div class="miniapp-preview-empty">从左侧添加首页组件</div>'}
            </div>
            <div class="miniapp-phone-tabs"><span>首页</span><span>分类</span><span>订单</span><span>我的</span></div>
          </div>
        </main>
        <aside class="miniapp-inspector">
          <div class="miniapp-pane-title"><strong>页面设置</strong><span>首页基础信息</span></div>
          <div class="settings-grid miniapp-page-grid">
            <label class="setting-field full">首页标题
              <input data-miniapp-home-field="title" value="${escapeAttr(home.title || "肆计包装")}">
            </label>
            <label class="setting-field full">副标题
              <input data-miniapp-home-field="subtitle" value="${escapeAttr(home.subtitle || "茶包装产品展示")}">
            </label>
          </div>
          <div class="miniapp-pane-title"><strong>组件属性</strong><span>当前选中模块</span></div>
          ${miniappInspectorHtml()}
        </aside>
      </div>
      <div class="print-template-note">跳转路径只保存首页、分类、订单、我的、商品搜索；旧购物车/支付路径会被后端清掉。</div>
      <div class="print-settings-actions">
        <button type="button" onclick="loadMiniappDesignSettings(true)">刷新</button>
        <button class="primary" id="saveMiniappDesignSettings" type="button">保存首页设计</button>
      </div>
    </section>`;
}

function collectMiniappDesignSettings() {
  return JSON.parse(JSON.stringify(miniappDraft()));
}

function addMiniappHomeModule(type = "nav") {
  const modules = miniappModules();
  modules.push(defaultMiniappModule(type));
  state.miniappSelectedIndex = modules.length - 1;
  renderMiniappDesigner();
}

function selectMiniappHomeModule(index = 0) {
  const modules = miniappModules();
  state.miniappSelectedIndex = Math.min(Math.max(Number(index || 0), 0), Math.max(modules.length - 1, 0));
  renderMiniappDesigner();
}

function moveMiniappHomeModule(index, delta) {
  const modules = miniappModules();
  const current = Number(index || 0);
  const next = current + Number(delta || 0);
  if (next < 0 || next >= modules.length) return;
  const temp = modules[current];
  modules[current] = modules[next];
  modules[next] = temp;
  state.miniappSelectedIndex = next;
  renderMiniappDesigner();
}

function removeMiniappHomeModule(index) {
  const modules = miniappModules();
  modules.splice(Number(index || 0), 1);
  state.miniappSelectedIndex = Math.min(Number(state.miniappSelectedIndex || 0), Math.max(modules.length - 1, 0));
  renderMiniappDesigner();
}

function updateMiniappHomeField(field, value) {
  if (!["title", "subtitle"].includes(field)) return;
  miniappHome()[field] = value;
  renderMiniappDesigner();
}

function updateMiniappModuleField(field, value, checked = false) {
  const module = miniappModules()[Number(state.miniappSelectedIndex || 0)];
  if (!module) return;
  if (field === "enabled") module.enabled = checked ? 1 : 0;
  else if (field === "limit") module.limit = Number(value || 8);
  else if (field === "type") {
    const next = { ...defaultMiniappModule(value), id: module.id, title: module.title, enabled: module.enabled };
    Object.assign(module, next);
  } else if (["title", "keywords", "category_id"].includes(field)) {
    module[field] = value;
  }
  renderMiniappDesigner();
}

function addMiniappItem() {
  const module = miniappModules()[Number(state.miniappSelectedIndex || 0)];
  if (!module) return;
  if (!Array.isArray(module.items)) module.items = [];
  module.items.push({ title: "", url: "/pages/goods-category/goods-category", image: "" });
  renderMiniappDesigner();
}

function removeMiniappItem(index) {
  const module = miniappModules()[Number(state.miniappSelectedIndex || 0)];
  if (!module || !Array.isArray(module.items)) return;
  module.items.splice(Number(index || 0), 1);
  renderMiniappDesigner();
}

function updateMiniappItemField(row, field, value) {
  const module = miniappModules()[Number(state.miniappSelectedIndex || 0)];
  if (!module || !Array.isArray(module.items)) return;
  const item = module.items[Number(row || 0)];
  if (!item || !["title", "url", "image"].includes(field)) return;
  item[field] = value;
  renderMiniappDesigner();
}

function renderMessage(text) {
  const lines = String(text || "").split("\n");
  let html = "";
  for (let i = 0; i < lines.length; i += 1) {
    if (i + 1 < lines.length && lines[i].includes("|") && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[i + 1])) {
      const table = [lines[i], lines[i + 1]];
      i += 2;
      while (i < lines.length && lines[i].includes("|")) {
        table.push(lines[i]);
        i += 1;
      }
      i -= 1;
      html += renderTable(table);
    } else {
      html += linkify(escapeHtml(lines[i])) + (i < lines.length - 1 ? "<br>" : "");
    }
  }
  return html;
}

function linkify(html) {
  return html.replace(/(https?:\/\/[^\s<]+|\/api\/images\/file\/[^\s<]+|blob:[^\s<]+)/g, (url) => {
    const clean = url.replace(/[，。,.]+$/, "");
    const isImage = /\.(png|jpe?g|webp|bmp|gif)(\?.*)?$/i.test(clean) || clean.includes("/api/images/file/") || clean.startsWith("blob:");
    const label = isImage ? "查看图片" : clean;
    return `<a href="${clean}" target="_blank" rel="noopener">${label}</a>${isImage ? `<img class="message-image" src="${clean}">` : ""}`;
  });
}

function splitRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function renderTable(lines) {
  const headers = splitRow(lines[0]);
  const rows = lines.slice(2).map(splitRow);
  return `<div class="md-table-wrap"><table class="md-table"><thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${headers.map((_, index) => `<td>${escapeHtml(row[index] || "")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function chatStorageKey() {
  return `sj_web_chat_${state.sessionId}`;
}

function historyStorageKey() {
  return `sj_web_business_history_${state.sessionId}`;
}

function persistMessages() {
  const messages = $("messages");
  if (!messages) return;
  const items = Array.from(messages.querySelectorAll(".message")).map((node) => ({
    role: node.dataset.role || (node.classList.contains("user") ? "user" : "assistant"),
    text: node.dataset.text || ""
  })).filter((item) => item.text);
  localStorage.setItem(chatStorageKey(), JSON.stringify(items.slice(-100)));
}

function restoreMessages() {
  const messages = $("messages");
  if (!messages) return;
  messages.innerHTML = "";
  try {
    const items = JSON.parse(localStorage.getItem(chatStorageKey()) || "[]");
    if (Array.isArray(items)) {
      items.forEach((item) => addMessage(item.role === "user" ? "user" : "assistant", item.text || "", false));
    }
  } catch (err) {
    console.warn(err);
  }
}

function persistBusinessHistory() {
  localStorage.setItem(historyStorageKey(), JSON.stringify((state.businessHistory || []).slice(0, 5)));
}

function restoreBusinessHistory() {
  try {
    const items = JSON.parse(localStorage.getItem(historyStorageKey()) || "[]");
    state.businessHistory = Array.isArray(items) ? items.slice(0, 5) : [];
  } catch (err) {
    state.businessHistory = [];
  }
}

function addMessage(role, text, shouldPersist = true) {
  const messages = $("messages");
  if (!messages) return;
  const message = document.createElement("div");
  message.className = `message ${role === "user" ? "user" : "assistant"}`;
  message.dataset.role = role === "user" ? "user" : "assistant";
  message.dataset.text = text || "";
  message.innerHTML = `<div class="bubble">${renderMessage(text)}</div><div class="msg-meta">${role === "user" ? "你" : "北极星"}</div>`;
  messages.appendChild(message);
  messages.scrollTop = messages.scrollHeight;
  if (shouldPersist) persistMessages();
  return message;
}

function updateMessage(node, text) {
  if (!node) return addMessage("assistant", text);
  node.dataset.text = text || "";
  const bubble = node.querySelector(".bubble");
  if (bubble) bubble.innerHTML = renderMessage(text);
  const messages = $("messages");
  if (messages) messages.scrollTop = messages.scrollHeight;
  persistMessages();
  return node;
}

function flattenRows(obj, prefix = "") {
  let rows = [];
  if (!obj || typeof obj !== "object") return rows;
  Object.entries(obj).forEach(([key, value]) => {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object" && !Array.isArray(value)) {
      rows = rows.concat(flattenRows(value, fullKey));
    } else {
      rows.push([fullKey, Array.isArray(value) ? value.join(", ") : value]);
    }
  });
  return rows;
}

function kvRows(rows) {
  return `<div class="kv">${rows.map(([key, value]) => `<div class="kv-row"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div>`;
}

function productLineHtml(product = {}) {
  const name = product.name || product.title || product.goods_name || product.product_name || "商品未识别";
  const color = product.color || product.spec || product.goods_color || "";
  const rawQty = product.qty ?? product.quantity ?? product.order_quantity;
  const qty = rawQty === undefined || rawQty === null || rawQty === "" ? 1 : rawQty;
  const unit = product.unit || product.unit_name || "";
  const warehouse = product.warehouse_name || product.warehouse || (Number(product.warehouse_id) === 1 ? "自己店里" : (Number(product.warehouse_id) === 2 ? "百鑫仓库" : ""));
  const price = product.price ? `，单价 ${product.price}` : "";
  return `<li><strong>${escapeHtml(name)}</strong>${color ? `<span>${escapeHtml(color)}</span>` : ""}<span>${escapeHtml(`${qty}${unit}`)}</span>${warehouse ? `<span>${escapeHtml(warehouse)}</span>` : ""}${price ? `<span>${escapeHtml(price)}</span>` : ""}</li>`;
}

function pendingActionOf(session = state.session) {
  const stateData = (session && session.state) || {};
  return (session && session.pending_action) || stateData.pending_action || "";
}

function isConfirmablePending(session = state.session) {
  const action = pendingActionOf(session);
  return action.includes("confirm_");
}

function pendingSummaryHtml(session = state.session) {
  const stateData = session.state || {};
  const action = pendingActionOf(session);
  const intent = session.pending_intent || "";
  const title = pendingTitle(session);
  let html = `<div class="business-summary"><h4>${escapeHtml(title)}</h4>`;

  if (action.includes("confirm_image_sales")) {
    const params = stateData.order_params || {};
    const customer = params.customer || params.customer_name || (params.customers || []).join("、") || "未识别";
    const products = params.products || [];
    html += `<p><b>客户：</b>${escapeHtml(customer)}</p>`;
    html += `<ul class="summary-lines">${products.length ? products.map(productLineHtml).join("") : "<li>商品信息未识别</li>"}</ul>`;
  } else if (action.includes("confirm_create_order")) {
    html += `<p><b>客户：</b>${escapeHtml(stateData.customer_name || stateData.customer || `客户#${stateData.customer_id || ""}` || "未识别")}</p>`;
    html += `<p><b>动作：</b>${stateData.auto_purchase ? "先进货入库，再创建销售单" : "创建销售单"}</p>`;
    const products = stateData.products || [];
    html += `<ul class="summary-lines">${products.length ? products.map(productLineHtml).join("") : "<li>商品信息未识别</li>"}</ul>`;
  } else if (action.includes("confirm_product_name")) {
    const products = stateData.products || [];
    const index = Number(stateData.product_index || 0);
    const current = products[index] || products[0] || {};
    html += `<p><b>客户：</b>${escapeHtml(stateData.customer_name || stateData.customer || "未识别")}</p>`;
    html += `<p><b>需要确认商品：</b>${escapeHtml([current.name || current.title || current.goods_name || "商品未识别", current.color || current.spec || ""].filter(Boolean).join(" "))}</p>`;
    html += `<ul class="summary-lines">${products.length ? products.map(productLineHtml).join("") : "<li>商品信息未识别</li>"}</ul>`;
  } else if (action.includes("confirm_image_workflow_orders")) {
    const items = stateData.parsed_list || [];
    html += `<p><b>动作：</b>创建 ${items.length || 0} 个工作流订单</p>`;
    html += `<ul class="summary-lines">${items.length ? items.map(productLineHtml).join("") : "<li>没有可创建的工作流订单</li>"}</ul>`;
    if (stateData.order_params && (stateData.order_params.products || []).length) {
      html += `<p><b>后续：</b>图片里包含开单/下单，确认工作流后会继续进入销售单确认。</p>`;
    } else if (stateData.optional_order_params && (stateData.optional_order_params.products || []).length) {
      html += `<p><b>后续：</b>提交工作流后会询问是否继续开销售单。</p>`;
    }
  } else if (action.includes("confirm_create_workflow_order")) {
    const parsed = stateData.parsed || {};
    html += `<p><b>客户：</b>${escapeHtml(parsed.customer || parsed.customer_name || "未填写")}</p>`;
    html += `<ul class="summary-lines">${productLineHtml(parsed)}</ul>`;
  } else if (action.includes("purchase")) {
    const params = stateData.params || stateData;
    html += `<p><b>动作：</b>进货入库</p>`;
    html += `<ul class="summary-lines">${productLineHtml(params)}</ul>`;
  } else if (action.includes("transfer")) {
    const params = stateData.params || stateData;
    html += `<p><b>动作：</b>调货/调拨</p>`;
    html += `<p><b>仓库：</b>${escapeHtml(params.from || params.out_warehouse || "调出仓库")} -> ${escapeHtml(params.to || params.enter_warehouse || "调入仓库")}</p>`;
    html += `<ul class="summary-lines">${productLineHtml(params)}</ul>`;
  } else if (action.includes("stocktaking") || intent.includes("stocktaking")) {
    const params = stateData.params || stateData;
    const products = params.products || stateData.products || [params];
    html += `<p><b>动作：</b>盘点/校准库存</p>`;
    html += `<ul class="summary-lines">${products.map(productLineHtml).join("")}</ul>`;
  } else if (intent.includes("bag_upload") || action.includes("bag_")) {
    const rows = [
      ["模板", stateData.template_name || stateData.bag_type || "待选择"],
      ["商品名", stateData.product_name || "待填写"],
      ["分类", stateData.category_name || "待识别"],
      ["编号预览", stateData.coding_preview || "ERP自动生成"],
      ["标题", stateData.title || "待生成"],
    ];
    html += kvRows(rows);
    if (stateData.image_path) html += `<p><b>图片：</b>${escapeHtml(String(stateData.image_path).split(/[\\\\/]/).pop())}</p>`;
    const bagImages = [
      ["标准图", stateData.standard_url],
      ["主图", stateData.main_url],
      ["详情页", stateData.detail_url],
    ].filter((item) => item[1]);
    if (bagImages.length) {
      html += `<div class="bag-preview-grid">${bagImages.map(([label, url]) => `
        <a class="bag-preview-item" href="${escapeAttr(url)}" target="_blank" rel="noopener">
          <span>${escapeHtml(label)}</span>
          <img src="${escapeAttr(url)}" alt="${escapeAttr(label)}">
        </a>
      `).join("")}</div>`;
    }
  } else {
    const rows = flattenRows(stateData).slice(0, 12);
    html += rows.length ? kvRows(rows) : '<div class="empty">这次确认没有结构化字段，按聊天内容核对即可。</div>';
  }

  html += isConfirmablePending(session)
    ? `<p class="summary-note">确认后才会真正写入系统；取消不会执行。</p></div>`
    : `<p class="summary-note">按聊天里的问题继续回复；这一步不会写入系统。</p></div>`;
  return html;
}

function editableField(path, label, value, type = "text") {
  const normalized = value ?? "";
  return `<label class="confirm-field"><span>${escapeHtml(label)}</span><input data-pending-path="${escapeAttr(path)}" data-original-value="${escapeAttr(normalized)}" type="${type}" value="${escapeAttr(normalized)}"></label>`;
}

function editableWarehouseSelect(path, label, value) {
  const selected = Number(value || 2);
  return `<label class="confirm-field"><span>${escapeHtml(label)}</span><select data-pending-path="${escapeAttr(path)}" data-original-value="${escapeAttr(selected)}">
    <option value="2" ${selected === 2 ? "selected" : ""}>百鑫仓库</option>
    <option value="1" ${selected === 1 ? "selected" : ""}>自己店里</option>
  </select></label>`;
}

function editablePurchaseWarehouseSelect(path, label, value) {
  return editableWarehouseSelect(path, label, value);
}

function editableProductFields(basePath, product = {}, index = 0, options = {}) {
  const includeWarehouse = options.includeWarehouse !== false;
  const includePrice = options.includePrice !== false;
  const warehouseLabel = options.warehouseLabel || "发货仓库";
  return `
    <div class="confirm-edit-line">
      <div class="line-title">商品 ${index + 1}</div>
      ${editableField(`${basePath}.name`, "商品", product.name || product.title || product.goods_name || product.product_name || "")}
      ${editableField(`${basePath}.color`, "颜色", product.color || product.spec || product.goods_color || "")}
      ${editableField(`${basePath}.qty`, "数量", product.qty ?? product.quantity ?? product.order_quantity ?? 1, "number")}
      ${includePrice ? editableField(`${basePath}.price`, "单价", product.price || "", "number") : ""}
      ${includeWarehouse ? editableWarehouseSelect(`${basePath}.warehouse_id`, warehouseLabel, product.warehouse_id || 2) : ""}
    </div>`;
}

function editablePurchaseProductFields(basePath, product = {}, index = 0) {
  const purchaseUnit = product.purchase_unit || product.unit || "套";
  const purchaseQty = product.purchase_qty ?? product.qty ?? product.quantity ?? product.order_quantity ?? 1;
  const orderQty = product.qty ?? product.quantity ?? product.order_quantity ?? "";
  const orderUnit = product.unit || "";
  const purchaseWarehouseId = product.purchase_warehouse_id || product.warehouse_id || 2;
  return `
    <div class="confirm-edit-line">
      <div class="line-title">进货商品 ${index + 1}${orderQty ? ` · 订单 ${escapeHtml(`${orderQty}${orderUnit}`)}` : ""}</div>
      ${editableField(`${basePath}.name`, "商品", product.name || product.title || product.goods_name || product.product_name || "")}
      ${editableField(`${basePath}.color`, "颜色", product.color || product.spec || product.goods_color || "")}
      ${editablePurchaseWarehouseSelect(`${basePath}.purchase_warehouse_id`, "入库仓库", purchaseWarehouseId)}
      ${editableField(`${basePath}.purchase_qty`, `进货数量（${purchaseUnit}）`, purchaseQty, "number")}
      ${editableField(`${basePath}.purchase_unit`, "进货单位", purchaseUnit)}
    </div>`;
}

function pendingEditableHtml(session = state.session) {
  const stateData = session.state || {};
  const action = session.pending_action || stateData.pending_action || "";
  const intent = session.pending_intent || "";
  let html = `<div class="business-summary confirm-edit-form">`;

  if (action.includes("confirm_image_sales")) {
    const params = stateData.order_params || {};
    const customer = params.customer || params.customer_name || (params.customers || []).join("、") || "未识别";
    const products = params.products || [];
    html += editableField("order_params.customer", "客户", customer === "未识别" ? "" : customer);
    html += products.length
      ? products.map((p, i) => editableProductFields(`order_params.products.${i}`, p, i, { includeWarehouse: false, includePrice: false })).join("")
      : "<div class=\"empty\">商品信息未识别</div>";
  } else if (action.includes("confirm_product_name")) {
    const products = stateData.products || [];
    const index = Number(stateData.product_index || 0);
    const current = products[index] || products[0] || {};
    html += editableField(`products.${index}.name`, "商品", current.name || current.title || current.goods_name || current.product_name || "");
    html += editableField(`products.${index}.color`, "颜色", current.color || current.spec || current.goods_color || "");
    html += `<p class="summary-note">请把商品名或颜色改准确后确认；如果已经准确，直接确认继续匹配。</p>`;
  } else if (action.includes("confirm_create_order")) {
    html += editableField("customer_name", "客户", stateData.customer_name || stateData.customer || "");
    html += editableWarehouseSelect("warehouse_id", "整单默认仓库", stateData.warehouse_id || 2);
    html += `<p><b>动作：</b>${stateData.auto_purchase ? "先进货入库，再创建销售单" : "创建销售单"}</p>`;
    const products = stateData.products || [];
    html += products.length ? products.map((p, i) => editableProductFields(`products.${i}`, p, i)).join("") : '<div class="empty">商品信息未识别</div>';
  } else if (action.includes("confirm_image_workflow_orders")) {
    const items = stateData.parsed_list || [];
    html += `<p><b>动作：</b>核对 OCR 识别结果，提交后直接创建 ${items.length || 0} 个工作流订单</p>`;
    html += items.length ? items.map((p, i) => `
      <div class="confirm-edit-line">
        <div class="line-title">工作流 ${i + 1}</div>
        ${editableField(`parsed_list.${i}.customer`, "客户", p.customer || "")}
        ${editableField(`parsed_list.${i}.goods_name`, "商品", p.goods_name || "")}
        ${editableField(`parsed_list.${i}.color`, "颜色", p.color || "")}
        ${editableField(`parsed_list.${i}.quantity`, "数量", p.quantity || 1, "number")}
        ${editableField(`parsed_list.${i}.remark`, "备注", p.remark || "")}
      </div>`).join("") : '<div class="empty">没有可创建的工作流订单</div>';
  } else if (action.includes("confirm_create_workflow_order")) {
    const parsed = stateData.parsed || {};
    html += editableField("parsed.customer", "客户", parsed.customer || parsed.customer_name || "");
    html += editableField("parsed.goods_name", "商品", parsed.goods_name || "");
    html += editableField("parsed.color", "颜色", parsed.color || "");
    html += editableField("parsed.quantity", "数量", parsed.quantity || 1, "number");
    html += editableField("parsed.remark", "备注", parsed.remark || "");
  } else if (action.includes("purchase")) {
    const params = stateData.params || stateData;
    const products = params.products || stateData.products || stateData.items || [];
    if (products.length) {
      const base = stateData.items ? "items" : `${stateData.params ? "params." : ""}products`;
      const entries = products
        .map((p, i) => ({ p, i }))
        .filter(({ p }) => !stateData.return_to_order || p.need_purchase || p.shortage_qty);
      html += entries.length
        ? entries.map(({ p, i }, visibleIndex) => editablePurchaseProductFields(`${base}.${i}`, p, visibleIndex)).join("")
        : pendingSummaryHtml(session);
    } else if (params.name || params.product_name || params.goods_name) {
      html += editablePurchaseProductFields(stateData.params ? "params" : "", params, 0);
    } else {
      html += pendingSummaryHtml(session);
    }
  } else if (action.includes("stocktaking") || intent.includes("stocktaking")) {
    const items = stateData.items || [];
    html += editableWarehouseSelect("warehouse_id", "盘点仓库", stateData.warehouse_id || 2);
    html += items.length
      ? items.map((p, i) => editableProductFields(`items.${i}`, p, i, { includeWarehouse: false, includePrice: false })).join("")
      : pendingSummaryHtml(session);
  } else if (action.includes("transfer")) {
    html += editableWarehouseSelect("from_wh", "调出仓库", stateData.from_wh || 2);
    html += editableWarehouseSelect("to_wh", "调入仓库", stateData.to_wh || 1);
    const items = stateData.items || [];
    if (items.length) {
      html += items.map((p, i) => editableProductFields(`items.${i}`, p, i, { includeWarehouse: false, includePrice: false })).join("");
    } else {
      html += pendingSummaryHtml(session);
    }
  } else {
    html += pendingSummaryHtml(session);
  }
  const note = action.includes("confirm_image_workflow_orders")
    ? "可以先改错的字段，提交后直接创建工作流订单。"
    : (action.includes("confirm_image_sales") ? "确认后进入销售单核对；取消则不继续开销售单。" : "可以先改错的字段，再确认执行。");
  html += `<p class="summary-note">${note}</p></div>`;
  return html;
}

function setPendingValue(target, path, value) {
  const parts = String(path || "").split(".").filter(Boolean);
  if (!parts.length) return;
  let ref = target;
  for (let i = 0; i < parts.length - 1; i += 1) {
    const key = /^\d+$/.test(parts[i]) ? Number(parts[i]) : parts[i];
    if (ref[key] === undefined || ref[key] === null) ref[key] = /^\d+$/.test(parts[i + 1]) ? [] : {};
    ref = ref[key];
  }
  const last = /^\d+$/.test(parts[parts.length - 1]) ? Number(parts[parts.length - 1]) : parts[parts.length - 1];
  ref[last] = value;
}

function collectPendingEdits() {
  const stateCopy = JSON.parse(JSON.stringify((state.session && state.session.state) || {}));
  const pendingAction = pendingActionOf(state.session);
  document.querySelectorAll("#businessConfirmBody [data-pending-path]").forEach((input) => {
    const original = input.dataset.originalValue ?? "";
    const path = input.dataset.pendingPath || "";
    if (input.type === "number") {
      const before = Number(original || 0);
      const after = Number(input.value || 0);
      if (Number.isFinite(before) && Number.isFinite(after) && before === after) return;
    } else if (String(input.value || "").trim() === String(original || "").trim()) {
      return;
    }
    const raw = input.type === "number" ? Number(input.value || 0) : input.value.trim();
    const value = input.type === "number" && Number.isFinite(raw) ? raw : (path.endsWith("warehouse_id") ? Number(input.value || 2) : input.value.trim());
    setPendingValue(stateCopy, path, value);
    if (path === "warehouse_id" && pendingAction.includes("confirm_create_order") && Array.isArray(stateCopy.products)) {
      stateCopy.products = stateCopy.products.map((product) => ({ ...product, warehouse_id: value }));
    } else if (path === "warehouse_id" && pendingAction.includes("purchase")) {
      if (Array.isArray(stateCopy.products)) {
        stateCopy.products = stateCopy.products.map((product) => ({ ...product, purchase_warehouse_id: value }));
      }
      if (Array.isArray(stateCopy.items)) {
        stateCopy.items = stateCopy.items.map((product) => ({ ...product, purchase_warehouse_id: value }));
      }
      if (stateCopy.params && Array.isArray(stateCopy.params.products)) {
        stateCopy.params.products = stateCopy.params.products.map((product) => ({ ...product, purchase_warehouse_id: value }));
      }
    }
  });
  return stateCopy;
}

async function savePendingEdits() {
  if (!(state.session && state.session.has_pending)) return;
  const editedState = collectPendingEdits();
  const res = await api("/api/session/pending", {
    method: "POST",
    body: { session_id: state.sessionId, state: editedState }
  });
  state.session = (res.data && res.data.session) || { ...state.session, state: editedState };
}

function pushBusinessHistory(card) {
  const duplicateKey = card.businessKey || "";
  const current = duplicateKey
    ? (state.businessHistory || []).filter((item) => item.businessKey !== duplicateKey)
    : (state.businessHistory || []);
  const item = { id: `biz_${Date.now()}_${Math.random().toString(16).slice(2)}`, time: new Date(), ...card };
  state.businessHistory = [item, ...current].slice(0, 5);
  persistBusinessHistory();
  renderBusinessContext();
  return item;
}

function businessHistoryHtml() {
  const cards = state.businessHistory || [];
  if (!cards.length) {
    return '<div class="empty">暂无业务记录。查询、开单、工作流处理后会保留最近 5 条。</div>';
  }
  return cards.map((card) => {
    const tagClass = "green-outline";
    const actions = card.actions || "";
    return `
      <div class="business-card history-card">
        <div class="card-top"><h3>${escapeHtml(card.title || "业务记录")}</h3><span class="tag ${tagClass}">${escapeHtml(card.label || "已处理")}</span></div>
        <div class="history-body">${card.html || ""}</div>
        ${actions ? `<div class="card-actions compact-actions">${actions}</div>` : ""}
      </div>`;
  }).join("");
}

function addInventoryHistory(keyword, list) {
  const total = (list || []).reduce((sum, item) => sum + Number(item.total_stock || 0), 0);
  const first = (list || [])[0];
  const html = `
    <p><b>${escapeHtml(keyword || "库存")}</b></p>
    <p>共 ${escapeHtml((list || []).length)} 个商品，合计 ${escapeHtml(total)} 套</p>
    ${first ? `<p class="muted">最多：${escapeHtml(first.title || "")} ${escapeHtml(first.total_stock || 0)} 套</p>` : '<p class="muted">没有查到有库存记录</p>'}
  `;
  pushBusinessHistory({ type: "inventory", title: "库存查询", label: keyword || "库存", html });
}

function parseOrderItemsFromText(response = "") {
  const lines = String(response || "").split(/\r?\n/);
  return lines.map((line) => {
    const text = line.trim();
    const match = text.match(/^(.+?)[:：]\s*([0-9.]+)\s*([^\s×xX]*)\s*[×xX]\s*([0-9.]+)\s*元?/);
    if (!match) return null;
    const nameParts = match[1].trim().split(/\s+/);
    return {
      name: nameParts[0] || match[1].trim(),
      color: nameParts.slice(1).join(" "),
      qty: Number(match[2]),
      unit: match[3] || "",
      price: Number(match[4])
    };
  }).filter(Boolean);
}

function parseOrderIdFromText(response = "", type = "") {
  const text = String(response || "");
  const sales = text.match(/销售单号[:： \t]*([A-Za-z0-9_-]+)/);
  if (sales) return sales[1];
  const workflowNo = text.match(/单号[:： \t]*([A-Za-z0-9_-]+)/);
  if (workflowNo && type !== "sales") return workflowNo[1];
  const workflow = text.match(/工作流订单(?:号|ID)[:：# \t]*([A-Za-z0-9_-]+)/);
  if (workflow && type !== "sales") return workflow[1];
  return "";
}

function responseHasCreatedWorkflow(response = "") {
  const text = String(response || "");
  return /工作流订单/.test(text) && /(创建成功|已创建|单号)/.test(text);
}

function parseCustomerFromText(response = "") {
  const match = String(response || "").match(/客户[:：]\s*([^\n\r]+)/);
  return match ? match[1].trim() : "";
}

function parseWorkflowItemsFromText(response = "") {
  const text = String(response || "");
  const numbered = text.split(/\r?\n/).map((line) => {
    const match = line.trim().match(/^\d+[.、]\s*([^|]+)\|\s*([^|]+?)\s*\|\s*([0-9.]+)\s*(?:\|\s*单号\s*([A-Za-z0-9_-]+))?/);
    if (!match) return null;
    const goodsParts = match[2].trim().split(/\s+/);
    return {
      customer: match[1].trim(),
      name: goodsParts[0] || match[2].trim(),
      color: goodsParts.slice(1).join(" "),
      qty: Number(match[3]),
      id: match[4] || ""
    };
  }).filter(Boolean);
  if (numbered.length) return numbered;

  const customer = parseCustomerFromText(text);
  const goodsMatch = text.match(/商品[:：]\s*([^\n\r]+)/);
  const qtyMatch = text.match(/数量[:：]\s*([0-9.]+)/);
  if (!customer && !goodsMatch && !qtyMatch) return [];
  const goodsParts = (goodsMatch ? goodsMatch[1].trim() : "").split(/\s+/);
  return [{
    customer,
    name: goodsParts[0] || "",
    color: goodsParts.slice(1).join(" "),
    qty: qtyMatch ? Number(qtyMatch[1]) : ""
  }];
}

function workflowIdsFromItems(items = []) {
  return [...new Set((items || []).map((item) => item && item.id).filter(Boolean).map(String))];
}

function orderItemsHtml(items = []) {
  if (!items.length) return "";
  return `<div class="history-items">${items.slice(0, 4).map((item) => {
    const title = [item.name || item.title || item.goods_name || "商品", item.color || item.spec || ""].filter(Boolean).join(" ");
    const qty = item.qty ?? item.quantity ?? item.buy_number ?? "";
    const unit = item.unit || "";
    const price = item.price ?? item.unit_price ?? "";
    const customer = item.customer ? `<small>${escapeHtml(item.customer)}</small>` : "";
    return `<div class="history-item"><span>${escapeHtml(title)}${customer}</span><strong>${escapeHtml(qty)}${escapeHtml(unit)}</strong>${price !== "" ? `<em>¥${escapeHtml(price)}</em>` : ""}</div>`;
  }).join("")}${items.length > 4 ? `<p class="muted">还有 ${escapeHtml(items.length - 4)} 项商品</p>` : ""}</div>`;
}

function addOrderHistory(session = state.session, response = "") {
  const order = session.last_order || {};
  const responseText = String(response || "");
  if (!order.type) {
    const firstLine = responseText.split("\n")[0] || "已处理";
    const compactHtml = `<p class="muted">${escapeHtml(firstLine)}</p>`;
    if (/盘点/.test(responseText) && /(完成|成功)/.test(responseText)) {
      pushBusinessHistory({ type: "stocktaking", title: "盘点", label: "已完成", html: compactHtml });
      return;
    }
    if (/(调货|调拨)/.test(responseText) && /(完成|成功)/.test(responseText)) {
      pushBusinessHistory({ type: "transfer", title: "调货", label: "已完成", html: compactHtml });
      return;
    }
    if (/进货/.test(responseText) && /(完成|成功)/.test(responseText)) {
      pushBusinessHistory({ type: "purchase", title: "进货", label: "已完成", html: compactHtml });
      return;
    }
  }
  const type = order.type || (response.includes("工作流") ? "workflow" : (response.includes("销售单") || response.includes("开单") ? "sales" : ""));
  if (!type) return;
  const workflowItems = type === "workflow" ? parseWorkflowItemsFromText(response) : [];
  const workflowIds = type === "workflow" ? workflowIdsFromItems(workflowItems) : [];
  const id = order.id || workflowIds[0] || parseOrderIdFromText(response, type);
  const actionId = type === "workflow" && workflowIds.length > 1 ? workflowIds.join(",") : id;
  const historyId = `biz_${type}_${id || Date.now()}_${Math.random().toString(16).slice(2)}`;
  const title = type === "sales" ? "销售单" : "工作流订单";
  const customer = order.customer || (workflowItems[0] && workflowItems[0].customer) || parseCustomerFromText(response);
  const items = order.products || order.items || (type === "workflow" ? workflowItems : parseOrderItemsFromText(response));
  const goods = order.goods_name || order.product_name || (!items.length && workflowItems[0] ? workflowItems[0].name : "");
  const total = order.total ?? "";
  const html = `
    ${workflowIds.length > 1 ? `<p class="muted">单号：${escapeHtml(workflowIds.join("、"))}</p>` : (id ? `<p class="muted">单号：${escapeHtml(id)}</p>` : "")}
    ${customer ? `<p>客户：${escapeHtml(customer)}</p>` : ""}
    ${goods ? `<p>商品：${escapeHtml(goods)}</p>` : ""}
    ${orderItemsHtml(items)}
    ${total !== "" ? `<p class="muted">合计：¥${escapeHtml(total)}</p>` : ""}
    <p class="muted">${escapeHtml(String(response || "").split("\n")[0] || "已处理")}</p>
  `;
  const actions = id
    ? (type === "sales"
      ? `<button class="danger" onclick="deleteSalesFromHistory('${escapeAttr(id)}', '${escapeAttr(historyId)}')">删除</button>`
      : `<button class="danger" onclick="deleteWorkflowFromHistory('${escapeAttr(actionId)}', '${escapeAttr(historyId)}')">删除</button>`)
    : "";
  pushBusinessHistory({ id: historyId, businessKey: actionId ? `${type}:${actionId}` : "", orderId: actionId, type, title, label: "已创建", html, actions });
}

function closeBusinessConfirm() {
  const mask = $("businessConfirmMask");
  if (mask) mask.classList.remove("open");
}

function showBusinessConfirm(session = state.session) {
  if (!session || !session.has_pending || !isConfirmablePending(session)) {
    closeBusinessConfirm();
    return;
  }
  let mask = $("businessConfirmMask");
  if (!mask) {
    mask = document.createElement("div");
    mask.id = "businessConfirmMask";
    mask.className = "confirm-mask business-confirm-mask";
    mask.innerHTML = `
      <div class="confirm-box business-confirm-box">
        <h3 class="confirm-title" id="businessConfirmTitle">业务确认</h3>
        <div class="confirm-message" id="businessConfirmBody"></div>
        <div class="confirm-actions business-confirm-actions">
          <button id="businessConfirmCancel">取消</button>
          <button class="danger-confirm" id="businessConfirmOk">确认执行</button>
        </div>
      </div>`;
    document.body.appendChild(mask);
    $("businessConfirmCancel").addEventListener("click", cancelBusinessCard);
    $("businessConfirmOk").addEventListener("click", confirmBusinessCard);
  }
  const title = $("businessConfirmTitle");
  const body = $("businessConfirmBody");
  const ok = $("businessConfirmOk");
  if (title) title.textContent = pendingTitle(session);
  if (body) body.innerHTML = pendingEditableHtml(session);
  if (ok) {
    const stateData = session.state || {};
    const action = pendingActionOf(session);
    ok.textContent = action.includes("confirm_image_workflow_orders")
      ? "提交工作流订单"
      : (action.includes("confirm_image_sales") ? "继续开单" : (action.includes("confirm_product_name") ? "继续匹配" : "确认执行"));
  }
  requestAnimationFrame(() => mask.classList.add("open"));
}

function closeInventoryPopup() {
  const mask = $("inventoryPopupMask");
  if (mask) mask.classList.remove("open");
}

function showInventoryPopup(keyword, list) {
  let mask = $("inventoryPopupMask");
  if (!mask) {
    mask = document.createElement("div");
    mask.id = "inventoryPopupMask";
    mask.className = "confirm-mask inventory-popup-mask";
    mask.innerHTML = `
      <div class="confirm-box inventory-popup-box">
        <h3 class="confirm-title" id="inventoryPopupTitle">库存查询</h3>
        <div class="confirm-message" id="inventoryPopupBody"></div>
        <div class="confirm-actions inventory-popup-actions">
          <button class="danger-confirm" id="inventoryPopupClose">关闭</button>
        </div>
      </div>`;
    document.body.appendChild(mask);
    $("inventoryPopupClose").addEventListener("click", closeInventoryPopup);
    mask.addEventListener("click", (event) => {
      if (event.target === mask) closeInventoryPopup();
    });
  }
  const title = $("inventoryPopupTitle");
  const body = $("inventoryPopupBody");
  const rows = Array.isArray(list) ? list : [];
  const total = rows.reduce((sum, item) => sum + Number(item.total_stock || 0), 0);
  if (title) title.textContent = `库存查询：${keyword || "库存"}`;
  if (body) {
    body.innerHTML = `
      <div class="inventory-popup-summary">
        <span>商品 ${escapeHtml(rows.length)}</span>
        <span>合计 ${escapeHtml(total)} 套</span>
      </div>
      <div class="inventory-popup-list">
        ${rows.length ? rows.slice(0, 3).map((card) => inventoryCardHtml(card, true)).join("") : '<div class="empty">没有查到有库存记录</div>'}
      </div>
      ${rows.length > 3 ? `<p class="muted">还有 ${escapeHtml(rows.length - 3)} 个商品，已缩略显示在右侧历史卡。</p>` : ""}
    `;
  }
  requestAnimationFrame(() => mask.classList.add("open"));
}

function pendingTitle(session = state.session) {
  const stateData = session.state || {};
  const action = pendingActionOf(session);
  const intent = session.pending_intent || "";
  if (intent.includes("bag_upload") || action.includes("bag_")) {
    if (action.includes("collect_bag_type")) return "选择泡袋模板";
    if (action.includes("collect_bag_archive")) return "上传泡袋压缩包";
    if (action.includes("collect_bag_name")) return "填写泡袋名称";
    if (action.includes("collect_bag_image")) return "上传泡袋图片";
    return "泡袋新品确认";
  }
  if (action.includes("confirm_image_workflow_orders")) return "OCR识别结果";
  if (action.includes("confirm_image_sales")) return "是否继续开销售单";
  if (action.includes("confirm_product_name")) return "商品匹配确认";
  if (action.includes("transfer")) return "调货确认";
  if (action.includes("purchase")) return "进货确认";
  if (action.includes("stocktaking") || intent.includes("stocktaking")) return "盘点确认";
  if (action.includes("workflow") || intent.includes("workflow")) return "工作流订单确认";
  if (action.includes("sales") || action.includes("order") || intent.includes("sales") || intent.includes("order")) return "销售单确认";
  if (action.includes("product") || intent.includes("product")) return "商品确认";
  return "AI 业务确认";
}

function renderBusinessContext() {
  const context = $("contextPanel");
  const drawerBody = $("drawerBody");
  const session = state.session || {};
  const data = session.state || session.last_extraction || {};
  const rows = flattenRows(data).slice(0, 18);
  const html = businessHistoryHtml();
  if (session.has_pending && isConfirmablePending(session)) showBusinessConfirm(session);
  else closeBusinessConfirm();
  if (context) {
    let slot = $("contextCards");
    if (!slot) {
      slot = document.createElement("div");
      slot.id = "contextCards";
      const head = context.querySelector(".panel-title");
      if (head) head.insertAdjacentElement("afterend", slot);
      else context.prepend(slot);
    }
    slot.innerHTML = html;
  }
  if (drawerBody) {
    drawerBody.innerHTML = session.has_pending
      ? `<div class="business-card">${pendingSummaryHtml(session)}</div>`
      : (rows.length ? `<div class="business-card"><div class="card-top"><h3>最近识别结果</h3><span class="tag blue">已识别</span></div>${kvRows(rows)}</div>` : html);
  }
}

function openDrawer(mode = "ai", row = {}) {
  state.drawerMode = mode;
  const drawer = $("drawer");
  const mask = $("drawerMask");
  const title = $("drawerTitle");
  const subtitle = $("drawerSubtitle");
  const body = $("drawerBody");
  const save = $("saveDrawer");
  if (!drawer || !mask || !body) return;
  if (mode === "ai") {
    if (title) title.textContent = "业务确认";
    if (subtitle) subtitle.textContent = "核对后确认执行，或修改后再提交。";
    if (save) save.style.display = "none";
    renderBusinessContext();
  } else if (mode === "workflow") {
    if (title) title.textContent = row.id ? "编辑工作流订单" : "新建工作流订单";
    if (subtitle) subtitle.textContent = "保存会直接调用工作流订单 API。";
    if (save) save.style.display = "";
    body.innerHTML = workflowForm(row);
  } else if (mode === "product") {
    if (title) title.textContent = row.id ? "编辑商品" : "新增商品";
    if (subtitle) subtitle.textContent = "保存会直接调用商品 API。";
    if (save) save.style.display = "";
    body.innerHTML = productForm(row);
    setSelectedProductCategories(Array.isArray(row.product_category_ids) ? row.product_category_ids : []);
    setProductDetailImages(htmlToImages(row.content || ""));
  } else if (mode === "inventory_action") {
    const isPurchase = row.type === "purchase";
    const isStocktaking = row.type === "stocktaking";
    if (title) title.textContent = isPurchase ? "进货入库" : (isStocktaking ? "盘点库存" : "调货");
    if (subtitle) subtitle.textContent = isPurchase
      ? "确认商品、颜色、数量和入库仓库。"
      : (isStocktaking ? "填写盘点后的目标库存数量。" : "确认商品、颜色、数量和仓库方向。");
    if (save) {
      save.style.display = "";
      save.textContent = isPurchase ? "确认进货" : (isStocktaking ? "确认盘点" : "确认调货");
    }
    body.innerHTML = inventoryActionForm(row);
  } else if (mode === "sales_detail") {
    if (title) title.textContent = "销售单明细";
    if (subtitle) subtitle.textContent = "";
    if (save) save.style.display = "none";
    body.innerHTML = salesDetailHtml(row);
  } else if (mode === "customer_sales") {
    if (title) title.textContent = "客户销售单";
    if (subtitle) subtitle.textContent = row.customerName || "";
    if (save) save.style.display = "none";
    body.innerHTML = '<div class="empty">正在加载销售单...</div>';
  } else if (mode === "customer_balance_ledger") {
    if (title) title.textContent = "余额明细";
    if (subtitle) subtitle.textContent = row.customerName || "";
    if (save) save.style.display = "none";
    body.innerHTML = '<div class="empty">正在加载余额明细...</div>';
  } else if (mode === "account_admin") {
    if (title) title.textContent = "账号审批";
    if (subtitle) subtitle.textContent = "新注册账号通过后才能进入系统。";
    if (save) save.style.display = "none";
    body.innerHTML = '<div class="empty">正在加载待审批账号...</div>';
  }
  document.body.classList.add("modal-open");
  drawer.classList.add("open");
  mask.classList.add("open");
}

function closeDrawer() {
  const drawer = $("drawer");
  const mask = $("drawerMask");
  if (drawer) drawer.classList.remove("open");
  if (mask) mask.classList.remove("open");
  const save = $("saveDrawer");
  if (save) save.textContent = "保存";
  document.body.classList.remove("modal-open");
}

function formatTime(ts) {
  const num = Number(ts || 0);
  if (!num) return "-";
  return new Date(num * 1000).toLocaleString();
}

async function initWebUser() {
  try {
    const res = await api("/api/web-auth/me");
    state.currentUser = res.data && res.data.user;
    document.body.classList.toggle("is-admin", !!(state.currentUser && Number(state.currentUser.is_admin) === 1));
  } catch (err) {
    console.warn(err);
  }
}

async function openAccountAdmin() {
  openDrawer("account_admin");
  await loadApprovalUsers();
}

async function loadApprovalUsers(status = "pending") {
  const body = $("drawerBody");
  if (body) body.innerHTML = '<div class="empty">\u6b63\u5728\u52a0\u8f7d\u5f85\u5ba1\u6279\u8d26\u53f7...</div>';
  try {
    const res = await api(`/api/web-auth/users?${query({ status })}`);
    const list = (res.data && res.data.items) || [];
    if (!body) return;
    if (!list.length) {
      body.innerHTML = '<div class="empty">\u6682\u65e0\u5f85\u5ba1\u6279\u8d26\u53f7</div>';
      return;
    }
    body.innerHTML = `<div class="approval-list">${list.map((user) => `
      <div class="approval-card">
        <div><strong>${escapeHtml(user.display_name || user.username || "")}</strong><div class="approval-meta">${escapeHtml(user.username || "")}<br>\u6ce8\u518c\u65f6\u95f4\uff1a${escapeHtml(formatTime(user.created_at))}</div></div>
        <div class="approval-actions">
          <button type="button" class="primary" data-approve-user-id="${Number(user.id)}">\u901a\u8fc7</button>
          <button type="button" class="danger" data-reject-user-id="${Number(user.id)}">\u62d2\u7edd</button>
        </div>
      </div>
    `).join("")}</div>`;
  } catch (err) {
    if (body) body.innerHTML = `<div class="empty">\u52a0\u8f7d\u5931\u8d25\uff1a${escapeHtml(err.message)}</div>`;
    throw err;
  }
}

async function approveWebUser(id) {
  await api(`/api/web-auth/users/${id}/approve`, { method: "POST" });
  toast("\u8d26\u53f7\u5df2\u901a\u8fc7");
  await loadApprovalUsers();
}

async function rejectWebUser(id) {
  await api(`/api/web-auth/users/${id}/reject`, { method: "POST" });
  toast("\u8d26\u53f7\u5df2\u62d2\u7edd");
  await loadApprovalUsers();
}


async function confirmBusinessCard() {
  try {
    await savePendingEdits();
  } catch (err) {
    toast(`保存修改失败：${err.message}`, true);
    return;
  }
  closeBusinessConfirm();
  sendChat("确认");
}

function cancelBusinessCard() {
  closeBusinessConfirm();
  sendChat("取消");
}

function editBusinessCard() {
  closeBusinessConfirm();
  $("chatInput").value = "修改：";
  $("chatInput").focus();
}

function inventoryKeywordFromMessage(message) {
  const text = String(message || "").trim();
  if (!/(库存|有货|查货|剩多少|还有多少)/.test(text)) return "";
  return text
    .replace(/^(帮我|麻烦|请|查一下|查下|查询|查|看一下|看看)/, "")
    .replace(/(库存|有货吗|有没有货|有货|查货|剩多少|还有多少|多少套|多少)$/g, "")
    .replace(/[，。！？?]/g, " ")
    .trim();
}

async function sendChat(text) {
  if (state.isSending) return;
  const input = $("chatInput");
  const message = (text || input.value || "").trim();
  if (!message && !state.pendingFile) return;
  if (message) addMessage("user", message);
  input.value = "";
  state.isSending = true;
  setBusy("sendButton", true);
  let pendingMessage = null;
  try {
    const inventoryKeyword = inventoryKeywordFromMessage(message);
    if (inventoryKeyword) {
      state.session = {};
      closeDrawer();
      setStatus("查询库存中");
      pendingMessage = addMessage("assistant", "正在查询库存...");
      await loadContextInventory(inventoryKeyword);
      updateMessage(pendingMessage, `库存查询完成：${inventoryKeyword}`);
      setStatus("库存已更新");
      return;
    }
    if (state.pendingFile) {
      const fileToUpload = state.pendingFile;
      state.pendingFile = null;
      clearPreview();
      const isImageFile = fileToUpload && ((fileToUpload.type || "").startsWith("image/") || /\.(png|jpe?g|webp|bmp|gif)$/i.test(fileToUpload.name || ""));
      const localPreviewUrl = isImageFile ? URL.createObjectURL(fileToUpload) : "";
      const uploadLabel = isImageFile ? "上传图片" : "上传附件";
      const userImageMessage = addMessage("user", `${uploadLabel}：${fileToUpload.name || "附件"}${localPreviewUrl ? `
${localPreviewUrl}` : ""}`, false);
      pendingMessage = addMessage("assistant", isImageFile ? "正在识别图片..." : "正在处理附件...");
      await uploadImage(fileToUpload, userImageMessage, localPreviewUrl);
      if (pendingMessage) {
        pendingMessage.remove();
        persistMessages();
      }
      pendingMessage = null;
    }
    if (message) {
      setStatus("北极星思考中");
      pendingMessage = addMessage("assistant", "正在处理中...");
      const res = await api("/api/agent/chat", {
        method: "POST",
        body: { message, session_id: state.sessionId, user_id: "web_user" }
      });
      const data = res.data || {};
      state.session = data.session || {};
      const responseText = data.response || "已处理";
      updateMessage(pendingMessage, responseText);
      pendingMessage = null;
      renderBusinessContext();
      if (!(state.session && state.session.has_pending) || responseHasCreatedWorkflow(responseText)) {
        addOrderHistory(state.session, responseText);
      }
      setStatus("对话完成");
    }
    refreshLight();
  } catch (err) {
    updateMessage(pendingMessage, `处理失败：${err.message}`);
    toast(err.message, true);
    setStatus("处理失败");
  } finally {
    state.isSending = false;
    setBusy("sendButton", false);
  }
}

async function uploadImage(file, userImageMessage = null, localPreviewUrl = "") {
  const form = new FormData();
  form.append("image", file, file.name || `paste_${Date.now()}.png`);
  form.append("session_id", state.sessionId);
  setStatus("图片识别中");
  const res = await api("/api/images/upload", { method: "POST", body: form });
  const data = res.data || {};
  state.session = data.session || {};
  const previewUrl = data.result && data.result.preview_url;
  if (userImageMessage && previewUrl) {
    updateMessage(userImageMessage, `上传图片：${file.name || "截图"}
${previewUrl}`);
  } else if (userImageMessage) {
    updateMessage(userImageMessage, `上传附件：${file.name || "附件"}`);
  } else if (!userImageMessage) {
    addMessage("user", `${previewUrl ? "上传图片" : "上传附件"}：${file.name || "附件"}${previewUrl ? `
${previewUrl}` : ""}`);
  }
  if (localPreviewUrl) setTimeout(() => URL.revokeObjectURL(localPreviewUrl), 1000);
  const responseText = data.response || "图片已识别";
  addMessage("assistant", responseText);
  renderBusinessContext();
  if (!(state.session && state.session.has_pending) || responseHasCreatedWorkflow(responseText)) {
    addOrderHistory(state.session, responseText);
  }
}

function setBusy(id, yes) {
  const el = $(id);
  if (el) el.classList.toggle("loading", !!yes);
}

function showPreview(file) {
  const tray = $("attachmentTray");
  const composer = document.querySelector(".composer");
  if (tray) {
    if (tray.dataset.previewUrl) URL.revokeObjectURL(tray.dataset.previewUrl);
    const isImage = file && ((file.type || "").startsWith("image/") || /\.(png|jpe?g|webp|bmp|gif)$/i.test(file.name || ""));
    if (isImage) {
      const url = URL.createObjectURL(file);
      tray.dataset.previewUrl = url;
      tray.innerHTML = `<span class="attachment-chip image-chip"><img src="${url}" alt=""><span>${escapeHtml(file.name || "截图")}</span></span>`;
    } else {
      tray.dataset.previewUrl = "";
      tray.innerHTML = `<span class="attachment-chip"><span>${escapeHtml(file.name || "附件")}</span></span>`;
    }
  }
  if (composer) composer.classList.add("has-attachment");
}

function clearPreview() {
  const tray = $("attachmentTray");
  const composer = document.querySelector(".composer");
  if (tray) {
    if (tray.dataset.previewUrl) URL.revokeObjectURL(tray.dataset.previewUrl);
    tray.dataset.previewUrl = "";
    tray.innerHTML = "";
  }
  if (composer) composer.classList.remove("has-attachment");
  if ($("attachmentInput")) $("attachmentInput").value = "";
}

function insertCommandPrefix(command) {
  const input = $("chatInput");
  if (!input) return;
  const value = input.value.trim();
  const prefixPattern = /^(开单|盘点|调货|进货|工作流|查库存)\b/;
  input.value = value
    ? (prefixPattern.test(value) ? value.replace(prefixPattern, command) : `${command} ${value}`)
    : `${command} `;
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
}

const SALES_CARD_HEIGHT_FALLBACK = 352;
const SALES_GRID_GAP = 14;
const WORKFLOW_CARD_HEIGHT_FALLBACK = 398;
const DASHBOARD_REFRESH_MS = 30000;

function nextFrame() {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
}

function skeletonCards(count) {
  return Array.from({ length: count }, () => `
    <div class="skeleton-card">
      <div class="sk-head"><div class="skeleton sk-line w60"></div><div class="skeleton sk-line w40" style="width:48px;height:18px;border-radius:99px;"></div></div>
      <div class="skeleton sk-line w40"></div>
      <div class="skeleton sk-line w80"></div>
      <div class="sk-row"><div class="skeleton sk-line" style="width:50px;"></div><div class="skeleton sk-line" style="width:60px;"></div></div>
      <div class="sk-actions"><div class="skeleton sk-btn"></div><div class="skeleton sk-btn"></div></div>
    </div>`).join("");
}

async function loadDashboardSummary() {
  try {
    const res = await api("/api/dashboard/summary");
    const data = res.data || {};
    const countEl = $("todaySalesCount");
    const amountEl = $("todaySalesAmount");
    const pendingEl = $("pendingWorkflowCount");
    if (countEl) countEl.textContent = `${Number(data.today_sales_count || 0)} 张`;
    if (amountEl) amountEl.textContent = `¥${money(data.today_sales_amount || 0)}`;
    if (pendingEl) pendingEl.textContent = `${Number(data.pending_workflow_count || 0)} 单`;
  } catch (err) {
    console.warn("dashboard summary failed", err);
    const countEl = $("todaySalesCount");
    const amountEl = $("todaySalesAmount");
    const pendingEl = $("pendingWorkflowCount");
    if (countEl && !countEl.textContent.trim()) countEl.textContent = "0 张";
    if (amountEl && !amountEl.textContent.trim()) amountEl.textContent = "¥0.00";
    if (pendingEl && !pendingEl.textContent.trim()) pendingEl.textContent = "0 单";
  }
}

async function loadSales(page) {
  if (page !== undefined) state.salesPage = page;
  await nextFrame();
  state.salesPageSize = calculateSalesPageSize();
  const keyword = ($("salesKeyword") && $("salesKeyword").value.trim()) || "";
  const target = $("salesList");
  if (target) target.innerHTML = skeletonCards(Math.min(state.salesPageSize, 8));
  try {
    const res = await api(`/api/sales/cards?${query({ keyword, page: state.salesPage, page_size: state.salesPageSize })}`);
    const list = normalizeList(res);
    state.lastSalesCards = list;
    state.salesTotal = (res.data && res.data.total) || list.length;
    setBadge("sales", state.salesTotal);
    state.salesLoadedAt = Date.now();
    renderSales(list, target);
    renderSalesPager();
  } catch (err) {
    if (target) target.innerHTML = `<div class="empty">加载失败：${escapeHtml(err.message)}</div>`;
  }
}

function renderSalesPager() {
  const pager = $("salesPager");
  if (!pager) return;
  const totalPages = Math.max(1, Math.ceil(state.salesTotal / state.salesPageSize));
  if (totalPages <= 1) { pager.innerHTML = ""; return; }
  pager.innerHTML = `
    <button ${state.salesPage <= 1 ? "disabled" : ""} onclick="loadSales(${state.salesPage - 1})">上一页</button>
    <span class="page-info">${state.salesPage} / ${totalPages} · 每页 ${state.salesPageSize}</span>
    <button ${state.salesPage >= totalPages ? "disabled" : ""} onclick="loadSales(${state.salesPage + 1})">下一页</button>
  `;
}
window.loadSales = loadSales;

function gridColumnCount(target) {
  if (!target) return 1;
  const styles = window.getComputedStyle(target);
  const template = styles.gridTemplateColumns || "";
  const computedColumns = template.split(" ").filter((item) => item && item !== "none").length;
  const rawMin = styles.getPropertyValue("--card-min-width").trim();
  const minWidth = Number.parseFloat(rawMin) || 360;
  const gap = Number.parseFloat(styles.columnGap || styles.gap) || SALES_GRID_GAP;
  const width = target.clientWidth || target.getBoundingClientRect().width || 0;
  const estimatedColumns = width > 0 ? Math.floor((width + gap) / (minWidth + gap)) : 1;
  return Math.max(1, computedColumns, estimatedColumns);
}

function calculateSalesPageSize() {
  const target = $("salesList");
  const columns = gridColumnCount(target);
  if (!target) return Math.max(6, Math.min(15, columns * 3));
  const rect = target.getBoundingClientRect();
  const cardHeight = salesCardHeight(target);
  const available = Math.max(cardHeight, window.innerHeight - rect.top - 22);
  const rows = Math.max(1, Math.floor((available + SALES_GRID_GAP) / (cardHeight + SALES_GRID_GAP)));
  return Math.max(columns, Math.min(60, rows * columns));
}

function salesCardHeight(target) {
  const raw = window.getComputedStyle(target).getPropertyValue("--sales-card-height").trim();
  const value = Number.parseFloat(raw);
  return Number.isFinite(value) ? value : SALES_CARD_HEIGHT_FALLBACK;
}

let salesResizeTimer = null;
function handleSalesResize() {
  clearTimeout(salesResizeTimer);
  salesResizeTimer = setTimeout(() => {
    const salesView = $("sales");
    if (salesView && salesView.classList.contains("active")) {
      const nextSize = calculateSalesPageSize();
      if (Math.abs(nextSize - state.salesPageSize) >= 1) loadSales(1);
    }
    const ordersView = $("orders");
    if (ordersView && ordersView.classList.contains("active")) {
      const nextSize = calculateWorkflowPageSize();
      if (Math.abs(nextSize - state.workflowPageSize) >= 1) loadWorkflow(1);
    }
    const inventoryView = $("inventory");
    if (inventoryView && inventoryView.classList.contains("active")) {
      const nextSize = calculateInventoryPageSize();
      if (Math.abs(nextSize - state.inventoryPageSize) >= 1) renderInventoryPage(1);
    }
    const productsView = $("products");
    if (productsView && productsView.classList.contains("active")) {
      const nextSize = calculateProductPageSize();
      if (Math.abs(nextSize - state.productPageSize) >= 1) loadProducts(1);
    }
  }, 180);
}

function scheduleActiveListRefresh(name) {
  if (name !== "sales" && name !== "orders" && name !== "inventory" && name !== "products") return;
  nextFrame().then(() => {
    if (name === "sales" && $("sales") && $("sales").classList.contains("active") && state.lastSalesCards.length) {
      const nextSize = calculateSalesPageSize();
      if (nextSize !== state.salesPageSize) loadSales(1);
    }
    if (name === "orders" && $("orders") && $("orders").classList.contains("active") && state.lastWorkflowCards.length) {
      const nextSize = calculateWorkflowPageSize();
      if (nextSize !== state.workflowPageSize) loadWorkflow(1);
    }
    if (name === "inventory" && $("inventory") && $("inventory").classList.contains("active") && state.lastInventoryCards.length) {
      const nextSize = calculateInventoryPageSize();
      if (nextSize !== state.inventoryPageSize) renderInventoryPage(1);
    }
    if (name === "products" && $("products") && $("products").classList.contains("active") && state.lastProducts.length) {
      const nextSize = calculateProductPageSize();
      if (nextSize !== state.productPageSize) loadProducts(1);
    }
  });
}

function renderSales(list, target, compact = false) {
  if (!target) return;
  target.innerHTML = list.length ? list.map((card) => {
    const id = Number(card.id || 0);
    const products = normalizeProducts(card.products);
    const rows = products.slice(0, compact ? 1 : 2);
    const productTotal = products.reduce((sum, p) => sum + quantityNumber(p.quantity ?? p.buy_number ?? p.num), 0);
    const count = productTotal || quantityNumber(card.total_quantity ?? card.buy_number_count ?? card.quantity ?? card.number);
    const hasMore = products.length > rows.length && !compact;
    const isDeleted = ["canceled", "deleted"].includes(String(card.status || "")) || /取消|删除/.test(String(card.status_text || ""));
    const statusTone = isDeleted ? "gray" : (String(card.status_text || "").includes("已") ? "green" : "amber");
    const productHtml = rows.length
      ? '<div class="product-lines' + (hasMore ? ' has-more' : '') + '" id="plines' + id + '">' + rows.map(function(p) {
        const qty = p.quantity ?? p.buy_number ?? p.num ?? "";
        const qtyNumber = Number(qty || 0);
        const totalNumber = Number(p.total_price || 0);
        const unitNumber = Number(p.price || 0) || (qtyNumber > 0 ? totalNumber / qtyNumber : 0);
        const subtotal = totalNumber || (unitNumber * qtyNumber);
        return '<div class="product-row"><span class="product-name">' + escapeHtml([p.title, p.spec].filter(Boolean).join(" ")) + '</span><span class="product-qty">x' + escapeHtml(qty || "-") + '</span><span class="product-unit-price">¥' + money(unitNumber) + '</span><span class="product-price">¥' + money(subtotal) + '</span></div>';
      }).join("") + (products.length > rows.length && !compact ? '<button class="expand-btn" onclick="event.stopPropagation(); openSalesDetail(' + id + ')">' + products.length + ' 项，查看全部</button>' : "") + '</div>'
      : '<div class="muted">' + escapeHtml(card.product_summary || "暂无商品信息") + '</div>';
    return `
      <div class="business-card sales-card" data-open-sales-detail="${id}">
        <div class="customer-name"><strong>${escapeHtml(card.customer_name || "客户")}</strong><span class="tag ${statusTone}">${escapeHtml(card.status_text || "销售单")}</span></div>
        <div class="muted">${escapeHtml(card.sales_no || `#${id}`)}</div>
        ${productHtml}
        <div class="kv">
          <div class="kv-row"><span>总数量</span><strong>${escapeHtml(quantityText(count))}</strong></div>
          <div class="kv-row"><span>总价</span><strong>¥${money(card.total_price || card.price)}</strong></div>
          <div class="kv-row"><span>付款</span><strong>${escapeHtml(card.pay_status_text || payStatusText(card.pay_status))}</strong></div>
          <div class="kv-row"><span>开单人</span><strong>${escapeHtml(operatorText(card))}</strong></div>
          <div class="kv-row"><span>时间</span><strong>${escapeHtml(card.date_text || card.date || card.add_time || "未记录")}</strong></div>
        </div>
        <div class="card-actions">
          <button class="primary" onclick="event.stopPropagation(); printSales(${id})">打印</button>
          ${isDeleted ? '<button disabled>已删除</button>' : `<button class="danger" onclick="event.stopPropagation(); deleteSales(${id})">删除</button>`}
        </div>
      </div>`;
  }).join("") : '<div class="empty">暂无销售单</div>';
}

function salesDetailHtml(card) {
  const products = normalizeProducts(card.products);
  const detailIsDeleted = String(card.status || "") === "deleted" || Boolean(card.deleted_at);
  const detailIsCanceled = String(card.status || "") === "canceled" && !detailIsDeleted;
  const rows = products.map((p, index) => {
    const qty = p.quantity ?? p.buy_number ?? p.num ?? "";
    const title = [p.title, p.spec].filter(Boolean).join(" ");
    return `
      <tr>
        <td>${index + 1}</td>
        <td>${escapeHtml(title || "商品")}</td>
        <td>${escapeHtml(qty || "-")}</td>
        <td>¥${money(p.price || 0)}</td>
        <td>¥${money(p.total_price || (Number(p.price || 0) * Number(qty || 0)))}</td>
      </tr>`;
  }).join("");
  const ledgerRows = Array.isArray(card.inventory_ledgers) ? card.inventory_ledgers : [];
  const ledgerHtml = ledgerRows.length ? ledgerRows.map((row) => `
    <div class="sales-flow-row">
      <strong>${escapeHtml(row.biz_type_text || bizTypeText(row.biz_type))}</strong>
      <span>${escapeHtml(row.warehouse_name || "仓库")} · ${escapeHtml(row.change_qty || "")} · ${escapeHtml(nativeDateText(row.occurred_at))} · ${escapeHtml(operatorText(row))}</span>
      <em>${escapeHtml(row.note || row.ledger_no || "")}</em>
    </div>`).join("") : '<div class="product-media-empty">暂无库存流水</div>';
  const deleteFlow = [
    "删除按钮只走自有库，不调用旧 ERP。",
    "系统会把销售单改为已删除，并从普通列表、客户消费、余额欠款里隐藏。",
    "删除时按原 sales_out 库存流水回滚，标签等不管库存的商品不会被加回库存。",
    "如果这单是余额付款，会同步写余额退回流水；月结/未付只删除应收，不扣余额。"
  ];
  return `
    <div class="sales-detail-bill">
      <div class="sales-detail-head">
        <div>
          <strong>${escapeHtml(card.customer_name || "客户")}</strong>
          <p>${escapeHtml(card.sales_no || "")}</p>
        </div>
        <span class="tag ${["canceled", "deleted"].includes(String(card.status || "")) ? "gray" : "green-outline"}">${escapeHtml(card.status_text || "销售单")}</span>
      </div>
      <div class="record-metrics sales-detail-metrics">
        ${metricHtml("付款状态", [card.pay_status_text || payStatusText(card.pay_status), card.pay_type_text || payTypeText(card.pay_type)].filter(Boolean).join(" / "))}
        ${metricHtml("应收金额", `¥${money(card.receivable_amount || card.total_price || 0)}`, "accent")}
        ${metricHtml("总数量", quantityText(card.total_quantity || card.buy_number_count || 0))}
        ${metricHtml("开单人", operatorText(card))}
        ${metricHtml("开单时间", nativeDateText(card.sales_at || card.date_text))}
        ${metricHtml("创建时间", nativeDateText(card.created_at))}
        ${metricHtml("更新时间", nativeDateText(card.updated_at))}
        ${detailIsCanceled && card.canceled_by_name ? metricHtml("取消人", card.canceled_by_name, "danger-metric") : ""}
        ${detailIsCanceled && card.canceled_at ? metricHtml("取消时间", nativeDateText(card.canceled_at), "danger-metric") : ""}
        ${detailIsCanceled && card.cancel_reason ? metricHtml("取消原因", card.cancel_reason, "danger-metric") : ""}
        ${card.deleted_by_name ? metricHtml("删除人", card.deleted_by_name, "danger-metric") : ""}
        ${card.deleted_at ? metricHtml("删除时间", nativeDateText(card.deleted_at), "danger-metric") : ""}
        ${card.delete_reason ? metricHtml("删除原因", card.delete_reason, "danger-metric") : ""}
      </div>
    </div>
    <div class="sales-detail-table-wrap">
      <table class="sales-detail-table">
        <thead><tr><th>#</th><th>商品</th><th>数量</th><th>单价</th><th>小计</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="5">暂无商品明细</td></tr>'}</tbody>
      </table>
    </div>
    <section class="sales-flow-section">
      <h3>库存流水</h3>
      <div class="sales-flow-list">${ledgerHtml}</div>
    </section>
    <section class="sales-flow-section">
      <h3>删除流程</h3>
      <div class="sales-delete-flow">${deleteFlow.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
    </section>`;
}

async function openSalesDetail(id) {
  const card = state.lastSalesCards.find((item) => Number(item.id || 0) === Number(id));
  if (!card && !id) return toast("没有找到销售单明细", true);
  openDrawer("sales_detail", card || { id });
  try {
    const res = await api(`/api/sales/${encodeURIComponent(id)}/detail`);
    const detail = res.data || {};
    openDrawer("sales_detail", { ...(card || {}), ...detail });
  } catch (err) {
    toast(err.message || "销售单明细加载失败", true);
  }
}
window.openSalesDetail = openSalesDetail;

async function doPrintSales(id) {
  if (!id) return toast("没有取到销售单号，无法打印", true);
  const btn = document.querySelector(`button[onclick="printSales(${id})"]`);
  if (btn) { btn.classList.add("loading"); btn.textContent = "提交中..."; }
  try {
    const res = await api(`/api/sales/${encodeURIComponent(id)}/print-task`, { method: "POST" });
    if (res.code !== 0) throw new Error(res.msg || "打印任务创建失败");
    if (btn) { btn.textContent = "已提交"; btn.classList.remove("loading"); }
    toast("已创建打印任务，等待本地打印程序处理");
  } catch (err) {
    if (btn) { btn.textContent = "打印"; btn.classList.remove("loading"); }
    toast(err.message || "打印失败", true);
  }
}

async function deleteSales(id) {
  if (!id) return;
  const ok = await confirmDialog({
    title: "删除销售单",
    message: "确认删除这个销售单？系统会在自有库里软删除这单，并把这单对应的库存出库流水回滚。",
    confirmText: "删除"
  });
  if (!ok) return false;
  await api(`/api/sales/${id}`, { method: "DELETE" });
  toast("销售单已删除");
  loadSales();
  loadDashboardSummary();
  return true;
}

function removeBusinessHistoryCard(historyCardId, actionName, id) {
  state.businessHistory = state.businessHistory.filter((card) => {
    if (historyCardId && String(card.id) === String(historyCardId)) return false;
    return !String(card.actions || "").includes(`${actionName}('${id}'`);
  });
  persistBusinessHistory();
  renderBusinessContext();
}

async function deleteSalesHistoryCard(id, historyCardId = "") {
  let targetId = id;
  if (!/^\d+$/.test(String(targetId || ""))) {
    const res = await api(`/api/sales/cards?${query({ keyword: targetId, page: 1, page_size: 5 })}`);
    const list = normalizeList(res);
    const match = list.find((item) => String(item.sales_no || item.id || "") === String(targetId)) || list[0];
    targetId = match && match.id;
  }
  if (!targetId) return toast("没有找到可删除的销售单", true);
  const deleted = await deleteSales(targetId);
  if (deleted) removeBusinessHistoryCard(historyCardId, "deleteSalesFromHistory", id);
}

async function printLatestSales() {
  if (!state.lastSalesCards.length) await loadSales();
  const first = state.lastSalesCards[0];
  if (!first) return toast("没有销售单可打印", true);
  await doPrintSales(first.id);
}

function imageList(row) {
  if (Array.isArray(row.order_images)) return row.order_images;
  if (row.order_images) return String(row.order_images).split(",").filter(Boolean);
  return [];
}

async function loadWorkflow(page) {
  if (page !== undefined) state.workflowPage = page;
  await nextFrame();
  state.workflowPageSize = calculateWorkflowPageSize();
  const keyword = ($("workflowKeyword") && $("workflowKeyword").value.trim()) || "";
  const filter = state.workflowFilter || "active";
  const target = $("workflowList");
  if (target) target.innerHTML = skeletonCards(Math.min(state.workflowPageSize, 8));
  try {
    const res = await api(`/api/workflow/orders?${query({ keyword, filter, page: state.workflowPage, page_size: state.workflowPageSize })}`);
    const list = normalizeList(res);
    state.lastWorkflowCards = list;
    state.workflowTotal = (res.data && res.data.total) || list.length;
    setBadge("orders", state.workflowTotal);
    state.workflowLoadedAt = Date.now();
    renderWorkflow(list, target);
    renderWorkflowPager();
  } catch (err) {
    if (target) target.innerHTML = `<div class="empty">加载失败：${escapeHtml(err.message)}</div>`;
  }
}

function renderWorkflowPager() {
  const pager = $("workflowPager");
  if (!pager) return;
  const totalPages = Math.max(1, Math.ceil(state.workflowTotal / state.workflowPageSize));
  if (totalPages <= 1) { pager.innerHTML = ""; return; }
  pager.innerHTML =
    '<button ' + (state.workflowPage <= 1 ? "disabled" : "") + ' onclick="loadWorkflow(' + (state.workflowPage - 1) + ')">上一页</button>' +
    '<span class="page-info">' + state.workflowPage + ' / ' + totalPages + ' · 每页 ' + state.workflowPageSize + '</span>' +
    '<button ' + (state.workflowPage >= totalPages ? "disabled" : "") + ' onclick="loadWorkflow(' + (state.workflowPage + 1) + ')">下一页</button>';
}
window.loadWorkflow = loadWorkflow;

function calculateWorkflowPageSize() {
  const target = $("workflowList");
  const columns = gridColumnCount(target);
  if (!target) return Math.max(6, Math.min(15, columns * 3));
  const rect = target.getBoundingClientRect();
  const cardHeight = workflowCardHeight(target);
  const available = Math.max(cardHeight, window.innerHeight - rect.top - 22);
  const rows = Math.max(1, Math.floor((available + SALES_GRID_GAP) / (cardHeight + SALES_GRID_GAP)));
  return Math.max(columns, Math.min(72, rows * columns));
}

function workflowCardHeight(target) {
  const raw = window.getComputedStyle(target).getPropertyValue("--workflow-card-height").trim();
  const value = Number.parseFloat(raw);
  return Number.isFinite(value) ? value : WORKFLOW_CARD_HEIGHT_FALLBACK;
}

function openOrderImages(imgsJson) {
  try {
    const imgs = JSON.parse(imgsJson);
    if (!imgs || !imgs.length) return;
    state.lightboxImages = imgs;
    state.lightboxIndex = 0;
    showLightbox();
  } catch(e) {}
}

function showLightbox() {
  let overlay = $("orderLightbox");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "orderLightbox";
    overlay.className = "lightbox-overlay";
    overlay.innerHTML = '<div class="lightbox-mask" onclick="closeLightbox()"></div><div class="lightbox-content"><button class="lightbox-close" onclick="closeLightbox()">&times;</button><button class="lightbox-prev" onclick="lightboxPrev()">&#8249;</button><button class="lightbox-next" onclick="lightboxNext()">&#8250;</button><img class="lightbox-img" id="lightboxImg"></div>';
    document.body.appendChild(overlay);
  }
  updateLightbox();
  requestAnimationFrame(() => overlay.classList.add("open"));
}

function updateLightbox() {
  const img = $("lightboxImg");
  if (img && state.lightboxImages && state.lightboxImages[state.lightboxIndex]) {
    img.src = state.lightboxImages[state.lightboxIndex];
  }
}

function closeLightbox() {
  const overlay = $("orderLightbox");
  if (overlay) overlay.classList.remove("open");
}

function lightboxPrev() {
  if (!state.lightboxImages) return;
  state.lightboxIndex = (state.lightboxIndex - 1 + state.lightboxImages.length) % state.lightboxImages.length;
  updateLightbox();
}

function lightboxNext() {
  if (!state.lightboxImages) return;
  state.lightboxIndex = (state.lightboxIndex + 1) % state.lightboxImages.length;
  updateLightbox();
}

window.openOrderImages = openOrderImages;
window.closeLightbox = closeLightbox;
window.lightboxPrev = lightboxPrev;
window.lightboxNext = lightboxNext;


function workflowCardHtml(row, compact = false) {
  const id = row.id || row.order_id;
  const made = Number(row.is_made || 0) === 1;
  const delivered = Number(row.is_delivered || 0) === 1;
  const screen = Number(row.is_screen_print || 0) === 1;
  const imgs = imageList(row);
  const firstImage = imgs[0] || "";
  const visualStyle = firstImage ? ' style="background-image:url(\'' + escapeAttr(firstImage) + '\')"' : "";
  const imageCount = imgs.length > 1 ? imgs.length + " 张图片" : "";
  const onclickImg = imgs.length ? ' onclick="openOrderImages(\'' + escapeAttr(JSON.stringify(imgs)) + '\')"' : "";
  const qty = escapeHtml(row.order_quantity || row.quantity || "-");
  const orderTime = row.order_time_text || row.date_text || row.date || row.add_time || "";
  const madeClass = made ? "done" : "pending";
  const deliveredClass = delivered ? "done" : "pending";
  const screenClass = screen ? "craft-on" : "craft-off";
  return `
    <div class="order-row" data-order-id="${escapeAttr(id || "")}">
      <div class="order-visual ${firstImage ? "has-image" : ""}"${visualStyle}${onclickImg}>${imageCount ? `<span class="order-visual-caption">${escapeHtml(imageCount)}</span>` : ""}</div>
      <div class="order-info-row">
        <div>
          <div class="order-customer"><strong>${escapeHtml(row.customer_name || "客户")}</strong><span class="muted">#${escapeHtml(id || "")} ${escapeHtml(row.customer_phone || "")}</span></div>
          <div class="order-time">${orderTime ? "时间 " + escapeHtml(orderTime) : ""}</div>
        </div>
        <div class="order-qty-block"><span>${qty}</span><strong>套</strong></div>
      </div>
      <div class="order-goods-row"><strong>${escapeHtml([row.goods_name || row.title, row.goods_color || row.color].filter(Boolean).join(" "))}</strong></div>
      <div class="order-status-strip"><span class="tag ${made ? "green" : "green-outline"}">${made ? "已制作" : "未制作"}</span><span class="tag ${delivered ? "green" : "green-outline"}">${delivered ? "已配送" : "未配送"}</span><span class="tag ${screen ? "green" : "green-outline"}">${screen ? "丝印" : "不丝印"}</span></div>
      ${compact ? "" : `<div class="card-actions"><button class="primary" onclick="doMarkWorkflow(${Number(id || 0)}, 'is_made')">${made ? "取消制作" : "制作完成"}</button><button class="primary" onclick="doMarkWorkflow(${Number(id || 0)}, 'is_delivered')">${delivered ? "取消配送" : "配送完成"}</button><button onclick="editWorkflow(${Number(id || 0)})">编辑</button><button class="danger" onclick="deleteWorkflow(${Number(id || 0)})">删除</button></div>`}
    </div>`;
}

function renderWorkflow(list, target, compact = false) {
  if (!target) return;
  target.innerHTML = list.length ? list.map((row) => workflowCardHtml(row, compact)).join("") : '<div class="empty">暂无工作流订单</div>';
}

function workflowForm(row = {}) {
  const images = imageList(row);
  return `
    <input id="drawerWfId" type="hidden" value="${escapeAttr(row.id || row.order_id || "")}">
    <input id="drawerWfPhone" type="hidden" value="${escapeAttr(row.customer_phone || "")}">
    <input id="drawerWfType" type="hidden" value="${escapeAttr(row.order_type || 0)}">
    <input id="drawerWfImages" type="hidden" value="${escapeAttr(JSON.stringify(images))}">
    <label>客户名称</label><input id="drawerWfCustomer" value="${escapeAttr(row.customer_name || "")}">
    <label>商品</label><input id="drawerWfGoods" value="${escapeAttr(row.goods_name || row.title || "")}">
    <div class="two-col"><div><label>颜色</label><input id="drawerWfColor" value="${escapeAttr(row.goods_color || row.color || "")}"></div><div><label>数量</label><input id="drawerWfQty" type="number" min="1" value="${escapeAttr(row.order_quantity || row.quantity || 1)}"></div></div>
    <label>是否丝印</label><select id="drawerWfPrint"><option value="0">不丝印</option><option value="1" ${Number(row.is_screen_print || 0) ? "selected" : ""}>丝印</option></select>
    <div class="workflow-images">
      <label>订单图片</label>
      <div class="workflow-image-grid" id="workflowImageGrid">${workflowImageGridHtml(images)}</div>
      <input id="workflowImageInput" type="file" accept="image/*" class="sr-only" multiple onchange="uploadWorkflowImages(this.files)">
    </div>
  `;
}

function workflowImageGridHtml(images) {
  const list = Array.isArray(images) ? images.filter(Boolean) : [];
  const uploadTile = '<label class="workflow-image-upload" for="workflowImageInput">+<span>上传图片</span></label>';
  if (!list.length) return uploadTile;
  return list.map((url, index) => `
    <div class="workflow-image-card">
      <img src="${escapeAttr(url)}" alt="">
      <button class="workflow-image-remove" type="button" onclick="removeWorkflowImage(${index})">×</button>
    </div>`).join("") + uploadTile;
}

function drawerWorkflowImages() {
  try {
    const value = $("drawerWfImages") ? $("drawerWfImages").value : "[]";
    const list = JSON.parse(value || "[]");
    return Array.isArray(list) ? list.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function setDrawerWorkflowImages(images) {
  const list = Array.isArray(images) ? images.filter(Boolean) : [];
  if ($("drawerWfImages")) $("drawerWfImages").value = JSON.stringify(list);
  if ($("workflowImageGrid")) $("workflowImageGrid").innerHTML = workflowImageGridHtml(list);
}

function removeWorkflowImage(index) {
  const list = drawerWorkflowImages();
  list.splice(index, 1);
  setDrawerWorkflowImages(list);
}

async function uploadWorkflowImages(files) {
  const list = drawerWorkflowImages();
  const items = Array.from(files || []);
  if (!items.length) return;
  const input = $("workflowImageInput");
  try {
    for (const file of items) {
      const form = new FormData();
      form.append("image", file, file.name || `workflow_${Date.now()}.jpg`);
      const res = await api("/api/workflow/images/upload", { method: "POST", body: form });
      const data = res.data || {};
      const url = data.url || data.full_url || data.path || (typeof data === "string" ? data : "");
      if (!url) throw new Error("OSS 未返回图片地址");
      list.push(url);
    }
    setDrawerWorkflowImages(list);
    toast("图片已上传");
  } catch (err) {
    toast("图片上传失败: " + err.message, true);
  } finally {
    if (input) input.value = "";
  }
}

async function resolveInventoryProductFromDrawer() {
  const productId = $("drawerInvProductId") && $("drawerInvProductId").value;
  if (productId) {
    return {
      id: productId,
      product_id: productId,
      unit_id: 1,
      title: $("drawerInvTitle").value.trim(),
      spec: $("drawerInvColor").value.trim()
    };
  }
  const keyword = [$("drawerInvTitle").value.trim(), $("drawerInvColor").value.trim()].filter(Boolean).join(" ");
  const list = normalizeList(await api(`/api/product/search?${query({ keyword })}`));
  if (list.length === 1) return list[0];
  throw new Error(list.length ? "匹配到多个商品，请先把商品和颜色写得更准确" : "没有匹配到商品");
}

async function saveInventoryActionFromDrawer() {
  const product = await resolveInventoryProductFromDrawer();
  const type = $("drawerInvType").value;
  const qty = Number($("drawerInvQty").value || 0);
  const color = $("drawerInvColor").value.trim() || product.spec || product.color || "";
  if (type === "stocktaking") {
    if (qty < 0) throw new Error("盘点数量不能小于0");
    await api("/api/inventory/stocktaking", {
      method: "POST",
      body: { product_id: product.product_id || product.id, unit_id: product.unit_id || 1, quantity: qty, warehouse_id: Number($("drawerInvWarehouse").value || 2), color }
    });
    toast("盘点已提交");
    return;
  }
  if (qty <= 0) throw new Error("数量必须大于0");
  if (type === "purchase") {
    await api("/api/inventory/purchase", {
      method: "POST",
      body: { product_id: product.product_id || product.id, unit_id: product.unit_id || 1, quantity: qty, warehouse_id: Number($("drawerInvWarehouse").value || 2), color }
    });
    toast("进货已提交");
  } else {
    const outWarehouseId = Number($("drawerInvOutWarehouse").value || 2);
    const enterWarehouseId = Number($("drawerInvEnterWarehouse").value || 1);
    if (outWarehouseId === enterWarehouseId) throw new Error("调出仓库和调入仓库不能相同");
    await api("/api/inventory/transfer", {
      method: "POST",
      body: { product_id: product.product_id || product.id, unit_id: product.unit_id || 1, quantity: qty, out_warehouse_id: outWarehouseId, enter_warehouse_id: enterWarehouseId, color }
    });
    toast("调货已提交");
  }
}

async function saveDrawer() {
  if (state.drawerMode === "workflow") {
    await api("/api/workflow/orders", {
      method: "POST",
      body: {
        id: $("drawerWfId").value || undefined,
        customer_name: $("drawerWfCustomer").value.trim(),
        customer_phone: $("drawerWfPhone").value.trim(),
        goods_name: $("drawerWfGoods").value.trim(),
        color: $("drawerWfColor").value.trim(),
        order_quantity: Number($("drawerWfQty").value || 0),
        is_screen_print: Number($("drawerWfPrint").value || 0),
        order_type: Number($("drawerWfType").value || 0),
        order_images: drawerWorkflowImages()
      }
    });
    toast("工作流订单已保存");
    closeDrawer();
    loadWorkflow();
    loadDashboardSummary();
  } else if (state.drawerMode === "product") {
    await saveProductFromDrawer();
    closeDrawer();
    loadProducts(state.productPage);
  } else if (state.drawerMode === "inventory_action") {
    await saveInventoryActionFromDrawer();
    closeDrawer();
    loadInventory(undefined, state.inventoryPage);
  }
}

function editWorkflowOrder(id) {
  const row = state.lastWorkflowCards.find((item) => Number(item.id || item.order_id) === Number(id));
  if (!row) return toast("没有找到工作流订单", true);
  openDrawer("workflow", row);
}

async function _markWorkflow(id, field) {
  try {
    const row = state.lastWorkflowCards.find((item) => Number(item.id || item.order_id) === Number(id));
    const value = row && Number(row[field] || 0) === 1 ? 0 : 1;
    const cardNode = document.querySelector(`#workflowList .order-row[data-order-id="${CSS.escape(String(id))}"]`);
    const button = cardNode ? cardNode.querySelector(`button[onclick="doMarkWorkflow(${Number(id || 0)}, '${field}')"]`) : null;
    if (button) button.classList.add("loading");
    await api("/api/workflow/orders/" + id + "/status", { method: "POST", body: { field: field, value: value } });
    if (row) row[field] = value;
    if (cardNode && row) {
      cardNode.outerHTML = workflowCardHtml(row, false);
    }
    toast("状态已更新");
    loadDashboardSummary();
  } catch (err) {
    toast("操作失败: " + err.message, true);
  }
}

async function deleteWorkflowOrder(id) {
  if (!id) return;
  const row = state.lastWorkflowCards.find((item) => Number(item.id || item.order_id) === Number(id));
  const ok = await confirmDialog({
    title: "删除订单",
    message: `确认删除${row && row.customer_name ? " " + row.customer_name + " 的" : "这个"}工作流订单？`,
    confirmText: "删除"
  });
  if (!ok) return false;
  const cardNode = document.querySelector(`#workflowList .order-row[data-order-id="${CSS.escape(String(id))}"]`);
  const button = cardNode ? cardNode.querySelector(".card-actions .danger") : null;
  if (button) button.classList.add("loading");
  try {
    await api(`/api/workflow/orders/${id}`, { method: "DELETE" });
    state.lastWorkflowCards = state.lastWorkflowCards.filter((item) => Number(item.id || item.order_id) !== Number(id));
    state.workflowTotal = Math.max(0, Number(state.workflowTotal || 0) - 1);
    if (cardNode) cardNode.remove();
    if ($("workflowList") && !state.lastWorkflowCards.length) $("workflowList").innerHTML = '<div class="empty">暂无工作流订单</div>';
    setBadge("orders", state.workflowTotal);
    renderWorkflowPager();
    toast("工作流订单已删除");
    loadDashboardSummary();
    return true;
  } catch (err) {
    if (button) button.classList.remove("loading");
    toast("删除失败: " + err.message, true);
    return false;
  }
}

async function deleteWorkflowHistoryCard(id, historyCardId = "") {
  const ids = String(id || "").split(",").map((item) => item.trim()).filter(Boolean);
  if (ids.length <= 1) {
    const deleted = await deleteWorkflowOrder(ids[0] || id);
    if (deleted) removeBusinessHistoryCard(historyCardId, "deleteWorkflowFromHistory", id);
    return;
  }
  const ok = await confirmDialog({
    title: "删除工作流订单",
    message: `确认删除这 ${ids.length} 个工作流订单吗？\n${ids.join("、")}`,
    confirmText: "删除"
  });
  if (!ok) return;
  const results = [];
  for (const workflowId of ids) {
    try {
      await api(`/api/workflow/orders/${encodeURIComponent(workflowId)}`, { method: "DELETE" });
      results.push({ id: workflowId, ok: true });
    } catch (err) {
      results.push({ id: workflowId, ok: false, error: err.message });
    }
  }
  const successIds = results.filter((item) => item.ok).map((item) => item.id);
  state.lastWorkflowCards = state.lastWorkflowCards.filter((item) => !successIds.includes(String(item.id || item.order_id)));
  state.workflowTotal = Math.max(0, Number(state.workflowTotal || 0) - successIds.length);
  if (successIds.length) removeBusinessHistoryCard(historyCardId, "deleteWorkflowFromHistory", id);
  loadDashboardSummary();
  loadWorkflow();
  const failed = results.filter((item) => !item.ok);
  if (failed.length) toast(`已删除 ${successIds.length} 个，失败 ${failed.length} 个`, true);
  else toast("工作流订单已删除");
}

async function loadInventory(keywordOverride, page) {
  if (state.inventoryTab !== "cards") {
    return loadInventoryManagement(page || 1);
  }
  if (page !== undefined) state.inventoryPage = page;
  else if (keywordOverride !== undefined) state.inventoryPage = 1;
  const keyword = (keywordOverride ?? (($("inventoryKeyword") && $("inventoryKeyword").value) || "")).trim();
  const only = 0;
  const target = $("inventoryList");
  if (target) target.innerHTML = skeletonCards(6);
  if (keyword) {
    state.contextInventory = { keyword, list: [], loading: true, updatedAt: Date.now() };
    renderBusinessContext();
  }
  const res = await api(`/api/inventory/cards?${query({ keyword, only_in_stock: only, limit: LIST_LIMITS.inventory })}`);
  const list = normalizeList(res);
  state.lastInventoryCards = list;
  state.inventoryTotal = list.length;
  if (keyword) {
    state.contextInventory = { keyword, list, loading: false, updatedAt: Date.now() };
    renderBusinessContext();
  }
  setBadge("inventory", list.length);
  renderInventoryPage(state.inventoryPage);
}
window.loadInventory = loadInventory;

async function loadContextInventory(keyword) {
  const cleanKeyword = String(keyword || "").trim();
  state.contextInventory = { keyword: cleanKeyword, list: [], loading: true, updatedAt: Date.now() };
  renderBusinessContext();
  const res = await api(`/api/inventory/cards?${query({ keyword: cleanKeyword, only_in_stock: 0, limit: LIST_LIMITS.inventory })}`);
  const list = normalizeList(res);
  state.contextInventory = { keyword: cleanKeyword, list, loading: false, updatedAt: Date.now() };
  showInventoryPopup(cleanKeyword, list);
  addInventoryHistory(cleanKeyword, list);
  return list;
}

function calculateInventoryPageSize() {
  const target = $("inventoryList");
  const columns = gridColumnCount(target);
  if (!target) return Math.max(4, columns * 2);
  const rect = target.getBoundingClientRect();
  const available = Math.max(320, window.innerHeight - rect.top - 28);
  const rows = Math.max(1, Math.floor((available + 14) / 285));
  return Math.max(columns * 2, Math.min(48, rows * columns));
}

function renderInventoryPage(page = state.inventoryPage) {
  state.inventoryPageSize = calculateInventoryPageSize();
  state.inventoryTotal = state.lastInventoryCards.length;
  const totalPages = Math.max(1, Math.ceil(state.inventoryTotal / state.inventoryPageSize));
  state.inventoryPage = Math.max(1, Math.min(page, totalPages));
  const start = (state.inventoryPage - 1) * state.inventoryPageSize;
  renderInventory(state.lastInventoryCards.slice(start, start + state.inventoryPageSize));
  renderInventoryPager();
}

function renderInventoryPager() {
  const pager = $("inventoryPager");
  if (!pager) return;
  const totalPages = Math.max(1, Math.ceil(state.inventoryTotal / state.inventoryPageSize));
  if (totalPages <= 1) { pager.innerHTML = ""; return; }
  pager.innerHTML =
    '<button ' + (state.inventoryPage <= 1 ? "disabled" : "") + ' onclick="renderInventoryPage(' + (state.inventoryPage - 1) + ')">上一页</button>' +
    '<span class="page-info">' + state.inventoryPage + ' / ' + totalPages + ' · 每页 ' + state.inventoryPageSize + '</span>' +
    '<button ' + (state.inventoryPage >= totalPages ? "disabled" : "") + ' onclick="renderInventoryPage(' + (state.inventoryPage + 1) + ')">下一页</button>';
}
window.renderInventoryPage = renderInventoryPage;

function colorCss(value) {
  const text = String(value || "").trim();
  const map = {
    红色: "#d92d20", 黄色: "#f4c430", 金色: "#c69214", 橙色: "#f97316", 蓝色: "#2563eb",
    绿色: "#16a34a", 橄榄绿: "#708238", 咖色: "#7a4a28", 深咖色: "#4b2e1f",
    古铜色: "#8c6239", 黑色: "#111", 白色: "#fff", 银色: "#c7c9cc", 灰色: "#8a8f98",
    香槟金: "#d8bd82", 粉色: "#f4a7b9", 紫色: "#7c3aed"
  };
  return map[text] || "";
}

function stockOf(item, name) {
  const rows = item.warehouses || item.stock || [];
  const needle = String(name || "").replace("仓库", "");
  if (Array.isArray(rows)) {
    const row = rows.find((warehouse) => String(warehouse.name || warehouse.warehouse_name || "").includes(needle));
    return row ? (row.stock ?? row.inventory ?? row.quantity ?? 0) : 0;
  }
  if (rows && typeof rows === "object") {
    const key = Object.keys(rows).find((warehouse) => String(warehouse).includes(needle));
    return key ? (rows[key] ?? 0) : 0;
  }
  return item[name] || item[needle] || 0;
}

function inventoryCardHtml(card, compact = false) {
  const colors = card.colors || [];
  const total = Number(card.total_stock ?? colors.reduce((sum, color) => sum + Number(color.total_stock ?? color.stock ?? (Number(stockOf(color, "百鑫")) + Number(stockOf(color, "店里")))), 0));
  const title = card.title || card.name || "库存";
  const displayColors = compact ? colors.slice(0, 8) : colors;
  return `
    <div class="business-card inventory-card ${compact ? "context-inventory-card" : ""}">
      <div class="card-top">
        <div class="inventory-title"><h3>${escapeHtml(title)}</h3><span class="tag ${Number(total) > 0 ? "green" : "green-outline"}">${escapeHtml(card.status_text || "库存")}</span></div>
        <div class="inventory-total"><strong>${escapeHtml(total)}</strong><span>合计库存</span></div>
      </div>
      <table class="table-lite"><thead><tr><th>颜色</th><th>百鑫仓库</th><th>店里仓库</th><th>合计</th>${compact ? "" : "<th>操作</th>"}</tr></thead><tbody>
        ${displayColors.map((color) => {
          const bx = stockOf(color, "百鑫");
          const store = stockOf(color, "店里");
          const rowTotal = Number(color.total_stock ?? color.stock ?? (Number(bx) + Number(store)));
          const colorName = color.color || "默认";
          const productId = color.product_id || card.product_id || card.id || "";
          return `<tr>
            <td><span class="swatch" style="background:${escapeAttr(colorCss(colorName) || "#ddd")}"></span>${escapeHtml(colorName)}</td>
            <td>${escapeHtml(bx)}</td>
            <td>${escapeHtml(store)}</td>
            <td><strong>${escapeHtml(rowTotal)}</strong></td>
            ${compact ? "" : `<td><div class="inventory-actions"><button class="primary" onclick="prepareInventoryAction('${escapeAttr(title)}', '${escapeAttr(colorName)}', 'transfer', '${escapeAttr(productId)}')">调</button><button onclick="prepareInventoryAction('${escapeAttr(title)}', '${escapeAttr(colorName)}', 'purchase', '${escapeAttr(productId)}')">进</button><button onclick="prepareInventoryAction('${escapeAttr(title)}', '${escapeAttr(colorName)}', 'stocktaking', '${escapeAttr(productId)}')">盘</button></div></td>`}
          </tr>`;
        }).join("")}
        ${colors.length > displayColors.length ? `<tr><td colspan="${compact ? 4 : 5}" class="muted">还有 ${escapeHtml(colors.length - displayColors.length)} 个颜色，可到库存页查看</td></tr>` : ""}
        <tr><td colspan="3"><strong>合计</strong></td><td><strong>${escapeHtml(total)}</strong></td>${compact ? "" : "<td></td>"}</tr>
      </tbody></table>
      ${compact ? "" : `<p class="muted">件规：${escapeHtml(card.piece_text || "未设置件套换算")}</p>`}
    </div>`;
}

function renderInventory(list) {
  const target = $("inventoryList");
  if (!target) return;
  target.classList.remove("table-mode");
  target.innerHTML = list.length ? list.map((card) => inventoryCardHtml(card)).join("") : '<div class="empty">暂无库存数据</div>';
}

function tableHtml(headers, rows, emptyText = "暂无数据") {
  if (!rows.length) return `<div class="empty">${escapeHtml(emptyText)}</div>`;
  return `<div class="business-card table-panel"><table class="table-lite wide-table"><thead><tr>${headers.map((item) => `<th>${escapeHtml(item.label)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${headers.map((item) => `<td>${escapeHtml(item.render ? item.render(row) : (row[item.key] ?? ""))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function nativeDate(value) {
  if (!value) return "";
  return String(value).replace("T", " ").slice(0, 19);
}

function nativeDateText(value) {
  return nativeDate(value) || "-";
}

function mapText(map, value, fallback = "-") {
  const key = String(value || "");
  if (!key) return fallback;
  return map[key] || key.replace(/_/g, " ");
}

const INVENTORY_DOC_TYPE_TEXT = {
  purchase_in: "进货入库",
  sales_out: "销售出库",
  transfer_out: "调拨出库",
  transfer_in: "调拨入库",
  stocktake_gain: "盘盈入库",
  stocktake_loss: "盘亏出库",
  adjust_in: "调整入库",
  adjust_out: "调整出库"
};

const INVENTORY_DIRECTION_TEXT = {
  in: "入库",
  out: "出库",
  transfer: "调拨",
  adjust: "调整"
};

const INVENTORY_STATUS_TEXT = {
  draft: "草稿",
  pending: "待确认",
  approved: "已通过",
  rejected: "已拒绝",
  confirmed: "已确认",
  completed: "已完成",
  canceled: "已取消",
  deleted: "已删除",
  active: "启用",
  inactive: "停用"
};

const INVENTORY_BIZ_TYPE_TEXT = {
  purchase_in: "进货入库",
  sales_out: "销售出库",
  sales_delete: "删除回滚",
  transfer_out: "调拨出库",
  transfer_in: "调拨入库",
  stocktake: "库存盘点",
  stocktake_gain: "盘盈",
  stocktake_loss: "盘亏",
  init: "初始化",
  adjust: "库存调整"
};

function docTypeText(value) {
  return mapText(INVENTORY_DOC_TYPE_TEXT, value);
}

function directionText(value) {
  return mapText(INVENTORY_DIRECTION_TEXT, value);
}

function inventoryStatusText(value) {
  return mapText(INVENTORY_STATUS_TEXT, value);
}

function approvalStatusText(value) {
  return mapText({
    pending: "待审核",
    approved: "已通过",
    rejected: "已拒绝",
    active: "启用",
    inactive: "停用"
  }, value);
}

function payStatusText(value) {
  return mapText({
    paid: "已付款",
    unpaid: "未付款",
    monthly: "月结",
    partial: "部分付款",
    refunded: "已退款"
  }, value);
}

function payTypeText(value) {
  return mapText({
    wechat: "微信",
    cash: "现金",
    balance: "余额",
    monthly: "月结",
    account: "账户",
    bank: "转账",
    alipay: "支付宝"
  }, value, "");
}

function bizTypeText(value) {
  return mapText(INVENTORY_BIZ_TYPE_TEXT, value);
}

function inventoryHeaders() {
  const commonProduct = [
    { label: "商品", render: (row) => row.title || row["产品名称"] || row.title_snapshot || "" },
    { label: "颜色", render: (row) => row.color || row.spec || row["【颜色】"] || row.color_snapshot || "" },
    { label: "编号", render: (row) => row.sku_no || row.sku_no_snapshot || "" }
  ];
  if (state.inventoryTab === "balances") {
    return commonProduct.concat([
      { label: "仓库", render: (row) => row.warehouse_name || row["【仓库】"] || "" },
      { label: "库存", render: (row) => row.inventory || row["库存数量"] || row.quantity || 0 },
      { label: "可用", render: (row) => row.available_qty || row.inventory || row.quantity || 0 }
    ]);
  }
  if (state.inventoryTab === "stock-documents") {
    return [
      { label: "单号", key: "doc_no" },
      { label: "类型", render: (row) => docTypeText(row.doc_type) },
      { label: "方向", render: (row) => directionText(row.direction) },
      { label: "仓库", key: "warehouse_name" },
      { label: "数量", key: "total_quantity" },
      { label: "状态", render: (row) => inventoryStatusText(row.status) },
      { label: "操作人", render: (row) => operatorText(row) },
      { label: "时间", render: (row) => nativeDate(row.confirmed_at || row.created_at) },
      { label: "备注", key: "note" }
    ];
  }
  if (state.inventoryTab === "stocktakes") {
    return [
      { label: "盘点单", key: "stocktake_no" },
      { label: "仓库", key: "warehouse_name" },
      { label: "状态", render: (row) => inventoryStatusText(row.status) },
      { label: "差异", key: "total_diff_qty" },
      { label: "操作人", render: (row) => operatorText(row) },
      { label: "时间", render: (row) => nativeDate(row.confirmed_at || row.created_at) },
      { label: "备注", key: "note" }
    ];
  }
  if (state.inventoryTab === "transfers") {
    return [
      { label: "调拨单", key: "transfer_no" },
      { label: "调出", key: "from_warehouse_name" },
      { label: "调入", key: "to_warehouse_name" },
      { label: "数量", key: "total_quantity" },
      { label: "状态", render: (row) => inventoryStatusText(row.status) },
      { label: "操作人", render: (row) => operatorText(row) },
      { label: "时间", render: (row) => nativeDate(row.confirmed_at || row.created_at) },
      { label: "备注", key: "note" }
    ];
  }
  if (state.inventoryTab === "ledger") {
    return commonProduct.concat([
      { label: "仓库", key: "warehouse_name" },
      { label: "变动", key: "change_qty" },
      { label: "变动前", key: "before_qty" },
      { label: "变动后", key: "after_qty" },
      { label: "业务", render: (row) => bizTypeText(row.biz_type) },
      { label: "操作人", render: (row) => operatorText(row) },
      { label: "时间", render: (row) => nativeDate(row.occurred_at || row.created_at) }
    ]);
  }
  return [
    { label: "仓库", key: "name" },
    { label: "编码", key: "code" },
    { label: "类型", key: "type" },
    { label: "默认销售", render: (row) => Number(row.is_default_sales || 0) ? "是" : "否" },
    { label: "默认入库", render: (row) => Number(row.is_default_inbound || 0) ? "是" : "否" }
  ];
}

function metricHtml(label, value, tone = "") {
  return `<div class="record-metric ${tone}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value ?? "-")}</strong></div>`;
}

function operatorText(row) {
  return row.operator_name || row.created_by_name || row.canceled_by_name || row.operator_username || row.created_by_username || row.canceled_by_username || "未记录";
}

function signedMoneyText(value) {
  const number = Number(value || 0);
  const sign = number < 0 ? "-" : "";
  return `${sign}¥${money(Math.abs(number))}`;
}

function signedDeltaText(value) {
  const number = Number(value || 0);
  const sign = number > 0 ? "+" : (number < 0 ? "-" : "");
  return `${sign}¥${money(Math.abs(number))}`;
}

function inventoryRecordHtml(row) {
  if (state.inventoryTab === "balances") {
    return `<article class="record-card inventory-record">
      <div class="record-main">
        <div><h3>${escapeHtml(row.title || row["产品名称"] || "商品")}</h3><p>${escapeHtml([row.color || row.spec || row["【颜色】"], row.sku_no || row.sku_no_snapshot].filter(Boolean).join(" · ") || "未记录颜色")}</p></div>
        <span class="tag green">${escapeHtml(row.warehouse_name || row["【仓库】"] || "仓库")}</span>
      </div>
      <div class="record-metrics">
        ${metricHtml("当前库存", row.inventory || row.quantity || 0, "accent")}
        ${metricHtml("可用库存", row.available_qty || row.inventory || row.quantity || 0)}
        ${metricHtml("锁定", row.locked_qty || 0)}
      </div>
    </article>`;
  }
  if (state.inventoryTab === "stock-documents") {
    return `<article class="record-card inventory-record">
      <div class="record-main">
        <div><h3>${escapeHtml(row.doc_no || "出入库单")}</h3><p>${escapeHtml(row.warehouse_name || "仓库未记录")} · ${escapeHtml(nativeDateText(row.confirmed_at || row.created_at))}</p></div>
        <span class="tag green-outline">${escapeHtml(docTypeText(row.doc_type))}</span>
      </div>
      <div class="record-metrics">
        ${metricHtml("方向", directionText(row.direction))}
        ${metricHtml("数量", row.total_quantity || 0, "accent")}
        ${metricHtml("状态", inventoryStatusText(row.status))}
        ${metricHtml("操作人", operatorText(row))}
      </div>
      ${row.note ? `<p class="record-note">${escapeHtml(row.note)}</p>` : ""}
    </article>`;
  }
  if (state.inventoryTab === "stocktakes") {
    return `<article class="record-card inventory-record">
      <div class="record-main">
        <div><h3>${escapeHtml(row.stocktake_no || "盘点单")}</h3><p>${escapeHtml(row.warehouse_name || "仓库未记录")} · ${escapeHtml(nativeDateText(row.confirmed_at || row.created_at))}</p></div>
        <span class="tag gray">${escapeHtml(inventoryStatusText(row.status))}</span>
      </div>
      <div class="record-metrics">
        ${metricHtml("盘点差异", row.total_diff_qty || 0, Number(row.total_diff_qty || 0) !== 0 ? "accent" : "")}
        ${metricHtml("操作人", operatorText(row))}
        ${metricHtml("备注", row.note || "-")}
      </div>
    </article>`;
  }
  if (state.inventoryTab === "transfers") {
    return `<article class="record-card inventory-record">
      <div class="record-main">
        <div><h3>${escapeHtml(row.transfer_no || "调拨单")}</h3><p>${escapeHtml(nativeDateText(row.confirmed_at || row.created_at))}</p></div>
        <span class="tag green-outline">${escapeHtml(inventoryStatusText(row.status))}</span>
      </div>
      <div class="record-route">
        <strong>${escapeHtml(row.from_warehouse_name || "调出仓")}</strong>
        <span>→</span>
        <strong>${escapeHtml(row.to_warehouse_name || "调入仓")}</strong>
      </div>
      <div class="record-metrics">
        ${metricHtml("调拨数量", row.total_quantity || 0, "accent")}
        ${metricHtml("操作人", operatorText(row))}
        ${metricHtml("备注", row.note || "-")}
      </div>
    </article>`;
  }
  if (state.inventoryTab === "ledger") {
    return `<article class="record-card inventory-record">
      <div class="record-main">
        <div><h3>${escapeHtml(row.title || row.title_snapshot || "商品")}</h3><p>${escapeHtml([row.color || row.color_snapshot, row.sku_no || row.sku_no_snapshot, row.warehouse_name].filter(Boolean).join(" · "))}</p></div>
        <span class="tag gold">${escapeHtml(bizTypeText(row.biz_type))}</span>
      </div>
      <div class="record-metrics">
        ${metricHtml("变动", row.change_qty || 0, Number(row.change_qty || 0) !== 0 ? "accent" : "")}
        ${metricHtml("变动前", row.before_qty || 0)}
        ${metricHtml("变动后", row.after_qty || 0)}
        ${metricHtml("操作人", operatorText(row))}
        ${metricHtml("时间", nativeDateText(row.occurred_at || row.created_at))}
      </div>
    </article>`;
  }
  return `<article class="record-card inventory-record">
    <div class="record-main">
      <div><h3>${escapeHtml(row.name || "仓库")}</h3><p>${escapeHtml(row.code || "无编码")}</p></div>
      <span class="tag green">${Number(row.is_enabled ?? 1) ? "启用" : "停用"}</span>
    </div>
    <div class="record-metrics">
      ${metricHtml("仓库类型", mapText({ self: "自有仓", supplier: "供应商仓", virtual: "虚拟仓" }, row.warehouse_type || row.type))}
      ${metricHtml("默认销售", Number(row.is_default_sales || 0) ? "是" : "否")}
      ${metricHtml("默认入库", Number(row.is_default_inbound || 0) ? "是" : "否")}
    </div>
  </article>`;
}

function inventoryEndpoint() {
  return {
    balances: "/api/inventory/balances",
    "stock-documents": "/api/stock-documents",
    stocktakes: "/api/stocktakes",
    transfers: "/api/transfers",
    ledger: "/api/inventory/ledger",
    warehouses: "/api/warehouses"
  }[state.inventoryTab] || "/api/inventory/balances";
}

async function loadInventoryManagement(page = 1) {
  state.inventoryPage = page;
  const keyword = (($("inventoryKeyword") && $("inventoryKeyword").value) || "").trim();
  const target = $("inventoryList");
  if (target) {
    target.classList.add("table-mode");
    target.innerHTML = skeletonCards(2);
  }
  const endpoint = inventoryEndpoint();
  const res = await api(`${endpoint}?${query({ keyword, page: state.inventoryPage, page_size: 50 })}`);
  const list = normalizeList(res);
  state.lastInventoryRows = list;
  state.inventoryTotal = (res.data && res.data.total) || list.length;
  setBadge("inventory", state.inventoryTotal);
  renderInventoryManagement(list);
  renderInventoryManagementPager();
}

function renderInventoryManagement(list) {
  const target = $("inventoryList");
  if (!target) return;
  target.classList.add("table-mode");
  target.innerHTML = list.length
    ? `<div class="management-list">${list.map((row) => inventoryRecordHtml(row)).join("")}</div>`
    : '<div class="empty">暂无库存记录</div>';
}

function renderInventoryManagementPager() {
  const pager = $("inventoryPager");
  if (!pager) return;
  const pageSize = 50;
  const totalPages = Math.max(1, Math.ceil(state.inventoryTotal / pageSize));
  if (totalPages <= 1) { pager.innerHTML = ""; return; }
  pager.innerHTML =
    '<button ' + (state.inventoryPage <= 1 ? "disabled" : "") + ' onclick="loadInventoryManagement(' + (state.inventoryPage - 1) + ')">上一页</button>' +
    '<span class="page-info">' + state.inventoryPage + ' / ' + totalPages + '</span>' +
    '<button ' + (state.inventoryPage >= totalPages ? "disabled" : "") + ' onclick="loadInventoryManagement(' + (state.inventoryPage + 1) + ')">下一页</button>';
}
window.loadInventoryManagement = loadInventoryManagement;

function setInventoryTab(tab) {
  state.inventoryTab = tab || "cards";
  state.inventoryPage = 1;
  document.querySelectorAll("[data-inventory-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.inventoryTab === state.inventoryTab);
  });
  if (state.inventoryTab === "cards") loadInventory(undefined, 1);
  else loadInventoryManagement(1);
}

async function loadCustomers(page = 1) {
  state.customerPage = page;
  const keyword = (($("customerKeyword") && $("customerKeyword").value) || "").trim();
  const target = $("customerList");
  if (target) target.innerHTML = skeletonCards(4);
  const endpoint = state.customerTab === "users" ? "/api/users" : "/api/customers";
  const res = await api(`${endpoint}?${query({ keyword, page: state.customerPage, page_size: state.customerPageSize, limit: LIST_LIMITS.customers })}`);
  const list = normalizeList(res);
  state.lastCustomers = list;
  state.customerTotal = (res.data && res.data.total) || list.length;
  setBadge("customers", state.customerTotal);
  renderCustomers(list);
  renderCustomerPager();
}
window.loadCustomers = loadCustomers;

function renderCustomers(list) {
  const target = $("customerList");
  if (!target) return;
  if (state.customerTab === "users") {
    target.innerHTML = renderUserList(list);
    return;
  }
  target.innerHTML = list.length ? `<div class="customer-card-grid">${list.map((customer) => {
    const customerId = Number(customer.id || customer.customer_id || 0);
    const customerName = customer.name || customer.customer_name || "客户";
    const isMonthly = Number(customer.is_monthly_customer || 0) === 1;
    return `
    <article class="record-card customer-card" data-open-customer-sales="${customerId}" data-customer-name="${escapeAttr(customerName)}">
      <div class="record-main">
        <div>
          <h3>${escapeHtml(customerName)}</h3>
          <p>${escapeHtml(customer.phone || customer.mobile || customer.contacts_mobile || "未绑定电话")}</p>
        </div>
        <span class="tag ${isMonthly ? "green-outline" : ""}">${isMonthly ? "月结客户" : "现结客户"}</span>
      </div>
      <div class="record-metrics customer-metrics">
        ${metricHtml("最近下单", nativeDateText(customer.latest_order_at))}
        ${metricHtml("最近金额", `¥${money(customer.latest_order_amount || 0)}`, "accent")}
        ${metricHtml("近1年消费", `¥${money(customer.year_amount || 0)}`, "accent")}
        ${metricHtml("余额", signedMoneyText(customer.balance_amount || 0), Number(customer.balance_amount || 0) < 0 ? "accent danger-metric" : "")}
      </div>
      <div class="customer-actions">
        <button type="button" data-open-customer-sales="${customerId}" data-customer-name="${escapeAttr(customerName)}">销售单</button>
        <button type="button" data-customer-balance-action="receipt" data-customer-id="${customerId}" data-customer-name="${escapeAttr(customerName)}">收款</button>
        <button type="button" data-customer-balance-action="recharge" data-customer-id="${customerId}" data-customer-name="${escapeAttr(customerName)}">充值</button>
        <button type="button" class="primary-action" data-customer-balance-action="settlement" data-customer-id="${customerId}" data-customer-name="${escapeAttr(customerName)}">结款</button>
        <button type="button" data-customer-monthly-toggle="${customerId}" data-customer-monthly-value="${isMonthly ? 0 : 1}">${isMonthly ? "取消月结" : "设为月结"}</button>
        <button type="button" data-customer-balance-action="adjust" data-customer-id="${customerId}" data-customer-name="${escapeAttr(customerName)}">调整余额</button>
        <button type="button" data-open-balance-ledger="${customerId}" data-customer-name="${escapeAttr(customerName)}">余额明细</button>
      </div>
    </article>
  `;
  }).join("")}</div>` : '<div class="empty">暂无客户</div>';
}

function userRoleText(role) {
  return roleLabel(role);
}

function renderRoleButtons(user, roleNames = []) {
  const roles = userRoleOptionsFromRules(roleNames);
  const current = roleCode(user.role);
  if (current && !roles.some(([value]) => value === current)) roles.push([current, roleLabel(current)]);
  return `<div class="role-buttons">${roles.map(([value, label]) => `<button type="button" class="${String(user.role || "") === value ? "active" : ""}" data-user-role="${escapeAttr(value)}" data-user-id="${Number(user.id || 0)}">${label}</button>`).join("")}</div>`;
}

function renderUserList(list, roleNames = []) {
  if (!list.length) return '<div class="empty">暂无用户</div>';
  return `<div class="management-list user-list">${list.map((user) => {
    const active = Number(user.is_active || 0) === 1;
    const current = roleCode(user.role);
    return `<article class="record-card user-row">
      <div class="user-main">
        <div>
          <h3>${escapeHtml(user.display_name || user.party_name || user.account_display || "用户")}</h3>
          <p>${escapeHtml(user.account_display || user.username || "")}${user.phone ? ` · ${escapeHtml(user.phone)}` : ""}${user.party_name ? ` · 绑定客户：${escapeHtml(user.party_name)}` : ""}</p>
        </div>
        <button type="button" class="enable-toggle ${active ? "on" : ""}" data-user-active="${active ? 0 : 1}" data-user-id="${Number(user.id || 0)}">${active ? "已启用" : "已停用"}</button>
      </div>
      <div class="user-controls">
        <div>
          <span>角色</span>
          ${renderRoleButtons({ ...user, role: current }, roleNames)}
        </div>
        <div class="user-status">
          <span>状态</span>
          <strong>${escapeHtml(userRoleText(current))} · ${escapeHtml(approvalStatusText(user.approval_status || (active ? "active" : "inactive")))}</strong>
        </div>
      </div>
    </article>`;
  }).join("")}</div>`;
}

async function updateCustomerMonthly(customerId, value) {
  if (!customerId) return;
  await api(`/api/customers/${customerId}`, {
    method: "POST",
    body: { is_monthly_customer: value ? 1 : 0 }
  });
  state.lastCustomers = state.lastCustomers.map((customer) => {
    const id = Number(customer.id || customer.customer_id || 0);
    return id === Number(customerId) ? { ...customer, is_monthly_customer: value ? 1 : 0 } : customer;
  });
  renderCustomers(state.lastCustomers);
  toast(value ? "已设为月结客户" : "已取消月结客户");
}

function customerSalesFilterHtml(customerId, customerName, active = {}) {
  const safeName = escapeAttr(customerName || "客户");
  const activePeriod = active.period || "";
  const month = active.month || "";
  const nowYear = new Date().getFullYear();
  const selectedYear = Number(active.year || (month ? String(month).slice(0, 4) : nowYear)) || nowYear;
  const selectedMonth = month ? Number(String(month).slice(5, 7)) : 0;
  const yearOptions = [nowYear, nowYear - 1, nowYear - 2].map((year) => (
    `<option value="${year}" ${year === selectedYear ? "selected" : ""}>${year}年</option>`
  )).join("");
  const monthButtons = Array.from({ length: 12 }, (_, i) => i + 1).map((num) => {
    const monthValue = `${selectedYear}-${String(num).padStart(2, "0")}`;
    return `<button type="button" class="${selectedMonth === num ? "active" : ""}" data-customer-sales-month="${Number(customerId)}" data-customer-name="${safeName}" data-month-value="${monthValue}">${num}月</button>`;
  }).join("");
  return `<div class="customer-sales-filter">
    <button type="button" class="${activePeriod === "" && !month ? "active" : ""}" data-customer-sales-filter="${Number(customerId)}" data-customer-name="${safeName}" data-period="">全部</button>
    <button type="button" class="${activePeriod === "1m" ? "active" : ""}" data-customer-sales-filter="${Number(customerId)}" data-customer-name="${safeName}" data-period="1m">最近1个月</button>
    <button type="button" class="${activePeriod === "3m" ? "active" : ""}" data-customer-sales-filter="${Number(customerId)}" data-customer-name="${safeName}" data-period="3m">最近3个月</button>
    <div class="month-filter"><select id="customerSalesYear">${yearOptions}</select></div>
    <div class="month-button-grid">${monthButtons}</div>
  </div>`;
}

function customerSalesHtml(customerId, customerName, list, total, summary = {}, active = {}) {
  const filter = customerSalesFilterHtml(customerId, customerName, active);
  const summaryHtml = `<div class="drawer-summary">
    <strong>${escapeHtml(summary.label || customerName)}</strong>
    <span>共 ${escapeHtml(summary.total ?? total ?? list.length)} 单 · 合计 ¥${money(summary.total_amount || 0)} · 余额 ${signedMoneyText(summary.balance_amount || 0)}</span>
  </div>`;
  if (!list.length) return `<div class="management-list customer-sales-list">${filter}${summaryHtml}<div class="empty">${escapeHtml(summary.label || customerName)} 暂无绑定销售单</div></div>`;
  return `<div class="management-list customer-sales-list">
    ${filter}
    ${summaryHtml}
    ${list.map((row) => `<article class="record-card customer-sale-card">
      <div class="record-main">
        <div><h3>${escapeHtml(row.sales_no || `销售单#${row.id}`)}</h3><p>${escapeHtml(nativeDateText(row.sales_at))}</p></div>
        <span class="tag green-outline">${escapeHtml(row.pay_status_text || payStatusText(row.pay_status))}</span>
      </div>
      <div class="record-metrics">
        ${metricHtml("数量", row.total_quantity || 0)}
        ${metricHtml("应收金额", `¥${money(row.receivable_amount || row.goods_amount || 0)}`, "accent")}
        ${metricHtml("付款", [row.pay_type_text || payTypeText(row.pay_type), row.pay_status_text || payStatusText(row.pay_status)].filter(Boolean).join(" / "))}
        ${metricHtml("开单人", operatorText(row))}
      </div>
      ${row.items_preview ? `<p class="record-note">${escapeHtml(row.items_preview)}</p>` : ""}
    </article>`).join("")}
  </div>`;
}

async function openCustomerSales(customerId, customerName = "客户", filters = {}) {
  if (!customerId) return;
  openDrawer("customer_sales", { customerName });
  const body = $("drawerBody");
  if (body) body.innerHTML = '<div class="empty">正在加载销售单...</div>';
  const res = await api(`/api/customers/${customerId}/sales?${query({ page: 1, page_size: 100, period: filters.period || "", month: filters.month || "" })}`);
  const list = normalizeList(res);
  if (body) body.innerHTML = customerSalesHtml(
    customerId,
    customerName,
    list,
    (res.data && res.data.total) || list.length,
    (res.data && res.data.summary) || {},
    filters
  );
}
window.openCustomerSales = openCustomerSales;

function balanceLedgerHtml(customerName, list, total, summary = {}) {
  const header = `<div class="drawer-summary balance-ledger-summary">
    <strong>${escapeHtml(customerName || summary.customer_name || "客户")}</strong>
    <span>当前余额 ${signedMoneyText(summary.balance_amount || 0)} · 未结 ¥${money(summary.debt_amount || 0)} · 共 ${total || list.length} 条</span>
  </div>`;
  if (!list.length) {
    return `<div class="management-list balance-ledger-list">${header}<div class="empty">暂无余额流水</div></div>`;
  }
  return `<div class="management-list balance-ledger-list">
    ${header}
    ${list.map((row) => {
      const delta = Number(row.balance_delta || 0);
      const deltaTone = delta < 0 ? "negative" : (delta > 0 ? "positive" : "");
      const title = [row.entry_type_text || row.entry_type || "余额流水", row.pay_type_text || ""].filter(Boolean).join(" / ");
      return `<article class="record-card balance-ledger-card">
        <div class="record-main">
          <div>
            <h3>${escapeHtml(title)}</h3>
            <p>${escapeHtml(nativeDateText(row.created_at))}${row.ledger_no ? ` · ${escapeHtml(row.ledger_no)}` : ""}</p>
          </div>
          <strong class="balance-ledger-delta ${deltaTone}">${escapeHtml(signedDeltaText(row.balance_delta || 0))}</strong>
        </div>
        <div class="record-metrics">
          ${metricHtml("金额", `¥${money(row.amount || 0)}`)}
          ${metricHtml("抵扣", `¥${money(row.applied_amount || 0)}`)}
          ${metricHtml("月份", row.related_month || "-")}
          ${metricHtml("操作人", operatorText(row))}
        </div>
        ${row.note ? `<p class="record-note">${escapeHtml(row.note)}</p>` : ""}
      </article>`;
    }).join("")}
  </div>`;
}

async function openCustomerBalanceLedger(customerId, customerName = "客户") {
  if (!customerId) return;
  openDrawer("customer_balance_ledger", { customerName });
  const body = $("drawerBody");
  if (body) body.innerHTML = '<div class="empty">正在加载余额明细...</div>';
  const res = await api(`/api/customers/${customerId}/balance-ledger?${query({ page: 1, page_size: 100 })}`);
  const list = normalizeList(res);
  if (body) body.innerHTML = balanceLedgerHtml(
    customerName,
    list,
    (res.data && res.data.total) || list.length,
    (res.data && res.data.summary) || {}
  );
}
window.openCustomerBalanceLedger = openCustomerBalanceLedger;

function paymentTypeOptions(selected = "wechat") {
  const options = [
    ["wechat", "微信"],
    ["cash", "现金"],
    ["bank", "转账"],
    ["alipay", "支付宝"]
  ];
  return options.map(([value, label]) => `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`).join("");
}

function customerById(customerId) {
  const id = Number(customerId || 0);
  return (state.lastCustomers || []).find((customer) => Number(customer.id || customer.customer_id || 0) === id) || {};
}

function balanceActionTitle(action) {
  return {
    receipt: "收款",
    recharge: "充值",
    settlement: "结款",
    adjust: "调整余额"
  }[String(action || "")] || "余额操作";
}

function selectedBalanceMonth() {
  const value = document.querySelector("[data-balance-month].active");
  return value ? value.dataset.balanceMonth : "";
}

async function loadBalanceMonthSummary(customerId, month) {
  const box = $("balanceMonthSummary");
  if (!box || !customerId || !month) return;
  box.textContent = "正在读取月份销售单...";
  const res = await api(`/api/customers/${customerId}/sales?${query({ page: 1, page_size: 1, month })}`);
  const summary = (res.data && res.data.summary) || {};
  const unpaid = Number(summary.unpaid_amount || 0);
  const total = Number(summary.total_amount || 0);
  const amountInput = $("balanceAmountInput");
  if (amountInput) amountInput.value = unpaid > 0 ? money(unpaid) : "";
  box.textContent = `${summary.label || month}：共 ${summary.total || 0} 单，合计 ¥${money(total)}，未结 ¥${money(unpaid)}`;
}

function openCustomerBalanceDialog(customerId, customerName, action) {
  if (!customerId) return;
  const title = balanceActionTitle(action);
  const isSettlement = action === "settlement";
  const isAdjust = action === "adjust";
  const customer = customerById(customerId);
  const currentBalance = customer.balance_amount;
  const now = new Date();
  const year = now.getFullYear();
  const currentMonth = `${year}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  let mask = $("customerBalanceMask");
  if (!mask) {
    mask = document.createElement("div");
    mask.id = "customerBalanceMask";
    mask.className = "confirm-mask";
    document.body.appendChild(mask);
  }
  const monthButtons = Array.from({ length: 12 }, (_, i) => i + 1).map((num) => {
    const value = `${year}-${String(num).padStart(2, "0")}`;
    return `<button type="button" class="${value === currentMonth ? "active" : ""}" data-balance-month="${value}">${num}月</button>`;
  }).join("");
  mask.innerHTML = `
    <div class="confirm-box balance-form-box" role="dialog" aria-modal="true">
      <h3 class="confirm-title">${escapeHtml(title)} · ${escapeHtml(customerName || "客户")}</h3>
      <div class="balance-form">
        ${isSettlement ? `
          <label>结款月份
            <select id="balanceYearSelect">
              <option value="${year}">${year}年</option>
              <option value="${year - 1}">${year - 1}年</option>
              <option value="${year - 2}">${year - 2}年</option>
            </select>
          </label>
          <div class="balance-month-grid">${monthButtons}</div>
          <div class="balance-summary" id="balanceMonthSummary">请选择月份</div>
        ` : ""}
        ${isAdjust ? `<div class="balance-summary">当前余额 ${signedMoneyText(currentBalance || 0)}。输入正数就是增加余额，输入负数就是减少余额。</div>` : ""}
        <label>${isSettlement ? "本次收款金额" : (isAdjust ? "调整金额" : "金额")}
          <input id="balanceAmountInput" type="number" ${isAdjust ? "" : 'min="0"'} step="0.01" placeholder="${isAdjust ? "例如 100 或 -50" : "0.00"}">
        </label>
        ${isAdjust ? "" : `<label>收款方式
          <select id="balancePayType">${paymentTypeOptions("wechat")}</select>
        </label>`}
        <label>备注
          <textarea id="balanceNoteInput" placeholder="可不填"></textarea>
        </label>
      </div>
      <div class="confirm-actions" style="margin-top:14px;">
        <button id="customerBalanceCancel">取消</button>
        <button class="danger-confirm" id="customerBalanceOk">确认${escapeHtml(title)}</button>
      </div>
    </div>`;
  const close = () => mask.classList.remove("open");
  $("customerBalanceCancel").onclick = close;
  $("customerBalanceOk").onclick = () => submitCustomerBalanceAction(customerId, customerName, action).catch((err) => toast(err.message, true));
  mask.onclick = (event) => { if (event.target === mask) close(); };
  if (isSettlement) {
    mask.querySelectorAll("[data-balance-month]").forEach((button) => {
      button.onclick = () => {
        const selectedYear = Number(($("balanceYearSelect") && $("balanceYearSelect").value) || year);
        const monthNum = String(button.dataset.balanceMonth || "").slice(5, 7);
        const monthValue = `${selectedYear}-${monthNum}`;
        mask.querySelectorAll("[data-balance-month]").forEach((node) => node.classList.toggle("active", node === button));
        button.dataset.balanceMonth = monthValue;
        loadBalanceMonthSummary(customerId, monthValue).catch((err) => toast(err.message, true));
      };
    });
    $("balanceYearSelect").onchange = () => {
      const active = mask.querySelector("[data-balance-month].active") || mask.querySelector("[data-balance-month]");
      if (active) active.click();
    };
    loadBalanceMonthSummary(customerId, currentMonth).catch((err) => toast(err.message, true));
  }
  requestAnimationFrame(() => mask.classList.add("open"));
}
window.openCustomerBalanceDialog = openCustomerBalanceDialog;

async function submitCustomerBalanceAction(customerId, customerName, action) {
  const amount = Number(($("balanceAmountInput") && $("balanceAmountInput").value) || 0);
  const isAdjust = action === "adjust";
  if (isAdjust) {
    if (!Number.isFinite(amount) || amount === 0) throw new Error("请输入调整金额，不能为0");
  } else if (!amount || amount <= 0) {
    throw new Error("请输入正确金额");
  }
  const body = {
    action,
    amount,
    pay_type: ($("balancePayType") && $("balancePayType").value) || (isAdjust ? "adjustment" : "wechat"),
    note: ($("balanceNoteInput") && $("balanceNoteInput").value.trim()) || ""
  };
  if (action === "settlement") {
    body.month = selectedBalanceMonth();
    if (!body.month) throw new Error("请选择结款月份");
  }
  const res = await api(`/api/customers/${customerId}/balance`, { method: "POST", body });
  const mask = $("customerBalanceMask");
  if (mask) mask.classList.remove("open");
  const data = res.data || {};
  toast(action === "settlement"
    ? `结款完成：${data.month || ""} ${data.order_count || 0} 单`
    : `${balanceActionTitle(action)}完成`
  );
  await loadCustomers(state.customerPage);
  if (action === "settlement") {
    openCustomerSales(customerId, customerName, { month: body.month }).catch((err) => toast(err.message, true));
  }
}

async function updateUserRole(userId, role) {
  if (!userId || !role) return;
  await api(`/api/users/${userId}`, { method: "PATCH", body: { role } });
  toast("角色已更新");
  if ($("settings") && $("settings").classList.contains("active") && state.settingsTab === "users") {
    loadPermissionSettings(true);
  } else {
    loadCustomers(state.customerPage);
  }
}
window.updateUserRole = updateUserRole;

async function updateUserActive(userId, isActive) {
  if (!userId) return;
  await api(`/api/users/${userId}`, { method: "PATCH", body: { is_active: Number(isActive || 0) } });
  toast(Number(isActive || 0) ? "账号已启用" : "账号已停用");
  if ($("settings") && $("settings").classList.contains("active") && state.settingsTab === "users") {
    loadPermissionSettings(true);
  } else {
    loadCustomers(state.customerPage);
  }
}
window.updateUserActive = updateUserActive;

function renderCustomerPager() {
  const pager = $("customerPager");
  if (!pager) return;
  if (state.customerTab !== "users") { pager.innerHTML = ""; return; }
  const totalPages = Math.max(1, Math.ceil(state.customerTotal / state.customerPageSize));
  if (totalPages <= 1) { pager.innerHTML = ""; return; }
  pager.innerHTML =
    '<button ' + (state.customerPage <= 1 ? "disabled" : "") + ' onclick="loadCustomers(' + (state.customerPage - 1) + ')">上一页</button>' +
    '<span class="page-info">' + state.customerPage + ' / ' + totalPages + '</span>' +
    '<button ' + (state.customerPage >= totalPages ? "disabled" : "") + ' onclick="loadCustomers(' + (state.customerPage + 1) + ')">下一页</button>';
}

function setCustomerTab(tab) {
  state.customerTab = tab || "customers";
  state.customerPage = 1;
  document.querySelectorAll("[data-customer-tab]").forEach((button) => {
    button.classList.toggle("active", button.dataset.customerTab === state.customerTab);
  });
  loadCustomers(1);
}

function inventoryActionForm(row = {}) {
  const isPurchase = row.type === "purchase";
  const isStocktaking = row.type === "stocktaking";
  const type = isPurchase ? "purchase" : (isStocktaking ? "stocktaking" : "transfer");
  return `
    <input id="drawerInvType" type="hidden" value="${escapeAttr(type)}">
    <input id="drawerInvProductId" type="hidden" value="${escapeAttr(row.product_id || "")}">
    <label>商品</label><input id="drawerInvTitle" value="${escapeAttr(row.title || "")}">
    <div class="two-col">
      <div><label>颜色</label><input id="drawerInvColor" value="${escapeAttr(row.color || "")}"></div>
      <div><label>${isStocktaking ? "盘点后数量" : "数量"}</label><input id="drawerInvQty" type="number" min="${isStocktaking ? "0" : "1"}" value="${isStocktaking ? "0" : "1"}"></div>
    </div>
    ${isPurchase || isStocktaking ? `<label>${isStocktaking ? "盘点仓库" : "入库仓库"}</label><select id="drawerInvWarehouse"><option value="2">百鑫仓库</option><option value="1">自己店里</option></select>` : `
      <div class="two-col">
        <div><label>调出仓库</label><select id="drawerInvOutWarehouse"><option value="2">百鑫仓库</option><option value="1">自己店里</option></select></div>
        <div><label>调入仓库</label><select id="drawerInvEnterWarehouse"><option value="1">自己店里</option><option value="2">百鑫仓库</option></select></div>
      </div>
    `}
  `;
}

function prepareInventoryAction(title, color, type, productId = "") {
  const actionType = type === "purchase" ? "purchase" : (type === "stocktaking" ? "stocktaking" : "transfer");
  state.inventoryAction = {
    type: actionType,
    title,
    color,
    product_id: productId
  };
  openDrawer("inventory_action", state.inventoryAction);
}

async function searchMoveProducts() {
  if (!$("moveKeyword")) throw new Error("API 操作台已移除");
  const keyword = $("moveKeyword").value.trim();
  if (!keyword) return toast("请输入商品关键词", true);
  const list = normalizeList(await api(`/api/product/search?${query({ keyword })}`));
  state.moveProductResults = list;
  $("moveProductChoices").innerHTML = list.length ? list.slice(0, LIST_LIMITS.choice).map((product) => `<button class="choice" onclick="selectMoveProduct(${Number(product.id || product.product_id || 0)})"><strong>${escapeHtml(product.title || product.name || "商品")}</strong><div class="muted">${escapeHtml(product.spec || product.simple_desc || "")} · ID ${escapeHtml(product.id || product.product_id || "")}</div></button>`).join("") : '<div class="empty">没有匹配商品</div>';
}

function selectMoveProduct(id) {
  if (!$("moveKeyword")) return;
  const product = state.moveProductResults.find((item) => Number(item.id || item.product_id) === Number(id));
  if (!product) return;
  state.moveProduct = product;
  $("moveKeyword").value = [product.title || product.name, product.spec].filter(Boolean).join(" ");
  $("moveSelectedHint").textContent = `已选择：${$("moveKeyword").value}`;
  $("moveProductChoices").innerHTML = "";
}

async function ensureMoveProduct() {
  if (state.moveProduct) return state.moveProduct;
  await searchMoveProducts();
  if (state.moveProductResults.length === 1) {
    selectMoveProduct(state.moveProductResults[0].id || state.moveProductResults[0].product_id);
    return state.moveProduct;
  }
  throw new Error("请先选择准确商品");
}

async function transferInventory() {
  const product = await ensureMoveProduct();
  const qty = Number($("moveQty").value || 0);
  const outWarehouseId = Number($("moveTransferFrom").value || 2);
  const enterWarehouseId = Number($("moveTransferTo").value || 1);
  if (qty <= 0) throw new Error("数量必须大于0");
  if (outWarehouseId === enterWarehouseId) throw new Error("调出仓库和调入仓库不能相同");
  await api("/api/inventory/transfer", {
    method: "POST",
    body: { product_id: product.product_id || product.id, unit_id: product.unit_id || 1, quantity: qty, out_warehouse_id: outWarehouseId, enter_warehouse_id: enterWarehouseId, color: product.spec || product.color || "" }
  });
  toast("调货已提交");
  loadInventory(undefined, state.inventoryPage);
}

async function purchaseInventory() {
  const product = await ensureMoveProduct();
  const qty = Number($("moveQty").value || 0);
  if (qty <= 0) throw new Error("数量必须大于0");
  await api("/api/inventory/purchase", {
    method: "POST",
    body: { product_id: product.product_id || product.id, unit_id: product.unit_id || 1, quantity: qty, warehouse_id: Number($("moveWarehouse").value || 2), color: product.spec || product.color || "" }
  });
  toast("进货已提交");
  loadInventory(undefined, state.inventoryPage);
}

function saleCustomerId(customer = {}) {
  return Number(customer.id || customer.customer_id || customer.company_id || 0);
}

function saleCustomerName(customer = {}) {
  return customer.name || customer.customer_name || customer.company_name || customer.title || "客户";
}

function saleCustomerMobile(customer = {}) {
  return customer.mobile || customer.contacts_mobile || customer.contacts_tel || customer.tel || customer.telephone || customer.phone || "";
}

function saleCustomerMonthly(customer = {}) {
  return Number(customer.is_monthly_customer || customer.monthly_customer || 0) === 1;
}

function applySaleCustomerPaymentRule(isMonthly) {
  if ($("salePaymentStatus")) $("salePaymentStatus").value = isMonthly ? "monthly" : "paid";
  if ($("salePayType")) $("salePayType").value = "wechat";
  syncSalePaymentUi();
}

async function refreshSaleCustomerMonthlyRule(customerId, customerName = "") {
  if (!customerId || !customerName) return false;
  const res = await api(`/api/customer/list?${query({ keyword: customerName })}`);
  const list = normalizeList(res);
  const matched = list.find((customer) => Number(saleCustomerId(customer)) === Number(customerId));
  if (!matched || !saleCustomerMonthly(matched)) return false;
  if (!state.saleCustomer || Number(state.saleCustomer.id || 0) !== Number(customerId)) return false;
  state.saleCustomer = {
    ...state.saleCustomer,
    name: saleCustomerName(matched) || state.saleCustomer.name || customerName,
    is_monthly_customer: 1
  };
  if ($("saleSelectedCustomer")) $("saleSelectedCustomer").textContent = `${state.saleCustomer.name} · 月结客户`;
  if ($("salePaymentStatus") && $("salePaymentStatus").value === "paid") {
    applySaleCustomerPaymentRule(true);
  }
  return true;
}

async function searchSaleCustomers() {
  if (!$("saleCustomer")) throw new Error("开单页面未加载");
  const keyword = $("saleCustomer").value.trim();
  if (!keyword) throw new Error("请输入客户关键词");
  const list = normalizeList(await api(`/api/customer/list?${query({ keyword })}`));
  state.saleCustomerResults = list;
  $("saleCustomerChoices").innerHTML = list.length ? list.slice(0, LIST_LIMITS.choice).map((customer) => {
    const name = saleCustomerName(customer);
    const mobile = saleCustomerMobile(customer);
    const id = saleCustomerId(customer);
    const monthly = saleCustomerMonthly(customer);
    return `<button class="choice" data-sale-customer-id="${id}" data-sale-customer-name="${escapeAttr(name)}" data-sale-customer-monthly="${monthly ? 1 : 0}"><strong>${escapeHtml(name)}</strong><div class="muted">${mobile ? escapeHtml(mobile) + " · " : ""}ID ${escapeHtml(id || "")}${monthly ? " · 月结客户" : ""}</div></button>`;
  }).join("") : '<div class="empty">没有客户结果，可以直接创建新客户。</div>';
  if (list.length === 1) {
    const customer = list[0];
    selectSaleCustomer(saleCustomerId(customer), saleCustomerName(customer), saleCustomerMonthly(customer));
  }
  return list;
}

function selectSaleCustomer(id, name, isMonthly = false) {
  state.saleCustomer = { id, name, is_monthly_customer: isMonthly ? 1 : 0 };
  if (!$("saleCustomer")) return;
  $("saleCustomer").value = name;
  $("saleSelectedCustomer").textContent = isMonthly ? `${name} · 月结客户` : name;
  applySaleCustomerPaymentRule(isMonthly);
  $("saleCustomerChoices").innerHTML = "";
  renderSaleLines();
  if (!isMonthly) refreshSaleCustomerMonthlyRule(id, name).catch((err) => console.warn("月结客户校验失败", err));
}

function openSaleCustomerCreateDialog() {
  if (!$("saleCustomer")) return;
  const prefill = $("saleCustomer").value.trim();
  let mask = $("saleCustomerCreateMask");
  if (!mask) {
    mask = document.createElement("div");
    mask.id = "saleCustomerCreateMask";
    mask.className = "confirm-mask";
    mask.innerHTML = `
      <div class="confirm-box" role="dialog" aria-modal="true">
        <h3 class="confirm-title">创建客户</h3>
        <div class="confirm-message">客户创建成功后会自动选中，可直接继续开单。</div>
        <div class="customer-create-form">
          <label>客户名称<input id="createCustomerName" autocomplete="off"></label>
          <label>联系人<input id="createCustomerContact" autocomplete="off" placeholder="可不填"></label>
          <label>电话<input id="createCustomerPhone" autocomplete="off" placeholder="可不填"></label>
        </div>
        <div class="confirm-actions" style="margin-top:16px;">
          <button id="saleCustomerCreateCancel">取消</button>
          <button class="danger-confirm" id="saleCustomerCreateOk">创建并选中</button>
        </div>
      </div>`;
    document.body.appendChild(mask);
    mask.addEventListener("click", (event) => {
      if (event.target === mask) closeSaleCustomerCreateDialog();
    });
  }
  $("createCustomerName").value = prefill;
  $("createCustomerContact").value = "";
  $("createCustomerPhone").value = "";
  $("saleCustomerCreateCancel").onclick = closeSaleCustomerCreateDialog;
  $("saleCustomerCreateOk").onclick = () => createSaleCustomerFromDialog().catch((err) => toast(err.message, true));
  requestAnimationFrame(() => {
    mask.classList.add("open");
    $("createCustomerName").focus();
    $("createCustomerName").select();
  });
}

function closeSaleCustomerCreateDialog() {
  const mask = $("saleCustomerCreateMask");
  if (mask) mask.classList.remove("open");
}

async function createSaleCustomerFromDialog() {
  const name = $("createCustomerName")?.value.trim() || "";
  const contactsName = $("createCustomerContact")?.value.trim() || "";
  const contactsTel = $("createCustomerPhone")?.value.trim() || "";
  if (!name) throw new Error("请输入客户名称");
  const ok = $("saleCustomerCreateOk");
  if (ok) {
    ok.disabled = true;
    ok.classList.add("loading");
  }
  try {
    const res = await api("/api/customer/create", {
      method: "POST",
      body: { name, contacts_name: contactsName, contacts_tel: contactsTel }
    });
    const customer = res.data || {};
    const id = saleCustomerId(customer);
    const customerName = saleCustomerName(customer) || name;
    if (!id) throw new Error("客户已创建，但没有取到客户ID，请搜索客户后再选择");
    closeSaleCustomerCreateDialog();
    selectSaleCustomer(id, customerName, saleCustomerMonthly(customer));
    if ($("saleCustomerChoices")) {
      $("saleCustomerChoices").innerHTML = `<div class="empty">${customer.existed ? "客户已存在，已选中。" : "客户创建成功，已选中。"}</div>`;
    }
    toast(customer.existed ? "客户已存在，已选中" : "客户创建成功，已选中");
  } finally {
    if (ok) {
      ok.disabled = false;
      ok.classList.remove("loading");
    }
  }
}

async function searchSaleProducts() {
  if (!$("saleProduct")) throw new Error("开单页面未加载");
  const keyword = $("saleProduct").value.trim();
  if (!keyword) throw new Error("请输入商品关键词");
  const list = normalizeList(await api(`/api/product/list?${query({ keyword, page: 1, page_size: LIST_LIMITS.choice, group: 1 })}`));
  state.saleProductGroups = list;
  state.saleProductResults = list;
  $("saleProductChoices").innerHTML = list.length ? list.slice(0, LIST_LIMITS.choice).map((product) => {
    const id = Number(product.id || product.product_id || 0);
    const title = product.title || product.name || "商品";
    const specs = Number(product.spec_count || productVariants(product).length || 1);
    const stock = productTracksInventory(product) ? (product.inventory ?? 0) : "不管库存";
    const category = product.product_category_text || product.simple_desc || "";
    return `<button class="choice" data-sale-product-id="${id}"><strong>${escapeHtml(title)}</strong><div class="muted">${escapeHtml(category)} · ${specs} 个颜色/规格 · 库存 ${escapeHtml(stock)} · ${productPriceText(product)}</div></button>`;
  }).join("") : '<div class="empty">没有商品结果</div>';
  if (list.length === 1) await openSaleProductVariants(list[0].id || list[0].product_id);
  return list;
}

function saleWarehouseOptions(selected) {
  const value = String(selected || $("saleWarehouse")?.value || 2);
  return [
    { id: 2, name: "百鑫仓库" },
    { id: 1, name: "自己店里" }
  ].map((item) => `<option value="${item.id}" ${String(item.id) === value ? "selected" : ""}>${item.name}</option>`).join("");
}

function productTracksInventory(item) {
  return Number((item && item.is_stock_item) ?? 1) !== 0;
}

function saleVariantStockText(variant) {
  if (!productTracksInventory(variant)) return "不管库存";
  if (variant.inventory !== undefined && variant.inventory !== null && variant.inventory !== "") return `库存 ${variant.inventory}`;
  return "库存 -";
}

async function openSaleProductVariants(id) {
  const product = state.saleProductResults.find((item) => Number(item.id || item.product_id) === Number(id));
  if (!product) return;
  const variants = productVariants(product);
  if (!variants.length) throw new Error("这个商品没有可选颜色/规格");
  if (variants.length === 1) {
    await selectSaleProductVariant(product, variants[0]);
    return;
  }
  await showSaleVariantPicker(product, variants);
}

async function selectSaleProductVariant(product, variant) {
  const productId = variant.id || variant.product_id || product.id || product.product_id;
  let price = Number(variant.price || variant.min_price || product.price || product.min_price || 0);
  if (state.saleCustomer) {
    try {
      const unitId = variant.unit_id || product.unit_id || 1;
      const priceRes = await api(`/api/customer/price?${query({ customer_id: state.saleCustomer.id, product_id: productId, unit_id: unitId })}`);
      if (priceRes.data && priceRes.data.price) price = Number(priceRes.data.price);
    } catch {}
  }
  const line = {
    product_id: productId,
    unit_id: variant.unit_id || product.unit_id || 1,
    title: product.title || product.name || variant.title || variant.name || "商品",
    spec: variant.spec || variant.color || product.spec || "",
    coding: variant.coding || product.coding || "",
    price,
    warehouse_id: Number($("saleWarehouse")?.value || 2),
    image: productImage(variant) || productImage(product),
    inventory: variant.inventory ?? product.inventory ?? "",
    is_stock_item: Number((variant.is_stock_item ?? product.is_stock_item ?? 1))
  };
  state.saleProduct = line;
  if (!$("saleProduct")) return;
  $("saleProduct").value = [state.saleProduct.title, state.saleProduct.spec].filter(Boolean).join(" ");
  $("saleProductChoices").innerHTML = "";
  await addSaleLine();
}

function showSaleVariantPicker(product, variants) {
  return new Promise((resolve) => {
    let mask = $("saleVariantMask");
    if (!mask) {
      mask = document.createElement("div");
      mask.id = "saleVariantMask";
      mask.className = "confirm-mask";
      mask.innerHTML = `
        <div class="confirm-box inventory-popup-box" role="dialog" aria-modal="true">
          <h3 class="confirm-title" id="saleVariantTitle"></h3>
          <p class="confirm-message" id="saleVariantMessage"></p>
          <div class="sale-variant-list" id="saleVariantList"></div>
          <div class="confirm-actions inventory-popup-actions">
            <button id="saleVariantCancel">取消</button>
          </div>
        </div>`;
      document.body.appendChild(mask);
    }
    $("saleVariantTitle").textContent = product.title || product.name || "选择颜色";
    $("saleVariantMessage").textContent = "选择一个颜色/规格后会加入销售明细。";
    $("saleVariantList").innerHTML = variants.map((variant, index) => {
      const color = variant.spec || variant.color || "默认";
      const price = Number(variant.price || variant.min_price || product.price || 0);
      const code = variant.coding || product.coding || "";
      return `<button type="button" class="sale-variant-card" data-sale-variant-index="${index}">
        <strong>${escapeHtml(color)}</strong>
        <div class="sale-variant-meta">
          <span>${escapeHtml(saleVariantStockText(variant))}</span>
          <span>¥${money(price)}</span>
          ${code ? `<span>${escapeHtml(code)}</span>` : ""}
        </div>
      </button>`;
    }).join("");
    const cleanup = (variant = null) => {
      mask.classList.remove("open");
      $("saleVariantCancel").onclick = null;
      $("saleVariantList").onclick = null;
      mask.onclick = null;
      document.removeEventListener("keydown", onKey);
      resolve(variant);
    };
    const onKey = (event) => {
      if (event.key === "Escape") cleanup(null);
    };
    $("saleVariantCancel").onclick = () => cleanup(null);
    $("saleVariantList").onclick = (event) => {
      const button = event.target.closest("[data-sale-variant-index]");
      if (!button) return;
      const variant = variants[Number(button.dataset.saleVariantIndex)];
      cleanup(variant || null);
    };
    mask.onclick = (event) => {
      if (event.target === mask) cleanup(null);
    };
    document.addEventListener("keydown", onKey);
    requestAnimationFrame(() => mask.classList.add("open"));
  }).then(async (variant) => {
    if (variant) await selectSaleProductVariant(product, variant);
  });
}

async function addSaleLine() {
  if (!$("saleQty")) throw new Error("开单页面未加载");
  if (!state.saleProduct) await searchSaleProducts();
  if (!state.saleProduct) throw new Error("请先选择商品");
  const qty = Math.max(1, Number($("saleQty").value || 1));
  const existing = state.saleLines.find((line) => Number(line.product_id) === Number(state.saleProduct.product_id) && Number(line.warehouse_id || 0) === Number(state.saleProduct.warehouse_id || 0));
  if (existing) {
    existing.buy_number = Number(existing.buy_number || 0) + qty;
    existing.price = state.saleProduct.price;
  } else {
    state.saleLines.push({ ...state.saleProduct, buy_number: qty, warehouse_id: Number(state.saleProduct.warehouse_id || $("saleWarehouse")?.value || 2) });
  }
  state.saleProduct = null;
  $("saleProduct").value = "";
  $("saleQty").value = 1;
  renderSaleLines();
  $("saleProduct").focus();
}

function renderSaleLines() {
  if (!$("saleLines") || !$("saleTotal")) return;
  $("saleLines").innerHTML = state.saleLines.length ? state.saleLines.map((line, index) => `
    <tr>
      <td>
        <div class="sale-product-name">${escapeHtml(line.title)}</div>
        <div class="sale-product-sub">ID ${escapeHtml(line.product_id)}${line.coding ? ` · ${escapeHtml(line.coding)}` : ""}${productTracksInventory(line) ? "" : " · 不管库存"}</div>
      </td>
      <td>${escapeHtml(line.spec || "默认")}</td>
      <td class="qty-cell"><input type="number" min="1" value="${escapeAttr(line.buy_number)}" data-sale-line-index="${index}" data-sale-line-field="buy_number"></td>
      <td class="warehouse-cell"><select data-sale-line-index="${index}" data-sale-line-field="warehouse_id">${saleWarehouseOptions(line.warehouse_id)}</select></td>
      <td class="price-cell"><input type="number" min="0" step="0.01" value="${escapeAttr(line.price)}" data-sale-line-index="${index}" data-sale-line-field="price"></td>
      <td class="amount-cell">¥${money(Number(line.buy_number || 0) * Number(line.price || 0))}</td>
      <td class="operate-cell"><button class="remove-line" data-remove-sale-line="${index}" title="删除明细">删除</button></td>
    </tr>`).join("") : '<tr><td class="sale-table-empty" colspan="7">还没有销售明细，先搜索礼盒并选择颜色。</td></tr>';
  const total = state.saleLines.reduce((sum, line) => sum + Number(line.buy_number || 0) * Number(line.price || 0), 0);
  const qty = state.saleLines.reduce((sum, line) => sum + Number(line.buy_number || 0), 0);
  $("saleTotal").textContent = `¥${money(total)}`;
  if ($("saleSummaryCustomer")) $("saleSummaryCustomer").textContent = state.saleCustomer ? state.saleCustomer.name : "未选择";
  if ($("saleSummaryCount")) $("saleSummaryCount").textContent = String(state.saleLines.length);
  if ($("saleSummaryQty")) $("saleSummaryQty").textContent = String(qty);
  if ($("saleSummaryAmount")) $("saleSummaryAmount").textContent = `¥${money(total)}`;
  if ($("saleSubmitAmount")) $("saleSubmitAmount").textContent = `¥${money(total)}`;
}

function updateSaleLine(index, field, value) {
  if (!state.saleLines[index]) return;
  if (field === "warehouse_id") state.saleLines[index][field] = Number(value || 0);
  else state.saleLines[index][field] = Number(value || 0);
  renderSaleLines();
}

function removeSaleLine(index) {
  state.saleLines.splice(index, 1);
  renderSaleLines();
}

function clearSaleForm() {
  state.saleCustomer = null;
  state.saleProduct = null;
  state.saleProductGroups = [];
  state.saleProductResults = [];
  state.saleLines = [];
  state.lastSaleResult = null;
  if (!$("saleCustomer")) return;
  $("saleCustomer").value = "";
  $("saleProduct").value = "";
  $("saleQty").value = 1;
  $("saleCustomerChoices").innerHTML = "";
  $("saleProductChoices").innerHTML = "";
  $("saleSelectedCustomer").textContent = "未选择客户";
  if ($("salePaymentStatus")) $("salePaymentStatus").value = "paid";
  if ($("salePayType")) $("salePayType").value = "wechat";
  syncSalePaymentUi();
  if ($("saleResultCard")) $("saleResultCard").innerHTML = "<strong>开单结果</strong><p>提交后这里会显示销售单号、打印和删除入口。</p>";
  setDefaultSaleCreateTime(true);
  renderSaleLines();
}

function salePaymentPayload() {
  if (state.saleCustomer && Number(state.saleCustomer.is_monthly_customer || 0) === 1) {
    return { pay_status: "monthly", pay_type: "monthly" };
  }
  const status = ($("salePaymentStatus") && $("salePaymentStatus").value) || "paid";
  if (status === "monthly") return { pay_status: "monthly", pay_type: "monthly" };
  if (status === "unpaid") return { pay_status: "unpaid", pay_type: "" };
  return { pay_status: "paid", pay_type: ($("salePayType") && $("salePayType").value) || "wechat" };
}

function syncSalePaymentUi() {
  const status = ($("salePaymentStatus") && $("salePaymentStatus").value) || "paid";
  const field = $("salePayTypeField");
  if (field) field.style.display = status === "paid" ? "" : "none";
}

async function quickSale() {
  if (state.saleSubmitting) return;
  if (!$('saleCustomer')) throw new Error('开单页面未加载');
  if (!state.saleCustomer) await searchSaleCustomers();
  if (!state.saleCustomer) throw new Error('请先选择客户');
  await refreshSaleCustomerMonthlyRule(state.saleCustomer.id, state.saleCustomer.name).catch((err) => console.warn("月结客户校验失败", err));
  if (!state.saleLines.length) await addSaleLine();
  const warehouseId = Number($('saleWarehouse').value || 2);
  const createTime = saleCreateTimeText();
  const payment = salePaymentPayload();
  if (!createTime) throw new Error('请选择创建时间');
  const invalid = state.saleLines.find((line) => Number(line.buy_number || 0) <= 0 || Number(line.price || 0) < 0 || !Number(line.warehouse_id || 0));
  if (invalid) throw new Error('请检查商品数量、单价和仓库');
  const buttons = [$('quickSaleBtn'), $('quickSaleBtnBottom')].filter(Boolean);
  state.saleSubmitting = true;
  buttons.forEach((button) => { button.disabled = true; button.classList.add('loading'); });
  try {
    const res = await api('/api/sales/add', {
      method: 'POST',
      body: {
        customer_id: state.saleCustomer.id,
        customer_name: state.saleCustomer.name,
        warehouse_id: warehouseId,
        create_time: createTime,
        pay_status: payment.pay_status,
        pay_type: payment.pay_type,
        products: state.saleLines.map((line) => ({
          product_id: line.product_id,
          unit_id: line.unit_id || 1,
          warehouse_id: Number(line.warehouse_id || warehouseId),
          buy_number: line.buy_number,
          price: line.price
        }))
      }
    });
    state.lastSaleResult = res.data || res;
    renderSaleResult(state.lastSaleResult);
    toast('销售单已创建');
    await loadSales();
    loadDashboardSummary();
    renderSaleLines();
  } finally {
    state.saleSubmitting = false;
    buttons.forEach((button) => { button.disabled = false; button.classList.remove('loading'); });
  }
}

function setDefaultSaleCreateTime(force = false) {
  const input = $("saleCreateTime");
  if (!input || (input.value && !force)) return;
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  input.value = now.toISOString().slice(0, 16);
}

function saleCreateTimeText() {
  const input = $("saleCreateTime");
  if (!input) return "";
  if (!input.value) return "";
  return input.value.replace("T", " ") + ":00";
}

function salesResultId(result) {
  if (!result || typeof result !== "object") return "";
  const direct = result.id || result.sales_id || result.order_id || result.order_no || result.no || result.data_id || "";
  if (direct) return direct;
  if (result.data && typeof result.data === "object") return salesResultId(result.data);
  if (result.result && typeof result.result === "object") return salesResultId(result.result);
  return "";
}

function renderSaleResult(result) {
  if (!$("saleResultCard")) return;
  const salesId = salesResultId(result);
  const numericId = Number(salesId);
  const canAct = Number.isFinite(numericId) && numericId > 0;
  const numberText = salesId ? `销售单号：${escapeHtml(salesId)}` : "销售单已创建";
  $("saleResultCard").innerHTML = `
    <strong>开单成功</strong>
    <p>${numberText}</p>
    <div class="sale-result-actions">
      ${canAct ? `<button type="button" onclick="printSales(${numericId})">打印</button>` : ""}
      ${canAct ? `<button type="button" class="danger" onclick="deleteSales(${numericId})">删除</button>` : ""}
      <button type="button" class="primary" onclick="setView('sales')">去销售单</button>
    </div>`;
}

async function loadProductCategories() {
  const bar = $("productCategoryBar");
  if (!bar) return;
  try {
    const list = normalizeList(await api("/api/product/categories"));
  state.productCategories = list;
  if (!state.productUnits.length || !state.productStatuses.length) {
    loadProductOptions().catch(() => {});
  }
    renderProductCategories();
  } catch (err) {
    bar.innerHTML = "";
  }
}

function renderProductCategories() {
  const bar = $("productCategoryBar");
  if (!bar) return;
  const list = state.productCategories.length ? state.productCategories : [{ id: "", name: "全部产品", total: state.productTotal || "" }];
  const tree = productCategoryTree(list);
  const activeGroupKey = state.productCategoryGroupKey || productCategoryGroupKeyForId(state.productCategoryId, tree);
  const activeGroup = tree.groups.find((group) => group.key === activeGroupKey);
  const majorHtml = [
    `<button class="${!activeGroupKey && !state.productCategoryId ? "active" : ""}" onclick="selectProductCategoryGroup('', '')">全部产品${tree.total ? ` ${escapeHtml(tree.total)}` : ""}</button>`,
    ...tree.groups.map((group) => {
      const active = group.key === activeGroupKey && !state.productCategoryId;
      return `<button class="${active ? "active" : ""}" onclick="selectProductCategoryGroup('${escapeAttr(group.key)}', '')">${escapeHtml(group.name)}${group.total ? ` ${escapeHtml(group.total)}` : ""}</button>`;
    })
  ].join("");
  const childHtml = activeGroup ? [
    `<button class="${!state.productCategoryId ? "active" : ""}" onclick="selectProductCategoryGroup('${escapeAttr(activeGroup.key)}', '')">全部${escapeHtml(activeGroup.name)}${activeGroup.total ? ` ${escapeHtml(activeGroup.total)}` : ""}</button>`,
    ...activeGroup.children.map((category) => {
      const id = category.id ?? "";
      const active = String(id) === String(state.productCategoryId || "");
      const total = category.total !== undefined && category.total !== "" ? ` ${category.total}` : "";
      return `<button class="${active ? "active" : ""}" onclick="selectProductCategoryGroup('${escapeAttr(activeGroup.key)}', '${escapeAttr(id)}')">${escapeHtml(category.name || "分类")}${escapeHtml(total)}</button>`;
    })
  ].join("") : "";
  bar.innerHTML = `<div class="product-category-level product-category-major">${majorHtml}</div>${activeGroup ? `<div class="product-category-level product-category-child">${childHtml}</div>` : ""}`;
}

function selectProductCategory(id) {
  state.productCategoryId = id || "";
  state.productCategoryGroupKey = productCategoryGroupKeyForId(id) || "";
  state.productPage = 1;
  renderProductCategories();
  loadProducts(1);
}
window.selectProductCategory = selectProductCategory;

function selectProductCategoryGroup(groupKey = "", categoryId = "") {
  state.productCategoryGroupKey = groupKey || "";
  state.productCategoryId = categoryId || "";
  state.productPage = 1;
  renderProductCategories();
  loadProducts(1);
}
window.selectProductCategoryGroup = selectProductCategoryGroup;

function productCategoryGroupKeyForId(id, tree = null) {
  if (!id) return "";
  const data = tree || productCategoryTree(state.productCategories);
  for (const group of data.groups || []) {
    if ((group.children || []).some((category) => String(category.id ?? "") === String(id))) return group.key;
  }
  return "";
}

function productCategoryMajor(category = {}) {
  const name = String(category.name || "");
  if (/快递|纸箱|物流|纸盒/.test(name)) return { key: "shipping", name: "快递纸箱", order: 30 };
  if (/泡袋|茶袋|袋|大红袍|肉桂|水仙|红茶|品种茶|公版|空白|宽版/.test(name)) return { key: "bag", name: "泡袋", order: 20 };
  if (/礼盒|小盒|盒/.test(name)) return { key: "gift_box", name: "礼盒", order: 10 };
  return { key: "other", name: "其他", order: 90 };
}

function productCategoryTree(list = []) {
  const categories = (list || []).filter((category) => String(category.id ?? "") !== "");
  const all = (list || []).find((category) => String(category.id ?? "") === "") || { total: state.productTotal || "" };
  const parents = categories.filter((category) => !Number(category.pid || category.parent_id || 0));
  const hasRealChildren = categories.some((category) => Number(category.pid || category.parent_id || 0));
  const groups = new Map();
  const addGroupCategory = (groupInfo, category) => {
    const current = groups.get(groupInfo.key) || { ...groupInfo, total: 0, children: [] };
    current.children.push(category);
    current.total += Number(category.total || 0);
    groups.set(groupInfo.key, current);
  };
  if (hasRealChildren) {
    const byId = new Map(categories.map((category) => [String(category.id ?? ""), category]));
    categories.forEach((category) => {
      const pid = String(category.pid || category.parent_id || "");
      if (!pid || pid === "0") return;
      const parent = byId.get(pid) || {};
      addGroupCategory({ key: `cat_${pid}`, name: parent.name || "其他", order: Number(parent.sort_order || parent.id || 99) }, category);
    });
    parents.filter((parent) => !categories.some((category) => String(category.pid || category.parent_id || "") === String(parent.id ?? ""))).forEach((parent) => {
      const info = productCategoryMajor(parent);
      addGroupCategory(info, parent);
    });
  } else {
    categories.forEach((category) => addGroupCategory(productCategoryMajor(category), category));
  }
  return {
    total: all.total !== undefined && all.total !== "" ? all.total : state.productTotal || "",
    groups: Array.from(groups.values()).sort((a, b) => a.order - b.order || a.name.localeCompare(b.name, "zh-Hans-CN"))
  };
}

async function loadProducts(page) {
  if (page !== undefined) state.productPage = page;
  await nextFrame();
  state.productPageSize = calculateProductPageSize();
  const keyword = ($("productKeyword") && $("productKeyword").value.trim()) || "";
  const target = $("productList");
  if (target) target.innerHTML = skeletonCards(Math.min(state.productPageSize, 8));
  const tree = productCategoryTree(state.productCategories);
  const activeGroup = tree.groups.find((group) => group.key === state.productCategoryGroupKey);
  const categoryIds = !state.productCategoryId && activeGroup ? activeGroup.children.map((category) => category.id).filter(Boolean).join(",") : "";
  const res = await api(`/api/product/list?${query({ keyword, page: state.productPage, page_size: state.productPageSize, category_id: state.productCategoryId, category_ids: categoryIds, group: 1 })}`);
  let list = normalizeList(res);
  if (!list.length && res.data && Array.isArray(res.data)) list = res.data;
  state.lastProducts = list;
  state.productTotal = (res.data && res.data.total) || list.length;
  setBadge("products", state.productTotal);
  renderProducts(list);
  renderProductPager();
  if (!state.productCategories.length) loadProductCategories();
  else if (!state.productUnits.length) loadProductOptions().catch(() => {});
}
window.loadProducts = loadProducts;

function calculateProductPageSize() {
  const target = $("productList");
  const columns = gridColumnCount(target);
  if (!target) return Math.max(8, columns * 2);
  const rect = target.getBoundingClientRect();
  const cardHeight = 360;
  const available = Math.max(cardHeight, window.innerHeight - rect.top - 24);
  const rows = Math.max(1, Math.floor((available + 14) / (cardHeight + 14)));
  return Math.max(columns, Math.min(80, rows * columns));
}

function renderProductPager() {
  const pager = $("productPager");
  if (!pager) return;
  const totalPages = Math.max(1, Math.ceil(state.productTotal / state.productPageSize));
  if (totalPages <= 1) { pager.innerHTML = ""; return; }
  pager.innerHTML =
    '<button ' + (state.productPage <= 1 ? "disabled" : "") + ' onclick="loadProducts(' + (state.productPage - 1) + ')">上一页</button>' +
    '<span class="page-info">' + state.productPage + ' / ' + totalPages + ' · 每页 ' + state.productPageSize + '</span>' +
    '<button ' + (state.productPage >= totalPages ? "disabled" : "") + ' onclick="loadProducts(' + (state.productPage + 1) + ')">下一页</button>';
}

function productImage(product) {
  const images = product.spu_main_image_url || product.main_images || product.images || product.image || "";
  if (Array.isArray(images)) return images[0] || "";
  const text = String(images || "").trim();
  if (!text) return "";
  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) return parsed[0] || "";
    if (typeof parsed === "string") return parsed;
  } catch {}
  return text.split(",")[0];
}

function productVariants(product) {
  const rows = Array.isArray(product.product_group_data) && product.product_group_data.length
    ? product.product_group_data
    : [product];
  return rows.filter(Boolean);
}

function productPriceText(product) {
  const min = Number(product.min_price ?? product.price ?? 0);
  const max = Number(product.max_price ?? product.price ?? min);
  if (max && max !== min) return `¥${money(min)}-${money(max)}`;
  return `¥${money(min || product.price || 0)}`;
}

function productColorNames(product) {
  const colors = [];
  const add = (value) => {
    const clean = String(value || "").trim();
    if (clean && !colors.includes(clean)) colors.push(clean);
  };
  if (Array.isArray(product.color_names)) product.color_names.forEach(add);
  if (Array.isArray(product.available_colors)) product.available_colors.forEach(add);
  productVariants(product).forEach((row) => add(row.color || row.spec));
  return colors;
}

function productColorCount(product) {
  const explicit = Number(product.color_count);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;
  return Math.max(1, productColorNames(product).length);
}

function productColorText(product) {
  const text = String(product.color_text || "").trim();
  if (text) return text;
  const colors = productColorNames(product);
  return colors.length ? colors.join(" / ") : "默认颜色";
}

function productColorSummaryHtml(product) {
  return `<div class="muted product-color-summary">${escapeHtml(productColorText(product))}</div>`;
}

function productCasePackText(product) {
  const piece = String(product.piece_text || "").trim();
  if (piece) return `件规：${piece.replace(/^件规[:：]\s*/, "").replace(/个/g, "套")}`;
  const qty = String(product.case_pack_qty || "").trim();
  if (qty) return `件规：1件${qty}套`;
  return "件规：未设置";
}

function productVariantHtml(product) {
  const rows = productVariants(product).slice(0, 6);
  return rows.map((row) => {
    const name = row.spec || row.color || "默认";
    const stock = row.inventory ?? 0;
    const code = row.coding ? ` · ${row.coding}` : "";
    return `<div class="product-spec-line"><span>${escapeHtml(name)}</span><strong>${escapeHtml(stock)}</strong><em>${escapeHtml(code)}</em></div>`;
  }).join("") + (productVariants(product).length > rows.length ? `<div class="product-spec-more">还有 ${productVariants(product).length - rows.length} 个规格</div>` : "");
}

function renderProducts(list) {
  const target = $("productList");
  if (!target) return;
  const tones = ["#e9e3d4", "#efe9da", "#e6dfcf", "#f2ead8"];
  target.innerHTML = list.length ? list.map((product, index) => {
    const id = product.id || product.product_id;
    const img = productImage(product);
    const shelves = isMallShelved(product);
    const statusOk = Number(product.status || 0) === 0;
    const colors = productColorCount(product);
    const packText = productCasePackText(product);
    const purchaseText = product.purchase_policy === "one_case" || Number(product.is_one_case_purchase || 0) ? "1件起订" : "按订单量";
    return `
      <article class="product-card" style="--tone:${tones[index % tones.length]}">
        <div class="product-image ${img ? "has-img" : ""}">${img ? `<img src="${escapeAttr(img)}">` : ""}</div>
        <div class="product-body">
          <div class="product-main">
            <div class="product-title-row">
              <h3>${escapeHtml(product.title || product.name || "商品")}</h3>
              <span class="product-count">${escapeHtml(colors)} 颜色</span>
            </div>
            ${productColorSummaryHtml(product)}
            <div class="product-price-row"><strong>${productPriceText(product)}</strong><span>${escapeHtml(packText)}</span></div>
          </div>
          <div class="product-tags">
            <span class="tag ${statusOk ? "green" : "green-outline"}">${escapeHtml(product.status_text || "正常")}</span>
            <span class="tag ${shelves ? "green" : "green-outline"}">${shelves ? "商城已上架" : "商城未上架"}</span>
            <span class="tag green-outline">${purchaseText}</span>
          </div>
          <div class="card-actions"><button onclick="editProduct(${Number(id || 0)})">编辑</button><button class="danger" onclick="deleteProduct(${Number(id || 0)})">删除</button><button class="product-shelf-button" onclick="shelvesProduct(${Number(id || 0)}, ${shelves ? 0 : 1})">${shelves ? "商城下架" : "商城上架"}</button></div>
        </div>
      </article>`;
  }).join("") : '<div class="empty">暂无商品结果</div>';
}

function isMallShelved(product) {
  return Number(product.system_goods_is_shelves ?? product.is_shelves ?? product.shelves ?? 0) === 1;
}

function productDataFromOptionsPayload(payload) {
  const data = payload && payload.data ? payload.data : payload;
  if (!data || typeof data !== "object") return {};
  if (data.data && typeof data.data === "object") {
    return {
      ...data.data,
      product_group_data: data.product_group_data || data.data.product_group_data || [],
      media_assets: data.data.media_assets || data.media_assets || []
    };
  }
  return data;
}

function mergeProductCategories(list) {
  const byId = new Map();
  state.productCategories.forEach((item) => byId.set(String(item.id ?? ""), item));
  (list || []).forEach((item) => {
    const key = String(item.id ?? "");
    byId.set(key, { ...(byId.get(key) || {}), ...item });
  });
  const all = byId.get("") || { id: "", name: "全部产品", total: state.productTotal || "" };
  const rest = Array.from(byId.values()).filter((item) => String(item.id ?? "") !== "");
  state.productCategories = [all].concat(rest);
}

async function loadProductOptions(productId = "") {
  const res = await api(`/api/product/options${productId ? `?id=${encodeURIComponent(productId)}` : ""}`);
  const data = res.data || {};
  const mediaAssets = (data.data && data.data.media_assets) || data.media_assets || [];
  if (Array.isArray(mediaAssets)) state.productMediaAssets = mediaAssets;
  if (Array.isArray(data.product_category)) {
    const savedCategories = state.productCategories.slice();
    const all = state.productCategories.find((item) => item.id === "") || { id: "", name: "全部产品", total: state.productTotal || "" };
    state.productCategories = savedCategories;
    mergeProductCategories(data.product_category);
  }
  state.productUnits = Array.isArray(data.unit_list) ? data.unit_list : state.productUnits;
  state.productStatuses = Array.isArray(data.product_status_list) ? data.product_status_list : state.productStatuses;
  renderProductCategories();
  return productDataFromOptionsPayload(data);
}

function unitName(unitId) {
  const item = state.productUnits.find((row) => String(row.id) === String(unitId));
  return item ? item.name : "单位";
}

function unitOptions(selected) {
  const list = state.productUnits.length ? state.productUnits : [{ id: 1, name: "套" }];
  return list.map((unit) => `<option value="${escapeAttr(unit.id)}" ${String(unit.id) === String(selected) ? "selected" : ""}>${escapeHtml(unit.name || "单位")}</option>`).join("");
}

function statusOptions(selected) {
  return state.productStatuses.map((item) => `<option value="${escapeAttr(item.value)}" ${String(item.value) === String(selected) ? "selected" : ""}>${escapeHtml(item.name || "状态")}</option>`).join("");
}

function selectedProductCategories() {
  try {
    const parsed = JSON.parse(($("drawerProductCategoryIds") && $("drawerProductCategoryIds").value) || "[]");
    return Array.isArray(parsed) ? parsed.map(Number).filter(Boolean) : [];
  } catch {
    return [];
  }
}

function setSelectedProductCategories(ids) {
  const list = (ids || []).map(Number).filter(Boolean);
  if ($("drawerProductCategoryIds")) $("drawerProductCategoryIds").value = JSON.stringify(list);
  const box = $("drawerProductCategories");
  if (!box) return;
  box.innerHTML = state.productCategories.filter((item) => item.id !== "").map((cat) => {
    const active = list.includes(Number(cat.id));
    return `<button type="button" class="${active ? "active" : ""}" onclick="toggleProductCategory(${Number(cat.id)})">${escapeHtml(cat.name || "分类")}</button>`;
  }).join("");
}

function toggleProductCategory(id) {
  const list = selectedProductCategories();
  const value = Number(id);
  const next = list.includes(value) ? list.filter((item) => item !== value) : list.concat(value);
  setSelectedProductCategories(next);
}
window.toggleProductCategory = toggleProductCategory;

function parseSimpleDesc(value) {
  const match = String(value || "").match(/规格[:：]?\s*([0-9.]+)\s*([^/]+)\/件/);
  const defaultUnit = state.productUnits.find((item) => item.name === "套") || state.productUnits[0] || { id: 1 };
  if (!match) return { desc_number: "", desc_unit_id: defaultUnit.id || 1 };
  const unit = state.productUnits.find((item) => item.name === match[2]) || defaultUnit;
  return { desc_number: match[1], desc_unit_id: unit.id || 1 };
}

function buildSimpleDescFromDrawer() {
  const number = ($("drawerProductDescNumber") && $("drawerProductDescNumber").value.trim()) || "";
  if (!number) return "";
  return `规格${number}${unitName(($("drawerProductDescUnit") && $("drawerProductDescUnit").value) || 1)}/件`;
}

function productMainImages() {
  try {
    const parsed = JSON.parse(($("drawerProductMainImages") && $("drawerProductMainImages").value) || "[]");
    return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function setProductMainImages(images) {
  const list = (images || []).filter(Boolean);
  if ($("drawerProductMainImages")) $("drawerProductMainImages").value = JSON.stringify(list);
  renderProductMainImageRow(list);
}

function removeProductMainImage() {
  setProductMainImages([]);
}
window.removeProductMainImage = removeProductMainImage;

function productMainImageRowHtml(images = []) {
  const first = (images || []).filter(Boolean)[0] || "";
  if (!first) {
    return `<button type="button" id="drawerProductImagePreview" class="product-image-preview empty-upload" onclick="openProductAssetPicker('main')"><span>+</span><strong>上传/选择</strong></button>`;
  }
  return `
    <button type="button" id="drawerProductImagePreview" class="product-image-preview" onclick="openProductAssetPicker('main')">
      <img src="${escapeAttr(first)}" alt="">
      <span class="product-image-remove" onclick="event.stopPropagation(); removeProductMainImage();">×</span>
    </button>
    <button type="button" class="product-detail-item product-upload-tile product-main-upload" onclick="openProductAssetPicker('main')"><span>+</span><strong>上传/选择</strong></button>`;
}

function renderProductMainImageRow(images = productMainImages()) {
  const row = $("drawerProductMainImageRow");
  if (row) row.innerHTML = productMainImageRowHtml(images);
}

function productDetailImages() {
  try {
    const parsed = JSON.parse(($("drawerProductDetailImages") && $("drawerProductDetailImages").value) || "[]");
    return Array.isArray(parsed) ? parsed.filter(Boolean) : [];
  } catch {
    return [];
  }
}

function setProductDetailImages(images) {
  const list = (images || []).filter(Boolean);
  if ($("drawerProductDetailImages")) $("drawerProductDetailImages").value = JSON.stringify(list);
  const grid = $("drawerProductDetailGrid");
  if (grid) {
    const imagesHtml = list.map((url, index) => `<div class="product-detail-item"><img src="${escapeAttr(url)}" alt=""><button type="button" class="product-detail-remove" onclick="removeProductDetailImage(${index})">×</button></div>`).join("");
    grid.innerHTML = imagesHtml + '<button type="button" class="product-detail-item product-upload-tile" onclick="openProductAssetPicker(\'detail\')"><span>+</span><strong>上传/选择</strong></button>';
  }
}

function removeProductDetailImage(index) {
  const list = productDetailImages();
  list.splice(index, 1);
  setProductDetailImages(list);
}
window.removeProductDetailImage = removeProductDetailImage;

function removeProductSpecImage(index) {
  const cards = Array.from(document.querySelectorAll(".product-spec-card"));
  const card = cards[Number(index || 0)];
  if (!card) return;
  const input = card.querySelector(".drawerSpecImages");
  if (input) input.value = "";
  const row = card.querySelector(".product-spec-image-row");
  if (row) row.innerHTML = productSpecImageButtonsHtml("", Number(index || 0));
}
window.removeProductSpecImage = removeProductSpecImage;

function productRowsForForm(product = {}) {
  const rows = Array.isArray(product.product_group_data) && product.product_group_data.length ? product.product_group_data : [product];
  return rows.map((row) => {
    const base = Array.isArray(row.base) && row.base.length ? row.base[0] : {};
    const specImage = row.spec_image_url || row.sku_image_url || base.images || "";
    return {
      local_key: localKey(),
      id: row.id || "",
      base_id: base.id || "",
      spec: row.spec || "",
      coding: row.coding || base.coding || "",
    barcode: base.barcode || "",
    unit_id: base.unit_id || row.unit_id || (state.productUnits[0] && state.productUnits[0].id) || 1,
    price: base.price || row.price || "",
    cost_price: base.cost_price || row.cost_price || "",
    is_stock_item: Number((row.is_stock_item ?? base.is_stock_item ?? 1)),
    images: specImage,
    image_url: specImage
  };
  });
}

function productMediaAssetType(asset) {
  return asset.media_type_text || {
    main_image: "主图",
    detail_image: "详情页",
    color_image: "颜色图",
    pending: "待绑定",
    image: "旧图片"
  }[String(asset.media_type || "")] || "图片";
}

function productAssetBindingText(asset = {}) {
  const type = String(asset.media_type || "");
  if (type === "pending") return "待绑定";
  const name = asset.binding_text || asset.product_name || asset.spu_title || "";
  if (name) return name;
  if (asset.spu_id) return `产品#${asset.spu_id}`;
  return "待绑定";
}

function productAssetTitleText(asset = {}) {
  return productAssetBindingText(asset);
}

function productAssetSourceText(asset = {}) {
  return asset.source_text || {
    migration: "迁移导入",
    upload: "上传",
    native_api: "系统保存",
    webui: "WebUI上传",
    manual: "手工维护",
    shopxo: "商城迁移",
    erp: "ERP迁移"
  }[String(asset.source || "")] || asset.source || "-";
}

function productAssetGroupText(asset = {}) {
  return asset.asset_group_text || (asset.media_type === "pending" ? "待绑定图片" : productAssetBindingText(asset));
}

function productAssetGroupKey(asset = {}) {
  return asset.asset_group_key || productAssetGroupText(asset);
}

function productMediaAssetsHtml(assets = []) {
  const list = Array.isArray(assets) ? assets.slice(0, 36) : [];
  if (!list.length) return '<div class="product-media-empty">暂无图片资产</div>';
  return list.map((asset, index) => {
    const url = asset.url || "";
    const type = String(asset.media_type || "pending");
    return `<div class="product-media-asset ${type === "pending" ? "pending" : ""}">
      ${lazyImageHtml(url, 120)}
      <div>
        <strong>${escapeHtml(productMediaAssetType(asset))}</strong>
        <span>${escapeHtml(productAssetBindingText(asset))}</span>
      </div>
      <div class="product-media-actions">
        <button type="button" onclick="applyProductAsset(${index}, 'main')">设主图</button>
        <button type="button" onclick="applyProductAsset(${index}, 'detail')">加详情</button>
        <button type="button" onclick="applyProductAsset(${index}, 'spec')">设颜色图</button>
      </div>
    </div>`;
  }).join("");
}

function renderProductMediaAssets() {
  const box = $("drawerProductMediaAssets");
  if (box) box.innerHTML = productMediaAssetsHtml(state.productMediaAssets);
}

function drawerProductIdValue() {
  return Number(($("drawerProductId") && $("drawerProductId").value) || 0);
}

function drawerProductTitleValue() {
  return (($("drawerProductTitle") && $("drawerProductTitle").value) || "").trim() || "当前产品";
}

function currentProductAssets() {
  const title = drawerProductTitleValue();
  const productId = drawerProductIdValue();
  const rows = [];
  productMainImages().forEach((url, index) => {
    rows.push({
      id: "",
      spu_id: productId || "",
      media_type: "main_image",
      media_type_text: "主图",
      url,
      product_name: title,
      binding_text: `${title} / 主图`,
      asset_group_text: "本产品图片",
      source: "drawer_main",
      source_text: "当前主图",
      sort_order: index
    });
  });
  productDetailImages().forEach((url, index) => {
    rows.push({
      id: "",
      spu_id: productId || "",
      media_type: "detail_image",
      media_type_text: "详情页",
      url,
      product_name: title,
      binding_text: `${title} / 详情图`,
      asset_group_text: "本产品图片",
      source: "drawer_detail",
      source_text: "当前详情页",
      sort_order: index
    });
  });
  Array.from(document.querySelectorAll(".product-spec-card")).forEach((card, index) => {
    const url = (card.querySelector(".drawerSpecImages") && card.querySelector(".drawerSpecImages").value) || "";
    if (!url) return;
    const color = (card.querySelector(".drawerSpecName") && card.querySelector(".drawerSpecName").value.trim()) || "默认颜色";
    rows.push({
      id: "",
      spu_id: productId || "",
      media_type: "color_image",
      media_type_text: "颜色图",
      url,
      product_name: title,
      binding_text: `${title} / ${color}`,
      asset_group_text: "本产品图片",
      sku_color: color,
      source: "drawer_spec",
      source_text: "当前颜色图",
      sort_order: index
    });
  });
  (state.productMediaAssets || [])
    .filter((asset) => {
      if (!productId) return false;
      const type = String(asset.media_type || "");
      if (type === "pending") return false;
      if (productId && asset.spu_id && Number(asset.spu_id) !== Number(productId)) return false;
      return ["main_image", "detail_image", "color_image", "image"].includes(type) || asset.spu_id;
    })
    .forEach((asset) => rows.push(asset));
  const seen = new Set();
  return rows.filter((asset) => {
    const key = asset.url || "";
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function assetListForPicker() {
  const tab = state.productAssetPickerTab || "pending";
  let list = [];
  if (tab === "product_assets") list = currentProductAssets();
  else if (tab === "all") list = state.productMediaAssets || [];
  else list = (state.productMediaAssets || []).filter((asset) => String(asset.media_type || "") === "pending" || !asset.spu_id);
  const keyword = String(state.productAssetPickerKeyword || "").trim().toLowerCase();
  if (!keyword) return list;
  return list.filter((asset) => productAssetKeywordText(asset).includes(keyword));
}

function applyProductAsset(index, target, specIndex = 0) {
  const source = target === "asset-list" ? state.productAssets : assetListForPicker();
  const asset = source[Number(index || 0)];
  const url = asset && asset.url;
  if (!url) return;
  if (target === "detail") {
    setProductDetailImages(productDetailImages().concat(url));
    toast("已加入详情页");
    return;
  }
  if (target === "spec") {
    const cards = Array.from(document.querySelectorAll(".product-spec-card"));
    const card = cards[Number(specIndex || 0)] || cards[0];
    if (!card) return;
    const input = card.querySelector(".drawerSpecImages");
    if (input) input.value = url;
    const row = card.querySelector(".product-spec-image-row");
    if (row) row.innerHTML = productSpecImageButtonsHtml(url, Number(specIndex || 0));
    toast("已设为颜色图");
    return;
  }
  setProductMainImages([url]);
  toast("已设为主图");
}
window.applyProductAsset = applyProductAsset;

function openProductAssetPicker(type = "main", index = 0) {
  state.productAssetPickerTarget = { type, index };
  state.productAssetPickerTab = drawerProductIdValue() || currentProductAssets().length ? "product_assets" : "pending";
  state.productAssetPickerKeyword = "";
  let mask = $("productAssetPickerMask");
  if (!mask) {
    mask = document.createElement("div");
    mask.id = "productAssetPickerMask";
    mask.className = "confirm-mask";
    mask.innerHTML = `
      <div class="confirm-box asset-picker-box" role="dialog" aria-modal="true">
        <div class="asset-picker-head">
          <div><h3 class="confirm-title">选择图片资产</h3><p class="confirm-message">可以选已有图片，也可以上传新图片。</p></div>
          <button type="button" id="productAssetPickerClose">关闭</button>
        </div>
        <div class="asset-picker-actions">
          <button type="button" class="primary" id="productAssetPickerUpload">上传新图片</button>
        </div>
        <div class="asset-picker-search">
          <input id="productAssetPickerKeyword" type="search" placeholder="搜索产品 / 分类 / 颜色 / 图片来源">
          <button type="button" id="productAssetPickerClear">清空</button>
        </div>
        <div class="segmented asset-picker-tabs" id="productAssetPickerTabs">
          <button type="button" data-picker-asset-tab="pending">未绑定</button>
          <button type="button" data-picker-asset-tab="product_assets">本产品图片</button>
          <button type="button" data-picker-asset-tab="all">全部图片</button>
        </div>
        <div class="asset-picker-grid" id="productAssetPickerGrid"></div>
      </div>`;
    document.body.appendChild(mask);
  }
  const searchInput = $("productAssetPickerKeyword");
  if (searchInput) searchInput.value = "";
  renderProductAssetPicker();
  loadPickerAssets(state.productAssetPickerTab).catch((err) => toast(err.message, true));
  $("productAssetPickerUpload").onclick = () => chooseProductUpload(type, index);
  $("productAssetPickerClose").onclick = closeProductAssetPicker;
  if ($("productAssetPickerKeyword")) {
    $("productAssetPickerKeyword").oninput = (event) => {
      state.productAssetPickerKeyword = event.target.value || "";
      renderProductAssetPicker();
    };
  }
  if ($("productAssetPickerClear")) {
    $("productAssetPickerClear").onclick = () => {
      state.productAssetPickerKeyword = "";
      const input = $("productAssetPickerKeyword");
      if (input) input.value = "";
      renderProductAssetPicker();
    };
  }
  $("productAssetPickerTabs").onclick = (event) => {
    const button = event.target.closest("[data-picker-asset-tab]");
    if (!button) return;
    state.productAssetPickerTab = button.dataset.pickerAssetTab || "";
    loadPickerAssets(state.productAssetPickerTab).catch((err) => toast(err.message, true));
  };
  mask.onclick = (event) => { if (event.target === mask) closeProductAssetPicker(); };
  requestAnimationFrame(() => mask.classList.add("open"));
}
window.openProductAssetPicker = openProductAssetPicker;

async function loadPickerAssets(tab = "") {
  const productId = drawerProductIdValue();
  const params = { limit: 2000 };
  if (tab === "pending") params.media_type = "pending";
  if (tab === "product_assets" && productId) params.product_id = productId;
  const res = await api(`/api/product/media?${query(params)}`);
  state.productMediaAssets = normalizeList(res);
  renderProductAssetPicker();
}

function closeProductAssetPicker() {
  const mask = $("productAssetPickerMask");
  if (mask) mask.classList.remove("open");
}
window.closeProductAssetPicker = closeProductAssetPicker;

function renderProductAssetPicker() {
  const grid = $("productAssetPickerGrid");
  if (!grid) return;
  document.querySelectorAll("[data-picker-asset-tab]").forEach((button) => {
    button.classList.toggle("active", (button.dataset.pickerAssetTab || "") === (state.productAssetPickerTab || ""));
  });
  const list = assetListForPicker().slice(0, 80);
  grid.innerHTML = list.length ? list.map((asset, index) => `
    <button type="button" class="asset-pick-card" data-pick-product-asset="${index}">
      ${lazyImageHtml(asset.url || "", 180)}
      <strong>${escapeHtml(productAssetTitleText(asset))}</strong>
      <span>${escapeHtml(productAssetGroupText(asset))}</span>
      <em>${escapeHtml(productMediaAssetType(asset))}</em>
    </button>
  `).join("") : `<div class="empty">${state.productAssetPickerKeyword ? "没有匹配图片" : "暂无可选图片，先上传一张。"}</div>`;
}

function productAssetMajorGroup(asset = {}) {
  const type = String(asset.media_type || "");
  const text = [
    asset.asset_group_text,
    asset.category_name,
    asset.product_name,
    asset.spu_title,
    asset.series,
    asset.size_label,
    asset.bag_type,
    asset.tea_type,
    asset.product_type,
    asset.category_product_type
  ].join(" ");
  const lower = text.toLowerCase();
  if (type === "pending" || (!asset.spu_id && !asset.product_name)) return { key: "pending", text: "待绑定", order: 90 };
  if (/快递|纸箱|shipping/.test(text) || lower.includes("shipping")) return { key: "shipping", text: "快递纸箱", order: 30 };
  if (/泡袋|大红袍|肉桂|水仙|红茶|品种茶|公版|空白|宽版/.test(text) || lower.includes("bag")) return { key: "bag", text: "泡袋", order: 20 };
  if (/礼盒|小盒|gift|box/.test(text) || lower.includes("gift_box")) return { key: "gift_box", text: "礼盒", order: 10 };
  return { key: "other", text: "其他产品", order: 80 };
}

function productAssetKeywordText(asset = {}) {
  const major = productAssetMajorGroup(asset);
  return [
    asset.url,
    asset.media_type,
    asset.media_type_text,
    asset.product_name,
    asset.spu_title,
    asset.binding_text,
    asset.asset_group_text,
    asset.category_name,
    asset.series,
    asset.size_label,
    asset.sku_color,
    asset.sku_no,
    asset.bag_type,
    asset.tea_type,
    asset.source_text,
    asset.source,
    major.text
  ].join(" ").toLowerCase();
}

function uniqueAssetPush(list, asset) {
  if (!asset || !asset.url) return;
  const key = [asset.media_type, asset.spu_id || "", asset.sku_color || "", asset.url].join("|");
  if (list.some((item) => [item.media_type, item.spu_id || "", item.sku_color || "", item.url].join("|") === key)) return;
  list.push(asset);
}

function productAssetsByProduct(list = []) {
  const map = new Map();
  (list || []).forEach((asset) => {
    if (!asset || String(asset.media_type || "") === "pending" || !asset.spu_id) return;
    const key = `spu:${asset.spu_id}`;
    const major = productAssetMajorGroup(asset);
    const current = map.get(key) || {
      key,
      spu_id: asset.spu_id,
      title: asset.product_name || asset.spu_title || `产品#${asset.spu_id}`,
      groupText: productAssetGroupText(asset),
      major,
      main: [],
      detail: [],
      color: [],
      assets: [],
      colors: new Set(),
      updatedAt: ""
    };
    if (!current.title || /^产品#/.test(current.title)) current.title = asset.product_name || asset.spu_title || current.title;
    if (!current.groupText || current.groupText === "待绑定图片") current.groupText = productAssetGroupText(asset);
    if (major.order < current.major.order) current.major = major;
    uniqueAssetPush(current.assets, asset);
    if (asset.media_type === "main_image") uniqueAssetPush(current.main, asset);
    else if (asset.media_type === "detail_image") uniqueAssetPush(current.detail, asset);
    else if (asset.media_type === "color_image") {
      uniqueAssetPush(current.color, asset);
      current.colors.add(asset.sku_color || "默认颜色");
    }
    const time = String(asset.updated_at || asset.created_at || "");
    if (time > current.updatedAt) current.updatedAt = time;
    map.set(key, current);
  });
  return Array.from(map.values()).map((group) => {
    group.colorNames = Array.from(group.colors).sort((a, b) => a.localeCompare(b, "zh-Hans-CN"));
    group.imageCount = group.main.length + group.detail.length + group.color.length;
    group.preview = (group.main[0] || group.color[0] || group.detail[0] || {}).url || "";
    return group;
  }).sort((a, b) => {
    if (a.major.order !== b.major.order) return a.major.order - b.major.order;
    return a.title.localeCompare(b.title, "zh-Hans-CN");
  });
}

function productAssetMajorGroups(list = []) {
  const map = new Map();
  (list || []).forEach((asset) => {
    const group = productAssetMajorGroup(asset);
    if (state.productAssetView !== "all" && group.key === "pending") return;
    const current = map.get(group.key) || { ...group, count: 0 };
    current.count += 1;
    map.set(group.key, current);
  });
  return Array.from(map.values()).sort((a, b) => a.order - b.order);
}

function renderProductAssetGroups(list = []) {
  const bar = $("assetGroupBar");
  if (!bar) return;
  if (state.productAssetView === "pending") {
    state.productAssetGroup = "";
    bar.innerHTML = "";
    return;
  }
  const groups = productAssetMajorGroups(list);
  if (state.productAssetGroup && !groups.some((group) => group.key === state.productAssetGroup)) {
    state.productAssetGroup = "";
  }
  bar.innerHTML = [
    `<button type="button" class="${!state.productAssetGroup ? "active" : ""}" data-asset-group="">全部分类</button>`,
    ...groups.map((group) => `<button type="button" class="${group.key === state.productAssetGroup ? "active" : ""}" data-asset-group="${escapeAttr(group.key)}">${escapeHtml(group.text)} ${escapeHtml(group.count)}</button>`)
  ].join("");
}

function assetProductCountsHtml(group) {
  return `<div class="asset-count-row">
    <div><span>主图</span><strong>${group.main.length}</strong></div>
    <div><span>详情</span><strong>${group.detail.length}</strong></div>
    <div><span>颜色</span><strong>${Math.max(group.colorNames.length, group.color.length ? 1 : 0)}</strong></div>
  </div>`;
}

function assetProductThumbsHtml(group) {
  const thumbs = [].concat(group.main, group.detail, group.color).slice(0, 5);
  if (!thumbs.length) return '<div class="asset-mini-strip empty">暂无图片</div>';
  return `<div class="asset-mini-strip">${thumbs.map((asset) => lazyImageHtml(asset.url || "", 120)).join("")}</div>`;
}

function assetProductCardHtml(group, compact = false) {
  const colors = group.colorNames.length ? group.colorNames.join("、") : (group.color.length ? "默认颜色" : "未设置");
  return `<article class="asset-product-card ${compact ? "compact" : ""}">
    <div class="asset-product-top">
      ${lazyImageHtml(group.preview || "", 260, group.title)}
      <div>
        <h3 title="${escapeAttr(group.title)}">${escapeHtml(group.title)}</h3>
        <p>${escapeHtml([group.groupText, group.major.text].filter(Boolean).join(" · "))}</p>
        <span>颜色：${escapeHtml(colors)}</span>
      </div>
    </div>
    ${assetProductCountsHtml(group)}
    ${assetProductThumbsHtml(group)}
    <button type="button" class="asset-open-button" data-open-asset-product-detail="${escapeAttr(group.key)}">查看图片</button>
  </article>`;
}

function calculateProductAssetPageSize(view = state.productAssetView || "products") {
  const target = $("productAssetList");
  if (!target) return view === "all" || view === "pending" ? 80 : 40;
  const rect = target.getBoundingClientRect();
  const width = target.clientWidth || rect.width || window.innerWidth || 1000;
  const isFlat = view === "all" || view === "pending";
  const minWidth = isFlat ? 170 : 300;
  const cardHeight = isFlat ? 240 : 260;
  const gap = 10;
  const columns = Math.max(1, Math.floor((width + gap) / (minWidth + gap)));
  const available = Math.max(cardHeight, window.innerHeight - rect.top - 46);
  const rows = Math.max(1, Math.floor((available + gap) / (cardHeight + gap)));
  const cap = isFlat ? 120 : 80;
  return Math.max(columns, Math.min(cap, rows * columns));
}

function productAssetPageItems(list = []) {
  const totalPages = Math.max(1, Math.ceil(list.length / Math.max(1, state.productAssetPageSize)));
  state.productAssetPage = Math.max(1, Math.min(Number(state.productAssetPage || 1), totalPages));
  const start = (state.productAssetPage - 1) * state.productAssetPageSize;
  return list.slice(start, start + state.productAssetPageSize);
}

function renderProductAssetProductList(list = []) {
  const target = $("productAssetList");
  if (!target) return 0;
  const groups = productAssetsByProduct(list);
  state.productAssetProductGroups = groups;
  const visible = productAssetPageItems(groups);
  target.innerHTML = groups.length
    ? `<div class="asset-product-grid">${visible.map((group) => assetProductCardHtml(group)).join("")}</div><div class="asset-list-summary">共 ${escapeHtml(groups.length)} 个产品 · ${escapeHtml(list.length)} 张图片</div>`
    : '<div class="empty">暂无已绑定商品图片</div>';
  return groups.length;
}

function renderProductAssetCategoryList(list = []) {
  const target = $("productAssetList");
  if (!target) return 0;
  const products = productAssetsByProduct(list);
  state.productAssetProductGroups = products;
  const visibleProducts = productAssetPageItems(products);
  const categories = new Map();
  visibleProducts.forEach((group) => {
    const current = categories.get(group.major.key) || { ...group.major, products: [], imageCount: 0 };
    current.products.push(group);
    current.imageCount += group.imageCount;
    categories.set(group.major.key, current);
  });
  const ordered = Array.from(categories.values()).sort((a, b) => a.order - b.order);
  target.innerHTML = ordered.length ? `<div class="asset-category-list">${ordered.map((category) => `
    <section class="asset-category-section">
      <div class="asset-category-head">
        <div><h2>${escapeHtml(category.text)}</h2><p>${escapeHtml(category.products.length)} 个产品 · ${escapeHtml(category.imageCount)} 张图片</p></div>
      </div>
      <div class="asset-product-grid compact">${category.products.map((group) => assetProductCardHtml(group, true)).join("")}</div>
    </section>
  `).join("")}</div><div class="asset-list-summary">共 ${escapeHtml(products.length)} 个产品 · 按分类分组</div>` : '<div class="empty">暂无分类图片</div>';
  return products.length;
}

function assetFlatCardHtml(asset) {
  return `<article class="asset-card">
    ${asset.id ? `<button type="button" class="asset-delete" data-delete-asset-id="${Number(asset.id)}">×</button>` : ""}
    ${lazyImageHtml(asset.url || "", 260, productAssetTitleText(asset))}
    <div class="asset-card-body">
      <div class="record-main">
        <div><h3 title="${escapeAttr(productAssetTitleText(asset))}">${escapeHtml(productAssetTitleText(asset))}</h3><p>${escapeHtml(productAssetGroupText(asset))}</p></div>
        <span class="tag ${asset.media_type === "pending" ? "gold" : "green-outline"}">${escapeHtml(productMediaAssetType(asset))}</span>
      </div>
      <div class="asset-card-meta">
        <span>${escapeHtml(productAssetSourceText(asset))}</span>
        <span>${escapeHtml(nativeDateText(asset.updated_at || asset.created_at))}</span>
      </div>
    </div>
  </article>`;
}

function renderProductAssetFlatList(list = [], emptyText = "暂无图片资产") {
  const target = $("productAssetList");
  if (!target) return 0;
  const visible = productAssetPageItems(list);
  target.innerHTML = list.length
    ? `<div class="asset-card-grid">${visible.map((asset) => assetFlatCardHtml(asset)).join("")}</div><div class="asset-list-summary">共 ${escapeHtml(list.length)} 张图片</div>`
    : `<div class="empty">${escapeHtml(emptyText)}</div>`;
  return list.length;
}

function renderCurrentProductAssets() {
  const keyword = (($("assetKeyword") && $("assetKeyword").value) || "").trim().toLowerCase();
  const raw = state.productAssets || [];
  const filterKey = [state.productAssetView || "products", state.productAssetGroup || "", keyword].join("|");
  if (filterKey !== state.productAssetLastFilter) {
    state.productAssetPage = 1;
    state.productAssetLastFilter = filterKey;
  }
  renderProductAssetGroups(raw);
  const view = state.productAssetView || "products";
  state.productAssetPageSize = calculateProductAssetPageSize(view);
  let list = raw.filter((asset) => {
    const major = productAssetMajorGroup(asset);
    const groupOk = !state.productAssetGroup || major.key === state.productAssetGroup;
    const keywordOk = !keyword || productAssetKeywordText(asset).includes(keyword);
    return groupOk && keywordOk;
  });
  if (view === "pending") list = list.filter((asset) => String(asset.media_type || "") === "pending" || !asset.spu_id);
  if (view === "products" || view === "categories") list = list.filter((asset) => String(asset.media_type || "") !== "pending" && asset.spu_id);
  let count = 0;
  if (view === "categories") count = renderProductAssetCategoryList(list);
  else if (view === "pending") count = renderProductAssetFlatList(list, "暂无待绑定图片");
  else if (view === "all") count = renderProductAssetFlatList(list, "暂无图片资产");
  else count = renderProductAssetProductList(list);
  state.productAssetTotal = count;
  setBadge("product-assets", count);
  renderProductAssetPager();
}

function renderProductAssetPager() {
  const pager = $("assetPager");
  if (!pager) return;
  const totalPages = Math.max(1, Math.ceil(Number(state.productAssetTotal || 0) / Math.max(1, state.productAssetPageSize)));
  if (totalPages <= 1) { pager.innerHTML = ""; return; }
  pager.innerHTML =
    '<button ' + (state.productAssetPage <= 1 ? "disabled" : "") + ' onclick="loadProductAssetPage(' + (state.productAssetPage - 1) + ')">上一页</button>' +
    '<span class="page-info">' + state.productAssetPage + ' / ' + totalPages + ' · 每页 ' + state.productAssetPageSize + '</span>' +
    '<button ' + (state.productAssetPage >= totalPages ? "disabled" : "") + ' onclick="loadProductAssetPage(' + (state.productAssetPage + 1) + ')">下一页</button>';
}

function loadProductAssetPage(page) {
  state.productAssetPage = Math.max(1, Number(page || 1));
  renderCurrentProductAssets();
}
window.loadProductAssetPage = loadProductAssetPage;

async function loadProductAssets() {
  const target = $("productAssetList");
  if (target) target.innerHTML = skeletonCards(4);
  const res = await api(`/api/product/media?${query({ limit: 6000 })}`);
  state.productAssets = normalizeList(res);
  renderCurrentProductAssets();
}
window.loadProductAssets = loadProductAssets;

function assetDetailTileHtml(asset, options = {}) {
  const label = options.label || "";
  return `<div class="asset-detail-tile">
    ${asset.id ? `<button type="button" class="asset-delete" data-delete-asset-id="${Number(asset.id)}">×</button>` : ""}
    ${lazyImageHtml(asset.url || "", 620, asset.sku_color || productMediaAssetType(asset))}
    ${label ? `<span>${escapeHtml(label)}</span>` : ""}
  </div>`;
}

function assetDetailSectionHtml(title, list = [], emptyText = "暂无图片") {
  return `<section class="asset-detail-section">
    <div class="asset-detail-section-head"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(list.length)} 张</span></div>
    ${list.length ? `<div class="asset-detail-grid">${list.map((asset) => assetDetailTileHtml(asset)).join("")}</div>` : `<div class="product-media-empty">${escapeHtml(emptyText)}</div>`}
  </section>`;
}

function assetColorSectionsHtml(list = []) {
  if (!list.length) return assetDetailSectionHtml("颜色图", [], "暂无颜色图");
  const map = new Map();
  list.forEach((asset) => {
    const color = asset.sku_color || "默认颜色";
    const current = map.get(color) || [];
    current.push(asset);
    map.set(color, current);
  });
  return `<section class="asset-detail-section">
    <div class="asset-detail-section-head"><strong>颜色图</strong><span>${escapeHtml(map.size)} 个颜色</span></div>
    <div class="asset-color-list">${Array.from(map.entries()).map(([color, assets]) => `
      <div class="asset-color-block">
        <h4>${escapeHtml(color)}</h4>
        <div class="asset-detail-grid">${assets.map((asset) => assetDetailTileHtml(asset)).join("")}</div>
      </div>
    `).join("")}</div>
  </section>`;
}

function openProductAssetDetail(key) {
  const group = (state.productAssetProductGroups || []).find((item) => item.key === key);
  if (!group) return;
  state.productAssetDetailKey = key;
  let mask = $("productAssetDetailMask");
  if (!mask) {
    mask = document.createElement("div");
    mask.id = "productAssetDetailMask";
    mask.className = "confirm-mask";
    document.body.appendChild(mask);
  }
  const colors = group.colorNames.length ? group.colorNames.join("、") : "未设置";
  mask.innerHTML = `
    <div class="confirm-box asset-detail-box" role="dialog" aria-modal="true">
      <div class="asset-picker-head">
        <div>
          <h3 class="confirm-title">${escapeHtml(group.title)}</h3>
          <p class="confirm-message">${escapeHtml([group.groupText, group.major.text, `颜色：${colors}`].filter(Boolean).join(" · "))}</p>
        </div>
        <button type="button" id="productAssetDetailClose">关闭</button>
      </div>
      ${assetProductCountsHtml(group)}
      <div class="asset-detail-sections">
        ${assetDetailSectionHtml("主图", group.main, "暂无主图")}
        ${assetDetailSectionHtml("详情页", group.detail, "暂无详情页图片")}
        ${assetColorSectionsHtml(group.color)}
      </div>
    </div>`;
  $("productAssetDetailClose").onclick = closeProductAssetDetail;
  mask.onclick = (event) => { if (event.target === mask) closeProductAssetDetail(); };
  requestAnimationFrame(() => mask.classList.add("open"));
}
window.openProductAssetDetail = openProductAssetDetail;

function closeProductAssetDetail() {
  const mask = $("productAssetDetailMask");
  if (mask) mask.classList.remove("open");
}
window.closeProductAssetDetail = closeProductAssetDetail;

async function deleteProductAsset(id) {
  if (!id) return;
  const ok = await confirmDialog({ title: "删除图片资产", message: "确认删除这张图片记录？不会删除 OSS 原图，只从资产表停用。", confirmText: "删除" });
  if (!ok) return;
  await api(`/api/product/media/${id}`, { method: "DELETE" });
  toast("图片资产已删除");
  closeProductAssetDetail();
  await loadProductAssets();
}
window.deleteProductAsset = deleteProductAsset;

function setAssetView(view) {
  state.productAssetView = view || "products";
  state.productAssetGroup = "";
  document.querySelectorAll("[data-asset-view]").forEach((button) => {
    button.classList.toggle("active", (button.dataset.assetView || "") === state.productAssetView);
  });
  if ((state.productAssets || []).length) renderCurrentProductAssets();
  else loadProductAssets().catch((err) => toast(err.message, true));
}
window.setAssetView = setAssetView;

function setAssetTab(tab) {
  setAssetView(tab || "products");
}
window.setAssetTab = setAssetTab;

function setAssetGroup(group) {
  state.productAssetGroup = group || "";
  if ((state.productAssets || []).length) renderCurrentProductAssets();
  else loadProductAssets().catch((err) => toast(err.message, true));
}
window.setAssetGroup = setAssetGroup;

function productForm(product = {}) {
  state.productMediaAssets = Array.isArray(product.media_assets) ? product.media_assets : state.productMediaAssets;
  const mainImages = Array.isArray(product.main_images_list) ? product.main_images_list : (productImage(product) ? [productImage(product)] : []);
  const desc = parseSimpleDesc(product.simple_desc || "");
  const detailImages = htmlToImages(product.content || "");
  const categoryIds = Array.isArray(product.product_category_ids) ? product.product_category_ids.map(Number).filter(Boolean) : [];
  const rows = productRowsForForm(product);
  const oneCaseChecked = (product.purchase_policy || (Number(product.is_one_case_purchase || 0) ? "one_case" : "order_qty")) === "one_case" ? "checked" : "";
  return `
    <input id="drawerProductId" type="hidden" value="${escapeAttr(product.id || product.product_id || "")}">
    <input id="drawerProductMainImages" type="hidden" value="${escapeAttr(JSON.stringify(mainImages))}">
    <input id="drawerProductDetailImages" type="hidden" value="${escapeAttr(JSON.stringify(detailImages))}">
    <input id="drawerProductCategoryIds" type="hidden" value="${escapeAttr(JSON.stringify(categoryIds))}">
    <label>商品名称</label><input id="drawerProductTitle" value="${escapeAttr(product.title || product.name || "")}">
    <div class="product-image-editor">
      <label>主图</label>
      <div class="product-main-image-row" id="drawerProductMainImageRow">${productMainImageRowHtml(mainImages)}</div>
    </div>
    <label>分类（可多选）</label><div class="product-category-editor" id="drawerProductCategories"></div>
    <label>ERP 状态</label><select id="drawerProductStatus">${statusOptions(product.status ?? 0)}</select>
    <div class="two-col"><div><label>规格数量</label><input id="drawerProductDescNumber" type="number" step="1" value="${escapeAttr(desc.desc_number)}"></div><div><label>规格单位</label><select id="drawerProductDescUnit">${unitOptions(desc.desc_unit_id)}</select></div></div>
    <label class="product-stock-toggle"><input id="drawerProductOneCase" type="checkbox" ${oneCaseChecked}> 1件起订</label>
    <div class="product-section-row"><label>详情图片</label></div>
    <div class="product-detail-grid" id="drawerProductDetailGrid"></div>
    <label>规格 / 颜色</label>
    <div id="drawerProductSpecs">${productSpecsHtml(rows)}</div>
    <button type="button" onclick="addProductSpec()" class="block-action">添加规格</button>
  `;
}

function productSpecsFromDom() {
  return Array.from(document.querySelectorAll(".product-spec-card")).map((card) => ({
    id: card.querySelector(".drawerSpecId").value || "",
    base_id: card.querySelector(".drawerSpecBaseId").value || "",
    images: card.querySelector(".drawerSpecImages").value || "",
    spec: card.querySelector(".drawerSpecName").value.trim(),
    unit_id: card.querySelector(".drawerSpecUnit").value || 1,
    coding: card.querySelector(".drawerSpecCoding").value.trim(),
    barcode: card.querySelector(".drawerSpecBarcode").value.trim(),
    price: card.querySelector(".drawerSpecPrice").value || 0,
    cost_price: card.querySelector(".drawerSpecCostPrice").value || 0,
    is_stock_item: card.querySelector(".drawerSpecStockItem")?.checked ? 1 : 0
  }));
}

function productSpecsHtml(rows) {
  const list = rows && rows.length ? rows : [{ local_key: localKey(), unit_id: (state.productUnits[0] && state.productUnits[0].id) || 1 }];
  return list.map((spec, index) => productSpecHtml(spec, index, list.length)).join("");
}

function productSpecImageButtonsHtml(img = "", index = 0) {
  if (!img) {
    return `<button type="button" class="product-spec-upload product-upload-tile" onclick="openProductAssetPicker('spec', ${index})"><span>+</span><strong>上传/选择</strong></button>`;
  }
  return `
    <button type="button" class="product-spec-image" onclick="openProductAssetPicker('spec', ${index})">
      <img src="${escapeAttr(img)}" alt="">
      <span class="product-image-remove" onclick="event.stopPropagation(); removeProductSpecImage(${index});">×</span>
    </button>
    <button type="button" class="product-spec-upload product-upload-tile" onclick="openProductAssetPicker('spec', ${index})"><span>+</span><strong>上传/选择</strong></button>`;
}

function productSpecHtml(spec = {}, index = 0, total = 1) {
  const img = spec.image_url || spec.images || "";
  const stockChecked = Number(spec.is_stock_item ?? 1) !== 0 ? "checked" : "";
  return `
    <div class="product-spec-card" data-index="${index}">
      <input class="drawerSpecId" type="hidden" value="${escapeAttr(spec.id || "")}">
      <input class="drawerSpecBaseId" type="hidden" value="${escapeAttr(spec.base_id || "")}">
      <input class="drawerSpecImages" type="hidden" value="${escapeAttr(img || "")}">
      <div class="product-spec-head"><span>规格 ${index + 1}</span>${total > 1 ? `<button type="button" onclick="removeProductSpec(${index})">删除</button>` : ""}</div>
      <div class="product-spec-image-row">${productSpecImageButtonsHtml(img, index)}</div>
      <div class="two-col"><div><label>颜色/规格</label><input class="drawerSpecName" value="${escapeAttr(spec.spec || "")}"></div><div><label>单位</label><select class="drawerSpecUnit">${unitOptions(spec.unit_id || 1)}</select></div></div>
      <div class="two-col"><div><label>商品编码</label><input class="drawerSpecCoding" value="${escapeAttr(spec.coding || "")}"></div><div><label>条码</label><input class="drawerSpecBarcode" value="${escapeAttr(spec.barcode || "")}"></div></div>
      <div class="two-col"><div><label>售价</label><input class="drawerSpecPrice" type="number" step="0.01" value="${escapeAttr(spec.price || "")}"></div><div><label>成本价</label><input class="drawerSpecCostPrice" type="number" step="0.01" value="${escapeAttr(spec.cost_price || "")}"></div></div>
      <label class="product-stock-toggle"><input class="drawerSpecStockItem" type="checkbox" ${stockChecked}> 管理库存</label>
    </div>`;
}

function renderProductSpecs(rows) {
  const box = $("drawerProductSpecs");
  if (box) box.innerHTML = productSpecsHtml(rows);
}

function addProductSpec() {
  renderProductSpecs(productSpecsFromDom().concat([{ local_key: localKey(), unit_id: (state.productUnits[0] && state.productUnits[0].id) || 1 }]));
}
window.addProductSpec = addProductSpec;

function removeProductSpec(index) {
  const list = productSpecsFromDom();
  if (list.length <= 1) return;
  list.splice(index, 1);
  renderProductSpecs(list);
}
window.removeProductSpec = removeProductSpec;

function chooseProductUpload(type, index = null) {
  state.productUploadTarget = { type, index };
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.className = "sr-only";
  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if (file) uploadProductImage(file).catch((err) => toast(err.message, true));
    input.remove();
  }, { once: true });
  document.body.appendChild(input);
  input.click();
}
window.chooseProductUpload = chooseProductUpload;

async function editProduct(id) {
  const product = state.lastProducts.find((item) => Number(item.id || item.product_id) === Number(id));
  if (!product) return toast("没有找到商品", true);
  try {
    const full = await loadProductOptions(id);
    openDrawer("product", { ...product, ...full });
    setSelectedProductCategories(Array.isArray(full.product_category_ids) ? full.product_category_ids : product.product_category_ids || []);
    setProductDetailImages(htmlToImages(full.content || product.content || ""));
  } catch (err) {
    toast("商品详情加载失败: " + err.message, true);
    openDrawer("product", product);
    setSelectedProductCategories(product.product_category_ids || []);
    setProductDetailImages(htmlToImages(product.content || ""));
  }
}

async function saveProductFromDrawer() {
  const title = $("drawerProductTitle").value.trim();
  if (!title) throw new Error("请输入商品名称");
  const categoryIds = selectedProductCategories();
  if (!categoryIds.length) throw new Error("请选择分类");
  const specs = productSpecsFromDom();
  if (!specs.length) throw new Error("请添加规格");
  await api("/api/product/save", {
    method: "POST",
    body: productSavePayload({
      id: $("drawerProductId").value || undefined,
      title,
      categoryIds,
      specs
    })
  });
  toast("商品已保存");
}

function productSavePayload({ id, title, categoryIds, specs }) {
  const mainImages = productMainImages();
  const base = {};
  specs.forEach((spec, index) => {
    const productKey = spec.id ? String(spec.id) : `new_${index}`;
    const unitKey = spec.base_id ? String(spec.base_id) : "new_0";
    base[productKey] = {
      images: spec.images || mainImages[0] || "",
      spec: spec.spec || "",
      coding: spec.coding || "",
      is_stock_item: Number(spec.is_stock_item ?? 1) ? 1 : 0,
      note: "",
      default_warehouse_position: "",
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
    id,
    title,
    product_category_id: categoryIds,
    status: Number($("drawerProductStatus").value || 0),
    purchase_policy: $("drawerProductOneCase")?.checked ? "one_case" : "order_qty",
    simple_desc: buildSimpleDescFromDrawer(),
    content: detailImagesToHtml(productDetailImages()),
    main_images: mainImages,
    base
  };
}

async function uploadProductImage(file) {
  if (!file) return;
  const form = new FormData();
  form.append("image", file, file.name || `product_${Date.now()}.jpg`);
  const res = await api("/api/product/upload", { method: "POST", body: form });
  const data = res.data || {};
  const url = data.url || data.full_url || data.images || data.path || (typeof data === "string" ? data : "");
  const target = state.productUploadTarget || { type: "main" };
  if (target.type === "detail") {
    setProductDetailImages(productDetailImages().concat(url));
  } else if (target.type === "asset") {
    state.productAssets = [{ media_type: "pending", media_type_text: "待绑定", url, storage: "oss" }]
      .concat((state.productAssets || []).filter((asset) => asset.url !== url));
    state.productAssetGroup = "";
    setAssetView("pending");
  } else if (target.type === "spec") {
    const cards = Array.from(document.querySelectorAll(".product-spec-card"));
    const card = cards[Number(target.index || 0)];
    if (card) {
      const input = card.querySelector(".drawerSpecImages");
      if (input) input.value = url;
      const row = card.querySelector(".product-spec-image-row");
      if (row) row.innerHTML = productSpecImageButtonsHtml(url, Number(target.index || 0));
    }
  } else {
    setProductMainImages(url ? [url] : []);
  }
  if (url) {
    state.productMediaAssets = [{ media_type: "pending", media_type_text: "待绑定", url, storage: "oss" }]
      .concat((state.productMediaAssets || []).filter((asset) => asset.url !== url));
    renderProductMediaAssets();
    renderProductAssetPicker();
  }
  state.productUploadTarget = null;
  const input = $("productImageInput");
  if (input) input.value = "";
  toast("商品图片已上传");
}

async function deleteProduct(id) {
  if (!id) return;
  const ok = await confirmDialog({ title: "删除商品", message: "确认删除这个商品？", confirmText: "删除" });
  if (!ok) return;
  await api("/api/product/delete", { method: "POST", body: { ids: String(id) } });
  toast("商品已删除");
  loadProducts(state.productPage);
}

async function shelvesProduct(id, stateValue) {
  await api(`/api/product/${id}/shelves`, { method: "POST", body: { state: stateValue } });
  toast(stateValue ? "已提交上架" : "已提交下架");
  loadProducts(state.productPage);
}

async function refreshLight() {
  try {
    await Promise.all([loadDashboardSummary(), loadSales(), loadWorkflow()]);
  } catch (err) {
    console.warn(err);
  }
}

async function refreshAll() {
  setStatus("刷新中");
  try {
    await Promise.all([loadDashboardSummary(), loadSales(), loadWorkflow(), loadInventory(), loadProducts()]);
    setStatus("系统就绪");
  } catch (err) {
    toast(`刷新失败：${err.message}`, true);
    setStatus("刷新失败");
  }
}

async function handleQuickAction(action) {
  if (action === "refresh") return refreshAll();
  if (action === "print_latest") return printLatestSales();
  if (action === "inventory") {
    const keyword = (($("quickInvKeyword") && $("quickInvKeyword").value.trim()) || (($("inventoryKeyword") && $("inventoryKeyword").value.trim()) || ""));
    if (keyword) {
      $("inventoryKeyword").value = keyword;
      setView("workbench");
      return loadInventory(keyword);
    }
    if ($("quickInvKeyword")) $("quickInvKeyword").focus();
    else if ($("inventoryKeyword")) $("inventoryKeyword").focus();
    return toast("先输入库存关键词");
  }
  if (action === "transfer") return transferInventory();
  if (action === "purchase") return purchaseInventory();
  if (action === "sale") return quickSale();
  if (action === "workflow") return openDrawer("workflow");
}

function scrollParentForNumberInput(input) {
  let node = input && input.parentElement;
  while (node && node !== document.body) {
    const style = window.getComputedStyle(node);
    const canScroll = /(auto|scroll)/.test(style.overflowY || "") && node.scrollHeight > node.clientHeight;
    if (canScroll) return node;
    node = node.parentElement;
  }
  return document.scrollingElement || document.documentElement;
}

function blockNumberInputWheel(event) {
  const input = event.target && event.target.closest ? event.target.closest('input[type="number"]') : null;
  if (!input) return;
  event.preventDefault();
  const scroller = scrollParentForNumberInput(input);
  if (scroller) scroller.scrollTop += event.deltaY;
}

function bindEvents() {
  const bind = (id, event, handler) => {
    const el = $(id);
    if (el) el.addEventListener(event, handler);
  };
  document.addEventListener("wheel", blockNumberInputWheel, { passive: false });
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => handleQuickAction(button.dataset.action).catch((err) => toast(err.message, true)));
  });
  document.querySelectorAll("[data-command-prefix]").forEach((button) => {
    button.addEventListener("click", () => insertCommandPrefix(button.dataset.commandPrefix || ""));
  });
  document.querySelectorAll("[data-command-send]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = $("chatInput");
      if (input) input.value = button.dataset.commandSend || "";
      sendChat();
    });
  });
  document.addEventListener("click", (event) => {
    const saleCustomerButton = event.target.closest("[data-sale-customer-id]");
    if (saleCustomerButton) {
      event.preventDefault();
      selectSaleCustomer(
        Number(saleCustomerButton.dataset.saleCustomerId),
        saleCustomerButton.dataset.saleCustomerName || "客户",
        Number(saleCustomerButton.dataset.saleCustomerMonthly || 0) === 1
      );
      return;
    }
    const saleProductButton = event.target.closest("[data-sale-product-id]");
    if (saleProductButton) {
      event.preventDefault();
      openSaleProductVariants(Number(saleProductButton.dataset.saleProductId)).catch((err) => toast(err.message, true));
      return;
    }
    const removeSaleLineButton = event.target.closest("[data-remove-sale-line]");
    if (removeSaleLineButton) {
      event.preventDefault();
      removeSaleLine(Number(removeSaleLineButton.dataset.removeSaleLine));
      return;
    }
    const salesDetailCard = event.target.closest("[data-open-sales-detail]");
    if (salesDetailCard && !event.target.closest("button, a, input, select, textarea")) {
      event.preventDefault();
      openSalesDetail(Number(salesDetailCard.dataset.openSalesDetail)).catch((err) => toast(err.message, true));
      return;
    }
    const customerBalanceButton = event.target.closest("[data-customer-balance-action]");
    if (customerBalanceButton) {
      event.preventDefault();
      event.stopPropagation();
      openCustomerBalanceDialog(
        Number(customerBalanceButton.dataset.customerId),
        customerBalanceButton.dataset.customerName || "客户",
        customerBalanceButton.dataset.customerBalanceAction || "receipt"
      );
      return;
    }
    const customerBalanceLedgerButton = event.target.closest("[data-open-balance-ledger]");
    if (customerBalanceLedgerButton) {
      event.preventDefault();
      event.stopPropagation();
      openCustomerBalanceLedger(
        Number(customerBalanceLedgerButton.dataset.openBalanceLedger),
        customerBalanceLedgerButton.dataset.customerName || "客户"
      ).catch((err) => toast(err.message, true));
      return;
    }
    const customerMonthlyButton = event.target.closest("[data-customer-monthly-toggle]");
    if (customerMonthlyButton) {
      event.preventDefault();
      event.stopPropagation();
      updateCustomerMonthly(
        Number(customerMonthlyButton.dataset.customerMonthlyToggle),
        Number(customerMonthlyButton.dataset.customerMonthlyValue || 0) === 1
      ).catch((err) => toast(err.message, true));
      return;
    }
    const customerSalesButton = event.target.closest("[data-open-customer-sales]");
    if (customerSalesButton) {
      event.preventDefault();
      openCustomerSales(Number(customerSalesButton.dataset.openCustomerSales), customerSalesButton.dataset.customerName || "客户").catch((err) => toast(err.message, true));
      return;
    }
    const customerSalesFilter = event.target.closest("[data-customer-sales-filter]");
    if (customerSalesFilter) {
      event.preventDefault();
      openCustomerSales(
        Number(customerSalesFilter.dataset.customerSalesFilter),
        customerSalesFilter.dataset.customerName || "客户",
        { period: customerSalesFilter.dataset.period || "" }
      ).catch((err) => toast(err.message, true));
      return;
    }
    const customerSalesMonth = event.target.closest("[data-customer-sales-month]");
    if (customerSalesMonth) {
      event.preventDefault();
      const yearSelect = $("customerSalesYear");
      const monthValue = customerSalesMonth.dataset.monthValue || "";
      const month = yearSelect && monthValue ? `${yearSelect.value}-${monthValue.slice(5, 7)}` : monthValue;
      openCustomerSales(
        Number(customerSalesMonth.dataset.customerSalesMonth),
        customerSalesMonth.dataset.customerName || "客户",
        { month, year: yearSelect ? yearSelect.value : "" }
      ).catch((err) => toast(err.message, true));
      return;
    }
    const pickAssetButton = event.target.closest("[data-pick-product-asset]");
    if (pickAssetButton) {
      event.preventDefault();
      const target = state.productAssetPickerTarget || { type: "main", index: 0 };
      applyProductAsset(Number(pickAssetButton.dataset.pickProductAsset), target.type, target.index);
      closeProductAssetPicker();
      return;
    }
    const openAssetProductButton = event.target.closest("[data-open-asset-product-detail]");
    if (openAssetProductButton) {
      event.preventDefault();
      openProductAssetDetail(openAssetProductButton.dataset.openAssetProductDetail || "");
      return;
    }
    const deleteAssetButton = event.target.closest("[data-delete-asset-id]");
    if (deleteAssetButton) {
      event.preventDefault();
      deleteProductAsset(Number(deleteAssetButton.dataset.deleteAssetId)).catch((err) => toast(err.message, true));
      return;
    }
    const settingsTabButton = event.target.closest("[data-settings-tab]");
    if (settingsTabButton) {
      event.preventDefault();
      setSettingsTab(settingsTabButton.dataset.settingsTab || "print");
      return;
    }
    const addSettingButton = event.target.closest("[data-add-setting-row]");
    if (addSettingButton) {
      event.preventDefault();
      addSettingRow(addSettingButton.dataset.addSettingRow || "");
      return;
    }
    const removeSettingButton = event.target.closest("[data-remove-setting-row]");
    if (removeSettingButton) {
      event.preventDefault();
      const row = removeSettingButton.closest("[data-setting-row]");
      if (row) row.remove();
      return;
    }
    const stockValueButton = event.target.closest("[data-stock-value]");
    if (stockValueButton) {
      event.preventDefault();
      toggleSettingSegment(stockValueButton);
      return;
    }
    const addMiniappModuleButton = event.target.closest("[data-miniapp-add-module]");
    if (addMiniappModuleButton) {
      event.preventDefault();
      addMiniappHomeModule(addMiniappModuleButton.dataset.miniappAddModule || "nav");
      return;
    }
    const moveMiniappModuleButton = event.target.closest("[data-miniapp-module-move]");
    if (moveMiniappModuleButton) {
      event.preventDefault();
      moveMiniappHomeModule(Number(moveMiniappModuleButton.dataset.miniappIndex || state.miniappSelectedIndex || 0), Number(moveMiniappModuleButton.dataset.miniappModuleMove || 0));
      return;
    }
    const removeMiniappModuleButton = event.target.closest("[data-miniapp-module-remove]");
    if (removeMiniappModuleButton) {
      event.preventDefault();
      removeMiniappHomeModule(Number(removeMiniappModuleButton.dataset.miniappIndex || state.miniappSelectedIndex || 0));
      return;
    }
    const selectMiniappModuleButton = event.target.closest("[data-miniapp-select-module]");
    if (selectMiniappModuleButton) {
      event.preventDefault();
      selectMiniappHomeModule(Number(selectMiniappModuleButton.dataset.miniappSelectModule || 0));
      return;
    }
    if (event.target.closest("[data-miniapp-add-item]")) {
      event.preventDefault();
      addMiniappItem();
      return;
    }
    const removeMiniappItemButton = event.target.closest("[data-miniapp-remove-item]");
    if (removeMiniappItemButton) {
      event.preventDefault();
      removeMiniappItem(Number(removeMiniappItemButton.dataset.miniappRemoveItem || 0));
      return;
    }
    if (event.target.closest("#savePrintSettings")) {
      event.preventDefault();
      savePrintSettings().catch((err) => toast(err.message || "打印设置保存失败", true));
      return;
    }
    if (event.target.closest("#previewPrintSettings")) {
      event.preventDefault();
      previewPrintSettings();
      return;
    }
    if (event.target.closest("#refreshNumberSettings")) {
      event.preventDefault();
      loadNumberSettings(true).catch((err) => toast(err.message || "编号设置刷新失败", true));
      return;
    }
    if (event.target.closest("#saveNumberSettings")) {
      event.preventDefault();
      saveNumberSettings().catch((err) => toast(err.message || "编号设置保存失败", true));
      return;
    }
    if (event.target.closest("#saveProductBasicSettings")) {
      event.preventDefault();
      saveSystemSetting("product_basic", collectProductBasicSettings(), loadProductBasicSettings).catch((err) => toast(err.message || "商品基础设置保存失败", true));
      return;
    }
    if (event.target.closest("#saveInventoryRuleSettings")) {
      event.preventDefault();
      saveSystemSetting("inventory_rules", collectInventoryRuleSettings(), loadInventoryRuleSettings).catch((err) => toast(err.message || "库存规则保存失败", true));
      return;
    }
    if (event.target.closest("#savePaymentRuleSettings")) {
      event.preventDefault();
      saveSystemSetting("payment_rules", collectPaymentRuleSettings(), loadPaymentRuleSettings).catch((err) => toast(err.message || "收款结款设置保存失败", true));
      return;
    }
    if (event.target.closest("#saveImageSettings")) {
      event.preventDefault();
      saveSystemSetting("image_rules", collectImageSettings(), loadImageSettings).catch((err) => toast(err.message || "图片设置保存失败", true));
      return;
    }
    if (event.target.closest("#saveMiniappDesignSettings")) {
      event.preventDefault();
      saveSystemSetting("miniapp_design", collectMiniappDesignSettings(), loadMiniappDesignSettings).catch((err) => toast(err.message || "小程序设计保存失败", true));
      return;
    }
    const userRoleButton = event.target.closest("[data-user-role][data-user-id]");
    if (userRoleButton) {
      event.preventDefault();
      updateUserRole(Number(userRoleButton.dataset.userId), userRoleButton.dataset.userRole).catch((err) => toast(err.message, true));
      return;
    }
    const userActiveButton = event.target.closest("[data-user-active][data-user-id]");
    if (userActiveButton) {
      event.preventDefault();
      updateUserActive(Number(userActiveButton.dataset.userId), Number(userActiveButton.dataset.userActive)).catch((err) => toast(err.message, true));
      return;
    }
    const approveButton = event.target.closest("[data-approve-user-id]");
    if (approveButton) {
      event.preventDefault();
      approveWebUser(Number(approveButton.dataset.approveUserId)).catch((err) => toast(err.message, true));
      return;
    }
    const rejectButton = event.target.closest("[data-reject-user-id]");
    if (rejectButton) {
      event.preventDefault();
      rejectWebUser(Number(rejectButton.dataset.rejectUserId)).catch((err) => toast(err.message, true));
    }
  });
  document.addEventListener("change", (event) => {
    const lineInput = event.target.closest("[data-sale-line-index][data-sale-line-field]");
    if (lineInput) {
      updateSaleLine(Number(lineInput.dataset.saleLineIndex), lineInput.dataset.saleLineField, lineInput.value);
    }
    if (event.target && event.target.id === "salePaymentStatus") {
      syncSalePaymentUi();
    }
    const miniappHomeField = event.target.closest("[data-miniapp-home-field]");
    if (miniappHomeField) {
      updateMiniappHomeField(miniappHomeField.dataset.miniappHomeField || "", miniappHomeField.value);
      return;
    }
    const miniappModuleField = event.target.closest("[data-miniapp-module-field]");
    if (miniappModuleField) {
      updateMiniappModuleField(
        miniappModuleField.dataset.miniappModuleField || "",
        miniappModuleField.value,
        miniappModuleField.checked
      );
      return;
    }
    const miniappItemField = event.target.closest("[data-miniapp-item-field]");
    if (miniappItemField) {
      const row = miniappItemField.closest("[data-miniapp-item-index]");
      updateMiniappItemField(
        row ? Number(row.dataset.miniappItemIndex || 0) : 0,
        miniappItemField.dataset.miniappItemField || "",
        miniappItemField.value
      );
    }
  });
  document.querySelectorAll("[data-workflow-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      state.workflowFilter = button.dataset.workflowFilter || "active";
      document.querySelectorAll("[data-workflow-filter]").forEach((node) => {
        node.classList.toggle("active", node === button);
      });
      loadWorkflow(1);
    });
  });
  document.querySelectorAll("[data-inventory-tab]").forEach((button) => {
    button.addEventListener("click", () => setInventoryTab(button.dataset.inventoryTab || "cards"));
  });
  document.querySelectorAll("[data-customer-tab]").forEach((button) => {
    button.addEventListener("click", () => setCustomerTab(button.dataset.customerTab || "customers"));
  });
  document.querySelectorAll("[data-asset-view]").forEach((button) => {
    button.addEventListener("click", () => setAssetView(button.dataset.assetView || "products"));
  });
  const assetGroupBar = $("assetGroupBar");
  if (assetGroupBar) {
    assetGroupBar.addEventListener("click", (event) => {
      const button = event.target.closest("[data-asset-group]");
      if (!button) return;
      setAssetGroup(button.dataset.assetGroup || "");
    });
  }
  $("sendButton").addEventListener("click", () => sendChat());
  $("chatInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") sendChat();
  });
  bind("newChatButton", "click", () => {
    state.sessionId = newSessionId();
    state.session = {};
    state.contextInventory = null;
    state.businessHistory = [];
    localStorage.setItem("sj_web_session_id", state.sessionId);
    $("messages").innerHTML = "";
    persistMessages();
    persistBusinessHistory();
    renderBusinessContext();
    setView("workbench");
  });
  bind("contextButton", "click", () => openDrawer("ai"));
  bind("logoutButton", "click", async () => {
    try {
      await api("/api/web-auth/logout", { method: "POST" });
    } finally {
      window.location.href = "/login";
    }
  });
  bind("accountAdminButton", "click", () => openAccountAdmin().catch((err) => toast(err.message, true)));
  $("closeDrawer").addEventListener("click", closeDrawer);
  $("cancelDrawer").addEventListener("click", closeDrawer);
  $("saveDrawer").addEventListener("click", () => saveDrawer().catch((err) => toast(err.message, true)));
  $("drawerMask").addEventListener("click", closeDrawer);
  $("attachButton").addEventListener("click", () => $("attachmentInput").click());
  $("attachmentInput").addEventListener("change", (event) => {
    const file = event.target.files && event.target.files[0];
    if (file) {
      state.pendingFile = file;
      showPreview(file);
    }
  });
  document.addEventListener("paste", (event) => {
    const items = event.clipboardData && event.clipboardData.items;
    if (!items) return;
    for (const item of items) {
      if (item.type && item.type.startsWith("image/")) {
        const file = item.getAsFile();
        if (file) {
          event.preventDefault();
          state.pendingFile = file;
          showPreview(file);
          toast("已粘贴图片，正在识别");
          sendChat();
        }
        break;
      }
    }
  });
  bind("quickInvBtn", "click", () => {
    $("inventoryKeyword").value = $("quickInvKeyword").value;
    setInventoryTab("cards");
    setView("inventory");
    loadInventory($("quickInvKeyword").value);
  });
  bind("inventorySearchBtn", "click", () => loadInventory(undefined, 1));
  bind("customerSearchBtn", "click", () => loadCustomers(1));
  bind("assetSearchBtn", "click", () => {
    if ((state.productAssets || []).length) renderCurrentProductAssets();
    else loadProductAssets().catch((err) => toast(err.message, true));
  });
  bind("assetUploadButton", "click", () => chooseProductUpload("asset"));
  bind("salesSearchBtn", "click", () => loadSales(1));
  bind("workflowSearchBtn", "click", () => loadWorkflow(1));
  bind("productSearchBtn", "click", () => loadProducts(1));
  const newOrderButton2 = $("newOrderButton2");
  if (newOrderButton2) newOrderButton2.addEventListener("click", () => openDrawer("workflow"));
  $("newProductButton").addEventListener("click", async () => {
    await loadProductOptions();
    openDrawer("product");
    setSelectedProductCategories([]);
    setProductDetailImages([]);
  });
  document.querySelector("#inventory .primary").addEventListener("click", () => prepareInventoryAction("", "", "purchase"));
  document.querySelector("#sales .primary").addEventListener("click", () => setView("sale-create"));
  bind("moveKeyword", "input", () => {
    state.moveProduct = null;
    $("moveSelectedHint").textContent = "先搜索并选择商品，再执行。";
  });
  bind("moveProductSearchBtn", "click", () => searchMoveProducts().catch((err) => toast(err.message, true)));
  bind("transferBtn", "click", () => transferInventory().catch((err) => toast(err.message, true)));
  bind("purchaseBtn", "click", () => purchaseInventory().catch((err) => toast(err.message, true)));
  bind("saleCustomerSearchBtn", "click", () => searchSaleCustomers().catch((err) => toast(err.message, true)));
  bind("saleCustomerCreateBtn", "click", openSaleCustomerCreateDialog);
  bind("saleProductSearchBtn", "click", () => searchSaleProducts().catch((err) => toast(err.message, true)));
  bind("saleAddLineBtn", "click", () => addSaleLine().catch((err) => toast(err.message, true)));
  bind("saleClearBtn", "click", clearSaleForm);
  bind("quickSaleBtn", "click", () => quickSale().catch((err) => toast(err.message, true)));
  bind("saleClearBtnBottom", "click", clearSaleForm);
  bind("quickSaleBtnBottom", "click", () => quickSale().catch((err) => toast(err.message, true)));
  bind("saleCustomer", "keydown", (event) => {
    if (event.key === "Enter") searchSaleCustomers().catch((err) => toast(err.message, true));
  });
  bind("saleProduct", "keydown", (event) => {
    if (event.key === "Enter") searchSaleProducts().catch((err) => toast(err.message, true));
  });
  bind("saleQty", "keydown", (event) => {
    if (event.key === "Enter") addSaleLine().catch((err) => toast(err.message, true));
  });
  bind("productImageInput", "change", (event) => {
    const file = event.target.files && event.target.files[0];
    if (file) uploadProductImage(file).catch((err) => toast(err.message, true));
  });
  window.addEventListener("resize", handleSalesResize);
}

const actions = {
  openSalesDetail,
  deleteSales,
  markWorkflow: _markWorkflow,
  deleteWorkflow: deleteWorkflowOrder,
  editWorkflow: editWorkflowOrder,
  removeWorkflowImage,
  uploadWorkflowImages,
  prepareInventoryAction,
  selectMoveProduct,
  selectSaleCustomer,
  selectSaleProduct: openSaleProductVariants,
  updateSaleLine,
  removeSaleLine,
  editProduct,
  deleteProduct,
  shelvesProduct
};

window.printSales = (id) => doPrintSales(id).catch((err) => toast(err.message, true));
window.setView = setView;
window.openSalesDetail = actions.openSalesDetail;
window.deleteSales = (id) => actions.deleteSales(id).catch((err) => toast(err.message, true));
window.deleteSalesFromHistory = (id, historyCardId = "") => deleteSalesHistoryCard(id, historyCardId).catch((err) => toast(err.message, true));
window.doMarkWorkflow = (id, field) => actions.markWorkflow(id, field);
window.deleteWorkflow = (id) => actions.deleteWorkflow(id).catch((err) => toast(err.message, true));
window.deleteWorkflowFromHistory = (id, historyCardId = "") => deleteWorkflowHistoryCard(id, historyCardId).catch((err) => toast(err.message, true));
window.editWorkflow = (id) => actions.editWorkflow(id);
window.removeWorkflowImage = (index) => actions.removeWorkflowImage(index);
window.uploadWorkflowImages = (files) => actions.uploadWorkflowImages(files);
window.prepareInventoryAction = (title, color, type, productId) => actions.prepareInventoryAction(title, color, type, productId);
window.selectMoveProduct = (id) => actions.selectMoveProduct(id);
window.selectSaleCustomer = (id, name, isMonthly = false) => actions.selectSaleCustomer(id, name, isMonthly);
window.selectSaleProduct = (id) => actions.selectSaleProduct(id).catch((err) => toast(err.message, true));
window.updateSaleLine = (index, field, value) => actions.updateSaleLine(index, field, value);
window.removeSaleLine = (index) => actions.removeSaleLine(index);
window.editProduct = (id) => actions.editProduct(id).catch((err) => toast(err.message, true));
window.deleteProduct = (id) => actions.deleteProduct(id).catch((err) => toast(err.message, true));
window.shelvesProduct = (id, stateValue) => actions.shelvesProduct(id, stateValue).catch((err) => toast(err.message, true));
window.confirmBusinessCard = confirmBusinessCard;
window.cancelBusinessCard = cancelBusinessCard;
window.editBusinessCard = editBusinessCard;

setupDom();
restoreBusinessHistory();
restoreMessages();
bindEvents();
renderSaleLines();
renderBusinessContext();
initWebUser().finally(() => refreshAll());
setInterval(loadDashboardSummary, DASHBOARD_REFRESH_MS);
