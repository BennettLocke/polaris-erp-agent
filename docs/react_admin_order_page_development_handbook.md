# React 后台订单页开发手册

版本: v0.1
日期: 2026-05-26
适用范围: React + Radix/shadcn 后台的订单页重构

## 1. 页面定位

后台侧边栏不再使用“工作流”这个业务叫法，统一显示为“订单”。

但为了避免业务混淆，第一阶段的“订单页”只承接原来的 `workflow_order` 过程订单:

- 客户发来的订单需求、图片、OCR 信息、设计需求。
- 是否丝印、是否制作、是否发货、是否完成。
- 可能还没有 SKU, 也可能还没有生成销售单。
- 用于跟进订单过程，不直接扣库存。

和它相邻但不能混在一起的模块:

- “开单”: 创建正式销售单。
- “销售单”: 已经形成业务结算和打印出库的销售订单。
- “库存”: 只由正式销售单、入库、调拨、盘点等库存单据影响库存余额。

第一阶段可以把 React 路由命名为 `/admin/orders`, 同时保留 `/admin/workflow` 的兼容入口或跳转，避免旧入口失效。接口层暂时继续使用现有 `/api/workflow/orders`，不要为了改页面名称立刻改后端路由。

## 2. 核心业务边界

订单页管理的是过程订单，不是最终销售单。

必须遵守:

- 保存过程订单时，不创建销售单。
- 修改过程订单状态时，不扣库存。
- 删除过程订单时，使用软删除，保留业务日志。
- 状态变更必须写入 `workflow_order_log`。
- 过程订单可以没有 SKU, 因为有些订单仍处于客户发图、设计、询价阶段。
- 过程订单后续可以关联销售单，但关联动作不能自动扣库存。

库存扣减只能发生在正式销售单确认出库之后，由 `sales_order` / `inventory_ledger` / `inventory_balance` 相关逻辑处理。

## 3. 现有接口

第一阶段优先复用现有接口。

注意: 总 API 合同里历史上写过 `status` 查询参数，但当前后台实际路由读取的是 `filter`。订单页实现时以现有路由为准，相关文档已同步校正。

### 3.1 查询订单

`GET /api/workflow/orders`

查询参数:

- `keyword`: 搜索客户名、手机号、商品名、颜色。
- `filter`: `active` / `all` / `pending` / `unmade`。
- `page`: 页码。
- `page_size`: 每页数量，后端限制不超过 120。

返回主要字段:

- `id`
- `customer_name`
- `customer_phone`
- `goods_name`
- `goods_color`
- `order_quantity`
- `is_screen_print`
- `is_screen_print_text`
- `is_made`
- `is_delivered`
- `order_type`
- `status_text`
- `order_time_text`
- `complete_time_text`
- `order_images`
- `created_by_user_id`
- `created_by_name`

### 3.2 创建或编辑订单

`POST /api/workflow/orders`

提交字段:

- `order_id`: 编辑时传入。
- `customer_name`: 必填。
- `customer_phone`
- `goods_name`: 必填。
- `color`
- `order_quantity`
- `is_screen_print`
- `order_type`
- `order_images`
- `remark`

### 3.3 修改状态

`POST /api/workflow/orders/{id}/status`

允许修改字段:

- `is_made`
- `is_delivered`
- `order_type`

其中 `order_type = 1` 表示完成，后端会同步状态为 `completed`; 其他情况回到 `pending`。

### 3.4 删除订单

`DELETE /api/workflow/orders/{id}`

删除为软删除，后端会写删除日志。

### 3.5 前端数据归一

订单页组件不要直接到处使用后端原始字段，先在 API 层做一次归一。

建议归一字段:

- `id`: 数字 ID。
- `customerName`: 来自 `customer_name`。
- `customerPhone`: 来自 `customer_phone`。
- `goodsName`: 来自 `goods_name`。
- `color`: 优先 `goods_color`, 兼容 `color`。
- `quantity`: 来自 `order_quantity`, 兜底为 1。
- `screenPrint`: `is_screen_print === 1`。
- `made`: `is_made === 1`。
- `delivered`: `is_delivered === 1`。
- `completed`: `order_type === 1` 或后端状态为 `completed`。
- `imageUrls`: `order_images` 统一解析成数组，兼容字符串、JSON 字符串和数组。
- `creatorName`: 来自 `created_by_name`。

`order_type` 是历史字段，在当前接口里承担完成状态含义。React 页面不要把它直接展示成“订单类型”，只在归一层转换为 `completed`。

## 4. 状态口径

订单页要服务日常跟单，所以默认界面要比普通表格更快看到“谁的单、做没做、发没发、有没有丝印”。

看板分组必须保证同一张订单只出现一次。

推荐分组优先级:

1. 已完成: `completed === true`。
2. 待制作: `completed !== true && made !== true`。
3. 待发货: `completed !== true && made === true && delivered !== true`。
4. 其他进行中: 不满足以上条件，但仍未完成的历史数据。

按钮文案:

