import unittest
from unittest.mock import patch


class DeviceHotwordTests(unittest.TestCase):
    def test_device_hotwords_keep_fixed_business_terms_even_when_volc_dynamic_misses_them(self):
        from src.services.device_hotwords import build_device_asr_hotwords_response

        with patch("src.services.device_hotwords.get_volc_realtime_asr_config") as mocked_config:
            mocked_config.return_value.hotwords = ("库存", "半斤", "百鑫仓库")

            result = build_device_asr_hotwords_response(device_id="orangepi-xiaoxing-01")

        self.assertEqual(result["device_id"], "orangepi-xiaoxing-01")
        self.assertGreater(result["ttl_seconds"], 0)
        self.assertIn("见喜", result["hotwords"])
        self.assertIn("喜悦", result["hotwords"])
        self.assertIn("半斤", result["hotwords"])
        self.assertEqual(result["hotwords"].count("半斤"), 1)

    def test_device_hotwords_include_price_query_words(self):
        from src.services.device_hotwords import build_device_asr_hotwords_response

        with patch("src.services.device_hotwords.get_volc_realtime_asr_config") as mocked_config:
            mocked_config.return_value.hotwords = ()

            result = build_device_asr_hotwords_response(device_id="orangepi-xiaoxing-01")

        for word in ("多少钱", "价格", "售价", "单价"):
            self.assertIn(word, result["hotwords"])

    def test_device_hotwords_route_returns_versioned_hotwords(self):
        from src.channels import http_api

        service_response = {
            "version": "device-hotwords-test",
            "device_id": "orangepi-xiaoxing-01",
            "ttl_seconds": 3600,
            "hotwords": ["见喜", "喜悦", "半斤"],
        }

        with patch("src.channels.http_api.build_device_asr_hotwords_response", return_value=service_response) as mocked:
            with http_api.app.test_client() as client:
                response = client.get("/api/device/asr/hotwords?device_id=orangepi-xiaoxing-01")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"], service_response)
        mocked.assert_called_once_with(device_id="orangepi-xiaoxing-01")


if __name__ == "__main__":
    unittest.main()
