# 商品数据库明细设计

更新时间：2026-05-20

目标：把 ShopXO 商城商品表和 ERP 商品表收拢成北极星自己的商品中心。商品中心只认一套主数据，库存、开单、商品管理、泡袋上传、小程序展示都从这里取数。

参考业务规则：[[SKU管理]]、[[产品分类]]、[[件套换算]]、[[进货规则]]、[[数据库地图]]

## 1. 总体结构

| 表 | 第一轮是否建 | 用途 | 说明 |
|---|---|---|---|
| `product_spu` | 是 | 商品组/款式 | 放“这一款是什么”，比如 `【见喜】一两`、`【星禾】二三两` |
| `product_sku` | 是 | 真实商品/SKU | 放“具体可卖可库存的商品”，比如 `【见喜】一两 + 红色` |
| `product_category` | 是 | 商品分类 | 半斤礼盒、一两礼盒、肉桂泡袋、其他产品等 |
| `product_category_map` | 否 | 商品和分类关系 | 第一轮不建，分类直接写在 `product_sku` 里 |
| `product_unit` | 是 | 单位 | 套、捆、个、斤、张、件 |
| `product_alias` | 是 | 搜索/OCR/口语别名 | 让“喜悦三小盒”“喜悦 3 小盒”“三小盒喜悦”都能搜到 |
| `product_media` | 是 | 商品图片资产 | 主图、详情图、源图、缩略图；给图片上传插件和图片管理页用 |
| `product_price_rule` | 后置 | 阶梯价/特殊计价 | 主要给烫金泡袋、加工服务、批量价使用 |
| `product_channel_listing` | 后置 | 商城/小程序展示 | 第一轮可先把展示字段放 `product_sku`，多渠道时再拆 |

## 2. `product_spu` 商品组/款式表

`product_spu` 是商品的“款式层”。它不直接扣库存，不直接开单，只负责把多个 SKU 归到同一组。这里尽量少放名字字段：客户看见的标题就放一个 `title`，例如 `【喜悦】半斤`；平时口头说的 `喜悦半斤红色` 由 `series + size_label + sku.color` 自动拼出来，不单独存一套名称。

为了创建商品时更方便，可以在 SPU 上保留一个已有颜色列表 `available_colors`，但这个列表只是缓存/展示字段，真正可开单和可库存的颜色仍以 SKU 为准。

例子：

- `【见喜】一两` 是一个 SPU，下面有红色、黄色、蓝色等 SKU。
- `【星禾】二三两` 是一个 SPU，下面有不同颜色 SKU。
- 泡袋如果每个 SJ 编号基本只有一个成品，也可以一组一 SKU。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 商品组系统 ID | 数据库内部关联用，不给业务人员当编号 |
| `title` | VARCHAR(160) | 是 | 客户能看懂的商品标题 | 如 `【喜悦】半斤`、`【山川】三小盒` |
| `product_type` | VARCHAR(30) | 是 | 商品大类 | `gift_box` 礼盒、`bag` 泡袋、`material` 辅料、`service` 服务、`shipping` 快递耗材、`other` 其他 |
| `series` | VARCHAR(80) | 否 | 系列/品牌 | 见喜、岩味、星禾、山川、茶礼、SJ 泡袋等 |
| `size_label` | VARCHAR(80) | 否 | 规格 | 一两、二三两、半斤、五格、三小盒、六小盒等 |
| `available_colors` | JSON | 否 | 当前款式已有颜色列表 | 例如 `["红色","黄色","蓝色"]`；从该 SPU 下 SKU 的 `color` 汇总，也可创建商品时先写入 |
| `tea_type` | VARCHAR(80) | 否 | 茶类 | 泡袋常用：肉桂、水仙、大红袍、红茶、品种茶；礼盒可空 |
| `case_unit_id` | BIGINT | 否 | 包装/进货单位 | 通常指向单位 `件` |
| `case_pack_qty` | DECIMAL(12,3) | 否 | 1件包含多少销售单位 | 放在 SPU，因为同一款/系列通常统一，例如 1件=20套 |
| `default_category_id` | BIGINT | 否 | 默认分类 | 指向 `product_category.id` |
| `default_supplier_id` | BIGINT | 否 | 默认供应商 | 指向后续 `party.id`；如鑫创意、合丰、武洋 |
| `inventory_policy` | VARCHAR(20) | 是 | 默认库存策略 | `strict` 查库存并校验、`weak` 记录库存但不阻断、`none` 不查库存 |
| `purchase_policy` | VARCHAR(30) | 是 | 默认进货策略 | `one_case` 1件起订、`order_qty` 按订单数量、`none` 不进货 |
| `status` | VARCHAR(20) | 是 | 商品组状态 | `active` 启用、`inactive` 停用、`draft` 草稿、`deleted` 软删 |
| `sort_order` | INT | 否 | 排序 | 商品管理页用 |
| `note` | TEXT | 否 | 内部备注 | 人工备注，不参与搜索判断 |
| `source` | VARCHAR(30) | 是 | 数据来源 | `migration` 迁移、`manual` 手工、`bag_upload` 泡袋上传 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |
| `deleted_at` | DATETIME | 否 | 软删除时间 | 不物理删除，方便查账 |