- `made === false`: 显示“标记制作”。
- `made === true`: 显示“已制作”或“取消制作”。
- `delivered === false`: 显示“标记发货”。
- `delivered === true`: 显示“已发货”或“取消发货”。

完成状态不放成大按钮，放在更多菜单或详情里，避免误点。

## 5. 页面结构

推荐结构:

1. 顶部标题区
   - 标题: 订单
   - 副标题: 跟进客户订单、制作、发货和完成状态。
   - 右侧操作: 新建订单、刷新。

2. 搜索和筛选区
   - 搜索框: 客户、手机号、商品、颜色。
   - 状态筛选: 全部、待处理、未制作、未发货、已完成。
   - 辅助筛选: 丝印、非丝印、有图片、无图片。
   - 重置按钮。

3. 数据概览条
   - 订单总数。
   - 待制作。
   - 待发货。
   - 已完成。
   - 今日新增。

4. 主视图区
   - 默认: 订单看板。
   - 可选: 明细表格。

## 6. 默认视图: 订单看板

看板不做复杂拖拽，先做稳定的状态分区。

推荐分区:

- 待制作
- 待发货
- 最近完成

订单卡片信息:

- 客户名和手机号。
- 商品名、颜色、数量。
- 丝印徽章。
- 图片数量。
- 创建人。
- 下单时间。
- 制作状态开关。
- 发货状态开关。
- 更多操作菜单。

卡片要保持信息密度，不要做大图卡。订单页主要看状态和数据，图片只显示小缩略图或图片数量，需要时打开详情预览。

看板卡片建议使用紧凑两段结构:

- 第一段: 客户、手机号、下单时间、状态徽章。
- 第二段: 商品、颜色、数量、丝印、图片数量、创建人。

底部只放高频状态操作和更多菜单，不堆太多文字按钮。

## 7. 明细表格视图

表格用于批量查找和精确比对。

列建议:

- 客户
- 商品
- 颜色
- 数量
- 丝印
- 制作
- 发货
- 状态
- 创建人
- 下单时间
- 操作

表格行操作:

- 查看详情
- 编辑
- 标记制作
- 标记发货
- 标记完成
- 删除

## 8. 新建和编辑弹窗

使用 Dialog, 不做新页面跳转。

字段分组:

客户信息:

- 客户名
- 手机号

订单内容:

- 商品名
- 颜色
- 数量
- 是否丝印
- 图片
- 备注

状态:

- 是否制作
- 是否发货
- 是否完成

交互规则:

- 客户名和商品名必填。
- 数量默认 1。
- 图片使用现有图片资产选择能力。
- 保存成功后关闭弹窗并刷新当前列表。
- 保存失败时保留用户输入并显示错误。

## 9. 详情抽屉

详情建议用 Sheet。

详情内容:

- 基础信息。
- 图片预览。
- 制作、发货、完成状态。
- 备注。
- 操作日志。
- 未来关联销售单信息。

第一阶段如果后端详情接口只返回基础字段，可以先展示已有字段；日志和销售单关联可以预留区域，不展示假数据。

## 10. 状态交互

制作和发货是高频操作，要放在卡片或表格行里直接操作。

建议:

- 使用 Switch 或紧凑按钮组。
- 点击后调用 `/api/workflow/orders/{id}/status`。
- 成功后更新当前列表中的单条记录。
- 失败后恢复原状态并显示 toast。
- 完成状态可以在更多菜单中操作，避免误点。

不要用只改前端状态的假交互。

状态交互要防止重复点击:

- 请求中禁用当前订单的对应按钮。
- 成功后只更新这一张订单，不强制整页闪烁。
- 如果后端返回失败，恢复原值并显示错误。
- 如果出现 `401` 或 `403`, 交给全局 API 客户端处理登录和权限提示。

## 11. 加载、错误和空状态

订单页是高频页面，不能只有“加载失败”四个字。

必须覆盖:

- 首次加载: 使用 `Skeleton`。
- 搜索中: 保留原列表，筛选区显示轻量加载状态。
- 空结果: 区分“没有订单”和“当前筛选没有结果”。
- 接口失败: 显示可重试的错误块。
- 状态更新中: 只锁定当前卡片或当前行。

搜索建议做 300ms 防抖。快速连续搜索时，要忽略过期请求结果，避免旧结果覆盖新结果。

## 12. 组件库使用约定

继续沿用当前 React 后台的 Radix/shadcn 风格。

优先使用:

- `Button`
- `Input`
- `Textarea`
- `Badge`
- `Card`
- `Tabs`
- `Table`
- `Dialog`
- `Sheet`
- `AlertDialog`
- `DropdownMenu`
- `Switch`
- `Select`
- `Skeleton`
- `Tooltip`

不要在业务页面直接写原生 `button`、`input`、`select` 的裸样式。需要新交互时，先复用现有组件和样式变量。

视觉原则:

- 操作型后台，保持安静、清晰、紧凑。
- 不做营销式大标题和大卡片。
- 不使用大图作为主要信息。
- 同一页面的按钮、徽章、卡片、表格密度要和商品页、库存页保持一致。
- 状态颜色要克制: 待处理用灰/黄，制作完成用蓝/绿，发货完成用绿，异常或删除用红。

