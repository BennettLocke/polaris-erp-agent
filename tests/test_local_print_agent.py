"""Local print agent behavior tests."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import local_print_agent


class LocalPrintAgentTest(unittest.TestCase):
    def test_config_accepts_utf8_bom(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                '\ufeff{"base_url":"https://example.test","printer_name":"Test Printer"}',
                encoding="utf-8",
            )

            config = local_print_agent.load_print_agent_config(config_path, environ={})

        self.assertEqual(config["base_url"], "https://example.test")
        self.assertEqual(config["printer_name"], "Test Printer")

    def test_sumatra_print_settings_do_not_force_page_orientation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            pdf_path = tmp_path / "landscape.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n/MediaBox [0 0 595 420]\n")
            sumatra_path = tmp_path / "SumatraPDF.exe"
            sumatra_path.write_text("", encoding="utf-8")

            commands = []

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            def fake_run(cmd, **kwargs):
                commands.append(cmd)
                return Result()

            original_sumatra = local_print_agent.SUMATRA_PATH
            original_printer = local_print_agent.PRINTER_NAME
            local_print_agent.SUMATRA_PATH = sumatra_path
            local_print_agent.PRINTER_NAME = "Test Printer"
            try:
                with patch.object(local_print_agent.subprocess, "run", fake_run):
                    self.assertTrue(local_print_agent.print_pdf_windows(pdf_path))
            finally:
                local_print_agent.SUMATRA_PATH = original_sumatra
                local_print_agent.PRINTER_NAME = original_printer

        self.assertEqual(commands[0][3:5], ["-print-settings", "fit"])
        self.assertNotIn("landscape", commands[0])
        self.assertNotIn("portrait", commands[0])


if __name__ == "__main__":
    unittest.main()
