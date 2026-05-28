# React 后台 AI 工作台开发项目书

版本: v0.2
日期: 2026-05-27
适用入口: `/admin`
旧版参考: `/web` 里的 `AI 业务工作台`
关联接口: `/api/agent/chat`, `/api/agent/chat/stream`, `/api/images/upload`, `/api/session/pending`, `/api/agent/history`
关联业务页: 开单、销售单、订单、库存、客户、商品、设置、打印

## 0. 定位修正

这里的“工作台”不是普通首页，也不是数据看板。

旧 WebUI 的工作台核心是 AI 对话界面:

- 用户用自然语言开单、查库存、进货、盘点、调货、生成工作流订单、上传图片识别。
- AI 返回结果后，页面展示结构化确认卡、最近业务记录和可执行动作。
- 今日销售数量、今日销售金额、待完成订单只是辅助状态，不是页面主线。

React 版 `/admin` 必须恢复这个定位。以后如果要做经营数据、热销分析、趋势看板，应另建“数据看板”或“分析看板”，不要占用“工作台”这个入口。

## 1. 页面目标

工作台是北极星后台的 AI 操作入口，目标是让用户“说一句话就开始做业务”，同时把 AI 的执行过程变成可核对、可编辑、可确认的后台界面。

第一阶段必须支持:

- 文本对话: 开单、查库存、进货、盘点、调货、工作流订单、销售查询、打印、客户创建、常用帮助。
- 图片上传: 上传订单图或设计稿，后端识别后进入工作流或销售单确认。
- Pending 确认: AI 需要确认时，前端展示结构化表单，用户可改字段后确认执行。
- 最近业务记录: 保留最近查询、开单、工作流、库存动作，方便回看和继续操作。
- 中间弹窗: 所有确认、详情、图片预览、风险操作都用居中 Dialog，不用侧拉。
- 服务层一致: AI 最终写入销售、库存、客户、订单时必须走已有服务层或服务层包装 API，前端不能复制业务规则。

第一阶段不做:

- 普通经营首页。
- 大屏报表。
- 复杂趋势图。
- 独立于 Agent 的另一套开单/库存逻辑。
- 直接在前端写数据库或绕过服务层。

## 2. 旧 WebUI 调研结论

旧版工作台位于 `src/channels/http_api/webui_template.html` 和 `src/channels/http_api/webui_api.js`。

### 2.1 旧页面结构

旧页面在 `#workbench` 下主要包含:

```text
workbench
  workspace
    hero-strip
      今日销售单数量
      今日销售金额
      待完成订单

    chat
      chat-head
        AI 业务工作台
        智能体在线
        新会话
      messages
        assistant / user message

    command-strip
      开单 / 盘点 / 调货 / 进货 / 工作流 / 查库存 / 上传泡袋

    composer
      附件按钮
      file input
      chat input
      发送按钮
      attachment tray

contextPanel
  最近业务记录

businessConfirmMask
  业务确认弹窗
```

说明:

- 旧版已有 AI 对话、快捷指令、附件上传、最近业务记录。
- 旧版右侧 `contextPanel` 是最近业务记录，不是经营看板。
- 旧版仍有 `drawer`，React 版要改成居中 `Dialog`，符合现在后台交互要求。

### 2.2 当前可用接口

| 功能 | 接口 | 现状 | React 用法 |
| --- | --- | --- | --- |
| 文本对话 | `POST /api/agent/chat` | 可用 | 第一阶段主接口 |
| 流式对话 | `POST /api/agent/chat/stream` | 可用但仍是执行完成后分段输出 | 后续可接，第一阶段可先用普通对话 |
| 图片识别 | `POST /api/images/upload` | 可用，一次上传一张图 | 附件上传入口，批量时前端逐张提交 |
| pending 编辑 | `POST /api/session/pending` | 可用 | 确认弹窗保存修改后调用 |
| 会话历史 | `GET /api/agent/history?session_id=xxx` | 可用 | 新会话/恢复会话时加载 |
| 工作台辅助数字 | `GET /api/dashboard/summary` | 可用 | 只放紧凑状态条，不做主页面 |
| 库存快捷查询 | `/api/inventory/*` | 可用 | 简单库存查询可以走服务层快查 |

