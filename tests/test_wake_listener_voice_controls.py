import sys
import types
import unittest

if "audioop" not in sys.modules:
    audioop_stub = types.ModuleType("audioop")
    audioop_stub.rms = lambda *args, **kwargs: 0
    sys.modules["audioop"] = audioop_stub

from scripts import wake_listener


class WakeListenerVoiceControlTests(unittest.TestCase):
    def test_cancel_phrases_close_command_window(self) -> None:
        for phrase in ["没事了", "不用了", "取消", "算了", "不查了", "不用查了"]:
            with self.subTest(phrase=phrase):
                self.assertTrue(wake_listener.is_cancel_voice_command(phrase))
                self.assertFalse(wake_listener.should_continue_command_window(phrase))

    def test_short_fillers_still_keep_waiting(self) -> None:
        for phrase in ["嗯", "好", "行"]:
            with self.subTest(phrase=phrase):
                self.assertTrue(wake_listener.is_ignorable_voice_command(phrase))
                self.assertFalse(wake_listener.should_continue_command_window(phrase))


if __name__ == "__main__":
    unittest.main()
