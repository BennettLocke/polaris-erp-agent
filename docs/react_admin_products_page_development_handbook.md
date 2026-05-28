# React 后台商品页开发手册

版本：v0.1  
日期：2026-05-25  
适用入口：`/admin/products`  
关联入口：`/admin/media` 图片资产、`/admin/sales-new` 开单商品搜索、小程序商品详情 API  
当前状态：旧 `/web` 页面已下线，商品页只维护 `/admin/products` React 后台入口。

## 1. 页面定位

商品页不是单纯的图片墙，也不是只给开单搜索用的商品列表。它应该是商品资料工作台，围绕 SPU 管商品，围绕 SKU 管颜色、编号、价格和库存规则。

商品页必须回答这些问题：

- 这个产品叫什么，属于哪个大类和细分类。
- 这个产品有几个颜色，一共是什么颜色。
- 这个产品的件规是多少，比如 `件规：1件24套`。
- 这个产品是不是 1 件起订。
- 这个产品是否上架，小程序和商品列表能不能看到。
- 每个颜色对应哪个 `SJ` 编号、售价、成本价、单位。
- 这个商品扣不扣库存，泡袋、标签、服务类不能靠前端临时判断。
- 主图、详情页图、颜色图分别绑定到哪里。
- 新上传但未绑定的图片在哪里处理。
- 删除、下架、改库存规则这些动作谁操作过，后续能不能追溯。

商品页只负责展示、输入和触发动作。编号生成、上架过滤、库存规则、图片资产绑定、保存 SPU/SKU，都必须走 `ProductService` 和后端统一 API，不能在 React 页面里复制一套业务规则。

## 2. 当前代码现状

当前 `/admin/products` 和 `/admin/media` 已完成第一轮结构拆分：

- `admin/src/App.tsx` 只负责路由并导入 `ProductsPage`、`MediaPage`。
- `ProductsPage`、`MediaPage`、`ProductEditorDialog`、`ImageAssetPickerDialog` 已迁到 `admin/src/components/business/products/products-page.tsx`。
- `ProductToolbar`、`ProductCategoryFilter`、`ProductCardGrid`、`ProductCard`、`ProductPager` 已先拆成命名组件。
- 商品列表已开始使用 `Card`、`Badge`、`Tabs`、`Pagination`、`Skeleton`、`Empty`。
- `ProductEditorDialog` 已改成 `Dialog + Tabs + Field + Table + Select + Switch`，不再是一条长滚动旧表单；商品编辑弹窗已收紧尺寸，只保留底部保存动作。
- `ImageAssetPickerDialog` 已改成 `Dialog + Tabs + Input + Button + ScrollArea + Empty/Skeleton`。
- 下一步再把这些组件继续拆成独立文件，并补齐上架、下架、删除等风险动作。

当前已接入的前端 API 在 `admin/src/api.ts`：

| 动作 | 前端方法 | 后端入口 |
| --- | --- | --- |
| 商品列表 | `api.productList()` | `GET /api/product/list` |
| 商品分类 | `api.productCategories()` | `GET /api/product/categories` |
| 商品详情 | `api.productDetail(id)` | `GET /api/product/<id>` |
| 商品选项 | `api.productOptions(id)` | `GET /api/product/options` |
| 保存商品 | `api.saveProduct(payload)` | `POST /api/product/save` |
| 上传商品图 | `api.uploadProductImage(file)` | `POST /api/product/upload` |
| 图片资产 | `api.productMedia()` | `GET /api/product/media` |
| 删除图片资产 | `api.deleteProductMedia(id)` | `DELETE /api/product/media/<id>` |

当前后端服务层：

| 服务 | 文件 | 职责 |
| --- | --- | --- |
| `ProductService` | `src/services/business/products.py` | 商品搜索、列表、详情、保存、删除、上下架、图片资产、编号 |
| `SettingsService` | `src/services/business/settings.py` | 商品基础设置、库存规则、编号设置、图片/OSS 设置 |
| `MiniAppService` | `src/services/business/miniapp.py` | 小程序商品列表和详情，必须复用商品服务层规则 |

当前主要问题：

- 商品和图片资产已经离开 `App.tsx`，但第一版仍在同一个 `products-page.tsx` 内，后续还要继续细拆。
- 商品列表和商品编辑弹窗已开始替换 shadcn/Radix 组件；图片资产管理页仍保留部分旧样式，后续单独重做。
- 商品编辑弹窗里已去掉原生 `<input>`、`<select>`、`<button>`，改用 `Field`、`Input`、`Select`、`Button`、`Table`、`Switch`。
- 分类是横向长条，商品多时会出现横向滚动，不符合现在的后台风格。
- 商品卡片图片偏大问题已先收敛为紧凑 SPU 卡片，但资料完整度筛选还没补齐。
- 编辑弹窗已改为中间大 `Dialog`，并按基础信息、规格/颜色、图片、库存/上架、记录分 Tab。
- 规格列表已从大块卡片改为紧凑 `Table`，列宽、图片按钮和输入框必须控制在弹窗内，不能再让用户横向拖动才能看完整字段。
- 库存规则是 SPU/商品级设置，放在基础信息里；规格/颜色表只编辑颜色、编号、条码、单位、售价、成本和规格图。
- 图片选择器已统一为未绑定、本产品图片、全部图片三个入口，并复用在主图、详情页、规格图。
- 删除图片资产仍用 `window.confirm`，风险动作必须改成 `AlertDialog`。
- 加载态仍用文字空状态，应该用 `Skeleton`。