`/api/agent/chat` 当前返回:

```json
{
  "code": 0,
  "data": {
    "response": "处理结果文本",
    "session_id": "web_...",
    "session": {
      "has_pending": true,
      "pending_intent": "order",
      "pending_action": "confirm_create_order",
      "state": {},
      "last_extraction": {},
      "last_order": {}
    }
  }
}
```

React 版不要假设后端一定返回结构化结果卡。第一阶段以 `response` 文本和 `session` 快照为准，再通过适配器生成可展示的确认卡、业务记录和动作。

### 2.3 Agent 能力范围

当前 `SkillEngine` 已注册的主要意图包括:

| 意图 | 业务含义 |
| --- | --- |
| `order` | 销售开单 |
| `inventory` | 查库存 |
| `stocktaking` | 盘点 |
| `purchase` | 进货 |
| `transfer` | 调货/调拨 |
| `workflow` | 设计稿/过程订单 |
| `sales_query` | 销售单查询 |
| `sales_manage` | 销售单删除、作废等管理动作 |
| `customer_manage` | 创建客户 |
| `print` | 打印销售单 |
| `series_manage` | 1 件起订等系列规则 |
| `bag_upload` | 泡袋上传，受设备功能开关控制 |
| `help/chat/unknown` | 帮助、闲聊、兜底 |

React 工作台要尊重这个边界。页面只负责输入、展示、确认和调用接口，不在前端重新判断“该不该扣库存”“客户该不该月结”等业务规则。

## 3. 信息架构

React 工作台建议改成“两栏主界面 + 中间弹窗结果”。主界面只负责对话和回看，所有需要核对、查看详情、确认执行的业务结果都进入居中 Dialog。

```text
AgentWorkbenchPage
  WorkbenchStatusStrip
    今日销售单
    今日销售额
    待完成订单
    当前会话状态

  WorkbenchPanels
    ConversationPanel
      ChatHeader
      MessageList
      CommandStrip
      ChatComposer

    BusinessContextPanel
      RecentBusinessCards
      SessionTools
      PendingStatusCard

  DialogLayer
    AgentResultDialog
    AgentConfirmDialog
    InventoryResultDialog
    ImageOcrResultDialog
    ImagePreviewDialog
    BusinessDetailDialog
    RiskConfirmDialog
    SessionHistoryDialog
```

### 3.1 ConversationPanel

对话是主线。

内容:

- 顶部显示“AI 业务工作台”、智能体状态、新会话按钮。
- 中间是消息列表，用户消息靠右，AI 消息靠左。
- 底部是快捷指令和输入区。
- 输入区用 `Textarea`，支持多行，不再用单行 `Input`。
- 支持 Enter 发送、Shift+Enter 换行。
- 支持粘贴图片、选择附件、拖入图片。

### 3.2 Result Dialog

不要在主界面常驻一个大“执行结果”区域。执行结果应该做成居中弹窗，因为它是一次业务动作的核对和查看，不是后台首页信息。

弹窗触发规则:

1. 有 `session.has_pending` 且 `pending_action` 包含 `confirm_`: 打开 `AgentConfirmDialog`。
2. 图片识别返回 OCR/工作流结果: 打开 `ImageOcrResultDialog` 或直接进入确认弹窗。
3. 库存查询返回多 SKU/多仓库数据: 打开 `InventoryResultDialog`。
4. 销售单、工作流、进货、调货、盘点、打印等动作完成: 打开 `AgentResultDialog` 展示结果摘要和后续动作。
5. 普通闲聊、帮助、简单失败提示: 只显示在消息气泡，不弹窗。

主界面只保留很轻的状态提示，例如“当前有待确认操作”或“最近完成 1 条业务记录”。用户关闭弹窗后，右侧最近业务记录仍能重新打开详情。

