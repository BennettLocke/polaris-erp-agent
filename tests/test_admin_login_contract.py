from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = (ROOT / "admin" / "src" / "App.tsx").read_text(encoding="utf-8")


class AdminLoginContractTests(unittest.TestCase):
    def test_successful_login_clears_login_state(self):
        self.assertIn("function handleLogin(nextUser: AuthUser)", APP_SOURCE)
        self.assertIn("setUser(nextUser);", APP_SOURCE)
        self.assertIn("setNeedsLogin(false);", APP_SOURCE)
        self.assertIn("<LoginView onLogin={handleLogin} />", APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
