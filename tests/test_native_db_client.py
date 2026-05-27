"""Native database client smoke tests."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.engine.native_db import _clean_number_sequence_note, get_native_db_client


class NativeDBClientSmokeTest(unittest.TestCase):
    def test_native_db_client_init(self):
        client = get_native_db_client()
        self.assertEqual(client.db_config.get("name"), "sjagent_core")

    def test_number_sequence_note_repairs_unrecoverable_question_marks(self):
        self.assertEqual(
            _clean_number_sequence_note("??????? SJ1570 ??????"),
            "礼盒和泡袋统一从 SJ1570 往后自动编号",
        )
        self.assertEqual(
            _clean_number_sequence_note("礼盒和泡袋统一从 SJ1570 往后自动编号"),
            "礼盒和泡袋统一从 SJ1570 往后自动编号",
        )


if __name__ == "__main__":
    unittest.main()