### 3.3 BusinessContextPanel

右侧只放轻量上下文:

- 最近 5 条业务记录。
- 当前 session 的 last order。
- 当前 session 的 last extraction。
- 当前 pending 的小提示卡，不展示大表单。
- 删除、查看、打印等小按钮。

右侧记录用于回看，不替代销售单页、订单页、库存页。点击详情时打开居中 Dialog。

### 3.4 移动端布局

窄屏不硬塞多栏，改成 Tabs:

- `对话`
- `记录`

输入区固定在对话 Tab 底部，确认弹窗仍居中显示。

## 4. 操作逻辑

### 4.1 进入页面

进入 `/admin` 后:

1. 校验登录态。
2. 从 `localStorage` 读取 `sj_admin_agent_session_id`。
3. 没有 session 时创建 `web_${Date.now()}`。
4. 请求 `/api/agent/history?session_id=...` 恢复服务端历史。
5. 读取本地最近业务记录 `sj_admin_business_history_${sessionId}`。
6. 请求 `/api/dashboard/summary` 只更新顶部辅助数字。
7. 如果历史为空，显示一条简短欢迎消息和可用快捷指令。

失败处理:

- 历史加载失败不影响用户输入。
- 辅助数字加载失败只显示 `--` 和重试按钮。
- Agent 未初始化时，输入区禁用并显示错误提示。

### 4.2 发送文本

用户发送文本后:

1. 立即追加用户消息。
2. 清空输入框。
3. 追加 AI 占位消息“正在处理...”。
4. 调用 `POST /api/agent/chat`。
5. 成功后用 `data.response` 更新 AI 消息。
6. 保存 `data.session` 到当前状态。
7. 如果 `session.has_pending` 为真，进入 pending 流程。
8. 如果没有 pending，根据 `last_order`、结构化事件或文本解析生成最近业务记录。
9. 如果这次是库存、销售单、工作流、进货、调货、盘点、打印等业务结果，打开对应 `ResultDialog`。
10. 刷新右侧最近业务记录。

发送期间:

- 发送按钮进入 loading。
- 禁止重复提交。
- 允许用户继续看历史，但不允许再次确认同一个 pending。

### 4.3 Pending 确认

当 `session.has_pending === true`:

- 如果 `pending_action` 包含 `confirm_`，自动打开 `AgentConfirmDialog`。
- 同时在右侧最近记录上方显示一个轻量 `PendingStatusCard`，方便用户关闭弹窗后还能重新打开确认。
- 如果只是缺少参数的追问，不弹确认框，只在消息里继续问。

确认弹窗行为:

1. 根据 `pending_intent` 和 `pending_action` 渲染结构化字段。
2. 用户可修改客户、商品、颜色、数量、价格、仓库、备注等字段。
3. 点击确认前先调用 `POST /api/session/pending` 保存修改。
4. 保存成功后再发送 `"确认"` 到 `/api/agent/chat`。
5. 点击取消发送 `"取消"`，后端清理 pending。
6. 点击右上角关闭只关闭弹窗，不确认、不取消，pending 仍保留。

必须支持的确认类型:

| pending 类型 | 弹窗标题 | 核心字段 |
| --- | --- | --- |
| `confirm_create_order` | 销售单确认 | 客户、商品、颜色、数量、仓库、单价 |
| `confirm_image_sales` | 图片开单确认 | 识别出的客户和商品 |
| `confirm_product_name` | 商品匹配确认 | 商品、颜色 |
| `confirm_image_workflow_orders` | OCR 识别结果 | 客户、商品、颜色、数量、备注 |
| `confirm_create_workflow_order` | 工作流订单确认 | 客户、商品、颜色、数量、备注 |
| `purchase` | 进货确认 | 商品、颜色、数量、入库仓库 |
| `transfer` | 调货确认 | 调出仓库、调入仓库、商品、数量 |
| `stocktaking` | 盘点确认 | 仓库、商品、盘点后数量 |
| `bag_upload` | 泡袋上传确认 | 模板、商品名、分类、图片 |