## 3. `product_sku` 商品 SKU 表

`product_sku` 是最重要的表。智能体查商品、开单、库存、价格、泡袋上传，主要都看这张表。

业务上唯一认 `sku_no`，也就是 `SJxx` 编号。`id` 只是数据库内部关联用，如果以后要修正编号，不会牵动所有外键和历史单据。界面、开单、搜索、导入导出都显示 `sku_no`，不显示 `id`。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | SKU 系统 ID | 数据库内部关联用，不作为业务编号 |
| `spu_id` | BIGINT | 是 | 所属商品组 | 指向 `product_spu.id` |
| `sku_no` | VARCHAR(80) | 是 | 唯一业务编号 | 统一用 `SJxx`；这是内部唯一认的编号 |
| `primary_category_id` | BIGINT | 否 | 主分类 | 指向 `product_category.id`，用于最常用的列表筛选和排序 |
| `category_ids` | JSON | 否 | 所属分类列表 | 保存这个 SKU 属于哪些分类 ID，例如 `[3,18]`；包含主分类 |
| `color` | VARCHAR(60) | 否 | 标准颜色 | 只存红色、黄色、蓝色这类标准颜色；旧规格只在迁移时用来清洗 |
| `bag_type` | VARCHAR(40) | 否 | 泡袋版型 | 只存：长泡袋、短泡袋、红茶袋、宽版、空白；公版属于分类，不放这里 |
| `tea_type` | VARCHAR(80) | 否 | 茶类 | 肉桂、水仙、大红袍、红茶、品种茶；从分类/标题解析 |
| `material_type` | VARCHAR(80) | 否 | 辅料类型 | 内衬袋、纸箱、标签、提袋等 |
| `service_type` | VARCHAR(80) | 否 | 服务类型 | 机器包茶、烫金、UV、丝印、入盒烫膜等 |
| `unit_id` | BIGINT | 是 | 默认销售单位 | 指向 `product_unit.id`；礼盒=套，泡袋=捆，辅料=个/斤/张 |
| `min_purchase_qty` | DECIMAL(12,3) | 否 | 最小进货数量 | 1件起订则填 `1`，非1件起可为空或填订单数量规则 |
| `min_purchase_unit_id` | BIGINT | 否 | 最小进货单位 | 通常是 `件` 或默认销售单位 |
| `inventory_policy` | VARCHAR(20) | 是 | SKU 库存策略 | 优先级高于 SPU；`strict/weak/none` |
| `purchase_policy` | VARCHAR(30) | 是 | SKU 进货策略 | `one_case`、`order_qty`、`min_qty`、`none` |
| `default_warehouse_id` | BIGINT | 否 | 默认发货/入库仓库 | 默认百鑫仓库 ID=2 |
| `default_supplier_id` | BIGINT | 否 | 默认供应商 | 比 SPU 更细的供应商覆盖 |
| `retail_price` | DECIMAL(12,2) | 否 | 默认零售价 | 替代旧 ERP `price/min_price`；无历史价时开单用 |
| `min_price` | DECIMAL(12,2) | 否 | 最低展示价 | 多规格/阶梯价时用，第一轮可等于零售价 |
| `max_price` | DECIMAL(12,2) | 否 | 最高展示价 | 多规格/阶梯价时用 |
| `cost_price` | DECIMAL(12,2) | 否 | 成本价 | 来自 ERP `cost_price` 或后续人工维护 |
| `price_note` | VARCHAR(255) | 否 | 价格备注 | 如“按数量档位”“客户历史价优先” |
| `is_stock_item` | TINYINT | 是 | 是否库存品 | 礼盒/耗材为 1，加工服务可为 0 |
| `is_sellable` | TINYINT | 是 | 是否可销售/开单 | 下架不代表不能内部开单，所以单独放 |
| `is_listed` | TINYINT | 是 | 是否前台展示 | 第一轮代替 ShopXO 上下架；多渠道后迁到 listing 表 |
| `status` | VARCHAR(20) | 是 | SKU 状态 | `active`、`inactive`、`draft`、`deleted` |
| `main_image_url` | VARCHAR(500) | 否 | 主图快捷 URL | 从 `product_media` 的主图同步一份，方便列表快速读取 |
| `detail_image_urls` | JSON | 否 | 详情图快捷 URL 列表 | 从 `product_media` 的详情图汇总一份，方便商品页直接读取 |
| `content_html` | MEDIUMTEXT | 否 | 商品详情 HTML | 承接旧 ShopXO/ERP 详情页 |
| `search_text` | TEXT | 否 | 搜索冗余文本 | 自动生成：标题、颜色、编号、分类、别名拼起来，方便快速搜索 |
| `source` | VARCHAR(30) | 是 | 来源 | `migration`、`manual`、`bag_upload` |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |
| `deleted_at` | DATETIME | 否 | 软删除时间 | 不物理删除 |