## 3. 商品数据边界

商品页以自有数据库为准，不依赖 ShopXO 或旧 ERP 页面逻辑。

核心表：

| 表 | 用途 |
| --- | --- |
| `product_spu` | 产品系列，保存商品名、分类、可用颜色、件规、1 件起订、上下架等 SPU 级信息 |
| `product_sku` | SKU/颜色，保存唯一 `SJ` 编号、颜色、售价、成本、单位、库存规则 |
| `product_category` | 商品分类，礼盒、泡袋、辅料、纸箱、其他及其细分类 |
| `product_unit` | 单位，套、捆、个、张、斤等 |
| `product_media` | 图片资产，保存主图、详情图、颜色图、待绑定图 |
| `system_setting` | 编号、商品基础、库存规则、图片/OSS 规则 |

关键业务约束：

- 内部唯一商品编号是 `product_sku.sku_no`，也就是 `SJxxxx`。
- 新建商品、泡袋上传脚本都必须使用统一编号服务，不允许前端自己拼编号。
- SPU 可以保存可用颜色列表，创建和编辑商品时优先展示，不必每次反查 SKU。
- 0 颜色不允许显示成 0，只有默认规格时显示 `1 个颜色` 和 `默认颜色`。
- 颜色展示用普通文字和 `Badge`，不再把文字染成对应颜色。
- 件规统一显示为 `件规：1件X套`，单位按商品单位展示。
- 泡袋、标签、服务类等不扣库存规则来自设置和服务层，不在商品页临时硬编码。
- 商品上下架必须影响小程序商品列表和详情接口。详情接口也要能拦截下架商品。
- 删除商品优先软删除，保留历史销售单快照。

## 4. shadcn/Radix 组件映射

本页必须按 shadcn/Radix 的官方组件结构组织，参考：

- Card: https://ui.shadcn.com/docs/components/radix/card
- Table: https://ui.shadcn.com/docs/components/radix/table
- Dialog: https://ui.shadcn.com/docs/components/radix/dialog
- Tabs: https://ui.shadcn.com/docs/components/radix/tabs
- Dropdown Menu: https://ui.shadcn.com/docs/components/radix/dropdown-menu
- Pagination: https://ui.shadcn.com/docs/components/radix/pagination
- Empty: https://ui.shadcn.com/docs/components/radix/empty
- Skeleton: https://ui.shadcn.com/docs/components/radix/skeleton
- Badge: https://ui.shadcn.com/docs/components/radix/badge
- Button: https://ui.shadcn.com/docs/components/radix/button
- Input: https://ui.shadcn.com/docs/components/radix/input
- Select: https://ui.shadcn.com/docs/components/radix/select
- Alert Dialog: https://ui.shadcn.com/docs/components/radix/alert-dialog

| 页面需求 | 组件 | 使用规则 |
| --- | --- | --- |
| 页面标题和主动作 | `PageHeader`, `Button` | 标题为“商品”，右侧放“新增商品” |
| 搜索和筛选 | `Toolbar`, `Input`, `Button`, `Tabs`, `Select`, `Badge` | 搜索只保留一个结果区，不做上下两个结果 |
| 一级/二级分类 | `Tabs`, `Button`, `Badge` | 一级用 Tabs，二级用自动换行按钮组，禁止横向滚动条 |
| 商品主列表 | `Card`, `Badge`, `DropdownMenu`, `Pagination` | 商品需要看图，桌面默认紧凑卡片，不做巨大图片墙 |
| 可选表格视图 | `Table` | 后续可加“卡片/表格”切换，批量维护价格时用表格 |
| 商品编辑 | `Dialog`, `Tabs`, `Field`, `Input`, `Select`, `Switch`, `Table` | 用户更喜欢中间弹窗，复杂编辑也先使用大 Dialog |
| 规格/颜色编辑 | `Table`, `Input`, `Select`, `Button`, `Badge` | 多颜色用紧凑表格，不用一张颜色一个大卡片；禁止出现横向滚动条 |
| 图片选择 | `Dialog`, `Tabs`, `Input`, `Button`, `Card`, `Skeleton`, `Empty` | 未绑定、本产品图片、全部图片三个入口 |
| 上架/下架确认 | `AlertDialog` 或明确按钮 | 下架影响小程序展示，必须说明后果 |
| 删除商品/图片 | `AlertDialog` | 不能再用 `window.confirm` |
| 加载态 | `Skeleton` | 不用“商品加载中”文字占位 |
| 空状态 | `Empty` | 只在加载完成且无数据时展示 |

