# 泡袋上传与模板交接

这份文档用于新对话快速接上泡袋批量上传功能的当前状态。

## 当前能力

工作台快捷按钮“上传泡袋”直接打开居中弹窗，不发送聊天消息：

1. 选择岩茶、红茶或宽版，填写本批售价（元/捆，正数、最多两位小数），设置是否上架。
2. 类型切换时恢复对应默认价：岩茶 18、红茶 10、宽版 18；默认勾选上架。设置只作用于本批。
3. 选择一个 ZIP，核对文件名和大小，点击“开始上传”。处理中禁止重复提交、编辑和关闭弹窗，不展示估算百分比。
4. 完成后在弹窗查看新增/更新的商品名称、编号、售价、上架状态和逐项失败原因，同时在当前对话追加简要结果。

独立接口 `POST /api/product/bag-upload` 接收 multipart 字段 `archive`、`bag_type`、`price`、`is_listed`（`1`/`0`）。需同时有“设置”和“图片上传”权限，且启用 `bag_upload` 功能。该接口不读取或修改聊天 pending，已有待确认销售单保留。

商品资料、售价和 `is_listed` 在同一次商品保存事务写入；勾选上架同时保证商品启用，取消勾选只控制未上架。新增和带 SJ 编号更新都采用本批设置。单个商品保存失败列为失败，不影响其他商品；不提供整包自动重试。网络中断或超时需先核对商品库，避免重复新增。

原聊天输入“上传泡袋”的逐步流程继续兼容，未传新选项时保持原价格和上架处理。底层共用流程如下：

1. 询问泡袋类型：岩茶、红茶或宽版。
2. 用户上传 zip 压缩包，里面放多个 PNG 原始图。
3. 系统解压 PNG，文件名作为商品标题。
4. 原始图先由 `prepare_bag_image_v2.py` 预处理成标准泡袋图。
5. 标准图由 `batch_generate.py` 套模板，生成主图和详情页。
6. 主图和详情页上传 OSS。
7. 写入 sjagent_core 商品库和图片资产：文件名带 `SJ` 编号则更新已有商品，不带编号则新增商品。
8. 流程结束后清理服务器本地临时 zip、预处理图、主图、详情页和批处理目录。

## 模板规则

- 背景色：`#f8f8f8`。
- 固定副标题：`雅致非凡，尽显格调`。
- 网页模板和批处理脚本使用同一套 SVG/resvg 渲染逻辑。
- 服务器渲染依赖开源字体 `fonts-noto-cjk`，本地 Windows 仍优先使用微软雅黑。

## 岩茶

- 模板名：`rock-tea` / `岩茶`。
- 标准图尺寸：`550 x 1500`。
- 规格展示：`55MMx150MM`。
- 默认售价：`18` 元。
- 商品标题后缀：`长泡袋`。
- 分类优先级：原始文件名带“品种”时归已有的品种分类（ID `19`，数据库名称“品种茶袋”，展示名称“品种茶泡袋”）；否则沿用肉桂、水仙、大红袍等已有关键词分类；没有匹配时归“公版泡袋”（ID `9`）。
- “品种”只作为分类标记，生成图片、商品入库和完成提示里的商品名均去掉这两个字，并清理标记旁多余的空格、分隔符或空括号。
- 红茶、宽版模板仍分别固定归“红茶泡袋”和“宽版泡袋”，不被“品种”标记覆盖。

## 红茶

- 模板名：`black-tea` / `红茶`。
- 标准图尺寸：`520 x 1100`。
- 规格展示：`52MMx110MM`。
- 默认售价：`10` 元。
- 分类固定：`红茶泡袋`。
- 商品标题后缀：`短泡袋`。

## 文件名规则

PNG 文件名就是商品名。支持下面这些编号格式：

- `正山小种-SJ00022.png`
- `正山小种-sj00022.png`
- `SJ0509-小赤甘.png`
- `【SJ0509】小赤甘.png`

如果文件名里有 `SJ` 编号，系统会按该编号查询 sjagent_core 商品库并更新主图/详情页。找不到对应商品时会跳过，避免重复创建。

如果文件名里没有编号，系统会按 `SJ` 编号规则新增商品。

例如岩茶模板下，`奇兰.png` 归公版泡袋，`奇兰品种.png` 归品种茶泡袋，两者生成的名称主体都为“奇兰”；`老枞水仙.png` 仍归水仙泡袋，`水仙品种.png` 则优先归品种茶泡袋。

