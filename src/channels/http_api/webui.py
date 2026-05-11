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
  @media (min-width: 1800px) and (min-height: 1000px) {
    #inventoryList.section-grid { --card-min-width: 430px; column-width: 430px; column-gap: 16px; }
    #inventoryList .inventory-card { padding: 18px; }
  }
  #productCategoryBar { display: flex; gap: 8px; overflow-x: auto; padding: 0 0 12px; margin-top: -2px; }
  #productCategoryBar button { flex: 0 0 auto; height: 34px; min-height: 34px; padding: 0 12px; border-radius: 999px; font-size: 13px; }
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
  #productList .product-price-row { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; font-size: 12px; color: var(--muted); }
  #productList .product-price-row strong { color: var(--accent); font-size: 15px; }
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
  .product-image-preview { aspect-ratio: 1 / 1; width: min(180px, 100%); border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; background: #f4f1ea; display: grid; place-items: center; color: var(--muted); font-size: 12px; padding: 0; cursor: pointer; }
  .product-image-preview img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .product-image-preview,
  .product-detail-item,
  .product-spec-image { position: relative; }
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
  .product-detail-remove { position: absolute; top: 4px; right: 4px; width: 22px; height: 22px; min-height: 0; padding: 0; border-radius: 999px; background: rgba(17,17,17,.78); border-color: rgba(17,17,17,.78); color: #fff; line-height: 1; }
  .product-spec-card { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface-2); padding: 10px; display: grid; gap: 9px; }
  .product-spec-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; font-weight: 760; }
  .product-spec-image-row { display: flex; gap: 10px; align-items: center; }
  .product-spec-image { width: 74px; height: 74px; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #ebe7df; display: grid; place-items: center; color: var(--muted); font-size: 12px; padding: 0; cursor: pointer; }
  .product-spec-image img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .drawer-form .block-action { width: 100%; height: 38px; display: inline-flex; align-items: center; justify-content: center; }
  @media (min-width: 1800px) and (min-height: 1000px) {
    #productList.section-grid { --card-min-width: 245px; gap: 14px; }
  }
  #salesList.section-grid { --sales-card-height: 352px; --sales-product-height: 104px; --card-min-width: 360px; grid-template-columns: repeat(auto-fill, minmax(var(--card-min-width), 1fr)); align-items: start; grid-auto-rows: var(--sales-card-height); }
  #salesList .sales-card { height: var(--sales-card-height); min-height: 0; display: grid; grid-template-rows: auto auto var(--sales-product-height) auto auto; gap: 10px; margin-bottom: 0; overflow: hidden; }
  #salesList .customer-name strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  #salesList .product-lines { gap: 8px; padding: 10px; height: var(--sales-product-height); overflow: hidden; position: relative; align-content: start; margin-top: 0; }
  #salesList .product-lines.has-more::after { content: ""; position: absolute; bottom: 0; left: 0; right: 0; height: 28px; background: linear-gradient(transparent, #f8fafc); pointer-events: none; }
  #salesList .product-row { grid-template-columns: minmax(0, 1fr) 56px 92px; align-items: start; font-size: 13px; }
  #salesList .product-name { white-space: normal; overflow: visible; text-overflow: clip; line-height: 1.4; }
  #salesList .kv { margin: 0; }
  #salesList .product-price,
  #salesList .kv-row:nth-child(2) strong,
  .sales-detail-table td:nth-child(3),
  .sales-detail-table td:nth-child(4) { color: var(--accent); font-weight: 800; }
  #salesList .card-actions { align-self: end; margin-top: 0; padding-top: 8px; border-top: 1px solid var(--line); position: relative; z-index: 3; background: var(--surface); }
  .expand-btn { display: block; width: 100%; text-align: center; padding: 6px 0 2px; color: var(--muted); font-size: 12px; background: none; border: none; cursor: pointer; position: relative; z-index: 1; }
  .expand-btn:hover { color: var(--text); }
  .sales-detail-head { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
  .sales-detail-table-wrap { max-height: 56vh; overflow: auto; border: 1px solid var(--line); border-radius: 8px; }
  .sales-detail-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .sales-detail-table th,
  .sales-detail-table td { padding: 9px 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
  .sales-detail-table th { position: sticky; top: 0; background: #f8fafc; color: var(--muted); z-index: 1; }
  .sales-detail-table td:nth-child(1),
  .sales-detail-table td:nth-child(3),
  .sales-detail-table td:nth-child(4),
  .sales-detail-table td:nth-child(5) { white-space: nowrap; }
  @media (min-width: 1800px) and (min-height: 1000px) {
    #salesList.section-grid { --sales-card-height: 292px; --sales-product-height: 82px; --card-min-width: 330px; grid-template-columns: repeat(auto-fill, minmax(var(--card-min-width), 1fr)); }
    #salesList .sales-card { padding: 12px; gap: 8px; }
    #salesList .customer-name { padding-bottom: 8px; }
    #salesList .customer-name strong { font-size: 16px; }
    #salesList .product-lines { padding: 8px; gap: 6px; }
    #salesList .product-row { grid-template-columns: minmax(0, 1fr) 48px 78px; gap: 6px; font-size: 12px; }
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
        await post(mode === "login" ? "/api/web-auth/login" : "/api/web-auth/register", { username, password, display_name: displayName });
        message.className = "msg ok";
        message.textContent = "已登录，正在进入系统...";
        location.href = "/web";
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
            <button id="transferBtn">百鑫调到店里</button>
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
    html = html.replace(
        '<button class="primary" id="newOrderButton">新建开单</button>',
        '<button class="primary" id="newOrderButton">新建开单</button><button class="ghost" id="logoutButton">退出</button>',
        1,
    )
    html = html.replace("<h1>AI 业务工作台</h1>", "<h1>业务工作台</h1>", 1)
    html = html.replace("<p>开单、查库存、改订单、上下架商品，都从这里开始。</p>", "<p>开单、查库存、改订单、上下架商品。</p>", 1)
    html = html.replace("</style>", EXTRA_CSS + "\n</style>", 1)
    html = html.replace("  <div class=\"toast\" id=\"toast\"></div>", HIDDEN_HTML, 1)
    if 'id="toast"' not in html:
        html = html.replace("</body>", HIDDEN_HTML + "\n</body>", 1)
    return _replace_last_script(html, script)


def get_login_html():
    return LOGIN_HTML