禁止继续新增：

- `primary-action`
- `ghost-action`
- `status-badge`
- `panel`
- 原生 `<select>` 表单
- 原生 `<button>` 做业务按钮
- 页面里手写大块状态标签

## 5. 商品页整体结构

推荐结构：

```text
PageHeader
  标题：商品
  右侧：新增商品、刷新

ProductToolbar
  搜索商品、颜色、编号
  搜索按钮
  重置按钮
  状态筛选：全部、已上架、未上架
  库存规则筛选：全部、扣库存、不扣库存

ProductCategoryFilter
  一级分类 Tabs：全部、礼盒、泡袋、辅料、纸箱、其他
  二级分类按钮组：半斤礼盒、一两礼盒、肉桂泡袋、大红袍泡袋等

ProductSummaryStrip
  商品数
  上架数
  未上架数
  不扣库存数

ProductCardGrid
  ProductCard

Pagination

ProductEditorDialog
ImageAssetPickerDialog
ProductDeleteDialog
ProductShelfDialog
```

页面不再写长说明文字，主 UI 只保留能操作和能判断的数据。

## 6. 商品筛选和搜索设计

### 6.1 搜索

搜索支持：

- 商品名，比如“喜悦”“颜序”“茶派”。
- 规格，比如“半斤”“三两”。
- 颜色，比如“红色”“橙色”“默认颜色”。
- 商品编号，比如 `SJ1570`。

规则：

- 输入框不会自动弹一个假的下拉结果。
- 按 Enter 或点击“搜索”才请求列表。
- 搜索结果只出现在商品列表，不在输入框下面再显示一个结果区。
- 搜索后重置到第 1 页。
- 点击“重置”清空关键词、分类、状态和库存筛选。
- 搜索为空时显示当前分类下的商品，不显示“没有匹配”假状态。

### 6.2 分类

分类必须解决之前横向滚动问题。

一级分类建议：

- 全部
- 礼盒
- 泡袋
- 辅料
- 纸箱
- 其他

二级分类按当前一级分类显示，并自动换行：

礼盒示例：

- 半斤礼盒
- 一两礼盒
- 二两礼盒
- 三两礼盒
- 六小盒礼盒
- PVC礼盒
- 五格礼盒
- 2泡礼盒
- 其他礼盒

泡袋示例：

- 肉桂泡袋
- 大红袍泡袋
- 水仙泡袋
- 红茶泡袋
- 品种茶泡袋
- 纯色泡袋
- 公版泡袋
- 空白泡袋
- 宽版泡袋
- 其他泡袋

规则：

- 一级分类改变时，二级分类重置为“全部”。
- 二级分类改变时，页码重置为第 1 页。
- 每个分类显示数量，但数量是辅助信息，不挤占标题。
- 没有归类的商品显示在“其他”，不要凭空隐藏。

### 6.3 状态筛选

状态筛选建议第一版只做：

- 全部
- 已上架
- 未上架

后续再加：

- 有图
- 无图
- 有详情页
- 无详情页
- 1件起订
- 普通起订
- 扣库存
- 不扣库存

### 6.4 资料完整度筛选

审核后补充：商品页还应该承担“资料体检”的作用，否则后面小程序、开单和 Agent 都会被脏商品资料拖住。

建议在商品页增加一组“待完善”筛选，不作为第一眼主筛选，但要能一键查：

| 筛选 | 含义 | 处理动作 |
| --- | --- | --- |
| 无主图 | SPU 没有主图 | 进入图片 Tab 绑定主图 |
| 无详情图 | SPU 没有详情页图片 | 进入图片 Tab 补详情页 |
| 缺件规 | `case_pack_qty` 为空或 0 | 进入基础信息补件规 |
| 缺价格 | 任一 SKU 售价为空或异常 | 进入规格表格补价格 |
| 缺颜色 | 颜色为空或显示旧文案 | 自动转为 `默认颜色` 或人工修正 |
| 编号异常 | SKU 编号不是 `SJxxxx` 或重复 | 只提示，修复必须走编号服务 |
| 未上架有图 | 资料已完整但未上架 | 可以批量评估是否上架 |

这些筛选的价值：

- 商品迁移后可以快速清理历史遗留问题。
- 小程序不会展示缺主图、缺详情的商品。
- 开单和 Agent 搜索时不会遇到颜色、件规和编号不完整的数据。
- 后续做批量修复时有明确入口。

## 7. 商品卡片设计

商品列表默认使用紧凑卡片，因为商品管理需要看主图，但卡片不能像现在一样过大。

卡片建议尺寸：

- 桌面端：每行 4 到 6 个，按容器宽度自适应。
- 主图：固定 88 到 104 px 正方形，`object-fit: cover`。
- 卡片高度稳定，标题和颜色列表最多 2 行。
- 小屏幕每行 1 到 2 个。

卡片内容：

