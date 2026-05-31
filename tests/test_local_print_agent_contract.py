import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_local_print_agent():
    module_path = ROOT / "scripts" / "local_print_agent.py"
    spec = importlib.util.spec_from_file_location("local_print_agent_contract", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LocalPrintAgentContractTest(unittest.TestCase):
    def test_print_agent_loads_file_config_then_environment_overrides(self):
        agent = load_local_print_agent()
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "base_url": "http://config.example",
                        "printer_name": "Config Printer",
                        "check_interval": 9,
                        "print_token": "from-config",
                        "chromium_path": "C:/Edge/config.exe",
                        "agent_name": "config-agent",
                    }
                ),
                encoding="utf-8",
            )

            config = agent.load_print_agent_config(
                config_path,
                environ={
                    "SJAGENT_PRINT_BASE_URL": "https://env.example/",
                    "SJAGENT_PRINT_CHECK_INTERVAL": "4",
                    "SJAGENT_PRINTER_NAME": "Env Printer",
                },
            )

        self.assertEqual(config["base_url"], "https://env.example")
        self.assertEqual(config["printer_name"], "Env Printer")
        self.assertEqual(config["check_interval"], 4)
        self.assertEqual(config["print_token"], "from-config")
        self.assertEqual(config["chromium_path"], "C:/Edge/config.exe")
        self.assertEqual(config["agent_name"], "config-agent")

    def test_print_agent_defaults_to_public_sjagent_domain(self):
        agent = load_local_print_agent()

        config = agent.load_print_agent_config(config_path=Path("__missing_config__.json"), environ={})

        self.assertEqual(config["base_url"], "https://ai.513sjbz.com")
        self.assertEqual(config["service_name"], "sjAutoPrint")

    def test_sjautoprint_service_files_are_kept_in_source(self):
        service_dir = ROOT / "scripts" / "sjautoprint"

        expected_files = [
            "README.md",
            "auto_print.py",
            "config.example.json",
            "install_sjautoprint.ps1",
            "uninstall_sjautoprint.ps1",
        ]
        for name in expected_files:
            self.assertTrue((service_dir / name).exists(), name)

        installer = (service_dir / "install_sjautoprint.ps1").read_text(encoding="utf-8")
        self.assertIn("sjAutoPrint", installer)
        self.assertIn("ShopXOAutoPrint", installer)
        self.assertIn("https://ai.513sjbz.com", installer)
        self.assertIn("SJAGENT_PRINT_CONFIG", installer)

        config = json.loads((service_dir / "config.example.json").read_text(encoding="utf-8"))
        self.assertEqual(config["base_url"], "https://ai.513sjbz.com")
        self.assertEqual(config["service_name"], "sjAutoPrint")


if __name__ == "__main__":
    unittest.main()
