# sjagent 系统检测报告

日期：2026-05-28
范围：React 新后台、Flask HTTP API、业务服务层、NativeDBClient、小程序接口、部署与测试文档。
方式：本地静态审查、文档核对、关键代码抽样、并行子任务审查。未进行线上渗透、未连接生产数据库、未修改业务代码。

## 1. 总体结论

sjagent 现在已经从旧后台进入“React 后台 + 服务层 + 小程序接口 + 设置中心”的重构阶段。后台主要页面已经具备可操作形态：工作台、商品、库存、订单、客户、销售、设置、小程序设置、图片资产、打印预览都已经接入。但系统还没有达到“可以放心对外暴露和稳定长期运营”的程度。

最需要优先处理的是四类问题：

1. 安全：小程序手机号/微信绑定链路可被伪造，后台 session secret 有公开默认值。
2. 业务一致性：调拨后开单仓库口径可能错账，泡袋批量上传单位写死。
3. 数据隔离：小程序部分订单/库存/个人中心接口存在未按客户绑定隔离的风险。
4. 发布质量：Docker 监听地址、`admin_dist` hash 资源、构建与 smoke 测试链路还不稳。

建议把接下来一轮工作分成三步：

1. 先修 P0/P1 安全和账务风险。
2. 再补订单、库存、客户、工作台这些高频页面的操作闭环。
3. 最后收敛部署流程、文档状态、自动化测试，把“能用”推进到“可发布、可回滚、可追责”。

### 1.1 本轮处理进度（2026-05-28 追加）

本轮已经把报告里多数 P0/P1/P2 可落地项补上，并补了对应回归测试。当前状态：

- 已修安全边界：微信登录不信客户端 openid、miniapp 私有接口按路径强制 token、上传/裁图校验、session id 路径穿越、生产密钥配置、销售下架 SKU 二次校验。
- 已修业务一致性：调拨后销售出库仓口径、泡袋单位写死、工作流订单回填销售单、小程序个人中心按客户隔离。
- 已修高频页面闭环：订单分页/图片/制作配送字段，库存流水精确查询和风险确认，客户详情销售分页，设置页当前账号/最后管理员保护。
- 已修体验和工程项：图片资产上传规则、旧 MediaPage 死代码、库存状态后端筛选、客户余额校验、页面文案、文档口径、日志忽略、锁定依赖、admin_dist 和 HTTP smoke。
- 已新增基础分析能力：`AnalyticsService.hot_products()` 已对后台和小程序开放，工作台已显示热销预览。完整数据看板仍作为后续独立页面继续做。
- 已下线旧 `/web` 页面：后台页面入口统一为 `/admin`，旧 WebUI 模板、脚本、启动脚本和迁移期计划书已从仓库移除。

## 2. 当前系统状态

### 2.1 已基本成型

- React 后台主壳：侧边导航、登录态、页面头、统一 API client。
- 商品页：卡片式商品管理、上下架、图片资产、1:1 裁剪、分类/库存策略联动。
- 库存页：卡片瀑布式总览、明细表、流水、出入库、盘点、调拨。
- 订单页：订单卡片、图片展示、中央弹窗详情、制作/配送状态、最近完成区。
- 客户页：客户卡片、详情弹窗、销售记录、余额/收款/对账单。
- 设置页：商品基础、库存规则、收款结款、图片资产、小程序设置、用户权限、打印预览。
- 工作台：AI 对话界面、快捷指令、业务结果弹窗、确认弹窗。
- 小程序接口：商品列表/详情、首页配置、订单、个人中心、热销接口雏形。
- 打印链路：销售单打印 HTML、打印任务、设置页 iframe 预览。

### 2.2 尚未稳定闭环

- 工作台确认弹窗还是通用字段表单，没有按开单、调拨、进货、盘点做类型化确认。
- 订单页缺手工建单时的图片选择/上传和制作/配送字段。
- 库存页部分筛选和流水查询还偏前端兜底，缺精确后端参数。
- 小程序热销 API 已有，工作台已接入预览；首页货架和完整数据看板还需要继续产品化。
- 权限后端已有角色和路由规则，前端已对设置、库存动作、调余额做第一批隐藏/禁用；后续还要扩到删单、商品删除等低频危险动作。
- 文档中的“待迁移”口径已清理一轮；后续新增页面时继续以 `/admin` 项目书为准。
- 发布链路仍偏手工，缺 CI、构建产物策略、静态资源 smoke。

## 3. P0：必须优先修复

### 3.1 小程序客户绑定可被伪造

证据：

- `src/channels/http_api/__init__.py:4638` 的 `/api/auth/register` 接收前端账号/手机号。
- `src/services/business/auth.py:515` 的 `native_register()` 用手机号查客户，并在 `auth.py:532` 附近直接写入 `approved/is_active=1`。
- `src/channels/http_api/__init__.py:4691` 附近允许客户端传 `openid`。
- `src/services/business/auth.py:804` 附近只有在传了 `phone_code` 且 profile 没手机号时才调微信取号，随后 `auth.py:813` 使用 profile 手机号绑定客户。