| 区域 | 显示 |
| --- | --- |
| 主图 | SPU 主图，没有图时用 `Skeleton` 或无图占位 |
| 标题 | 商品名，比如 `【喜悦】半斤` |
| 副标题 | 一级分类 / 二级分类 |
| 徽章 | 已上架、未上架、1件起订、不扣库存 |
| 指标 1 | `N 个颜色` |
| 指标 2 | 颜色列表，比如 `红色 / 蓝色 / 黄色 / 默认颜色` |
| 指标 3 | `件规：1件24套` |
| 指标 4 | 价格范围或最低价 |
| 操作 | 编辑、更多 |

颜色规则：

- 有几个 SKU 就显示几个颜色。
- 只有一个默认 SKU 时显示 `1 个颜色` 和 `默认颜色`。
- 颜色文字不染色，避免页面花。
- 颜色太多时显示前 5 个，再显示 `+N`。

库存规则显示：

- 礼盒类通常显示 `扣库存`。
- 泡袋类按系统规则显示 `不扣库存`，不要让用户在列表上误以为可以随便改。
- 标签、服务类等不扣库存商品也显示 `不扣库存`。
- 不显示英文字段名，比如 `purchase_in`、`is_stock_item`。

操作区：

- 直接显示：`编辑`
- 更多菜单：查看图片、复制编号、上架/下架、删除
- 删除必须进入 `AlertDialog`
- 下架必须说明“小程序和商品接口将不再展示这个商品”

## 8. 商品编辑 Dialog

用户更倾向中间弹窗，所以商品编辑第一版使用大 `Dialog`，不使用右侧 `Sheet`。

推荐宽度：

- 桌面：`min(1080px, 96vw)`
- 高度：`min(90vh, ...)`
- 内部用 `Tabs` 分区，不做一条长滚动到底。

结构：

```text
DialogHeader
  商品名
  状态徽章
  保存按钮

Tabs
  基础信息
  规格/颜色
  图片
  库存/上架
  操作记录
```

### 8.1 基础信息

字段：

| 字段 | 组件 | 规则 |
| --- | --- | --- |
| 商品名称 | `Field + Input` | 必填 |
| 一级分类 | `Select` 或 `Tabs` | 选择后联动二级分类 |
| 二级分类 | `Select` | 必填 |
| 件规 | `Field + Input` | 数字输入，显示为 `件规：1件X套` |
| 默认单位 | `Select` | 默认 `套` |
| 1件起订 | `Switch` | 保存为 `purchase_policy` 或对应字段 |
| 可用颜色 | 只读摘要或可编辑标签 | 来源于 SKU，也可保存到 SPU |

数字输入规则：

- `onWheel` 必须 blur，避免鼠标滚轮误改价格或件规。
- 件规不能小于 0。
- 空件规显示“未设置”，不拼奇怪文案。

### 8.2 规格/颜色

规格编辑必须改成表格，而不是一张颜色一个大卡片。

表格列：

| 列 | 内容 |
| --- | --- |
| 颜色/规格 | 标准颜色文本，默认是 `默认颜色` |
| 规格图 | 小缩略图 + 上传/选择按钮 |
| 商品编号 | `SJxxxx`，已有 SKU 只读，新 SKU 由服务层生成 |
| 单位 | `Select` |
| 售价 | 数字输入 |
| 成本价 | 数字输入 |
| 条码 | 可选输入 |
| 库存规则 | `Badge` 或受控开关，固定规则要只读 |
| 操作 | 删除未提交的新规格，历史 SKU 删除要二次确认 |

规则：

- 新增规格默认颜色为 `默认颜色`，用户可改为红色、黄色等标准颜色。
- 保存后 SPU 的可用颜色同步更新。
- 商品编号不能手动乱填。新建 SKU 时前端可以显示“保存后自动生成”，后端返回实际 `SJ` 编号。
- 价格和成本价允许为 0，但要显示为 `¥0.00`。
- 删除已有 SKU 会影响历史数据时必须走服务层确认，第一版可以先禁用已有 SKU 删除，只允许删除新加未保存行。

### 8.3 图片

图片分三类：

| 类型 | 绑定 | 显示规则 |
| --- | --- | --- |
| 主图 | SPU | 一个产品只显示一个主图 |
| 详情页 | SPU | 多张，按顺序显示 |
| 颜色图 | SKU | 每个颜色最多一个主规格图 |

图片区域规则：

- 主图后面直接有“上传/选择”入口。
- 详情页后面直接有“上传/选择”入口。
- 每个颜色行后面直接有“上传/选择”入口。
- 没图时只显示一个清晰的占位和一个按钮，不出现两个意义重复的按钮。
- 选图弹窗关闭后，选中的图立即显示在对应位置。
- 删除当前绑定图只解除当前商品里的绑定，不等于删除资产库图片。

### 8.4 图片选择器

图片选择器统一为 `ImageAssetPickerDialog`。

顶部：

- 标题：选择图片资产
- 搜索：产品名、分类、颜色、来源
- 上传新图片按钮

