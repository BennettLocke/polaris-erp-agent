# React 后台设置页开发项目书

版本: v0.1  
日期: 2026-05-26  
适用入口: `/admin/settings`  
相关旧入口: `/admin/media`, `/admin/miniapp-images`，现已整合到设置页
当前状态: 旧 `/web` 页面已下线，设置页只维护 `/admin/settings` React 后台入口。

## 1. 页面定位

设置页要成为 React 后台的系统配置中心。它不是一个“占位设置页”，也不是把所有表单堆在一起的大杂烩，而是把低频但关键的规则、图片资产、小程序配置、用户权限和打印规则集中到一个稳定入口里。

本轮用户明确要求:

- 把现在独立的“图片资产”放进设置页。
- 把现在独立的“小程序图片”放进设置页，并改名为“小程序设置”。
- 小程序设置第一阶段不用扩展新能力，只把现在已有的首页轮播、分类图标、底部导航图标维护能力集成进去。
- 图片资产和小程序设置是两个独立功能，只是同归到设置页入口下；不能把商品图片资产库和小程序前台图片配置混成一个页面、一套数据或一个保存流程。
- 其他设置功能参考历史业务逻辑，保留编号、商品基础、库存规则、收款结款、图片/OSS、用户权限、打印设置等已有业务逻辑。
- 组件风格必须和当前 React + Radix/shadcn 后台一致。

页面目标:

- 让左侧主导航更干净，`图片资产` 和 `小程序图片` 不再作为高频业务入口暴露。
- 让设置功能按业务归类，而不是按历史文件来源归类。
- 设置相关入口统一收进 `/admin/settings`，避免已有功能分散。
- 每个设置分区都独立加载、独立保存、独立报错，避免一个接口失败拖垮整个设置页。

## 2. 当前代码现状

当前 React 后台已经有三块相关代码:

| 功能 | 现状 | 主要文件 |
| --- | --- | --- |
| 设置页 | 已有基础版，但还在 `admin/src/SettingsPage.tsx`，内部使用较多原生 `button/input/select` 和旧样式类 | `admin/src/SettingsPage.tsx` |
| 小程序图片 | 已有独立页面，维护轮播图、商品分类图标、底部导航图标 | `admin/src/components/business/miniapp-images/miniapp-images-page.tsx` |
| 图片资产 | 已有独立页面，代码在商品页文件底部，支持分类筛选、分页、删除 | `admin/src/components/business/products/products-page.tsx` 的 `MediaPage` |

当前接口已经具备:

| 功能 | 接口 |
| --- | --- |
| SKU 编号设置 | `GET/POST /api/settings/number/sku` |
| 系统设置 | `GET/POST /api/settings/system/{setting_key}` |
| 销售单打印设置 | `GET/POST /api/settings/print/sales` |
| 用户列表和角色启停 | `GET /api/users`, `PATCH /api/users/{id}` |
| 仓库列表 | `GET /api/warehouses` |
| 小程序图片配置 | `GET /api/miniapp/image-config`, `PATCH /api/miniapp/image-config` |
| 小程序图片上传 | `POST /api/miniapp/image-config/upload` |
| 商品图片资产 | `GET /api/product/media`, `DELETE /api/product/media/{id}` |
| 图片上传和裁切 | `POST /api/product/upload`, `POST /api/product/crop-square` |

历史设置区包含:

- 编号设置
- 商品基础
- 库存规则
- 收款结款
- 图片/OSS
- 小程序设计
- 用户权限
- 打印设置

第一阶段 React 设置页只承接已稳定可用、当前 React 已有接口支撑的功能。小程序完整设计器、仓库增删改、ASR 热词管理可以在设置页预留入口，但不要在本轮伪造功能。

## 3. 信息架构

建议设置页使用“左侧设置导航 + 右侧内容区”的结构。桌面端左侧导航固定宽度，右侧展示当前分区；窄屏时降级为横向滚动 Tabs。

分组建议:

