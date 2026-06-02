# Polaris ERP Agent

[中文说明](./README.zh-CN.md) | [English Guide](./README.en.md)

Polaris ERP Agent is the server-side ERP, AI assistant, mini-program API, print pipeline, and React admin console for a small-batch packaging business. It centralizes products, SKUs, inventory, customers, sales orders, workflow orders, image assets, printing, analytics, and AI-assisted operations into the `sjagent_core` business database.

北极星 Polaris ERP Agent 是面向小批量包装业务的自有 ERP 后台和智能体服务端。它把商品、库存、客户、销售单、订单流程、图片资产、打印、小程序接口、数据看板和 AI 工作台统一到 `sjagent_core` 业务库，日常运营入口统一使用 `/admin` React 后台。

## Highlights

- **Unified business core**: product, inventory, sales, customer balance, workflow, mini-program, and print rules are handled in the service layer instead of being duplicated in the UI.
- **React admin console**: a production-focused admin system for workbench chat, sales, customers, products, inventory, workflow orders, settings, image assets, and print preview.
- **AI operations workbench**: natural-language inventory lookup, sales order drafting, stock-in, transfer, stocktake, order-image recognition, and structured confirmation dialogs.
- **Mini-program ready**: customer login, product listing, detail pages, order APIs, profile APIs, hot-product analytics, and secure customer binding.
- **Image and product asset pipeline**: product main images, color/spec images, detail images, square crop flow, batch upload, OSS upload, and product-scoped media binding.
- **Print chain**: sales print templates, print preview, server-side print tasks, and the bundled `sjAutoPrint` local Windows print agent.
- **Device-client split**: the Xiaoxing device code is maintained separately in [BennettLocke/polaris-xiaoxing-device](https://github.com/BennettLocke/polaris-xiaoxing-device), keeping the Orange Pi client lightweight while the ERP server owns business logic.

## Related Repositories

| Repository | Purpose |
| --- | --- |
| [BennettLocke/polaris-erp-agent](https://github.com/BennettLocke/polaris-erp-agent) | Main server, React admin, ERP APIs, AI workflows, database access, print tasks, and deployment scripts. |
| [BennettLocke/polaris-xiaoxing-device](https://github.com/BennettLocke/polaris-xiaoxing-device) | Xiaoxing Orange Pi client: wake word, microphone capture, ASR/TTS forwarding, local `/screen`, systemd services, install/update scripts, and device smoke tests. |
| [shadcn-ui/ui](https://github.com/shadcn-ui/ui) | The React admin component system is based on shadcn/ui patterns: source-owned components, Radix primitives, semantic tokens, and composable UI blocks. |
| [radix-ui/primitives](https://github.com/radix-ui/primitives) | Low-level accessible primitives behind dialogs, menus, selects, tabs, switches, and other interaction components. |

## Official Mini Program Source

The current customer-facing WeChat / uni-app mall source is maintained in the internal shared-drive workspace:

```text
Z:\肆计包装小程序\商城小程序源码\sj-mall-uniapp
```

This is the canonical mini-program codebase for the storefront experience: home, category browsing, product lists, product detail, order query, sales-order account pages, login/binding, settings, contact, and share assets. It is a thin client for `polaris-erp-agent`: business data comes from the sjagent service layer and the `/api/mini/*` APIs, while product, customer, order, inventory, shelf-state, and hot-product rules remain on the server.

Another local folder may exist at:

```text
Z:\肆计包装小程序\商城小程序源码\polaris-ai-erp-weapp
```

That folder is not the current source of truth for the mini program. Treat it as a historical or reference copy unless the project owner explicitly promotes it. Server deployment does not require either mini-program workspace; mini-program releases should be built from `sj-mall-uniapp` with uni-app / HBuilderX and pointed at the production backend domain.

## Local Design System Workspace

Polaris also has an internal local component-library workspace on the shared drive:

```text
Z:\肆计包装小程序\组件库全新重做
```

This local workspace is not required to deploy the ERP server. It is the design-system source used to keep the mini-program, web previews, and admin UI language aligned. It maintains CSS/HTML components, uni-app components, preview pages, and tests under `css-components/`, `uni-app-components/`, `preview/`, and `tests/`.

The main server repository applies that design language in `admin/src/components/ui`, `admin/src/styles.css`, and the React business pages, while the local component-library workspace remains the place to refine reusable mini-program and preview components before they are adopted by product screens.

## Quick Start

For complete deployment instructions, use:

- [中文部署与维护说明](./README.zh-CN.md)
- [English deployment and maintenance guide](./README.en.md)

Minimal production flow:

```bash
git clone https://github.com/BennettLocke/polaris-erp-agent.git /opt/sjagent
cd /opt/sjagent

python3.11 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-lock.txt

cd admin
npm ci
npm run build
cd ..

cp .env.example .env
# Edit database, secret, OSS, mini-program, LLM, and print/device settings.

python -m unittest discover -s tests
python scripts/smoke_http_routes.py

python main.py --mode http --http-host 127.0.0.1 --http-port 8080
```

Default entry points:

| Entry | Path |
| --- | --- |
| React admin | `/admin` |
| Health check | `/health` |
| Mini-program APIs | `/api/mini/*` |
| Device voice command API | `/api/device/voice/command` |
| Local print task APIs | `/api/print/*` |

## Architecture

```text
React Admin / Mini Program / AI Workbench / Xiaoxing Device
        |
        v
Flask HTTP API
        |
        v
Business Services
        |
        v
Native sjagent_core Database + OSS + Print Agent + LLM/ASR/TTS Providers
```

The system is intentionally split into a **heavy server** and a **thin device client**:

- The server owns inventory, sales, customer balance, product matching, order creation, image handling, analytics, and security.
- The Xiaoxing client focuses on wake word, local audio, local screen, TTS playback, and forwarding recognized commands to the server.
- This keeps the Orange Pi stable and easy to update while all business rules remain testable in one server repository.

## Quality Bar

Before deployment, run:

```bash
python -m unittest discover -s tests
cd admin && npm run build && cd ..
python scripts/smoke_http_routes.py
```

The repository includes service-layer tests, admin API contract tests, mini-program listing tests, print flow tests, inventory/sales regression checks, and static admin build validation.