## 4. `product_category` 商品分类表

分类第一轮直接承接旧 ERP 分类 ID，避免现有 React 后台的分类筛选断掉。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 分类 ID | 新库自增或固定初始化 |
| `parent_id` | BIGINT | 否 | 上级分类 | 当前多为 0，后续可做层级 |
| `code` | VARCHAR(80) | 否 | 分类编码 | 如 `gift_box_1liang`、`bag_rougui` |
| `name` | VARCHAR(80) | 是 | 分类名称 | 半斤礼盒、肉桂泡袋、其他产品 |
| `product_type` | VARCHAR(30) | 是 | 分类对应大类 | `gift_box/bag/material/service/shipping/other` |
| `inventory_policy` | VARCHAR(20) | 否 | 默认库存策略 | 分类级默认值，如礼盒 strict、服务 none |
| `default_unit_id` | BIGINT | 否 | 默认单位 | 礼盒=套，泡袋=捆 |
| `icon` | VARCHAR(500) | 否 | 分类普通图标 | 来自 ShopXO `sxo_goods_category.icon` |
| `icon_active` | VARCHAR(500) | 否 | 分类选中图标 | 来自 ShopXO `sxo_goods_category.icon_active` |
| `realistic_images` | VARCHAR(500) | 否 | 分类实景图 | 兼容 ShopXO 分类页字段 |
| `big_images` | VARCHAR(500) | 否 | 分类楼层大图 | 兼容 ShopXO 首页/分类字段 |
| `sort_order` | INT | 否 | 排序 | 商品管理页分类排序 |
| `is_enabled` | TINYINT | 是 | 是否启用 | 1 启用，0 停用 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |

## 5. 分类直接放在 SKU 里

第一轮不建 `product_category_map`。分类字典仍然保留在 `product_category`，但每个 SKU 直接写自己属于哪些分类。

这样做更贴近现在的使用方式：看 SKU 时就知道它属于半斤礼盒、肉桂泡袋、公版等分类，不需要再绕一张关系表。未来如果分类变得很多、需要复杂排序或多端展示，再拆 `product_category_map` 也来得及。

| SKU 字段 | 示例值 | 说明 |
|---|---|---|
| `primary_category_id` | `半斤礼盒` 对应的分类 ID | 主分类，用于默认筛选、列表归类 |
| `category_ids` | `[半斤礼盒ID, 公版ID]` | 全部所属分类；前端显示时再关联 `product_category.name` |

## 6. `product_unit` 单位表