Tabs：

- 未绑定
- 本产品图片
- 全部图片

规则：

- “本产品图片”包含当前 SPU 的主图、详情页、颜色图，不只包含详情页。
- 图片按缩略图显示，卡片要小，不能一屏只能看几张。
- 使用 `loading="lazy"`。
- 第一版每页最多 80 张，后续改成分页或虚拟列表。
- 搜索只筛当前 Tab 的结果。
- 同一个 URL 去重。
- 上传成功后写入 `product_media`，如果选择了绑定目标，保存商品时完成绑定。
- 未绑定图片可以在图片资产页删除，商品编辑里只做选择和解绑。

### 8.5 库存/上架

本区只显示和触发服务层规则，不在前端重算规则。

显示：

- 当前商品是否上架。
- 小程序是否可见。
- 默认库存规则。
- 各 SKU 是否扣库存。
- 最近库存数量摘要。

动作：

- 上架
- 下架
- 保存库存规则

下架确认文案必须说明：

```text
下架后，小程序商品列表和商品详情接口不会再展示这个商品。历史销售单不受影响。
```

库存规则限制：

- 泡袋等固定不扣库存分类，页面可以展示规则，但不能让用户随便改成扣库存。
- 如果确实要改固定规则，应该去设置页的商品基础/库存规则处理，不在商品编辑里临时改。

### 8.6 操作记录

第一版可以先显示空状态，但结构要留好：

- 创建人
- 最后编辑人
- 上架/下架记录
- 图片绑定记录
- SKU 编号生成记录

没有数据时使用 `Empty`，不写大段解释。

### 8.7 保存前差异和风险提示

商品编辑不应该点保存就静默覆盖。审核后补充：涉及价格、编号、库存规则、上架状态、主图这些字段时，保存前要能让用户知道改了什么。

第一版建议：

- 普通字段修改直接保存，例如商品名、件规、详情图顺序。
- 价格修改在保存按钮上方显示简短差异：`红色：¥22.00 -> ¥24.00`。
- 主图变更显示差异：`主图已更换`。
- 库存规则从扣库存改为不扣库存，必须二次确认。
- 上架/下架必须走单独确认弹窗，不混在普通保存里。
- SKU 编号不允许在前端直接改；如果未来要改编号，必须走编号变更流程和日志。

这样可以避免误改价格、误换主图、误改库存规则。

### 8.8 状态模型统一

当前商品里至少会涉及三个不同含义的状态，页面必须显示清楚，不能全部叫“状态”。

| 状态 | 字段建议 | 含义 | 影响 |
| --- | --- | --- | --- |
| 资料状态 | `status` | 商品资料是否有效，比如 active/deleted | 后台是否保留、是否软删除 |
| 开单可用 | `is_sellable` | React 后台、Agent 能不能用于开销售单 | 开单搜索和 Agent 开单 |
| 小程序上架 | `is_listed` | 小程序商品列表和详情能不能看到 | `/api/mini/search/datalist` 和 `/api/mini/goods/detail` |

第一版 UI 建议：

- 列表卡片只显示用户关心的中文：`已上架`、`未上架`、`开单可用`、`不可开单`。
- 编辑 Dialog 的“库存/上架”Tab 里分开显示这三个状态。
- `下架` 只影响小程序展示，不等于删除商品，也不应该影响历史销售单。
- `不可开单` 会影响后台开单和 Agent，但不一定影响历史销售单。
- `删除商品` 是软删除，必须单独确认。

后端边界：

- 小程序列表和详情必须使用 `listed_only=True`。
- 开单商品搜索应使用开单可用规则，不能简单等同于小程序上架。
- Agent 商品匹配也应读取同一套开单可用规则。

## 9. 新增商品流程

新增商品不能只是打开一个空编辑框，还要按编号和图片规则走服务层。

流程：

1. 点击“新增商品”。
2. 打开 `ProductEditorDialog`，默认进入“基础信息”。
3. 填商品名、分类、件规、默认单位。
4. 在“规格/颜色”添加一个或多个颜色。
5. 新 SKU 编号显示为“保存后自动生成”。
6. 上传或选择主图、详情页、颜色图。
7. 点击保存。
8. 后端 `ProductService.save()` 生成 SPU/SKU，调用统一编号服务生成 `SJ` 编号。
9. 返回新商品 ID 和 SKU 编号。
10. 前端刷新列表并打开保存成功提示。

校验：

- 商品名必填。
- 分类必填。
- 至少有一个规格。
- 每个规格必须有颜色文本，空值保存为 `默认颜色`。
- 售价不能小于 0。
- 件规不能小于 0。
- 图片可以为空，但无主图商品要在列表上有明显无图占位。

## 10. API 和服务层边界

### 10.1 当前接口继续使用

第一版继续使用现有接口：

```text
GET    /api/product/list
GET    /api/product/categories
GET    /api/product/<id>
GET    /api/product/options
POST   /api/product/save
POST   /api/product/upload
GET    /api/product/media
DELETE /api/product/media/<id>
```