影响：

攻击者只要知道客户手机号，就可能注册或伪造微信登录资料，绑定成该客户，读取余额、近期订单、销售单等。

建议：

- 禁止客户端直传 `openid` 作为可信身份，必须服务端用 `jscode2session` 换取。
- 注册时不要自动绑定客户；命中客户手机号后进入待审核或短信/微信手机号校验。
- 手机号绑定必须来自微信 `phone_code` 或短信服务端校验结果。
- 小程序客户查询接口统一按 `linked_party_id` 限制。
- 补测试：伪造手机号注册不能直接绑定客户；微信 quick login 无 `phone_code` 不能靠 body 手机号绑定。

处理状态（2026-05-28）：已完成主要修复。

- 微信快捷登录不再读取客户端传入的 `openid/open_id`，只用服务端 `jscode2session` 结果。
- 绑定手机号必须走 `phone_code` 或服务端已保存的可信手机号；普通注册不再直接靠前端手机号绑定客户。
- 小程序个人中心、订单流等客户数据已按 `linked_party_id` 隔离；员工/管理员才保留全局视角。
- 已补回归：`test_auth_api_contract.py`、`test_miniapp_customer_isolation.py`、`test_miniapp_order_permissions.py`、`test_native_db_client.py`。

### 3.2 后台 Flask session secret 有公开默认值

证据：

- `src/channels/http_api/__init__.py:40` 缺少 `SJAGENT_SECRET_KEY` 时使用固定值 `sjagent-webui-auth-secret`。
- `src/channels/http_api/__init__.py:227` 附近后台身份从 Flask session 的 `auth_user_id` 读取。
- `.env.example` 和 `docker-compose.yml` 没有强制配置 `SJAGENT_SECRET_KEY`。

影响：

如果生产环境漏配密钥，后台 session cookie 可能被伪造，后台登录态存在绕过风险。

建议：

- 生产模式下缺少高熵 `SJAGENT_SECRET_KEY` 直接拒绝启动。
- `.env.example`、Docker、systemd 部署文档都加入必填项。
- 设置 `SESSION_COOKIE_SECURE=True`，保留 `HttpOnly` 与 `SameSite=Lax`。
- 轮换线上 cookie/session。

处理状态（2026-05-28）：已完成代码和配置修复。

- Flask secret 已改为 `_resolve_flask_secret_key()`，不再保留公开固定默认值。
- 已设置 session cookie 安全项；`.env.example` 和 Docker 配置已补 `SJAGENT_SECRET_KEY`。
- 本地开发缺密钥仍允许临时密钥并打印警告；生产/部署必须显式配置。

### 3.3 调拨后开单仓库口径冲突

证据：

- `src/core/nodes/inventory.py:221` 附近会在本店有货时生成 `1 -> 2` 调拨。
- `src/core/nodes/executor.py:90`、`executor.py:160` 附近后续销售明细仍可能沿用原 `warehouse_id=1`。
- `src/skills/order_flow/workflow.py:1064` 附近新版订单流在“百鑫无货、本店有货”时口径又偏向进货，和旧 core 节点不一致。

影响：

可能出现“从本店调到百鑫，又从本店销售扣库存”的错账，库存流水和实际业务不一致。

建议：

- 抽统一的 `InventoryDecisionService`，把库存决策收敛到一个服务。
- 明确四种结果：百鑫发货、本店发货需确认、本店调拨到百鑫后百鑫发货、进货到百鑫后发货。
- 调拨成功后销售单仓库应指向最终出库仓。
- 补端到端测试：百鑫 0、本店足量，断言调拨 `1 -> 2` 后销售明细仓库为 2。

处理状态（2026-05-28）：已完成关键错账修复。

- 智能体执行调拨后，销售单商品行使用调入仓作为最终出库仓。
- 已补 `tests/test_p0_inventory_and_bag_upload.py`，覆盖“本店调拨到百鑫后从百鑫销售扣库存”。

### 3.4 泡袋批量上传新 SKU 单位写死

证据：

- `src/skills/bag_upload/workflow.py:563` 附近新 SKU `unit_id=1` 写死。
- `docs/product_database_schema.md:251` 说明泡袋 SKU 单位应为“捆”。
- 业务知识库 `[[产品分类]]` 也说明泡袋单位为“捆”。

影响：

泡袋会被错误写成“套”，后续开单、统计、价格、库存和报表都会被污染。

建议：

- 按单位名查询“捆”的真实 `product_unit.id`，禁止写死 1。
- 做一次只读审计：找出 `product_type='bubble_bag'` 且单位不是“捆”的 SKU。
- 历史数据先出清单，人工确认后再修。

处理状态（2026-05-28）：已完成新写入修复，历史数据建议另开只读审计。

- 泡袋批量上传新增商品时按单位列表查找“捆”，不再写死 `unit_id=1`。
- 已补 `tests/test_p0_inventory_and_bag_upload.py`，锁定新泡袋 SKU 单位为“捆”。

## 4. P1：高优先级功能与风险

### 4.1 小程序 API 鉴权按请求头分流，存在绕过风险