旧 ERP 只有套、捆、个、斤、张。新库建议补一个 `件`，因为进货和件套换算会频繁用到。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 单位 ID | 新库固定初始化；需要有 `件` |
| `name` | VARCHAR(30) | 是 | 单位名称 | 套、捆、个、斤、张、件 |
| `code` | VARCHAR(30) | 是 | 单位编码 | `set/bundle/piece/jin/sheet/case` |
| `unit_type` | VARCHAR(30) | 是 | 单位类型 | `sale` 销售、`package` 包装、`weight` 重量、`service` 服务 |
| `precision_scale` | TINYINT | 是 | 小数位 | 套/捆/个通常 0，斤可以 2 |
| `is_enabled` | TINYINT | 是 | 是否启用 | 单位停用后历史单据仍保留 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |

## 7. `product_alias` 搜索别名表

这张表是给智能体准备的，不是传统 ERP 必备表。它能显著减少 OCR、语音、口语下单的匹配错误。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 别名 ID | 自增 |
| `target_type` | VARCHAR(20) | 是 | 指向对象类型 | `spu` 或 `sku` |
| `target_id` | BIGINT | 是 | 指向对象 ID | SPU/SKU ID |
| `alias` | VARCHAR(160) | 是 | 原始别名 | 如 `喜悦3小盒`、`星禾三小`、`SJ506` |
| `normalized_alias` | VARCHAR(160) | 是 | 标准化别名 | 去空格、去括号、数字中文统一后保存 |
| `alias_type` | VARCHAR(30) | 是 | 别名类型 | `ocr`、`voice`、`manual`、`old_title`、`spoken_name`、`code` |
| `weight` | INT | 是 | 匹配权重 | 越高越优先，人工确认别名权重最高 |
| `is_enabled` | TINYINT | 是 | 是否启用 | 错误别名可停用 |
| `source` | VARCHAR(30) | 是 | 来源 | `migration`、`user_feedback`、`auto_extract` |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |

## 8. `product_media` 商品图片资产表

`product_media` 不是开单、库存必须用的表，但建议第一轮保留。它的意义是管“图片资产”：一个商品有多张详情图、源图、缩略图，或者同一张图要复用、去重、替换留历史时，单独表会更好管。

以后做图片上传插件、泡袋图片生成、商品图库、图片管理页面时，这张表会很有用。`product_sku.main_image_url` 和 `product_sku.detail_image_urls` 只是快捷缓存，真正的图片明细以 `product_media` 为准。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 图片 ID | 自增 |
| `sku_id` | BIGINT | 否 | 关联 SKU | 商品图片通常关联 SKU |
| `spu_id` | BIGINT | 否 | 关联 SPU | 组级通用图片可关联 SPU |
| `media_type` | VARCHAR(30) | 是 | 图片类型 | `main` 主图、`detail` 详情图、`source` 源图、`thumbnail` 缩略图 |
| `url` | VARCHAR(500) | 是 | 图片 URL | OSS 或本地静态 URL |
| `storage` | VARCHAR(30) | 是 | 存储位置 | `oss`、`local`、`legacy` |
| `path` | VARCHAR(500) | 否 | 存储路径 | OSS key 或本地相对路径 |
| `file_name` | VARCHAR(255) | 否 | 文件名 | 原始上传文件名或生成文件名 |
| `mime_type` | VARCHAR(80) | 否 | 文件类型 | image/png、image/jpeg |
| `width` | INT | 否 | 图片宽度 | 后续可用于前端裁切 |
| `height` | INT | 否 | 图片高度 | 后续可用于前端裁切 |
| `sha256` | CHAR(64) | 否 | 文件哈希 | 去重、清理用 |
| `sort_order` | INT | 是 | 排序 | 主图 0，详情图按顺序 |
| `is_active` | TINYINT | 是 | 是否有效 | 替换图片时旧图可保留但停用 |
| `source` | VARCHAR(30) | 是 | 来源 | `migration`、`bag_upload`、`manual` |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 图片替换、排序、停用时更新 |

## 9. `product_price_rule` 价格规则表（后置）

