from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AdminProductModelContractTest(unittest.TestCase):
    def test_editor_exposes_one_spu_model_and_only_saves_changed_binding(self):
        source = (ROOT / 'admin/src/components/business/products/products-page.tsx').read_text(encoding='utf-8')
        self.assertIn('<TabsTrigger value="model">3D 模型</TabsTrigger>', source)
        self.assertIn('ProductModelEditor', source)
        self.assertIn('modelChanged', source)
        self.assertIn('model_asset_id', source)
        self.assertIn('releaseStagedModels', source)
        self.assertIn('modelUploading', source)

    def test_preview_is_lazy_and_model_upload_does_not_reuse_image_processing(self):
        path = ROOT / 'admin/src/components/business/products/product-model-editor.tsx'
        self.assertTrue(path.exists(), 'missing model editor')
        source = path.read_text(encoding='utf-8')
        self.assertIn('lazy(', source)
        self.assertIn('import("./product-model-preview")', source)
        self.assertIn('previewOpen', source)
        self.assertIn('uploadProductModel', source)
        self.assertNotIn('uploadProductImage', source)


if __name__ == '__main__':
    unittest.main()