```text
设置
  基础规则
    编号规则
    商品基础
    库存规则
    收款结款

  资产与小程序
    图片资产
    小程序设置

  系统
    用户权限
    打印设置
```

说明:

- 原来的“图片/OSS”不再作为单独大入口，合并到“图片资产”里的“上传规则”子区。
- 原来的“小程序图片”改名为“小程序设置”，第一阶段内容仍然是图片配置。
- 原 React 侧栏里的 `图片资产` 和 `小程序图片` 后续可以移除，或者保留隐藏兼容路由。
- `/admin/media` 访问时固定映射到 `/admin/settings?section=media`，打开“图片资产”分区。
- `/admin/miniapp-images` 访问时固定映射到 `/admin/settings?section=miniapp`，打开“小程序设置”分区。

必须明确边界:

| 分区 | 管什么 | 不管什么 | 数据来源 |
| --- | --- | --- | --- |
| 图片资产 | 商品主图、详情页、颜色图、待绑定图片、OSS 上传规则 | 不维护小程序首页轮播、分类入口图标、底部导航图标 | `product_media`、`product_sku.main_image_url`、`image_rules` |
| 小程序设置 | 小程序首页轮播图、商品分类图标、底部导航图标 | 不管理商品主图、详情页、颜色图、待绑定资产库 | `miniapp_asset`、`product_category.icon/icon_active`、小程序图片配置接口 |

这两个分区可以放在同一个设置页导航下，但实现时必须拆成 `MediaSettingsPanel` 和 `MiniappSettingsPanel` 两个组件，接口调用、加载状态、保存状态和错误提示都各自独立。

## 4. 页面布局

推荐结构:

```text
SettingsPage
  PageHeader
    标题: 设置
    副标题: 管理编号、库存、收款、图片、小程序、用户和打印规则
    右侧: 刷新当前分区

  SettingsShell
    SettingsNav
      分组导航
      当前分区 Badge 或说明

    SettingsContent
      SectionToolbar
      SectionAlert
      SectionPanel
      SectionSaveBar
```

视觉规则:

- 设置页是后台配置工具，保持安静、紧凑、清晰。
- 不做营销式大标题，不做大面积装饰卡片。
- 页面内容不要再套多层大卡片。外层用布局，具体分区和重复项用 `Card`。
- 表单区域使用两列或三列网格，字段说明放在字段下方，不要用长段落占据首屏。
- 高危动作如删除图片、停用用户、修改角色使用 `AlertDialog` 或明确二次确认。
- 成功和失败提示统一用当前项目已有的 `form-success/form-error` 样式或后续接入 `sonner`，不要使用 `window.alert`。

## 5. 组件拆分

建议新建目录:

```text
admin/src/components/business/settings/
  index.ts
  settings-page.tsx
  settings-shell.tsx
  settings-nav.tsx
  settings-section-header.tsx
  settings-save-bar.tsx
  setting-list-editor.tsx
  setting-summary-strip.tsx
  number-settings-panel.tsx
  product-basic-panel.tsx
  inventory-rules-panel.tsx
  payment-rules-panel.tsx
  media-settings-panel.tsx
  miniapp-settings-panel.tsx
  user-permissions-panel.tsx
  print-settings-panel.tsx
```

保留 `admin/src/SettingsPage.tsx` 作为兼容导出也可以，但最终业务实现应放到 `components/business/settings/`，避免根目录继续变大。

组件职责:

| 组件 | 职责 |
| --- | --- |
| `SettingsPage` | 解析当前分区、加载公共数据、承接路由兼容 |
| `SettingsShell` | 设置页左右布局和移动端 Tabs 降级 |
| `SettingsNav` | 分组导航、分区切换、未保存状态提示 |
| `SettingsSectionHeader` | 当前分区标题、说明、刷新按钮 |
| `SettingsSaveBar` | 保存按钮、重置按钮、保存状态、最近保存时间 |
| `SettingListEditor` | 单位、泡袋版型、付款方式、调整原因等字符串列表编辑 |
| `SettingSummaryStrip` | 编号统计、图片资产统计等紧凑数字条 |
| `NumberSettingsPanel` | SKU 编号规则和变更记录 |
| `ProductBasicPanel` | 商品单位、泡袋版型、默认件规、默认单位、分类新增/编辑 |
| `InventoryRulesPanel` | 默认出库仓、是否允许负库存、分类库存策略、扣/不扣库存关键词 |
| `PaymentRulesPanel` | 付款状态、已付方式、默认结算方式、余额调整原因、月结说明 |
| `MediaSettingsPanel` | 图片资产列表、图片类型筛选、分页、删除、上传规则 |
| `MiniappSettingsPanel` | 小程序首页轮播、分类图标、底部导航图标上传维护 |
| `UserPermissionsPanel` | 用户搜索、角色切换、启停、固定权限说明 |
| `PrintSettingsPanel` | 销售单打印模板、纸张、方向、显示字段、预览入口 |

## 6. shadcn/Radix 组件使用

组件来源以 `admin/src/components/ui` 为准。继续沿用当前 React 后台的 shadcn/Radix 风格。

| 场景 | 组件 | 规则 |
| --- | --- | --- |
| 页面标题 | `PageHeader`, `Button` | 右侧只放刷新当前分区等少量动作 |
| 设置导航 | `Tabs` 或自定义基于 `Button` 的分组导航 | 桌面左侧，移动端横向滚动 |
| 表单字段 | `Field`, `FieldGroup`, `Input`, `Textarea`, `Select`, `Switch` | 不再用原生 `input/select/button` 直接写业务样式 |
| 字符串列表编辑 | `Input`, `Button`, `Badge` | 添加、删除项要可见，重复项直接忽略或提示 |
| 图片资产筛选 | `Tabs`, `Badge`, `Button` | 全部、待绑定、主图、详情页、颜色图 |
| 图片网格 | `Card`, `Badge`, `DropdownMenu`, `AlertDialog` | 删除必须二次确认 |
| 小程序图片维护 | `Card`, `Button`, `Badge`, `Skeleton` | 上传按钮放在每个图片槽位，不做隐藏操作 |
| 用户管理 | `Table` 或紧凑 `Card`, `Select`, `Switch`, `Badge` | 角色和启停必须左对齐，当前状态明显 |
| 打印设置 | `FieldGroup`, `Select`, `Switch`, `Input`, `Button` | 预览和保存分开 |
| 加载状态 | `Skeleton` | 不使用纯文字“加载中”占位 |
| 空状态 | `Empty` | 区分“无数据”和“当前筛选无结果” |
| 危险确认 | `AlertDialog` | 删除图片、停用用户等 |
| 轻提示 | `sonner` 或当前项目统一消息块 | 成功、失败、权限错误用中文 |

禁止:

- 新增原生业务按钮样式。
- 使用 `window.confirm`、`window.alert`。
- 把所有设置一次性放进一个巨大表单保存。
- 在前端绕过服务层直接拼业务规则。
- 在设置页里伪造小程序设计器、仓库增删改等未完成能力。

## 7. 数据加载策略

设置页应按分区懒加载，而不是打开页面一次性请求所有接口。

推荐策略:

- 首屏只加载当前分区。
- 切换分区时加载该分区数据，已加载过的数据可缓存。
- 点击“刷新”只刷新当前分区。
- 每个分区有自己的 `loading`, `error`, `dirty`, `saving` 状态。
- 保存成功后只刷新当前分区，不整页闪烁。
- 切换分区时如果当前分区有未保存修改，提示用户保存或放弃。
- 如果当前分区有未保存修改，切换分区、刷新当前分区、离开设置页或打开旧兼容路由时都要用 `AlertDialog` 提示。按钮固定为“保存并继续”“放弃修改”“取消”，不能静默丢弃。

示例状态:

```ts
type SettingsSectionKey =
  | "number"
  | "product"
  | "inventory"
  | "payment"
  | "media"
  | "miniapp"
  | "users"
  | "print";

type SectionState<T> = {
  data: T | null;
  draft: T | null;
  loading: boolean;
  saving: boolean;
  error: string;
  dirty: boolean;
};
```