证据：

- `src/channels/http_api/__init__.py:331` 的 `_miniapp_auth_guard()` 只有 `X-SJ-Client == miniapp` 才校验 token。
- `src/channels/http_api/__init__.py:378` 附近 Web 守卫整体放行 `/api/mini/`。
- 订单流、工作流搜索、库存搜索等接口在 `/api/mini/` 下。

影响：

未带 `X-SJ-Client` 的请求可能绕过 miniapp guard，访问不应公开的订单、库存、客户相关数据。

建议：

- 按路径决定是否需要鉴权，不依赖客户端请求头。
- 公开 allowlist 只保留商品展示类接口，如首页、商品分类、商品列表、商品详情。
- 订单、库存、客户摘要、个人中心必须强制 token。
- 客户角色只能查自己的 `linked_party_id` 数据；员工/管理员才允许全局。

处理状态（2026-05-28）：已完成主要修复。

- `/api/mini/` 私有接口改为按路径强制鉴权，不再依赖 `X-SJ-Client`。
- 商品浏览、首页等公开接口保留 allowlist；订单、工作流搜索、库存搜索、客户摘要必须带 token。
- 客户角色只能查自己的订单和个人中心数据，客户角色不能访问员工库存/客户搜索接口。
- 已补 `tests/test_miniapp_order_permissions.py`。

### 4.2 商品裁图接口存在 SSRF 与下载放大风险

证据：

- `src/channels/http_api/__init__.py:3829` `_open_product_crop_image()` 接收 URL。
- `__init__.py:3846` 只限制 http/https。
- `__init__.py:3853` 直接 `requests.get()`。
- `__init__.py:3855` 在完整读入后才检查 25MB。

影响：

有图片上传权限的账号可请求内网地址、云元数据地址，或用大文件造成内存/带宽压力。

建议：

- 裁图只允许传已上传媒体 id 或白名单 OSS 域名。
- 阻断 localhost、私网、链路本地、云元数据地址。
- 使用流式下载和硬上限，下载前校验 `Content-Type`，下载后用 Pillow 验证并重新编码。

处理状态（2026-05-28）：已完成主要修复。

- 裁图远程 URL 已加私网、localhost、云元数据地址拦截。
- 远程下载改为流式读取并受大小上限约束，落盘后用图片解码校验。
- 已补 `tests/test_security_boundaries.py`。

### 4.3 上传接口只看扩展名，缺全局大小和内容校验

证据：

- `src/channels/http_api/__init__.py:1531` `_allowed_image()` 只检查后缀。
- `/api/images/upload`、`/api/workflow/images/upload`、`/api/product/upload`、`/api/miniapp/image-config/upload` 多处直接保存文件。
- 未看到 Flask `MAX_CONTENT_LENGTH` 全局限制。

影响：

存在磁盘 DoS、图片炸弹、伪装文件上传 OSS 的风险。

建议：

- 配置 `MAX_CONTENT_LENGTH`。
- 用 Pillow 或 magic 验证真实图片类型、像素数和解码安全。
- 上传前后限速限频。
- 上传到 OSS 前强制重新编码成受控格式。

处理状态（2026-05-28）：已完成基础校验。

- 已配置 `MAX_CONTENT_LENGTH`，上传保存后调用图片校验，伪造 jpg 和格式伪装会失败。
- 后续仍建议增加账号级限频和统一重编码策略。

### 4.4 会话文件名可路径穿越

证据：

- `src/core/session.py:40` 使用 `HISTORY_DIR / f"{session_id}.json"`，未校验 `session_id`。
- `src/channels/http_api/__init__.py:2298`、`__init__.py:2304` 附近从请求读取 `session_id`。

影响：

已登录用户可构造 session id 读写 sessions 目录外的 `.json` 文件，造成信息泄露或状态污染。

建议：

- `session_id` 只允许 `[A-Za-z0-9_-]`。
- 或完全由服务端生成，不信任前端传入。
- `resolve()` 后确认目标路径仍在 `HISTORY_DIR` 内。

处理状态（2026-05-28）：已完成。

- `SessionManager` 已增加 session id 规范化，只允许安全字符，路径穿越会被拒绝。
- 已补 `tests/test_security_boundaries.py`。

### 4.5 销售/库存写入未再次校验商品可售与上架状态

证据：

- `src/engine/native_db.py:5971` `_get_sku_for_update()` 只要求未删除。
- `src/engine/native_db.py:6270` 附近销售写入使用该 SKU。
- `src/engine/native_db.py:2441` 附近上下架只更新 `is_listed`。

影响：

绕过前端或使用旧 SKU id，可能对下架/停用 SKU 开单、调拨、盘点。

建议：

- 销售接口默认要求 `status='active' AND is_sellable=1`。
- 小程序与普通后台开单还应要求 `is_listed=1`。
- 如管理员需要 override，必须明确记录原因和操作人。

处理状态（2026-05-28）：已完成默认销售拦截。