### 10.2 建议补充参数

`GET /api/product/list` 建议支持：

```ts
type ProductListQuery = {
  keyword?: string;
  page?: number;
  pageSize?: number;
  categoryId?: string | number;
  parentCategory?: string;
  listed?: "all" | "listed" | "unlisted";
  inventoryPolicy?: "all" | "stock" | "non_stock";
  hasImage?: "all" | "yes" | "no";
  sort?: "updated_desc" | "name_asc" | "created_desc";
};
```

前端第一版可以先接 `keyword/page/pageSize/categoryId`，但类型和页面结构要为后续筛选预留。

### 10.3 保存 payload 边界

前端可以整理表单 payload，但不能决定：

- 最终 SKU 编号。
- 库存固定分类规则。
- 上架后小程序是否可见。
- 图片资产最终绑定写哪些表。
- 历史 SKU 是否允许删除。

这些由 `ProductService.save()` 和数据库事务决定。

### 10.4 小程序商品详情

小程序商品详情接口，比如 `/api/mini/goods/detail?id=96`，也属于统一 API。它应该走服务层：

```text
MiniAppService.goods_detail()
  -> ProductService.info(product_id, listed_only=True)
```

要求：

- 商品下架后，列表接口不返回。
- 商品下架后，详情接口也不能继续返回正常商品。
- 小程序不扣库存，只读商品、图片、价格、工作流需要的资料。

### 10.5 开单和 Agent 边界

商品页改完以后，不能只看 `/admin/products` 自己好不好看，还要验证开单页和 Agent 是否读到同一套商品规则。

必须对齐：

- `1件起订`：商品编辑保存后，开单页商品搜索和 Agent 开单都能读到。
- `件规`：商品编辑保存后，工作流识别“1件”时按件规换算数量。
- `颜色`：SPU 可用颜色和 SKU 颜色一致，开单页不会显示 0 个颜色。
- `开单可用`：不可开单商品不应被开单页和 Agent 当作可销售商品。
- `不扣库存`：泡袋、标签、服务类即使能开单，也不参与库存扣减和删除回滚。
- `售价`：编辑 SKU 售价后，开单页优先显示客户历史价，其次显示商品当前售价。

这部分要在后续实现里补契约测试，避免商品页改了，但开单和 Agent 还读旧字段。

## 11. 文件拆分方案

下一步实现时，不能继续扩大 `App.tsx`。

新增目录：

```text
admin/src/components/business/products/
  index.ts
  types.ts
  utils.ts
  products-page.tsx
  product-toolbar.tsx
  product-category-filter.tsx
  product-summary-strip.tsx
  product-card-grid.tsx
  product-card.tsx
  product-editor-dialog.tsx
  product-basic-tab.tsx
  product-sku-table.tsx
  product-media-tab.tsx
  image-asset-picker-dialog.tsx
  product-delete-dialog.tsx
  product-shelf-dialog.tsx
  product-empty.tsx
  product-skeleton.tsx
```

职责：

| 文件 | 职责 |
| --- | --- |
| `products-page.tsx` | 页面状态、加载商品、连接各业务组件 |
| `product-toolbar.tsx` | 搜索、状态筛选、重置、新增商品 |
| `product-category-filter.tsx` | 一级/二级分类展示和选择 |
| `product-summary-strip.tsx` | 商品数量和状态摘要 |
| `product-card-grid.tsx` | 桌面和移动端商品卡片网格 |
| `product-card.tsx` | 单个 SPU 卡片 |
| `product-editor-dialog.tsx` | 编辑弹窗容器和保存流程 |
| `product-basic-tab.tsx` | 基础信息表单 |
| `product-sku-table.tsx` | SKU/颜色/价格/库存规则表格 |
| `product-media-tab.tsx` | 主图、详情页、颜色图编辑 |
| `image-asset-picker-dialog.tsx` | 图片资产选择和上传 |
| `product-delete-dialog.tsx` | 删除商品确认 |
| `product-shelf-dialog.tsx` | 上架/下架确认 |
| `utils.ts` | 商品标题、颜色、件规、价格、图片 URL 格式化 |
| `types.ts` | 商品页组件 props 和查询类型 |

`App.tsx` 只保留：

- 路由分发。
- 全局登录态。
- `route === "products" ? <ProductsPage /> : ...`

## 12. 视觉标准

商品页视觉必须靠近 shadcn 后台示例，而不是旧版后台。

标准：

- 主色只用黑、白、灰和语义色，不做大面积绿色。
- 字体沿用后台统一字体规则，中文优先苹方；Windows 环境可退到 Microsoft YaHei。
- 卡片圆角和按钮圆角跟随 shadcn 组件，不再手写巨大圆角。
- 卡片尺寸小而稳定，主图固定比例，文字不把卡片撑高。
- 徽章统一用 `Badge`，不手写状态块。
- 按钮统一用 `Button`，图标用 `lucide-react` 且加 `data-icon`。
- 分类切换不要横向滚动条。
- 表单使用 `Field`，不要用原生 label 加 input 堆样式。
- 商品编辑里不要卡片套卡片。Tabs 内每个区域用表格、字段组或图片网格。
- 图片资产缩略图必须懒加载，图片多时不应该明显卡顿。

