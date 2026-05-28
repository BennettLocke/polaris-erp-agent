"""Contract tests for mini-program authentication routes."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTTP_API_SOURCE = (ROOT / "src" / "channels" / "http_api" / "__init__.py").read_text(encoding="utf-8")
MAIN_SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")
COMPOSE_SOURCE = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
ENV_EXAMPLE_SOURCE = (ROOT / ".env.example").read_text(encoding="utf-8")


class AuthApiContractTests(unittest.TestCase):
    def test_wechat_quick_login_accepts_miniapp_login_and_phone_codes(self):
        self.assertIn('body.get("login_code")', HTTP_API_SOURCE)
        self.assertIn('body.get("loginCode")', HTTP_API_SOURCE)
        self.assertIn('body.get("phone_code")', HTTP_API_SOURCE)
        self.assertIn('body.get("phoneCode")', HTTP_API_SOURCE)
        self.assertIn("phone_code=phone_code", HTTP_API_SOURCE)

    def test_wechat_quick_login_does_not_trust_client_openid(self):
        start = HTTP_API_SOURCE.index("def auth_wechat_quick_login")
        next_route = HTTP_API_SOURCE.index("@app.route", start + 1)
        source = HTTP_API_SOURCE[start:next_route]

        self.assertNotIn('body.get("openid")', source)
        self.assertNotIn('body.get("open_id")', source)
        self.assertIn("authcode=authcode", source)

    def test_web_session_secret_has_no_public_default(self):
        self.assertIn("SJAGENT_SECRET_KEY", HTTP_API_SOURCE)
        self.assertIn("_resolve_flask_secret_key", HTTP_API_SOURCE)
        self.assertNotIn("sjagent-webui-auth-secret", HTTP_API_SOURCE)
        self.assertIn("SESSION_COOKIE_SECURE", HTTP_API_SOURCE)

    def test_http_api_host_is_configurable_for_docker(self):
        self.assertIn("SJAGENT_HTTP_HOST", HTTP_API_SOURCE)
        self.assertIn("SJAGENT_HTTP_HOST", MAIN_SOURCE)
        self.assertIn("--http-host", MAIN_SOURCE)
        self.assertIn("run_api_server(host=host", MAIN_SOURCE)
        self.assertIn("SJAGENT_HTTP_HOST=${SJAGENT_HTTP_HOST:-0.0.0.0}", COMPOSE_SOURCE)
        self.assertIn("SJAGENT_HTTP_HOST=127.0.0.1", ENV_EXAMPLE_SOURCE)

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

    def test_native_auth_exposes_bind_phone_route(self):
        self.assertIn('@app.route("/api/auth/bind-phone", methods=["POST"])', HTTP_API_SOURCE)
        self.assertIn('body.get("phone_code")', HTTP_API_SOURCE)
        self.assertIn('body.get("phoneCode")', HTTP_API_SOURCE)
        self.assertIn("bind_native_phone", HTTP_API_SOURCE)
        self.assertIn("verify_token", HTTP_API_SOURCE)

    def test_miniapp_customer_summary_requires_current_native_user(self):
        self.assertIn('@app.route("/api/mini/customer/summary", methods=["GET"])', HTTP_API_SOURCE)
        self.assertIn("mini_customer_summary_api", HTTP_API_SOURCE)
        self.assertIn("_mini_request_user()", HTTP_API_SOURCE)
        self.assertIn("customer_summary(user)", HTTP_API_SOURCE)


if __name__ == "__main__":
    unittest.main()