## 13. 旧入口和兼容边界

订单页改名只改 React 后台的用户可见命名，不改旧业务入口。

必须保持:

- 旧 `/web` 工作流页面继续可用，直到 React 订单页验收通过。
- 小程序 `/api/mini/workflow-order/*` 不受影响。
- Agent 工具 `workflow_order_*` 不受影响。
- 后端接口 `/api/workflow/orders` 第一阶段不改名。
- React 新路由 `/admin/orders` 和旧路由 `/admin/workflow` 都能进入同一页面或兼容跳转。

已同步更新的文档:

- `docs/react_admin_api_contract.md`: 页面名从工作流订单改为订单，路由增加 `/admin/orders`, 查询参数校正为 `filter`。
- `docs/react_admin_ui_component_plan.md`: Sidebar 和页面组件匹配表里的“工作流”改为“订单”。
- `docs/react_admin_page_design_blueprint.md`: 后续页面顺序里的“工作流”改为“订单”。

## 14. 前端命名建议

界面名称使用“订单”。

代码里要避免和正式销售单混淆:

- 页面组件: `OrdersPage`
- 过程订单类型: `ProcessOrder` 或 `WorkflowOrder`
- API 方法: `fetchProcessOrders`, `saveProcessOrder`, `updateProcessOrderStatus`
- 不要把 `workflow_order` 直接命名为 `SalesOrder`。

如果新增路由:

- `/admin/orders`: 新订单页。
- `/admin/workflow`: 兼容旧入口，跳转或渲染同一个页面。

## 15. 权限和操作人

订单页的写操作必须依赖当前登录态。

前端规则:

- 页面不自己伪造操作人。
- 创建、编辑、状态变更、删除都由后端根据 session 写操作人。
- `401` 跳登录或显示登录失效。
- `403` 显示无权限提示，不跳登录。
- 删除必须用 `AlertDialog`, 文案说明“删除后从订单页隐藏，但保留日志”。

权限细分如果第一阶段后端还没有开放，可以先按现有后台登录权限执行，但组件结构要预留禁用态。

## 16. 第一阶段实施清单

1. 侧边栏文案从“工作流”改为“订单”。
2. 增加 `/admin/orders` 路由，并兼容旧 `/admin/workflow`。
3. 增加订单 API 封装。
4. 增加订单数据类型。
5. 增加 API 数据归一层。
6. 实现订单看板默认视图。
7. 实现搜索、筛选、分页或加载更多。
8. 实现制作、发货状态更新。
9. 实现新建和编辑弹窗。
10. 实现详情抽屉和图片预览。
11. 实现删除确认。
12. 同步总 API 合同和 UI 组件文档里的“工作流”命名。
13. 补充页面契约测试。
14. 手动验证桌面和窄屏布局。

## 17. 测试要求

建议增加或更新契约测试:

- 侧边栏显示“订单”，不再显示“工作流”作为主菜单名。
- `/admin/orders` 能进入订单页。
- `/admin/workflow` 兼容旧入口。
- 页面使用现有组件库结构，不出现裸控件样式回退。
- 查询接口调用 `/api/workflow/orders`。
- 查询参数使用 `filter`, 不再写成历史 `status`。
- 状态更新只调用 `/api/workflow/orders/{id}/status`。
- 前端归一层把 `order_type` 转成 `completed`, 页面组件不直接展示 `order_type`。
- 保存过程订单不会触发销售单创建。
- 保存过程订单不会触发库存扣减。
- 删除订单调用软删除接口。
- 旧 `/web` 工作流页面不受 React 改名影响。
- 小程序 `/api/mini/workflow-order/*` 不受 React 改名影响。

后端已有逻辑需要重点回归:

- `WorkflowService.save_order`
- `WorkflowService.list_orders`
- `WorkflowService.update_status`
- `WorkflowService.delete_orders`
- 原小程序 `/api/mini/workflow-order/*` 兼容能力。

## 18. 后续增强

这些不建议放进第一阶段:

- 过程订单一键转销售单。
- 销售单和过程订单合并视图。
- 看板拖拽改状态。
- 批量状态更新。
- 客户历史订单联动。
- 商品/SKU 智能匹配。
- 图片 OCR 重新识别。

后续可以增加“去开单”动作，把过程订单信息带到开单页，但仍然必须由正式开单动作创建销售单并扣库存。

## 19. 验收标准

页面完成后必须满足:

- 用户在侧边栏看到的是“订单”。
- 能一眼看到待制作、待发货、已完成的订单。
- 能快速搜索客户、手机号、商品、颜色。
- 能直接修改制作和发货状态。
- 能新建、编辑、删除过程订单。
- 不会误扣库存。
- 不会把过程订单误当成销售单。
- 桌面宽屏信息密度高，窄屏不挤压错位。
- 视觉风格和商品页、库存页一致。
- 旧 `/web`、小程序和 Agent 工作流入口不受影响。
