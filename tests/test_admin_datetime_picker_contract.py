from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AdminDateTimePickerContractTest(unittest.TestCase):
    def test_date_time_picker_uses_readable_chinese_copy(self):
        source = (ROOT / "admin" / "src" / "components" / "ui" / "date-time-picker.tsx").read_text(encoding="utf-8")

        self.assertIn("选择开单时间", source)
        self.assertIn("现在", source)
        self.assertIn("选择小时", source)
        self.assertIn("选择分钟", source)
        for mojibake in ["閫", "骞", "鏈", "鍒", "灏"]:
            self.assertNotIn(mojibake, source)


if __name__ == "__main__":
    unittest.main()
