import unittest
import wave
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from src.services import voice_prompts
from src.services.voice_prompts import get_prompts


def pcm16_rms(frames: bytes) -> int:
    samples = [int.from_bytes(frames[i:i + 2], "little", signed=True) for i in range(0, len(frames), 2)]
    return int(math.sqrt(sum(sample * sample for sample in samples) / len(samples)))


def pcm16_peak(frames: bytes) -> int:
    return max(abs(int.from_bytes(frames[i:i + 2], "little", signed=True)) for i in range(0, len(frames), 2))


class VoicePromptsTests(unittest.TestCase):
    def test_wake_prompts_are_the_three_approved_replies(self) -> None:
        self.assertEqual([prompt.text for prompt in get_prompts("wake")], ["我在", "在呢", "小星在"])

    def test_wake_prompts_play_in_round_robin_order(self) -> None:
        voice_prompts.reset_prompt_cycle("wake")

        keys = [voice_prompts.pick_prompt("wake").key for _ in range(5)]

        self.assertEqual(keys, [
            "wake_wozai",
            "wake_zaine",
            "wake_xiaoxing",
            "wake_wozai",
            "wake_zaine",
        ])

    def test_prompt_wav_normalization_raises_quiet_audio_to_target_rms(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "quiet.wav"
            samples = (400).to_bytes(2, "little", signed=True) * 24000
            with wave.open(str(path), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(24000)
                target.writeframes(samples)

            voice_prompts.normalize_prompt_wav(path, target_rms=2000)

            with wave.open(str(path), "rb") as source:
                frames = source.readframes(source.getnframes())
                self.assertGreaterEqual(pcm16_rms(frames), 1900)
                self.assertLessEqual(pcm16_peak(frames), 26000)


if __name__ == "__main__":
    unittest.main()
