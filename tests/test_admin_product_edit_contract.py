from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminProductEditContractTest(unittest.TestCase):
    def test_react_product_editor_uses_product_service_contract(self):
        api_source = (ROOT / "admin" / "src" / "api.ts").read_text(encoding="utf-8")
        app_source = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")
        product_source = (
            ROOT / "admin" / "src" / "components" / "business" / "products" / "products-page.tsx"
        ).read_text(encoding="utf-8")
        picker_source = product_source.split("function ImageAssetPickerDialog", 1)[1].split(
            "function ProductEditorDialog", 1
        )[0]
        editor_source = product_source.split("function ProductEditorDialog", 1)[1].split(
            "function ProductToolbar", 1
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
