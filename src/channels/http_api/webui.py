"""WebUI - Beijixing order-management workspace."""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>肆计包装-北极星订单管理机器人</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
:root {
  --bg: #ffffff;
  --panel: #ffffff;
  --panel-soft: #fafafa;
  --text: #171717;
  --muted: #667085;
  --line: #dedbd4;
  --line-soft: #ece8df;
  --blue: #111111;
  --blue-dark: #2a2a2a;
  --green: #111111;
  --red: #d36a5f;
  --amber: #d7a84b;
  --gold: #d4af64;
  --gold-soft: #f1d594;
  --shadow: 0 12px 30px rgba(16, 24, 40, 0.08);
  --shadow-soft: 0 5px 16px rgba(16, 24, 40, 0.06);
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  background: #ffffff;
  color: var(--text);
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.header {
  background: rgba(255, 255, 255, 0.96);
  border-bottom: 1px solid var(--line-soft);
  padding: 12px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.brand { min-width: 0; }
.brand h1 { font-size: 17px; font-weight: 760; letter-spacing: 0; color: #111111; }
.brand-sub { margin-top: 3px; font-size: 12px; color: var(--muted); }
.top-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
.pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid #ddd6c8;
  background: #fffdf8;
  color: #4f4636;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}
.pill.pending { border-color: #d7a84b; background: #fff8e8; color: #9a6a12; }
.btn-new, .btn, .send-btn, .mini-btn, .seg-btn {
  font-family: inherit;
  border-radius: 7px;
  cursor: pointer;
}
.btn-new {
  background: linear-gradient(180deg, #d0a650, #a77d28);
  color: #14110b;
  border: none;
  min-height: 32px;
  padding: 0 13px;
  font-size: 13px;
  box-shadow: var(--shadow-soft);
}
.btn-new:hover { background: linear-gradient(180deg, #e1bb67, #b78a31); }

.workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 292px minmax(420px, 1fr) 320px;
  gap: 14px;
  padding: 14px;
}
.rail, .status-rail, .chat-card {
  min-height: 0;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e8e2d7;
  border-radius: 8px;
  box-shadow: var(--shadow);
}
.rail, .status-rail {
  overflow-y: auto;
  padding: 12px;
}
.section-title {
  font-size: 13px;
  color: #111111;
  font-weight: 750;
  margin: 2px 0 10px;
}
.quick-card, .side-card {
  background: #ffffff;
  border: 1px solid #e8e2d7;
  border-radius: 8px;
  padding: 11px;
  margin-bottom: 10px;
  box-shadow: var(--shadow-soft);
}
.quick-card h2, .side-card h2 {
  font-size: 14px;
  line-height: 1.2;
  color: #111111;
  margin-bottom: 9px;
}
.field { margin-bottom: 8px; }
.field label {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.field input, .field select, textarea {
  width: 100%;
  border: 1px solid #d7d0c2;
  background: #ffffff;
  color: var(--text);
  border-radius: 7px;
  padding: 8px 9px;
  font-size: 13px;
  outline: none;
  font-family: inherit;
}
.field input:focus, .field select:focus, textarea:focus {
  border-color: var(--gold);
  box-shadow: 0 0 0 3px rgba(212, 175, 100, 0.12);
}
.form-row { display: grid; grid-template-columns: 1fr 84px; gap: 8px; }
.segmented {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 8px;
}
.seg-btn {
  border: 1px solid #d7d0c2;
  background: #fafafa;
  color: #171717;
  min-height: 32px;
  font-size: 13px;
}
.seg-btn.active {
  background: #fff2cc;
  border-color: #b88a35;
  color: #7a4d00;
  font-weight: 700;
}
.btn {
  width: 100%;
  min-height: 35px;
  border: 1px solid #d7d0c2;
  background: #ffffff;
  color: var(--text);
  font-size: 13px;
}
.btn:hover { background: #faf7ef; }
.btn-primary { background: linear-gradient(180deg, #d0a650, #a77d28); border-color: #b88a35; color: #14110b; font-weight: 700; }
.btn-primary:hover { background: linear-gradient(180deg, #e1bb67, #b78a31); }
.btn-green { background: var(--green); border-color: var(--green); color: #fff; font-weight: 700; }
.btn-green:hover { background: #2a2a2a; }
.btn-danger { border-color: #f1aaaa; color: var(--red); background: #fff; }
.btn-danger:hover { background: #fff5f5; }
.hint { font-size: 12px; color: #8a8170; line-height: 1.45; margin-top: 6px; }

.chat-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.chat-toolbar {
  padding: 11px 13px;
  border-bottom: 1px solid var(--line-soft);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  background: #ffffff;
}
.chat-title { font-size: 14px; font-weight: 750; color: #111111; }
.chat-sub { font-size: 12px; color: var(--muted); margin-top: 2px; }
.chat-box {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
  background: #ffffff;
}
.msg {
  margin-bottom: 14px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.msg.user { align-items: flex-end; }
.msg-head {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 5px;
  font-size: 12px;
  color: var(--muted);
}
.msg.user .msg-head { flex-direction: row-reverse; }
.avatar {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: #111111;
  font-size: 12px;
  font-weight: 700;
}
.msg.user .avatar { background: #d0a650; color: #15110a; }
.role-name { font-weight: 700; color: #344054; }
.bubble {
  width: fit-content;
  max-width: min(760px, 92%);
  padding: 13px 15px;
  border-radius: 8px;
  line-height: 1.62;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  box-shadow: var(--shadow-soft);
}
.msg.user .bubble { background: #111111; color: #ffffff; border: 1px solid #111111; }
.msg.assistant .bubble { background: #ffffff; color: var(--text); border: 1px solid #e8e2d7; }
.message-link { color: #9b6a13; font-weight: 700; text-decoration: none; border-bottom: 1px solid rgba(155,106,19,.35); }
.msg.user .message-link { color: #f5d58a; border-bottom-color: rgba(245,213,138,.5); }
.message-image {
  display: block;
  max-width: min(520px, 100%);
  max-height: 320px;
  margin-top: 8px;
  border-radius: 8px;
  border: 1px solid #e8e2d7;
  object-fit: contain;
  background: #ffffff;
}
.time { font-size: 11px; color: #98a2b3; margin-top: 5px; padding: 0 2px; }
.msg-meta { margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap; }
.intent-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: #fff8e8;
  border: 1px solid #ead49d;
  color: #7a4d00;
  font-size: 12px;
}
.welcome {
  background: #ffffff;
  border: 1px solid #e8e2d7;
  border-radius: 8px;
  padding: 30px 18px;
  text-align: center;
  color: var(--muted);
  line-height: 1.8;
  box-shadow: var(--shadow-soft);
}
.typing { color: var(--muted); font-size: 13px; padding: 8px 0; }
.pending-panel {
  display: none;
  margin: 12px 14px 0;
  border: 1px solid #d7a84b;
  background: #fff8e8;
  border-radius: 8px;
  padding: 12px 14px;
  box-shadow: var(--shadow-soft);
}
.pending-panel.show { display: block; }
.pending-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.pending-title { font-size: 14px; font-weight: 760; color: #7a4d00; }
.pending-detail { font-size: 13px; color: #5f4308; line-height: 1.55; white-space: pre-wrap; }
.pending-buttons { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.pending-buttons .btn { width: auto; padding: 0 12px; }
.composer {
  background: #ffffff;
  border-top: 1px solid var(--line-soft);
}
.input-bar { padding: 12px 14px 14px; display: flex; gap: 10px; align-items: flex-end; }
.input-wrap { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.correction-row { display: none; gap: 6px; flex-wrap: wrap; }
.correction-row.show { display: flex; }
.chip {
  border: 1px solid #d7d0c2;
  background: #ffffff;
  color: #344054;
  padding: 6px 9px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 12px;
}
.chip:hover { background: #faf7ef; }
textarea {
  resize: none;
  min-height: 44px;
  max-height: 120px;
  line-height: 1.5;
  font-size: 14px;
}
.send-btn {
  background: linear-gradient(180deg, #d0a650, #a77d28);
  color: #14110b;
  border: none;
  min-height: 44px;
  padding: 0 22px;
  font-size: 14px;
  font-weight: 700;
  box-shadow: var(--shadow-soft);
}
.send-btn:hover { background: linear-gradient(180deg, #e1bb67, #b78a31); }
.send-btn:disabled { background: #d7d0c2; color: #8a8170; cursor: not-allowed; }
.upload-btn {
  min-height: 44px;
  width: 46px;
  border: 1px solid #d7d0c2;
  background: #ffffff;
  color: #171717;
  font-size: 18px;
  font-weight: 700;
  box-shadow: var(--shadow-soft);
}
.upload-btn:hover { background: #faf7ef; border-color: #b88a35; }
.upload-btn:disabled { background: #f2f1ee; color: #8a8170; cursor: not-allowed; }

.status-grid { display: grid; gap: 10px; }
.kv { display: grid; grid-template-columns: 72px 1fr; gap: 8px; font-size: 13px; line-height: 1.45; }
.kv span:first-child { color: var(--muted); }
.kv span:last-child { color: #111111; font-weight: 650; word-break: break-word; }
.list-item {
  border: 1px solid #e8e2d7;
  background: #ffffff;
  border-radius: 8px;
  padding: 9px;
  margin-bottom: 8px;
}
.list-main { font-size: 13px; font-weight: 720; color: #111111; line-height: 1.35; }
.list-sub { font-size: 12px; color: var(--muted); margin-top: 4px; line-height: 1.35; }
.list-actions { display: flex; gap: 6px; margin-top: 8px; }
.mini-btn {
  min-height: 28px;
  padding: 0 8px;
  border: 1px solid #d7d0c2;
  background: #ffffff;
  color: #344054;
  font-size: 12px;
}
.mini-btn:hover { background: #faf7ef; }
.mini-btn.danger { border-color: #f1aaaa; color: var(--red); background: #fff; }
.mini-btn.danger:hover { background: #fff5f5; }
.empty { font-size: 12px; color: #8a8170; padding: 8px 0; }
.md-table-wrap {
  margin: 10px 0 12px;
  overflow-x: auto;
  border: 1px solid #d9c48f;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(17, 17, 17, 0.06);
}
.md-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 360px;
  background: #ffffff;
}
.md-table th,
.md-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #efe7d5;
  text-align: left;
  font-size: 13px;
}
.md-table th {
  color: #fff8df;
  background: #111111;
  font-weight: 760;
}
.md-table td { color: #222222; vertical-align: middle; }
.md-table tbody tr:nth-child(even) { background: #fffaf0; }
.md-table tbody tr:hover { background: #f7ecd0; }
.md-table td:last-child,
.md-table th:last-child { text-align: right; font-variant-numeric: tabular-nums; font-weight: 720; }
.md-table tr:last-child td { border-bottom: none; }
.color-cell { display: inline-flex; align-items: center; gap: 7px; white-space: nowrap; }
.color-swatch {
  width: 13px;
  height: 13px;
  border-radius: 3px;
  border: 1px solid rgba(0, 0, 0, 0.16);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.35);
  flex: 0 0 auto;
}

@media (max-width: 1180px) {
  .workspace { grid-template-columns: 280px minmax(420px, 1fr); }
  .status-rail { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
  .status-rail .section-title { grid-column: 1 / -1; margin-bottom: 0; }
}
@media (max-width: 820px) {
  body { height: auto; min-height: 100vh; }
  .workspace { grid-template-columns: 1fr; padding: 10px; }
  .rail, .status-rail, .chat-card { max-height: none; }
  .status-rail { display: block; }
  .chat-card { min-height: 72vh; }
  .top-actions { max-width: 54%; }
  .input-bar { padding: 10px; }
  .send-btn { padding: 0 16px; }
}
</style>
</head>
<body>

<div class="header">
  <div class="brand">
    <h1>肆计包装-北极星订单管理机器人</h1>
    <div class="brand-sub" id="sessionId"></div>
  </div>
  <div class="top-actions">
    <span class="pill" id="intentPill">空闲</span>
    <span class="pill" id="pendingPill">无待处理</span>
    <button class="btn-new" onclick="newSession()">新会话</button>
  </div>
</div>

<div class="workspace">
  <aside class="rail">
    <div class="section-title">快捷指令</div>

    <div class="quick-card">
      <h2>查库存</h2>
      <div class="field">
        <label>礼盒名称 / 规格 / 颜色</label>
        <input id="invKeyword" placeholder="例：见喜二三两黄色">
      </div>
      <button class="btn btn-primary" onclick="submitInventory()">查询库存</button>
      <div class="hint">可输入名称、规格、颜色，或任意组合。</div>
    </div>

    <div class="quick-card">
      <h2>调货</h2>
      <div class="field">
        <label>商品</label>
        <input id="transferProduct" placeholder="例：见喜3两 黄色">
      </div>
      <div class="form-row">
        <div class="field">
          <label>数量</label>
          <input id="transferQty" type="number" min="1" placeholder="7">
        </div>
        <div class="field">
          <label>单位</label>
          <select id="transferUnit">
            <option>套</option>
            <option>个</option>
            <option>件</option>
            <option>张</option>
          </select>
        </div>
      </div>
      <label class="field"><span style="display:block;font-size:12px;color:#667085;margin-bottom:4px;">调出仓库</span></label>
      <div class="segmented">
        <button class="seg-btn active" id="fromBx" onclick="setTransferFrom('百鑫')">百鑫仓库</button>
        <button class="seg-btn" id="fromSelf" onclick="setTransferFrom('自己店里')">自己店里</button>
      </div>
      <button class="btn btn-green" onclick="submitTransfer()">生成调货</button>
      <div class="hint" id="transferHint">当前：百鑫仓库 → 自己店里</div>
    </div>

    <div class="quick-card">
      <h2>创建销售单</h2>
      <div class="field">
        <label>客户</label>
        <input id="salesCustomer" placeholder="例：宴袍">
      </div>
      <div class="field">
        <label>礼盒</label>
        <input id="salesProduct" placeholder="例：见喜二三两黄色">
      </div>
      <div class="form-row">
        <div class="field">
          <label>数量</label>
          <input id="salesQty" type="number" min="1" placeholder="10">
        </div>
        <div class="field">
          <label>单位</label>
          <select id="salesUnit">
            <option>套</option>
            <option>个</option>
            <option>件</option>
            <option>张</option>
          </select>
        </div>
      </div>
      <button class="btn btn-primary" onclick="submitSales()">创建销售单</button>
      <div class="hint">会走北极星的客户、商品、库存和确认流程。</div>
    </div>
  </aside>

  <main class="chat-card">
    <div class="chat-toolbar">
      <div>
        <div class="chat-title">对话工作区</div>
        <div class="chat-sub">表单和自由输入都会交给北极星理解与核对</div>
      </div>
      <button class="mini-btn" onclick="refreshRecent()">刷新单据</button>
    </div>

    <div class="chat-box" id="chatBox">
      <div class="welcome">直接输入消息开始对话<br>左侧快捷表单可快速生成业务指令</div>
    </div>

    <div class="composer">
      <div class="pending-panel" id="pendingPanel">
        <div class="pending-head">
          <div class="pending-title" id="pendingTitle">待确认</div>
          <button class="mini-btn" onclick="toggleCorrections()">理解错了</button>
        </div>
        <div class="pending-detail" id="pendingDetail"></div>
        <div class="pending-buttons" id="pendingButtons"></div>
      </div>

      <div class="input-bar">
        <div class="input-wrap">
          <div class="correction-row" id="correctionRow">
            <button class="chip" onclick="quickCorrection('不是查库存，是调货')">改成调货</button>
            <button class="chip" onclick="quickCorrection('不是调货，是查库存')">改成查库存</button>
            <button class="chip" onclick="quickCorrection('不是普通订单，是工作流订单')">改成工作流</button>
            <button class="chip" onclick="quickCorrection('不是工作流，是查客户订单')">改成查订单</button>
          </div>
          <textarea id="input" placeholder="输入消息... (Enter发送, Shift+Enter换行)" rows="1"></textarea>
        </div>
        <input id="imageInput" type="file" accept="image/png,image/jpeg,image/webp,image/bmp" hidden onchange="uploadImage(this.files[0])">
        <button class="upload-btn" id="uploadBtn" title="上传设计稿图片" onclick="document.getElementById('imageInput').click()">＋</button>
        <button class="send-btn" id="sendBtn" onclick="send()">发送</button>
      </div>
    </div>
  </main>

  <aside class="status-rail">
    <div class="section-title">状态与单据</div>

    <div class="side-card">
      <h2>识别状态</h2>
      <div class="status-grid">
        <div class="kv"><span>意图</span><span id="sideIntent">空闲</span></div>
        <div class="kv"><span>待处理</span><span id="sidePending">无</span></div>
        <div class="kv"><span>会话</span><span id="sideSession"></span></div>
      </div>
    </div>

    <div class="side-card">
      <h2>最近销售单</h2>
      <div id="salesList"><div class="empty">加载中...</div></div>
    </div>

    <div class="side-card">
      <h2>最近工作流订单</h2>
      <div id="workflowList"><div class="empty">加载中...</div></div>
    </div>
  </aside>
</div>

<script>
const API = '/api/agent/chat';
const HISTORY_API = '/api/agent/history';
const RECENT_API = '/api/orders/recent';
const IMAGE_API = '/api/images/upload';
let sessionId = localStorage.getItem('sj_session_id') || ('web_' + Date.now());
let sending = false;
let currentSession = {};
let transferFrom = '百鑫';
let lastUploadSignature = '';
let lastUploadAt = 0;

localStorage.setItem('sj_session_id', sessionId);

const chatBox = document.getElementById('chatBox');
const input = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const uploadBtn = document.getElementById('uploadBtn');
const imageInput = document.getElementById('imageInput');
const pendingPanel = document.getElementById('pendingPanel');
const pendingTitle = document.getElementById('pendingTitle');
const pendingDetail = document.getElementById('pendingDetail');
const pendingButtons = document.getElementById('pendingButtons');
const pendingPill = document.getElementById('pendingPill');
const intentPill = document.getElementById('intentPill');
const correctionRow = document.getElementById('correctionRow');
const sideIntent = document.getElementById('sideIntent');
const sidePending = document.getElementById('sidePending');
const sideSession = document.getElementById('sideSession');
const salesList = document.getElementById('salesList');
const workflowList = document.getElementById('workflowList');

const intentLabels = {
  order: '下单',
  inventory: '查库存',
  stocktaking: '盘点',
  purchase: '进货',
  transfer: '调货',
  sales_query: '查订单',
  sales_manage: '订单管理',
  workflow: '工作流',
  knowledge: '知识',
  chat: '闲聊',
  help: '帮助',
  unknown: '未知'
};
const actionLabels = {
  confirm_transfer: '待确认调货',
  collect_transfer_color: '补充调货颜色',
  collect_transfer_quantity: '补充调货数量',
  confirm_sales_query_customer: '确认客户',
  confirm_image_sales: '确认图片开单',
  confirm_stocktaking: '确认盘点',
  collect_stocktaking_color: '补充盘点颜色',
  collect_stocktaking_quantity: '补充盘点数量',
  confirm_purchase_enter: '确认进货',
  collect_purchase_color: '补充进货颜色',
  collect_purchase_quantity: '补充进货数量',
  collect_workflow_order: '补充工作流订单'
};

document.getElementById('sessionId').textContent = '会话 ' + sessionId.slice(-8);
sideSession.textContent = sessionId.slice(-8);

input.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
});

loadHistory();
refreshRecent();

function loadHistory() {
  fetch(HISTORY_API + '?session_id=' + encodeURIComponent(sessionId))
    .then(r => r.json())
    .then(data => {
      if (data.code === 0) {
        if (data.data.history && data.data.history.length > 0) {
          removeWelcome();
          data.data.history.forEach(msg => appendMsg(msg.role === 'user' ? 'user' : 'assistant', msg.content, false));
          scrollBottom();
        }
        updateSessionState(data.data.session || {});
      }
    })
    .catch(() => {});
}

function refreshRecent() {
  fetch(RECENT_API + '?limit=6')
    .then(r => r.json())
    .then(data => {
      if (data.code === 0) {
        renderRecentSales(data.data.sales || []);
        renderRecentWorkflows(data.data.workflows || []);
      }
    })
    .catch(() => {
      salesList.innerHTML = '<div class="empty">加载失败</div>';
      workflowList.innerHTML = '<div class="empty">加载失败</div>';
    });
}

function renderRecentSales(rows) {
  if (!rows.length) {
    salesList.innerHTML = '<div class="empty">暂无销售单</div>';
    return;
  }
  salesList.innerHTML = rows.map(row => {
    const id = row.id || row.sales_id || row.sales_no || '';
    const customer = row.customer_display || row.customer_name || row.company_name || row.customer || '客户未识别';
    const amount = row.total_price ? '金额 ' + row.total_price : '';
    return `<div class="list-item">
      <div class="list-main">销售单 ${escapeHtml(id)}</div>
      <div class="list-sub">${escapeHtml(customer)} ${escapeHtml(amount)}</div>
      <div class="list-actions">
        <button class="mini-btn" onclick="sendMessage('查销售单${escapeJs(id)}详情')">查看</button>
        <button class="mini-btn danger" onclick="sendMessage('删除销售单 ${escapeJs(id)}')">删除</button>
      </div>
    </div>`;
  }).join('');
}

function renderRecentWorkflows(rows) {
  if (!rows.length) {
    workflowList.innerHTML = '<div class="empty">暂无工作流订单</div>';
    return;
  }
  workflowList.innerHTML = rows.map(row => {
    const id = row.id || row.order_id || row.workflow_order_id || '';
    const customer = row.customer_name || row.company_name || row.customer || '';
    const goods = row.goods_name || row.product_name || row.title || row.name || '';
    return `<div class="list-item">
      <div class="list-main">工作流 ${escapeHtml(id)}</div>
      <div class="list-sub">${escapeHtml(customer)} ${escapeHtml(goods)}</div>
      <div class="list-actions">
        <button class="mini-btn" onclick="sendMessage('查询工作流订单 ${escapeJs(id)}')">查看</button>
        <button class="mini-btn danger" onclick="sendMessage('删除工作流订单 ${escapeJs(id)}')">删除</button>
      </div>
    </div>`;
  }).join('');
}

function newSession() {
  sessionId = 'web_' + Date.now();
  localStorage.setItem('sj_session_id', sessionId);
  document.getElementById('sessionId').textContent = '会话 ' + sessionId.slice(-8);
  sideSession.textContent = sessionId.slice(-8);
  chatBox.innerHTML = '<div class="welcome">新会话已创建<br>输入消息开始对话</div>';
  updateSessionState({});
  input.value = '';
  input.focus();
}

function appendMsg(role, text, showMeta = true) {
  removeWelcome();
  const typing = chatBox.querySelector('.typing');
  if (typing) typing.remove();
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  const now = new Date();
  const time = now.getHours().toString().padStart(2,'0') + ':' + now.getMinutes().toString().padStart(2,'0');
  const roleName = role === 'user' ? '你' : '北极星';
  const avatar = role === 'user' ? '你' : '北';
  const meta = role === 'assistant' && showMeta ? buildMessageMeta() : '';
  div.innerHTML =
    '<div class="msg-head"><span class="avatar">' + avatar + '</span><span class="role-name">' + roleName + '</span></div>' +
    '<div class="bubble">' + renderMessageContent(text) + '</div>' +
    meta +
    '<div class="time">' + time + '</div>';
  chatBox.appendChild(div);
  scrollBottom();
}

function buildMessageMeta() {
  const extraction = currentSession.last_extraction || {};
  if (!extraction.intent) return '';
  return '<div class="msg-meta"><span class="intent-badge">识别：' + escapeHtml(intentLabels[extraction.intent] || extraction.intent) + '</span></div>';
}

function removeWelcome() {
  const welcome = chatBox.querySelector('.welcome');
  if (welcome) welcome.remove();
}
function showTyping() {
  const div = document.createElement('div');
  div.className = 'typing';
  div.id = 'typing';
  div.textContent = '北极星正在核对...';
  chatBox.appendChild(div);
  scrollBottom();
}
function scrollBottom() { chatBox.scrollTop = chatBox.scrollHeight; }

function send() { sendMessage(input.value.trim()); }
function sendMessage(msg) {
  if (!msg || sending) return;
  if (msg === '/new') { newSession(); return; }

  sending = true;
  sendBtn.disabled = true;
  uploadBtn.disabled = true;
  input.value = '';
  input.style.height = 'auto';
  correctionRow.classList.remove('show');
  appendMsg('user', msg, false);
  showTyping();

  fetch(API, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message: msg, session_id: sessionId})
  })
  .then(r => r.json())
  .then(data => {
    sending = false;
    sendBtn.disabled = false;
    uploadBtn.disabled = false;
    if (data.code === 0) {
      updateSessionState(data.data.session || {});
      appendMsg('assistant', data.data.response);
      refreshRecent();
    } else {
      appendMsg('assistant', '错误: ' + (data.msg || '未知错误'));
    }
  })
  .catch(err => {
    sending = false;
    sendBtn.disabled = false;
    uploadBtn.disabled = false;
    appendMsg('assistant', '请求失败: ' + err.message);
  });
}

function uploadImage(file) {
  if (!file || sending) return;
  if (!file.type || !file.type.startsWith('image/')) {
    appendMsg('assistant', '请上传图片文件。');
    imageInput.value = '';
    return;
  }

  const fileName = file.name || ('剪贴板图片_' + Date.now() + '.png');
  const uploadSignature = [fileName, file.size || 0, file.lastModified || 0].join(':');
  const nowMs = Date.now();
  if (uploadSignature === lastUploadSignature && nowMs - lastUploadAt < 8000) {
    imageInput.value = '';
    appendMsg('assistant', '这张图片刚刚已经提交过了，先等当前结果出来，避免重复创建工作流订单。');
    return;
  }
  lastUploadSignature = uploadSignature;
  lastUploadAt = nowMs;

  const form = new FormData();
  form.append('image', file, fileName);
  form.append('session_id', sessionId);

  sending = true;
  sendBtn.disabled = true;
  uploadBtn.disabled = true;
  correctionRow.classList.remove('show');
  const localPreviewUrl = URL.createObjectURL(file);
  appendMsg('user', '上传设计稿图片：' + fileName + '\\n' + localPreviewUrl, false);
  showTyping();

  fetch(IMAGE_API, { method: 'POST', body: form })
    .then(r => {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(data => {
      sending = false;
      sendBtn.disabled = false;
      uploadBtn.disabled = false;
      imageInput.value = '';
      if (data.code === 0) {
        try {
          updateSessionState(data.data.session || {});
          appendMsg('assistant', data.data.response);
          refreshRecent();
        } catch (uiErr) {
          console.error('图片结果展示失败', uiErr);
          appendMsg('assistant', '图片已经处理成功，但页面展示结果时出错。请刷新页面后查看最近工作流订单。');
        }
      } else {
        lastUploadSignature = '';
        appendMsg('assistant', '图片识别失败: ' + (data.msg || '未知错误'));
      }
    })
    .catch(err => {
      sending = false;
      sendBtn.disabled = false;
      uploadBtn.disabled = false;
      imageInput.value = '';
      lastUploadSignature = '';
      appendMsg('assistant', '图片上传失败: ' + err.message);
    });
}

document.addEventListener('paste', (event) => {
  if (sending) return;
  const items = Array.from((event.clipboardData && event.clipboardData.items) || []);
  const imageItem = items.find(item => item.kind === 'file' && item.type.startsWith('image/'));
  if (!imageItem) return;

  const file = imageItem.getAsFile();
  if (!file) return;
  event.preventDefault();
  uploadImage(file);
});

function updateSessionState(session) {
  currentSession = session || {};
  const extraction = currentSession.last_extraction || {};
  const intentText = extraction.intent ? (intentLabels[extraction.intent] || extraction.intent) : '空闲';
  intentPill.textContent = '识别：' + intentText;
  sideIntent.textContent = intentText;

  if (!currentSession.has_pending) {
    pendingPill.textContent = '无待处理';
    pendingPill.classList.remove('pending');
    sidePending.textContent = '无';
    pendingPanel.classList.remove('show');
    pendingDetail.textContent = '';
    pendingButtons.innerHTML = '';
    return;
  }

  const action = currentSession.pending_action || '';
  const intent = currentSession.pending_intent || '';
  const state = currentSession.state || {};
  const pendingText = actionLabels[action] || inferPendingLabel(intent, state);
  pendingPill.textContent = pendingText;
  pendingPill.classList.add('pending');
  sidePending.textContent = pendingText;
  pendingPanel.classList.add('show');
  pendingTitle.textContent = pendingText || '需要你确认';
  pendingDetail.textContent = buildPendingDetail(currentSession);
  pendingButtons.innerHTML = '';

  if (isConfirmAction(action, currentSession.state || {})) {
    pendingButtons.appendChild(makeButton('确认执行', 'btn btn-green', () => sendMessage('确认')));
  }
  pendingButtons.appendChild(makeButton('取消', 'btn btn-danger', () => sendMessage('取消')));
}

function buildPendingDetail(session) {
  const state = session.state || {};
  const action = session.pending_action || '';
  if (action === 'confirm_transfer' && Array.isArray(state.items)) {
    const lines = [(state.from_name || '调出仓库') + ' → ' + (state.to_name || '调入仓库')];
    state.items.forEach(item => {
      lines.push('- ' + (item.title || '商品') + (item.spec ? ' ' + item.spec : '') + '，调 ' + (item.qty || item.transfer_number || '') + ' 套，库存 ' + (item.stock ?? ''));
    });
    return lines.join('\\n');
  }
  if (action === 'collect_transfer_color') return '请补充要调拨的颜色。';
  if (action === 'collect_transfer_quantity') return '请补充要调拨的数量。';
  if (action === 'confirm_stocktaking' && Array.isArray(state.items)) {
    const lines = ['仓库：' + (state.warehouse_name || '仓库')];
    state.items.forEach(item => {
      const stock = item.current_stock !== undefined && item.current_stock !== '' ? '，当前库存 ' + item.current_stock : '';
      lines.push('- ' + (item.title || '商品') + (item.spec ? ' ' + item.spec : '') + '，盘点为 ' + (item.qty || item.number || '') + (item.unit || '套') + stock);
    });
    return lines.join('\\n');
  }
  if (action === 'collect_stocktaking_color') return '请补充要盘点的颜色。';
  if (action === 'collect_stocktaking_quantity') return '请补充盘点后的数量。';
  if (action === 'confirm_purchase_enter' && Array.isArray(state.items)) {
    const lines = ['仓库：' + (state.warehouse_name || '仓库')];
    state.items.forEach(item => {
      lines.push('- ' + (item.title || '商品') + (item.spec ? ' ' + item.spec : '') + '，进货 ' + (item.qty || item.buy_number || '') + (item.unit || '套'));
    });
    return lines.join('\\n');
  }
  if (action === 'collect_purchase_color') return '请补充要进货的颜色。';
  if (action === 'collect_purchase_quantity') return '请补充进货数量。';
  if (action === 'confirm_image_sales') {
    const params = state.order_params || {};
    const rows = [];
    if (params.customer) rows.push('客户：' + params.customer);
    (params.products || []).forEach(item => {
      rows.push('- ' + (item.name || '商品') + (item.color ? ' ' + item.color : '') + '，' + (item.qty || item.quantity || 1) + (item.unit || '套'));
    });
    return rows.join('\\n') || '是否根据图片识别结果继续开销售单？';
  }
  if (state.sales_ids) return '销售单：' + state.sales_ids.join('、');
  if (state.workflow_ids) return '工作流订单：' + state.workflow_ids.join('、');
  if (state.partial_params) return '正在补充参数，请按北极星的问题回复。';
  return '北极星正在等待你的回复。';
}

function inferPendingLabel(intent, state) {
  if (state.sales_ids) return '待确认删除销售单';
  if (state.workflow_ids) return '待确认删除工作流';
  return '等待：' + (intentLabels[intent] || intent || '回复');
}
function isConfirmAction(action, state) {
  return (action && action.indexOf('confirm') >= 0) || !!(state.sales_ids || state.workflow_ids);
}
function makeButton(text, className, onClick) {
  const btn = document.createElement('button');
  btn.className = className;
  btn.textContent = text;
  btn.onclick = onClick;
  return btn;
}
function toggleCorrections() { correctionRow.classList.toggle('show'); }
function quickCorrection(text) { sendMessage(text); }

function setTransferFrom(value) {
  transferFrom = value;
  document.getElementById('fromBx').classList.toggle('active', value === '百鑫');
  document.getElementById('fromSelf').classList.toggle('active', value === '自己店里');
  const to = value === '百鑫' ? '自己店里' : '百鑫仓库';
  document.getElementById('transferHint').textContent = '当前：' + (value === '百鑫' ? '百鑫仓库' : '自己店里') + ' → ' + to;
}
function submitInventory() {
  const keyword = document.getElementById('invKeyword').value.trim();
  if (!keyword) return;
  sendMessage('查下' + keyword + '库存');
}
function submitTransfer() {
  const product = document.getElementById('transferProduct').value.trim();
  const qty = document.getElementById('transferQty').value.trim();
  const unit = document.getElementById('transferUnit').value;
  if (!product || !qty) return;
  const from = transferFrom;
  const to = from === '百鑫' ? '自己店里' : '百鑫';
  sendMessage(product + ' 从' + from + '调货' + qty + unit + '到' + to);
}
function submitSales() {
  const customer = document.getElementById('salesCustomer').value.trim();
  const product = document.getElementById('salesProduct').value.trim();
  const qty = document.getElementById('salesQty').value.trim();
  const unit = document.getElementById('salesUnit').value;
  if (!customer || !product || !qty) return;
  sendMessage('客户' + customer + ' ' + product + qty + unit + ' 下单');
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = text || '';
  return d.innerHTML;
}
function renderMessageContent(text) {
  const lines = String(text || '').split('\\n');
  const chunks = [];
  let i = 0;
  while (i < lines.length) {
    if (isMarkdownTableAt(lines, i)) {
      const tableLines = [lines[i], lines[i + 1]];
      i += 2;
      while (i < lines.length && lines[i].includes('|') && lines[i].trim()) {
        tableLines.push(lines[i]);
        i += 1;
      }
      chunks.push(renderMarkdownTable(tableLines));
      continue;
    }
    const textLines = [];
    while (i < lines.length && !isMarkdownTableAt(lines, i)) {
      textLines.push(lines[i]);
      i += 1;
    }
    if (textLines.length) {
      chunks.push('<div class="text-block">' + renderTextBlock(textLines.join('\\n')) + '</div>');
    }
  }
  return chunks.join('');
}
function renderTextBlock(text) {
  const urlRe = new RegExp('(?:https?://[^\\s]+|/api/images/file/[^\\s]+|blob:[^\\s]+)', 'g');
  let html = '';
  let lastIndex = 0;
  String(text || '').replace(urlRe, (url, offset) => {
    html += escapeHtml(text.slice(lastIndex, offset));
    const cleanUrl = url.replace(/[，。),）]+$/, '');
    const suffix = url.slice(cleanUrl.length);
    html += '<a class="message-link" href="' + escapeHtml(cleanUrl) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(cleanUrl) + '</a>';
    if (isImageUrl(cleanUrl)) {
      html += '<img class="message-image" src="' + escapeHtml(cleanUrl) + '" alt="上传图片">';
    }
    html += escapeHtml(suffix);
    lastIndex = offset + url.length;
    return url;
  });
  html += escapeHtml(text.slice(lastIndex));
  return html;
}
function isImageUrl(url) {
  return url.startsWith('blob:') || new RegExp('\\.(png|jpe?g|webp|bmp|gif)(\\?.*)?$', 'i').test(url);
}
function isMarkdownTableAt(lines, idx) {
  if (idx + 1 >= lines.length) return false;
  return lines[idx].includes('|') && /^\\s*\\|?\\s*:?-{3,}:?\\s*(\\|\\s*:?-{3,}:?\\s*)+\\|?\\s*$/.test(lines[idx + 1]);
}
function splitTableRow(line) {
  return line.trim().replace(/^\\|/, '').replace(/\\|$/, '').split('|').map(cell => cell.trim());
}
function renderMarkdownTable(tableLines) {
  const headers = splitTableRow(tableLines[0]);
  const rows = tableLines.slice(2).map(splitTableRow).filter(row => row.length);
  const thead = '<thead><tr>' + headers.map(h => '<th>' + escapeHtml(h) + '</th>').join('') + '</tr></thead>';
  const tbody = '<tbody>' + rows.map(row => '<tr>' + headers.map((header, idx) => '<td>' + renderTableCell(header, row[idx] || '') + '</td>').join('') + '</tr>').join('') + '</tbody>';
  return '<div class="md-table-wrap"><table class="md-table">' + thead + tbody + '</table></div>';
}
function renderTableCell(header, value) {
  if (String(header || '').trim() === '颜色') {
    const css = colorToCss(value);
    if (css) {
      return '<span class="color-cell"><span class="color-swatch" style="background:' + css + '"></span>' + escapeHtml(value) + '</span>';
    }
  }
  return escapeHtml(value);
}
function colorToCss(value) {
  const text = String(value || '').trim();
  if (!text || text === '-') return '';
  const map = {
    '红色': '#d92d20',
    '黄色': '#f4c430',
    '金色': '#c69214',
    '橙色': '#f97316',
    '蓝色': '#2563eb',
    '绿色': '#16a34a',
    '橄榄绿': '#708238',
    '咖色': '#7a4a28',
    '深咖色': '#4b2e1f',
    '古铜色': '#8c6239',
    '黑色': '#111111',
    '白色': '#ffffff',
    '银色': '#c7c9cc',
    '灰色': '#8a8f98',
    '紫色': '#7c3aed',
    '粉色': '#f472b6'
  };
  return map[text] || '';
}
function escapeJs(value) {
  return String(value || '').replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
}
</script>
</body>
</html>"""


def get_webui_html():
    """返回 WebUI HTML"""
    return HTML_TEMPLATE
