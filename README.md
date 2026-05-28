# Polaris ERP Agent

Polaris ERP Agent 是一套面向小批量包装业务的自有后台与智能体系统。它把商品、库存、客户、订单、销售单、图片资产、打印和小程序接口统一到 `sjagent_core` 业务库，并提供 React 后台、HTTP API、智能体对话入口和可部署的服务端运行方式。

当前项目已经完成旧后台迁移，日常运营入口统一为 `/admin` React 后台。

## 核心能力

- React 后台：工作台、开单、销售单、客户、商品、库存、订单、设置。
- AI 工作台：自然语言查库存、开单、进货、调拨、盘点、识别订单图和泡袋上传。
- 商品中心：SPU/SKU、分类、颜色、件规、上下架、主图、颜色规格图、图片资产和 `sjagent_core 商品库`。
- 库存中心：百鑫仓和门店仓库存总览、明细、流水、进货、调拨、盘点。
- 订单中心：过程订单图片、制作状态、配送状态、最近完成和销售单关联。
- 客户中心：客户卡片、月结、收款、结款、余额调整、销售记录和对账单。
- 小程序接口：首页配置、商品列表、商品详情、订单、个人中心、热销商品。
- 打印链路：销售单打印模板、打印预览、打印任务和本地打印代理接口。
- 泡袋批量上传：上传设计图压缩包，自动生成主图/详情图，上传 OSS 并写入自有商品库。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.11, Flask, LangGraph, PyMySQL |
| 前端 | React 19, Vite, TypeScript, Radix/shadcn 风格组件 |
| 数据库 | MySQL, 主业务库 `sjagent_core` |
| 图片 | OSS, Pillow, RapidOCR |
| 部署 | systemd 或 Docker Compose |

## 目录结构

```text
admin/                         React 后台源码
src/channels/http_api/          Flask HTTP API 和 admin_dist 静态资源
src/services/business/          自有业务服务层
src/engine/native_db.py         sjagent_core 数据访问层
src/core/                       智能体图、节点、工具注册
src/skills/                     业务技能工作流
scripts/                        迁移、检查、打印、图片处理脚本
database/                       数据库建表和迁移 SQL
docs/                           当前手册、迁移记录、检测报告
tests/                          单元测试和合同测试
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

### 3. 安装前端依赖并构建

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

`.env`、日志、上传文件、缓存和运行时数据已在 `.gitignore` 中排除，不要提交到仓库。

### 6. 初始化或迁移数据库

数据库结构说明见：

- `docs/business_database_schema.md`
- `docs/native_migration_tables.md`
- `database/schema/`

如果是新环境，需要先创建 `sjagent_core` 数据库和业务表，再导入商品、客户、库存和历史单据。已有生产环境通常只需要确认 `.env` 指向正确数据库。

### 7. 本地验证

```bash
python -m unittest discover -s tests
python scripts/smoke_http_routes.py
```

如果只想确认静态资源：

```bash
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

## Docker Compose

Docker 适合快速验证，生产建议先确认数据库、OSS、字体和持久化目录。

```bash
cp .env.example .env
# 编辑 .env 后启动
docker compose up -d --build
docker compose logs -f sjagent
```

容器内默认监听 `0.0.0.0:8080`，宿主机可访问 `http://127.0.0.1:8080/admin`。

## 常用命令

```bash
# 控制台对话
python main.py --mode console

# 单次执行
python main.py --message "查下半斤礼盒库存"

# HTTP API
python main.py --mode http --http-port 8080

# 前端开发
cd admin
npm run dev

# 前端生产构建
cd admin
npm run build
```

## 发布更新流程

服务器以后从 GitHub 拉取：

```bash
cd /opt/sjagent
git fetch origin
git pull --ff-only origin main
. .venv/bin/activate
pip install -r requirements-lock.txt
cd admin && npm ci && npm run build && cd ..
python scripts/smoke_http_routes.py
sudo systemctl restart sjagent.service
sudo systemctl is-active sjagent.service
```

## 安全说明

- 生产环境必须设置高强度 `SJAGENT_SECRET_KEY`。
- 小程序微信登录不信任客户端传入 openid，必须由服务端用 code 换取。
- 小程序私有接口按路径强制 token 鉴权，客户只能访问自己绑定的数据。
- 上传和裁图接口会校验图片类型、大小和远程 URL 安全边界。
- 销售单创建时会二次校验 SKU 是否 active、可售、已上架。
- `.env`、日志、上传目录、会话文件和缓存目录不得提交到 Git。

## 项目文档

| 文档 | 内容 |
| --- | --- |
| `docs/README.md` | 文档目录说明 |
| `docs/react_admin_api_contract.md` | React 后台 API 合同 |
| `docs/react_admin_page_design_blueprint.md` | 页面级设计蓝图 |
| `docs/sjagent_system_audit_report_2026-05-28.md` | 系统检测和修复进度 |
| `docs/react_admin_workbench_page_development_handbook.md` | 工作台项目书 |
| `docs/native_runtime_cutover.md` | 自有库运行切换记录 |
| `docs/bag_upload_handoff.md` | 泡袋批量上传流程 |

## 维护原则

- 前端只负责展示和交互，库存、余额、上下架、删除回滚等规则必须走服务层。
- 新后台统一使用 React + Radix/shadcn 风格组件，详情和确认优先使用中间弹窗。
- 业务接口必须落到 `src/services/business`，避免在路由和页面里重复写规则。
- 上线前至少执行：`python -m unittest discover -s tests`、`npm run build`、`python scripts/smoke_http_routes.py`。
