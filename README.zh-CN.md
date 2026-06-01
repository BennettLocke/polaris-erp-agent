# 北极星 Polaris ERP Agent

[English Guide](./README.en.md) | [GitHub 首页](./README.md)

北极星 Polaris ERP Agent 是一套面向小批量包装业务的自有 ERP 后台与智能体服务端。它把商品、SKU、库存、客户、销售单、订单流程、图片资产、打印、小程序接口、数据看板和 AI 工作台统一到 `sjagent_core` 业务库，并通过 `/admin` React 后台提供日常运营入口。

这个仓库是主服务端。小星设备端源码独立维护在 [BennettLocke/polaris-xiaoxing-device](https://github.com/BennettLocke/polaris-xiaoxing-device)。

## 项目定位

Polaris ERP Agent 解决的是包装业务日常运营里的几个核心问题：

- 商品和 SKU 多，颜色、件规、图片、上下架、起订规则需要统一维护。
- 库存同时涉及门店仓、百鑫仓、进货、调货、盘点和流水。
- 客户有月结、余额、对账、历史价格和销售记录。
- 销售单、订单制作、配送、打印、小程序和 AI 对话都需要共用同一套业务规则。
- 设备端硬件资源有限，不适合承载复杂 ERP 逻辑，需要把业务集中放在服务端。

因此本项目采用“服务端重业务、客户端轻交互”的架构：服务端负责所有业务判断和数据落库，React 后台、小程序、AI 工作台、小星设备端都通过统一 API 使用这些能力。

## 核心能力

| 模块 | 能力 |
| --- | --- |
| React 后台 | 工作台、开单、销售单、客户、商品、库存、订单、设置、图片资产、打印预览。 |
| AI 工作台 | 自然语言查库存、开单、进货、调货、盘点、识别订单图片、结构化确认和执行结果弹窗。 |
| 商品中心 | SPU/SKU、分类、颜色、件规、价格、上下架、主图、颜色规格图、详情图、图片资产绑定。 |
| 库存中心 | 门店仓与百鑫仓库存总览、明细表、流水、出入库、盘点、调拨和缺货查询。 |
| 销售中心 | 开单、收款方式、余额扣款、月结、删除回滚、打印、销售单详情和操作记录。 |
| 客户中心 | 客户卡片、手机号绑定、月结、余额、收款、对账单、最近消费和销售记录。 |
| 订单中心 | 订单图片、制作状态、配送状态、最近完成、分页和销售单关联。 |
| 小程序接口 | 首页配置、商品列表、商品详情、客户登录、订单、个人中心、热销商品数据。 |
| 图片管线 | 批量上传、1:1 裁切、主图/颜色规格图/详情图、OSS 上传、商品范围内选择和排序。 |
| 打印链路 | 销售单打印模板、打印预览、服务端打印任务、本地 `sjAutoPrint` Windows 打印代理。 |

## 小星设备端

设备端仓库：[BennettLocke/polaris-xiaoxing-device](https://github.com/BennettLocke/polaris-xiaoxing-device)

小星设备端的定位是“轻客户端”，适合 Orange Pi Zero3 这类资源有限的设备。它的优点是：

- **轻量稳定**：设备只负责唤醒、录音、ASR/TTS、屏幕显示和命令转发，不在本地跑复杂 ERP 逻辑。
- **业务统一**：库存、客户、商品纠错、开单、规则判断都交给主服务端，避免 Web、语音、屏幕三处重复实现。
- **独立部署**：设备仓库提供 `device-overlay/`、`systemd/`、`install_overlay.sh`、`update_device.sh` 和 `smoke_test.py`，方便设备端单独更新。
- **本地体验完整**：支持 openWakeWord “小星小星”唤醒、USB 麦克风采集、火山 ASR/TTS、480x320 本地 `/screen` 小屏页面。
- **服务端可观测**：设备调用 `/api/device/voice/command`，服务端返回 `speak` 和 `display`，方便统一记录、调试和优化。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.11, Flask, PyMySQL, service-layer architecture |
| 智能体 | LLM provider adapters, business tools, structured confirmation flows |
| 前端 | React 19, Vite, TypeScript, Radix/shadcn 风格组件 |
| 数据库 | MySQL, 主业务库 `sjagent_core` |
| 图片 | OSS, Pillow, RapidOCR, square crop pipeline |
| 打印 | HTML/PDF print templates, server print tasks, `sjAutoPrint` local agent |
| 部署 | systemd, Docker Compose, smoke-test scripts |

## 目录结构

```text
admin/                         React 后台源码
src/channels/http_api/          Flask HTTP API 和 admin_dist 静态资源
src/services/business/          商品、库存、客户、销售、设置、小程序等业务服务层
src/engine/native_db.py         sjagent_core 数据访问层
src/core/                       智能体、工具、配置、技能调度
src/skills/                     业务技能工作流
scripts/                        部署、迁移、打印、图片、语音和检查脚本
scripts/sjautoprint/            Windows 本地打印代理安装包
database/                       数据库建表和迁移 SQL
docs/                           API 合同、页面项目书、数据库说明、部署和审计文档
tests/                          单元测试、合同测试和回归测试
```

## 环境要求

- Python 3.11
- Node.js 20 或更高版本
- MySQL 5.7/8.0
- Linux 服务器建议安装中文字体：

```bash
sudo apt-get update
sudo apt-get install -y fonts-noto-cjk
```

Windows 打印端如果需要自动接收服务器打印任务，可安装本仓库自带的 `sjAutoPrint`：

```powershell
powershell -ExecutionPolicy Bypass -File Z:\sjagent\scripts\sjautoprint\install_sjautoprint.ps1
```

## 快速部署

下面以 Ubuntu/Debian + systemd 为例。生产环境建议使用独立数据库用户，并通过 Nginx 反代到 `127.0.0.1:8080`。

### 1. 拉取代码

```bash
cd /opt
git clone https://github.com/BennettLocke/polaris-erp-agent.git sjagent
cd /opt/sjagent
```

如果服务器已经有旧仓库：

```bash
cd /opt/sjagent
git remote set-url origin https://github.com/BennettLocke/polaris-erp-agent.git
git fetch origin
git checkout main
git pull --ff-only origin main
```

### 2. 创建 Python 环境

```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-lock.txt
```

开发环境也可以使用 `requirements.txt`，生产部署优先使用 `requirements-lock.txt`。

### 3. 构建 React 后台

```bash
cd /opt/sjagent/admin
npm ci
npm run build
cd /opt/sjagent
```

构建产物会输出到 `src/channels/http_api/admin_dist`。构建脚本会自动检查 `index.html` 引用的 JS/CSS 是否存在。

### 4. 安装泡袋模板依赖

```bash
cd /opt/sjagent/scripts/bag_template
npm ci --omit=dev
cd /opt/sjagent
```

### 5. 配置环境变量

```bash
cp .env.example .env
nano .env
```

生产至少需要配置：

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

`.env`、日志、上传文件、缓存和运行时数据已经在 `.gitignore` 中排除，不要提交到仓库。

### 6. 初始化或迁移数据库

数据库结构说明：

- `docs/business_database_schema.md`
- `docs/product_database_schema.md`
- `docs/native_migration_tables.md`
- `database/schema/`

新环境需要先创建 `sjagent_core` 数据库和业务表，再导入商品、客户、库存和历史单据。已有生产环境通常只需要确认 `.env` 指向正确数据库。

### 7. 本地验证

```bash
python -m unittest discover -s tests
python scripts/smoke_http_routes.py
python scripts/check_admin_dist.py
```

### 8. 启动服务

直接启动：

```bash
. /opt/sjagent/.venv/bin/activate
python main.py --mode http --http-host 127.0.0.1 --http-port 8080
```

systemd 示例：

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

保存为 `/etc/systemd/system/sjagent.service` 后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl enable sjagent.service
sudo systemctl restart sjagent.service
sudo systemctl status sjagent.service
```

### 9. 访问入口

| 入口 | 地址 |
| --- | --- |
| React 后台 | `http://服务器域名/admin` |
| 健康检查 | `http://服务器域名/health` |
| 小程序 API | `http://服务器域名/api/mini/*` |
| 设备语音 API | `http://服务器域名/api/device/voice/command` |

## Docker Compose

Docker 适合快速验证，生产建议先确认数据库、OSS、字体和持久化目录。

```bash
cp .env.example .env
# 编辑 .env 后启动
docker compose up -d --build
docker compose logs -f sjagent
```

容器内默认监听 `0.0.0.0:8080`，宿主机可访问 `http://127.0.0.1:8080/admin`。

## 发布更新流程

服务器以后从 GitHub 拉取：

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

## 安全说明

- 生产环境必须设置高强度 `SJAGENT_SECRET_KEY`。
- 小程序微信登录不信任客户端传入 openid，必须由服务端用 code 换取。
- 小程序私有接口按路径强制 token 鉴权，客户只能访问自己绑定的数据。
- 上传和裁图接口会校验图片类型、大小和远程 URL 安全边界。
- 销售、库存、余额、删除回滚、上下架和打印任务都必须经过服务层。
- `.env`、日志、上传目录、会话文件和缓存目录不得提交到 Git。

## 维护原则

- 前端只负责展示和交互，库存、余额、上下架、删除回滚等规则必须走服务层。
- 新后台统一使用 React + Radix/shadcn 风格组件，详情和确认优先使用中间弹窗。
- 业务接口必须落到 `src/services/business`，避免在路由和页面里重复写规则。
- 上线前至少执行 `python -m unittest discover -s tests`、`npm run build`、`python scripts/smoke_http_routes.py`。