## 8. 分区设计

### 8.1 编号规则

接口:

- `GET /api/settings/number/sku`
- `POST /api/settings/number/sku`

展示:

- 当前下一编号
- 配置起点
- 已用 SJ 编号数
- 商品 SKU 总数
- 编号前缀
- 手动调整下一号
- 补零位数
- 备注
- 编号变更记录

交互:

- 保存只影响后续新建商品和上传脚本的自动编号，不改历史 SKU。
- 输入下一编号时要保留后端校验，不在前端硬猜冲突规则。
- 保存失败保留用户输入。
- 变更记录只读。

### 8.2 商品基础

接口:

- `GET /api/settings/system/product_basic`
- `POST /api/settings/system/product_basic`

展示:

- 分类管理列表，显示分类名、商品类型、商品数、库存策略。
- 新增分类和编辑分类使用 `Dialog`，字段包括分类名称、商品类型、分类库存策略、排序。
- 单位列表。
- 泡袋版型列表。
- 默认件规。
- 默认单位。

交互:

- 单位和泡袋版型使用 `SettingListEditor`。
- 默认单位从单位列表中选择。
- 分类库存策略保存后调用 `/api/product/categories`，由服务层同步分类下 SKU 的 `is_stock_item` 和 `inventory_policy`。
- 保存只提交 `value`，不要把 `categories` 等接口附加展示数据反写回设置。

### 8.3 库存规则

接口:

- `GET /api/settings/system/inventory_rules`
- `POST /api/settings/system/inventory_rules`
- `GET /api/warehouses`

展示:

- 分类库存策略表，可直接把分类切为扣库存、不扣库存或弱库存。
- 扣库存分类列表。
- 不扣库存分类列表。
- 扣库存关键词和不扣库存关键词列表编辑。
- 默认出库仓库。
- 是否允许负库存开单。

交互:

- 默认出库仓库来自 `warehouses`。
- 保存关键词规则时，后端会把匹配到的分类策略同步为扣库存或不扣库存，再同步分类下 SKU。
- 分类有明确 `inventory_policy` 时分类优先；分类未明确时再走关键词兜底。
- 泡袋、茶袋、标签、服务、设计、制版、辅料、快递纸箱、PVC礼盒等作为默认不扣库存关键词保留，但前端允许维护关键词配置。
- 仓库增删改第一阶段不做，因为当前 React 可用接口只有仓库列表。

### 8.4 收款结款

接口:

- `GET /api/settings/system/payment_rules`
- `POST /api/settings/system/payment_rules`

展示:

- 付款状态列表。
- 已付方式列表。
- 默认结算状态。
- 默认已付方式。
- 余额调整原因。
- 月结说明。

交互:

- 默认值必须来自对应列表。
- 删除一个列表项时，如果它正被默认值使用，前端应要求先切换默认值。
- 月结说明用 `Textarea` 或单行 `Input`，取决于现有字段长度。
- 保存后开单页和客户余额相关页面下一次加载应使用新配置。

### 8.5 图片资产

图片资产分区承接现在独立的“图片资产”页面，同时合并原“图片/OSS”设置。

接口:

- `GET /api/product/media?page=&page_size=&media_type=`
- `DELETE /api/product/media/{id}`
- `POST /api/product/upload`
- `GET /api/settings/system/image_rules`
- `POST /api/settings/system/image_rules`

建议子 Tabs:

- `资产库`: 全部图片、待绑定、主图、详情页、颜色图。
- `上传规则`: OSS 路径、缩略图规则、待绑定清理天数、上传后自动压缩、资产分类规则。

资产库展示:

- 图片预览，保持 1:1 缩略图，不拉伸。
- 图片列表必须使用缩略图 URL 或 OSS `x-oss-process` 规则，避免大量原图直接进入设置页造成加载慢。
- 绑定对象: 商品名、颜色、分类、待绑定。
- 图片类型: 主图、详情页、颜色图、待绑定。
- 来源和存储类型。
- 分页。
- 上传新图片入口，上传后作为待绑定图片进入资产库。
- 删除动作。

