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

    def test_native_auth_exposes_change_password_route(self):
        self.assertIn('@app.route("/api/auth/change-password", methods=["POST"])', HTTP_API_SOURCE)
        self.assertIn("change_native_password", HTTP_API_SOURCE)
        self.assertIn('body.get("old_password")', HTTP_API_SOURCE)
        self.assertIn('body.get("new_password")', HTTP_API_SOURCE)

    def test_native_auth_exposes_register_route(self):
        self.assertIn('@app.route("/api/auth/register", methods=["POST"])', HTTP_API_SOURCE)
        self.assertIn("native_register", HTTP_API_SOURCE)
        self.assertIn('body.get("display_name")', HTTP_API_SOURCE)
        self.assertIn('body.get("client_type")', HTTP_API_SOURCE)

    def test_native_auth_me_post_updates_display_username(self):
        self.assertIn('@app.route("/api/auth/me", methods=["GET", "POST"])', HTTP_API_SOURCE)
        self.assertIn('request.method == "POST"', HTTP_API_SOURCE)
        self.assertIn("update_native_profile", HTTP_API_SOURCE)
        self.assertIn('body.get("display_name")', HTTP_API_SOURCE)

    def test_miniapp_customer_summary_requires_current_native_user(self):
        self.assertIn('@app.route("/api/mini/customer/summary", methods=["GET"])', HTTP_API_SOURCE)
        self.assertIn("mini_customer_summary_api", HTTP_API_SOURCE)
        self.assertIn("_mini_request_user()", HTTP_API_SOURCE)
        self.assertIn("customer_summary(user)", HTTP_API_SOURCE)


if __name__ == "__main__":
    unittest.main()