- 销售单创建时 `_get_sku_for_update(..., require_sellable=True)` 会再次校验 `status/is_sellable/is_listed`。
- 入库、盘点、调拨不套用销售可售校验，避免历史整理和库存修正被误拦。
- 已补 `tests/test_native_db_client.py`。

### 4.6 小程序个人中心统计没有按客户隔离

证据：

- `src/services/business/miniapp.py:530` 附近 `user_center_payload()` 查询全局 `workflow_orders` 与 `sales_cards`。
- `customer_summary()` 已按 `linked_party_id` 限制，但个人中心入口没有完全沿用。

影响：

客户可能看到非本人订单统计或最近订单。

建议：

- 客户角色传 `customer_id=linked_party_id`。
- 员工/管理员才显示全局统计。
- 补客户与员工两套测试。

处理状态（2026-05-28）：已完成。

- `MiniAppService.user_center_payload()` 已按客户 `linked_party_id` 限制统计；未绑定客户不回退全局数据。
- 员工/管理员继续显示全局运营统计。
- 已补 `tests/test_miniapp_customer_isolation.py`。

### 4.7 小程序热销接口未接入首页货架和看板

证据：

- `src/services/business/analytics.py:68` 已有 `AnalyticsService.hot_products()`。
- `src/services/business/miniapp.py:360` 附近 `product_shelf_items()` 仍按关键词/分类拉商品，没有接 `sort=hot/sales`。
- `analytics.py:149` 附近 product 维度按历史标题聚合，可能拆散同一 SPU。

影响：

小程序无法真正返回“热销货架”；未来看板也缺统一聚合口径。

建议：

- 首页模块支持 `sort=sales|hot|latest|price_asc`。
- 热销统一按 SPU ID 聚合，标题使用当前 SPU 展示名，历史标题只做 fallback。
- 增加缓存或按天汇总表，避免每次实时扫销售明细。
- 在 React 后台增加数据看板页：热销商品、客户复购、销售趋势、库存周转、缺货提醒。

处理状态（2026-05-28）：已完成第一阶段。

- `AnalyticsService.hot_products()` 已按 SPU/SKU 维度聚合，并过滤删除、下架、不可用商品。
- 已暴露 `/api/analytics/hot-products` 和 `/api/mini/analytics/hot-products`。
- React 工作台右侧已接入热销预览；完整数据看板仍作为后续独立页面。

### 4.8 工作流订单和销售单没有闭环

证据：

- `docs/business_database_schema.md:132`、`:153` 设计上支持 `workflow_order.sales_order_id` 和销售单来源。
- `src/services/business/workflow.py:9` `WorkflowService.save_order()` 没有 SKU、销售单、操作人等关联入参。
- `src/skills/workflow_order/workflow.py:50` 附近图片确认后创建工作流和开单没有回填关联。

影响：

订单从识别、制作、配送到销售开单之间缺追踪链，后续对账和售后查证困难。

建议：

- 增加 `link_sales_order(workflow_id, sales_id, operator_user_id)`。
- 开单成功后写 `workflow_order.sales_order_id` 和 `sales_order.source_workflow_id`。
- 状态日志写 `link_sales`。

处理状态（2026-05-28）：已完成。

- 已增加 `WorkflowService.link_sales_order()` 和 `NativeDBClient.link_workflow_sales_order()`，在同一事务内更新工作流订单、销售单来源和 `workflow_order_log`。
- `SalesService.create_order()`、`/api/sales/add`、AI 工具 `sales_add` 已支持 `workflow_order_id`。
- 图片识别创建工作流后继续开销售单时，会把新建的工作流订单 ID 传到开单流程。
- 已补测试：服务层、数据库写入合同、工作台流程传参。

### 4.9 Docker HTTP API 可能无法从宿主访问

证据：

- `Dockerfile:28` 使用 `python main.py --mode all`。
- `docker-compose.yml:31` 发布 `8080:8080`。
- `main.py:51` 调 `run_api_server(port=port)`。
- `src/channels/http_api/__init__.py:4859` 默认 `host="127.0.0.1"`。

影响：

容器内 Flask 只监听 loopback，宿主机/Nginx/探活访问 8080 可能失败。

建议：

- HTTP host 可配置。
- Docker 环境绑定 `0.0.0.0`。
- 增加 `docker compose up` 后 `/health` smoke。

处理状态（2026-05-28）：已完成主要修复，仍建议上线前做真实容器 smoke。

- `run_api_server()` 已支持 `SJAGENT_HTTP_HOST` 和命令行 `--http-host`。
- 本地默认仍为 `127.0.0.1`，`docker-compose.yml` 默认传入 `0.0.0.0`。
- `.env.example` 已补充 `SJAGENT_HTTP_HOST`，并补了合同测试覆盖。

### 4.10 当前 `admin_dist` hash 资源未跟踪

证据：

- `src/channels/http_api/admin_dist/index.html:7` 引用 `index-Byi9R0zI.js`。
- `src/channels/http_api/admin_dist/index.html:8` 引用 `index-D2ZvG6dM.css`。
- 这两个新资源当前是未跟踪文件，旧 hash 资源已删除。

影响：