交互:

- 删除图片使用 `AlertDialog`，不要使用 `window.confirm`。
- 删除后刷新当前页。如果当前页删除到空且不是第一页，自动回到上一页。
- 图片加载失败显示稳定占位，不让卡片高度跳动。
- 待绑定图片要清楚显示，方便后续绑定商品。
- 上传新图片时使用现有 `POST /api/product/upload`，成功后刷新“待绑定”或当前筛选；不要把上传后的商品图片混入小程序设置。
- 上传规则保存和资产列表删除互不影响。

### 8.6 小程序设置

第一阶段承接现在“小程序图片”页面的功能，不扩展完整小程序设计器。

接口:

- `GET /api/miniapp/image-config`
- `POST /api/miniapp/image-config/upload`
- `PATCH /api/miniapp/image-config`

展示:

- 首页轮播图。
- 商品分类图标，包含未选中图标和选中图标。
- 底部导航图标，包含未选中图标和选中图标。

命名:

- 主导航和设置分区都叫“小程序设置”。
- 页面内可以说明“当前先维护小程序图片配置”。
- 不再叫“小程序图片”。

交互:

- 每个图片槽位有明确标题、用途说明、当前图片、替换按钮。
- 小程序设置里的图片只服务小程序前台配置，不进入商品图片资产列表，也不作为商品主图、详情页或颜色图展示。
- 上传成功后立即调用 `PATCH /api/miniapp/image-config` 保存对应字段。
- 保存成功后刷新当前配置。
- 失败时保留原图，不做半成功状态。
- 首页轮播、分类图标、底部导航分成三个清晰区域。
- 完整小程序设计器第一阶段不做，只预留后续“页面设计”入口或说明。

### 8.7 用户权限

接口:

- `GET /api/users?keyword=&page=&page_size=`
- `PATCH /api/users/{id}`
- 可读权限说明来自服务层固定角色规则，不在前端随意编辑。

展示:

- 用户显示名、账号、手机、关联客户。
- 角色: 管理员、员工、客户、访客。
- 启用状态。
- 审核状态或最近登录时间，如接口有返回则展示。
- 固定权限说明。

交互:

- 搜索账号、姓名、电话。
- 角色切换用 `Select` 或紧凑分段控制，更新后刷新当前列表。
- 启停用 `Switch`，停用用户需要二次确认。
- 当前登录用户不允许把自己停用或降成无权限角色，至少前端要拦截，后端也应保护。
- 需要补后端合同测试，确认接口层不能把当前登录管理员误停用或降成无设置权限角色。
- 权限规则第一阶段只读，避免前端保存一套和后端 `FIXED_ROLE_PERMISSIONS` 不一致的权限。

### 8.8 打印设置

接口:

- `GET /api/settings/print/sales`
- `POST /api/settings/print/sales`
- `POST /api/sales/{id}/print-task`
- `GET /api/sales/{id}/print-html?auto=0`

展示:

- 模板名称。
- 标题。
- 纸张。
- 方向。
- 字号。
- 份数。
- 是否显示开单人。
- 是否显示客户电话。
- 是否显示付款状态。
- 是否显示备注。
- 底部文字。
- 最近销售单预览入口。

交互:

- 保存模板不自动打印。
- 预览使用最近销售单 `latest_print_url`。
- 创建打印任务用明确按钮，避免误点。
- 没有最近销售单时禁用预览和打印任务按钮。

## 9. 路由和导航调整

`RouteKey` 建议移除独立可见项:

- `media`
- `miniapp-images`

但路由兼容要保留:

```ts
function routeFromLocation(): RouteKey {
  const segment = ...;
  if (segment === "media") {
    return "settings";
  }
  if (segment === "miniapp-images") {
    return "settings";
  }
}
```

同时在 `SettingsPage` 内根据路径或 query 决定初始分区:

