import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTTP_API_SOURCE = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
SMOKE_SOURCE = (ROOT / "scripts" / "smoke_http_routes.py").read_text(encoding="utf-8")
README_SOURCE = (ROOT / "README.md").read_text(encoding="utf-8")


class LegacyWebRemovedContractTests(unittest.TestCase):
    def test_legacy_webui_files_are_removed(self):
        removed_files = [
            ROOT / "src" / "channels" / "http_api" / "webui.py",
            ROOT / "src" / "channels" / "http_api" / "webui_api.js",
            ROOT / "src" / "channels" / "http_api" / "webui_template.html",
            ROOT / "start_webui_background.ps1",
            ROOT / "启动北极星WebUI.bat",
        ]
        for file_path in removed_files:
            self.assertFalse(file_path.exists(), str(file_path))

    def test_flask_no_longer_registers_legacy_web_routes(self):
        self.assertNotIn('@app.route("/web"', HTTP_API_SOURCE)
        self.assertNotIn('@app.route("/login"', HTTP_API_SOURCE)
        self.assertNotIn("src.channels.http_api.webui", HTTP_API_SOURCE)
        self.assertIn('@app.route("/admin"', HTTP_API_SOURCE)

    def test_smoke_and_readme_use_react_admin_entry(self):
        self.assertNotIn('client.get("/web")', SMOKE_SOURCE)
        self.assertNotIn('client.get("/login")', SMOKE_SOURCE)
        self.assertNotIn("旧 WebUI 备用", README_SOURCE)
        self.assertNotIn("服务器域名/web", README_SOURCE)


if __name__ == "__main__":
    unittest.main()
