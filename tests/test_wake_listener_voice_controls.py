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

    def test_wake_reply_ignore_time_extends_command_window(self) -> None:
        args = types.SimpleNamespace(command_window_seconds=2.0, wake_reply_ignore_seconds=1.2)
        original = wake_listener.time.monotonic
        wake_listener.time.monotonic = lambda: 100.0
        try:
            self.assertEqual(wake_listener.command_window_deadline(args), 102.0)
            self.assertEqual(wake_listener.command_window_deadline(args, after_wake_reply=True), 103.2)
        finally:
            wake_listener.time.monotonic = original

    def test_alsa_capture_uses_nonblocking_mode_and_sleeps_on_empty_reads(self) -> None:
        class FakeAlsa(types.ModuleType):
            PCM_CAPTURE = 1
            PCM_NORMAL = 2
            PCM_NONBLOCK = 3
            PCM_FORMAT_S32_LE = 4

            def __init__(self):
                super().__init__("alsaaudio")
                self.instances = []

            class PCM:
                def __init__(self, *, type, mode, device):
                    self.type = type
                    self.mode = mode
                    self.device = device
                    self.reads = 0
                    fake_alsa.instances.append(self)

                def setchannels(self, value):
                    self.channels = value

                def setrate(self, value):
                    self.rate = value

                def setformat(self, value):
                    self.format = value

                def setperiodsize(self, value):
                    self.period_size = value

                def read(self):
                    self.reads += 1
                    if self.reads == 1:
                        return 0, b""
                    return 2, b"abcd"

        fake_alsa = FakeAlsa()
        original_alsa = sys.modules.get("alsaaudio")
        original_sleep = wake_listener.time.sleep
        sleeps = []
        sys.modules["alsaaudio"] = fake_alsa
        wake_listener.time.sleep = lambda seconds: sleeps.append(seconds)
        try:
            frames = wake_listener._capture_alsa(types.SimpleNamespace(input_device="hw:test"), period_size=480)
            self.assertEqual(next(frames), b"abcd")
            self.assertEqual(fake_alsa.instances[0].mode, fake_alsa.PCM_NONBLOCK)
            self.assertTrue(sleeps)
        finally:
            wake_listener.time.sleep = original_sleep
            if original_alsa is None:
                sys.modules.pop("alsaaudio", None)
            else:
                sys.modules["alsaaudio"] = original_alsa

    def test_handle_command_uses_device_command_api_when_configured(self) -> None:
        args = types.SimpleNamespace(
            device_command_url="http://server/api/device/voice/command",
            device_command_timeout=5,
            device_id="orangepi-xiaoxing-01",
            agent_session_id="orangepi_voice",
            output_device="",
            screen_state_url="",
            speak_results=True,
            tts_max_chars=180,
            processing_prompt=False,
        )
        original_post = wake_listener.post_device_command
        original_run = wake_listener.run_agent_command
        original_speak = wake_listener.speak_text
        original_screen = wake_listener.screen_notify
        calls = []
        screen_calls = []
        display = {"mode": "inventory_result", "title": "喜悦半斤库存", "summary": "共1项，6套", "items": []}
        try:
            wake_listener.post_device_command = lambda _args, command: {
                "ok": True,
                "speak": "喜悦半斤，百鑫红色有6套。",
                "display": display,
                "device_action": {"next_state": "idle", "listen_again": False},
            }
            wake_listener.run_agent_command = lambda *a, **k: (_ for _ in ()).throw(AssertionError("旧 Agent 不应该被调用"))
            wake_listener.speak_text = lambda _args, text, **kwargs: calls.append(text)
            wake_listener.screen_notify = lambda *a, **kwargs: screen_calls.append(kwargs)

            handled = wake_listener.handle_command(args, "喜悦半斤库存")

            self.assertTrue(handled)
            self.assertEqual(calls, ["喜悦半斤，百鑫红色有6套。"])
            self.assertIn({"role": "assistant", "text": "共1项，6套", "display": display}, screen_calls)
        finally:
            wake_listener.post_device_command = original_post
            wake_listener.run_agent_command = original_run
            wake_listener.speak_text = original_speak
            wake_listener.screen_notify = original_screen


if __name__ == "__main__":
    unittest.main()