普通礼盒和泡袋第一轮直接用 `product_sku.retail_price`。这张表主要给阶梯价和特殊加工服务。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 规则 ID | 自增 |
| `sku_id` | BIGINT | 是 | SKU ID | 指向 `product_sku.id` |
| `rule_type` | VARCHAR(30) | 是 | 规则类型 | `qty_tier` 数量档、`customer` 客户专价、`process` 工艺价 |
| `min_qty` | DECIMAL(12,3) | 否 | 最小数量 | 阶梯价起点 |
| `max_qty` | DECIMAL(12,3) | 否 | 最大数量 | 阶梯价终点，空表示无上限 |
| `unit_id` | BIGINT | 否 | 数量单位 | 个、捆、套等 |
| `price` | DECIMAL(12,2) | 是 | 单价 | 符合规则时使用 |
| `customer_id` | BIGINT | 否 | 客户 ID | 客户专价时使用 |
| `priority` | INT | 是 | 优先级 | 同时命中时取高优先级 |
| `is_enabled` | TINYINT | 是 | 是否启用 | 规则停用不删除 |
| `note` | VARCHAR(255) | 否 | 备注 | 如“大量双面烫金” |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |

## 10. `product_channel_listing` 商品展示表（后置）

第一轮只有一个小程序/商城展示渠道时，可以先不用这张表，把 `is_listed`、`display_title`、图片直接放 `product_sku`。等未来有多渠道展示，再拆出来。

| 字段 | 类型建议 | 是否必填 | 存什么 | 来源/说明 |
|---|---|---:|---|---|
| `id` | BIGINT | 是 | 展示记录 ID | 自增 |
| `sku_id` | BIGINT | 是 | SKU ID | 指向 `product_sku.id` |
| `channel` | VARCHAR(40) | 是 | 展示渠道 | `miniapp`、`web`、`shop`、`internal` |
| `display_title` | VARCHAR(180) | 否 | 渠道展示标题 | 可不同于开单标题 |
| `display_desc` | VARCHAR(255) | 否 | 渠道短描述 | 商品卡片使用 |
| `display_images` | JSON | 否 | 渠道展示图片 | URL 列表 |
| `is_listed` | TINYINT | 是 | 是否上架 | 替代 ShopXO `is_shelves` |
| `sort_order` | INT | 否 | 排序 | 渠道内排序 |
| `created_at` | DATETIME | 是 | 创建时间 | 新库时间 |
| `updated_at` | DATETIME | 是 | 更新时间 | 新库时间 |

## 11. 礼盒怎么存

| 示例字段 | 示例值 | 说明 |
|---|---|---|
| `product_spu.title` | `【见喜】一两` | 客户能看懂的商品标题 |
| `product_spu.product_type` | `gift_box` | 礼盒类 |
| `product_spu.series` | `见喜` | 系列 |
| `product_spu.size_label` | `一两` | 规格 |
| `product_spu.case_pack_qty` | `48` | 1件=48套，同款统一 |
| 自动口头名 | `见喜一两红色` | 由 `series + size_label + color` 生成，不单独存 |
| `product_sku.sku_no` | `SJ0001` | 唯一业务编号 |
| `product_sku.color` | `红色` | 具体颜色 |
| `product_sku.unit_id` | `套` | 销售单位 |
| `product_sku.inventory_policy` | `strict` | 礼盒查库存 |
| `product_sku.purchase_policy` | `one_case` | 1件起订 |
| `product_sku.default_warehouse_id` | `2` | 默认百鑫仓库 |

## 12. 泡袋怎么存

| 示例字段 | 示例值 | 说明 |
|---|---|---|
| `product_spu.title` | `【SJ0506】九龙窠肉桂-长泡袋` | 单编号泡袋可一组一 SKU |
| `product_spu.product_type` | `bag` | 泡袋类 |
| `product_spu.tea_type` | `肉桂` | 茶类 |
| `product_sku.sku_no` | `SJ0506` | 唯一业务编号 |
| `product_sku.bag_type` | `长泡袋` | 泡袋版型 |
| `product_sku.unit_id` | `捆` | 销售单位 |
| `product_sku.retail_price` | `18.00` | 默认价格 |
| `product_sku.inventory_policy` | `none` 或 `weak` | 按业务决定是否查库存 |
| `product_sku.main_image_url` | OSS URL | 泡袋上传生成主图 |
| `product_media.media_type` | `detail` | 详情图单独存，SKU 里只同步快捷列表 |

## 13. 从旧库迁移时字段怎么来

