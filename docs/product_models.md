# Product GLB Models / 商品 3D 模型

## Behavior

商品编辑的「3D 模型」页签维护整款商品的一个模型。该 SPU 的颜色 SKU 共用绑定，不建立跨商品模型库。上传、预览、更换、解除绑定均不修改材质或颜色；绑定在保存商品时提交，取消编辑保留旧绑定。

文件为贴图内嵌的 GLB 2.0，最多 50 MiB。动画起点表示开盒，终点表示合盒；多段部件动画按同一时间轴联动。无动画的模型只提供视角操作。模型及 Three.js 预览按需加载。

## Database and API

- Apply `database/schema/005_product_models.sql` **before** activating the application update. It creates two new tables only and does not migrate existing product, price or inventory data. Normal product reads do not install schema.
- `product_model_asset` owns OSS metadata and upload ownership. `product_model_binding` has one binding per SPU and a unique asset ID. An asset's first SPU ownership remains permanent after unbinding.
- `POST /api/product/models/upload`: multipart field `model`; returns an asset with `id`, `url`, `file_name`, `byte_size`, `sha256`, `animation_count`, and `materials`.
- Product detail and edit options return `model`. `POST /api/product/save` accepts optional `model_asset_id`: omitted preserves, `null` unbinds, positive integer binds. The product write and binding share one transaction.
- `DELETE /api/product/models/:id/pending` claims an uploader's never-bound asset for cleanup. A committed deletion tombstone prevents concurrent binding. Cleanup retries remain allowed if the OSS delete failed.
- Upload and pending cleanup require the existing product-maintenance (`设置`) and image-upload (`图片上传`) permissions. OSS keys and URLs are generated on the server; no arbitrary URL can be submitted as a binding.

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
node --test admin/src/components/business/products/product-model-upload.test.cjs admin/src/components/business/products/product-model-preview.test.cjs
```

The opt-in `tests/test_product_model_mysql_integration.py` accepts only the disposable database `sjagent_model_test` at `127.0.0.1:13319`; it never uses production connection settings. Set `SJAGENT_RUN_MODEL_MYSQL_TESTS=1` to run against that prepared instance. It verifies real product saves, two-color sharing, replacement, unbinding, cross-SPU rejection, cleanup retry and rollback after a later save failure.

`tests/test_admin_product_models_browser.cjs` requires the isolated `model_demo` environment, a local desktop GLB and Playwright. It refuses a business account. It verifies a real OSS upload, actual cross-origin WebGL rendering, animation, no eager model download, cancellation cleanup and desktop/mobile framing. Test screenshots and fixtures stay in ignored scratch directories.

The first release does not implement per-color material editing, cross-product asset reuse, a mini-program viewer, or automatic server deployment.

### Verification Boundaries

- Targeted backend/service regressions, real disposable InnoDB transactions, frontend interaction tests, build and actual OSS/WebGL checks were run. The disposable database and local preview are not the production system.
- The release is based on the latest production revision, including existing sales, price memory, inventory and image-correction changes. Model/backend regressions, frontend interaction tests and the production build were rerun after integrating that baseline.
- The existing admin toolchain reports eight dependency audit advisories, including Vite/build-tool issues. The new Three.js dependency is not among the reported packages. No unrelated dependency upgrade or audit fix was applied here; the development server binds only to loopback.
- Unknown upload responses or storage failures beyond bounded cleanup retries may leave unbound assets. Their database records/tombstones remain available for operator cleanup; no permanent cleanup scheduler is introduced in this release.
