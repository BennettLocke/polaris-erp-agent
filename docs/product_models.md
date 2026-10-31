# Product GLB Models / 商品 3D 模型

## Behavior

商品编辑的「3D 模型」页签维护整款商品的一个模型。该 SPU 的颜色 SKU 共用绑定，不建立跨商品模型库。上传不修改材质或颜色；绑定及颜色配置在保存商品时提交，取消编辑保留旧绑定和配置。颜色仅用于预览，不改写原始 GLB。

文件为贴图内嵌的 GLB 2.0，最多 50 MiB。动画起点表示开盒，终点表示合盒；多段部件动画按同一时间轴联动。无动画的模型只提供视角操作。模型及 Three.js 预览按需加载。

## Database and API

- Apply `database/schema/005_product_models.sql` **before** activating the application update. It creates two new tables only and does not migrate existing product, price or inventory data. Normal product reads do not install schema.
- `product_model_asset` owns OSS metadata and upload ownership. `product_model_binding` has one binding per SPU and a unique asset ID. An asset's first SPU ownership remains permanent after unbinding.
- `POST /api/product/models/upload`: multipart field `model`; returns an asset with `id`, `url`, `file_name`, `byte_size`, `sha256`, `animation_count`, and `materials`.
- Product detail and edit options return `model` and a separate top-level `model_config`. `POST /api/product/save` accepts optional `model_asset_id`: omitted preserves, `null` unbinds, positive integer binds. The product, binding, and config writes share one transaction.
- `DELETE /api/product/models/:id/pending` claims an uploader's never-bound asset for cleanup. A committed deletion tombstone prevents concurrent binding. Cleanup retries remain allowed if the OSS delete failed.
- Upload and pending cleanup require the existing product-maintenance (`设置`) and image-upload (`图片上传`) permissions. OSS keys and URLs are generated on the server; no arbitrary URL can be submitted as a binding.

### Binding Color Config Version 1

`product_model_binding.model_config` is nullable JSON. It belongs to the binding,
not the asset, and contains exactly this wire shape:

```typescript
model_config: {
  version: 1
  asset_id: number
  material_index: number | null
  sku_colors: Record<string, string>
  default_sku_key: string | null
  camera_direction: [number, number, number] | null
  default_pose: 'open'
} | null
```

- Submit config with the normal product save payload. `sku_colors` keys and a
  non-null `default_sku_key` reference that payload's `base` keys, such as `"123"`
  or `"new_0"`. After SKU writes, the backend stores real SKU ID strings. Numeric
  base keys may only update SKUs owned by the saved SPU. Unknown config fields,
  missing required fields, and unknown payload SKU keys are rejected.
- `asset_id` must exactly equal the bound positive integer asset ID. A non-null
  material index must be an integer found in the asset's original
  `materials[].index`; array offsets, booleans, and runtime UUIDs are not indices.
- Colors must be six-digit `#RRGGBB` hex strings; lowercase input is normalized
  to uppercase. Partial color maps and a null material index are accepted, so
  replacement can preserve colors while awaiting material selection. No color
  names are cached: current names remain in product SKU/group data.
- Camera direction must be null or a finite, nonzero, three-number JSON array.
  Booleans are rejected. Scale-first normalization with `math.hypot` handles huge
  and subnormal finite vectors without overflow. The only default pose is `open`.
- Omit `model_config` to preserve config. Replacing the model with config omitted
  retains same-SPU SKU hexes and the valid default key, updates `asset_id`, resets
  material and camera to null, and sets pose to `open`. Explicit null resets only
  config; unbinding clears the binding and its config. Config without a bound
  asset is rejected, except null, which is a no-op on an unbound product.
- Every normal product save also normalizes/prunes existing colors against live,
  nondeleted SKUs. Reads prune too. An invalid/unconfigured default falls back
  to the first configured live SKU in product order (`color ASC, id ASC`), or
  null when there are no configured colors. Omission of a SKU from `base` is not
  a deletion in the existing product API.
- Save-time pruning uses a current locking SKU read, not the transaction's older
  repeatable-read snapshot. Saves acquire SPU, binding, then SKU write/pruning
  locks in that order, preserving colors added by another committed save even
  when the ordinary save established its snapshot before that addition.
- Invalid submitted config raises `ValueError` and the API returns HTTP 400;
  title, SKUs, binding, config and any first asset ownership claim all roll back.
  Config-only model updates still require product-maintenance (`设置`) permission
  and forward operator context, but editing an already-bound asset's config
  does not require its original uploader or image-upload permission.
- `/api/mini/goods/detail` exposes `model` with only `id`, public `url`,
  `animation_count`, and `materials` (`index`/`name` only), plus `model_config` and
  legacy `model_url`/`has_model`. Config colors/defaults include only currently
  visible, active, listed SKU IDs, in visible product order. OSS keys, checksums,
  timestamps, and upload ownership metadata are excluded from the public model.
  List SQL is unchanged; no per-item model query, full config, or model metadata
  is added to lists.

### Existing-Table Migration