| 访问路径 | 设置分区 |
| --- | --- |
| `/admin/settings` | 默认 `number` 或上次使用分区 |
| `/admin/settings?section=media` | 图片资产 |
| `/admin/settings?section=miniapp` | 小程序设置 |
| `/admin/media` | 固定等效于 `/admin/settings?section=media` |
| `/admin/miniapp-images` | 固定等效于 `/admin/settings?section=miniapp` |

侧栏分组建议:

- 主业务: 工作台、开单、销售单、客户
- 资产: 商品、库存、订单
- 系统: 设置

这样设置页承接资产配置，不把低频配置放在主侧栏。

## 10. API 客户端调整

`admin/src/api.ts` 已有大部分方法。后续实现时建议补齐统一命名:

```ts
settingsNumber(): Promise<NumberSequenceSettings>
saveSettingsNumber(payload): Promise<NumberSequenceSettings>
settingsSystem(key): Promise<SystemSetting>
saveSettingsSystem(key, payload): Promise<SystemSetting>
settingsPrint(): Promise<PrintSettings>
saveSettingsPrint(payload): Promise<PrintSettings>
settingsUsers(query): Promise<ListResult<UserListItem>>
updateSettingsUser(id, payload): Promise<{ id: number; affected: number }>
settingsMedia(query): Promise<ListResult<ProductMediaAsset>>
uploadSettingsMedia(file): Promise<ProductUploadResult>
deleteSettingsMedia(id): Promise<{ id: number; affected: number }>
settingsMiniappImages(): Promise<MiniappImageConfig>
uploadSettingsMiniappImage(file): Promise<ProductUploadResult>
updateSettingsMiniappImage(payload): Promise<{ id: number; affected?: number }>
```

可以先复用现有方法名，但设置页内部建议通过一个薄包装层调用，避免后续迁路由时全页面散落修改。

## 11. 类型约束

需要确认或补充的类型:

```ts
type SettingsSectionKey =
  | "number"
  | "product"
  | "inventory"
  | "payment"
  | "media"
  | "miniapp"
  | "users"
  | "print";

type SystemSettingKey =
  | "product_basic"
  | "inventory_rules"
  | "payment_rules"
  | "image_rules";

type MediaTypeFilter =
  | ""
  | "pending"
  | "main_image"
  | "detail_image"
  | "color_image";
```

设置保存时要区分:

- `SystemSetting.value`: 可编辑配置。
- `SystemSetting.categories`, `SystemSetting.warehouses`, `SystemSetting.media_summary`: 展示用附加数据，不反写。
- `MiniappImageConfig.assets`, `MiniappImageConfig.categories`: 小程序图片配置数据，不走 `system_setting` 保存。
- `ProductMediaAsset`: 图片资产库数据，只能删除或后续绑定，不属于 `image_rules`。

## 12. 权限和安全

后端已有权限规则:

- 设置相关接口需要“设置”权限。
- 图片上传需要“图片上传”权限。
- 图片绑定和删除需要“图片绑定”权限。
- 用户更新需要“设置”权限。

前端规则:

- 没权限时显示接口返回的中文错误，不要吞掉。
- 保存按钮在请求中禁用，防止重复提交。
- 图片上传只接受图片文件。
- 删除图片、停用用户使用二次确认。
- 用户权限页不要展示可编辑的动态权限矩阵，第一阶段只做固定角色说明和角色切换。

## 13. 加载、错误和空状态

每个分区必须覆盖:

- 首次加载: `Skeleton`。
- 加载失败: 错误块 + 重试按钮。
- 空数据: `Empty`，说明当前没有数据或当前筛选无结果。
- 保存中: 只禁用当前分区保存按钮，不锁整个设置页。
- 上传中: 只锁当前图片槽位。
- 删除中: 只锁当前图片卡片。

错误文案要是中文:

- 设置加载失败
- 保存失败，请重试
- 图片上传失败
- 图片删除失败
- 用户更新失败
- 打印设置保存失败

不要把英文异常直接作为唯一文案。如果需要展示原始异常，放在后半句。

## 14. 实现顺序

