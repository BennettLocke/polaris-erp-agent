"""WebUI - Beijixing card workspace."""

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>肆计包装-北极星订单管理机器人</title>
<style>
* { box-sizing: border-box; }
:root {
  --bg: #f7f7f5;
  --paper: #ffffff;
  --ink: #171717;
  --muted: #74706a;
  --line: #e8e2d7;
  --line-strong: #d7cdbb;
  --gold: #b8892f;
  --gold-2: #d7ad55;
  --gold-soft: #fff6df;
  --black: #111111;
  --green: #16803c;
  --red: #c43d32;
  --blue: #2b5fb8;
  --shadow: 0 14px 34px rgba(20, 20, 20, .08);
  --shadow-soft: 0 8px 22px rgba(20, 20, 20, .06);
  --radius: 8px;
}
body {
  margin: 0;
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(255,255,255,.95), rgba(247,247,245,.96)),
    radial-gradient(circle at 8% 0, rgba(215,173,85,.14), transparent 30%);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  letter-spacing: 0;
}
button, input, select, textarea { font: inherit; }
button { cursor: pointer; }
.shell {
  width: min(1740px, 100%);
  margin: 0 auto;
  padding: 16px;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 14px;
  background: rgba(255,255,255,.92);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-soft);
  position: sticky;
  top: 10px;
  z-index: 20;
  backdrop-filter: blur(12px);
}
.brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
.logo {
  width: 38px; height: 38px; border-radius: 8px;
  display: grid; place-items: center;
  background: #111;
  color: var(--gold-2);
  box-shadow: inset 0 0 0 1px rgba(215,173,85,.38);
}
.brand h1 { margin: 0; font-size: 18px; line-height: 1.15; font-weight: 780; }
.brand p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
.top-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.status-pill {
  display: inline-flex; align-items: center; gap: 6px;
  height: 32px; padding: 0 11px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: #fff;
  color: #5f584e;
  font-size: 12px;
  white-space: nowrap;
}
.status-dot { width: 7px; height: 7px; border-radius: 99px; background: var(--green); box-shadow: 0 0 0 4px rgba(22,128,60,.1); }
.btn, .icon-btn {
  border: 1px solid var(--line-strong);
  background: #fff;
  color: var(--ink);
  border-radius: 7px;
  min-height: 34px;
  transition: .16s ease;
}
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 7px;
  padding: 0 12px;
  font-size: 13px;
}
.btn:hover, .icon-btn:hover { border-color: var(--gold); box-shadow: 0 0 0 3px rgba(184,137,47,.12); }
.btn.primary { background: #111; color: #fff; border-color: #111; }
.btn.gold { background: linear-gradient(180deg, #e2bd66, #b8892f); color: #17130b; border-color: #b8892f; font-weight: 720; }
.btn.danger { color: var(--red); border-color: #efb4ae; }
.btn.ghost { background: transparent; }
.icon-btn {
  width: 34px; height: 34px;
  display: inline-grid; place-items: center;
  padding: 0;
}
.layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 330px;
  gap: 14px;
  margin-top: 14px;
}
.stack { display: grid; gap: 14px; align-content: start; }
.panel {
  background: rgba(255,255,255,.96);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.panel-head {
  min-height: 48px;
  padding: 12px 13px;
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.panel-title { display: flex; align-items: center; gap: 8px; font-weight: 760; font-size: 14px; }
.panel-sub { color: var(--muted); font-size: 12px; margin-top: 3px; }
.panel-body { padding: 13px; }
.form-grid { display: grid; gap: 9px; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
label { display: block; color: var(--muted); font-size: 12px; margin-bottom: 5px; }
input, select, textarea {
  width: 100%;
  border: 1px solid var(--line-strong);
  border-radius: 7px;
  background: #fff;
  color: var(--ink);
  min-height: 36px;
  padding: 8px 10px;
  outline: none;
}
textarea { min-height: 72px; resize: vertical; }
input:focus, select:focus, textarea:focus { border-color: var(--gold); box-shadow: 0 0 0 3px rgba(184,137,47,.13); }
.hint { color: var(--muted); font-size: 12px; line-height: 1.5; }
.quick-list { display: flex; flex-wrap: wrap; gap: 7px; }
.quick-chip {
  border: 1px solid var(--line);
  background: #fff;
  color: #4f4637;
  min-height: 31px;
  padding: 0 9px;
  border-radius: 999px;
  font-size: 12px;
}
.quick-chip:hover { border-color: var(--gold); background: var(--gold-soft); }
.chat-panel { min-height: 655px; display: flex; flex-direction: column; }
.chat-body {
  flex: 1;
  min-height: 360px;
  max-height: 560px;
  overflow-y: auto;
  padding: 14px;
  background: linear-gradient(180deg, #fff, #fbfaf7);
}
.message { display: flex; margin-bottom: 12px; gap: 9px; }
.message.user { justify-content: flex-end; }
.bubble {
  max-width: min(780px, 84%);
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--shadow-soft);
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}
.message.user .bubble { background: #111; color: #fff; border-color: #111; }
.msg-meta { font-size: 11px; color: var(--muted); margin-bottom: 4px; }
.message.user .msg-meta { color: #d8d0bf; }
.composer {
  padding: 12px;
  border-top: 1px solid var(--line);
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 9px;
  background: #fff;
}
.composer textarea { min-height: 46px; max-height: 130px; }
.composer-actions { display: grid; grid-template-columns: auto auto; gap: 7px; align-content: end; }
.media-preview {
  display: none;
  margin: 0 12px 10px;
  padding: 9px;
  border: 1px dashed var(--line-strong);
  border-radius: 8px;
  color: var(--muted);
  font-size: 12px;
}
.media-preview img { display: block; max-width: 180px; max-height: 120px; border-radius: 7px; margin-top: 7px; border: 1px solid var(--line); }
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 10px; margin-bottom: 14px; }
.kpi {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow-soft);
  padding: 12px;
}
.kpi .label { color: var(--muted); font-size: 12px; }
.kpi .value { font-size: 22px; font-weight: 800; margin-top: 5px; }
.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.wide { grid-column: 1 / -1; }
.toolbar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.toolbar input, .toolbar select { width: auto; min-width: 150px; }
.list { display: grid; gap: 9px; }
.choices { display: grid; gap: 7px; max-height: 190px; overflow-y: auto; }
.choice {
  width: 100%;
  text-align: left;
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  padding: 9px;
}
.choice:hover { border-color: var(--gold); background: #fffaf0; }
.sale-lines { display: grid; gap: 8px; }
.line-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 74px 88px 34px;
  gap: 7px;
  align-items: end;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 9px;
}
.item {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 11px;
  box-shadow: var(--shadow-soft);
}
.item-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.item-title { font-weight: 760; line-height: 1.35; }
.item-sub { color: var(--muted); font-size: 12px; margin-top: 4px; }
.card-customer { font-size: 19px; font-weight: 820; line-height: 1.25; }
.card-no { color: var(--muted); font-size: 12px; margin-top: 4px; }
.card-total { color: var(--gold); font-size: 22px; font-weight: 760; text-align: right; white-space: nowrap; }
.card-count { color: var(--muted); font-size: 12px; margin-top: 4px; text-align: right; }
.product-lines { display: grid; gap: 6px; margin-top: 10px; padding: 9px; background: #faf9f6; border: 1px solid var(--line); border-radius: 8px; }
.product-row { display: grid; grid-template-columns: minmax(0, 1fr) 54px 82px; gap: 8px; align-items: center; font-size: 12px; }
.product-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 700; }
.product-qty { text-align: center; color: #39352f; font-weight: 700; }
.product-price { text-align: right; color: var(--gold); font-weight: 720; }
.image-strip { display: flex; gap: 8px; margin-top: 9px; overflow-x: auto; }
.thumb { width: 74px; height: 62px; border-radius: 7px; object-fit: cover; border: 1px solid var(--line); background: #f5f3ee; }
.status-line { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.tag {
  display: inline-flex; align-items: center; gap: 5px;
  min-height: 24px; padding: 0 8px;
  background: #faf8f3;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: #5d5447;
  font-size: 12px;
}
.tag.green { background: #ecfdf3; border-color: #c8efd7; color: var(--green); }
.tag.red { background: #fff0ee; border-color: #ffd0c8; color: var(--red); }
.tag.gold { background: var(--gold-soft); border-color: #f0d28a; color: #8a5d11; }
.tag.blue { background: #edf3ff; border-color: #ccdaf9; color: var(--blue); }
.tag.gray { background: #f2f2f2; border-color: #dedede; color: #666; }
.money { font-weight: 780; color: #7b5310; }
.swatch { width: 12px; height: 12px; border-radius: 99px; border: 1px solid rgba(0,0,0,.18); background: #ddd; }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; background: #fff; font-size: 13px; }
th, td { padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { background: #faf7ef; color: #5f584e; font-weight: 760; white-space: nowrap; }
tr:last-child td { border-bottom: none; }
.empty { color: var(--muted); text-align: center; padding: 20px 8px; border: 1px dashed var(--line-strong); border-radius: 8px; background: #fffdfa; }
.toast {
  position: fixed; right: 16px; bottom: 16px; z-index: 50;
  max-width: 360px;
  background: #111; color: #fff;
  border-radius: 8px;
  padding: 11px 13px;
  box-shadow: 0 18px 38px rgba(0,0,0,.22);
  display: none;
  line-height: 1.5;
}
.toast.show { display: block; }
.loading { opacity: .6; pointer-events: none; }
.mobile-tabs { display: none; }
.sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0,0,0,0); }
.icon-svg, [data-lucide] { width: 16px; height: 16px; stroke-width: 2; flex: 0 0 auto; }
a { color: var(--blue); }
.bubble img, .message-image { max-width: 260px; border: 1px solid var(--line); border-radius: 8px; display: block; margin-top: 8px; }
.md-table-wrap { overflow-x: auto; margin: 8px 0; border: 1px solid var(--line); border-radius: 8px; }
.md-table th, .md-table td { white-space: nowrap; }
.drawer-mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.24);
  z-index: 70;
  display: none;
}
.drawer-mask.open { display: block; }
.ai-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(430px, 92vw);
  z-index: 71;
  background: rgba(255,255,255,.98);
  border-left: 1px solid var(--line);
  box-shadow: -22px 0 54px rgba(20,20,20,.18);
  transform: translateX(104%);
  transition: transform .22s ease;
  display: flex;
  flex-direction: column;
}
.ai-drawer.open { transform: translateX(0); }
.drawer-head {
  padding: 16px;
  border-bottom: 1px solid var(--line);
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.drawer-title { font-size: 17px; font-weight: 820; }
.drawer-sub { color: var(--muted); font-size: 12px; margin-top: 3px; }
.drawer-body { padding: 14px; overflow-y: auto; display: grid; gap: 12px; }
.confirm-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  padding: 12px;
  box-shadow: var(--shadow-soft);
}
.kv { border: 1px solid var(--line); border-radius: 8px; overflow: hidden; margin-top: 10px; }
.kv-row { min-height: 34px; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 7px 9px; border-bottom: 1px solid var(--line); font-size: 12px; color: var(--muted); }
.kv-row:last-child { border-bottom: 0; }
.kv-value { color: var(--ink); font-weight: 760; text-align: right; }
@media (max-width: 1200px) {
  .layout { grid-template-columns: 280px 1fr; }
  .right-rail { grid-column: 1 / -1; grid-template-columns: repeat(2, minmax(0,1fr)); display: grid; }
}
@media (max-width: 820px) {
  .shell { padding: 10px; }
  .topbar { position: static; align-items: flex-start; }
  .top-actions { width: 100%; justify-content: flex-start; }
  .layout, .content-grid, .right-rail, .kpis { grid-template-columns: 1fr; }
  .two, .three { grid-template-columns: 1fr; }
  .composer { grid-template-columns: 1fr; }
  .composer-actions { grid-template-columns: 1fr 1fr; }
  .chat-panel { min-height: 560px; }
  .chat-body { max-height: 460px; }
  .toolbar input, .toolbar select { width: 100%; }
  .line-card { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="brand">
      <div class="logo"><i data-lucide="sparkles"></i></div>
      <div>
        <h1>肆计包装-北极星订单管理机器人</h1>
        <p>北极星 Web 工作台 · 开单、库存、工作流、商品和对话集中处理</p>
      </div>
    </div>
    <div class="top-actions">
      <span class="status-pill"><span class="status-dot"></span><span id="statusText">系统就绪</span></span>
      <button class="btn ghost" id="contextBtn"><i data-lucide="panel-right-open"></i>业务卡片</button>
      <button class="btn ghost" id="refreshAllBtn"><i data-lucide="refresh-cw"></i>刷新</button>
      <button class="btn primary" id="newSessionBtn"><i data-lucide="plus"></i>新会话</button>
    </div>
  </header>

  <main class="layout">
    <aside class="stack">
      <section class="panel">
        <div class="panel-head"><div><div class="panel-title"><i data-lucide="zap"></i>快捷操作</div><div class="panel-sub">所有按钮都直接调用 API</div></div></div>
        <div class="panel-body">
          <div class="quick-list" id="quickList">
            <button class="quick-chip" data-action="inventory">查库存</button>
            <button class="quick-chip" data-action="transfer">调货</button>
            <button class="quick-chip" data-action="purchase">进货</button>
            <button class="quick-chip" data-action="sale">创建销售单</button>
            <button class="quick-chip" data-action="workflow">创建工作流</button>
            <button class="quick-chip" data-action="print_latest">打印最新单</button>
            <button class="quick-chip" data-action="refresh">刷新全部</button>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><div class="panel-title"><i data-lucide="search"></i>库存查询</div></div>
        <div class="panel-body form-grid">
          <div><label>礼盒名称 / 规格 / 颜色</label><input id="quickInvKeyword" placeholder="例：见喜3两 红色"></div>
          <button class="btn gold" id="quickInvBtn"><i data-lucide="package-search"></i>查询库存</button>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><div class="panel-title"><i data-lucide="truck"></i>调货 / 进货</div></div>
        <div class="panel-body form-grid">
          <div><label>商品关键词</label><input id="moveKeyword" placeholder="例：茶派 黄色"></div>
          <button class="btn" id="moveProductSearchBtn"><i data-lucide="search"></i>搜索并选择商品</button>
          <div class="choices" id="moveProductChoices"></div>
          <div class="two">
            <div><label>数量</label><input id="moveQty" type="number" min="1" value="1"></div>
            <div><label>目标仓库</label><select id="moveWarehouse"><option value="1">自己店里</option><option value="2">百鑫仓库</option></select></div>
          </div>
          <div class="two">
            <button class="btn" id="transferBtn"><i data-lucide="shuffle"></i>百鑫调到店里</button>
            <button class="btn primary" id="purchaseBtn"><i data-lucide="archive-restore"></i>进货入库</button>
          </div>
          <div class="hint" id="moveSelectedHint">先搜索并选择商品，再调货或进货，避免误匹配。</div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><div class="panel-title"><i data-lucide="receipt-text"></i>快速开单</div></div>
        <div class="panel-body form-grid">
          <div><label>客户</label><input id="saleCustomer" placeholder="客户名称"></div>
          <button class="btn" id="saleCustomerSearchBtn"><i data-lucide="search"></i>搜索客户</button>
          <div class="choices" id="saleCustomerChoices"></div>
          <div><label>礼盒 / 商品</label><input id="saleProduct" placeholder="礼盒名称、规格、颜色"></div>
          <div class="two">
            <div><label>数量</label><input id="saleQty" type="number" min="1" value="1"></div>
            <div><label>仓库</label><select id="saleWarehouse"><option value="2">百鑫仓库</option><option value="1">自己店里</option></select></div>
          </div>
          <div class="two">
            <button class="btn" id="saleProductSearchBtn"><i data-lucide="search"></i>搜索商品</button>
            <button class="btn primary" id="saleAddLineBtn"><i data-lucide="plus"></i>加入明细</button>
          </div>
          <div class="choices" id="saleProductChoices"></div>
          <div class="sale-lines" id="saleLines"></div>
          <div class="item">
            <div class="item-top"><div><div class="item-title">销售单合计</div><div class="item-sub" id="saleSelectedCustomer">未选择客户</div></div><div class="money" id="saleTotal">¥0.00</div></div>
          </div>
          <div class="two">
            <button class="btn" id="saleClearBtn"><i data-lucide="eraser"></i>清空</button>
            <button class="btn gold" id="quickSaleBtn"><i data-lucide="send"></i>开销售单</button>
          </div>
        </div>
      </section>
    </aside>

    <section class="stack">
      <section class="panel chat-panel">
        <div class="panel-head">
          <div><div class="panel-title"><i data-lucide="bot"></i>北极星对话</div><div class="panel-sub">支持文字、图片上传、粘贴截图</div></div>
          <button class="icon-btn" id="clearChatBtn" title="清空显示"><i data-lucide="eraser"></i></button>
        </div>
        <div class="chat-body" id="chatBody"></div>
        <div class="media-preview" id="mediaPreview"></div>
        <div class="composer">
          <textarea id="messageInput" placeholder="直接说：查库存、开单、调货、进货、删除工作流、打印销售单..."></textarea>
          <div class="composer-actions">
            <label class="btn" for="imageInput"><i data-lucide="image-up"></i>图片</label>
            <input class="sr-only" type="file" id="imageInput" accept="image/*">
            <button class="btn primary" id="sendBtn"><i data-lucide="send-horizontal"></i>发送</button>
          </div>
        </div>
      </section>

      <section class="kpis">
        <div class="kpi"><div class="label">最近销售单</div><div class="value" id="kpiSales">-</div></div>
        <div class="kpi"><div class="label">工作流订单</div><div class="value" id="kpiWorkflow">-</div></div>
        <div class="kpi"><div class="label">库存结果</div><div class="value" id="kpiInventory">-</div></div>
        <div class="kpi"><div class="label">商品结果</div><div class="value" id="kpiProducts">-</div></div>
      </section>

      <section class="content-grid">
        <section class="panel">
          <div class="panel-head">
            <div><div class="panel-title"><i data-lucide="shopping-bag"></i>销售单</div><div class="panel-sub">最近销售单、搜索、打印</div></div>
          </div>
          <div class="panel-body">
            <div class="toolbar">
              <input id="salesKeyword" placeholder="客户 / 单号 / 商品">
              <button class="btn" id="salesSearchBtn"><i data-lucide="search"></i>搜索</button>
            </div>
            <div class="list" id="salesList" style="margin-top:10px"></div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div><div class="panel-title"><i data-lucide="warehouse"></i>库存</div><div class="panel-sub">分仓库、颜色、合计展示</div></div>
          </div>
          <div class="panel-body">
            <div class="toolbar">
              <input id="inventoryKeyword" placeholder="商品名称 / 颜色 / 规格">
              <label style="display:flex;align-items:center;gap:6px;margin:0;color:var(--muted);font-size:12px"><input id="onlyStock" type="checkbox" checked style="width:auto;min-height:auto">只看有库存</label>
              <button class="btn" id="inventorySearchBtn"><i data-lucide="search"></i>搜索</button>
            </div>
            <div class="list" id="inventoryList" style="margin-top:10px"></div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div><div class="panel-title"><i data-lucide="clipboard-list"></i>工作流订单</div><div class="panel-sub">查看、创建、删除、状态更新</div></div>
          </div>
          <div class="panel-body form-grid">
            <input id="wfId" type="hidden">
            <div class="three">
              <div><label>客户</label><input id="wfCustomer" placeholder="客户"></div>
              <div><label>礼盒</label><input id="wfGoods" placeholder="礼盒"></div>
              <div><label>数量</label><input id="wfQty" type="number" min="1" value="1"></div>
            </div>
            <div class="three">
              <div><label>颜色</label><input id="wfColor" placeholder="颜色"></div>
              <div><label>工艺</label><select id="wfPrint"><option value="0">无</option><option value="1">UV</option><option value="2">丝印</option></select></div>
              <div><label>类型</label><select id="wfType"><option value="0">普通</option><option value="1">加急</option></select></div>
            </div>
            <button class="btn gold" id="workflowCreateBtn"><i data-lucide="plus"></i>创建工作流订单</button>
            <div class="toolbar">
              <input id="workflowKeyword" placeholder="搜索工作流订单">
              <button class="btn" id="workflowSearchBtn"><i data-lucide="search"></i>搜索</button>
            </div>
            <div class="list" id="workflowList"></div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div><div class="panel-title"><i data-lucide="boxes"></i>商品管理</div><div class="panel-sub">搜索、上下架、删除、基础创建</div></div>
          </div>
          <div class="panel-body form-grid">
            <div class="toolbar">
              <input id="productKeyword" placeholder="商品关键词">
              <button class="btn" id="productSearchBtn"><i data-lucide="search"></i>搜索</button>
            </div>
            <input id="productId" type="hidden">
            <input id="productImageUrl" type="hidden">
            <div class="three">
              <div><label>商品名称</label><input id="productTitle" placeholder="新商品名称"></div>
              <div><label>规格/颜色</label><input id="productSpec" placeholder="规格或颜色"></div>
              <div><label>价格</label><input id="productPrice" type="number" step="0.01" placeholder="价格"></div>
            </div>
            <div class="toolbar">
              <label class="btn" for="productImageInput"><i data-lucide="image-up"></i>上传商品图</label>
              <input class="sr-only" type="file" id="productImageInput" accept="image/*">
              <button class="btn primary" id="productSaveBtn"><i data-lucide="save"></i>保存商品</button>
              <button class="btn" id="productResetBtn" type="button"><i data-lucide="eraser"></i>清空</button>
            </div>
            <div class="hint" id="productEditHint">可创建商品，也可在下方列表点“编辑”后保存。</div>
            <div class="list" id="productList"></div>
          </div>
        </section>
      </section>
    </section>

    <aside class="stack right-rail">
      <section class="panel">
        <div class="panel-head"><div class="panel-title"><i data-lucide="activity"></i>识别状态</div></div>
        <div class="panel-body">
          <div class="list" id="stateList">
            <div class="item"><div class="item-title">会话</div><div class="item-sub" id="sessionText"></div></div>
            <div class="item"><div class="item-title">最后动作</div><div class="item-sub" id="lastAction">等待操作</div></div>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><div class="panel-title"><i data-lucide="clock-3"></i>最近销售单</div></div>
        <div class="panel-body"><div class="list" id="recentSales"></div></div>
      </section>

      <section class="panel">
        <div class="panel-head"><div class="panel-title"><i data-lucide="workflow"></i>最近工作流</div></div>
        <div class="panel-body"><div class="list" id="recentWorkflow"></div></div>
      </section>
    </aside>
  </main>
</div>
<div class="drawer-mask" id="drawerMask"></div>
<aside class="ai-drawer" id="aiDrawer" aria-label="AI 业务确认">
  <div class="drawer-head">
    <div>
      <div class="drawer-title">当前对话生成的业务卡</div>
      <div class="drawer-sub">AI 给结果，人来确认。需要执行的动作都在这里核对。</div>
    </div>
    <button class="icon-btn" id="closeDrawerBtn" title="关闭"><i data-lucide="x"></i></button>
  </div>
  <div class="drawer-body" id="drawerBody"></div>
</aside>
<div class="toast" id="toast"></div>

<script>
const $ = (id) => document.getElementById(id);
const state = {
  sessionId: localStorage.getItem('sj_web_session_id') || newSessionId(),
  pendingFile: null,
  lastInventoryCards: [],
  lastProducts: [],
  saleCustomer: null,
  saleProduct: null,
  saleLines: [],
  moveProduct: null,
  moveProductResults: [],
  lastSalesCards: [],
  lastWorkflowCards: [],
  session: {},
  warehouses: []
};
localStorage.setItem('sj_web_session_id', state.sessionId);

function newSessionId() { return 'web_' + Date.now(); }
function iconRefresh() {
  if (window.lucide) {
    window.lucide.createIcons();
    return;
  }
  const icons = {
    sparkles: '<path d="M12 3l1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4L12 3z"/><path d="M5 14l.7 2.1L8 17l-2.3.9L5 20l-.7-2.1L2 17l2.3-.9L5 14z"/>',
    zap: '<path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
    'package-search': '<path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 4-1.8"/><path d="M21 7v6"/><circle cx="18" cy="18" r="3"/><path d="M20.2 20.2L22 22"/>',
    truck: '<path d="M3 6h11v10H3z"/><path d="M14 9h4l3 4v3h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
    shuffle: '<path d="M16 3h5v5"/><path d="M4 20l17-17"/><path d="M21 16v5h-5"/><path d="M15 15l6 6"/><path d="M4 4l5 5"/>',
    'archive-restore': '<path d="M3 7h18"/><path d="M5 7v12h14V7"/><path d="M9 15l3-3 3 3"/><path d="M12 12v6"/>',
    'receipt-text': '<path d="M5 2h14v20l-3-2-2 2-2-2-2 2-2-2-3 2V2z"/><path d="M8 7h8M8 11h8M8 15h5"/>',
    send: '<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/>',
    bot: '<rect x="5" y="7" width="14" height="12" rx="3"/><path d="M12 7V3"/><circle cx="9" cy="13" r="1"/><circle cx="15" cy="13" r="1"/>',
    eraser: '<path d="M7 21h10"/><path d="M3 15l9-9 7 7-8 8H7l-4-4v-2z"/>',
    'image-up': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 13l3-3 3 3 2-2 3 4"/><path d="M12 3v5"/><path d="M9 6l3-3 3 3"/>',
    'send-horizontal': '<path d="M3 12h18"/><path d="M15 6l6 6-6 6"/>',
    'shopping-bag': '<path d="M6 7h12l-1 14H7L6 7z"/><path d="M9 7a3 3 0 0 1 6 0"/>',
    printer: '<path d="M6 9V3h12v6"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 14h12v8H6z"/>',
    warehouse: '<path d="M3 21V8l9-5 9 5v13"/><path d="M7 21v-8h10v8"/><path d="M9 17h6"/>',
    'clipboard-list': '<path d="M9 3h6l1 3H8l1-3z"/><path d="M6 5H5a2 2 0 0 0-2 2v13h18V7a2 2 0 0 0-2-2h-1"/><path d="M8 11h8M8 15h8"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    boxes: '<path d="M3 7l6-3 6 3-6 3-6-3z"/><path d="M9 10v7l-6-3V7"/><path d="M15 7l6 3-6 3-6-3"/><path d="M15 13v7l6-3v-7"/>',
    save: '<path d="M5 3h12l2 2v16H5z"/><path d="M8 3v6h8"/><path d="M8 17h8"/>',
    activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    'clock-3': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5h4"/>',
    workflow: '<rect x="3" y="4" width="6" height="6" rx="1"/><rect x="15" y="14" width="6" height="6" rx="1"/><path d="M9 7h3a3 3 0 0 1 3 3v4"/>',
    'refresh-cw': '<path d="M21 12a9 9 0 0 1-15 6.7"/><path d="M3 12a9 9 0 0 1 15-6.7"/><path d="M18 3v5h-5"/><path d="M6 21v-5h5"/>',
    'panel-right-open': '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16"/><path d="M10 9l-3 3 3 3"/>',
    x: '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>',
    'trash-2': '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M6 6l1 16h10l1-16"/><path d="M10 11v6M14 11v6"/>'
  };
  document.querySelectorAll('i[data-lucide]').forEach((node) => {
    const name = node.getAttribute('data-lucide');
    node.outerHTML = '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (icons[name] || '<circle cx="12" cy="12" r="8"/>') + '</svg>';
  });
}
function setStatus(text) { $('statusText').textContent = text; $('lastAction').textContent = text; }
function toast(text, danger=false) {
  const el = $('toast');
  el.textContent = text;
  el.style.background = danger ? '#c43d32' : '#111';
  el.classList.add('show');
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (m) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}
function escapeJs(value) {
  return String(value ?? '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, ' ');
}
function money(v) {
  const n = Number(v || 0);
  if (!Number.isFinite(n)) return String(v || '0');
  return n.toFixed(2);
}
function normalizeList(res) {
  const data = res && res.data;
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.list)) return data.list;
  if (data && data.data && Array.isArray(data.data.list)) return data.data.list;
  if (res && Array.isArray(res.list)) return res.list;
  return [];
}
function api(path, options={}) {
  return fetch(path, {
    method: options.method || 'GET',
    headers: options.body instanceof FormData ? {} : {'Content-Type': 'application/json'},
    body: options.body instanceof FormData ? options.body : (options.body ? JSON.stringify(options.body) : undefined)
  }).then(async (res) => {
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch { data = {code: res.status, msg: text}; }
    if (!res.ok || (data.code && Number(data.code) !== 0)) {
      throw new Error(data.msg || ('HTTP ' + res.status));
    }
    return data;
  });
}
function query(params) {
  return Object.keys(params).filter(k => params[k] !== undefined && params[k] !== null && params[k] !== '')
    .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(params[k])).join('&');
}

function addMessage(role, text) {
  const el = document.createElement('div');
  el.className = 'message ' + (role === 'user' ? 'user' : 'bot');
  const name = role === 'user' ? '你' : '北极星';
  el.innerHTML = '<div class="bubble"><div class="msg-meta">' + name + '</div>' + renderMessage(text) + '</div>';
  $('chatBody').appendChild(el);
  $('chatBody').scrollTop = $('chatBody').scrollHeight;
}
function renderMessage(text) {
  const lines = String(text || '').split('\n');
  let html = '';
  for (let i = 0; i < lines.length; i++) {
    if (i + 1 < lines.length && lines[i].includes('|') && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[i+1])) {
      const table = [lines[i], lines[i+1]];
      i += 2;
      while (i < lines.length && lines[i].includes('|')) { table.push(lines[i]); i++; }
      i--;
      html += renderTable(table);
    } else {
      html += linkify(escapeHtml(lines[i])) + (i < lines.length - 1 ? '<br>' : '');
    }
  }
  return html;
}
function linkify(html) {
  return html.replace(/(https?:\/\/[^\s<]+|\/api\/images\/file\/[^\s<]+)/g, (url) => {
    const clean = url.replace(/[，。,.]+$/, '');
    const img = /\.(png|jpe?g|webp|bmp|gif)(\?.*)?$/i.test(clean) || clean.includes('/api/images/file/');
    return '<a href="' + clean + '" target="_blank" rel="noopener">' + clean + '</a>' + (img ? '<img class="message-image" src="' + clean + '">' : '');
  });
}
function splitRow(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(s => s.trim());
}
function renderTable(lines) {
  const headers = splitRow(lines[0]);
  const rows = lines.slice(2).map(splitRow).filter(Boolean);
  return '<div class="md-table-wrap"><table class="md-table"><thead><tr>' + headers.map(h => '<th>' + escapeHtml(h) + '</th>').join('') + '</tr></thead><tbody>' +
    rows.map(row => '<tr>' + headers.map((h, idx) => '<td>' + renderCell(h, row[idx] || '') + '</td>').join('') + '</tr>').join('') +
    '</tbody></table></div>';
}
function renderCell(header, value) {
  if (String(header).includes('颜色')) {
    const css = colorCss(value);
    return '<span class="tag">' + (css ? '<span class="swatch" style="background:' + css + '"></span>' : '') + escapeHtml(value) + '</span>';
  }
  return escapeHtml(value);
}
function colorCss(value) {
  const text = String(value || '').trim();
  const map = {'红色':'#d92d20','黄色':'#f4c430','金色':'#c69214','橙色':'#f97316','蓝色':'#2563eb','绿色':'#16a34a','橄榄绿':'#708238','咖色':'#7a4a28','深咖色':'#4b2e1f','古铜色':'#8c6239','黑色':'#111','白色':'#fff','银色':'#c7c9cc','灰色':'#8a8f98','香槟金':'#d8bd82'};
  return map[text] || '';
}
function pendingTitle(session = state.session) {
  const action = session.pending_action || '';
  const intent = session.pending_intent || '';
  if (action.includes('transfer')) return '调货确认';
  if (action.includes('purchase')) return '进货确认';
  if (action.includes('sales') || intent.includes('sales')) return '销售单确认';
  if (action.includes('workflow') || intent.includes('workflow')) return '订单确认';
  if (action.includes('product') || intent.includes('product')) return '商品确认';
  return session.has_pending ? '等待确认' : '业务卡片';
}
function readableKey(key) {
  const map = {
    customer_name: '客户', customer: '客户', sales_id: '销售单ID', sales_ids: '销售单',
    product_name: '商品', goods_name: '商品', title: '商品', color: '颜色', goods_color: '颜色',
    quantity: '数量', qty: '数量', order_quantity: '数量', price: '价格', total_price: '金额',
    out_warehouse_name: '调出仓库', enter_warehouse_name: '调入仓库', warehouse_name: '仓库',
    note: '备注', action: '动作', status: '状态'
  };
  return map[key] || key.replace(/_/g, ' ');
}
function flattenRows(obj, prefix='') {
  if (!obj || typeof obj !== 'object') return [];
  const rows = [];
  Object.keys(obj).forEach(key => {
    const value = obj[key];
    if (value === undefined || value === null || value === '') return;
    const label = prefix ? prefix + ' - ' + readableKey(key) : readableKey(key);
    if (Array.isArray(value)) {
      if (value.length && typeof value[0] === 'object') {
        value.slice(0, 6).forEach((item, idx) => rows.push(...flattenRows(item, label + (idx + 1))));
      } else {
        rows.push([label, value.join('、')]);
      }
    } else if (typeof value === 'object') {
      rows.push(...flattenRows(value, label));
    } else {
      rows.push([label, value]);
    }
  });
  return rows;
}
function kvRows(rows) {
  return '<div class="kv">' + rows.map(row => '<div class="kv-row"><span>' + escapeHtml(row[0]) + '</span><strong class="kv-value">' + escapeHtml(row[1]) + '</strong></div>').join('') + '</div>';
}
function renderBusinessContext() {
  const body = $('drawerBody');
  if (!body) return;
  const session = state.session || {};
  const data = session.state || session.last_extraction || {};
  let rows = flattenRows(data).slice(0, 18);
  let html = '';
  if (session.has_pending) {
    html += '<section class="confirm-card"><div class="item-top"><div><div class="item-title">' + escapeHtml(pendingTitle(session)) + '</div><div class="item-sub">请核对后确认，或回到对话补充修改。</div></div><span class="tag gold">待确认</span></div>';
    html += rows.length ? kvRows(rows) : '<div class="empty">这次确认没有结构化字段，按聊天内容核对即可。</div>';
    html += '<div class="toolbar" style="margin-top:12px"><button class="btn primary" onclick="confirmBusinessCard()">确认执行</button><button class="btn" onclick="editBusinessCard()">修改</button><button class="btn danger" onclick="cancelBusinessCard()">取消</button></div></section>';
  } else if (rows.length) {
    html += '<section class="confirm-card"><div class="item-title">最近识别结果</div>' + kvRows(rows) + '</section>';
  }
  if (!html) {
    html = '<div class="empty">暂无业务卡。你在左侧对话里开单、调货、识别图片后，这里会出现核对卡片。</div>';
  }
  body.innerHTML = html;
  iconRefresh();
}
function openDrawer() {
  renderBusinessContext();
  $('drawerMask').classList.add('open');
  $('aiDrawer').classList.add('open');
}
function closeDrawer() {
  $('drawerMask').classList.remove('open');
  $('aiDrawer').classList.remove('open');
}
function confirmBusinessCard() { closeDrawer(); sendChat('确认'); }
function cancelBusinessCard() { closeDrawer(); sendChat('取消'); }
function editBusinessCard() {
  closeDrawer();
  $('messageInput').value = '修改：';
  $('messageInput').focus();
}

async function sendChat(text) {
  const message = (text ?? $('messageInput').value).trim();
  if (!message && !state.pendingFile) return;
  if (message) addMessage('user', message);
  $('messageInput').value = '';
  setBusy('sendBtn', true);
  try {
    if (state.pendingFile) {
      await uploadImage(state.pendingFile);
      state.pendingFile = null;
      clearPreview();
    }
    if (message) {
      setStatus('北极星思考中');
      const res = await api('/api/agent/chat', {method:'POST', body:{message, session_id: state.sessionId, user_id:'web_user'}});
      const data = res.data || {};
      state.session = data.session || {};
      addMessage('bot', data.response ? data.response : '已处理');
      renderBusinessContext();
      if (state.session && state.session.has_pending) openDrawer();
      setStatus('对话完成');
    }
    refreshLight();
  } catch (err) {
    addMessage('bot', '处理失败：' + err.message);
    toast(err.message, true);
    setStatus('处理失败');
  } finally {
    setBusy('sendBtn', false);
  }
}
async function uploadImage(file) {
  addMessage('user', '上传图片：' + (file.name || '截图'));
  const form = new FormData();
  form.append('image', file, file.name || ('paste_' + Date.now() + '.png'));
  form.append('session_id', state.sessionId);
  setStatus('图片识别中');
  const res = await api('/api/images/upload', {method:'POST', body: form});
  const data = res.data || {};
  state.session = data.session || {};
  addMessage('bot', data.response ? data.response : '图片已识别');
  renderBusinessContext();
  if (state.session && state.session.has_pending) openDrawer();
}
function setBusy(id, yes) { const el = $(id); if (el) el.classList.toggle('loading', !!yes); }
function clearPreview() { $('mediaPreview').style.display = 'none'; $('mediaPreview').innerHTML = ''; $('imageInput').value = ''; }
function showPreview(file) {
  const url = URL.createObjectURL(file);
  $('mediaPreview').style.display = 'block';
  $('mediaPreview').innerHTML = '已选择图片，发送时会自动识别。<img src="' + url + '">';
}

async function loadSales() {
  const keyword = $('salesKeyword').value.trim();
  const res = await api('/api/sales/cards?' + query({keyword, page_size: 8}));
  const list = normalizeList(res);
  state.lastSalesCards = list;
  $('kpiSales').textContent = list.length;
  renderSales(list, $('salesList'));
  renderSales(list.slice(0, 5), $('recentSales'), true);
}
function renderSales(list, target, compact=false) {
  target.innerHTML = list.length ? list.map(card => {
    const id = Number(card.id || 0);
    const rows = (card.products || []).slice(0, compact ? 1 : 4);
    const productHtml = rows.length ? '<div class="product-lines">' + rows.map(p => {
      const qty = p.quantity ?? p.buy_number ?? p.num ?? '';
      return '<div class="product-row"><span class="product-name">' + escapeHtml([p.title, p.spec].filter(Boolean).join(' ')) + '</span><span class="product-qty">x' + escapeHtml(qty || '-') + '</span><span class="product-price">¥' + money(p.total_price || (Number(p.price || 0) * Number(qty || 0))) + '</span></div>';
    }).join('') + '</div>' : '<div class="item-sub">' + escapeHtml(card.product_summary || '无明细') + '</div>';
    const count = card.buy_number_count || rows.reduce((sum, p) => sum + Number(p.quantity ?? p.buy_number ?? 0), 0);
    const actions = compact
      ? '<button class="btn" onclick="printSales(' + id + ')"><i data-lucide="printer"></i>打印</button><button class="btn" onclick="editSales(' + id + ')">修改</button>'
      : '<button class="btn primary" onclick="printSales(' + id + ')"><i data-lucide="printer"></i>打印</button><button class="btn" onclick="editSales(' + id + ')">修改</button><button class="btn danger" onclick="deleteSales(' + id + ')"><i data-lucide="trash-2"></i>删除</button>';
    return '<div class="item"><div class="item-top"><div><div class="card-customer">' + escapeHtml(card.customer_name || '客户') + '</div><div class="card-no">' + escapeHtml(card.sales_no || ('#' + id)) + '</div></div><div><div class="card-total">¥' + money(card.total_price || card.price) + '</div><div class="card-count">共 ' + escapeHtml(count || 0) + ' 件</div></div></div><div class="tags"><span class="tag">' + escapeHtml(card.status_text || '销售单') + '</span><span class="tag gray">' + escapeHtml(card.date || card.date_text || card.add_time || '') + '</span></div>' + productHtml + '<div class="toolbar" style="margin-top:12px">' + actions + '</div></div>';
  }).join('') : '<div class="empty">暂无销售单</div>';
  iconRefresh();
}
async function printSales(id) {
  if (!id) return toast('缺少销售单 ID', true);
  await api('/api/sales/' + id + '/print-task', {method:'POST', body:{}});
  toast('已创建打印任务');
}
async function deleteSales(id) {
  if (!id || !confirm('确定删除这个销售单？删除后会按系统规则回滚库存。')) return;
  await api('/api/sales/' + id, {method:'DELETE'});
  toast('销售单已删除');
  loadSales();
}
function editSales(id) {
  if (!id) return;
  sendChat('修改销售单 ' + id);
}
async function printLatestSales() {
  if (!state.lastSalesCards.length) await loadSales();
  const card = state.lastSalesCards[0];
  if (!card || !card.id) return toast('没有可打印的销售单', true);
  await printSales(card.id);
}

async function loadInventory(keywordOverride) {
  const keyword = (keywordOverride ?? $('inventoryKeyword').value).trim();
  const only = $('onlyStock').checked ? 1 : 0;
  const res = await api('/api/inventory/cards?' + query({keyword, only_in_stock: only, limit: 18}));
  const list = normalizeList(res);
  state.lastInventoryCards = list;
  $('kpiInventory').textContent = list.length;
  renderInventory(list);
}
function renderInventory(list) {
  $('inventoryList').innerHTML = list.length ? list.map(card => {
    const colors = card.colors || [];
    const total = card.total_stock ?? card.total_inventory ?? colors.reduce((n, c) => n + Number(c.total_stock || 0), 0);
    const rows = colors.length ? colors : [{color: card.spec || card.color || '默认', total_stock: total, warehouses: card.warehouses || {}}];
    const whHtml = '<div class="table-wrap" style="margin-top:9px"><table><thead><tr><th>颜色</th><th>百鑫仓库</th><th>店里仓库</th><th>合计</th></tr></thead><tbody>' + rows.map(c => {
      const wh = c.warehouses || {};
      const bx = wh['百鑫仓库'] ?? wh.baixin ?? wh['1'] ?? 0;
      const shop = wh['店里仓库'] ?? wh.shop ?? wh['2'] ?? 0;
      const totalColor = c.total_stock ?? (Number(bx || 0) + Number(shop || 0));
      return '<tr><td>' + (colorCss(c.color) ? '<span class="swatch" style="background:' + colorCss(c.color) + '"></span>' : '') + escapeHtml(c.color || '默认') + '</td><td>' + escapeHtml(bx) + '</td><td>' + escapeHtml(shop) + '</td><td><b>' + escapeHtml(totalColor) + '</b></td></tr>';
    }).join('') + '</tbody></table></div>';
    const firstColor = rows[0] && rows[0].color ? rows[0].color : '';
    return '<div class="item"><div class="item-top"><div><div class="item-title">' + escapeHtml(card.title || card.product_name || '') + '</div><div class="item-sub">' + escapeHtml(card.piece_text || card.simple_desc || card.desc || '') + '</div></div><div><div class="card-total">' + escapeHtml(total) + '</div><div class="card-count">库存</div></div></div><div class="tags"><span class="tag">ID ' + escapeHtml(card.product_id || card.id || '') + '</span><span class="tag">' + escapeHtml(card.status_text || '库存') + '</span></div>' + whHtml + '<div class="toolbar" style="margin-top:12px"><button class="btn" onclick="prepareInventoryAction(\'' + escapeJs(card.title || card.product_name || '') + '\',\'' + escapeJs(firstColor) + '\',\'transfer\')">调货</button><button class="btn" onclick="prepareInventoryAction(\'' + escapeJs(card.title || card.product_name || '') + '\',\'' + escapeJs(firstColor) + '\',\'purchase\')">进货</button></div></div>';
  }).join('') : '<div class="empty">没有库存结果</div>';
  iconRefresh();
}
function prepareInventoryAction(title, color, type) {
  $('moveKeyword').value = [title, color].filter(Boolean).join(' ');
  state.moveProduct = null;
  $('moveSelectedHint').textContent = '已带入库存商品，请点“搜索商品”确认后再' + (type === 'purchase' ? '进货' : '调货') + '。';
  $('moveKeyword').focus();
  toast('已带入商品到调货/进货卡片');
}
async function firstProductByKeyword(keyword) {
  if (!keyword) throw new Error('请输入商品关键词');
  const inv = await api('/api/inventory/cards?' + query({keyword, only_in_stock: 0, limit: 1}));
  const invList = normalizeList(inv);
  if (invList.length && (invList[0].product_id || invList[0].id)) return invList[0];
  const prod = await api('/api/product/search?' + query({keyword}));
  const prodList = normalizeList(prod);
  if (prodList.length) return prodList[0];
  throw new Error('没有匹配到商品');
}
async function searchMoveProducts() {
  const keyword = $('moveKeyword').value.trim();
  if (!keyword) return toast('请输入商品关键词', true);
  const res = await api('/api/product/search?' + query({keyword}));
  const list = normalizeList(res);
  state.moveProductResults = list;
  $('moveProductChoices').innerHTML = list.length ? list.slice(0, 10).map(p => {
    const id = p.id || p.product_id;
    return '<button class="choice" onclick="selectMoveProduct(' + Number(id || 0) + ')"><div class="item-title">' + escapeHtml(p.title || p.name || '') + '</div><div class="item-sub">' + escapeHtml(p.spec || '') + ' · ID ' + escapeHtml(id || '') + ' · ¥' + money(p.price || p.min_price || 0) + '</div></button>';
  }).join('') : '<div class="empty">没有匹配到商品</div>';
  if (list.length === 1) selectMoveProduct(list[0].id || list[0].product_id);
}
function selectMoveProduct(id) {
  const product = (state.moveProductResults || []).find(p => Number(p.id || p.product_id) === Number(id));
  if (!product) return toast('没有找到商品', true);
  state.moveProduct = product;
  $('moveKeyword').value = [product.title || product.name || '', product.spec || ''].filter(Boolean).join(' ');
  $('moveSelectedHint').textContent = '已选择商品：' + $('moveKeyword').value + '（ID ' + id + '）';
  $('moveProductChoices').innerHTML = '';
}
async function transferInventory() {
  const keyword = $('moveKeyword').value.trim();
  const qty = Number($('moveQty').value || 0);
  if (!state.moveProduct) await searchMoveProducts();
  const product = state.moveProduct;
  if (!product) return toast('请先选择商品', true);
  await api('/api/inventory/transfer', {method:'POST', body:{product_id: product.product_id || product.id, unit_id: product.unit_id || 1, quantity: qty, out_warehouse_id: 2, enter_warehouse_id: 1, color: product.spec || product.color || ''}});
  toast('调货已提交');
  loadInventory(keyword);
}
async function purchaseInventory() {
  const keyword = $('moveKeyword').value.trim();
  const qty = Number($('moveQty').value || 0);
  if (!state.moveProduct) await searchMoveProducts();
  const product = state.moveProduct;
  if (!product) return toast('请先选择商品', true);
  await api('/api/inventory/purchase', {method:'POST', body:{product_id: product.product_id || product.id, unit_id: product.unit_id || 1, quantity: qty, warehouse_id: Number($('moveWarehouse').value || 2), color: product.spec || product.color || ''}});
  toast('进货已提交');
  loadInventory(keyword);
}

async function searchSaleCustomers() {
  const keyword = $('saleCustomer').value.trim();
  if (!keyword) return toast('请输入客户名称', true);
  const list = normalizeList(await api('/api/customer/list?' + query({keyword})));
  $('saleCustomerChoices').innerHTML = list.length ? list.slice(0, 8).map(c => '<button class="choice" onclick="selectSaleCustomer(' + Number(c.id || 0) + ',\'' + escapeJs(c.name || c.customer_name || '') + '\')"><div class="item-title">' + escapeHtml(c.name || c.customer_name || '') + '</div><div class="item-sub">客户ID ' + escapeHtml(c.id || '') + '</div></button>').join('') : '<div class="empty">没有匹配到客户</div>';
  if (list.length === 1) selectSaleCustomer(list[0].id, list[0].name || list[0].customer_name || '');
}
function selectSaleCustomer(id, name) {
  state.saleCustomer = {id: Number(id), name};
  $('saleCustomer').value = name;
  $('saleSelectedCustomer').textContent = '客户：' + name + '（ID ' + id + '）';
  $('saleCustomerChoices').innerHTML = '';
}
async function searchSaleProducts() {
  const keyword = $('saleProduct').value.trim();
  if (!keyword) return toast('请输入商品关键词', true);
  const list = normalizeList(await api('/api/product/search?' + query({keyword})));
  $('saleProductChoices').innerHTML = list.length ? list.slice(0, 10).map(p => {
    const id = p.id || p.product_id;
    return '<button class="choice" onclick="selectSaleProduct(' + Number(id || 0) + ')"><div class="item-title">' + escapeHtml(p.title || p.name || '') + '</div><div class="item-sub">' + escapeHtml(p.spec || '') + ' · ID ' + escapeHtml(id || '') + ' · ¥' + money(p.price || p.min_price || 0) + '</div></button>';
  }).join('') : '<div class="empty">没有匹配到商品</div>';
  state.saleProductResults = list;
  if (list.length === 1) selectSaleProduct(list[0].id || list[0].product_id);
}
async function selectSaleProduct(id) {
  const product = (state.saleProductResults || []).find(p => Number(p.id || p.product_id) === Number(id));
  if (!product) return toast('没有找到商品', true);
  state.saleProduct = product;
  $('saleProduct').value = [product.title || product.name || '', product.spec || ''].filter(Boolean).join(' ');
  $('saleProductChoices').innerHTML = '';
  if (state.saleCustomer && state.saleCustomer.id) {
    try {
      const priceRes = await api('/api/customer/price?' + query({customer_id: state.saleCustomer.id, product_id: id}));
      const price = priceRes.data && priceRes.data.price;
      if (price) product.price = price;
    } catch (e) {}
  }
}
async function addSaleLine() {
  if (!state.saleProduct) await searchSaleProducts();
  const p = state.saleProduct;
  if (!p) return;
  const qty = Number($('saleQty').value || 0);
  if (qty <= 0) return toast('请输入数量', true);
  const id = p.id || p.product_id;
  const existing = state.saleLines.find(line => Number(line.product_id) === Number(id));
  if (existing) {
    existing.buy_number += qty;
  } else {
    state.saleLines.push({
      product_id: Number(id),
      unit_id: Number(p.unit_id || 1),
      title: p.title || p.name || '',
      spec: p.spec || '',
      buy_number: qty,
      price: Number(p.price || p.min_price || p.retail_price || 0),
      warehouse_id: Number($('saleWarehouse').value || 2)
    });
  }
  state.saleProduct = null;
  $('saleProduct').value = '';
  renderSaleLines();
}
function renderSaleLines() {
  $('saleLines').innerHTML = state.saleLines.length ? state.saleLines.map((line, idx) => '<div class="line-card"><div><div class="item-title">' + escapeHtml(line.title) + '</div><div class="item-sub">' + escapeHtml(line.spec || '') + ' · ID ' + escapeHtml(line.product_id) + '</div></div><div><label>数量</label><input type="number" min="1" value="' + escapeHtml(line.buy_number) + '" onchange="updateSaleLine(' + idx + ',\'buy_number\',this.value)"></div><div><label>单价</label><input type="number" step="0.01" value="' + escapeHtml(line.price) + '" onchange="updateSaleLine(' + idx + ',\'price\',this.value)"></div><button class="icon-btn" onclick="removeSaleLine(' + idx + ')"><i data-lucide="trash-2"></i></button></div>').join('') : '<div class="empty">还没有销售明细，先搜索商品并加入明细。</div>';
  const total = state.saleLines.reduce((sum, line) => sum + Number(line.buy_number || 0) * Number(line.price || 0), 0);
  $('saleTotal').textContent = '¥' + money(total);
  iconRefresh();
}
function updateSaleLine(idx, field, value) {
  if (!state.saleLines[idx]) return;
  state.saleLines[idx][field] = Number(value || 0);
  renderSaleLines();
}
function removeSaleLine(idx) {
  state.saleLines.splice(idx, 1);
  renderSaleLines();
}
function clearSaleForm() {
  state.saleCustomer = null;
  state.saleProduct = null;
  state.saleLines = [];
  $('saleCustomer').value = '';
  $('saleProduct').value = '';
  $('saleQty').value = 1;
  $('saleCustomerChoices').innerHTML = '';
  $('saleProductChoices').innerHTML = '';
  $('saleSelectedCustomer').textContent = '未选择客户';
  renderSaleLines();
}
async function quickSale() {
  if (!state.saleCustomer) await searchSaleCustomers();
  if (!state.saleCustomer) return toast('请先选择客户', true);
  if (!state.saleLines.length) await addSaleLine();
  if (!state.saleLines.length) return toast('请先加入商品明细', true);
  const warehouseId = Number($('saleWarehouse').value || 2);
  await api('/api/sales/add', {method:'POST', body:{customer_id: state.saleCustomer.id, warehouse_id: warehouseId, products: state.saleLines.map(line => ({product_id: line.product_id, unit_id: line.unit_id || 1, warehouse_id: warehouseId, buy_number: line.buy_number, price: line.price}))}});
  toast('销售单已创建');
  clearSaleForm();
  loadSales();
}

async function loadWorkflow() {
  const keyword = $('workflowKeyword').value.trim();
  const res = await api('/api/workflow/orders?' + query({keyword, page_size: 8}));
  const list = normalizeList(res);
  state.lastWorkflowCards = list;
  $('kpiWorkflow').textContent = list.length;
  renderWorkflow(list, $('workflowList'));
  renderWorkflow(list.slice(0, 5), $('recentWorkflow'), true);
}
function renderWorkflow(list, target, compact=false) {
  target.innerHTML = list.length ? list.map(row => {
    const id = row.id || row.order_id;
    const made = Number(row.is_made || 0) === 1;
    const delivered = Number(row.is_delivered || 0) === 1;
    const screen = Number(row.is_screen_print || 0) === 1;
    const images = Array.isArray(row.order_images) ? row.order_images : (row.order_images ? String(row.order_images).split(',') : []);
    const imageHtml = images.length && !compact ? '<div class="image-strip">' + images.slice(0, 4).map(url => '<img class="thumb" src="' + escapeHtml(url) + '" alt="">').join('') + '</div>' : '';
    return '<div class="item"><div class="item-top"><div><div class="card-customer">' + escapeHtml(row.customer_name || row.customer || '客户') + '</div><div class="card-no">' + escapeHtml(row.customer_phone || '') + ' #' + escapeHtml(id || '') + '</div></div><div><div class="card-total">' + escapeHtml(row.order_quantity || row.quantity || '-') + '</div><div class="card-count">件</div></div></div><div class="product-lines"><div class="product-row"><span class="product-name">' + escapeHtml(row.goods_name || row.title || '') + '</span><span>' + escapeHtml(row.goods_color || row.color || '') + '</span></div></div><div class="tags"><span class="tag">' + escapeHtml(row.status_text || row.status || '订单') + '</span><span class="tag ' + (made ? 'green' : 'gray') + '">' + (made ? '已制作' : '未制作') + '</span><span class="tag ' + (delivered ? 'green' : 'gray') + '">' + (delivered ? '已配送' : '未配送') + '</span>' + (screen ? '<span class="tag gold">丝印</span>' : '') + '</div><div class="status-line">' + escapeHtml(row.order_time_text || row.date_text || '') + '</div>' + imageHtml + (compact ? '' : '<div class="toolbar" style="margin-top:12px"><button class="btn" onclick="editWorkflow(' + Number(id || 0) + ')">编辑</button><button class="btn" onclick="markWorkflow(' + Number(id || 0) + ',\'is_made\')">' + (made ? '取消制作' : '制作完成') + '</button><button class="btn" onclick="markWorkflow(' + Number(id || 0) + ',\'is_delivered\')">' + (delivered ? '取消配送' : '完成配送') + '</button><button class="btn danger" onclick="deleteWorkflow(' + Number(id || 0) + ')"><i data-lucide="trash-2"></i>删除</button></div>') + '</div>';
  }).join('') : '<div class="empty">暂无工作流订单</div>';
  iconRefresh();
}
async function createWorkflow() {
  const body = {
    id: $('wfId') ? $('wfId').value || undefined : undefined,
    customer_name: $('wfCustomer').value.trim(),
    goods_name: $('wfGoods').value.trim(),
    color: $('wfColor').value.trim(),
    order_quantity: Number($('wfQty').value || 0),
    is_screen_print: Number($('wfPrint').value || 0),
    order_type: Number($('wfType').value || 0)
  };
  if (!body.customer_name || !body.goods_name || body.order_quantity <= 0) return toast('客户、礼盒和数量必填', true);
  await api('/api/workflow/orders', {method:'POST', body});
  toast('工作流订单已创建');
  clearWorkflowForm();
  loadWorkflow();
}
function editWorkflow(id) {
  const row = state.lastWorkflowCards.find(item => Number(item.id || item.order_id) === Number(id));
  if (!row) return toast('没有找到工作流订单', true);
  if (!$('wfId')) {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.id = 'wfId';
    $('workflowList').parentNode.appendChild(input);
  }
  $('wfId').value = row.id || row.order_id || '';
  $('wfCustomer').value = row.customer_name || row.customer || '';
  $('wfGoods').value = row.goods_name || row.title || '';
  $('wfColor').value = row.goods_color || row.color || '';
  $('wfQty').value = row.order_quantity || row.quantity || 1;
  $('wfPrint').value = row.is_screen_print || 0;
  $('wfType').value = row.order_type || 0;
  toast('已载入工作流订单，可修改后保存');
}
function clearWorkflowForm() {
  if ($('wfId')) $('wfId').value = '';
  $('wfCustomer').value = '';
  $('wfGoods').value = '';
  $('wfColor').value = '';
  $('wfQty').value = 1;
  $('wfPrint').value = 0;
  $('wfType').value = 0;
}
async function markWorkflow(id, field) {
  if (!id) return;
  const row = state.lastWorkflowCards.find(item => Number(item.id || item.order_id) === Number(id));
  const value = row && Number(row[field] || 0) === 1 ? 0 : 1;
  await api('/api/workflow/orders/' + id + '/status', {method:'POST', body:{field, value}});
  toast('状态已更新');
  loadWorkflow();
}
async function deleteWorkflow(id) {
  if (!id || !confirm('确定删除这个工作流订单？')) return;
  await api('/api/workflow/orders/' + id, {method:'DELETE'});
  toast('工作流订单已删除');
  loadWorkflow();
}

async function loadProducts() {
  const keyword = $('productKeyword').value.trim();
  const res = await api('/api/product/list?' + query({keyword, page_size: 12, group: 1}));
  let list = normalizeList(res);
  if (!list.length && res.data && Array.isArray(res.data)) list = res.data;
  state.lastProducts = list;
  $('kpiProducts').textContent = list.length;
  renderProducts(list);
}
function renderProducts(list) {
  $('productList').innerHTML = list.length ? list.map(p => {
    const id = p.id || p.product_id;
    const images = p.main_images || p.images || p.image || '';
    const firstImage = Array.isArray(images) ? images[0] : String(images || '').split(',')[0];
    const shelves = Number(p.is_shelves ?? p.shelves ?? p.is_home_recommended ?? 0) === 1;
    const status = p.status_text || p.is_enable_text || p.status || '商品';
    const imgHtml = firstImage ? '<img class="thumb" src="' + escapeHtml(firstImage) + '" alt="">' : '';
    return '<div class="item"><div class="item-top"><div style="display:flex;gap:10px;align-items:center">' + imgHtml + '<div><div class="item-title">' + escapeHtml(p.title || p.name || '') + '</div><div class="item-sub">' + escapeHtml(p.spec || p.simple_desc || p.desc || '') + '</div></div></div><div><div class="card-total">¥' + money(p.price || p.min_price || 0) + '</div><div class="card-count">' + escapeHtml(p.unit || p.unit_name || '') + '</div></div></div><div class="tags"><span class="tag">ID ' + escapeHtml(id || '') + '</span><span class="tag">' + escapeHtml(p.coding || '无编码') + '</span><span class="tag ' + (shelves ? 'green' : 'gray') + '">' + (shelves ? '上架商城' : '未上架') + '</span><span class="tag">' + escapeHtml(status) + '</span></div><div class="toolbar" style="margin-top:12px"><button class="btn" onclick="editProduct(' + Number(id || 0) + ')">编辑</button><button class="btn" onclick="shelvesProduct(' + Number(id || 0) + ',1)">上架</button><button class="btn" onclick="shelvesProduct(' + Number(id || 0) + ',0)">下架</button><button class="btn danger" onclick="deleteProduct(' + Number(id || 0) + ')"><i data-lucide="trash-2"></i>删除</button></div></div>';
  }).join('') : '<div class="empty">暂无商品结果</div>';
  iconRefresh();
}
function editProduct(id) {
  const item = state.lastProducts.find(p => Number(p.id || p.product_id || 0) === Number(id));
  if (!item) return toast('没有找到商品数据', true);
  const images = item.main_images || item.images || item.image || '';
  const firstImage = Array.isArray(images) ? images[0] : String(images || '').split(',')[0];
  $('productId').value = item.id || item.product_id || '';
  $('productTitle').value = item.title || item.name || '';
  $('productSpec').value = item.spec || '';
  $('productPrice').value = item.price || item.min_price || '';
  $('productImageUrl').value = firstImage || '';
  $('productEditHint').textContent = '正在编辑商品 ID ' + $('productId').value;
  $('productTitle').focus();
}
function resetProductForm() {
  $('productId').value = '';
  $('productTitle').value = '';
  $('productSpec').value = '';
  $('productPrice').value = '';
  $('productImageUrl').value = '';
  $('productImageInput').value = '';
  $('productEditHint').textContent = '可创建商品，也可在下方列表点“编辑”后保存。';
}
async function saveProduct() {
  const title = $('productTitle').value.trim();
  if (!title) return toast('请输入商品名称', true);
  const body = {
    id: $('productId').value || undefined,
    title,
    spec: $('productSpec').value.trim(),
    price: $('productPrice').value || undefined,
    images: $('productImageUrl').value || undefined,
    main_images: $('productImageUrl').value || undefined
  };
  await api('/api/product/save', {method:'POST', body});
  toast('商品已保存');
  $('productKeyword').value = title;
  loadProducts();
}
async function uploadProductImage(file) {
  if (!file) return;
  const form = new FormData();
  form.append('image', file, file.name || ('product_' + Date.now() + '.jpg'));
  const res = await api('/api/product/upload', {method:'POST', body: form});
  const data = res.data || {};
  const url = data.url || data.images || data.path || data.full_url || (typeof data === 'string' ? data : '');
  $('productImageUrl').value = url || JSON.stringify(data);
  $('productEditHint').textContent = url ? '商品图已上传：' + url : '商品图已上传，保存时会带入返回数据。';
  toast('商品图已上传');
}
async function deleteProduct(id) {
  if (!id || !confirm('确定删除商品？')) return;
  await api('/api/product/delete', {method:'POST', body:{ids:String(id)}});
  toast('商品已删除');
  loadProducts();
}
async function shelvesProduct(id, stateValue) {
  if (!id) return;
  await api('/api/product/' + id + '/shelves', {method:'POST', body:{state: stateValue}});
  toast(stateValue ? '已提交上架' : '已提交下架');
}

async function refreshLight() {
  try { await Promise.all([loadSales(), loadWorkflow()]); } catch (e) { console.warn(e); }
}
async function refreshAll() {
  setStatus('刷新中');
  try {
    await Promise.all([loadSales(), loadInventory(), loadWorkflow(), loadProducts()]);
    setStatus('系统就绪');
  } catch (err) {
    toast('刷新失败：' + err.message, true);
    setStatus('刷新失败');
  }
}
async function handleQuickAction(action) {
  const focusMap = {
    inventory: 'quickInvKeyword',
    transfer: 'moveKeyword',
    purchase: 'moveKeyword',
    sale: 'saleCustomer',
    workflow: 'wfCustomer'
  };
  if (action === 'refresh') return refreshAll();
  if (action === 'print_latest') return printLatestSales();
  if (action === 'inventory') {
    const keyword = $('quickInvKeyword').value.trim() || $('inventoryKeyword').value.trim();
    if (keyword) {
      $('inventoryKeyword').value = keyword;
      await loadInventory(keyword);
      return;
    }
  }
  if (action === 'transfer') {
    if ($('moveKeyword').value.trim() && Number($('moveQty').value || 0) > 0) {
      await transferInventory();
      return;
    }
  }
  if (action === 'purchase') {
    if ($('moveKeyword').value.trim() && Number($('moveQty').value || 0) > 0) {
      await purchaseInventory();
      return;
    }
  }
  if (action === 'sale') {
    if (state.saleCustomer && state.saleLines.length) {
      await quickSale();
      return;
    }
  }
  if (action === 'workflow') {
    if ($('wfCustomer').value.trim() && $('wfGoods').value.trim()) {
      await createWorkflow();
      return;
    }
  }
  const target = focusMap[action];
  if (target && $(target)) {
    $(target).focus();
    toast('请先填写这张卡片里的参数，然后点执行按钮');
  }
}
function bindEvents() {
  $('sessionText').textContent = state.sessionId;
  $('sendBtn').addEventListener('click', () => sendChat());
  $('messageInput').addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) sendChat(); });
  $('newSessionBtn').addEventListener('click', () => { state.sessionId = newSessionId(); state.session = {}; localStorage.setItem('sj_web_session_id', state.sessionId); $('sessionText').textContent = state.sessionId; $('chatBody').innerHTML = ''; addMessage('bot', '已开启新会话。'); renderBusinessContext(); closeDrawer(); });
  $('clearChatBtn').addEventListener('click', () => { $('chatBody').innerHTML = ''; });
  $('contextBtn').addEventListener('click', openDrawer);
  $('closeDrawerBtn').addEventListener('click', closeDrawer);
  $('drawerMask').addEventListener('click', closeDrawer);
  $('refreshAllBtn').addEventListener('click', refreshAll);
  $('imageInput').addEventListener('change', (e) => { const file = e.target.files && e.target.files[0]; if (file) { state.pendingFile = file; showPreview(file); } });
  document.addEventListener('paste', (e) => {
    const items = e.clipboardData && e.clipboardData.items;
    if (!items) return;
    for (const item of items) {
      if (item.type && item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) { e.preventDefault(); state.pendingFile = file; showPreview(file); toast('已粘贴图片，正在识别'); sendChat(); }
        break;
      }
    }
  });
  document.querySelectorAll('.quick-chip').forEach(btn => btn.addEventListener('click', () => handleQuickAction(btn.dataset.action).catch(e => toast(e.message, true))));
  $('quickInvBtn').addEventListener('click', async () => { $('inventoryKeyword').value = $('quickInvKeyword').value; await loadInventory($('quickInvKeyword').value); });
  $('inventorySearchBtn').addEventListener('click', () => loadInventory());
  $('salesSearchBtn').addEventListener('click', loadSales);
  $('workflowSearchBtn').addEventListener('click', loadWorkflow);
  $('workflowCreateBtn').addEventListener('click', createWorkflow);
  $('moveKeyword').addEventListener('input', () => { state.moveProduct = null; $('moveSelectedHint').textContent = '先搜索并选择商品，再调货或进货，避免误匹配。'; });
  $('moveProductSearchBtn').addEventListener('click', () => searchMoveProducts().catch(e => toast(e.message, true)));
  $('transferBtn').addEventListener('click', () => transferInventory().catch(e => toast(e.message, true)));
  $('purchaseBtn').addEventListener('click', () => purchaseInventory().catch(e => toast(e.message, true)));
  $('saleCustomerSearchBtn').addEventListener('click', () => searchSaleCustomers().catch(e => toast(e.message, true)));
  $('saleProductSearchBtn').addEventListener('click', () => searchSaleProducts().catch(e => toast(e.message, true)));
  $('saleAddLineBtn').addEventListener('click', () => addSaleLine().catch(e => toast(e.message, true)));
  $('saleClearBtn').addEventListener('click', clearSaleForm);
  $('quickSaleBtn').addEventListener('click', () => quickSale().catch(e => toast(e.message, true)));
  $('productSearchBtn').addEventListener('click', loadProducts);
  $('productSaveBtn').addEventListener('click', () => saveProduct().catch(e => toast(e.message, true)));
  $('productResetBtn').addEventListener('click', resetProductForm);
  $('productImageInput').addEventListener('change', (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) uploadProductImage(file).catch(err => toast(err.message, true));
  });
}
window.printSales = (id) => printSales(id).catch(e => toast(e.message, true));
window.deleteSales = (id) => deleteSales(id).catch(e => toast(e.message, true));
window.editSales = (id) => editSales(id);
window.prepareInventoryAction = (title, color, type) => prepareInventoryAction(title, color, type);
window.markWorkflow = (id, field) => markWorkflow(id, field).catch(e => toast(e.message, true));
window.deleteWorkflow = (id) => deleteWorkflow(id).catch(e => toast(e.message, true));
window.editWorkflow = (id) => editWorkflow(id);
window.deleteProduct = (id) => deleteProduct(id).catch(e => toast(e.message, true));
window.shelvesProduct = (id, stateValue) => shelvesProduct(id, stateValue).catch(e => toast(e.message, true));
window.editProduct = (id) => editProduct(id);
window.selectSaleCustomer = (id, name) => selectSaleCustomer(id, name);
window.selectSaleProduct = (id) => selectSaleProduct(id).catch(e => toast(e.message, true));
window.updateSaleLine = (idx, field, value) => updateSaleLine(idx, field, value);
window.removeSaleLine = (idx) => removeSaleLine(idx);
window.selectMoveProduct = (id) => selectMoveProduct(id);
window.confirmBusinessCard = () => confirmBusinessCard();
window.cancelBusinessCard = () => cancelBusinessCard();
window.editBusinessCard = () => editBusinessCard();

bindEvents();
addMessage('bot', '你好，我是北极星。现在 WebUI 已经整合开单、库存、工作流、商品和对话能力。');
renderSaleLines();
renderBusinessContext();
iconRefresh();
refreshAll();
</script>
</body>
</html>"""


def get_webui_html():
    """Return the WebUI HTML."""
    return HTML_TEMPLATE
