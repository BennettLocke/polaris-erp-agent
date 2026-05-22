"""WebUI - Beijixing card workspace."""

from pathlib import Path


_BASE_DIR = Path(__file__).resolve().parent
_TEMPLATE_PATH = _BASE_DIR / "webui_template.html"
_SCRIPT_PATH = _BASE_DIR / "webui_api.js"


EXTRA_CSS = """
  .api-tools { display: grid; gap: 12px; }
  .api-tools .tool-group { display: grid; gap: 8px; }
  .api-tools .tool-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .api-tools input,
  .api-tools select { min-width: 0; }
  .workflow-filter { display: inline-flex; gap: 6px; padding: 4px; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
  .workflow-filter button { height: 32px; min-height: 32px; padding: 0 10px; border-radius: 6px; font-size: 13px; background: transparent; box-shadow: none; }
  .workflow-filter button.active { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 700; }
  .api-tools .choices { display: grid; gap: 7px; max-height: 190px; overflow: auto; }
  .api-tools .choice { width: 100%; text-align: left; padding: 9px; }
  .api-tools .sale-lines { display: grid; gap: 8px; }
  .api-tools .line-card { border: 1px solid var(--line); border-radius: 8px; padding: 9px; background: var(--surface-2); display: grid; gap: 7px; }
  .api-tools .line-edit { display: grid; grid-template-columns: 1fr 1fr auto; gap: 7px; align-items: end; }
  .api-tools label { display: block; color: var(--muted); font-size: 12px; margin: 0 0 4px; }
  .api-tools .hint { color: var(--muted); font-size: 12px; line-height: 1.5; margin: 0; }
  .api-tools .primary,
  .drawer .primary,
  .context .primary { border-color: var(--accent); background: var(--accent); color: #fff; font-weight: 700; }
  .danger { color: var(--coral); border-color: #ffd0cd; }
  .empty { color: var(--muted); text-align: center; padding: 18px 8px; border: 1px dashed var(--line); border-radius: 8px; background: #fff; }
  .toast { position: fixed; right: 16px; bottom: 16px; z-index: 80; max-width: 360px; background: #17231f; color: #fff; border-radius: 8px; padding: 11px 13px; box-shadow: 0 18px 38px rgba(0,0,0,.22); display: none; line-height: 1.5; }
  .toast.show { display: block; }
  .confirm-mask { position: fixed; inset: 0; z-index: 120; display: grid; place-items: center; padding: 18px; background: rgba(17,17,17,.28); backdrop-filter: blur(3px); opacity: 0; pointer-events: none; transition: opacity .18s ease; }
  .confirm-mask.open { opacity: 1; pointer-events: auto; }
  .confirm-box { width: min(380px, 94vw); border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); box-shadow: 0 24px 70px rgba(20,20,20,.24); padding: 16px; transform: translateY(8px) scale(.98); transition: transform .18s ease; }
  .confirm-mask.open .confirm-box { transform: translateY(0) scale(1); }
  .confirm-title { margin: 0; color: var(--text); font-size: 17px; line-height: 1.35; font-weight: 780; }
  .confirm-message { margin: 8px 0 16px; color: var(--muted); font-size: 13px; line-height: 1.6; }
  .confirm-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
  .confirm-actions button { height: 38px; display: inline-flex; align-items: center; justify-content: center; }
  .confirm-actions .danger-confirm { background: #111; border-color: #111; color: #fff; font-weight: 760; }
  .business-confirm-box { width: min(560px, 94vw); max-height: 86vh; overflow: auto; }
  .business-confirm-actions { grid-template-columns: 1fr 1.2fr; position: sticky; bottom: -16px; background: var(--surface); padding-top: 10px; }
  .inventory-popup-box { width: min(760px, 96vw); max-height: 88vh; overflow: auto; }
  .inventory-popup-actions { grid-template-columns: 1fr; position: sticky; bottom: -16px; background: var(--surface); padding-top: 10px; }
  .inventory-popup-summary { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
  .inventory-popup-summary span { padding: 5px 9px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface-2); color: var(--text); font-size: 12px; font-weight: 760; }
  .inventory-popup-list { display: grid; gap: 10px; }
  .sr-only { position: absolute !important; width: 1px !important; height: 1px !important; padding: 0 !important; margin: -1px !important; overflow: hidden !important; clip: rect(0, 0, 0, 0) !important; white-space: nowrap !important; border: 0 !important; }
  #workbench.view.active { height: calc(100vh - 112px); min-height: 0; }
  #workbench .workspace { height: 100%; min-height: 0; grid-template-rows: auto minmax(0, 1fr) auto; }
  #workbench .chat { height: 100%; min-height: 0; overflow: hidden; grid-template-rows: auto minmax(0, 1fr); }
  #workbench .messages { min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
  #workbench .messages:empty { min-height: 0; }
  .workflow-images { display: grid; gap: 9px; }
  .workflow-image-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr)); gap: 8px; }
  .workflow-image-card { position: relative; aspect-ratio: 1.45; border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; background: #f4f1ea; }
  .workflow-image-card img { width: 100%; height: 100%; object-fit: contain; display: block; }
  .workflow-image-remove { position: absolute; top: 5px; right: 5px; width: 24px; height: 24px; min-height: 0; padding: 0; border-radius: 999px; background: rgba(17,17,17,.78); border-color: rgba(17,17,17,.78); color: #fff; line-height: 1; }
  .workflow-image-upload { aspect-ratio: 1.45; min-height: 64px; border: 1px dashed var(--line-strong); border-radius: var(--radius); display: grid; place-items: center; align-content: center; gap: 4px; cursor: pointer; color: var(--text); background: var(--surface-2); font-size: 13px; font-weight: 700; }
  .workflow-image-upload:hover { border-color: var(--accent); }
  .workflow-image-upload span { display: block; color: var(--muted); font-size: 11px; font-weight: 600; }
  .product-lines { display: grid; gap: 6px; margin-top: 10px; padding: 9px; background: #f8fafc; border: 1px solid var(--line); border-radius: 8px; }
  .product-row { display: grid; grid-template-columns: minmax(0, 1fr) 54px 82px; gap: 8px; align-items: center; font-size: 12px; }
  .product-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 700; }
  .product-qty { text-align: center; color: #39352f; font-weight: 700; }
  .product-price { text-align: right; color: var(--accent); font-weight: 700; }
  #inventoryList.section-grid { --card-min-width: 390px; display: block; column-width: 390px; column-gap: 14px; }
  #inventoryList.table-mode.section-grid { display: grid; grid-template-columns: 1fr; column-width: auto; column-gap: 0; }
  #inventoryList.table-mode .business-card { display: block; width: 100%; margin: 0; }
  #inventoryList .inventory-card { padding: 16px; display: inline-grid; width: 100%; gap: 12px; margin: 0 0 14px; break-inside: avoid; page-break-inside: avoid; vertical-align: top; }
  #inventoryList .inventory-title { min-width: 0; }
  #inventoryList .inventory-title h3 { margin-bottom: 4px; }
  #inventoryList .inventory-total { min-width: 74px; text-align: right; }
  #inventoryList .inventory-total strong { display: block; color: var(--accent); font-size: 30px; line-height: 1; font-weight: 850; }
  #inventoryList .inventory-total span { color: var(--muted); font-size: 12px; font-weight: 700; }
  #inventoryList .table-lite { font-size: 13px; }
  #inventoryList .table-lite th,
  #inventoryList .table-lite td { padding: 9px 7px; vertical-align: middle; }
  #inventoryList .table-lite th:nth-child(2),
  #inventoryList .table-lite th:nth-child(3),
  #inventoryList .table-lite th:nth-child(4),
  #inventoryList .table-lite td:nth-child(2),
  #inventoryList .table-lite td:nth-child(3),
  #inventoryList .table-lite td:nth-child(4) { text-align: right; white-space: nowrap; }
  #inventoryList .inventory-actions { display: flex; justify-content: flex-end; gap: 5px; }
  #inventoryList .inventory-actions button { height: 28px; min-height: 28px; padding: 0 8px; font-size: 12px; }
  .management-list { display: grid; gap: 10px; width: 100%; }
  .record-card { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); box-shadow: 0 8px 22px rgba(31, 24, 15, .05); padding: 13px; display: grid; gap: 12px; min-width: 0; }
  .record-card h3 { margin: 0; color: var(--text); font-size: 16px; line-height: 1.28; letter-spacing: 0; }
  .record-card p { margin: 0; color: var(--muted); font-size: 12px; line-height: 1.45; }
  .record-main { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; align-items: start; }
  .record-main > div { min-width: 0; display: grid; gap: 4px; }
  .record-main button { height: 32px; min-height: 32px; padding: 0 11px; font-size: 12px; }
  .record-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(112px, 1fr)); gap: 8px; }
  .record-metric { min-width: 0; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 8px 9px; display: grid; gap: 3px; }
  .record-metric span { color: var(--muted); font-size: 11px; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .record-metric strong { color: var(--text); font-size: 14px; line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .record-metric.accent strong { color: var(--accent); font-size: 16px; font-weight: 850; }
  .record-metric.danger-metric strong { color: var(--coral); }
  .record-note { border-top: 1px solid var(--line); padding-top: 9px; }
  .record-route { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 8px; align-items: center; padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); }
  .record-route strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); }
  .record-route span { color: var(--muted); font-weight: 850; }
  #customerList.section-grid { display: block; }
  .customer-card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 10px; align-items: start; }
  .customer-card { cursor: pointer; padding: 12px; gap: 10px; }
  .customer-card .record-main { grid-template-columns: 1fr; gap: 5px; }
  .customer-card h3 { font-size: 15px; }
  .customer-card p { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .customer-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 7px; align-items: stretch; padding-top: 2px; }
  .customer-actions button { width: 100%; height: 32px; min-height: 32px; padding: 0 7px; border-radius: 8px; font-size: 12px; font-weight: 760; justify-content: center; background: #fff; }
  .customer-actions .primary-action { background: #111; border-color: #111; color: #fff; }
  .customer-card:hover,
  .user-row:hover,
  .inventory-record:hover { border-color: #c9d8d1; background: #fffefa; }
  .customer-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }
  .customer-metrics .record-metric { padding: 8px; }
  .customer-metrics .record-metric strong { font-size: 14px; }
  .customer-metrics .record-metric.accent strong { font-size: 17px; }
  .customer-metrics .record-metric:first-child { grid-column: auto; }
  .user-row { gap: 11px; }
  .user-main { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; align-items: center; }
  .user-main > div { min-width: 0; display: grid; gap: 4px; }
  .user-main p { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .user-controls { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(160px, .6fr); gap: 10px; align-items: center; }
  .user-controls > div { min-width: 0; display: grid; gap: 6px; }
  .user-controls span { color: var(--muted); font-size: 11px; font-weight: 760; }
  .role-buttons { display: flex; flex-wrap: wrap; gap: 6px; }
  .role-buttons button { height: 30px; min-height: 30px; padding: 0 9px; border-radius: 999px; font-size: 12px; }
  .role-buttons button.active { background: #111; border-color: #111; color: #fff; }
  .enable-toggle { height: 32px; min-height: 32px; padding: 0 11px; border-color: #e2d6c4; color: #7b6650; background: #fffaf1; }
  .enable-toggle.on { border-color: #b9e3cf; color: var(--accent); background: #f3fbf7; }
  .user-status strong { color: var(--text); font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .drawer-summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 4px 0; }
  .drawer-summary strong { color: var(--text); font-size: 16px; }
  .drawer-summary span { color: var(--muted); font-size: 12px; font-weight: 760; }
  .customer-sales-filter { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding-bottom: 2px; }
  .customer-sales-filter button { height: 32px; min-height: 32px; padding: 0 10px; border-radius: 999px; font-size: 12px; }
  .customer-sales-filter button.active { background: #111; border-color: #111; color: #fff; }
  .month-filter { display: flex; align-items: center; gap: 7px; }
  .month-filter select { height: 32px; border: 1px solid var(--line); border-radius: 8px; padding: 0 8px; background: #fff; color: var(--text); }
  .month-button-grid { display: flex; flex-wrap: wrap; gap: 6px; width: 100%; }
  .month-button-grid button { min-width: 48px; }
  .balance-form-box { width: min(520px, 94vw); }
  .balance-form { display: grid; gap: 12px; }
  .balance-form label { display: grid; gap: 6px; color: var(--muted); font-size: 12px; font-weight: 760; }
  .balance-form input,
  .balance-form select,
  .balance-form textarea { width: 100%; border: 1px solid var(--line); border-radius: 8px; padding: 9px 10px; background: #fff; color: var(--text); box-sizing: border-box; }
  .balance-form textarea { min-height: 68px; resize: vertical; }
  .balance-month-grid { display: flex; flex-wrap: wrap; gap: 6px; }
  .balance-month-grid button { min-width: 48px; height: 30px; min-height: 30px; padding: 0 8px; border-radius: 999px; font-size: 12px; }
  .balance-month-grid button.active { background: #111; border-color: #111; color: #fff; }
  .balance-summary { border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 9px 10px; color: var(--text); font-size: 13px; line-height: 1.55; }
  .balance-ledger-list { gap: 9px; }
  .balance-ledger-summary { border-bottom: 1px solid var(--line); padding-bottom: 9px; margin-bottom: 2px; }
  .balance-ledger-card { padding: 11px; gap: 10px; box-shadow: none; }
  .balance-ledger-delta { align-self: center; justify-self: end; font-size: 18px; font-weight: 900; color: var(--text); white-space: nowrap; }
  .balance-ledger-delta.positive { color: var(--accent); }
  .balance-ledger-delta.negative { color: var(--coral); }
  .settings-layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; margin-top: 14px; }
  .settings-layout[hidden] { display: none !important; }
  .settings-panel { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); padding: 16px; display: grid; gap: 16px; max-width: 980px; }
  .settings-panel-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--line); }
  .settings-panel-head h3 { margin: 0; color: var(--text); font-size: 18px; line-height: 1.25; }
  .settings-panel-head p { margin: 4px 0 0; color: var(--muted); font-size: 13px; line-height: 1.5; }
  .settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .settings-summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }
  .setting-stat { border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 10px 12px; min-width: 0; }
  .setting-stat span { display: block; color: var(--muted); font-size: 12px; font-weight: 760; margin-bottom: 4px; }
  .setting-stat strong { display: block; color: var(--text); font-size: 20px; line-height: 1.15; overflow-wrap: anywhere; }
  .settings-log-list { display: grid; gap: 8px; }
  .settings-log-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; align-items: center; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 9px 10px; color: var(--text); font-size: 13px; }
  .settings-log-row small { display: block; margin-top: 3px; color: var(--muted); font-weight: 700; line-height: 1.45; }
  .setting-block { display: grid; gap: 9px; min-width: 0; }
  .setting-block.full { grid-column: 1 / -1; }
  .setting-block-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--muted); font-size: 12px; font-weight: 800; }
  .setting-block-title button { height: 30px; min-height: 30px; padding: 0 10px; border-radius: 999px; font-size: 12px; }
  .miniapp-design-panel { max-width: none; }
  .miniapp-designer { display: grid; grid-template-columns: 250px minmax(320px, 1fr) 360px; gap: 14px; align-items: start; }
  .miniapp-palette,
  .miniapp-inspector,
  .miniapp-canvas-wrap { border: 1px solid var(--line); border-radius: 8px; background: #fff; padding: 12px; min-width: 0; }
  .miniapp-canvas-wrap { display: grid; place-items: center; background: var(--surface-2); min-height: 680px; }
  .miniapp-pane-title { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; margin: 0 0 10px; }
  .miniapp-pane-title strong { color: var(--text); font-size: 14px; line-height: 1.3; }
  .miniapp-pane-title span { color: var(--muted); font-size: 12px; font-weight: 760; }
  .miniapp-palette-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
  .miniapp-palette-grid button { display: grid; gap: 3px; min-height: 58px; padding: 9px; border-radius: 8px; text-align: left; align-content: center; background: var(--surface-2); box-shadow: none; }
  .miniapp-palette-grid button strong { color: var(--text); font-size: 13px; line-height: 1.2; }
  .miniapp-palette-grid button span { color: var(--muted); font-size: 11px; line-height: 1.2; }
  .miniapp-outline { display: grid; gap: 8px; }
  .miniapp-outline-row { display: grid; grid-template-columns: minmax(0, 1fr) 30px 30px 30px; gap: 5px; align-items: center; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 6px; }
  .miniapp-outline-row.active { border-color: #94d8bd; background: #f3fbf7; }
  .miniapp-outline-row.off { opacity: .62; }
  .miniapp-outline-main { min-width: 0; min-height: 34px; padding: 0 6px; display: grid; gap: 2px; border: 0; background: transparent; box-shadow: none; text-align: left; }
  .miniapp-outline-main strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text); font-size: 13px; }
  .miniapp-outline-main span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); font-size: 11px; font-weight: 760; }
  .miniapp-outline-row > button:not(.miniapp-outline-main) { width: 30px; height: 30px; min-height: 30px; padding: 0; border-radius: 999px; font-size: 12px; }
  .miniapp-phone { width: 375px; min-height: 640px; border: 1px solid #d9dee2; border-radius: 28px; background: #f6f7f8; box-shadow: 0 22px 60px rgba(30,38,48,.16); overflow: hidden; }
  .miniapp-phone-bar { height: 26px; background: #111; position: relative; }
  .miniapp-phone-bar::after { content: ""; position: absolute; left: 50%; top: 9px; width: 72px; height: 6px; margin-left: -36px; border-radius: 999px; background: rgba(255,255,255,.86); }
  .miniapp-phone-nav { padding: 14px 16px 12px; display: grid; gap: 3px; background: #fff; border-bottom: 1px solid var(--line); }
  .miniapp-phone-nav strong { color: var(--text); font-size: 18px; line-height: 1.25; }
  .miniapp-phone-nav span { color: var(--muted); font-size: 12px; font-weight: 760; }
  .miniapp-phone-scroll { height: 540px; overflow: auto; padding: 10px; display: grid; gap: 10px; align-content: start; }
  .miniapp-phone-tabs { height: 48px; display: grid; grid-template-columns: repeat(4, 1fr); align-items: center; background: #fff; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; font-weight: 800; text-align: center; }
  .miniapp-phone-tabs span:first-child { color: var(--accent); }
  .miniapp-preview-module { width: 100%; display: block; border: 1px solid transparent; border-radius: 8px; background: transparent; padding: 0; box-shadow: none; text-align: left; overflow: hidden; }
  .miniapp-preview-module.active { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(42, 126, 91, .12); }
  .miniapp-preview-module.disabled { opacity: .45; }
  .miniapp-preview-banner { height: 132px; padding: 14px; display: grid; align-content: end; gap: 4px; border-radius: 8px; background: linear-gradient(135deg, #1d2a25, #527165); color: #fff; }
  .miniapp-preview-banner strong { font-size: 20px; line-height: 1.2; }
  .miniapp-preview-banner span { color: rgba(255,255,255,.78); font-size: 12px; }
  .miniapp-preview-nav { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; padding: 12px 8px; border-radius: 8px; background: #fff; }
  .miniapp-preview-nav span { min-width: 0; display: grid; justify-items: center; gap: 5px; color: var(--text); font-size: 11px; font-weight: 760; }
  .miniapp-preview-nav i { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 999px; background: #e9f5ef; color: var(--accent); font-style: normal; font-weight: 900; }
  .miniapp-preview-nav em { grid-column: 1 / -1; color: var(--muted); font-style: normal; text-align: center; }
  .miniapp-preview-title { padding: 3px 2px 8px; color: var(--text); font-size: 15px; font-weight: 900; }
  .miniapp-preview-products { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .miniapp-preview-products span { min-width: 0; display: grid; gap: 6px; border-radius: 8px; background: #fff; padding: 8px; }
  .miniapp-preview-products b { aspect-ratio: 1.25; border-radius: 7px; background: #ece8df; }
  .miniapp-preview-products i { color: var(--text); font-size: 11px; line-height: 1.3; font-style: normal; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .miniapp-preview-image { height: 96px; padding: 12px; display: grid; align-content: center; gap: 3px; border-radius: 8px; background: #ede7dc; color: var(--text); }
  .miniapp-preview-image.hot { background: repeating-linear-gradient(135deg, #ede7dc 0 12px, #f8f5ee 12px 24px); }
  .miniapp-preview-image strong { font-size: 16px; line-height: 1.25; }
  .miniapp-preview-image span { color: var(--muted); font-size: 12px; font-weight: 760; }
  .miniapp-preview-empty,
  .miniapp-inspector-empty { border: 1px dashed var(--line-strong); border-radius: 8px; background: #fff; color: var(--muted); padding: 18px; text-align: center; font-size: 13px; line-height: 1.55; }
  .miniapp-inspector { display: grid; gap: 12px; }
  .miniapp-inspector-head { display: flex; justify-content: space-between; gap: 10px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); }
  .miniapp-inspector-head strong { color: var(--text); font-size: 14px; }
  .miniapp-inspector-head span { color: var(--muted); font-size: 12px; font-weight: 760; }
  .miniapp-page-grid,
  .miniapp-inspector-grid { grid-template-columns: 1fr; }
  .miniapp-item-editor { display: grid; gap: 8px; }
  .miniapp-item-row { display: grid; grid-template-columns: 1fr 1fr 1fr 34px; gap: 7px; align-items: center; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 8px; }
  .miniapp-item-row input { min-width: 0; border: 1px solid var(--line); border-radius: 8px; padding: 8px 9px; background: #fff; color: var(--text); }
  .setting-list { display: grid; gap: 8px; }
  .setting-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 8px; align-items: center; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 8px; }
  .setting-row.two { grid-template-columns: minmax(0, 1fr) auto; }
  .setting-row input,
  .setting-row select { min-height: 34px; background: #fff; }
  .setting-row-name { display: grid; gap: 2px; min-width: 0; }
  .setting-row-name strong { color: var(--text); font-size: 14px; line-height: 1.25; overflow-wrap: anywhere; }
  .setting-row-name span { color: var(--muted); font-size: 12px; line-height: 1.35; }
  .setting-segment { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; overflow: hidden; background: #fff; white-space: nowrap; }
  .setting-segment button { min-height: 30px; height: 30px; border: 0; border-radius: 0; padding: 0 10px; background: transparent; color: var(--muted); box-shadow: none; }
  .setting-segment button.active { background: var(--accent); color: #fff; }
  .setting-delete { width: 34px; height: 34px; min-height: 34px; padding: 0; border-radius: 999px; color: var(--coral); }
  .setting-radio { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 12px; font-weight: 760; white-space: nowrap; }
  .setting-radio input { width: 16px; height: 16px; accent-color: var(--accent); }
  .setting-rule-card { display: grid; gap: 5px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 11px 12px; }
  .setting-rule-card strong { color: var(--text); font-size: 14px; line-height: 1.3; }
  .setting-rule-card span { color: var(--muted); font-size: 12px; line-height: 1.55; }
  .setting-role-card { display: grid; gap: 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 8px; }
  .setting-role-card .setting-row { border: 0; background: transparent; padding: 0; }
  .role-fixed-head > div { display: grid; gap: 3px; min-width: 0; }
  .role-fixed-head strong { color: var(--text); font-size: 14px; line-height: 1.3; }
  .role-fixed-head span { color: var(--muted); font-size: 12px; line-height: 1.35; }
  .setting-permission-details { border-top: 1px solid var(--line); padding-top: 8px; }
  .setting-permission-details summary { cursor: pointer; color: var(--muted); font-size: 12px; font-weight: 760; line-height: 1.45; }
  .setting-permission-details .setting-chip-grid { margin-top: 8px; }
  .setting-chip-grid { display: flex; flex-wrap: wrap; gap: 7px; }
  .setting-chip.readonly { display: inline-flex; align-items: center; min-height: 28px; border: 1px solid #b9e3cf; border-radius: 999px; background: #f3fbf7; padding: 0 9px; color: var(--accent); font-size: 12px; font-weight: 760; }
  .setting-chip-toggle input { position: absolute; opacity: 0; pointer-events: none; }
  .setting-chip-toggle span { display: inline-flex; align-items: center; min-height: 30px; border: 1px solid var(--line); border-radius: 999px; background: #fff; padding: 0 10px; color: var(--muted); font-size: 12px; font-weight: 760; cursor: pointer; }
  .setting-chip-toggle input:checked + span { border-color: #b9e3cf; background: #f3fbf7; color: var(--accent); }
  .setting-field { display: grid; gap: 6px; color: var(--muted); font-size: 12px; font-weight: 760; }
  .setting-field input,
  .setting-field select,
  .setting-field textarea { width: 100%; min-width: 0; border: 1px solid var(--line); border-radius: 8px; padding: 9px 10px; background: #fff; color: var(--text); box-sizing: border-box; }
  .setting-field textarea { min-height: 92px; resize: vertical; line-height: 1.55; }
  .setting-field.full { grid-column: 1 / -1; }
  .print-toggle-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 8px; }
  .print-toggle { display: flex; align-items: center; gap: 8px; min-height: 40px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 0 10px; color: var(--text); font-size: 13px; font-weight: 760; }
  .print-toggle input { width: 16px; height: 16px; accent-color: var(--accent); }
  .print-settings-actions { display: flex; flex-wrap: wrap; gap: 9px; justify-content: flex-end; padding-top: 2px; }
  .print-settings-actions button { height: 38px; padding: 0 14px; }
  .settings-tabs { width: fit-content; margin-top: -4px; }
  .print-template-note { border: 1px dashed var(--line-strong); border-radius: 8px; background: #fbfcfd; padding: 10px 12px; color: var(--muted); font-size: 13px; line-height: 1.6; }
  @media (max-width: 760px) {
    .settings-grid { grid-template-columns: 1fr; }
    .settings-panel-head { display: grid; }
  }
  @media (max-width: 760px) {
    .record-main,
    .user-main,
    .user-controls { grid-template-columns: 1fr; }
    .customer-metrics .record-metric:first-child { grid-column: auto; }
  }
  .context-inventory-list { display: grid; gap: 10px; }
  .context-inventory-card { padding: 10px; box-shadow: none; }
  .context-inventory-card .card-top { margin-bottom: 8px; align-items: center; }
  .context-inventory-card .inventory-title h3 { font-size: 13px; line-height: 1.35; }
  .context-inventory-card .inventory-total { text-align: right; min-width: 56px; }
  .context-inventory-card .inventory-total strong { display: block; color: var(--accent); font-size: 22px; line-height: 1; }
  .context-inventory-card .inventory-total span { color: var(--muted); font-size: 11px; font-weight: 700; }
  .context-inventory-card .table-lite { font-size: 12px; }
  .context-inventory-card .table-lite th,
  .context-inventory-card .table-lite td { padding: 7px 5px; white-space: nowrap; }
  .context-inventory-card .table-lite th:nth-child(n+2),
  .context-inventory-card .table-lite td:nth-child(n+2) { text-align: right; }
  .business-summary { display: grid; gap: 10px; }
  .business-summary h4 { margin: 0; font-size: 15px; color: var(--text); }
  .business-summary p { margin: 0; color: var(--muted); line-height: 1.55; font-size: 13px; }
  .business-summary p b { color: var(--text); }
  .summary-lines { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
  .summary-lines li { display: flex; flex-wrap: wrap; gap: 6px 9px; align-items: center; padding: 9px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); font-size: 13px; line-height: 1.45; }
  .summary-lines li strong { color: var(--text); }
  .summary-lines li span { color: var(--muted); }
  .bag-preview-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .bag-preview-item { display: grid; gap: 6px; min-width: 0; color: var(--muted); font-size: 12px; text-decoration: none; }
  .bag-preview-item span { color: var(--text); font-weight: 700; }
  .bag-preview-item img { width: 100%; height: 116px; object-fit: contain; border: 1px solid var(--line); border-radius: 8px; background: #f8f8f8; }
  .summary-note { padding-top: 4px; border-top: 1px solid var(--line); }
  .history-card { display: grid; gap: 8px; }
  #contextCards { display: grid; gap: 12px; margin-top: 12px; }
  .history-card .history-body { display: grid; gap: 5px; font-size: 13px; line-height: 1.5; color: var(--muted); }
  .history-card .history-body p { margin: 0; }
  .history-card .history-body b { color: var(--text); }
  .compact-actions { grid-template-columns: 1fr; margin-top: 4px; }
  .compact-actions button { height: 32px; min-height: 32px; font-size: 12px; }
  .confirm-edit-form { gap: 12px; }
  .confirm-edit-line { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; padding: 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); }
  .confirm-edit-line .line-title { grid-column: 1 / -1; font-size: 12px; font-weight: 800; color: var(--text); }
  .confirm-field { display: grid; gap: 4px; color: var(--muted); font-size: 12px; }
  .confirm-field input, .confirm-field select { width: 100%; min-width: 0; height: 34px; border: 1px solid var(--line); border-radius: 7px; padding: 0 9px; background: #fff; color: var(--text); font-size: 13px; box-sizing: border-box; }
  .confirm-field input:focus, .confirm-field select:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(31,138,112,.12); }
  .sale-create-actions { display: flex; align-items: center; gap: 10px; }
  .sale-create-shell { display: grid; gap: 14px; }
  .sale-order-card { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); box-shadow: var(--shadow); padding: 16px; display: grid; gap: 16px; }
  .sale-panel { display: grid; gap: 13px; }
  .sale-basic-panel { padding-bottom: 16px; border-bottom: 1px solid var(--line); }
  .sale-panel-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .sale-panel-head > div { display: grid; gap: 3px; min-width: 0; }
  .sale-panel-head strong { color: var(--text); font-size: 18px; line-height: 1.2; }
  .sale-panel-head span { color: var(--muted); font-size: 13px; line-height: 1.4; }
  .sale-panel-head select { width: 142px; height: 38px; border: 1px solid var(--line); border-radius: 8px; padding: 0 10px; background: #fff; color: var(--text); }
  .sale-basic-grid { display: grid; grid-template-columns: minmax(280px, 1.4fr) minmax(220px, .7fr) minmax(220px, .9fr); gap: 12px; align-items: start; }
  .sale-field { display: grid; gap: 7px; min-width: 0; }
  .sale-field label { color: var(--muted); font-size: 12px; font-weight: 700; }
  .sale-field > input,
  .sale-field > select,
  .sale-readonly { width: 100%; height: 42px; min-width: 0; border: 1px solid var(--line); border-radius: 8px; padding: 0 12px; background: #fff; color: var(--text); font-size: 14px; box-sizing: border-box; display: flex; align-items: center; }
  .sale-readonly { background: #f8fafc; font-weight: 760; }
  .sale-search-row { display: grid; grid-template-columns: minmax(0, 1fr) 112px; gap: 10px; }
  .sale-customer-row { grid-template-columns: minmax(0, 1fr) 112px 112px; }
  .sale-search-row input,
  .sale-product-search-cell input { min-width: 0; height: 42px; border: 1px solid var(--line); border-radius: 8px; padding: 0 12px; background: #fff; color: var(--text); font-size: 14px; }
  .sale-field > input:focus,
  .sale-field > select:focus,
  .sale-search-row input:focus,
  .sale-product-search-cell input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(31,138,112,.12); }
  .sale-choice-list { display: grid; gap: 8px; max-height: 230px; overflow: auto; }
  .sale-choice-list:empty { display: none; }
  .sale-choice-list .choice { width: 100%; text-align: left; display: grid; gap: 3px; padding: 10px 12px; border-radius: 8px; background: #f8fafc; border: 1px solid var(--line); color: var(--text); box-shadow: none; }
  .sale-choice-list .choice:hover { border-color: var(--accent); background: #f7fbf9; }
  .sale-lines-panel { min-height: 360px; overflow: hidden; }
  .sale-lines-table-wrap { overflow: auto; border: 1px solid var(--line); border-radius: 9px; background: #fff; }
  .sale-lines-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 880px; }
  .sale-lines-table th,
  .sale-lines-table td { padding: 10px 9px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: middle; }
  .sale-lines-table th { position: sticky; top: 0; z-index: 1; background: #f8fafc; color: var(--muted); font-size: 12px; font-weight: 800; }
  .sale-lines-table tbody tr:hover { background: #fbfcfb; }
  .sale-lines-table tfoot td { background: #fbfcfb; border-bottom: 0; border-top: 1px solid var(--line); vertical-align: top; }
  .sale-search-table-row input,
  .sale-search-table-row select { height: 38px; }
  .sale-product-search-cell { position: relative; display: grid; gap: 8px; }
  .sale-product-search-cell .sale-choice-list { max-height: 190px; }
  .sale-search-table-btn { width: 100%; height: 38px; min-height: 38px; }
  .sale-lines-table .sale-product-name { min-width: 190px; font-weight: 800; color: var(--text); }
  .sale-lines-table .sale-product-sub { color: var(--muted); font-size: 11px; margin-top: 3px; }
  .sale-lines-table input,
  .sale-lines-table select { width: 100%; min-width: 0; height: 34px; border: 1px solid var(--line); border-radius: 7px; padding: 0 8px; background: #fff; color: var(--text); box-sizing: border-box; font-size: 13px; }
  .sale-lines-table .qty-cell { width: 92px; }
  .sale-lines-table .warehouse-cell { width: 132px; }
  .sale-lines-table .price-cell { width: 112px; }
  .sale-lines-table .amount-cell { width: 118px; color: var(--accent); font-weight: 850; }
  .sale-lines-table .operate-cell { width: 76px; }
  .sale-lines-table .remove-line { height: 32px; min-height: 32px; padding: 0 10px; color: var(--coral); border-color: #ffd0cd; background: #fff; }
  .sale-table-empty { text-align: center !important; color: var(--muted); padding: 34px 8px !important; background: #fff; }
  .sale-table-footer { display: flex; flex-wrap: wrap; gap: 14px; justify-content: flex-end; align-items: center; padding: 12px 2px 14px; color: var(--muted); font-size: 13px; }
  .sale-table-footer strong { color: var(--accent); font-size: 16px; }
  .sale-total-pill { color: var(--accent); font-size: 22px; font-weight: 850; white-space: nowrap; }
  .sale-submit-bar { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(150px, auto) auto minmax(220px, 320px); gap: 12px; align-items: center; padding: 14px 0 0; border-top: 1px solid var(--line); position: sticky; bottom: 0; z-index: 5; background: var(--surface); }
  .sale-submit-bar > div:not(.sale-result-card):not(.sale-submit-actions) { display: grid; gap: 3px; min-width: 0; }
  .sale-submit-bar span { color: var(--muted); font-size: 12px; }
  .sale-submit-bar strong { color: var(--text); font-size: 18px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .sale-submit-bar #saleSubmitAmount { color: var(--accent); font-size: 22px; }
  .sale-submit-actions { display: flex; align-items: center; gap: 8px; }
  .sale-result-card { border: 1px dashed var(--line-strong); border-radius: 9px; padding: 12px; display: grid; gap: 9px; background: #fff; color: var(--muted); font-size: 13px; line-height: 1.6; }
  .sale-result-card strong { color: var(--text); font-size: 15px; }
  .sale-result-card p { margin: 0; }
  .sale-result-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .sale-result-actions button { height: 34px; min-height: 34px; padding: 0 10px; }
  .sale-variant-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; margin-top: 12px; }
  .sale-variant-card { border: 1px solid var(--line); border-radius: 9px; background: #f8fafc; padding: 10px; display: grid; gap: 8px; text-align: left; cursor: pointer; }
  .sale-variant-card:hover { border-color: var(--accent); background: #f7fbf9; }
  .sale-variant-card strong { color: var(--text); font-size: 15px; }
  .sale-variant-meta { display: flex; flex-wrap: wrap; gap: 6px; color: var(--muted); font-size: 12px; }
  .sale-variant-meta span { padding: 3px 7px; border-radius: 999px; border: 1px solid var(--line); background: #fff; }
  .customer-create-form { display: grid; gap: 12px; margin-top: 12px; }
  .customer-create-form label { display: grid; gap: 6px; color: var(--muted); font-size: 12px; font-weight: 700; }
  .customer-create-form input { width: 100%; height: 40px; min-width: 0; border: 1px solid var(--line); border-radius: 8px; padding: 0 11px; background: #fff; color: var(--text); font-size: 14px; box-sizing: border-box; }
  .customer-create-form input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(31,138,112,.12); }
  @media (max-width: 1180px) {
    .sale-basic-grid { grid-template-columns: 1fr 1fr; }
    .sale-submit-bar { grid-template-columns: 1fr 1fr; position: static; }
    .sale-submit-actions,
    .sale-result-card { grid-column: 1 / -1; }
  }
  @media (max-width: 760px) {
    .sale-create-actions { width: 100%; display: grid; grid-template-columns: 1fr 1fr; }
    .sale-basic-grid,
    .sale-search-row { grid-template-columns: 1fr; }
    .sale-panel-head { align-items: stretch; flex-direction: column; }
    .sale-panel-head select { width: 100%; }
    .sale-submit-bar { grid-template-columns: 1fr; }
  }
  @media (min-width: 1800px) and (min-height: 1000px) {
    #inventoryList.section-grid { --card-min-width: 430px; column-width: 430px; column-gap: 16px; }
    #inventoryList .inventory-card { padding: 18px; }
  }
  #productCategoryBar { display: grid; gap: 8px; padding: 0 0 12px; margin-top: -2px; overflow: visible; }
  #productCategoryBar .product-category-level { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; min-width: 0; }
  #productCategoryBar .product-category-child { padding: 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); }
  #productCategoryBar button { flex: 0 0 auto; height: 34px; min-height: 34px; padding: 0 12px; border-radius: 999px; font-size: 13px; }
  #productCategoryBar .product-category-child button { height: 30px; min-height: 30px; font-size: 12px; background: #fff; }
  #productCategoryBar button.active { background: #111; border-color: #111; color: #fff; }
  #productList.section-grid { --card-min-width: 260px; grid-template-columns: repeat(auto-fill, minmax(var(--card-min-width), 1fr)); gap: 14px; align-items: start; }
  #productList .product-card { display: grid; grid-template-rows: auto 1fr; overflow: hidden; min-height: 430px; }
  #productList .product-image { aspect-ratio: 1 / 1; height: auto; min-height: 0; }
  #productList .product-image::before,
  #productList .product-image::after { display: none; }
  #productList .product-image img { width: 100%; height: 100%; object-fit: cover; display: block; }
  #productList .product-body { display: grid; gap: 11px; padding-bottom: 12px; }
  #productList .product-body h3 { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 40px; }
  #productList .tag { min-height: 20px; padding: 2px 7px; border-radius: 999px; font-size: 11px; line-height: 1; border-width: 1px; }
  .tag.gold { background: #f8edcf; color: #75520d; border-color: #e3c678; }
  .tag.muted-tag { background: #eee8da; color: #7b7263; border-color: #d8cdbb; }
  #productList .product-title-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: start; gap: 8px; }
  #productList .product-count { display: inline-flex; align-items: center; justify-content: center; height: 22px; padding: 0 8px; border-radius: 999px; background: #27834f; color: #fff; font-size: 11px; font-weight: 760; white-space: nowrap; }
  #productList .product-color-summary { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 34px; line-height: 1.45; }
  #productList .product-price-row { display: grid; gap: 3px; font-size: 12px; color: var(--muted); }
  #productList .product-price-row strong { color: var(--accent); font-size: 15px; }
  #productList .product-price-row span { color: var(--muted); font-weight: 760; }
  #productList .product-spec-list { display: none; }
  #productList .product-spec-line { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; column-gap: 8px; font-size: 12px; color: #2b2824; }
  #productList .product-spec-line span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #productList .product-spec-line strong { color: var(--accent); font-size: 12px; }
  #productList .product-spec-line em { grid-column: 1 / -1; color: var(--muted); font-style: normal; font-size: 10px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #productList .product-spec-more { color: var(--muted); font-size: 11px; }
  #productList .product-tags { display: flex; flex-wrap: wrap; gap: 5px; }
  #productList .tag,
  #inventoryList .tag,
  #workflowList .tag { min-height: 24px; padding: 2px 8px; border-radius: 999px; font-size: 12px; line-height: 1; border-width: 1px; font-weight: 500; }
  .tag.green-outline { background: #fff; color: var(--accent); border-color: #b9e3cf; }
  .tag.gray { background: #f2f0eb; color: #70685c; border-color: #d5cec2; }
  #productList .card-actions { display: flex; flex-wrap: wrap; justify-content: flex-start; gap: 8px; margin-top: auto; padding-top: 10px; border-top: 1px solid var(--line); }
  #productList .card-actions button { min-width: 0; min-height: 34px; height: 34px; padding: 0 10px; font-size: 13px; display: inline-flex; align-items: center; justify-content: center; }
  #productList .card-actions .product-shelf-button { background: #27834f; border-color: #27834f; color: #fff; }
  #productList .card-actions .product-shelf-button:hover { background: #216f43; border-color: #216f43; }
  .product-image-editor { display: grid; gap: 8px; }
  .product-main-image-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
  .product-image-preview { aspect-ratio: 1 / 1; width: min(180px, 100%); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; background: #f4f1ea; display: grid; place-items: center; color: var(--muted); font-size: 12px; padding: 0; cursor: pointer; }
  .product-image-preview img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .product-image-preview,
  .product-detail-item,
  .product-spec-image,
  .product-spec-upload { position: relative; }
  .product-image-preview.empty-upload,
  .product-upload-tile,
  .product-spec-image.empty-upload { border-style: dashed; border-color: #9ca3af; background: #e5e7eb; color: #4b5563; align-content: center; gap: 4px; }
  .product-image-preview.empty-upload span,
  .product-upload-tile span,
  .product-spec-image.empty-upload span { display: block; font-size: 24px; line-height: 1; font-weight: 760; }
  .product-image-preview.empty-upload strong,
  .product-upload-tile strong,
  .product-spec-image.empty-upload strong { display: block; font-size: 12px; line-height: 1; }
  .product-image-remove { position: absolute; top: 4px; right: 4px; width: 22px; height: 22px; border-radius: 999px; background: rgba(17,17,17,.78); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 16px; line-height: 1; z-index: 2; }
  .product-image-upload { width: min(180px, 100%); aspect-ratio: 1 / 1; border: 1px dashed var(--line-strong); border-radius: var(--radius); display: grid; place-items: center; align-content: center; gap: 4px; cursor: pointer; color: var(--text); background: var(--surface-2); font-size: 14px; font-weight: 760; }
  .product-image-upload span { display: block; color: var(--muted); font-size: 11px; font-weight: 600; }
  .product-category-editor { display: flex; flex-wrap: wrap; gap: 7px; }
  .product-category-editor button { min-height: 32px; height: 32px; padding: 0 10px; border-radius: 999px; font-size: 12px; }
  .product-category-editor button.active { background: #111; border-color: #111; color: #fff; }
  .product-detail-grid { display: flex; flex-wrap: wrap; gap: 8px; }
  .product-detail-item { position: relative; width: 82px; height: 82px; border-radius: 8px; border: 1px solid var(--line); overflow: hidden; background: #f4f1ea; }
  .product-detail-item img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .product-upload-tile { display: grid; place-items: center; padding: 0; cursor: pointer; }
  .product-main-upload { width: 82px; height: 82px; }
  .product-detail-remove { position: absolute; top: 4px; right: 4px; width: 22px; height: 22px; min-height: 0; padding: 0; border-radius: 999px; background: rgba(17,17,17,.78); border-color: rgba(17,17,17,.78); color: #fff; line-height: 1; }
  .product-section-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .product-section-row label { margin: 0; }
  .asset-picker-box { width: min(920px, 96vw); max-height: 88vh; overflow: auto; }
  .asset-picker-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
  .asset-picker-head .confirm-message { margin-bottom: 0; }
  .asset-picker-actions { display: flex; justify-content: flex-end; padding: 10px 0; }
  .asset-picker-search { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; margin-bottom: 10px; }
  .asset-picker-search input { width: 100%; height: 36px; border: 1px solid var(--line); border-radius: 8px; padding: 0 10px; background: #fff; color: var(--text); box-sizing: border-box; }
  .asset-picker-search input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(31,138,112,.12); }
  .asset-picker-search button { height: 36px; min-height: 36px; padding: 0 10px; border-radius: 8px; font-size: 12px; background: #fff; }
  .asset-picker-tabs { margin-bottom: 10px; }
  .asset-picker-tabs button.active { background: #111; border-color: #111; color: #fff; }
  .asset-picker-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(118px, 1fr)); gap: 10px; }
  .asset-group-bar { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 14px; }
  .asset-group-bar button { height: 32px; min-height: 32px; padding: 0 10px; border-radius: 999px; font-size: 12px; background: #fff; }
  .asset-group-bar button.active { background: #111; border-color: #111; color: #fff; }
  .asset-head-actions { display: flex; align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }
  .asset-pick-card { display: grid; gap: 6px; padding: 7px; border-radius: 8px; border: 1px solid var(--line); background: var(--surface-2); color: var(--text); text-align: left; min-height: 0; height: auto; }
  .asset-pick-card:hover { border-color: var(--accent); background: #f7fbf9; }
  .asset-pick-card img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 7px; border: 1px solid var(--line); background: #f4f1ea; }
  .asset-pick-card strong { color: var(--text); font-size: 12px; line-height: 1.25; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asset-pick-card span { color: var(--muted); font-size: 12px; font-weight: 760; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asset-pick-card em { color: var(--muted); font-style: normal; font-size: 11px; line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #productAssetList.section-grid { display: block; }
  .asset-product-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 10px; align-items: start; }
  .asset-product-grid.compact { grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
  .asset-product-card { border: 1px solid var(--line); border-radius: 8px; background: var(--surface); box-shadow: 0 5px 14px rgba(31, 24, 15, .04); padding: 10px; display: grid; gap: 9px; min-width: 0; content-visibility: auto; contain-intrinsic-size: 260px; }
  .asset-product-card.compact { box-shadow: none; }
  .asset-product-top { display: grid; grid-template-columns: 84px minmax(0, 1fr); gap: 10px; align-items: start; min-width: 0; }
  .asset-product-top img { width: 84px; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 7px; border: 1px solid var(--line); background: #f4f1ea; }
  .asset-product-top h3 { margin: 0; color: var(--text); font-size: 14px; line-height: 1.28; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asset-product-top p { margin: 3px 0 0; color: var(--muted); font-size: 12px; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asset-product-top span { display: block; margin-top: 5px; color: var(--muted); font-size: 11px; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asset-count-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
  .asset-count-row div { border: 1px solid var(--line); border-radius: 7px; background: var(--surface-2); padding: 6px 7px; display: flex; justify-content: space-between; gap: 6px; align-items: center; min-width: 0; }
  .asset-count-row span { color: var(--muted); font-size: 11px; white-space: nowrap; }
  .asset-count-row strong { color: var(--accent); font-size: 14px; line-height: 1; }
  .asset-mini-strip { display: grid; grid-template-columns: repeat(5, 1fr); gap: 5px; min-height: 42px; }
  .asset-mini-strip.empty { display: grid; place-items: center; border: 1px dashed var(--line); border-radius: 7px; color: var(--muted); font-size: 12px; background: var(--surface-2); }
  .asset-mini-strip img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 6px; border: 1px solid var(--line); background: #f4f1ea; min-width: 0; }
  .asset-open-button { height: 32px; min-height: 32px; border-radius: 8px; font-size: 12px; background: #fff; }
  .asset-category-list { display: grid; gap: 12px; }
  .asset-category-section { display: grid; gap: 10px; }
  .asset-category-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 2px 1px 0; }
  .asset-category-head h2 { margin: 0; font-size: 17px; color: var(--text); }
  .asset-category-head p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
  .asset-card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 10px; align-items: start; }
  .asset-card { position: relative; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); box-shadow: 0 5px 14px rgba(31, 24, 15, .04); overflow: hidden; display: grid; grid-template-rows: auto 1fr; content-visibility: auto; contain-intrinsic-size: 240px; }
  .asset-delete { position: absolute; top: 6px; right: 6px; z-index: 2; width: 24px; height: 24px; min-height: 0; padding: 0; border-radius: 999px; background: rgba(17,17,17,.76); border-color: rgba(17,17,17,.76); color: #fff; font-size: 16px; line-height: 1; }
  .asset-card > img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; display: block; background: #f4f1ea; border-bottom: 1px solid var(--line); }
  .asset-card-body { padding: 8px; display: grid; gap: 7px; min-width: 0; }
  .asset-card h3 { margin: 0; font-size: 13px; line-height: 1.25; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asset-card p { margin: 0; color: var(--muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asset-card .record-main { align-items: start; gap: 8px; }
  .asset-card .tag { font-size: 11px; padding: 3px 7px; }
  .asset-card-meta { display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 11px; min-width: 0; }
  .asset-card-meta span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asset-list-summary { grid-column: 1 / -1; color: var(--muted); font-size: 12px; text-align: right; padding: 2px 4px; }
  .asset-detail-box { width: min(960px, 96vw); max-height: 90vh; overflow: auto; }
  .asset-detail-sections { display: grid; gap: 12px; margin-top: 12px; }
  .asset-detail-section { display: grid; gap: 8px; }
  .asset-detail-section-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .asset-detail-section-head strong { color: var(--text); font-size: 14px; }
  .asset-detail-section-head span { color: var(--muted); font-size: 12px; }
  .asset-detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(112px, 1fr)); gap: 9px; }
  .asset-detail-tile { position: relative; display: grid; gap: 5px; padding: 6px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); min-width: 0; }
  .asset-detail-tile img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; border-radius: 7px; border: 1px solid var(--line); background: #f4f1ea; }
  .asset-detail-tile span { color: var(--muted); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .asset-color-list { display: grid; gap: 10px; }
  .asset-color-block { display: grid; gap: 7px; }
  .asset-color-block h4 { margin: 0; color: var(--text); font-size: 13px; }
  .product-media-assets { display: grid; gap: 8px; max-height: 260px; overflow: auto; border: 1px solid var(--line); border-radius: 8px; padding: 8px; background: #fff; }
  .product-media-empty { color: var(--muted); font-size: 12px; text-align: center; padding: 14px 8px; border: 1px dashed var(--line); border-radius: 8px; background: var(--surface-2); }
  .product-media-asset { display: grid; grid-template-columns: 54px minmax(0, 1fr); gap: 9px; align-items: center; padding: 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); }
  .product-media-asset.pending { border-style: dashed; background: #fffaf1; }
  .product-media-asset img { width: 54px; height: 54px; border-radius: 7px; border: 1px solid var(--line); object-fit: cover; background: #f4f1ea; }
  .product-media-asset strong { color: var(--text); font-size: 13px; line-height: 1.2; }
  .product-media-asset span { display: block; color: var(--muted); font-size: 11px; line-height: 1.4; margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .product-media-actions { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 6px; }
  .product-media-actions button { height: 28px; min-height: 28px; padding: 0 8px; border-radius: 999px; font-size: 11px; }
  .product-spec-card { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface-2); padding: 10px; display: grid; gap: 9px; }
  .product-spec-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; font-weight: 760; }
  .product-spec-image-row { display: flex; gap: 10px; align-items: center; }
  .product-spec-image,
  .product-spec-upload { width: 74px; height: 74px; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; display: grid; place-items: center; color: var(--muted); font-size: 12px; padding: 0; cursor: pointer; }
  .product-spec-image { background: #ebe7df; }
  .product-spec-image img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .product-spec-upload strong { font-size: 11px; }
  .drawer-form .block-action { width: 100%; height: 38px; display: inline-flex; align-items: center; justify-content: center; }
  @media (min-width: 1800px) and (min-height: 1000px) {
    #productList.section-grid { --card-min-width: 245px; gap: 14px; }
  }
  #salesList.section-grid { --sales-card-height: 382px; --sales-product-height: 104px; --card-min-width: 360px; grid-template-columns: repeat(auto-fill, minmax(var(--card-min-width), 1fr)); align-items: start; grid-auto-rows: auto; }
  #salesList .sales-card { min-height: var(--sales-card-height); height: auto; min-width: 0; display: grid; grid-template-rows: auto auto minmax(82px, var(--sales-product-height)) auto auto; gap: 10px; margin-bottom: 0; overflow: visible; cursor: pointer; }
  #salesList .customer-name strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #salesList .product-lines { gap: 8px; padding: 10px; height: var(--sales-product-height); overflow: hidden; position: relative; align-content: start; margin-top: 0; }
  #salesList .product-lines.has-more::after { content: ""; position: absolute; bottom: 0; left: 0; right: 0; height: 28px; background: linear-gradient(transparent, #f8fafc); pointer-events: none; }
  #salesList .product-row { grid-template-columns: minmax(0, 1fr) 48px 76px 86px; align-items: start; font-size: 13px; }
  #salesList .product-name { white-space: normal; overflow: visible; text-overflow: clip; line-height: 1.4; }
  #salesList .product-unit-price { text-align: right; color: var(--muted); font-weight: 760; white-space: nowrap; }
  #salesList .kv { margin: 0; }
  #salesList .product-price,
  #salesList .kv-row:nth-child(2) strong,
  .sales-detail-table td:nth-child(3),
  .sales-detail-table td:nth-child(4) { color: var(--accent); font-weight: 800; }
  #salesList .card-actions { align-self: end; margin-top: 0; padding-top: 8px; border-top: 1px solid var(--line); position: relative; z-index: 3; background: var(--surface); }
  #salesList .card-actions button { min-height: 34px; }
  .expand-btn { display: block; width: 100%; text-align: center; padding: 6px 0 2px; color: var(--muted); font-size: 12px; background: none; border: none; cursor: pointer; position: relative; z-index: 1; }
  .expand-btn:hover { color: var(--text); }
  .sales-detail-bill { display: grid; gap: 10px; }
  .sales-detail-head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
  .sales-detail-head p { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
  .sales-detail-metrics { grid-template-columns: repeat(auto-fit, minmax(148px, 1fr)); }
  .sales-detail-table-wrap { max-height: 56vh; overflow: auto; border: 1px solid var(--line); border-radius: 8px; }
  .sales-detail-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .sales-detail-table th,
  .sales-detail-table td { padding: 9px 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
  .sales-detail-table th { position: sticky; top: 0; background: #f8fafc; color: var(--muted); z-index: 1; }
  .sales-detail-table td:nth-child(1),
  .sales-detail-table td:nth-child(3),
  .sales-detail-table td:nth-child(4),
  .sales-detail-table td:nth-child(5) { white-space: nowrap; }
  .sales-flow-section { display: grid; gap: 8px; margin-top: 12px; }
  .sales-flow-section h3 { margin: 0; color: var(--text); font-size: 14px; }
  .sales-flow-list { display: grid; gap: 8px; }
  .sales-flow-row { border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 9px 10px; display: grid; gap: 3px; }
  .sales-flow-row strong { color: var(--text); font-size: 13px; }
  .sales-flow-row span,
  .sales-flow-row em { color: var(--muted); font-size: 12px; font-style: normal; }
  .sales-delete-flow { display: grid; gap: 6px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 10px; }
  .sales-delete-flow span { color: var(--text); font-size: 12px; line-height: 1.45; }
  @media (min-width: 1800px) and (min-height: 1000px) {
    #salesList.section-grid { --sales-card-height: 318px; --sales-product-height: 82px; --card-min-width: 330px; grid-template-columns: repeat(auto-fill, minmax(var(--card-min-width), 1fr)); }
    #salesList .sales-card { padding: 12px; gap: 8px; }
    #salesList .customer-name { padding-bottom: 8px; }
    #salesList .customer-name strong { font-size: 16px; }
    #salesList .product-lines { padding: 8px; gap: 6px; }
    #salesList .product-row { grid-template-columns: minmax(0, 1fr) 42px 64px 72px; gap: 6px; font-size: 12px; }
    #salesList .kv { gap: 6px; }
    #salesList .kv-row { font-size: 12px; }
    #salesList .card-actions { padding-top: 7px; }
    #salesList .card-actions button { min-height: 31px; padding: 0 9px; font-size: 12px; }
    #salesList .expand-btn { padding-top: 4px; font-size: 12px; }
  }
  .thumb-strip { display: flex; gap: 7px; overflow: auto; }
  .thumb { width: 64px; height: 54px; object-fit: cover; border-radius: 7px; border: 1px solid var(--line); background: #f5f3ee; }
  .swatch { width: 12px; height: 12px; border-radius: 99px; border: 1px solid rgba(0,0,0,.18); display: inline-block; vertical-align: middle; margin-right: 5px; }
  .message-image { display: block; width: min(260px, 100%); max-height: 180px; object-fit: contain; border: 1px solid var(--line); border-radius: 8px; margin-top: 8px; background: #f5f3ee; }
  .image-chip { display: inline-flex; align-items: center; gap: 8px; border-radius: 10px; padding: 5px 8px 5px 5px; }
  .image-chip img { width: 42px; height: 34px; object-fit: cover; border-radius: 7px; border: 1px solid var(--line); background: #f5f3ee; }
  .image-chip span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .admin-only { display: none; }
  body.is-admin .admin-only { display: block; }
  #accountAdminButton strong, #accountAdminButton span { pointer-events: none; }
  .chat-head-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; justify-content: flex-end; }
  .approval-list { display: grid; gap: 10px; }
  .approval-card { border: 1px solid var(--line); border-radius: 8px; background: var(--surface-2); padding: 12px; display: grid; gap: 10px; }
  .approval-card strong { color: var(--text); font-size: 15px; }
  .approval-meta { color: var(--muted); font-size: 12px; line-height: 1.5; }
  .approval-actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .approval-actions button { min-height: 34px; padding: 0 12px; }
  .md-table-wrap { overflow: auto; border: 1px solid var(--line); border-radius: 8px; margin: 8px 0; }
  .md-table { width: 100%; border-collapse: collapse; }
  .md-table th,
  .md-table td { padding: 8px; border-bottom: 1px solid var(--line); white-space: nowrap; text-align: left; }
  .md-table th { background: #f8fafc; color: var(--muted); }
  .drawer.open { transform: translate(-50%, -50%) scale(1); }
  .drawer-mask.open { opacity: 1; pointer-events: auto; backdrop-filter: blur(2px); }
  .loading { opacity: .6; pointer-events: none; }
  #orders.view.active { display: block; }
  .order-visual { position: relative; overflow: hidden; }
  .order-visual-caption { position: absolute; left: 10px; bottom: 9px; padding: 4px 8px; border-radius: 999px; background: rgba(255,255,255,.82); color: var(--muted); font-size: 12px; font-weight: 700; }
  .loading-placeholder { grid-column: 1 / -1; display: flex; align-items: center; justify-content: center; gap: 10px; padding: 40px 0; color: var(--muted); font-size: 14px; }
  .spinner { width: 20px; height: 20px; border: 2.5px solid var(--line); border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .skeleton { background: linear-gradient(90deg, var(--surface-2) 25%, var(--surface-1) 50%, var(--surface-2) 75%); background-size: 200% 100%; animation: shimmer 1.2s ease-in-out infinite; border-radius: 6px; }
  @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  .skeleton-card { border: 1px solid var(--line); border-radius: var(--radius); padding: 14px; display: grid; gap: 10px; }
  .skeleton-card .sk-head { display: flex; justify-content: space-between; }
  .skeleton-card .sk-line { height: 14px; }
  .skeleton-card .sk-line.w60 { width: 60%; }
  .skeleton-card .sk-line.w40 { width: 40%; }
  .skeleton-card .sk-line.w80 { width: 80%; }
  .skeleton-card .sk-line.h20 { height: 20px; }
  .skeleton-card .sk-row { display: flex; justify-content: space-between; }
  .skeleton-card .sk-actions { display: flex; gap: 8px; justify-content: flex-end; padding-top: 8px; border-top: 1px solid var(--line); }
  .skeleton-card .sk-btn { width: 64px; height: 30px; border-radius: 6px; }
  .pager { display: inline-flex; align-items: center; gap: 4px; }
  .pager button { min-width: 40px; height: 36px; padding: 0 14px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface-2); color: var(--text); font-size: 14px; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; }
  .pager button:hover:not(:disabled) { background: var(--surface-1); border-color: var(--accent); }
  .pager button:disabled { opacity: .35; cursor: default; }
  .pager .page-info { font-size: 12px; color: var(--muted); padding: 0 6px; white-space: nowrap; }
  .card-actions button.loading { opacity: .6; pointer-events: none; }
  .tag-gray { border: 1.5px solid #b0aaa0; background: #f0ece4; color: #6b6459; }
  .tag-outline { border: 1.5px solid #333; background: #fff; color: #333; }
  .lightbox-overlay { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; opacity: 0; pointer-events: none; transition: opacity .22s ease; }
  .lightbox-overlay.open { opacity: 1; pointer-events: auto; }
  .lightbox-mask { position: absolute; inset: 0; background: rgba(0,0,0,.72); backdrop-filter: blur(6px); }
  .lightbox-content { position: relative; z-index: 1; max-width: 90vw; max-height: 90vh; display: flex; align-items: center; justify-content: center; }
  .lightbox-img { max-width: 90vw; max-height: 88vh; border-radius: 10px; box-shadow: 0 20px 60px rgba(0,0,0,.45); object-fit: contain; }
  .lightbox-close { position: fixed; top: 18px; right: 22px; z-index: 2; width: 40px; height: 40px; border-radius: 99px; border: none; background: rgba(255,255,255,.18); color: #fff; font-size: 26px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background .15s; }
  .lightbox-close:hover { background: rgba(255,255,255,.35); }
  .lightbox-prev,
  .lightbox-next { position: fixed; top: 50%; z-index: 2; transform: translateY(-50%); width: 44px; height: 44px; border-radius: 99px; border: none; background: rgba(255,255,255,.18); color: #fff; font-size: 28px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background .15s; }
  .lightbox-prev { left: 16px; }
  .lightbox-next { right: 16px; }
  .lightbox-prev:hover,
  .lightbox-next:hover { background: rgba(255,255,255,.35); }
  #workflowList.section-grid { --workflow-card-height: 492px; --workflow-image-height: 150px; --card-min-width: 320px; grid-template-columns: repeat(auto-fill, minmax(var(--card-min-width), 1fr)); align-items: start; grid-auto-rows: var(--workflow-card-height); gap: 16px; }
  #workflowList .order-row { max-width: none; height: var(--workflow-card-height); min-height: 0; display: grid; grid-template-rows: var(--workflow-image-height) auto auto auto minmax(96px, 1fr); gap: 12px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); padding: 16px; overflow: hidden; box-shadow: 0 10px 24px rgba(31, 24, 15, .06); }
  #workflowList .order-row::before { display: none !important; content: none !important; }
  #workflowList .order-row > div { padding: 0; border-bottom: none !important; }
  #workflowList .order-visual { height: var(--workflow-image-height); width: 100%; cursor: pointer; border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; margin-bottom: 0; background: linear-gradient(135deg, rgba(255,255,255,.72), rgba(255,255,255,0)), #f0ece4; background-size: contain; background-repeat: no-repeat; background-position: center; }
  #workflowList .order-visual.has-image { background-color: transparent; }
  #workflowList .order-visual.has-image::after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0), rgba(0,0,0,.08)); pointer-events: none; }
  #workflowList .order-visual.has-image:hover { opacity: .94; }
  #workflowList .order-info-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 12px; min-height: 88px; }
  #workflowList .order-customer { display: grid; grid-template-columns: minmax(0, 1fr); gap: 3px; }
  #workflowList .order-customer strong { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 22px; line-height: 1.15; }
  #workflowList .order-customer .muted { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #workflowList .order-row > div:not(.order-visual):not(.card-actions):not(.order-goods-row):not(.order-status-strip):not(.order-info-row) { margin-bottom: 0; }
  #workflowList .order-time { min-height: 22px; display: flex; align-items: center; color: var(--muted); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #workflowList .card-actions { justify-content: stretch; align-self: end; align-content: flex-end; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; min-height: 88px; padding-top: 10px; border-top: 1px solid var(--line); margin-top: 0; background: var(--surface); position: relative; z-index: 2; }
  #workflowList .card-actions button { width: 100%; min-width: 0; height: 40px; min-height: 40px; padding: 0 9px; font-size: 12px; display: inline-flex; align-items: center; justify-content: center; line-height: 1; box-sizing: border-box; }
  #workflowList .order-goods-row { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 0; min-height: 44px; }
  #workflowList .order-goods-row strong { flex: 1; min-width: 0; line-height: 1.35; font-size: 20px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  #workflowList .order-qty-block { min-width: 86px; min-height: 76px; display: flex; align-items: flex-end; justify-content: flex-end; gap: 6px; padding-top: 8px; }
  #workflowList .order-qty-block span { font-size: 42px; line-height: .9; font-weight: 900; color: var(--accent); letter-spacing: 0; }
  #workflowList .order-qty-block strong { font-size: 18px; line-height: 1.1; font-weight: 850; color: #171512; margin-bottom: 4px; }
  #workflowList .order-status-strip { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-height: 28px; }
  @media (min-width: 1800px) and (min-height: 1000px) {
    #workflowList.section-grid { --workflow-card-height: 448px; --workflow-image-height: 134px; --card-min-width: 300px; grid-template-columns: repeat(auto-fill, minmax(var(--card-min-width), 1fr)); }
    #workflowList .order-row { padding: 14px; gap: 10px; grid-template-rows: var(--workflow-image-height) auto auto auto minmax(88px, 1fr); }
    #workflowList .order-customer strong { font-size: 15px; }
    #workflowList .order-goods-row { min-height: 38px; }
    #workflowList .order-qty-block { min-width: 74px; min-height: 62px; }
    #workflowList .order-qty-block span { font-size: 34px; }
    #workflowList .order-qty-block strong { font-size: 15px; }
    #workflowList .tag { min-height: 22px; padding: 2px 7px; font-size: 11px; }
    #workflowList .card-actions { min-height: 82px; padding-top: 8px; }
    #workflowList .card-actions button { height: 36px; min-height: 36px; }
  }
"""


