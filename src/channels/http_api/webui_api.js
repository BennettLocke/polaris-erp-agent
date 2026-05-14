const $ = (id) => document.getElementById(id);

const LIST_LIMITS = {
  sales: 80,
  workflow: 100,
  inventory: 160,
  products: 120,
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
  inventoryPage: 1,
  inventoryPageSize: 8,
  inventoryTotal: 0,
  contextInventory: null,
  businessHistory: [],
  lastProducts: [],
  productPage: 1,
  productPageSize: 20,
  productTotal: 0,
  productCategoryId: "",
  productCategories: [],
  productUnits: [],
  productStatuses: [
    { value: 0, name: "正常" },
    { value: 1, name: "下架" },
    { value: 2, name: "停售" },
    { value: 3, name: "停产" }
  ],
  productUploadTarget: null,
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

  insertToolbar("sales", "salesKeyword", "搜索客户 / 商品 / 订单号", "salesSearchBtn");
  insertToolbar("orders", "workflowKeyword", "搜索客户 / 商品 / 电话", "workflowSearchBtn");
  insertToolbar("inventory", "inventoryKeyword", "搜索礼盒 / 颜色", "inventorySearchBtn");
  insertToolbar("products", "productKeyword", "搜索商品关键词", "productSearchBtn");

  setBadge("sales", "-");
  setBadge("orders", "-");
  setBadge("inventory", "-");
  setBadge("products", "-");
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
    renderSaleLines();
  }
  if (name === "sales" && !state.lastSalesCards.length) loadSales();
  if (name === "orders" && !state.lastWorkflowCards.length) loadWorkflow();
  if (name === "inventory" && !state.lastInventoryCards.length) loadInventory();
  if (name === "products" && !state.lastProducts.length) loadProducts();
  scheduleActiveListRefresh(name);
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
    if (title) title.textContent = isPurchase ? "进货入库" : "调货";
    if (subtitle) subtitle.textContent = isPurchase ? "确认商品、颜色、数量和入库仓库。" : "确认商品、颜色、数量和仓库方向。";
    if (save) {
      save.style.display = "";
      save.textContent = isPurchase ? "确认进货" : "确认调货";
    }
    body.innerHTML = inventoryActionForm(row);
  } else if (mode === "sales_detail") {
    if (title) title.textContent = "销售单明细";
    if (subtitle) subtitle.textContent = "";
    if (save) save.style.display = "none";
    body.innerHTML = salesDetailHtml(row);
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
    const productHtml = rows.length
      ? '<div class="product-lines' + (hasMore ? ' has-more' : '') + '" id="plines' + id + '">' + rows.map(function(p) {
        const qty = p.quantity ?? p.buy_number ?? p.num ?? "";
        return '<div class="product-row"><span class="product-name">' + escapeHtml([p.title, p.spec].filter(Boolean).join(" ")) + '</span><span class="product-qty">x' + escapeHtml(qty || "-") + '</span><span class="product-price">¥' + money(p.total_price || (Number(p.price || 0) * Number(qty || 0))) + '</span></div>';
      }).join("") + (products.length > rows.length && !compact ? '<button class="expand-btn" onclick="openSalesDetail(' + id + ')">' + products.length + ' 项，查看全部</button>' : "") + '</div>'
      : '<div class="muted">' + escapeHtml(card.product_summary || "暂无商品信息") + '</div>';
    return `
      <div class="business-card sales-card">
        <div class="customer-name"><strong>${escapeHtml(card.customer_name || "客户")}</strong><span class="tag ${String(card.status_text || "").includes("已") ? "green" : "amber"}">${escapeHtml(card.status_text || "销售单")}</span></div>
        <div class="muted">${escapeHtml(card.sales_no || `#${id}`)}</div>
        ${productHtml}
        <div class="kv">
          <div class="kv-row"><span>总数量</span><strong>${escapeHtml(quantityText(count))}</strong></div>
          <div class="kv-row"><span>总价</span><strong>¥${money(card.total_price || card.price)}</strong></div>
          <div class="kv-row"><span>时间</span><strong>${escapeHtml(card.date_text || card.date || card.add_time || "未记录")}</strong></div>
        </div>
        <div class="card-actions">
          <button class="primary" onclick="printSales(${id})">打印</button>
          <button class="danger" onclick="deleteSales(${id})">删除</button>
        </div>
      </div>`;
  }).join("") : '<div class="empty">暂无销售单</div>';
}

function salesDetailHtml(card) {
  const products = normalizeProducts(card.products);
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
  return `
    <div class="sales-detail-head">
      <strong>${escapeHtml(card.customer_name || "客户")}</strong>
      <span class="muted">${escapeHtml(card.sales_no || "")}</span>
    </div>
    <div class="sales-detail-table-wrap">
      <table class="sales-detail-table">
        <thead><tr><th>#</th><th>商品</th><th>数量</th><th>单价</th><th>小计</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="5">暂无商品明细</td></tr>'}</tbody>
      </table>
    </div>`;
}

function openSalesDetail(id) {
  const card = state.lastSalesCards.find((item) => Number(item.id || 0) === Number(id));
  if (!card) return toast("没有找到销售单明细", true);
  openDrawer("sales_detail", card);
}

async function doPrintSales(id) {
  if (!id) return toast("没有取到销售单号，无法打印", true);
  const btn = document.querySelector(`button[onclick="printSales(${id})"]`);
  if (btn) { btn.classList.add("loading"); btn.textContent = "提交中..."; }
  try {
    const res = await api(`/api/sales/${encodeURIComponent(id)}/print-task`, { method: "POST" });
    if (res.code !== 0) throw new Error(res.msg || "打印任务创建失败");
    if (btn) { btn.textContent = "已提交"; btn.classList.remove("loading"); }
    toast("已提交打印");
  } catch (err) {
    if (btn) { btn.textContent = "打印"; btn.classList.remove("loading"); }
    toast(err.message || "打印失败", true);
  }
}

async function deleteSales(id) {
  if (!id) return;
  const ok = await confirmDialog({
    title: "删除销售单",
    message: "确认删除这个销售单？删除后会按 ERP 规则处理库存和记录。",
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
  if (page !== undefined) state.inventoryPage = page;
  else if (keywordOverride !== undefined) state.inventoryPage = 1;
  const keyword = (keywordOverride ?? (($("inventoryKeyword") && $("inventoryKeyword").value) || "")).trim();
  const only = 1;
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
  const res = await api(`/api/inventory/cards?${query({ keyword: cleanKeyword, only_in_stock: 1, limit: LIST_LIMITS.inventory })}`);
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
  const onlyInStock = true;
  const colors = (card.colors || []).filter((color) => !onlyInStock || Number(color.total_stock ?? color.stock ?? 0) > 0 || Number(stockOf(color, "百鑫")) > 0 || Number(stockOf(color, "店里")) > 0);
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
            ${compact ? "" : `<td><div class="inventory-actions"><button class="primary" onclick="prepareInventoryAction('${escapeAttr(title)}', '${escapeAttr(colorName)}', 'transfer', '${escapeAttr(productId)}')">调</button><button onclick="prepareInventoryAction('${escapeAttr(title)}', '${escapeAttr(colorName)}', 'purchase', '${escapeAttr(productId)}')">进</button></div></td>`}
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
  target.innerHTML = list.length ? list.map((card) => inventoryCardHtml(card)).join("") : '<div class="empty">暂无库存数据</div>';
}

function inventoryActionForm(row = {}) {
  const isPurchase = row.type === "purchase";
  return `
    <input id="drawerInvType" type="hidden" value="${escapeAttr(row.type || "transfer")}">
    <input id="drawerInvProductId" type="hidden" value="${escapeAttr(row.product_id || "")}">
    <label>商品</label><input id="drawerInvTitle" value="${escapeAttr(row.title || "")}">
    <div class="two-col">
      <div><label>颜色</label><input id="drawerInvColor" value="${escapeAttr(row.color || "")}"></div>
      <div><label>数量</label><input id="drawerInvQty" type="number" min="1" value="1"></div>
    </div>
    ${isPurchase ? `<label>入库仓库</label><select id="drawerInvWarehouse"><option value="2">百鑫仓库</option><option value="1">自己店里</option></select>` : `
      <div class="two-col">
        <div><label>调出仓库</label><select id="drawerInvOutWarehouse"><option value="2">百鑫仓库</option><option value="1">自己店里</option></select></div>
        <div><label>调入仓库</label><select id="drawerInvEnterWarehouse"><option value="1">自己店里</option><option value="2">百鑫仓库</option></select></div>
      </div>
    `}
  `;
}

function prepareInventoryAction(title, color, type, productId = "") {
  state.inventoryAction = {
    type: type === "purchase" ? "purchase" : "transfer",
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

async function searchSaleCustomers() {
  if (!$("saleCustomer")) throw new Error("开单页面未加载");
  const keyword = $("saleCustomer").value.trim();
  if (!keyword) throw new Error("请输入客户关键词");
  const list = normalizeList(await api(`/api/customer/list?${query({ keyword })}`));
  state.saleCustomerResults = list;
  $("saleCustomerChoices").innerHTML = list.length ? list.slice(0, LIST_LIMITS.choice).map((customer) => {
    const name = customer.name || customer.customer_name || customer.company_name || customer.title || "客户";
    const mobile = customer.mobile || customer.tel || customer.telephone || customer.phone || "";
    const id = Number(customer.id || customer.customer_id || 0);
    return `<button class="choice" data-sale-customer-id="${id}" data-sale-customer-name="${escapeAttr(name)}"><strong>${escapeHtml(name)}</strong><div class="muted">${mobile ? escapeHtml(mobile) + " · " : ""}ID ${escapeHtml(id || "")}</div></button>`;
  }).join("") : '<div class="empty">没有客户结果</div>';
  if (list.length === 1) {
    const customer = list[0];
    selectSaleCustomer(customer.id || customer.customer_id, customer.name || customer.customer_name || customer.company_name || customer.title || "客户");
  }
  return list;
}

function selectSaleCustomer(id, name) {
  state.saleCustomer = { id, name };
  if (!$("saleCustomer")) return;
  $("saleCustomer").value = name;
  $("saleSelectedCustomer").textContent = name;
  $("saleCustomerChoices").innerHTML = "";
  renderSaleLines();
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
    const stock = product.inventory ?? 0;
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

function saleVariantStockText(variant) {
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
    inventory: variant.inventory ?? product.inventory ?? ""
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
        <div class="sale-product-sub">ID ${escapeHtml(line.product_id)}${line.coding ? ` · ${escapeHtml(line.coding)}` : ""}</div>
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
  if ($("saleResultCard")) $("saleResultCard").innerHTML = "<strong>开单结果</strong><p>提交后这里会显示销售单号、打印和删除入口。</p>";
  setDefaultSaleCreateTime(true);
  renderSaleLines();
}

async function quickSale() {
  if (state.saleSubmitting) return;
  if (!$('saleCustomer')) throw new Error('开单页面未加载');
  if (!state.saleCustomer) await searchSaleCustomers();
  if (!state.saleCustomer) throw new Error('请先选择客户');
  if (!state.saleLines.length) await addSaleLine();
  const warehouseId = Number($('saleWarehouse').value || 2);
  const createTime = saleCreateTimeText();
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
  bar.innerHTML = list.map((category) => {
    const id = category.id ?? "";
    const active = String(id) === String(state.productCategoryId || "");
    const total = category.total !== undefined && category.total !== "" ? ` ${category.total}` : "";
    return `<button class="${active ? "active" : ""}" onclick="selectProductCategory('${escapeAttr(id)}')">${escapeHtml(category.name || "分类")}${escapeHtml(total)}</button>`;
  }).join("");
}

function selectProductCategory(id) {
  state.productCategoryId = id || "";
  state.productPage = 1;
  renderProductCategories();
  loadProducts(1);
}
window.selectProductCategory = selectProductCategory;

async function loadProducts(page) {
  if (page !== undefined) state.productPage = page;
  await nextFrame();
  state.productPageSize = calculateProductPageSize();
  const keyword = ($("productKeyword") && $("productKeyword").value.trim()) || "";
  const target = $("productList");
  if (target) target.innerHTML = skeletonCards(Math.min(state.productPageSize, 8));
  const res = await api(`/api/product/list?${query({ keyword, page: state.productPage, page_size: state.productPageSize, category_id: state.productCategoryId, group: 1 })}`);
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
  const images = product.main_images || product.images || product.image || "";
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
    const specs = Number(product.spec_count || productVariants(product).length || 1);
    const category = product.product_category_text || product.simple_desc || "未分类";
    const coding = product.coding || product.product_code || id || "";
    return `
      <article class="product-card" style="--tone:${tones[index % tones.length]}">
        <div class="product-image ${img ? "has-img" : ""}">${img ? `<img src="${escapeAttr(img)}">` : ""}</div>
        <div class="product-body">
          <div class="product-main">
            <div class="product-title-row">
              <h3>${escapeHtml(product.title || product.name || "商品")}</h3>
              <span class="product-count">${escapeHtml(specs)} 规格</span>
            </div>
            <div class="muted">${escapeHtml(category)} · 编号 ${escapeHtml(coding)}</div>
            <div class="product-price-row"><strong>${productPriceText(product)}</strong></div>
          </div>
          <div class="product-tags">
            <span class="tag ${statusOk ? "green" : "green-outline"}">${escapeHtml(product.status_text || "正常")}</span>
            <span class="tag ${shelves ? "green" : "green-outline"}">${shelves ? "商城已上架" : "商城未上架"}</span>
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
    return { ...data.data, product_group_data: data.product_group_data || data.data.product_group_data || [] };
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
  const preview = $("drawerProductImagePreview");
  if (preview) {
    preview.classList.toggle("empty-upload", !list[0]);
    preview.innerHTML = list[0]
      ? `<img src="${escapeAttr(list[0])}" alt=""><span class="product-image-remove" onclick="event.stopPropagation(); removeProductMainImage();">×</span>`
      : '<span>+</span><strong>上传主图</strong>';
  }
}