### 4.4 图片上传

上传入口支持:

- 点击附件按钮选择图片。
- 粘贴剪贴板图片。
- 拖拽图片到对话区。

处理规则:

- 当前 `/api/images/upload` 一次只接收一张图片。
- 如果用户选择多张，前端按顺序逐张上传，每张都生成一条用户图片消息和一条 AI 识别结果。
- 上传图片后必须带当前 `session_id`，保证识别结果进入同一个 pending 链路。
- OCR 识别结果不放在主界面大区域里，必须打开 `ImageOcrResultDialog` 或进入 `AgentConfirmDialog`。
- 图片预览用 `ImagePreviewDialog`，不打开新页面。
- 上传失败时保留用户消息，并在 AI 消息位置显示失败原因。

图片用途:

- 订单图: 识别客户、商品、数量，进入工作流或销售单确认。
- 设计稿: 创建工作流订单。
- 泡袋图: 如果 `bag_upload` 功能启用，进入泡袋上传流程。

### 4.5 快捷指令

快捷指令不是独立功能，只是帮用户组织输入。

建议指令:

| 指令 | 行为 |
| --- | --- |
| 开单 | 在输入框插入 `开单 ` |
| 查库存 | 插入 `查库存 ` |
| 进货 | 插入 `进货 ` |
| 调货 | 插入 `调货 ` |
| 盘点 | 插入 `盘点 ` |
| 工作流 | 插入 `工作流 ` |
| 上传泡袋 | 直接发送 `上传泡袋`，进入泡袋流程 |

React 版可以先用横向按钮，后续再升级为 `Command` 弹层。

### 4.6 库存查询

旧 WebUI 对简单库存查询做了前端快查。React 版建议:

- 简单句式如“查半斤红色库存”可以先走库存服务层接口，提高速度。
- 复杂句式如“查库存，顺便看能不能给某客户开 20 套”必须走 Agent，因为需要综合开单规则。
- 快查结果也要以 AI 消息、`InventoryResultDialog` 和右侧记录摘要展示，不能变成另一个库存页面。
- 如果当前有 pending，只有用户明确发起新请求时才切走，不要误清 pending。

### 4.7 最近业务记录

最近业务记录按 session 存本地，最多 5 条。

记录类型:

- 库存查询。
- 销售单创建。
- 工作流订单创建。
- 进货。
- 调货。
- 盘点。
- 打印。
- 客户创建。

每条记录包含:

```ts
type BusinessHistoryItem = {
  id: string
  businessKey?: string
  type: "inventory" | "sales" | "workflow" | "purchase" | "transfer" | "stocktaking" | "print" | "customer"
  title: string
  label: string
  summary: string
  createdAt: string
  orderId?: string
  actions?: BusinessAction[]
}
```

如果同一个销售单或工作流单重复出现，用 `businessKey` 去重，把最新记录放到最前面。

### 4.8 新会话和历史

新会话按钮:

- 创建新的 `session_id`。
- 清空当前消息列表。
- 清空当前 pending。
- 不删除旧 session 文件。
- 本地记录旧 session 到最近会话列表。

历史:

- 当前已有 `/api/agent/history?session_id=xxx`，用于恢复指定 session。
- 后端暂时没有 session 列表接口，第一阶段用 localStorage 保存最近 session。
- 后续可新增 `GET /api/agent/sessions`，让多设备也能恢复历史。

## 5. 组件使用规范

组件必须沿用当前 React + Radix/shadcn 体系，以 `admin/src/components/ui` 为准。

