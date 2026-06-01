import unittest
from unittest.mock import patch

from src.channels.http_api.screen import get_screen_html
from src.services import screen_state


class ScreenStateDisplayTests(unittest.TestCase):
    def setUp(self):
        screen_state.update_screen_state(status="idle", reset=True)

    def test_update_screen_state_keeps_structured_display_payload(self):
        display = {
            "mode": "inventory_result",
            "title": "喜悦半斤库存",
            "summary": "共2项，14套",
            "items": [{"warehouse": "百鑫仓库", "color": "红色", "qty": 6}],
        }

        state = screen_state.update_screen_state(
            status="talk",
            role="assistant",
            text="喜悦半斤，百鑫红色有6套。",
            display=display,
            source="voice-device",
        )

        self.assertEqual(state["display"], display)
        self.assertEqual(state["latest"]["display"], display)

    def test_notify_screen_state_posts_display_payload(self):
        display = {"mode": "inventory_result", "title": "喜悦半斤库存", "items": []}

        with patch("src.services.screen_state.requests.post") as mocked_post:
            mocked_post.return_value.status_code = 200

            ok = screen_state.notify_screen_state(
                "talk",
                role="assistant",
                text="喜悦半斤库存",
                display=display,
                url="http://screen/api/screen/state",
            )

        self.assertTrue(ok)
        self.assertEqual(mocked_post.call_args.kwargs["json"]["display"], display)

    def test_screen_page_renders_structured_inventory_display(self):
        html = get_screen_html()

        self.assertIn("function renderDisplayPayload", html)
        self.assertIn("const display = state.display || latest.display || {}", html)
        self.assertIn("inventory-display", html)
        self.assertIn("item.warehouse_label || item.warehouse", html)
        self.assertIn("item.product_name", html)
        self.assertIn("item.color", html)
        self.assertIn("item.qty", html)

    def test_screen_page_renders_structured_price_display(self):
        html = get_screen_html()

        self.assertIn('mode !== "price_result"', html)
        self.assertIn('mode !== "price_empty"', html)
        self.assertIn("price-display", html)
        self.assertIn("item.price_text", html)


if __name__ == "__main__":
    unittest.main()