带编号重新上传时，分类仍按本次原始文件名判断；仅有编号、没有名称或标记时用已有商品名称判断。商品名称沿用已有详情，只去掉“品种”标记，不使用不同的文件名改名；图片标题与完成提示保持一致。编号、规格保留，弹窗上传时售价和上架状态按本批设置更新。不批量清理历史商品，也不调整小程序分类隐藏规则。

分类和名称回归检查：`python -m unittest tests.test_bag_upload_categories tests.test_p0_inventory_and_bag_upload -q`，包含单图、ZIP 混合分类、并发处理、带编号更新和红茶/宽版模板。

## 相关文件

- 智能体流程：`src/skills/bag_upload/workflow.py`
- 上传弹窗：`admin/src/components/business/workbench/bag-upload-dialog.tsx`
- 独立上传接口：`src/channels/http_api/__init__.py`
- 预处理脚本：`scripts/bag_template/prepare_bag_image_v2.py`
- 主图/详情页生成脚本：`scripts/bag_template/batch_generate.py`
- resvg 渲染器：`scripts/bag_template/render_svg_resvg.js`
- 手动调参网页：`scripts/bag_template/bag_manual_adjust.html`
- 示例标准图：`scripts/bag_template/SJ0506-raw-standard.png`

## 部署要求

### 上传限制

- 单张图片默认 25MB，泡袋 ZIP 默认 100MB，分别由 `SJAGENT_MAX_IMAGE_UPLOAD_BYTES`、`SJAGENT_MAX_BAG_ARCHIVE_UPLOAD_BYTES` 设置（字节，MB 按 1024 × 1024 计算）。
- `/api/images/upload` 和 `/api/product/bag-upload` 的请求体额度增加，额外预留 1MB 表单开销；其他接口保持原额度。图片本身仍按 25MB 校验。
- 前端从 `/api/images/upload-limits` 获取当前限制，超限文件不发送上传请求。弹窗完成或结果不确定时不允许原包重复提交，部分失败应核对后单独处理失败文件。
- 每个 ZIP 最多 100 张 PNG、1000 个目录/文件项，单张解压后最多 64MB，整个压缩包解压后总大小最多 512MB；不支持加密 PNG。校验在解压和商品写入之前执行。
- Nginx 在现有站点配置中为此入口增加精确匹配，保留原 HTTPS、鉴权转发等设置：

```nginx
location = /api/images/upload {
    client_max_body_size 101m;
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}

location = /api/product/bag-upload {
    client_max_body_size 101m;
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 1800s;
    proxy_send_timeout 300s;
}
```

仓库中提供同内容的 `scripts/nginx/bag-upload.conf`，可在站点 `server` 块内使用 `include /opt/sjagent/scripts/nginx/bag-upload.conf;`，不要同时配置两份相同的 location。

调整 ZIP 配额后同步更新该入口额度并预留 1MB；先运行 `nginx -t`，通过后再 reload。不要只改反代而遗漏应用额度。批量处理中断或超时后先核对已生成的商品，再重试，避免重复新增。

回归检查：`python -m unittest tests.test_bag_upload_limits tests.test_bag_upload_dialog_api tests.test_bag_upload_categories tests.test_admin_bag_upload_dialog_contract -q`；前端安装依赖后执行 `node --test tests/test_agent_upload_frontend.mjs`。新弹窗的校验、重复提交锁和 multipart 测试也可通过 `node --test admin/src/components/business/workbench/bag-upload-dialog.test.cjs` 单独运行。

在服务器上需要：

```bash
cd /opt/sjagent/scripts/bag_template
npm ci --omit=dev
apt-get install -y fonts-noto-cjk
fc-cache -f
systemctl restart sjagent.service
```

当前线上服务目录是 `/opt/sjagent`，systemd 服务名是 `sjagent.service`。

## 清理策略

- OSS 上传成功后，本地主图和详情页会立即删除。
- 不管某个商品写入 sjagent_core 商品库成功还是失败，只要生成过本地图，都会在 `finally` 中清理。
- 不管批量里是否有失败项，上传 zip 和批处理目录都会在流程结束时清理。
- 失败原因会保留在对话结果里，不依赖服务器残留图片排查。

## 注意事项

- 不要把 Windows 的微软雅黑字体直接提交或复制到服务器作为项目字体，授权不稳。服务器使用 `fonts-noto-cjk`。
- 泡袋模板交接只包含泡袋相关脚本、模板和示例图。
- `data/generated/` 和 `data/uploads/` 里的泡袋测试图属于临时产物，不应作为功能提交的一部分。