Changing `005_product_models.sql` only covers fresh installs. Before starting
this backend on an existing installation, explicitly run
`scripts/migrate_product_model_config.py`. It checks `INFORMATION_SCHEMA.COLUMNS`
and adds only the missing nullable JSON column. It never rewrites bindings or
config data, and is never called during application startup or normal saves.
MySQL 5.7 syntax is used; MariaDB's nullable LONGTEXT JSON representation is also
accepted. Incompatible existing column types/nullability stop the migration.
DDL may acquire a metadata lock; use the existing backup/deployment procedure.

For the disposable local database, run from the release checkout:

```powershell
C:\Python314\python.exe scripts/migrate_product_model_config.py --host 127.0.0.1 --port 13319 --database sjagent_model_test --user root
```

`python -m scripts.migrate_product_model_config` is supported too. For a real
installation, explicitly select the intended connection using the existing
schema tool's environment variables or CLI flags. Do not put passwords in shell
history. Reruns report `already present; unchanged`; do not drop the column as
a rollback, since that would destroy saved config data.

## OSS and Deployment

模型以 `product_models/YYYYMMDD/<uuid>.glb` 保存，Content-Type 为 `model/gltf-binary`。使用现有后端 OSS 配置，密钥不会交给浏览器。无需图片处理、裁剪或重新烘焙。

1. Back up the target database using the existing deployment procedure. Review `005_product_models.sql`, then apply only this schema with the repository schema tool's `--only 005_product_models` option. Do not run unrelated initialization or seed endpoints.
2. Include `scripts/nginx/product-model-upload.conf` in the existing HTTPS server block and validate Nginx before reload. The model route allows 51 MiB multipart bodies; other upload limits remain unchanged.
3. `SJAGENT_MAX_MODEL_UPLOAD_BYTES` defaults to `52428800`. Keep frontend, application and proxy limits aligned if changing it.
4. Preserve existing OSS CORS rules. Add GET/HEAD access for the exact admin origin and development origin. Verify `Access-Control-Allow-Origin` and `Vary: Origin` at the actual CDN/model URL, not only at the bucket endpoint. Cross-origin preview requests omit credentials.
5. Build the admin bundle and deploy it with the backend/schema change. No GLB files, temporary databases, credentials or local preview fixtures belong in Git.

The production admin origin is `https://ai.513sjbz.com`. On 2026-10-31 its exact GET/HEAD origin was added while preserving existing bucket rules, including the development preview origins. The CORS response varies by origin. Verify the actual CDN response during deployment; this is an operational setting, not an automatic startup action.

## Verification

```powershell
python -m pytest tests/test_product_models.py tests/test_product_model_api.py tests/test_native_product_models.py tests/test_admin_product_model_contract.py -q
C:\Python314\python.exe -m pytest tests/test_product_model_config.py tests/test_product_model_config_migration.py tests/test_miniapp_product_listing_contract.py -q
$env:SJAGENT_RUN_MODEL_MYSQL_TESTS='1'
C:\Python314\python.exe -m pytest tests/test_product_model_mysql_integration.py -q
node --test admin/src/components/business/products/product-model-upload.test.cjs admin/src/components/business/products/product-model-preview.test.cjs
```

The opt-in `tests/test_product_model_mysql_integration.py` accepts only the disposable database `sjagent_model_test` at `127.0.0.1:13319`; it never uses production connection settings. Set `SJAGENT_RUN_MODEL_MYSQL_TESTS=1` to run against that prepared instance. It verifies real product saves, new-key-to-SKU mapping, config replacement/reset, visible mini colors/defaults, pruning deleted colors, migration rerun preservation, two-color sharing, replacement, unbinding, cross-SPU rejection, cleanup retry and rollback after a later save failure or invalid config. Tests create and remove only their own product/asset fixtures; existing demo bindings remain in place.

`tests/test_admin_product_models_browser.cjs` requires the isolated `model_demo` environment, a local desktop GLB and Playwright. It refuses a business account. It verifies a real OSS upload, actual cross-origin WebGL rendering, animation, no eager model download, cancellation cleanup and desktop/mobile framing. Test screenshots and fixtures stay in ignored scratch directories.

The version-one config supports one recolorable original material and per-SKU hexes. It does not implement multiple recolorable material slots, cross-product asset reuse, a mini-program viewer, or automatic server deployment.

### Verification Boundaries

- Targeted backend/service regressions, real disposable InnoDB transactions, frontend interaction tests, build and actual OSS/WebGL checks were run. The disposable database and local preview are not the production system.
- The release is based on the latest production revision, including existing sales, price memory, inventory and image-correction changes. Model/backend regressions, frontend interaction tests and the production build were rerun after integrating that baseline.
- The existing admin toolchain reports eight dependency audit advisories, including Vite/build-tool issues. The new Three.js dependency is not among the reported packages. No unrelated dependency upgrade or audit fix was applied here; the development server binds only to loopback.
- Unknown upload responses or storage failures beyond bounded cleanup retries may leave unbound assets. Their database records/tombstones remain available for operator cleanup; no permanent cleanup scheduler is introduced in this release.
