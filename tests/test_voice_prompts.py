import unittest

from src.services.voice_prompts import get_prompts


class VoicePromptsTests(unittest.TestCase):
    def test_wake_prompts_are_the_three_approved_replies(self) -> None:
        self.assertEqual([prompt.text for prompt in get_prompts("wake")], ["在呢", "我在", "小星在"])


if __name__ == "__main__":
    unittest.main()
