(function () {
  const ASSET_BASE = "./assets/images";
  const STORAGE_KEY = "sj_miniapp_designer_standalone_v1";
  const root = document.getElementById("designerRoot");
  const importInput = document.getElementById("jsonImportInput");
  const toastNode = document.getElementById("toast");

  const MODULE_GROUPS = [
    { key: "base", label: "基础组件" },
    { key: "goods", label: "商品组件" },
    { key: "marketing", label: "营销组件" },
    { key: "tool", label: "工具组件" }
  ];

  const MODULE_TYPES = [
    { type: "search", key: "search", label: "搜索", desc: "商品关键词搜索", group: "base" },
    { type: "banner", key: "carousel", label: "轮播图", desc: "首页广告轮播", group: "base" },
    { type: "nav", key: "nav-group", label: "导航组", desc: "快捷入口", group: "base" },
    { type: "image", key: "img-magic", label: "图片魔方", desc: "单图/多图展示", group: "base" },
    { type: "hot_zone", key: "hot-zone", label: "热区", desc: "图片热区跳转", group: "base" },
    { type: "title", key: "title", label: "标题", desc: "标题栏", group: "base" },
    { type: "notice", key: "notice", label: "公告", desc: "滚动通知", group: "base" },
    { type: "rich_text", key: "rich-text", label: "富文本", desc: "图文内容", group: "base" },
    { type: "video", key: "video", label: "视频", desc: "视频展示", group: "base" },
    { type: "row_line", key: "row-line", label: "辅助线", desc: "分割线", group: "base" },
    { type: "blank", key: "auxiliary-blank", label: "辅助空白", desc: "留白间距", group: "base" },
    { type: "product_shelf", key: "goods-list", label: "商品列表", desc: "产品列表", group: "goods" },
    { type: "goods_magic", key: "goods-magic", label: "商品魔方", desc: "商品组合展示", group: "goods" },
    { type: "goods_tabs", key: "goods-tabs", label: "商品选项卡", desc: "分组商品", group: "goods" },
    { type: "coupon", key: "coupon", label: "优惠券", desc: "优惠券模块", group: "marketing" },
    { type: "seckill", key: "seckill", label: "秒杀", desc: "限时活动", group: "marketing" },
    { type: "activity", key: "activity", label: "活动", desc: "活动入口", group: "marketing" },
    { type: "tabs", key: "tabs", label: "选项卡", desc: "页面分组", group: "tool" },
    { type: "tabs_carousel", key: "tabs-carousel", label: "选项卡轮播", desc: "组合轮播", group: "tool" },
    { type: "data_magic", key: "data-magic", label: "数据魔方", desc: "自定义数据", group: "tool" },
    { type: "data_tabs", key: "data-tabs", label: "数据选项卡", desc: "数据分组", group: "tool" },
    { type: "float_window", key: "float-window", label: "浮动窗口", desc: "悬浮入口", group: "tool" }
  ];

  const PAGE_OPTIONS = [
    ["/pages/index/index", "首页"],
    ["/pages/goods-category/goods-category", "分类"],
    ["/pages/order/order", "订单"],
    ["/pages/user/user", "我的"],
    ["/pages/search/search", "搜索"],
    ["/pages/product/list", "商品列表"]
  ];

  const state = {
    selectedIndex: 0,
    inspectorTab: "content",
    dragIndex: null,
    tick: 0,
    design: loadDesign()
  };

  function $(id) {
    return document.getElementById(id);
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function escapeAttr(value) {
    return escapeHtml(value);
  }

  function checkedAttr(value) {
    return Number(value) ? "checked" : "";
  }

  function idFor(type) {
    return `${type}_${Date.now()}_${Math.random().toString(16).slice(2, 7)}`;
  }

  function moduleMeta(type) {
    return MODULE_TYPES.find((item) => item.type === type) || MODULE_TYPES[0];
  }

  function moduleTypeLabel(type) {
    return moduleMeta(type).label || "模块";
  }

  function moduleIcon(type) {
    return `${ASSET_BASE}/layout/siderbar/${moduleMeta(type).key}.png`;
  }

  function defaultTabbar() {
    return {
      style: {
        color: "#606266",
        selected_color: "#2a94ff",
        background_color: "#ffffff",
        border_style: "black"
      },
      items: [
        { text: "首页", page_path: "/pages/index/index", icon: "static/images/common/tabbar/home.png", selected_icon: "static/images/black/tabbar/home.png", enabled: 1 },
        { text: "分类", page_path: "/pages/goods-category/goods-category", icon: "static/images/common/tabbar/category.png", selected_icon: "static/images/black/tabbar/category.png", enabled: 1 },
        { text: "订单", page_path: "/pages/order/order", icon: "static/images/common/tabbar/cart.png", selected_icon: "static/images/black/tabbar/cart.png", enabled: 1 },
        { text: "我的", page_path: "/pages/user/user", icon: "static/images/common/tabbar/user.png", selected_icon: "static/images/black/tabbar/user.png", enabled: 1 }
      ]
    };
  }

  function defaultDesign() {
    return {
      version: 1,
      home: {
        title: "肆计包装",
        subtitle: "茶包装产品展示",
        style: { background: "#f5f5f5", primary: "#2a94ff" },
        modules: [
          defaultModule("search"),
          defaultModule("banner"),
          defaultModule("nav"),
          defaultModule("title"),
          defaultModule("product_shelf"),
          defaultModule("notice")
        ]
      },
      tabbar: defaultTabbar()
    };
  }

  function defaultItem(type) {
    if (type === "product") return { title: "岩韵礼盒", subtitle: "半斤装", price: "128", image: "", url: "/pages/product/list" };
    if (type === "coupon") return { title: "新客券", amount: "20", threshold: "满 200 可用", url: "/pages/user/user" };
    if (type === "hot") return { title: "热区", url: "/pages/product/list", x: 10, y: 12, w: 38, h: 28 };
    if (type === "tab") return { title: "推荐", subtitle: "精选产品", content: "岩韵礼盒 / 山川礼盒 / 空白泡袋", image: "", url: "/pages/product/list" };
    if (type === "data") return { title: "新品", subtitle: "本周更新", value: "12", url: "/pages/product/list" };
    if (type === "activity") return { title: "新品专区", subtitle: "茶礼盒上新", image: "", url: "/pages/product/list" };
    return { title: "肆计包装", subtitle: "", image: "", url: "/pages/goods-category/goods-category" };
  }

  function defaultModule(type = "nav") {
    const id = idFor(type);
    const base = { id, type, enabled: 1, title: moduleTypeLabel(type), style: {} };
    switch (type) {
      case "search":
        return { ...base, title: "搜索", placeholder: "请输入搜索内容", url: "/pages/search/search" };
      case "banner":
        return { ...base, title: "首页轮播", interval: 3, items: [
          { title: "肆计包装", subtitle: "茶包装产品展示", image: "", url: "/pages/goods-category/goods-category" },
          { title: "新品礼盒", subtitle: "按分类查看", image: "", url: "/pages/product/list" }
        ] };
      case "nav":
        return { ...base, title: "快捷导航", columns: 4, items: [
          { title: "分类", url: "/pages/goods-category/goods-category", image: "" },
          { title: "订单", url: "/pages/order/order", image: "" },
          { title: "我的", url: "/pages/user/user", image: "" },
          { title: "搜索", url: "/pages/search/search", image: "" }
        ] };
      case "image":
        return { ...base, title: "图片魔方", layout: "two", items: [
          { title: "茶叶盒", image: "", url: "/pages/product/list" },
          { title: "泡袋", image: "", url: "/pages/product/list" }
        ] };
      case "hot_zone":
        return { ...base, title: "热区", image: "", items: [
          defaultItem("hot"),
          { title: "分类入口", url: "/pages/goods-category/goods-category", x: 56, y: 48, w: 34, h: 30 }
        ] };
      case "title":
        return { ...base, title: "推荐专区", subtitle: "精选产品", more_text: "查看更多", url: "/pages/product/list" };
      case "notice":
        return { ...base, title: "公告", content: "欢迎来到肆计包装，新品已更新", items: [
          { title: "新品已更新", url: "/pages/product/list" },
          { title: "分类数据已接入", url: "/pages/goods-category/goods-category" }
        ] };
      case "rich_text":
        return { ...base, title: "富文本", content: "肆计包装产品展示\n支持编辑多行图文说明。" };
      case "video":
        return { ...base, title: "视频", video_url: "", cover: "", items: [{ title: "视频封面", image: "", url: "" }] };
      case "row_line":
        return { ...base, title: "辅助线", height: 1, color: "#dcdfe6" };
      case "blank":
        return { ...base, title: "辅助空白", height: 24 };
      case "product_shelf":
        return { ...base, title: "推荐产品", keywords: "", category_id: "", limit: 8, layout: "two", products: [
          defaultItem("product"),
          { title: "山川礼盒", subtitle: "大盒", price: "168", image: "", url: "/pages/product/list" },
          { title: "空白泡袋", subtitle: "通用", price: "38", image: "", url: "/pages/product/list" },
          { title: "茶叶罐", subtitle: "圆罐", price: "88", image: "", url: "/pages/product/list" }
        ] };
      case "goods_magic":
        return { ...base, title: "商品魔方", columns: 2, items: [
          defaultItem("product"),
          { title: "山川礼盒", subtitle: "大盒", price: "168", image: "", url: "/pages/product/list" }
        ] };
      case "goods_tabs":
        return { ...base, title: "商品选项卡", active_tab: 0, items: [
          { title: "新品", subtitle: "4 件商品", content: "岩韵礼盒 / 山川礼盒 / 泡袋 / 茶叶罐", url: "/pages/product/list" },
          { title: "热销", subtitle: "6 件商品", content: "半斤礼盒 / 经典天地盖", url: "/pages/product/list" }
        ] };
      case "coupon":
        return { ...base, title: "优惠券", items: [
          defaultItem("coupon"),
          { title: "满减券", amount: "50", threshold: "满 500 可用", url: "/pages/user/user" }
        ] };
      case "seckill":
        return { ...base, title: "秒杀", end_time: "23:59:59", items: [
          { title: "限时礼盒", subtitle: "今日特价", price: "99", image: "", url: "/pages/product/list" },
          { title: "泡袋组合", subtitle: "限量", price: "29", image: "", url: "/pages/product/list" }
        ] };
      case "activity":
        return { ...base, title: "活动", items: [
          defaultItem("activity"),
          { title: "爆款专区", subtitle: "客户常买", image: "", url: "/pages/product/list" }
        ] };
      case "tabs":
        return { ...base, title: "选项卡", active_tab: 0, items: [
          defaultItem("tab"),
          { title: "分类", subtitle: "按产品分类", content: "茶叶盒 / 泡袋 / 罐子", url: "/pages/goods-category/goods-category" }
        ] };
      case "tabs_carousel":
        return { ...base, title: "选项卡轮播", active_tab: 0, items: [
          { title: "推荐", subtitle: "轮播一", image: "", url: "/pages/product/list" },
          { title: "新品", subtitle: "轮播二", image: "", url: "/pages/product/list" }
        ] };
      case "data_magic":
        return { ...base, title: "数据魔方", columns: 2, items: [
          defaultItem("data"),
          { title: "分类", subtitle: "已整理", value: "8", url: "/pages/goods-category/goods-category" }
        ] };
      case "data_tabs":
        return { ...base, title: "数据选项卡", active_tab: 0, items: [
          { title: "新品", subtitle: "最近更新", content: "新品礼盒、泡袋、罐子", url: "/pages/product/list" },
          { title: "客户常看", subtitle: "访问数据", content: "岩韵、山川、经典款", url: "/pages/product/list" }
        ] };
      case "float_window":
        return { ...base, title: "客服", position: "right_bottom", icon_text: "客服", url: "/pages/user/user" };
      default:
        return defaultModule("nav");
    }
  }

  function loadDesign() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return defaultDesign();
      const parsed = normalizeDesign(JSON.parse(raw));
      return parsed;
    } catch (err) {
      return defaultDesign();
    }
  }

  function normalizeDesign(input) {
    const fallback = defaultDesign();
    const design = input && typeof input === "object" ? input : fallback;
    if (!design.home || typeof design.home !== "object") design.home = fallback.home;
    if (!Array.isArray(design.home.modules)) design.home.modules = [];
    if (!design.home.style || typeof design.home.style !== "object" || Array.isArray(design.home.style)) design.home.style = clone(fallback.home.style);
    if (!design.tabbar || typeof design.tabbar !== "object" || Array.isArray(design.tabbar)) design.tabbar = defaultTabbar();
    if (!Array.isArray(design.tabbar.items)) design.tabbar.items = defaultTabbar().items;
    if (!design.tabbar.style || typeof design.tabbar.style !== "object" || Array.isArray(design.tabbar.style)) design.tabbar.style = defaultTabbar().style;
    design.version = Number(design.version || 1);
    design.home.title = design.home.title || "肆计包装";
    design.home.subtitle = design.home.subtitle || "茶包装产品展示";
    return design;
  }

  function home() {
    state.design = normalizeDesign(state.design);
    return state.design.home;
  }

  function modules() {
    return home().modules;
  }

  function tabbar() {
    return normalizeDesign(state.design).tabbar;
  }

  function selectedModule() {
    return modules()[Number(state.selectedIndex || 0)];
  }

  function styleObject(target) {
    if (!target.style || typeof target.style !== "object" || Array.isArray(target.style)) target.style = {};
    return target.style;
  }

  function styleValue(target, field, fallback = "") {
    const style = target.style && typeof target.style === "object" && !Array.isArray(target.style) ? target.style : {};
    return style[field] ?? fallback;
  }

  function moduleStyleAttr(module) {
    const style = module && typeof module.style === "object" && !Array.isArray(module.style) ? module.style : {};
    const rules = [];
    if (style.background) rules.push(`--miniapp-module-bg:${String(style.background).slice(0, 40)}`);
    if (style.radius !== undefined && style.radius !== "") rules.push(`--miniapp-module-radius:${Math.min(Math.max(Number(style.radius || 0), 0), 40)}px`);
    if (style.margin_top !== undefined && style.margin_top !== "") rules.push(`--miniapp-module-margin-top:${Math.min(Math.max(Number(style.margin_top || 0), 0), 80)}px`);
    if (style.margin_bottom !== undefined && style.margin_bottom !== "") rules.push(`--miniapp-module-margin-bottom:${Math.min(Math.max(Number(style.margin_bottom || 0), 0), 80)}px`);
    return rules.length ? ` style="${escapeAttr(rules.join(";"))}"` : "";
  }

  function itemIcon(item, fallback = "") {
    const title = String(item.title || fallback || "项").trim();
    return escapeHtml(title.slice(0, 1) || "项");
  }

  function imgStyle(url, overlay = false) {
    if (!url) return "";
    const value = overlay
      ? `background-image: linear-gradient(180deg, rgba(0,0,0,.08), rgba(0,0,0,.32)), url('${escapeAttr(url)}')`
      : `background-image: url('${escapeAttr(url)}')`;
    return ` style="${value}"`;
  }

  function currentRotatingIndex(items) {
    const list = Array.isArray(items) ? items : [];
    if (!list.length) return 0;
    return Math.abs(Number(state.tick || 0)) % list.length;
  }

  function renderProducts(items, columns = "two") {
    const list = Array.isArray(items) && items.length ? items : [defaultItem("product"), defaultItem("product")];
    const cls = columns === "one" ? "one" : columns === "three" ? "three" : "";
    return `<div class="miniapp-preview-products ${cls}">
      ${list.slice(0, columns === "three" ? 6 : 4).map((item) => `
        <span>
          <b${imgStyle(item.image)}></b>
          <i>${escapeHtml(item.title || "商品卡片")}</i>
          ${item.price ? `<small>¥${escapeHtml(item.price)}</small>` : ""}
        </span>
      `).join("")}
    </div>`;
  }

  function renderCardGrid(items, columns = 2, mode = "normal") {
    const list = Array.isArray(items) && items.length ? items : [defaultItem("activity"), defaultItem("activity")];
    const cls = Number(columns) === 3 ? "three" : "two";
    return `<div class="miniapp-card-grid ${cls}">
      ${list.slice(0, Number(columns) === 3 ? 6 : 4).map((item) => `
        <span class="miniapp-card">
          <b${imgStyle(item.image)}></b>
          <strong>${escapeHtml(item.title || "卡片")}</strong>
          <i>${escapeHtml(item.subtitle || item.content || "")}</i>
          ${mode === "data" ? `<small>${escapeHtml(item.value || "")}</small>` : item.price ? `<small>¥${escapeHtml(item.price)}</small>` : ""}
        </span>
      `).join("")}
    </div>`;
  }

  function renderPreviewModule(module = {}, index = 0) {
    const type = module.type || "nav";
    const active = Number(state.selectedIndex || 0) === index ? "main-border" : "";
    const disabled = Number(module.enabled ?? 1) ? "" : "disabled";
    const title = module.title || moduleTypeLabel(type);
    const base = `type="button" draggable="true" class="miniapp-preview-module ${active} ${disabled}" data-miniapp-select-module="${index}" data-drag-index="${index}"${moduleStyleAttr(module)}`;

    if (type === "banner") {
      const items = Array.isArray(module.items) && module.items.length ? module.items : [{ title: "轮播图" }];
      const current = currentRotatingIndex(items);
      const item = items[current] || items[0];
      return `<button ${base}>
        <div class="miniapp-preview-banner"${imgStyle(item.image, true)}>
          <strong>${escapeHtml(item.title || title || "首页轮播")}</strong>
          <span>${escapeHtml(item.subtitle || `${items.length} 张轮播`)}</span>
          <div class="miniapp-dots">${items.map((_, dot) => `<i class="${dot === current ? "active" : ""}"></i>`).join("")}</div>
        </div>
      </button>`;
    }

    if (type === "search") {
      return `<button ${base}><div class="miniapp-preview-search"><span>⌕</span><em>${escapeHtml(module.placeholder || "请输入搜索内容")}</em></div></button>`;
    }

    if (type === "nav") {
      const items = Array.isArray(module.items) ? module.items : [];
      return `<button ${base}>
        <div class="miniapp-preview-nav" style="grid-template-columns:repeat(${Math.min(Math.max(Number(module.columns || 4), 3), 5)},1fr)">
          ${items.slice(0, 10).map((item) => `<span><i>${miniImageOrText(item)}</i>${escapeHtml(item.title || "导航")}</span>`).join("") || "<em>暂无导航</em>"}
        </div>
      </button>`;
    }

    if (type === "product_shelf") {
      return `<button ${base}><div class="miniapp-preview-title">${escapeHtml(title || "商品区")}</div>${renderProducts(module.products, module.layout || "two")}</button>`;
    }

    if (type === "goods_magic") {
      return `<button ${base}><div class="miniapp-preview-title">${escapeHtml(title)}</div>${renderCardGrid(module.items, module.columns || 2, "product")}</button>`;
    }

    if (type === "goods_tabs" || type === "tabs" || type === "data_tabs") {
      const items = Array.isArray(module.items) && module.items.length ? module.items : [defaultItem("tab")];
      const current = Math.min(Math.max(Number(module.active_tab || 0), 0), items.length - 1);
      const activeItem = items[current] || items[0];
      return `<button ${base}>
        <div class="tabs-preview">
          <div class="tabs-nav">${items.slice(0, 4).map((item, tabIndex) => `<span class="${tabIndex === current ? "active" : ""}">${escapeHtml(item.title || `分组${tabIndex + 1}`)}</span>`).join("")}</div>
          <div class="tabs-body">${escapeHtml(activeItem.content || activeItem.subtitle || "选项卡内容")}</div>
        </div>
      </button>`;
    }

    if (type === "coupon") {
      const items = Array.isArray(module.items) && module.items.length ? module.items : [defaultItem("coupon")];
      return `<button ${base}><div class="miniapp-preview-title">${escapeHtml(title)}</div><div class="coupon-strip">
        ${items.slice(0, 2).map((item) => `<span class="coupon-card"><strong>¥${escapeHtml(item.amount || "20")}</strong><small>${escapeHtml(item.title || "优惠券")} · ${escapeHtml(item.threshold || "")}</small></span>`).join("")}
      </div></button>`;
    }

    if (type === "seckill") {
      return `<button ${base}>
        <div class="seckill-head"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(module.end_time || "23:59:59")}</span></div>
        ${renderProducts(module.items, "two")}
      </button>`;
    }

    if (type === "activity") {
      return `<button ${base}><div class="miniapp-preview-title">${escapeHtml(title)}</div>${renderCardGrid(module.items, 2, "normal")}</button>`;
    }

    if (type === "tabs_carousel") {
      const items = Array.isArray(module.items) && module.items.length ? module.items : [defaultItem("tab")];
      const current = currentRotatingIndex(items);
      const item = items[current] || items[0];
      return `<button ${base}>
        <div class="tabs-preview">
          <div class="tabs-nav">${items.slice(0, 4).map((row, tabIndex) => `<span class="${tabIndex === current ? "active" : ""}">${escapeHtml(row.title || `轮播${tabIndex + 1}`)}</span>`).join("")}</div>
          <div class="miniapp-preview-image"${imgStyle(item.image)}><strong>${escapeHtml(item.subtitle || item.title || title)}</strong><span>${escapeHtml(`${items.length} 个轮播项`)}</span></div>
        </div>
      </button>`;
    }

    if (type === "data_magic") {
      return `<button ${base}><div class="miniapp-preview-title">${escapeHtml(title)}</div>${renderCardGrid(module.items, module.columns || 2, "data")}</button>`;
    }

    if (type === "title") {
      return `<button ${base}><div class="miniapp-preview-heading"><strong>${escapeHtml(title || "标题")}</strong><span>${escapeHtml(module.subtitle || module.more_text || "副标题")}</span></div></button>`;
    }

    if (type === "notice") {
      const items = Array.isArray(module.items) ? module.items : [];
      const item = items.length ? items[currentRotatingIndex(items)] : null;
      return `<button ${base}><div class="miniapp-preview-notice"><strong>${escapeHtml(title || "公告")}</strong><span>${escapeHtml((item && item.title) || module.content || "新品已更新")}</span></div></button>`;
    }

    if (type === "row_line") {
      const height = Math.min(Math.max(Number(module.height || 1), 1), 12);
      const color = module.color || "#dcdfe6";
      return `<button ${base}><div class="miniapp-preview-line" style="--line-height:${height}px;background:${escapeAttr(color)}"></div></button>`;
    }

    if (type === "blank") {
      const height = Math.min(Math.max(Number(module.height || 24), 12), 120);
      return `<button ${base}><div class="miniapp-preview-blank" style="height:${height}px"></div></button>`;
    }

    if (type === "video") {
      const item = Array.isArray(module.items) && module.items.length ? module.items[0] : {};
      return `<button ${base}><div class="miniapp-preview-video"${imgStyle(module.cover || item.image, true)}><span>▶</span><strong>${escapeHtml(title || "视频")}</strong></div></button>`;
    }

    if (type === "rich_text") {
      return `<button ${base}><div class="miniapp-preview-rich"><strong>${escapeHtml(title || "富文本")}</strong><p>${escapeHtml(module.content || "图文内容")}</p></div></button>`;
    }

    if (type === "hot_zone") {
      const items = Array.isArray(module.items) ? module.items : [];
      return `<button ${base}>
        <div class="miniapp-preview-image hot"${imgStyle(module.image)}>
          <strong>${escapeHtml(title || "热区")}</strong>
          <small>配置点击区域</small>
          <div class="hot-zone-points">${items.map((item) => `<span style="left:${Number(item.x || 0)}%;top:${Number(item.y || 0)}%;width:${Number(item.w || 28)}%;height:${Number(item.h || 22)}%">${escapeHtml(item.title || "热区")}</span>`).join("")}</div>
        </div>
      </button>`;
    }

    if (type === "float_window") {
      return `<button ${base}><div class="miniapp-preview-blank" style="height:84px"></div><span class="float-window-preview">${escapeHtml(module.icon_text || title || "客服")}</span></button>`;
    }

    const item = Array.isArray(module.items) && module.items.length ? module.items[0] : {};
    return `<button ${base}>
      <div class="miniapp-preview-image"${imgStyle(item.image)}>
        <strong>${escapeHtml(item.title || title || moduleTypeLabel(type))}</strong>
        <span>${escapeHtml(moduleTypeLabel(type))}</span>
      </div>
    </button>`;
  }

  function miniImageOrText(item) {
    if (item.image) return `<span style="width:100%;height:100%;border-radius:50%;background-image:url('${escapeAttr(item.image)}');background-size:cover;background-position:center"></span>`;
    return itemIcon(item);
  }

  function outlineRow(module = {}, index = 0, total = 0) {
    const active = Number(state.selectedIndex || 0) === index ? "drawer-drag-bg" : "";
    const off = Number(module.enabled ?? 1) ? "" : "off";
    return `<div class="miniapp-outline-row ${active} ${off}" draggable="true" data-drag-index="${index}" data-miniapp-select-module="${index}">
      <button type="button" class="miniapp-outline-main" data-miniapp-select-module="${index}">
        <span class="iconfont">☰</span>
        <img src="${moduleIcon(module.type)}" alt="">
        <strong>${escapeHtml(module.title || moduleTypeLabel(module.type))}</strong>
        <small>${escapeHtml(moduleTypeLabel(module.type))}</small>
      </button>
      <button type="button" data-miniapp-module-move="-1" data-miniapp-index="${index}" ${index <= 0 ? "disabled" : ""} title="上移">↑</button>
      <button type="button" data-miniapp-module-move="1" data-miniapp-index="${index}" ${index >= total - 1 ? "disabled" : ""} title="下移">↓</button>
      <button type="button" data-miniapp-module-duplicate data-miniapp-index="${index}" title="复制">⧉</button>
      <button type="button" class="setting-delete" data-miniapp-module-remove data-miniapp-index="${index}" title="删除">×</button>
    </div>`;
  }

  function inspectorTabsHtml() {
    const tab = state.inspectorTab === "style" ? "style" : "content";
    return `<div class="radio-group">
      <button class="${tab === "content" ? "active" : ""}" type="button" data-miniapp-inspector-tab="content">内容</button>
      <button class="${tab === "style" ? "active" : ""}" type="button" data-miniapp-inspector-tab="style">样式</button>
    </div>`;
  }

  function moduleTypeOptions(current = "nav") {
    return MODULE_TYPES.map((item) => `<option value="${escapeAttr(item.type)}" ${item.type === current ? "selected" : ""}>${escapeHtml(item.label)}</option>`).join("");
  }

  function pageOptions(current = "") {
    return PAGE_OPTIONS.map(([value, label]) => `<option value="${escapeAttr(value)}" ${value === current ? "selected" : ""}>${escapeHtml(label)}</option>`).join("");
  }

  function inputField(label, name, value, type = "text", attrs = "") {
    return `<label class="shopxo-form-item"><span>${escapeHtml(label)}</span><input class="shopxo-input" type="${escapeAttr(type)}" data-miniapp-module-field="${escapeAttr(name)}" value="${escapeAttr(value ?? "")}" ${attrs}></label>`;
  }

  function selectField(label, name, value, options) {
    return `<label class="shopxo-form-item"><span>${escapeHtml(label)}</span><select class="shopxo-input" data-miniapp-module-field="${escapeAttr(name)}">${options.map((item) => `<option value="${escapeAttr(item[0])}" ${String(item[0]) === String(value) ? "selected" : ""}>${escapeHtml(item[1])}</option>`).join("")}</select></label>`;
  }

  function textareaField(label, name, value) {
    return `<label class="shopxo-form-item column"><span>${escapeHtml(label)}</span><textarea class="shopxo-input" data-miniapp-module-field="${escapeAttr(name)}">${escapeHtml(value ?? "")}</textarea></label>`;
  }

  function tabbarEditor() {
    const data = tabbar();
    const style = data.style || {};
    const items = Array.isArray(data.items) ? data.items : [];
    return `
      <div class="shopxo-form-card">
        <div class="shopxo-card-title">底部导航</div>
        <label class="shopxo-form-item"><span>默认颜色</span><input class="shopxo-input" data-miniapp-tabbar-style-field="color" value="${escapeAttr(style.color || "#606266")}"></label>
        <label class="shopxo-form-item"><span>选中颜色</span><input class="shopxo-input" data-miniapp-tabbar-style-field="selected_color" value="${escapeAttr(style.selected_color || "#2a94ff")}"></label>
        <label class="shopxo-form-item"><span>背景颜色</span><input class="shopxo-input" data-miniapp-tabbar-style-field="background_color" value="${escapeAttr(style.background_color || "#ffffff")}"></label>
        <label class="shopxo-form-item"><span>边框样式</span>
          <select class="shopxo-input" data-miniapp-tabbar-style-field="border_style">
            <option value="black" ${style.border_style !== "white" ? "selected" : ""}>黑色</option>
            <option value="white" ${style.border_style === "white" ? "selected" : ""}>白色</option>
          </select>
        </label>
      </div>
      <div class="shopxo-form-card">
        <div class="shopxo-card-title"><span>导航项</span><button type="button" class="shopxo-el-button shopxo-el-button--small" data-miniapp-reset-tabbar>重置</button></div>
        <div class="miniapp-tabbar-editor">
          ${items.map((item, index) => `
            <div class="miniapp-tabbar-row" data-miniapp-tabbar-index="${index}">
              <label><span>名称</span><input class="shopxo-input" data-miniapp-tabbar-field="text" value="${escapeAttr(item.text || "")}"></label>
              <label><span>页面</span><select class="shopxo-input" data-miniapp-tabbar-field="page_path">${pageOptions(item.page_path)}</select></label>
              <label><span>默认图标</span><input class="shopxo-input" data-miniapp-tabbar-field="icon" value="${escapeAttr(item.icon || "")}"></label>
              <label><span>选中图标</span><input class="shopxo-input" data-miniapp-tabbar-field="selected_icon" value="${escapeAttr(item.selected_icon || "")}"></label>
            </div>
          `).join("")}
        </div>
      </div>`;
  }

  function arrayEditor(title, listName, fields, emptyType = "") {
    const module = selectedModule();
    if (!module) return "";
    const items = Array.isArray(module[listName]) ? module[listName] : [];
    const cols = Math.min(Math.max(fields.length, 1), 5);
    return `<div class="shopxo-form-card full">
      <div class="shopxo-card-title">
        <span>${escapeHtml(title)}</span>
        <button type="button" class="shopxo-el-button shopxo-el-button--small" data-miniapp-add-item data-list-name="${escapeAttr(listName)}" data-empty-type="${escapeAttr(emptyType)}">+添加</button>
      </div>
      <div class="miniapp-item-editor">
        ${items.map((item, index) => `
          <div class="miniapp-item-row" style="--item-cols:${cols}" data-list-name="${escapeAttr(listName)}" data-miniapp-item-index="${index}">
            ${fields.map((field) => itemInput(field, item)).join("")}
            <button type="button" class="setting-delete" data-miniapp-remove-item="${index}" data-list-name="${escapeAttr(listName)}" title="删除">×</button>
          </div>
        `).join("") || '<div class="empty">还没有内容项</div>'}
      </div>
    </div>`;
  }

  function itemInput(field, item) {
    const value = item[field.name] ?? "";
    if (field.type === "select") {
      return `<label><span>${escapeHtml(field.label)}</span><select class="shopxo-input" data-miniapp-item-field="${escapeAttr(field.name)}">${field.options.map((option) => `<option value="${escapeAttr(option[0])}" ${String(option[0]) === String(value) ? "selected" : ""}>${escapeHtml(option[1])}</option>`).join("")}</select></label>`;
    }
    return `<label><span>${escapeHtml(field.label)}</span><input class="shopxo-input" type="${escapeAttr(field.type || "text")}" data-miniapp-item-field="${escapeAttr(field.name)}" value="${escapeAttr(value)}" ${field.attrs || ""}></label>`;
  }

  function inspectorHtml() {
    if (Number(state.selectedIndex) < 0) {
      const page = home();
      const tab = state.inspectorTab === "style" ? "style" : "content";
      return `
        <div class="settings-title"><div class="title">页面设置</div>${inspectorTabsHtml()}</div>
        <div class="setting-content">
          ${tab === "style" ? `
            <div class="shopxo-form-card">
              <div class="shopxo-card-title">页面样式</div>
              <label class="shopxo-form-item"><span>背景颜色</span><input class="shopxo-input" data-miniapp-home-style-field="background" value="${escapeAttr(styleValue(page, "background", "#f5f5f5"))}"></label>
              <label class="shopxo-form-item"><span>主题颜色</span><input class="shopxo-input" data-miniapp-home-style-field="primary" value="${escapeAttr(styleValue(page, "primary", "#2a94ff"))}"></label>
            </div>
          ` : `
            <div class="shopxo-form-card">
              <div class="shopxo-card-title">页面内容</div>
              <label class="shopxo-form-item"><span>页面标题</span><input class="shopxo-input" data-miniapp-home-field="title" value="${escapeAttr(page.title || "肆计包装")}"></label>
              <label class="shopxo-form-item"><span>副标题</span><input class="shopxo-input" data-miniapp-home-field="subtitle" value="${escapeAttr(page.subtitle || "茶包装产品展示")}"></label>
            </div>
            ${tabbarEditor()}
          `}
        </div>`;
    }

    const selected = selectedModule();
    if (!selected) {
      return `<div class="settings-title"><div class="title">组件设置</div></div><div class="setting-content"><div class="empty">从左侧新增模块，或在中间预览里选择一个模块。</div></div>`;
    }
    const type = selected.type || "nav";
    const tab = state.inspectorTab === "style" ? "style" : "content";
    return `
      <div class="settings-title"><div class="title">${escapeHtml(selected.title || moduleTypeLabel(type))}</div>${inspectorTabsHtml()}</div>
      <div class="setting-content">
        ${tab === "style" ? styleEditor(selected) : contentEditor(selected)}
      </div>`;
  }

  function styleEditor(module) {
    return `<div class="shopxo-form-card">
      <div class="shopxo-card-title">模块样式</div>
      <label class="shopxo-form-item"><span>背景颜色</span><input class="shopxo-input" data-miniapp-module-style-field="background" value="${escapeAttr(styleValue(module, "background", ""))}" placeholder="#ffffff"></label>
      <label class="shopxo-form-item"><span>上间距</span><input class="shopxo-input" type="number" min="0" max="80" data-miniapp-module-style-field="margin_top" value="${escapeAttr(styleValue(module, "margin_top", 0))}"></label>
      <label class="shopxo-form-item"><span>下间距</span><input class="shopxo-input" type="number" min="0" max="80" data-miniapp-module-style-field="margin_bottom" value="${escapeAttr(styleValue(module, "margin_bottom", 0))}"></label>
      <label class="shopxo-form-item"><span>圆角</span><input class="shopxo-input" type="number" min="0" max="40" data-miniapp-module-style-field="radius" value="${escapeAttr(styleValue(module, "radius", 0))}"></label>
    </div>`;
  }

  function contentEditor(module) {
    const type = module.type || "nav";
    const index = Number(state.selectedIndex || 0);
    const common = `
      <div class="shopxo-form-card">
        <div class="shopxo-card-title">基础设置</div>
        <label class="shopxo-form-item"><span>模块类型</span><select class="shopxo-input" data-miniapp-module-field="type">${moduleTypeOptions(type)}</select></label>
        <label class="shopxo-form-item"><span>模块标题</span><input class="shopxo-input" data-miniapp-module-field="title" value="${escapeAttr(module.title || "")}" placeholder="例如：推荐产品"></label>
        <label class="shopxo-switch-row"><span>显示模块</span><input type="checkbox" data-miniapp-module-field="enabled" ${checkedAttr(module.enabled ?? 1)}><i></i></label>
      </div>
      <div class="shopxo-form-card">
        <div class="shopxo-card-title">组件操作</div>
        <div class="miniapp-module-actions">
          <button type="button" class="shopxo-el-button" data-miniapp-module-move="-1" data-miniapp-index="${index}">上移</button>
          <button type="button" class="shopxo-el-button" data-miniapp-module-move="1" data-miniapp-index="${index}">下移</button>
          <button type="button" class="shopxo-el-button" data-miniapp-module-duplicate data-miniapp-index="${index}">复制</button>
          <button type="button" class="shopxo-el-button miniapp-danger-button" data-miniapp-module-remove data-miniapp-index="${index}">删除</button>
        </div>
      </div>`;
    const linkField = inputField("跳转路径", "url", module.url || "");
    if (type === "search") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">搜索设置</div>${inputField("提示文字", "placeholder", module.placeholder || "")}${linkField}</div>`;
    if (type === "banner") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">轮播设置</div>${inputField("切换秒数", "interval", module.interval || 3, "number", 'min="1" max="12"')}</div>${arrayEditor("轮播项", "items", imageFields(), "base")}`;
    if (type === "nav") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">导航设置</div>${selectField("每行数量", "columns", module.columns || 4, [["3", "3 个"], ["4", "4 个"], ["5", "5 个"]])}</div>${arrayEditor("导航项", "items", imageFields(), "base")}`;
    if (type === "image") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">魔方设置</div>${selectField("布局", "layout", module.layout || "two", [["one", "单列"], ["two", "双列"], ["three", "三列"]])}</div>${arrayEditor("图片项", "items", imageFields(), "base")}`;
    if (type === "hot_zone") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">底图设置</div>${inputField("底图地址", "image", module.image || "")}</div>${arrayEditor("热区项", "items", hotFields(), "hot")}`;
    if (type === "title") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">标题设置</div>${inputField("副标题", "subtitle", module.subtitle || "")}${inputField("更多文字", "more_text", module.more_text || "")}${linkField}</div>`;
    if (type === "notice") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">公告设置</div>${textareaField("公告内容", "content", module.content || "")}</div>${arrayEditor("公告链接", "items", simpleFields(), "base")}`;
    if (type === "rich_text") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">富文本设置</div>${textareaField("内容", "content", module.content || "")}</div>`;
    if (type === "video") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">视频设置</div>${inputField("视频地址", "video_url", module.video_url || "")}${inputField("封面地址", "cover", module.cover || "")}</div>`;
    if (type === "row_line") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">辅助线设置</div>${inputField("高度", "height", module.height || 1, "number", 'min="1" max="12"')}${inputField("颜色", "color", module.color || "#dcdfe6")}</div>`;
    if (type === "blank") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">空白设置</div>${inputField("高度", "height", module.height || 24, "number", 'min="1" max="120"')}</div>`;
    if (type === "product_shelf") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">商品设置</div>${inputField("搜索关键词", "keywords", module.keywords || "")}${inputField("分类 ID", "category_id", module.category_id || "")}${inputField("展示数量", "limit", module.limit || 8, "number", 'min="1" max="30"')}${selectField("布局", "layout", module.layout || "two", [["one", "单列"], ["two", "双列"], ["three", "三列"]])}</div>${arrayEditor("预览商品", "products", productFields(), "product")}`;
    if (type === "goods_magic") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">魔方设置</div>${selectField("列数", "columns", module.columns || 2, [["2", "双列"], ["3", "三列"]])}</div>${arrayEditor("商品项", "items", productFields(), "product")}`;
    if (type === "goods_tabs") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">选项卡设置</div>${inputField("默认分组", "active_tab", module.active_tab || 0, "number", 'min="0"')}</div>${arrayEditor("商品分组", "items", tabFields(), "tab")}`;
    if (type === "coupon") return common + arrayEditor("优惠券", "items", couponFields(), "coupon");
    if (type === "seckill") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">秒杀设置</div>${inputField("结束时间", "end_time", module.end_time || "23:59:59")}</div>${arrayEditor("秒杀商品", "items", productFields(), "product")}`;
    if (type === "activity") return common + arrayEditor("活动入口", "items", activityFields(), "activity");
    if (type === "tabs") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">选项卡设置</div>${inputField("默认分组", "active_tab", module.active_tab || 0, "number", 'min="0"')}</div>${arrayEditor("选项卡", "items", tabFields(), "tab")}`;
    if (type === "tabs_carousel") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">轮播设置</div>${inputField("默认分组", "active_tab", module.active_tab || 0, "number", 'min="0"')}</div>${arrayEditor("轮播分组", "items", imageFields(), "tab")}`;
    if (type === "data_magic") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">数据魔方设置</div>${selectField("列数", "columns", module.columns || 2, [["2", "双列"], ["3", "三列"]])}</div>${arrayEditor("数据项", "items", dataFields(), "data")}`;
    if (type === "data_tabs") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">数据选项卡设置</div>${inputField("默认分组", "active_tab", module.active_tab || 0, "number", 'min="0"')}</div>${arrayEditor("数据分组", "items", tabFields(), "tab")}`;
    if (type === "float_window") return common + `<div class="shopxo-form-card"><div class="shopxo-card-title">悬浮设置</div>${inputField("显示文字", "icon_text", module.icon_text || "")}${selectField("位置", "position", module.position || "right_bottom", [["right_bottom", "右下"], ["left_bottom", "左下"]])}${linkField}</div>`;
    return common;
  }

  function imageFields() {
    return [
      { name: "title", label: "标题" },
      { name: "url", label: "跳转" },
      { name: "image", label: "图片" },
      { name: "subtitle", label: "说明" }
    ];
  }

  function simpleFields() {
    return [
      { name: "title", label: "标题" },
      { name: "url", label: "跳转" }
    ];
  }

  function productFields() {
    return [
      { name: "title", label: "名称" },
      { name: "price", label: "价格" },
      { name: "image", label: "图片" },
      { name: "url", label: "跳转" }
    ];
  }

  function couponFields() {
    return [
      { name: "title", label: "名称" },
      { name: "amount", label: "金额" },
      { name: "threshold", label: "门槛" },
      { name: "url", label: "跳转" }
    ];
  }

  function hotFields() {
    return [
      { name: "title", label: "标题" },
      { name: "url", label: "跳转" },
      { name: "x", label: "X%", type: "number", attrs: 'min="0" max="100"' },
      { name: "y", label: "Y%", type: "number", attrs: 'min="0" max="100"' },
      { name: "w", label: "宽%", type: "number", attrs: 'min="1" max="100"' },
      { name: "h", label: "高%", type: "number", attrs: 'min="1" max="100"' }
    ];
  }

  function tabFields() {
    return [
      { name: "title", label: "标题" },
      { name: "subtitle", label: "说明" },
      { name: "content", label: "内容" },
      { name: "url", label: "跳转" }
    ];
  }

  function dataFields() {
    return [
      { name: "title", label: "标题" },
      { name: "value", label: "数值" },
      { name: "subtitle", label: "说明" },
      { name: "url", label: "跳转" }
    ];
  }

  function activityFields() {
    return [
      { name: "title", label: "标题" },
      { name: "subtitle", label: "说明" },
      { name: "image", label: "图片" },
      { name: "url", label: "跳转" }
    ];
  }

  function componentGroupHtml(group) {
    const items = MODULE_TYPES.filter((item) => item.group === group.key);
    if (!items.length) return "";
    return `<div class="shopxo-collapse-item">
      <div class="shopxo-collapse-title">${escapeHtml(group.label)}</div>
      <div class="component">
        ${items.map((item) => `
          <button type="button" class="item" data-miniapp-add-module="${escapeAttr(item.type)}" title="${escapeAttr(item.desc)}">
            <div class="siderbar-show">
              <img class="img" src="${ASSET_BASE}/layout/siderbar/${escapeAttr(item.key)}.png" alt="">
              <div>${escapeHtml(item.label)}</div>
            </div>
          </button>
        `).join("")}
      </div>
    </div>`;
  }

  function render() {
    state.design = normalizeDesign(state.design);
    const page = home();
    const list = modules();
    if (state.selectedIndex >= list.length) state.selectedIndex = list.length ? list.length - 1 : -1;
    const pageStyle = page.style || {};
    const tabbarStyle = tabbar().style || {};
    const tabbarItems = Array.isArray(tabbar().items) ? tabbar().items : [];
    const navCols = Math.max(tabbarItems.length || 4, 1);
    root.innerHTML = `
      <div class="designer-shell">
        <header class="designer-topbar">
          <div class="designer-brand">
            <h1>肆计小程序首页设计器</h1>
            <span>独立预览版 · 后端暂未接入</span>
          </div>
          <div class="topbar-actions">
            <button type="button" class="shopxo-el-button" data-designer-action="demo">恢复示例</button>
            <button type="button" class="shopxo-el-button" data-designer-action="import">导入 JSON</button>
            <button type="button" class="shopxo-el-button" data-designer-action="export">导出 JSON</button>
            <button type="button" class="shopxo-el-button" data-designer-action="clear">清空</button>
            <button type="button" class="shopxo-el-button shopxo-el-button--primary" data-designer-action="save">保存草稿</button>
          </div>
        </header>
        <section class="shopxo-diy" style="--miniapp-page-bg:${escapeAttr(pageStyle.background || "#f5f5f5")};--miniapp-page-primary:${escapeAttr(pageStyle.primary || "#2a94ff")};--miniapp-tabbar-bg:${escapeAttr(tabbarStyle.background_color || "#ffffff")};--miniapp-tabbar-color:${escapeAttr(tabbarStyle.color || "#606266")};--miniapp-tabbar-selected:${escapeAttr(tabbarStyle.selected_color || pageStyle.primary || "#2a94ff")};">
          <div class="shopxo-app-wrapper">
            <div class="shopxo-app-content">
              <aside class="siderbar">
                <div class="shopxo-side-head"><span>组件库</span><small>${MODULE_TYPES.length} 个组件</small></div>
                ${MODULE_GROUPS.map(componentGroupHtml).join("")}
              </aside>
              <div class="drawer-container ${list.length ? "" : "empty"}">
                <div class="drawer-content">
                  <div class="drawer-title">已选组件(${list.length})</div>
                  <div class="drawer-drag-area">
                    <div class="miniapp-outline">${list.map((module, index) => outlineRow(module, index, list.length)).join("") || '<div class="empty">还没有模块</div>'}</div>
                  </div>
                </div>
              </div>
              <main class="main">
                <div class="model">
                  <div class="model-content">
                    <div class="acticons">
                      <button type="button" class="shopxo-el-button shopxo-el-button--large" data-miniapp-page-settings>页面设置</button>
                      <button type="button" class="shopxo-el-button shopxo-el-button--large" data-designer-action="export">导出</button>
                      <button type="button" class="shopxo-el-button shopxo-el-button--large" data-designer-action="import">导入</button>
                      <button type="button" class="shopxo-el-button shopxo-el-button--large" data-designer-action="clear">清空</button>
                    </div>
                    <div class="model-drag">
                      <div class="page-bg"></div>
                      <button type="button" class="model-top ${Number(state.selectedIndex) < 0 ? "page-settings-border" : ""}" data-miniapp-page-settings>
                        <div class="roll">
                          <div class="status-bar"><img class="img" src="${ASSET_BASE}/layout/main/main-top.png" alt=""></div>
                          <div class="model-head">
                            <div class="model-head-content">${escapeHtml(page.title || "肆计包装")}</div>
                            <div class="model-head-subtitle">${escapeHtml(page.subtitle || "茶包装产品展示")}</div>
                          </div>
                        </div>
                      </button>
                      <div class="model-wall">
                        <div class="model-wall-content">
                          <div class="drag-area">${list.map(renderPreviewModule).join("") || '<div class="miniapp-preview-empty">从左侧添加首页组件</div>'}</div>
                        </div>
                      </div>
                      <button type="button" class="footer-nav" data-miniapp-page-settings>
                        <div class="footer-nav-content" style="grid-template-columns:repeat(${navCols},1fr)">
                          ${tabbarItems.map((item, index) => `<span class="${index === 0 ? "active" : ""}">${escapeHtml(item.text || "")}</span>`).join("") || '<span class="active">首页</span><span>分类</span><span>订单</span><span>我的</span>'}
                        </div>
                      </button>
                    </div>
                  </div>
                </div>
              </main>
              <aside class="settings">${inspectorHtml()}</aside>
            </div>
            <div class="shopxo-app-footer">
              <button type="button" class="shopxo-el-button" data-designer-action="copy-json">复制 JSON</button>
              <button type="button" class="shopxo-el-button" data-miniapp-page-settings>页面/导航设置</button>
              <button type="button" class="shopxo-el-button shopxo-el-button--primary" data-designer-action="save">保存草稿</button>
            </div>
          </div>
        </section>
      </div>`;
  }

  function addModule(type = "nav") {
    modules().push(defaultModule(type));
    state.selectedIndex = modules().length - 1;
    state.inspectorTab = "content";
    render();
  }

  function selectModule(index = 0) {
    state.selectedIndex = Math.min(Math.max(Number(index || 0), 0), Math.max(modules().length - 1, 0));
    render();
  }

  function selectPageSettings() {
    state.selectedIndex = -1;
    render();
  }

  function moveModule(index, delta) {
    const list = modules();
    const current = Number(index || 0);
    const next = current + Number(delta || 0);
    if (next < 0 || next >= list.length) return;
    const temp = list[current];
    list[current] = list[next];
    list[next] = temp;
    state.selectedIndex = next;
    render();
  }

  function reorderModule(from, to) {
    const list = modules();
    const start = Number(from);
    const end = Number(to);
    if (start === end || start < 0 || end < 0 || start >= list.length || end >= list.length) return;
    const [item] = list.splice(start, 1);
    list.splice(end, 0, item);
    state.selectedIndex = end;
    render();
  }

  function removeModule(index) {
    modules().splice(Number(index || 0), 1);
    state.selectedIndex = Math.min(Number(state.selectedIndex || 0), Math.max(modules().length - 1, 0));
    if (!modules().length) state.selectedIndex = -1;
    render();
  }

  function duplicateModule(index) {
    const list = modules();
    const source = list[Number(index || 0)];
    if (!source) return;
    const copy = clone(source);
    copy.id = idFor(copy.type || "module");
    copy.title = `${copy.title || moduleTypeLabel(copy.type)} 副本`;
    list.splice(Number(index || 0) + 1, 0, copy);
    state.selectedIndex = Number(index || 0) + 1;
    render();
  }

  function updateHomeField(field, value) {
    if (!["title", "subtitle"].includes(field)) return;
    home()[field] = value;
    render();
  }

  function updateHomeStyle(field, value) {
    if (!["background", "primary"].includes(field)) return;
    styleObject(home())[field] = value;
    render();
  }

  function updateTabbarStyle(field, value) {
    if (!["color", "selected_color", "background_color", "border_style"].includes(field)) return;
    tabbar().style[field] = value;
    render();
  }

  function updateTabbarItem(index, field, value) {
    if (!["text", "page_path", "icon", "selected_icon"].includes(field)) return;
    const item = tabbar().items[Number(index || 0)];
    if (!item) return;
    item[field] = value;
    render();
  }

  function updateModuleField(field, value, checked = false) {
    const module = selectedModule();
    if (!module) return;
    if (field === "enabled") module.enabled = checked ? 1 : 0;
    else if (field === "type") {
      const next = defaultModule(value);
      next.id = module.id;
      next.enabled = module.enabled;
      next.style = module.style || {};
      modules()[Number(state.selectedIndex || 0)] = next;
    } else if (["limit", "height", "columns", "interval", "active_tab"].includes(field)) {
      module[field] = Number(value || 0);
    } else {
      module[field] = value;
    }
    render();
  }

  function updateModuleStyle(field, value) {
    const module = selectedModule();
    if (!module) return;
    const style = styleObject(module);
    if (["margin_top", "margin_bottom", "radius"].includes(field)) style[field] = Math.min(Math.max(Number(value || 0), 0), field === "radius" ? 40 : 80);
    else if (field === "background") style[field] = value;
    render();
  }

  function addListItem(listName = "items", emptyType = "") {
    const module = selectedModule();
    if (!module) return;
    if (!Array.isArray(module[listName])) module[listName] = [];
    module[listName].push(defaultItem(emptyType || (listName === "products" ? "product" : "base")));
    render();
  }

  function removeListItem(listName = "items", index = 0) {
    const module = selectedModule();
    if (!module || !Array.isArray(module[listName])) return;
    module[listName].splice(Number(index || 0), 1);
    render();
  }

  function updateListItem(listName = "items", index = 0, field = "", value = "") {
    const module = selectedModule();
    if (!module || !Array.isArray(module[listName])) return;
    const item = module[listName][Number(index || 0)];
    if (!item) return;
    const numericFields = new Set(["x", "y", "w", "h"]);
    item[field] = numericFields.has(field) ? Number(value || 0) : value;
    render();
  }

  function resetTabbar() {
    state.design.tabbar = defaultTabbar();
    render();
  }

  function saveDraft() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.design));
    showToast("草稿已保存到本地浏览器");
  }

  function exportJson() {
    const blob = new Blob([JSON.stringify(state.design, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `sj-miniapp-design-${Date.now()}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function copyJson() {
    const text = JSON.stringify(state.design, null, 2);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      showToast("JSON 已复制");
      return;
    }
    showToast("当前浏览器不支持直接复制，请用导出 JSON");
  }

  function clearDesign() {
    home().modules = [];
    state.selectedIndex = -1;
    render();
  }

  function restoreDemo() {
    state.design = defaultDesign();
    state.selectedIndex = 0;
    state.inspectorTab = "content";
    render();
    showToast("已恢复示例组件");
  }

  function handleAction(action) {
    if (action === "save") saveDraft();
    else if (action === "export") exportJson();
    else if (action === "import") importInput.click();
    else if (action === "clear") clearDesign();
    else if (action === "demo") restoreDemo();
    else if (action === "copy-json") copyJson().catch(() => showToast("复制失败"));
  }

  function showToast(text) {
    toastNode.textContent = text;
    toastNode.classList.add("show");
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => toastNode.classList.remove("show"), 1800);
  }

  document.addEventListener("click", (event) => {
    const actionButton = event.target.closest("[data-designer-action]");
    if (actionButton) {
      event.preventDefault();
      handleAction(actionButton.dataset.designerAction || "");
      return;
    }
    const inspectorTab = event.target.closest("[data-miniapp-inspector-tab]");
    if (inspectorTab) {
      event.preventDefault();
      state.inspectorTab = inspectorTab.dataset.miniappInspectorTab === "style" ? "style" : "content";
      render();
      return;
    }
    if (event.target.closest("[data-miniapp-page-settings]")) {
      event.preventDefault();
      selectPageSettings();
      return;
    }
    if (event.target.closest("[data-miniapp-reset-tabbar]")) {
      event.preventDefault();
      resetTabbar();
      return;
    }
    const addModuleButton = event.target.closest("[data-miniapp-add-module]");
    if (addModuleButton) {
      event.preventDefault();
      addModule(addModuleButton.dataset.miniappAddModule || "nav");
      return;
    }
    const moveButton = event.target.closest("[data-miniapp-module-move]");
    if (moveButton) {
      event.preventDefault();
      moveModule(Number(moveButton.dataset.miniappIndex || state.selectedIndex || 0), Number(moveButton.dataset.miniappModuleMove || 0));
      return;
    }
    const duplicateButton = event.target.closest("[data-miniapp-module-duplicate]");
    if (duplicateButton) {
      event.preventDefault();
      duplicateModule(Number(duplicateButton.dataset.miniappIndex || state.selectedIndex || 0));
      return;
    }
    const removeButton = event.target.closest("[data-miniapp-module-remove]");
    if (removeButton) {
      event.preventDefault();
      removeModule(Number(removeButton.dataset.miniappIndex || state.selectedIndex || 0));
      return;
    }
    const selectButton = event.target.closest("[data-miniapp-select-module]");
    if (selectButton) {
      event.preventDefault();
      selectModule(Number(selectButton.dataset.miniappSelectModule || 0));
      return;
    }
    const addItemButton = event.target.closest("[data-miniapp-add-item]");
    if (addItemButton) {
      event.preventDefault();
      addListItem(addItemButton.dataset.listName || "items", addItemButton.dataset.emptyType || "");
      return;
    }
    const removeItemButton = event.target.closest("[data-miniapp-remove-item]");
    if (removeItemButton) {
      event.preventDefault();
      removeListItem(removeItemButton.dataset.listName || "items", Number(removeItemButton.dataset.miniappRemoveItem || 0));
    }
  });

  document.addEventListener("change", (event) => {
    const homeField = event.target.closest("[data-miniapp-home-field]");
    if (homeField) {
      updateHomeField(homeField.dataset.miniappHomeField || "", homeField.value);
      return;
    }
    const homeStyleField = event.target.closest("[data-miniapp-home-style-field]");
    if (homeStyleField) {
      updateHomeStyle(homeStyleField.dataset.miniappHomeStyleField || "", homeStyleField.value);
      return;
    }
    const tabbarStyleField = event.target.closest("[data-miniapp-tabbar-style-field]");
    if (tabbarStyleField) {
      updateTabbarStyle(tabbarStyleField.dataset.miniappTabbarStyleField || "", tabbarStyleField.value);
      return;
    }
    const tabbarField = event.target.closest("[data-miniapp-tabbar-field]");
    if (tabbarField) {
      const row = tabbarField.closest("[data-miniapp-tabbar-index]");
      updateTabbarItem(row ? Number(row.dataset.miniappTabbarIndex || 0) : 0, tabbarField.dataset.miniappTabbarField || "", tabbarField.value);
      return;
    }
    const moduleField = event.target.closest("[data-miniapp-module-field]");
    if (moduleField) {
      updateModuleField(moduleField.dataset.miniappModuleField || "", moduleField.value, moduleField.checked);
      return;
    }
    const moduleStyleField = event.target.closest("[data-miniapp-module-style-field]");
    if (moduleStyleField) {
      updateModuleStyle(moduleStyleField.dataset.miniappModuleStyleField || "", moduleStyleField.value);
      return;
    }
    const itemField = event.target.closest("[data-miniapp-item-field]");
    if (itemField) {
      const row = itemField.closest("[data-miniapp-item-index]");
      const listNameNode = itemField.closest("[data-list-name]");
      updateListItem(
        listNameNode ? listNameNode.dataset.listName || "items" : "items",
        row ? Number(row.dataset.miniappItemIndex || 0) : 0,
        itemField.dataset.miniappItemField || "",
        itemField.value
      );
    }
  });

  document.addEventListener("dragstart", (event) => {
    const node = event.target.closest("[data-drag-index]");
    if (!node) return;
    state.dragIndex = Number(node.dataset.dragIndex || 0);
    node.classList.add("dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(state.dragIndex));
  });

  document.addEventListener("dragend", (event) => {
    const node = event.target.closest("[data-drag-index]");
    if (node) node.classList.remove("dragging");
    state.dragIndex = null;
  });

  document.addEventListener("dragover", (event) => {
    if (event.target.closest("[data-drag-index]")) event.preventDefault();
  });

  document.addEventListener("drop", (event) => {
    const node = event.target.closest("[data-drag-index]");
    if (!node) return;
    event.preventDefault();
    const from = state.dragIndex ?? Number(event.dataTransfer.getData("text/plain") || 0);
    const to = Number(node.dataset.dragIndex || 0);
    reorderModule(from, to);
  });

  importInput.addEventListener("change", () => {
    const file = importInput.files && importInput.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        state.design = normalizeDesign(JSON.parse(String(reader.result || "{}")));
        state.selectedIndex = modules().length ? 0 : -1;
        state.inspectorTab = "content";
        render();
        showToast("JSON 已导入");
      } catch (err) {
        showToast("JSON 格式不正确");
      } finally {
        importInput.value = "";
      }
    };
    reader.readAsText(file, "utf-8");
  });

  setInterval(() => {
    if (document.activeElement && document.activeElement.closest(".settings")) return;
    state.tick += 1;
    render();
  }, 3500);

  render();
})();