| 页面需求 | 组件 | 使用规则 |
| --- | --- | --- |
| 主布局 | CSS Grid 或 `ResizablePanelGroup` | 桌面两栏: 对话 + 最近记录；窄屏 Tabs |
| 消息滚动 | `ScrollArea` | 对话区独立滚动，不让整页抖动 |
| 输入区 | `Textarea`, `Button` | Enter 发送，Shift+Enter 换行 |
| 附件按钮 | `Button`, `Tooltip` | 用 lucide `Paperclip` / `Image` 图标 |
| 快捷指令 | `Button`，后续 `Command` | 第一阶段保持轻量 |
| 状态 | `Badge` | 智能体在线、pending、已完成 |
| 执行结果 | `Dialog`, `Table`, `Badge`, `Card` | 当前结果用中间弹窗展示 |
| 最近记录 | `Card`, `DropdownMenu` | 右栏最多 5 条 |
| 业务确认 | `Dialog` | 居中弹窗，禁止侧拉 |
| 风险确认 | `AlertDialog` | 删除、取消、覆盖库存等 |
| 图片预览 | `Dialog` | 居中大图，可左右切换 |
| 会话历史 | `Dialog`, `Table` | 中间弹窗，不用 Drawer |
| 加载态 | `Skeleton` | 消息、结果卡、状态条都要有 |
| 错误 | `Alert` 或现有 toast | 不使用 `window.alert` |

禁止新增:

- `Sheet` / `Drawer` 作为工作台详情或确认。
- 原生 `<button>` 做业务按钮。
- 原生 `<select>` 做核心业务选择。
- 大 Hero、渐变背景、营销式卡片。
- 把数据看板塞进工作台第一屏。
- 常驻大面积 `ExecutionPanel` 展示业务结果。

## 6. Dialog 规范

用户明确要求: 弹窗做中间，不做侧拉。

工作台所有弹窗都走中间 `Dialog` 或 `AlertDialog`:

| 弹窗 | 用途 | 宽度建议 |
| --- | --- | --- |
| `AgentConfirmDialog` | AI 写入前确认和编辑 | 720-880px |
| `AgentResultDialog` | 销售单、工作流、进货、调货、盘点、打印完成后的结果 | 720-900px |
| `InventoryResultDialog` | 多 SKU / 多仓库库存查询结果 | 760-960px |
| `ImageOcrResultDialog` | 图片识别出的客户、商品、颜色、数量、备注 | 760-960px |
| `BusinessDetailDialog` | 销售单/工作流/库存动作详情 | 760-960px |
| `ImagePreviewDialog` | 查看上传图或识别图 | 720-1000px |
| `RiskConfirmDialog` | 删除、取消、覆盖等风险动作 | 420-520px |
| `SessionHistoryDialog` | 查看和恢复历史会话 | 720-900px |

弹窗要求:

- 点击空白处关闭只关闭弹窗，不执行确认。
- 确认执行必须点明确按钮。
- 弹窗底部按钮顺序统一: 左侧次要动作，右侧主动作。
- 键盘 Esc 关闭弹窗，但不能误触发取消 pending。
- 表单字段错误显示在字段下方，不只弹 toast。

结果弹窗内容要求:

- 顶部标题直接写业务类型，例如“库存查询结果”“销售单已创建”“工作流订单已创建”。
- 主体用表格或结构化字段，不把 AI 大段文本原样塞进去。
- 底部提供明确后续动作，例如“查看销售单”“打印预览”“打开订单页”“再次编辑”“关闭”。
- 关闭结果弹窗不影响右侧最近业务记录，用户可以从记录里再次打开。
- 只有确认类弹窗会触发写入；结果类弹窗只负责查看和跳转。

## 7. 数据流设计

### 7.1 前端状态

建议拆成 4 个 hook:

```ts
useAgentSession()
  sessionId
  sessionSnapshot
  createNewSession()
  loadHistory()
  updatePendingState()

useAgentMessages()
  messages
  appendUserMessage()
  appendAssistantMessage()
  updateMessage()
  persistMessages()

useAgentTransport()
  sendMessage()
  uploadImages()
  isSending
  error

useAgentResultDialog()
  openResult()
  closeResult()
  resultType
  resultPayload

useBusinessHistory()
  items
  pushItem()
  removeItem()
  restoreItems()
```

### 7.2 API client