## 13. 功能验收标准

### 13.1 商品列表

- 打开 `/admin/products` 可以加载商品。
- 搜索商品名、颜色、编号可以返回结果。
- 搜索结果只出现在商品列表，不出现两个结果区。
- 分类分为一级和二级，不出现横向长滚动。
- 分页可用，换页不丢筛选条件。
- 商品卡片显示主图、商品名、分类、颜色数、颜色列表、件规、价格、上架状态。
- 只有默认规格时显示 `1 个颜色` 和 `默认颜色`。
- 件规显示为 `件规：1件X套`。
- 状态、库存规则全部中文显示。
- 加载中使用 `Skeleton`。
- 无数据使用 `Empty`。

### 13.2 商品编辑

- 点击编辑打开中间 `Dialog`。
- Dialog 使用 `Tabs` 分基础信息、规格/颜色、图片、库存/上架。
- 基础信息可编辑商品名、分类、件规、1件起订。
- 规格/颜色用表格编辑，能改颜色、单位、售价、成本价。
- 数字输入滚轮不会误改值。
- 新增规格默认显示 `默认颜色`。
- 保存走 `POST /api/product/save`。
- 保存成功刷新当前列表。
- 保存失败在弹窗内显示明确错误。

### 13.3 图片

- 主图只能显示一个。
- 详情页可以多张。
- 颜色图跟 SKU/颜色绑定。
- 主图、详情页、颜色图都有“上传/选择”入口。
- 图片选择器包含 `未绑定`、`本产品图片`、`全部图片`。
- 本产品图片包含主图、详情页、颜色图，不只包含详情页。
- 图片选择器支持搜索和上传。
- 图片缩略图使用懒加载。
- 已选图片立即显示在对应位置。

### 13.4 上架、删除和服务层

- 上架/下架走服务层，不在前端只改本地状态。
- 下架后小程序商品列表和详情接口按服务层规则过滤。
- 删除商品使用 `AlertDialog`。
- 删除图片资产使用 `AlertDialog`。
- 前端不直接判断泡袋是否扣库存，只展示服务层返回规则。
- `/admin/products` 刷新后仍然可以打开。

### 13.5 商品质量和跨链路验收

- 可以一键筛出无主图、无详情图、缺件规、缺价格、编号异常商品。
- 下架商品不会出现在小程序商品列表。
- 下架商品详情接口返回“商品已下架或不存在”。
- 不可开单商品不会被开单页和 Agent 当作可销售商品。
- 1 件起订商品在商品页、开单页、Agent 里显示一致。
- 泡袋和标签类商品显示不扣库存，销售单删除时不会恢复库存。
- 商品主图改动不会被旧图覆盖。
- 图片上传后进入图片资产表，未绑定时能从“待绑定”筛出。

## 14. 技术验收标准

必须补契约测试：

- `ProductsPage` 从 `components/business/products` 导入，不继续定义在 `App.tsx`。
- 商品页不再使用 `primary-action`、`ghost-action`、`status-badge`、`panel`。
- 商品页业务组件不直接写原生 `<button>`、`<input>`、`<select>`，统一使用 UI 组件。
- 商品列表使用 `Card + Badge + Pagination`。
- 编辑弹窗使用 `Dialog + Tabs + Field`。
- 规格列表使用 `Table`。
- 删除商品和删除图片资产使用 `AlertDialog`。
- 图片选择器使用 `Dialog + Tabs + Skeleton + Empty`。
- 商品页仍调用现有商品 API，不绕过服务层。

推荐验证命令：

```powershell
python -m unittest tests.test_admin_product_edit_contract tests.test_admin_products_media_contract tests.test_admin_shadcn_foundation_contract -v
cd Z:\sjagent\admin
npm.cmd run build
```

浏览器验证：

- 打开 `http://127.0.0.1:8081/admin/products`。
- 搜索“喜悦”。
- 切换礼盒和泡袋分类。
- 打开一个商品编辑。
- 修改件规但不保存，确认不会影响列表。
- 点主图上传/选择，确认弹窗可见且只出现一个选择入口。
- 切换未绑定、本产品图片、全部图片。
- 打开 `http://127.0.0.1:8081/admin/media`，确认图片资产仍正常。
- 打开 `http://127.0.0.1:8081/admin/products`，确认商品页仍可用。

## 15. 开发阶段计划

### 阶段 1：商品页拆分

目标：从 `App.tsx` 拆出商品业务组件，页面功能不变。

当前状态：已完成第一轮结构拆分。`App.tsx` 已不再定义 `function ProductsPage` 和 `function MediaPage`，只负责导入和路由渲染。

交付：

