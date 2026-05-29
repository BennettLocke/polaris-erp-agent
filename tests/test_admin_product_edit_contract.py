from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminProductEditContractTest(unittest.TestCase):
    def test_product_page_has_create_product_entrypoint(self):
        product_source = (
            ROOT / "admin" / "src" / "components" / "business" / "products" / "products-page.tsx"
        ).read_text(encoding="utf-8")
        toolbar_source = product_source.split("function ProductToolbar", 1)[1].split(
            "function ProductQuickFilters", 1
        )[0]
        editor_source = product_source.split("function ProductEditorDialog", 1)[1].split(
            "function ProductToolbar", 1
        )[0]

        self.assertIn("createProductDraft", product_source)
        self.assertIn("onCreate", toolbar_source)
        self.assertIn("新增商品", toolbar_source)
        self.assertIn("<Plus data-icon=\"inline-start\" />", toolbar_source)
        self.assertIn("const isCreate = open && !productId", editor_source)
        self.assertIn('{isCreate ? "新增商品" : "编辑商品"}', editor_source)
        self.assertIn("id: isCreate ? undefined : productId || undefined", editor_source)

    def test_react_product_editor_uses_product_service_contract(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        product_source = (
            ROOT / "admin" / "src" / "components" / "business" / "products" / "products-page.tsx"
        ).read_text(encoding="utf-8")
        http_source = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
        picker_source = product_source.split("function ImageAssetPickerDialog", 1)[1].split(
            "function ProductEditorDialog", 1
        )[0]
        editor_source = product_source.split("function ProductEditorDialog", 1)[1].split(
            "function ProductToolbar", 1
        )[0]
        crop_source = product_source.split("function SquareImageCropDialog", 1)[1].split(
            "function ProductEditorDialog", 1
        )[0]
        type_source = (ROOT / "admin" / "src" / "types.ts").read_text(encoding="utf-8")
        style_source = (ROOT / "admin" / "src" / "styles.css").read_text(encoding="utf-8")

        self.assertIn("productDetail", api_source)
        self.assertIn("/api/product/${id}", api_source)
        self.assertIn("productOptions", api_source)
        self.assertIn("/api/product/options", api_source)
        self.assertIn("saveProduct", api_source)
        self.assertIn("/api/product/save", api_source)
        self.assertIn("uploadProductImage", api_source)
        self.assertIn("/api/product/upload", api_source)
        self.assertIn("cropProductImageSquare", api_source)
        self.assertIn("/api/product/crop-square", api_source)

        self.assertIn("ProductEditorDialog", product_source)
        self.assertIn("ImageAssetPickerDialog", product_source)
        self.assertIn("DialogContent", product_source)
        self.assertIn("TabsContent", product_source)
        self.assertIn("FieldGroup", product_source)
        self.assertIn("SelectTrigger", product_source)
        self.assertIn("Table", product_source)
        self.assertIn("Switch", product_source)
        self.assertIn("ScrollArea", product_source)
        self.assertIn("product-spec-table", product_source)
        self.assertIn("asset-picker-search", product_source)
        self.assertIn(".asset-picker-dialog .asset-picker-card.sj-button", style_source)
        self.assertIn("width: 100%;", style_source)
        self.assertIn("display: grid;", style_source)
        self.assertIn(".asset-picker-dialog .asset-picker-card img", style_source)
        self.assertIn("display: block;", style_source)
        self.assertIn("SquareImageCropDialog", product_source)
        self.assertIn("ImageCropTarget", product_source)
        self.assertIn("SquareCropResult", product_source)
        self.assertIn("pendingSquareCrop", editor_source)
        self.assertIn('pickerTarget.type !== "detail"', editor_source)
        self.assertIn("confirmSquareCrop", editor_source)
        self.assertIn("cropProductImageSquare", editor_source)
        self.assertIn("ApiError", product_source)
        self.assertIn("后台裁切接口还没生效", editor_source)
        self.assertIn("err instanceof ApiError && err.status === 404", editor_source)
        self.assertIn("sourceUrl", product_source)
        self.assertIn("canvas.toBlob", product_source)
        self.assertIn("onPointerDown", product_source)
        self.assertIn("onPointerMove", product_source)
        self.assertIn("zoomCropWithWheel", crop_source)
        self.assertIn("onWheel={zoomCropWithWheel}", crop_source)
        self.assertIn("event.preventDefault()", crop_source)
        self.assertIn("offsetRef", crop_source)
        self.assertIn("zoomRef", crop_source)
        self.assertNotIn('type="range"', crop_source)
        self.assertNotIn("square-crop-controls", crop_source)
        self.assertIn("square-crop-stage", product_source)
        self.assertIn(".square-crop-dialog", style_source)
        self.assertIn(".square-crop-stage", style_source)
        self.assertNotIn(".square-crop-controls", style_source)
        self.assertIn('re.compile(r"^/api/product/crop-square$")', http_source)
        self.assertIn('@app.route("/api/product/crop-square"', http_source)
        self.assertIn("def product_crop_square_api", http_source)
        self.assertIn("Image.open", http_source)
        self.assertIn("Image.Resampling.LANCZOS", http_source)
        self.assertIn("source_size", http_source)
        self.assertIn("未绑定", product_source)
        self.assertIn("本产品图片", product_source)
        self.assertIn("全部图片", product_source)
        self.assertIn("main_images", product_source)
        self.assertIn("content", product_source)
        self.assertIn("product_category_id", product_source)
        self.assertIn("purchase_policy", product_source)
        self.assertIn("base[", product_source)
        self.assertIn("onWheel={inputNoWheel}", product_source)
        self.assertIn("stockItem", editor_source)
        self.assertIn("setStockItem", editor_source)
        self.assertIn("is_stock_item: stockValue", editor_source)
        self.assertIn("库存规则", editor_source)
        self.assertNotIn("规格库存规则", editor_source)
        spec_table_source = editor_source.split('<Table className="product-spec-table">', 1)[1].split(
            "</Table>", 1
        )[0]
        self.assertNotIn("Switch checked={Number(spec.is_stock_item", spec_table_source)
        self.assertNotIn("is_stock_item", spec_table_source)
        self.assertIn('from "./components/business/products"', app_source)
        self.assertNotIn("<select", editor_source)
        self.assertNotIn("<input", editor_source)
        self.assertNotIn("<button", editor_source)
        self.assertNotIn("ghost-action", editor_source)
        self.assertNotIn("primary-action", editor_source)
        self.assertNotIn("segmented-control", picker_source)
        self.assertNotIn("input-with-button", picker_source)

        self.assertIn("ProductOptions", type_source)
        self.assertIn("ProductSavePayload", type_source)


if __name__ == "__main__":
    unittest.main()