在 `admin/src/lib/api.ts` 增加或补齐:

```ts
agentChat(payload)
agentChatStream(payload)
agentHistory(sessionId)
updateSessionPending(sessionId, state)
uploadAgentImage(file, sessionId)
dashboardSummary()
```

类型建议:

```ts
type AgentSessionSnapshot = {
  has_pending: boolean
  pending_intent?: string
  pending_action?: string
  state?: Record<string, unknown>
  last_extraction?: Record<string, unknown>
  last_order?: Record<string, unknown>
}

type AgentChatResponse = {
  response: string
  session_id: string
  session: AgentSessionSnapshot
}
```

### 7.3 结果适配器

后端第一阶段主要返回文本，所以前端需要一个轻量适配器:

```ts
buildPendingView(session)
buildBusinessHistoryFromResponse(session, response)
buildInventoryResultFromResponse(response)
```

适配器只做展示，不做业务判断。

后续推荐后端在 Agent 返回中增加结构化字段:

```json
{
  "response": "已创建销售单...",
  "events": [
    {
      "type": "sales_created",
      "id": "SO...",
      "customer": "齐唯茶业",
      "items": [],
      "total": 360
    }
  ]
}
```

有了 `events` 后，前端就不需要解析文本。

## 8. 文件结构建议

```text
admin/src/components/business/workbench/
  workbench-page.tsx
  workbench-status-strip.tsx
  conversation-panel.tsx
  message-list.tsx
  message-bubble.tsx
  command-strip.tsx
  chat-composer.tsx
  business-context-panel.tsx
  pending-status-card.tsx
  agent-confirm-dialog.tsx
  agent-result-dialog.tsx
  inventory-result-dialog.tsx
  image-ocr-result-dialog.tsx
  image-preview-dialog.tsx
  session-history-dialog.tsx
  risk-confirm-dialog.tsx
  workbench-adapters.ts
  workbench-types.ts
```

路由:

- `/admin` 指向 `WorkbenchPage`。
- 如已有普通 Dashboard 组件，改名为 `AnalyticsPage` 或后续迁到 `/admin/analytics`。
- 不再把 `/admin` 绑定到经营首页。

## 9. 视觉和交互标准

工作台要和当前后台组件风格一致:

- 仍然是黑、白、灰为主，少量状态色只用于成功、警告、危险。
- 不做大面积渐变。
- 不做“AI 科技感”装饰。
- 消息气泡保持克制，圆角不超过现有卡片体系。
- 卡片不嵌套卡片。
- 对话栏和右侧记录栏高度固定在页面可视高度内，各自独立滚动。
- 输入区固定在对话栏底部，发送时不跳动。
- 右侧记录要比对话区更紧凑，避免抢主线。
- 结果弹窗要比确认弹窗更偏“查看”，确认弹窗才偏“编辑和执行”。

桌面建议宽度:

| 区域 | 宽度 |
| --- | --- |
| 对话区 | minmax(520px, 1fr) |
| 记录区 | 260-320px |

窄屏:

- 两栏改 Tabs。
- 顶部状态条最多两列。
- 消息最长宽度不超过容器 86%。

## 10. 业务边界

工作台是入口，不是业务规则中心。

| 行为 | 要求 |
| --- | --- |
| 开销售单 | 由 Agent workflow 调用销售服务层，前端只确认 |
| 删除销售单 | 走销售单删除接口，必须弹风险确认 |
| 查库存 | 走库存服务层或 Agent，不直接查旧 ERP |
| 进货 | 走库存服务层，写库存流水和操作人 |
| 调货 | 走库存服务层，两边仓库同时变动 |
| 盘点 | 走库存服务层，写盘点流水 |
| 工作流订单 | 走过程订单接口，不扣库存 |
| 图片识别 | 走 `/api/images/upload`，结果进入同一 session |
| 打印 | 走打印任务接口，不直接拼打印状态 |
| 客户创建 | 走客户服务层，手机号绑定规则仍在后端 |