| 新字段 | 旧来源 | 处理规则 |
|---|---|---|
| `product_sku.id` | 新库自增或内部生成 | 只做数据库内部关联，业务上不用它 |
| 迁移对照 | `sxo_plugins_erp_product.id/group_key/goods_id` | 只写迁移对照表或迁移报告，不写进商品主表 |
| `product_spu.title` | `sxo_plugins_erp_product.title` | 相同旧 group_key 下取统一标题，作为客户可见标题 |
| `product_sku.color` | `sxo_plugins_erp_product.spec` | 只迁移清洗后的标准颜色；无法识别的写入迁移异常报告，不进主表 |
| `product_sku.sku_no` | 新生成或清洗后的 SJ 编号 | 迁移后统一为 `SJxx`，作为唯一业务编号 |
| `product_sku.retail_price` | `product_base.price`、`product.price`、`min_price` | 优先 product_base.price |
| `product_sku.cost_price` | `product_base.cost_price`、`product.cost_price` | 优先 product_base.cost_price |
| `product_spu.case_pack_qty` | `sxo_plugins_erp_product.simple_desc` | 正则解析 `20套/件`、`200个/件`，按 SPU 汇总确认 |
| `product_sku.unit_id` | `sxo_plugins_erp_product_base.unit_id` | 迁移到 `product_unit` 后关联 |
| `product_sku.main_image_url` | `main_images`、`images`、`sxo_goods.images` | 从 `product_media` 主图同步一份快捷 URL |
| `product_sku.detail_image_urls` | `main_images`、`images`、`content` | 从 `product_media` 详情图汇总一份快捷列表 |
| `product_media` | `main_images`、`images`、`content` | 拆成主图、详情图、源图、缩略图记录 |
| `product_sku.primary_category_id/category_ids` | `sxo_plugins_erp_product_category_join` | 汇总到 SKU 字段；主分类取原主分类或最常用分类 |
| `product_sku.is_listed` | `sxo_goods.is_shelves` | 没有关联时默认内部可用、前台不上架 |

## 14. 第一轮建表取舍

第一轮我建议只做这些商品相关表：

| 优先级 | 表 | 原因 |
|---:|---|---|
| 1 | `product_spu` | 解决商品组和多颜色/多规格问题 |
| 2 | `product_sku` | 商品中心核心，开单、库存、搜索都靠它 |
| 3 | `product_category` | 保留现有分类筛选 |
| 4 | `product_unit` | 单位和件套换算基础 |
| 5 | `product_alias` | 让智能体搜索/OCR 更稳 |
| 6 | `product_media` | 图片上传插件、图片管理页、主图/详情图/源图管理需要 |

`product_price_rule` 和 `product_channel_listing` 可以后置，不影响第一轮商品、库存、开单迁移。

## 15. 当前落地状态

2026-05-20 已新增脚本 `scripts/migrate_product_catalog.py`，用于创建商品中心表并从旧 ShopXO/ERP 表导入商品数据。

| 项目 | 当前结果 | 说明 |
|---|---:|---|
| 目标库 | `sjagent_core` | 使用新库账号导入；该账号只允许服务器本机访问，本地执行时通过临时 SSH 隧道连接 |
| `product_unit` | 6 | 旧单位 5 个，加了 `件` |
| `product_category` | 22 | 保留旧分类 ID |
| `product_spu` | 552 | 按旧 `group_key` 聚合，但旧 key 只进迁移对照表 |
| `product_sku` | 927 | 业务唯一编号为 `sku_no`，没有重复 |
| `product_alias` | 3590 | 编号、标题、口头名称等搜索别名 |
| `product_media` | 6403 | 主图、详情图等图片资产 |
| 迁移对照 | 1479 | 放在 `migration_product_ref`，不进入商品主表 |
| 分类缺失 SKU | 2 | 旧商品本身没有分类关联，留待人工确认 |
| 无标准颜色 SKU | 453 | 多数是泡袋/服务/辅料没有颜色；旧 `spec` 非标准颜色不写入 `color` |

导入报告：`data/migration/product_import_report.json`。

补充：前一次测试曾因旧数据库账号无 `CREATE DATABASE` 权限，把表建在旧库里；当前正式导入已经落到 `sjagent_core`。旧 ShopXO/ERP 表未删除、未覆盖。
