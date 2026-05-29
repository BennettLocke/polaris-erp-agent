from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DocumentationContractTest(unittest.TestCase):
    def test_current_upload_docs_name_native_product_store(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        handoff = (ROOT / "docs" / "bag_upload_handoff.md").read_text(encoding="utf-8")

        self.assertIn("sjagent_core 商品库", readme)
        self.assertIn("sjagent_core 商品库", handoff)
        for source in (readme, handoff):
            self.assertNotIn("写入 ERP", source)
            self.assertNotIn("上传 ERP", source)
            self.assertNotIn("查询 ERP 商品", source)
            self.assertNotIn("ERP 标题后缀", source)

    def test_local_admin_logs_are_ignored(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("admin/*.log", gitignore)

    def test_python_dependency_lock_file_exists(self):
        lock_path = ROOT / "requirements-lock.txt"
        self.assertTrue(lock_path.exists())
        lock_source = lock_path.read_text(encoding="utf-8")

        self.assertIn("langgraph==0.2.60", lock_source)
        self.assertIn("flask==3.0.0", lock_source)
        self.assertIn('openwakeword==0.6.0; platform_system == "Linux"', lock_source)
        self.assertNotIn(">=", lock_source)

    def test_ocr_runtime_dependency_is_pinned_for_server(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        lock_source = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")

        self.assertIn("rapidocr_onnxruntime", requirements)
        self.assertIn("rapidocr_onnxruntime==1.4.4", lock_source)


if __name__ == "__main__":
    unittest.main()