如果前端发现 Agent 返回和业务页展示不一致，以业务服务层数据为准，并把工作台记录刷新掉。

## 11. 测试和验收

### 11.1 前端契约测试

新增 `tests/test_admin_workbench_page_contract.py`，至少检查:

- `/admin` 对应 React 工作台，不再是普通 dashboard 文案。
- 页面包含 `AI 业务工作台` 或 `AI 工作台`。
- 使用 `/api/agent/chat`、`/api/session/pending`、`/api/images/upload`。
- 工作台组件中不出现 `Sheet` / `Drawer` 作为确认和详情。
- 输入区使用 `Textarea`。
- 有 `AgentConfirmDialog` 或同等居中 Dialog 组件。
- 有 `AgentResultDialog` / `InventoryResultDialog` / `ImageOcrResultDialog` 中至少一个结果弹窗组件。
- 不允许出现常驻大面积 `ExecutionPanel` 作为结果展示区。
- 有最近业务记录组件。

### 11.2 Agent 回归测试

继续运行:

```powershell
python tests\agent_dialog_regression.py
```

重点看:

- 你是谁 / 帮助。
- 查库存。
- 开单预览。
- pending 切换新请求。
- 工作流图片相关提示。

### 11.3 前端手工验收

必测操作:

1. 进入 `/admin`，看到 AI 对话工作台。
2. 输入“你能做什么”，能返回帮助。
3. 输入“查下半斤库存”，能看到 AI 消息，并通过库存结果弹窗查看明细。
4. 输入开单语句，出现居中确认弹窗。
5. 在确认弹窗改数量或仓库，点确认后能继续执行。
6. 点取消，pending 被清掉。
7. 上传一张订单图，能打开识别结果弹窗或进入工作流确认。
8. 点击最近业务记录详情，打开居中弹窗。
9. 新会话后消息清空，旧会话不丢。
10. 旧 `/web` 仍可用。

### 11.4 构建验证

```powershell
cd Z:\sjagent\admin
npm.cmd run build
```

如有后端改动，再运行相关 Python 测试。

## 12. 分阶段实现

### Phase 1: React 工作台恢复 AI 主线

- `/admin` 改成 `WorkbenchPage`。
- 接 `/api/agent/chat`。
- 接 `/api/agent/history`。
- 接 `/api/session/pending`。
- 接 `/api/images/upload`。
- 实现两栏布局、消息、输入、快捷指令、确认 Dialog、结果 Dialog、最近业务记录。
- 顶部只保留紧凑辅助数字。

### Phase 2: 结构化结果增强

- 后端 Agent 返回 `events` 或 `result_cards`。
- 前端减少文本解析。
- 销售单、工作流、库存、打印动作都能从结构化结果弹窗跳详情。
- 简单库存查询优化成服务层直查，但仍显示在对话主线里。

### Phase 3: 会话和分析增强

- 新增 session 列表接口。
- 支持跨设备恢复会话。
- 对常用 AI 操作做统计。
- 另建数据看板，不混入工作台。

## 13. 验收标准

工作台完成后应满足:

- 用户第一眼知道这里是 AI 对话工作台。
- 可以直接用自然语言开始业务。
- AI 准备写入系统前，一定有结构化确认。
- 所有确认和详情都是中间弹窗。
- 业务执行结果不常驻在主界面大区块里，必须用结果弹窗展示。
- 最近业务记录能回看最近 5 条关键结果。
- 工作台不再被设计成普通经营首页。
- 业务写入结果和销售、库存、订单、客户页面一致。
- 旧 `/web` 不受影响。

## 14. 后续看板说明

热销、趋势、客户排行、库存预警、经营数据这些需求是必要的，但它们不属于本页第一阶段。

建议后续新增:

- `/admin/analytics`
- `/api/analytics/hot-products`
- `/api/analytics/sales-trends`
- `/api/analytics/customer-ranking`
- `/api/analytics/inventory-warnings`

这样工作台继续负责“AI 操作”，看板负责“经营分析”，两者不会混在一起。
