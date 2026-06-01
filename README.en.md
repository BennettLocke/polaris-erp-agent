# Polaris ERP Agent

[中文说明](./README.zh-CN.md) | [GitHub Home](./README.md)

Polaris ERP Agent is a server-side ERP, AI assistant, mini-program API, print pipeline, and React admin console for a small-batch packaging business. It centralizes products, SKUs, inventory, customers, sales orders, workflow orders, image assets, printing, analytics, and AI-assisted operations into the `sjagent_core` business database.

This repository is the main server. The Xiaoxing device client is maintained separately at [BennettLocke/polaris-xiaoxing-device](https://github.com/BennettLocke/polaris-xiaoxing-device).

## What This Project Solves

Polaris ERP Agent is designed for an operations-heavy packaging workflow:

- Many products and SKUs with colors, package specs, images, listing state, and purchase rules.
- Inventory across the local shop warehouse and Baixin warehouse, including stock-in, transfers, stocktakes, and ledgers.
- Customers with monthly settlement, balance payments, statements, historical prices, and sales records.
- Sales orders, workflow orders, production status, delivery status, printing, mini-program APIs, and AI chat all sharing one set of business rules.
- Low-power voice/screen devices that should not run complicated ERP logic locally.

The architecture uses a **business-heavy server** and **thin clients**. React Admin, the mini-program, the AI workbench, and the Xiaoxing device all call the same server-side services.

## Core Features

| Area | Capabilities |
| --- | --- |
| React Admin | Workbench, sales creation, sales orders, customers, products, inventory, workflow orders, settings, image assets, and print preview. |
| AI Workbench | Natural-language inventory lookup, sales drafting, stock-in, transfers, stocktake, order-image recognition, structured confirmations, and result dialogs. |
| Product Center | SPU/SKU management, categories, colors, package specs, prices, listing state, main images, color/spec images, detail images, and media binding. |
| Inventory Center | Local and Baixin warehouse overview, details, ledgers, stock-in/out, stocktake, transfers, and shortage queries. |
| Sales Center | Sales creation, payment method changes, balance deduction, monthly settlement, delete rollback, printing, order detail, and operation logs. |
| Customer Center | Customer cards, phone binding, monthly settlement, balance, collection, statements, recent purchases, and sales history. |
| Workflow Orders | Order images, production status, delivery status, recent completions, pagination, and sales-order links. |
| Mini-program APIs | Home configuration, product lists, product details, customer login, orders, profile, and hot-product analytics. |
| Image Pipeline | Batch upload, 1:1 crop, main/color/detail images, OSS upload, product-scoped selection, and detail-image ordering. |
| Print Pipeline | Sales print templates, print preview, server print tasks, and the bundled `sjAutoPrint` local Windows print agent. |

## Xiaoxing Device Client

Device repository: [BennettLocke/polaris-xiaoxing-device](https://github.com/BennettLocke/polaris-xiaoxing-device)

The Xiaoxing device repository is a lightweight Orange Pi client. Its strengths:

- **Stable thin client**: the device handles wake word, microphone capture, ASR/TTS, screen display, and command forwarding only.
- **Single business authority**: inventory, customers, product correction, sales creation, and rule checks stay on the main server.
- **Independent deployment**: the repository includes `device-overlay/`, `systemd/`, `install_overlay.sh`, `update_device.sh`, and `smoke_test.py`.
- **Complete local interaction**: openWakeWord wake phrase, USB microphone capture, Volcano ASR/TTS, and a local 480x320 `/screen` page.
- **Server-side observability**: the device calls `/api/device/voice/command`; the server returns `speak` and `display` payloads that are easy to log, debug, and improve.

## Technology Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11, Flask, PyMySQL, service-layer architecture |
| AI Agent | LLM provider adapters, business tools, structured confirmation flows |
| Frontend | React 19, Vite, TypeScript, Radix/shadcn-style components |
| Database | MySQL, main business schema `sjagent_core` |
| Images | OSS, Pillow, RapidOCR, square crop pipeline |
| Printing | HTML/PDF print templates, server print tasks, `sjAutoPrint` local agent |
| Deployment | systemd, Docker Compose, smoke-test scripts |

## Component Library

The React admin component system is based on [shadcn-ui/ui](https://github.com/shadcn-ui/ui), with interaction primitives from [radix-ui/primitives](https://github.com/radix-ui/primitives). Polaris follows the shadcn/ui model where UI components live as source code inside the project instead of being consumed as a black-box package. Buttons, dialogs, cards, tables, tabs, selects, dropdown menus, badges, empty states, and skeletons can therefore be refined for the real operations workflow.

Polaris also has an internal local component-library workspace:

```text
Z:\肆计包装小程序\组件库全新重做
```

This workspace is not required for server deployment. It is the local design-system source for Polaris / SJ mini-program and admin visual language. It maintains:

- `css-components/`: CSS / HTML component implementations for visual rules, sizing, states, spacing, and Chinese UI conventions.
- `uni-app-components/`: reusable `sj-*` uni-app components for the mini-program.
- `preview/`: component preview and acceptance pages that render real component output.
- `tests/`: Node tests for component files, preview entries, and CSS / uni-app / preview mapping.

Relationship with this main repository:

- `admin/src/components/ui` contains the React admin components actually used by the ERP console.
- `admin/src/styles.css` carries admin visual tokens, layout density, and business-page styling.
- The local component library keeps mini-program and preview components aligned with the `sj-` prefix, Chinese copy, component states, example counts, and acceptance rules.
- New or redesigned components should be proven in the local component library first, then the stable visual and interaction rules can be applied to the React admin.

Why this works well for Polaris:

- **Consistent visual language**: every admin page uses the same buttons, cards, dialogs, tables, filters, and status badges.
- **Maintainable source-owned UI**: components live in `admin/src/components/ui/` and can evolve with the business.
- **Accessible primitives**: Dialog, AlertDialog, Select, DropdownMenu, Tabs, and related interactions are powered by Radix primitives.
- **Good fit for an ERP console**: composable components support dense operational pages without drifting into marketing-page design.
- **Mini-program alignment**: local `uni-app-components/sj-*` components keep the customer-facing mini-program close to the admin visual system.

## Repository Layout

```text
admin/                         React admin source
src/channels/http_api/          Flask HTTP API and admin_dist static assets
src/services/business/          Product, inventory, customer, sales, settings, mini-program services
src/engine/native_db.py         sjagent_core database access layer
src/core/                       Agent, tools, config, skill dispatch
src/skills/                     Business skill workflows
scripts/                        Deployment, migration, print, image, voice, and check scripts
scripts/sjautoprint/            Windows local print-agent installer
database/                       Database schema and migration SQL
docs/                           API contracts, page handbooks, database docs, deployment notes, audit reports
tests/                          Unit, contract, and regression tests
```

## Requirements

- Python 3.11
- Node.js 20 or newer
- MySQL 5.7/8.0
- Chinese fonts on Linux servers:

```bash
sudo apt-get update
sudo apt-get install -y fonts-noto-cjk
```

If a Windows machine needs to receive centralized print tasks, install the bundled `sjAutoPrint` service:

```powershell
powershell -ExecutionPolicy Bypass -File Z:\sjagent\scripts\sjautoprint\install_sjautoprint.ps1
```

## Quick Deployment

The following example uses Ubuntu/Debian with systemd. In production, use a dedicated database user and reverse proxy traffic to `127.0.0.1:8080` with Nginx.

### 1. Clone

```bash
cd /opt
git clone https://github.com/BennettLocke/polaris-erp-agent.git sjagent
cd /opt/sjagent
```

If the server already has an older checkout:

```bash
cd /opt/sjagent
git remote set-url origin https://github.com/BennettLocke/polaris-erp-agent.git
git fetch origin
git checkout main
git pull --ff-only origin main
```

### 2. Create the Python Environment

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-lock.txt
```

Use `requirements.txt` for development if needed. Prefer `requirements-lock.txt` for production.

### 3. Build React Admin

```bash
cd /opt/sjagent/admin
npm ci
npm run build
cd /opt/sjagent
```

The build is written to `src/channels/http_api/admin_dist`. The build script validates that `index.html` references existing JS/CSS assets.

### 4. Install Bag Template Dependencies

```bash
cd /opt/sjagent/scripts/bag_template
npm ci --omit=dev
cd /opt/sjagent
```

### 5. Configure Environment Variables

```bash
cp .env.example .env
nano .env
```

Minimum production settings:

```env
SJAGENT_ENV=production
SJAGENT_HTTP_HOST=127.0.0.1
SJAGENT_SECRET_KEY=replace-with-a-long-random-secret
SJAGENT_SESSION_COOKIE_SECURE=1

SJAGENT_CORE_DB_HOST=127.0.0.1
SJAGENT_CORE_DB_PORT=3306
SJAGENT_CORE_DB_NAME=sjagent_core
SJAGENT_CORE_DB_USER=sjagent_core
SJAGENT_CORE_DB_PASSWORD=replace-with-db-password

OSS_ACCESS_KEY_ID=replace-with-oss-key
OSS_ACCESS_KEY_SECRET=replace-with-oss-secret

WECHAT_MINIAPP_APPID=replace-with-miniapp-appid
WECHAT_MINIAPP_SECRET=replace-with-miniapp-secret
```

`.env`, logs, uploaded files, caches, and runtime data are ignored by Git. Do not commit secrets.

### 6. Initialize or Migrate the Database

Database references:

- `docs/business_database_schema.md`
- `docs/product_database_schema.md`
- `docs/native_migration_tables.md`
- `database/schema/`

For a fresh environment, create the `sjagent_core` database and tables, then import products, customers, inventory, and historical orders. For an existing production system, verify that `.env` points to the correct database.

### 7. Verify Locally

```bash
python -m unittest discover -s tests
python scripts/smoke_http_routes.py
python scripts/check_admin_dist.py
```

### 8. Start the Service

Direct start:

```bash
. /opt/sjagent/.venv/bin/activate
python main.py --mode http --http-host 127.0.0.1 --http-port 8080
```

systemd example:

```ini
[Unit]
Description=Polaris ERP Agent
After=network.target mysql.service

[Service]
Type=simple
WorkingDirectory=/opt/sjagent
EnvironmentFile=/opt/sjagent/.env
ExecStart=/opt/sjagent/.venv/bin/python /opt/sjagent/main.py --mode http --http-host 127.0.0.1 --http-port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Save it as `/etc/systemd/system/sjagent.service`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sjagent.service
sudo systemctl restart sjagent.service
sudo systemctl status sjagent.service
```

### 9. Entry Points

| Entry | URL |
| --- | --- |
| React admin | `http://your-domain/admin` |
| Health check | `http://your-domain/health` |
| Mini-program APIs | `http://your-domain/api/mini/*` |
| Device voice API | `http://your-domain/api/device/voice/command` |

## Docker Compose

Docker is useful for quick validation. For production, verify database, OSS, fonts, and persistent directories first.

```bash
cp .env.example .env
# Edit .env, then start:
docker compose up -d --build
docker compose logs -f sjagent
```

The container listens on `0.0.0.0:8080`. Visit `http://127.0.0.1:8080/admin` on the host.

## Release Update Flow

Servers should pull from GitHub:

```bash
cd /opt/sjagent
git fetch origin
git pull --ff-only origin main
. .venv/bin/activate
pip install -r requirements-lock.txt
cd admin && npm ci && npm run build && cd ..
python -m unittest discover -s tests
python scripts/smoke_http_routes.py
sudo systemctl restart sjagent.service
sudo systemctl is-active sjagent.service
```

## Security Notes

- Set a strong `SJAGENT_SECRET_KEY` in production.
- Mini-program login must exchange WeChat `code` on the server. Do not trust client-provided openid.
- Private mini-program routes require token authentication, and customers can only access their own bound data.
- Upload and crop APIs validate image type, size, and remote URL boundaries.
- Sales, inventory, balances, delete rollback, listing state, and print tasks must go through the service layer.
- Never commit `.env`, logs, upload directories, session files, or caches.

## Maintenance Principles

- Frontend code handles presentation and interaction only. Business rules belong in `src/services/business`.
- React Admin uses the Radix/shadcn-style component system. Details and confirmations should use centered dialogs.
- API routes should delegate to business services instead of duplicating rules.
- Before deployment, run `python -m unittest discover -s tests`, `npm run build`, and `python scripts/smoke_http_routes.py`.
