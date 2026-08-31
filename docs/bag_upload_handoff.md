# 泡袋上传与模板交接

这份文档用于新对话快速接上泡袋批量上传功能的当前状态。

## 当前能力

用户在 React 后台工作台输入“上传泡袋”后，智能体会进入泡袋商品流程：

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

## 相关文件

- 智能体流程：`src/skills/bag_upload/workflow.py`
- 预处理脚本：`scripts/bag_template/prepare_bag_image_v2.py`
- 主图/详情页生成脚本：`scripts/bag_template/batch_generate.py`
- resvg 渲染器：`scripts/bag_template/render_svg_resvg.js`
- 手动调参网页：`scripts/bag_template/bag_manual_adjust.html`
- 示例标准图：`scripts/bag_template/SJ0506-raw-standard.png`

## 部署要求

### 上传限制

- 单张图片默认 25MB，泡袋 ZIP 默认 100MB，分别由 `SJAGENT_MAX_IMAGE_UPLOAD_BYTES`、`SJAGENT_MAX_BAG_ARCHIVE_UPLOAD_BYTES` 设置（字节，MB 按 1024 × 1024 计算）。
- 只有 `/api/images/upload` 的请求体额度增加，额外预留 1MB 表单开销；其他接口保持原额度。图片本身仍按 25MB 校验。
- 前端从 `/api/images/upload-limits` 获取当前限制，超限文件不发送上传请求；失败会结束等待消息，并保留失败文件及尚未提交的文件供手动重试。
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
```

仓库中提供同内容的 `scripts/nginx/bag-upload.conf`，可在站点 `server` 块内使用 `include /opt/sjagent/scripts/nginx/bag-upload.conf;`，不要同时配置两份相同的 location。

调整 ZIP 配额后同步更新该入口额度并预留 1MB；先运行 `nginx -t`，通过后再 reload。不要只改反代而遗漏应用额度。批量处理中断或超时后先核对已生成的商品，再重试，避免重复新增。

回归检查：`python -m unittest tests.test_bag_upload_limits -q`；前端安装依赖后执行 `node --test tests/test_agent_upload_frontend.mjs`。

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