如果只提交 `index.html` 或服务端只拉已跟踪文件，`/admin` 会加载 404 JS/CSS，出现白屏。

建议：

- 明确策略二选一：
  - 构建产物不入库，部署时跑 `npm ci && npm run build`。
  - 或提交 `admin_dist` 全目录，并加 dist freshness 检查。
- 服务器部署脚本必须包含静态资源 smoke。

处理状态（2026-05-28）：已完成发布前静态资源检查。

- 已增加 `scripts/check_admin_dist.py`，会解析 `admin_dist/index.html` 并检查 `/admin/assets/*` 引用文件存在且非空。
- `admin/package.json` 的 `npm run build` 已串联 `npm run check:dist`，构建后自动做 hash 资源检查。
- 已补 `tests/test_admin_dist_contract.py` 覆盖当前 dist、缺失资源报错和构建脚本约束。

### 4.11 自动化回归缺真实构建和静态路由 smoke

现状：

- `tests/test_admin_*` 多数是源码字符串合同测试。
- `admin/package.json` 只有 `dev/build/preview`，没有前端 test。
- 缺 Flask test client 对 `/admin`、静态资源、权限态的 smoke。

建议发布门禁：

- `python -m unittest`
- `cd admin && npm ci && npm run build`
- Flask test client 检查 `/health`、`/admin`、`/admin/login`、`admin_dist` 静态资源。
- 浏览器 smoke 检查登录页、主要后台页面、图片资源不白屏。

处理状态（2026-05-28）：已完成基础 Flask smoke，浏览器 smoke 仍保留为人工/后续自动化项。

- 已增加 `scripts/smoke_http_routes.py`，不用启动真实 HTTP 服务即可检查 `/health`、根路径跳转 `/admin`、`/admin` shell、`/admin/login` shell、admin hash 静态资源和未登录 `/api/web-auth/me`。
- 已补 `tests/test_http_smoke_contract.py`，保证 smoke runner 覆盖核心路由。
- 后续如接 CI，可把顺序固定为 `python -m unittest`、`cd admin && npm run build`、`python scripts/smoke_http_routes.py`。

### 4.12 工作台确认弹窗需要类型化

证据：

- `admin/src/components/business/workbench/workbench-page.tsx:1094` 使用 `flattenState(...).slice(0, 18)` 渲染普通 `Input`。
- `docs/react_admin_workbench_page_development_handbook.md:278` 要求按意图渲染客户、商品、颜色、数量、仓库等字段。

影响：

开单、调拨、进货、盘点前不能用结构化控件确认，容易误填。

建议：

- 按 `pending_intent/pending_action` 建 typed confirm schema。
- 商品用 Combobox，数量用数字输入，仓库用 Select，危险动作用 AlertDialog。
- 保留通用 fallback 处理未知技能。

处理状态（2026-05-28）：已完成第一版类型化确认弹窗。

- `AgentConfirmDialog` 已按销售单、工作流订单、商品匹配、进货、调货、盘点、泡袋上传分区渲染字段，不再直接把所有 pending state 平铺成一张表。
- 每个分区保留可编辑字段，并继续通过原 `updateSessionPending` 合并回 session state；未知结构仍走通用 fallback。
- 已补 `tests/test_admin_workbench_page_contract.py` 合同测试，锁定类型化 schema、分区组件和样式选择器。
- 后续增强项：商品/客户/仓库字段可以继续替换为 Combobox 或 Select，目前第一版仍使用现有 `Input` 保持风险低。

### 4.13 设置页用户权限缺当前用户保护

证据：

- `admin/src/components/business/settings/settings-page.tsx:1871`、`:1891` 附近可改角色/禁用账号。
- `admin/src/App.tsx:979` 没有向 `SettingsPage` 传当前用户。

影响：

管理员可能把自己降权或禁用，导致后台锁死。

建议：

- 传入当前用户。
- 禁止自禁用；自降权需二次确认并提示后果。
- 后端也应阻止最后一个管理员被禁用/降权。

处理状态（2026-05-28）：已完成当前账号与最后管理员保护。

- `App` 已把当前登录用户传入 `SettingsPage`，用户权限表可识别并标记“当前账号”。
- 当前账号的角色选择和启用开关在前端禁用，并增加安全提示，说明当前账号和最后一个管理员保护规则。
- `UserService.update` 已用 `operator_user_id` 阻止自禁用、自改角色，并阻止最后一个启用管理员被停用或降为非管理员。
- `/api/users/<id>` 已把当前 Web 登录用户作为 `operator_user_id` 传给服务层，避免绕过前端直接调用接口。
- 已补设置页合同测试和用户服务回归测试。

### 4.14 订单页分页和手工建单字段不完整

证据：

- `admin/src/components/business/orders/orders-page.tsx:100`、`:1088` 有分页状态但没有分页/加载更多入口。
- `tests/test_admin_order_page_contract.py:96` 反而排除了分页组件。
- `orders-page.tsx:79` 的 `OrderFormState` 缺图片和制作/配送字段。
- `orders-page.tsx:755` 附近表单无图片选择/上传。

影响：

超过首批订单无法浏览；React 后台手工建单信息不完整。