建议按这个顺序做，避免一次性重构太大:

1. 新建 `components/business/settings/` 目录，迁移 `SettingsPage` 外壳和基础导航。
2. 接入分区路由: `/admin/settings?section=...`，兼容 `/admin/media` 和 `/admin/miniapp-images`。
3. 先迁移低风险基础设置: 编号、商品基础、库存规则、收款结款。
4. 再迁移写操作较多的系统设置: 用户权限、打印设置。
5. 把 `MediaPage` 从商品页文件中拆出为 `MediaSettingsPanel`，放进设置页的“图片资产”分区，并补上传待绑定图片入口。
6. 把 `MiniappImagesPage` 改造成 `MiniappSettingsPanel`，命名改为“小程序设置”。注意它和图片资产是两个独立分区，不能共用保存逻辑。
7. 移除侧栏中独立的“图片资产”和“小程序图片”可见入口，保留路由兼容。
8. 统一原生控件为 shadcn/Radix 组件。
9. 补静态合同测试和必要的交互测试。
10. 构建 React，并检查设置页、图片资产、小程序设置的浏览器表现。

## 15. 测试计划

建议新增或更新:

| 测试 | 目的 |
| --- | --- |
| `tests/test_admin_settings_page_contract.py` | 确认设置页包含新分区、旧路由固定映射、组件拆分和接口调用 |
| `tests/test_admin_media_settings_contract.py` | 确认图片资产进入设置页，支持上传待绑定图片，删除使用 `AlertDialog` 而不是 `window.confirm` |
| `tests/test_admin_miniapp_settings_contract.py` | 确认“小程序图片”命名改为“小程序设置”，且仍调用现有小程序图片接口，不调用商品图片资产接口 |
| `tests/test_admin_user_settings_contract.py` | 确认当前登录管理员不能通过接口误停用自己或把自己降成无设置权限角色 |
| `tests/test_business_services.py` 相关用例 | 保持 `SettingsService`, `MiniAppService`, `ProductService.media_assets` 行为稳定 |

前端构建验证:

```powershell
cd Z:\sjagent\admin
npm.cmd run build
```

后端静态和服务层验证:

```powershell
cd Z:\sjagent
python -m unittest tests.test_admin_settings_page_contract tests.test_business_services -v
```

浏览器验收点:

- `/admin/settings` 默认进入设置页。
- `/admin/media` 能打开设置页图片资产分区。
- `/admin/miniapp-images` 能打开设置页小程序设置分区。
- 图片资产筛选、分页、上传待绑定图片、删除可用。
- 小程序首页轮播、分类图标、底部导航图标可替换。
- 图片资产和小程序设置在视觉上相邻但功能独立，切换、上传、保存、报错互不影响。
- 编号、库存、收款、打印等原设置保存流程不退化。

## 16. 第一阶段不做

以下内容不要在第一阶段硬做:

- 小程序完整可视化设计器。
- 仓库新增、编辑、删除。
- 动态权限矩阵编辑。
- ASR 热词管理页面。
- 图片资产批量删除。
- 图片资产批量绑定。
- 小程序发布、缓存刷新、版本管理。

这些都可以后续放在设置页，但需要对应服务层接口和单独项目书。

## 17. 验收标准

本轮设置页完成后，应满足:

- 侧栏只保留“设置”，不再暴露“小程序图片”和“图片资产”两个低频入口。
- 访问旧 React 路由仍然能进入对应设置分区。
- 小程序图片功能改名为“小程序设置”，现有能力不丢。
- 图片资产功能完整迁入设置页，能筛选、分页、上传待绑定图片、删除。
- 图片资产和小程序设置是两个独立分区，不能混用数据、接口、保存状态和错误状态。
- 旧设置里的编号、商品基础、库存规则、收款结款、用户权限、打印设置都能使用。
- 所有表单和操作控件使用当前 shadcn/Radix 组件风格。
- 没有原生确认弹窗，没有英文裸错误，没有伪造未完成业务能力。
- 构建通过，相关合同测试通过。