LOGIN_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>北极星登录</title>
  <style>
    :root {
      --bg: #f6f3ed;
      --surface: #fff;
      --surface-2: #f8fafc;
      --text: #20242a;
      --muted: #77808d;
      --line: #dfe5ea;
      --accent: #0f8f78;
      --gold: #c89f5d;
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
      background:
        linear-gradient(135deg, rgba(255,255,255,.82), rgba(255,255,255,0) 42%),
        radial-gradient(circle at 18% 18%, rgba(200,159,93,.18), transparent 30%),
        var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
      letter-spacing: 0;
    }
    .shell {
      width: min(980px, 100%);
      display: grid;
      grid-template-columns: .92fr 1fr;
      gap: 18px;
      align-items: stretch;
    }
    .brand, .panel {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: rgba(255,255,255,.94);
      box-shadow: 0 24px 70px rgba(35, 32, 28, .12);
    }
    .brand {
      padding: 28px;
      display: grid;
      align-content: space-between;
      min-height: 540px;
      overflow: hidden;
      position: relative;
    }
    .brand::after {
      content: "";
      position: absolute;
      inset: auto -80px -120px auto;
      width: 320px;
      height: 320px;
      background: linear-gradient(135deg, rgba(15,143,120,.2), rgba(200,159,93,.18));
      transform: rotate(18deg);
    }
    .logo { display: flex; gap: 12px; align-items: center; position: relative; z-index: 1; }
    .mark {
      width: 42px;
      height: 42px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      background: #111;
      color: #f6d48a;
      font-weight: 850;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.12);
    }
    .logo strong { display: block; font-size: 18px; }
    .logo span { display: block; color: var(--muted); font-size: 12px; margin-top: 3px; }
    .brand-main { position: relative; z-index: 1; }
    .brand-main h1 { margin: 0 0 14px; font-size: 36px; line-height: 1.12; }
    .brand-main p { margin: 0; color: var(--muted); line-height: 1.8; font-size: 14px; }
    .chips { display: flex; gap: 8px; flex-wrap: wrap; position: relative; z-index: 1; }
    .chips span {
      border: 1px solid var(--line);
      background: var(--surface-2);
      border-radius: 999px;
      padding: 7px 10px;
      color: #39424e;
      font-size: 12px;
      font-weight: 700;
    }
    .panel { padding: 28px; display: grid; align-content: center; }
    .tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 22px; }
    .tabs button, .actions button {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--surface);
      color: var(--text);
      min-height: 42px;
      font-size: 14px;
      font-weight: 760;
      cursor: pointer;
    }
    .tabs button.active { background: #111; border-color: #111; color: #fff; }
    .form { display: grid; gap: 14px; }
    label { display: grid; gap: 7px; color: var(--muted); font-size: 13px; font-weight: 700; }
    input {
      width: 100%;
      min-height: 46px;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 0 13px;
      outline: none;
      color: var(--text);
      background: #fff;
      font-size: 15px;
    }
    input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(15,143,120,.12); }
    .actions { display: grid; grid-template-columns: 1fr; gap: 10px; margin-top: 6px; }
    .actions .primary { background: #111; border-color: #111; color: #fff; }
    .hint { color: var(--muted); font-size: 12px; line-height: 1.6; margin: 6px 0 0; }
    .msg { min-height: 20px; color: #d3544a; font-size: 13px; line-height: 1.5; }
    .msg.ok { color: var(--accent); }
    .register-only { display: none; }
    .is-register .register-only { display: grid; }
    @media (max-width: 760px) {
      body { padding: 14px; place-items: stretch; }
      .shell { grid-template-columns: 1fr; }
      .brand { min-height: 260px; padding: 22px; }
      .brand-main h1 { font-size: 28px; }
      .panel { padding: 20px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="brand">
      <div class="logo">
        <div class="mark">北</div>
        <div><strong>肆计包装</strong><span>北极星订单管理机器人</span></div>
      </div>
      <div class="brand-main">
        <h1>登录北极星工作台</h1>
        <p>开单、库存、工作流订单和商品资料都在这里处理。每个账号独立进入系统，减少误操作和会话混用。</p>
      </div>
      <div class="chips"><span>订单管理</span><span>库存查询</span><span>工作流</span><span>商品维护</span></div>
    </section>
    <section class="panel" id="authPanel">
      <div class="tabs">
        <button id="loginTab" class="active" type="button">登录</button>
        <button id="registerTab" type="button">注册</button>
      </div>
      <form class="form" id="authForm">
        <label>账号<input id="username" autocomplete="username" placeholder="请输入账号"></label>
        <label>密码<input id="password" type="password" autocomplete="current-password" placeholder="请输入密码"></label>
        <label class="register-only">显示名称<input id="displayName" placeholder="例如：杉"></label>
        <label class="register-only">确认密码<input id="password2" type="password" autocomplete="new-password" placeholder="再次输入密码"></label>
        <div class="msg" id="message"></div>
        <div class="actions"><button class="primary" id="submitButton" type="submit">登录进入</button></div>
        <p class="hint">注册后可直接登录。密码只保存加密摘要，不保存明文。</p>
      </form>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    let mode = "login";
    function setMode(next) {
      mode = next;
      $("authPanel").classList.toggle("is-register", mode === "register");
      $("loginTab").classList.toggle("active", mode === "login");
      $("registerTab").classList.toggle("active", mode === "register");
      $("submitButton").textContent = mode === "login" ? "登录进入" : "注册并进入";
      $("message").textContent = "";
      $("message").className = "msg";
    }
    async function post(url, body) {
      const res = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body)
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || (data.code && Number(data.code) !== 0)) throw new Error(data.msg || "操作失败");
      return data;
    }
    $("loginTab").onclick = () => setMode("login");
    $("registerTab").onclick = () => setMode("register");
    $("authForm").onsubmit = async (event) => {
      event.preventDefault();
      const message = $("message");
      message.className = "msg";
      message.textContent = "";
      const username = $("username").value.trim();
      const password = $("password").value;
      const displayName = $("displayName").value.trim();
      const password2 = $("password2").value;
      if (!username || !password) {
        message.textContent = "请输入账号和密码";
        return;
      }
      if (mode === "register" && password !== password2) {
        message.textContent = "两次密码不一致";
        return;
      }
      $("submitButton").disabled = true;
      try {
        const result = await post(mode === "login" ? "/api/web-auth/login" : "/api/web-auth/register", { username, password, display_name: displayName });
        message.className = "msg ok";
        if (result.data && result.data.pending) {
          message.textContent = "已提交注册，等待管理员审批后才能登录。";
          setMode("login");
        } else {
          message.textContent = "已登录，正在进入系统...";
          location.href = "/web";
        }
      } catch (err) {
        message.textContent = err.message;
      } finally {
        $("submitButton").disabled = false;
      }
    };
  </script>
</body>
</html>"""


TOOLS_HTML = """
      <div class="side-card api-tools" id="apiTools">
        <h3>API 操作台</h3>
        <p>所有按钮直接调用后端接口，聊天只做 AI 兜底。</p>

        <div class="tool-group">
          <label>库存关键词</label>
          <input id="quickInvKeyword" placeholder="例：见喜 3两 红色">
          <button class="primary" id="quickInvBtn">查询库存</button>
        </div>

        <div class="tool-group">
          <label>调货 / 进货商品</label>
          <input id="moveKeyword" placeholder="例：茶客 红色">
          <button id="moveProductSearchBtn">搜索并选择商品</button>
          <div class="choices" id="moveProductChoices"></div>
          <div class="tool-row">
            <div><label>数量</label><input id="moveQty" type="number" min="1" value="1"></div>
            <div><label>入库仓库</label><select id="moveWarehouse"><option value="1">自己店里</option><option value="2">百鑫仓库</option></select></div>
          </div>
          <div class="tool-row">
            <div><label>调出仓库</label><select id="moveTransferFrom"><option value="2">百鑫仓库</option><option value="1">自己店里</option></select></div>
            <div><label>调入仓库</label><select id="moveTransferTo"><option value="1">自己店里</option><option value="2">百鑫仓库</option></select></div>
          </div>
          <div class="tool-row">
            <button id="transferBtn">确认调货</button>
            <button class="primary" id="purchaseBtn">进货入库</button>
          </div>
          <p class="hint" id="moveSelectedHint">先搜索并选择商品，再执行。</p>
        </div>

        <div class="tool-group">
          <label>开销售单客户</label>
          <input id="saleCustomer" placeholder="客户名称">
          <button id="saleCustomerSearchBtn">搜索客户</button>
          <div class="choices" id="saleCustomerChoices"></div>
          <label>礼盒 / 商品</label>
          <input id="saleProduct" placeholder="名称 / 规格 / 颜色">
          <div class="tool-row">
            <div><label>数量</label><input id="saleQty" type="number" min="1" value="1"></div>
            <div><label>出库仓库</label><select id="saleWarehouse"><option value="2">百鑫仓库</option><option value="1">自己店里</option></select></div>
          </div>
          <div class="tool-row">
            <button id="saleProductSearchBtn">搜索商品</button>
            <button class="primary" id="saleAddLineBtn">加入明细</button>
          </div>
          <div class="choices" id="saleProductChoices"></div>
          <div class="sale-lines" id="saleLines"></div>
          <div class="kv-row"><span id="saleSelectedCustomer">未选择客户</span><strong id="saleTotal">¥0.00</strong></div>
          <div class="tool-row">
            <button id="saleClearBtn">清空</button>
            <button class="primary" id="quickSaleBtn">开销售单</button>
          </div>
        </div>
      </div>
"""


HIDDEN_HTML = """
  <input id="wfId" type="hidden">
  <input id="wfCustomer" type="hidden">
  <input id="wfGoods" type="hidden">
  <input id="wfQty" type="hidden" value="1">
  <input id="wfColor" type="hidden">
  <input id="wfPrint" type="hidden" value="0">
  <input id="wfType" type="hidden" value="0">
  <input id="productId" type="hidden">
  <input id="productTitle" type="hidden">
  <input id="productSpec" type="hidden">
  <input id="productPrice" type="hidden">
  <input id="productImageUrl" type="hidden">
  <input id="productImageInput" type="file" accept="image/*" class="sr-only">
  <div id="productEditHint" class="sr-only"></div>
  <div class="toast" id="toast"></div>
"""


def _replace_last_script(html: str, script: str) -> str:
    start = html.rfind("<script>")
    end = html.rfind("</script>")
    if start == -1 or end == -1 or end < start:
        return html + f"\n<script>\n{script}\n</script>\n"
    return html[:start] + f"<script>\n{script}\n</script>" + html[end + len("</script>"):]


def get_webui_html():
    """Return the WebUI HTML."""
    html = _TEMPLATE_PATH.read_text(encoding="utf-8")
    script = _SCRIPT_PATH.read_text(encoding="utf-8")
    html = html.replace("<title>AI 订单库存工作台</title>", "<title>肆计包装-北极星订单管理机器人</title>")
    html = html.replace("<div class=\"mark\">AI</div>", "<div class=\"mark\">北</div>", 1)
    html = html.replace("<strong>订单工作台</strong>", "<strong>肆计包装</strong>", 1)
    html = html.replace("<span>对话驱动的订单库存</span>", "<span>北极星订单管理机器人</span>", 1)
    html = html.replace("<button class=\"ghost\" id=\"newChatButton\">新建对话</button>", "<button class=\"ghost\" id=\"newChatButton\">新会话</button>", 1)
    html = html.replace("<h1>AI 业务工作台</h1>", "<h1>业务工作台</h1>", 1)
    html = html.replace("<p>开单、查库存、改订单、上下架商品，都从这里开始。</p>", "<p>开单、查库存、改订单、上下架商品。</p>", 1)
    html = html.replace("</style>", EXTRA_CSS + "\n</style>", 1)
    html = html.replace("  <div class=\"toast\" id=\"toast\"></div>", HIDDEN_HTML, 1)
    if 'id="toast"' not in html:
        html = html.replace("</body>", HIDDEN_HTML + "\n</body>", 1)
    return _replace_last_script(html, script)


def get_login_html():
    return LOGIN_HTML
