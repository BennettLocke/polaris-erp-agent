import unittest

from scripts.smoke_http_routes import run_smoke_tests


class HttpSmokeContractTests(unittest.TestCase):
    def test_smoke_runner_checks_core_static_and_auth_routes(self):
        result = run_smoke_tests()

        self.assertEqual(result["code"], 0, result)
        checked = {item["name"] for item in result["checks"]}
        self.assertIn("health", checked)
        self.assertIn("login", checked)
        self.assertIn("web_requires_login", checked)
        self.assertIn("admin_shell", checked)
        self.assertIn("admin_assets", checked)
        self.assertIn("web_auth_me_unauthorized", checked)


if __name__ == "__main__":
    unittest.main()
