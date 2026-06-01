import unittest
from unittest.mock import patch


class FakeInventoryService:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return self.rows


class FakeProductService:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def search(self, keyword: str, *, limit: int = 80, listed_only: bool = False):
        self.calls.append({"keyword": keyword, "limit": limit, "listed_only": listed_only})
        return self.rows


class DeviceVoiceCommandServiceTests(unittest.TestCase):
    def test_inventory_command_returns_speak_display_and_device_action(self):
        from src.services.device_voice import build_device_voice_command_response

        service = FakeInventoryService(
            [
                {
                    "product_id": 11,
                    "产品名称": "【喜悦】半斤",
                    "【颜色】": "红色",
                    "【仓库】": "百鑫仓库",
                    "warehouse_id": 2,
                    "库存数量": 6,
                },
                {
                    "product_id": 12,
                    "产品名称": "【喜悦】半斤",
                    "【颜色】": "黄色",
                    "【仓库】": "自己店里",
                    "warehouse_id": 1,
                    "库存数量": 8,
                },
            ]
        )

        with patch("src.services.device_voice.get_inventory_service", return_value=service):
            result = build_device_voice_command_response(
                text="喜悦半斤红色库存",
                device_id="orangepi-xiaoxing-01",
                session_id="voice-session-1",
                trace_id="trace-1",
                asr_confidence=0.91,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["trace_id"], "trace-1")
        self.assertEqual(result["intent"], "inventory_query")
        self.assertEqual(result["device_action"]["next_state"], "idle")
        self.assertFalse(result["device_action"]["listen_again"])
        self.assertIn("喜悦 半斤", result["speak"])
        self.assertIn("百鑫", result["speak"])
        self.assertIn("红色有6套", result["speak"])
        self.assertIn("自己店里", result["speak"])
        self.assertEqual(result["display"]["mode"], "inventory_result")
        self.assertEqual(result["display"]["title"], "喜悦 半斤库存")
        self.assertEqual(result["display"]["summary"], "共2项，14套")
        self.assertEqual(len(result["display"]["items"]), 2)
        self.assertEqual(
            service.calls[0],
            {
                "keyword": "喜悦 半斤",
                "color": "红色",
                "warehouse_id": None,
                "only_in_stock": True,
                "limit": 100,
            },
        )

    def test_broad_inventory_command_speaks_matching_product_names(self):
        from src.services.device_voice import build_device_voice_command_response

        service = FakeInventoryService(
            [
                {
                    "product_id": 51,
                    "产品名称": "【见喜】二三两",
                    "【颜色】": "黄色",
                    "【仓库】": "百鑫仓库",
                    "warehouse_id": 2,
                    "库存数量": 5,
                },
                {
                    "product_id": 52,
                    "产品名称": "【岩彩】二三两",
                    "【颜色】": "黄色",
                    "【仓库】": "百鑫仓库",
                    "warehouse_id": 2,
                    "库存数量": 8,
                },
            ]
        )

        with patch("src.services.device_voice.get_inventory_service", return_value=service):
            result = build_device_voice_command_response(
                text="百鑫库存3两黄色的有什么",
                device_id="orangepi-xiaoxing-01",
                session_id="voice-session-broad",
                trace_id="trace-broad",
            )

        self.assertEqual(result["intent"], "inventory_query")
        self.assertEqual(service.calls[0]["keyword"], "二三两")
        self.assertEqual(service.calls[0]["color"], "黄色")
        self.assertEqual(service.calls[0]["warehouse_id"], 2)
        self.assertIn("见喜二三两黄色有5套", result["speak"])
        self.assertIn("岩彩二三两黄色有8套", result["speak"])
        self.assertEqual(result["display"]["items"][0]["product_name"], "【见喜】二三两")

    def test_broad_inventory_command_ignores_trailing_stock_question_words(self):
        from src.services.device_voice import build_device_voice_command_response

        service = FakeInventoryService(
            [
                {
                    "product_id": 61,
                    "产品名称": "【喜悦】二三两",
                    "【颜色】": "红色",
                    "【仓库】": "百鑫仓库",
                    "warehouse_id": 2,
                    "库存数量": 5,
                }
            ]
        )

        with patch("src.services.device_voice.get_inventory_service", return_value=service):
            result = build_device_voice_command_response(
                text="百鑫库存二三两有什么有库存的",
                device_id="orangepi-xiaoxing-01",
                session_id="voice-session-stock-tail",
                trace_id="trace-stock-tail",
            )

        self.assertEqual(result["intent"], "inventory_query")
        self.assertEqual(service.calls[0]["keyword"], "二三两")
        self.assertEqual(service.calls[0]["warehouse_id"], 2)
        self.assertEqual(result["display"]["query"]["product_name"], "二三两")
        self.assertIn("喜悦二三两红色有5套", result["speak"])

    def test_unclear_command_asks_user_to_repeat_without_querying_inventory(self):
        from src.services.device_voice import build_device_voice_command_response

        service = FakeInventoryService([])

        with patch("src.services.device_voice.get_inventory_service", return_value=service):
            result = build_device_voice_command_response(
                text="嗯",
                device_id="orangepi-xiaoxing-01",
                session_id="voice-session-2",
                trace_id="trace-2",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["intent"], "clarification")
        self.assertEqual(result["speak"], "没听清商品名，再说一遍。")
        self.assertTrue(result["device_action"]["listen_again"])
        self.assertEqual(result["device_action"]["next_state"], "listening")
        self.assertEqual(service.calls, [])

    def test_common_series_mishear_is_corrected_before_inventory_search(self):
        from src.services.device_voice import build_device_voice_command_response

        service = FakeInventoryService(
            [
                {
                    "product_id": 21,
                    "产品名称": "【喜悦】半斤",
                    "【颜色】": "红色",
                    "【仓库】": "百鑫仓库",
                    "warehouse_id": 2,
                    "库存数量": 6,
                }
            ]
        )

        with patch("src.services.device_voice.get_inventory_service", return_value=service):
            result = build_device_voice_command_response(
                text="喜越半斤裤存",
                device_id="orangepi-xiaoxing-01",
                session_id="voice-session-3",
                trace_id="trace-3",
            )

        self.assertEqual(service.calls[0]["keyword"], "喜悦 半斤")
        self.assertEqual(result["display"]["query"]["original_text"], "喜越半斤裤存")
        self.assertEqual(result["display"]["query"]["normalized_text"], "喜悦半斤库存")
        self.assertIn("按喜悦 半斤查询", result["display"]["summary"])

    def test_inventory_empty_result_keeps_listening_for_repeat(self):
        from src.services.device_voice import build_device_voice_command_response

        service = FakeInventoryService([])

        with patch("src.services.device_voice.get_inventory_service", return_value=service):
            result = build_device_voice_command_response(
                text="喜悦半斤库存",
                device_id="orangepi-xiaoxing-01",
                session_id="voice-session-4",
                trace_id="trace-4",
            )

        self.assertEqual(result["intent"], "inventory_query")
        self.assertEqual(result["display"]["mode"], "inventory_empty")
        self.assertTrue(result["device_action"]["listen_again"])
        self.assertEqual(result["device_action"]["next_state"], "listening")
        self.assertIn("再说一下名称", result["speak"])

    def test_price_command_returns_product_price_without_inventory_search(self):
        from src.services.device_voice import build_device_voice_command_response

        inventory_service = FakeInventoryService([])
        product_service = FakeProductService(
            [
                {
                    "product_id": 31,
                    "title": "【喜悦】半斤",
                    "color": "红色",
                    "price": "18.00",
                },
                {
                    "product_id": 32,
                    "title": "【喜悦】半斤",
                    "color": "黄色",
                    "price": "18.00",
                },
            ]
        )

        with patch("src.services.device_voice.get_inventory_service", return_value=inventory_service):
            with patch("src.services.device_voice.get_product_service", return_value=product_service):
                result = build_device_voice_command_response(
                    text="喜悦半斤多少钱",
                    device_id="orangepi-xiaoxing-01",
                    session_id="voice-session-price",
                    trace_id="trace-price",
                )

        self.assertEqual(inventory_service.calls, [])
        self.assertEqual(product_service.calls, [{"keyword": "喜悦 半斤", "limit": 50, "listed_only": False}])
        self.assertEqual(result["intent"], "price_query")
        self.assertEqual(result["device_action"]["next_state"], "idle")
        self.assertEqual(result["display"]["mode"], "price_result")
        self.assertEqual(result["display"]["title"], "喜悦 半斤价格")
        self.assertEqual(result["display"]["summary"], "售价18元")
        self.assertEqual(result["display"]["items"][0]["price_text"], "18元")
        self.assertIn("喜悦 半斤售价18元", result["speak"])

    def test_price_command_filters_color_when_color_is_spoken(self):
        from src.services.device_voice import build_device_voice_command_response

        product_service = FakeProductService(
            [
                {"product_id": 41, "title": "【喜悦】半斤", "color": "红色", "price": "18.00"},
                {"product_id": 42, "title": "【喜悦】半斤", "color": "黄色", "price": "19.00"},
            ]
        )

        with patch("src.services.device_voice.get_product_service", return_value=product_service):
            result = build_device_voice_command_response(
                text="喜悦半斤红色多少钱",
                device_id="orangepi-xiaoxing-01",
                session_id="voice-session-price-color",
                trace_id="trace-price-color",
            )

        self.assertEqual(result["display"]["summary"], "红色18元")
        self.assertEqual([item["color"] for item in result["display"]["items"]], ["红色"])
        self.assertIn("红色18元", result["speak"])

    def test_price_empty_result_keeps_listening_for_repeat(self):
        from src.services.device_voice import build_device_voice_command_response

        product_service = FakeProductService([])

        with patch("src.services.device_voice.get_product_service", return_value=product_service):
            result = build_device_voice_command_response(
                text="火星半斤多少钱",
                device_id="orangepi-xiaoxing-01",
                session_id="voice-session-price-empty",
                trace_id="trace-price-empty",
            )

        self.assertEqual(result["intent"], "price_query")
        self.assertEqual(result["display"]["mode"], "price_empty")
        self.assertTrue(result["device_action"]["listen_again"])
        self.assertEqual(result["device_action"]["next_state"], "listening")
        self.assertIn("再说一下名称", result["speak"])


class DeviceVoiceCommandApiTests(unittest.TestCase):
    def test_device_voice_command_route_wraps_service_response(self):
        from src.channels import http_api

        service_response = {
            "ok": True,
            "trace_id": "trace-api",
            "intent": "inventory_query",
            "speak": "喜悦半斤，百鑫红色有6套。",
            "display": {"mode": "inventory_result", "title": "喜悦半斤库存", "items": []},
            "device_action": {"next_state": "idle", "listen_again": False},
            "timing": {"server_ms": 1},
        }

        with patch("src.channels.http_api.build_device_voice_command_response", return_value=service_response) as mocked:
            with http_api.app.test_client() as client:
                response = client.post(
                    "/api/device/voice/command",
                    json={
                        "device_id": "orangepi-xiaoxing-01",
                        "session_id": "voice-session-api",
                        "trace_id": "trace-api",
                        "text": "喜悦半斤库存",
                        "asr_confidence": 0.88,
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"], service_response)
        mocked.assert_called_once_with(
            text="喜悦半斤库存",
            device_id="orangepi-xiaoxing-01",
            session_id="voice-session-api",
            trace_id="trace-api",
            asr_confidence=0.88,
        )


if __name__ == "__main__":
    unittest.main()