function removeProductMainImage() {
  setProductMainImages([]);
}
window.removeProductMainImage = removeProductMainImage;

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
    grid.innerHTML = imagesHtml + '<button type="button" class="product-detail-item product-upload-tile" onclick="chooseProductUpload(\'detail\')"><span>+</span><strong>上传</strong></button>';
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
  const preview = card.querySelector(".product-spec-image");
  if (input) input.value = "";
  if (preview) {
    preview.classList.add("empty-upload");
    preview.innerHTML = "<span>+</span><strong>规格图</strong>";
  }
}
window.removeProductSpecImage = removeProductSpecImage;

function productRowsForForm(product = {}) {
  const rows = Array.isArray(product.product_group_data) && product.product_group_data.length ? product.product_group_data : [product];
  return rows.map((row) => {
    const base = Array.isArray(row.base) && row.base.length ? row.base[0] : {};
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
      images: row.images || "",
      image_url: row.images || ""
    };
  });
}

function productForm(product = {}) {
  const mainImages = Array.isArray(product.main_images_list) ? product.main_images_list : (productImage(product) ? [productImage(product)] : []);
  const desc = parseSimpleDesc(product.simple_desc || "");
  const detailImages = htmlToImages(product.content || "");
  const categoryIds = Array.isArray(product.product_category_ids) ? product.product_category_ids.map(Number).filter(Boolean) : [];
  const rows = productRowsForForm(product);
  return `
    <input id="drawerProductId" type="hidden" value="${escapeAttr(product.id || product.product_id || "")}">
    <input id="drawerProductMainImages" type="hidden" value="${escapeAttr(JSON.stringify(mainImages))}">
    <input id="drawerProductDetailImages" type="hidden" value="${escapeAttr(JSON.stringify(detailImages))}">
    <input id="drawerProductCategoryIds" type="hidden" value="${escapeAttr(JSON.stringify(categoryIds))}">
    <label>商品名称</label><input id="drawerProductTitle" value="${escapeAttr(product.title || product.name || "")}">
    <div class="product-image-editor">
      <label>主图</label>
      <button type="button" id="drawerProductImagePreview" class="product-image-preview ${mainImages[0] ? "" : "empty-upload"}" onclick="chooseProductUpload('main')">${mainImages[0] ? `<img src="${escapeAttr(mainImages[0])}" alt=""><span class="product-image-remove" onclick="event.stopPropagation(); removeProductMainImage();">×</span>` : "<span>+</span><strong>上传主图</strong>"}</button>
    </div>
    <label>分类（可多选）</label><div class="product-category-editor" id="drawerProductCategories"></div>
    <label>ERP 状态</label><select id="drawerProductStatus">${statusOptions(product.status ?? 0)}</select>
    <div class="two-col"><div><label>规格数量</label><input id="drawerProductDescNumber" type="number" step="1" value="${escapeAttr(desc.desc_number)}"></div><div><label>规格单位</label><select id="drawerProductDescUnit">${unitOptions(desc.desc_unit_id)}</select></div></div>
    <label>详情图片</label>
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
    cost_price: card.querySelector(".drawerSpecCostPrice").value || 0
  }));
}

function productSpecsHtml(rows) {
  const list = rows && rows.length ? rows : [{ local_key: localKey(), unit_id: (state.productUnits[0] && state.productUnits[0].id) || 1 }];
  return list.map((spec, index) => productSpecHtml(spec, index, list.length)).join("");
}

function productSpecHtml(spec = {}, index = 0, total = 1) {
  const img = spec.image_url || spec.images || "";
  return `
    <div class="product-spec-card" data-index="${index}">
      <input class="drawerSpecId" type="hidden" value="${escapeAttr(spec.id || "")}">
      <input class="drawerSpecBaseId" type="hidden" value="${escapeAttr(spec.base_id || "")}">
      <input class="drawerSpecImages" type="hidden" value="${escapeAttr(img || "")}">
      <div class="product-spec-head"><span>规格 ${index + 1}</span>${total > 1 ? `<button type="button" onclick="removeProductSpec(${index})">删除</button>` : ""}</div>
      <div class="product-spec-image-row"><button type="button" class="product-spec-image ${img ? "" : "empty-upload"}" onclick="chooseProductUpload('spec', ${index})">${img ? `<img src="${escapeAttr(img)}" alt=""><span class="product-image-remove" onclick="event.stopPropagation(); removeProductSpecImage(${index});">×</span>` : "<span>+</span><strong>规格图</strong>"}</button></div>
      <div class="two-col"><div><label>颜色/规格</label><input class="drawerSpecName" value="${escapeAttr(spec.spec || "")}"></div><div><label>单位</label><select class="drawerSpecUnit">${unitOptions(spec.unit_id || 1)}</select></div></div>
      <div class="two-col"><div><label>商品编码</label><input class="drawerSpecCoding" value="${escapeAttr(spec.coding || "")}"></div><div><label>条码</label><input class="drawerSpecBarcode" value="${escapeAttr(spec.barcode || "")}"></div></div>
      <div class="two-col"><div><label>售价</label><input class="drawerSpecPrice" type="number" step="0.01" value="${escapeAttr(spec.price || "")}"></div><div><label>成本价</label><input class="drawerSpecCostPrice" type="number" step="0.01" value="${escapeAttr(spec.cost_price || "")}"></div></div>
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
  } else if (target.type === "spec") {
    const cards = Array.from(document.querySelectorAll(".product-spec-card"));
    const card = cards[Number(target.index || 0)];
    if (card) {
      const input = card.querySelector(".drawerSpecImages");
      const preview = card.querySelector(".product-spec-image");
      if (input) input.value = url;
      if (preview) {
        preview.classList.remove("empty-upload");
        preview.innerHTML = `<img src="${escapeAttr(url)}" alt=""><span class="product-image-remove" onclick="event.stopPropagation(); removeProductSpecImage(${Number(target.index || 0)});">×</span>`;
      }
    }
  } else {
    setProductMainImages(url ? [url] : []);
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

function bindEvents() {
  const bind = (id, event, handler) => {
    const el = $(id);
    if (el) el.addEventListener(event, handler);
  };
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
      selectSaleCustomer(Number(saleCustomerButton.dataset.saleCustomerId), saleCustomerButton.dataset.saleCustomerName || "客户");
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
    setView("inventory");
    loadInventory($("quickInvKeyword").value);
  });
  bind("inventorySearchBtn", "click", () => loadInventory(undefined, 1));
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
window.selectSaleCustomer = (id, name) => actions.selectSaleCustomer(id, name);
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