- `admin/src/components/business/products/` 目录。
- `ProductsPage`、`ProductCardGrid`、`ProductCard`、`ProductToolbar`。
- `App.tsx` 只导入和渲染 `ProductsPage`。
- 契约测试确认 `App.tsx` 不再包含 `function ProductsPage`。

### 阶段 2：列表视觉和分类重做

目标：商品列表变成 shadcn 风格紧凑 SPU 卡片，分类不再横向滚动。

当前状态：已开始落地。商品列表工具栏已使用 `Input + Button`，一级分类已使用 `Tabs`，二级分类改成自动换行按钮组；一级分类筛选已通过 `product_type` 参数走 `ProductService.list()`，不是前端假筛选。泡袋一级分类会同时查询 `bag` 和 `bubble_bag`，避免历史类型漏数据。商品卡片已使用 `Card + Badge`，加载态和空状态已使用 `Skeleton`、`Empty`；卡片密度已再次收紧为小尺寸 SPU 卡，减少图片高度、指标块高度和卡片间距。

交付：

- 一级/二级分类筛选。
- 商品卡片新视觉。
- `Skeleton` 加载态。
- `Empty` 空状态。
- `Pagination` 分页。
- 资料完整度筛选：无主图、无详情图、缺件规、缺价格、编号异常。

### 阶段 3：商品编辑 Dialog 重做

目标：编辑弹窗从一条长滚动改成 `Dialog + Tabs`。

当前状态：已落地第一版。`ProductEditorDialog` 使用 shadcn/Radix `DialogContent`、`TabsContent`、`FieldGroup`、`Select`、`Table`、`Switch`、`ScrollArea`，基础信息、规格/颜色、图片、上架/起订和记录已分区。规格/颜色已改成表格编辑，价格输入保留 `onWheel={inputNoWheel}` 防误滚。本轮已把“扣不扣库存”提升到基础信息，保存时统一写入所有 SKU；规格表不再逐行显示库存规则，弹窗移除顶部重复保存按钮并收紧卡片、表格和输入框密度。

交付：

- 基础信息 Tab：已完成。
- 规格/颜色表格：已完成第一版。
- 图片 Tab：已完成。
- 上架/起订 Tab：已完成基础状态和 1 件起订展示；库存规则改到基础信息统一设置。
- 保存流程仍调用 `api.saveProduct()`：已保留。
- 待补：上架状态、开单可用状态、小程序上架状态三者分离；保存前差异确认。

### 阶段 4：图片选择器重做

目标：图片选择和上传统一，商品编辑和图片资产页共用规则。

当前状态：已落地第一版。`ImageAssetPickerDialog` 使用 `DialogContent + Tabs + Input + Button + ScrollArea + Skeleton + Empty`，保留未绑定、本产品图片、全部图片三个入口，主图、详情页和规格图都走同一个选择器。

交付：

- `ImageAssetPickerDialog` 拆出独立组件：待后续从 `products-page.tsx` 继续拆文件。
- Tabs：未绑定、本产品图片、全部图片：已完成。
- 搜索、上传、懒加载、去重：已完成第一版。
- 主图、详情页、颜色图三个入口复用同一个选择器：已完成，颜色图入口当前命名为规格图。
- 待补：图片资产管理页同步重做、删除图片资产改 `AlertDialog`、缩略图分页/虚拟列表。

### 阶段 5：上架/下架/删除补齐

目标：风险动作全部有确认，业务规则走服务层。

交付：

- 商品卡片上架/下架 `AlertDialog`：已完成第一版。
- 商品卡片删除 `AlertDialog`：已完成第一版。
- `ProductService.delete()` / `ProductService.update_shelves()`：后端已按 SPU 级处理，点一个产品会同步处理该 SPU 下全部 SKU。
- 删除图片资产改成 `AlertDialog`。
- 资料状态、开单可用、小程序上架三个状态在 UI 上分清。
- 下架后小程序列表和详情过滤由服务层验证。

### 阶段 6：联调和验收

目标：商品页、图片资产页、开单页、小程序商品详情四处数据一致。

交付：

- 商品页契约测试。
- 图片选择器契约测试。
- admin build 通过。
- 浏览器 smoke 通过。
- `/admin/products` smoke 通过。

## 16. 后续拓展方向

- 商品批量上下架。
- 批量改分类。
- 批量导入价格。
- SKU 价格历史。
- 商品操作日志。
- 商品复制，新建相似商品。
- 商品详情页预览小程序展示效果。
- 图片资产 AI 自动分类。
- 图片缩略图预生成和虚拟列表。
- 多渠道商品展示，比如后台、小程序、未来商城各自的上架状态。
- 商品销售排行和滞销提醒。
- 商品资料体检看板：无图、缺详情、缺件规、缺价格、编号异常集中处理。
- 商品批量导出和导入：用于批量核价、批量补分类，但导入必须走服务层校验。
- 商品变更审批：价格、库存规则、编号变更可以进入审核流，避免误操作。
