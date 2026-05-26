"""Contract tests for mini-program authentication routes."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTTP_API_SOURCE = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")


class AuthApiContractTests(unittest.TestCase):
    def test_wechat_quick_login_accepts_miniapp_login_and_phone_codes(self):
        self.assertIn('body.get("login_code")', HTTP_API_SOURCE)
        self.assertIn('body.get("loginCode")', HTTP_API_SOURCE)
        self.assertIn('body.get("phone_code")', HTTP_API_SOURCE)
        self.assertIn('body.get("phoneCode")', HTTP_API_SOURCE)
        self.assertIn("phone_code=phone_code", HTTP_API_SOURCE)


if __name__ == "__main__":
    unittest.main()
