import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_admin_dist import extract_admin_asset_paths, verify_admin_dist


ROOT = Path(__file__).resolve().parents[1]


class AdminDistContractTests(unittest.TestCase):
    def test_current_admin_dist_index_references_existing_assets(self):
        result = verify_admin_dist(ROOT)

        self.assertEqual(result["code"], 0, result)
        self.assertGreaterEqual(len(result["assets"]), 2)
        self.assertTrue(all(path.startswith("/admin/assets/") for path in result["assets"]))

    def test_check_admin_dist_reports_missing_referenced_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "src" / "channels" / "http_api" / "admin_dist"
            assets = dist / "assets"
            assets.mkdir(parents=True)
            (assets / "ok.js").write_text("console.log('ok')", encoding="utf-8")
            (dist / "index.html").write_text(
                '<script type="module" src="/admin/assets/ok.js"></script>'
                '<link rel="stylesheet" href="/admin/assets/missing.css">',
                encoding="utf-8",
            )

            result = verify_admin_dist(root)

        self.assertEqual(result["code"], 1)
        self.assertIn("/admin/assets/missing.css", result["missing"])

    def test_extract_admin_asset_paths_ignores_external_urls(self):
        html = (
            '<script src="/admin/assets/app.js"></script>'
            '<link href="https://cdn.example.com/vendor.css">'
            '<img src="/uploads/logo.png">'
        )

        self.assertEqual(extract_admin_asset_paths(html), ["/admin/assets/app.js"])

    def test_admin_build_runs_dist_check(self):
        package = json.loads((ROOT / "admin" / "package.json").read_text(encoding="utf-8"))
        scripts = package.get("scripts") or {}

        self.assertIn("check:dist", scripts)
        self.assertIn("python3 ../scripts/check_admin_dist.py", scripts["check:dist"])
        self.assertIn("npm run check:dist", scripts["build"])


if __name__ == "__main__":
    unittest.main()