建议：

- 待制作、待配送、最近完成都支持分页或加载更多。
- 新建/编辑订单加图片资产选择/上传。
- 表单内加入制作、配送、完成状态字段。

处理状态（2026-05-28）：已完成主要修复。

- 订单看板已保留按状态列的独立分页，避免回到整页大分页。
- 手工新建/编辑订单表单已补订单图片上传、多图预览、移除图片、已制作、已配送、完成状态字段。
- 保存订单时已带上 `order_images`、`is_made`、`is_delivered`、`order_type`，后端 `/api/workflow/orders`、`WorkflowService.save_order()`、`NativeDBClient.save_workflow_order()` 均已接收并写入。
- 已补 `tests/test_admin_order_page_contract.py` 合同测试覆盖表单字段、图片上传 API、前后端保存字段传递。

### 4.15 库存流水和风险确认还不够稳

证据：

- `admin/src/components/business/inventory/inventory-page.tsx:913` 用 `keyword` 查 SKU 流水。
- `inventory-page.tsx:995` 提交调拨/盘点前只做基础校验。
- `docs/react_admin_inventory_page_development_handbook.md:432` 要求低库存、盘点差异触发风险确认。

影响：

同名 SKU 或多仓场景可能混入无关流水；大额盘点差异或超库存调拨容易误提交。

建议：

- 后端 `inventory_ledger` 支持 `sku_id`、`warehouse_id` 精确筛选。
- 调拨、盘点超过阈值时弹中央 `AlertDialog`。
- 弹窗展示当前库存、变更数量、变更后库存、影响仓库。

处理状态（2026-05-28）：

- 已完成。`InventoryLedgerDrawer` 改为按 `skuId + warehouseId` 查询，不再用 SKU 编号关键词模糊匹配单 SKU 流水。
- 已完成。`/api/inventory/ledger`、`InventoryService.ledger()`、`NativeDBClient.inventory_ledger()` 均支持 `sku_id`、`warehouse_id` 精确筛选。
- 已完成。调拨超出当前行库存、盘点差异过大时弹中央 `AlertDialog`，展示当前库存、变更数量、变更后库存和影响仓库，确认后才提交。
- 已补 `tests/test_admin_inventory_page_contract.py` 合同测试覆盖精确筛选和风险确认弹窗。

### 4.16 客户详情销售记录固定前 20 条

证据：

- `admin/src/components/business/customers/customer-detail-dialog.tsx:98` 固定 `pageSize: 20`。
- 销售 tab 无分页。

影响：

大客户历史订单无法完整核对。

建议：

- 像余额流水一样补销售记录分页、总数和加载状态。
- 支持按月份/状态筛选。

处理状态（2026-05-28）：

- 已完成。客户详情销售 tab 增加独立 `salesPage/salesTotal/salesPageCount`，使用 `salesPageSize` 分页加载，不再固定前 20 条。
- 已完成。销售记录支持按月份/近 1 月/近 3 月和付款状态筛选，筛选变化后自动回到第一页。
- 已完成。`/api/customers/<id>/sales`、`CustomerService.sales()`、`NativeDBClient.customer_sales()` 支持 `pay_status`，可筛选未结、已付款、月结、未付款。
- 已补 `tests/test_admin_customer_cards_contract.py` 合同测试覆盖销售分页和付款状态筛选。

## 5. P2：应尽快整理的体验、文档和维护项

处理状态（2026-05-28）：本节 5.1 至 5.8 已完成本轮收尾。

- 设置页已加入图片上传规则面板，图片资产仍与小程序设置分开。
- 商品模块旧 `MediaPage` 已清理，图片资产入口统一到设置页。
- 库存状态筛选已改后端筛选并保持分页。
- 客户收款/结款/调余额校验已加强，调整余额必须填写原因。
- 页面元信息、项目文档、自有库口径、日志忽略和依赖锁文件已更新。

下面 5.1-5.8 的“证据”保留为原始审查记录；本轮处理状态以上方清单为准。

### 5.1 设置页图片资产缺上传规则编辑

证据：

- `admin/src/components/business/settings/settings-page.tsx:1387` 已加载 `image_rules`。
- `settings-page.tsx:1503` 之后主要是资产库 UI，没有上传规则编辑面板。
- `docs/react_admin_settings_page_development_handbook.md:348` 要求资产库/上传规则双 tab。

建议：

- 图片资产保留为独立模块。
- 增加上传规则面板：OSS 路径、压缩规则、待绑定清理天数、1:1 主图规则。

### 5.2 商品模块保留旧 `MediaPage` 死代码

证据：

- `admin/src/components/business/products/index.ts:1` 仍导出旧组件。
- `admin/src/components/business/products/products-page.tsx:2270` 附近旧 `MediaPage` 仍存在。
- `products-page.tsx:2298` 仍含 `window.confirm`。
- App 已把媒体路由导向设置页。

建议：

- 删除旧导出，或改成明确重定向 wrapper。
- 测试同步到设置页图片资产入口。

### 5.3 库存状态筛选只筛当前页

证据：

- `admin/src/components/business/inventory/inventory-page.tsx:257`。
- `inventory-page.tsx:1423` 强制 `pageCount=1`。

影响：

后续页的零库存/负库存可能被隐藏。

建议：

- 改为后端筛选。
- 或保留分页并明确显示“当前页筛选”。

### 5.4 客户收款/调整校验偏弱

证据：

- `admin/src/components/business/customers/customer-balance-action-dialog.tsx:52` 用 `unpaid_amount || total_amount` 估算。
- `customer-balance-action-dialog.tsx:76` 提交不强制调整备注。

建议：

- 显式使用未付金额。
- 调整类必须填备注。
- 收款/结款动作需要展示影响的销售单和余额变化。

### 5.5 页面元信息和说明落后

证据：

- `admin/src/App.tsx:116`、`:119` 仍标商品/库存为“待迁移页面”。
- `admin/src/components/layout/page-header.tsx:39` 顶部说明仍写“当前接入登录态、工作台、设置页”。

建议：

- 更新页面状态文案。
- 把顶部说明改成当前后台能力边界。
- 文档中把旧计划标为历史参考。

### 5.6 文档口径混用 ERP 与自有库

证据：

- `README.md:8`、`docs/bag_upload_handoff.md:15` 仍写“ERP”。
- 实现已经走 `ProductService.save()` 和 `sjagent_core` 商品库。

建议：

- 统一表述为“sjagent_core 商品库/图片资产”。
- “ERP”只保留在历史迁移说明中。

### 5.7 开发日志未忽略

证据：

- 当前存在未跟踪 `admin/vite-workbench.err.log`、`admin/vite-workbench.out.log`。
- `.gitignore` 只忽略根 `logs/`，没有 `admin/*.log`。

建议：

- 忽略 `admin/*.log` 或统一写入 `logs/`。

### 5.8 依赖版本只有下限

证据：

- `requirements.txt` 多数为 `>=`。

建议：

- 生产部署使用锁文件。
- 定期受控升级，避免“今天能装、明天变坏”。

## 6. 建议新增的功能

### 6.1 数据看板

原因：

小程序需要热销数据，后台未来也需要看板。当前已有 `AnalyticsService.hot_products()`，但还没有完整看板。

建议模块：

- 销售趋势：今日、本周、本月销售额、订单数、客单价。
- 热销商品：按 SPU 聚合，支持时间范围、分类、客户类型。
- 客户分析：复购、欠款、月结、最近下单。
- 库存看板：低库存、零库存、长期未动、百鑫/本店库存对比。
- 工作流看板：待制作、待配送、超时、最近完成。

实现建议：

- 第一版可以实时 SQL 查询服务层，不必先新建数据库。
- 数据量上来后再增加日汇总表和缓存。
- API 放在 `/api/analytics/*`，小程序与后台共用服务层。

处理状态（2026-05-28）：已完成热销数据第一版。

- 已新增 `AnalyticsService.hot_products()`，支持 `today/7d/week/month/30d/90d`、SPU/SKU 维度、分类名过滤和数量限制。
- 已开放后台 `/api/analytics/hot-products` 与小程序 `/api/mini/analytics/hot-products`。
- 工作台右侧已经显示最近 7 天热销预览；完整趋势、客户复购、库存周转看板仍待独立页面实现。

### 6.2 统一业务决策服务

建议新建服务：

- `InventoryDecisionService`
- `OrderLinkService`
- `UploadValidationService`
- `AnalyticsService` 扩展热销/看板聚合

目的：

把智能体、React 后台、小程序对同一业务规则的调用统一起来，避免“一个地方调拨、一个地方进货、一个地方直接开单”。

### 6.3 权限感知 UI

现状：

后端有 `FIXED_ROLE_PERMISSIONS` 和路由权限规则，但前端侧边栏和按钮基本没有按权限收敛。

建议：

- `/api/web-auth/me` 返回权限列表。
- 前端按权限隐藏或禁用：删单、调库存、盘点、调拨、调余额、设置、用户管理。
- 后端继续作为最终权限边界，前端只做体验和误操作防护。

处理状态（2026-05-28）：已完成第一批权限感知 UI。

- `/api/web-auth/me` 已返回权限列表。
- 设置导航按权限隐藏，库存调拨/盘点/调整和客户调余额已按权限禁用。
- 后端权限仍作为最终边界；删单、商品删除等更多低频危险动作建议继续扩展。

### 6.4 图片资产治理

建议补齐：

- 批量上传进度与失败重试。
- 未绑定图片批量删除、批量归档、重复图片识别。
- 主图/颜色规格图强制 1:1 策略。
- 上传规则设置：最大尺寸、压缩、OSS 路径、清理天数。
- 媒体绑定审计：谁绑定、绑定到哪个 SPU/SKU、何时解绑。

### 6.5 打印中心增强

当前：

打印预览已可用，模板已经回到用户喜欢的版式，商品明细表格线更清楚。

建议补齐：

- 打印任务队列状态页。
- 打印失败原因和重试。
- 纸张/边距校准预设。
- 打印模板版本记录。
- 不同客户/场景模板预设。

## 7. 页面级调整清单

### 工作台

- 确认弹窗改为类型化表单。
- 输入框契约需要统一：用户更喜欢横向输入，文档和测试要跟实际设计保持一致。
- 快捷按钮保持在输入框上方。
- 业务结果弹窗保留中央弹窗，不做侧拉。
- 结果历史建议服务端持久化，不只靠 localStorage。

### 商品页

- 商品卡片当前方向是对的：1:1 图片、小卡片、状态徽章、常用上下架按钮。
- 需要补上传安全校验、批量上传进度、重复图片识别。
- 下架后后端写入要保证 SPU/SKU 全部同步，小程序只读 `listed_only=True`。
- 开单接口也要校验下架 SKU 不可继续售卖。

### 库存页

- 卡片瀑布式适合看“某款盒子某颜色百鑫/自己店库存”。
- 没库存的 SKU 应继续显示，便于进货调货。
- 流水查询改精确参数。
- 调拨/盘点增加风险确认。
- 库存筛选改后端，不只筛当前页。

### 订单页

- 名称“订单”比“工作流”更符合用户认知。
- 图片必须展示，点击图片中央弹窗。
- 详情用中央弹窗，空白处查看更多信息。
- 最近完成只显示 7 天内，超过用分页。
- 待制作/待配送也要有分页或加载更多。
- 完成后仍可取消已制作/取消配送。
- 手工建单补图片、制作、配送字段。

### 客户页

- 客户创建手机号后要触发小程序绑定链路，但必须经过可信手机号校验。
- 客户详情销售记录补分页。
- 收款/调整金额和备注校验加强。
- 对账单 PDF/打印模板后续接设置页。

### 设置页

- 商品基础只维护分类、单位、件规。
- 扣不扣库存只在库存规则页编辑，这是正确方向。
- 图片资产和小程序设置必须保持两个模块，不要合并。
- 用户权限要防止自禁用、自降权、最后管理员被禁用。
- 打印预览保留一个可点击打印按钮，避免顶部/底部重复。

## 8. 测试补强清单

优先新增这些回归：

1. 小程序手机号伪造注册不能绑定客户。
2. 微信 quick login 禁止客户端直传 openid/phone 绑定。
3. `SJAGENT_SECRET_KEY` 生产缺失时拒绝启动。
4. `/api/mini/` 私有接口不带 token 必须 401。
5. 商品裁图拒绝内网/localhost URL。
6. 上传非图片内容即使扩展名是 jpg 也必须失败。
7. session id 路径穿越被拒绝。
8. 下架 SKU 不能通过销售接口继续开单。
9. 百鑫 0、本店有货：调拨后销售出库仓正确。
10. 泡袋批量上传单位必须为“捆”。
11. 小程序个人中心客户只能看到自己的数据。
12. 热销商品按 SPU 聚合。
13. 工作流订单开单后回填销售单关联。
14. React build 后 `admin_dist/index.html` 引用资源存在。
15. Flask smoke 覆盖 `/health`、`/admin`、`/admin/login`、静态资源、未登录/已登录/403。

## 9. 推荐推进顺序

### 第一阶段：安全和错账风险

目标：先让系统不暴露客户数据、不伪造后台登录、不产生库存错账。

- 修手机号/微信绑定。
- 修 `SJAGENT_SECRET_KEY` 默认值。
- 修 `/api/mini/` 鉴权。
- 修上传/裁图安全。
- 修 session id 路径穿越。
- 修销售/库存写入对上下架状态的二次校验。
- 修调拨后开单仓库口径。
- 修泡袋单位写死。

### 第二阶段：业务闭环

目标：让订单、库存、客户、商品、小程序数据口径一致。

- 工作流订单回填销售单。
- 小程序个人中心按客户隔离。
- 热销 API 接首页和看板。
- 库存流水精确查询。
- 订单页分页、图片字段、制作/配送字段。
- 客户详情销售分页。

### 第三阶段：运营体验

目标：减少误操作，让日常使用更舒服。

- 工作台类型化确认弹窗。
- 库存调拨/盘点风险确认。
- 设置页自降权/自禁用保护。
- 图片资产上传规则。
- 打印中心增强。

### 第四阶段：发布工程化

目标：服务器更新可重复、可验证、可回滚。

- 明确 `admin_dist` 策略。
- Docker host 绑定修复。
- 本地/服务器/Docker 启动文档拆分。
- 加 CI 或最小发布门禁。
- 清理过期文档和开发日志。

## 10. 结论

这个系统的方向是对的：React 后台已经开始贴近真实业务，商品、库存、订单、客户、设置这几块也越来越像一个能长期使用的运营后台。但现在最大的问题不是 UI，而是“可信边界”和“业务口径统一”。

建议下一步不要继续堆新页面，先把 P0/P1 修完。尤其是小程序客户绑定、后台密钥、miniapp 鉴权、调拨后开单仓库、泡袋单位这几项，都是会影响安全、客户数据、库存账的基础问题。修完这些，再做数据看板和体验优化，会稳很多。
