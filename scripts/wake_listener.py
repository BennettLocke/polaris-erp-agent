"""Simple wake-word listener for the Orange Pi desktop robot.

Record short chunks from INMP441, send speech-like chunks to ASR, and play a
cached wake prompt when the transcript resembles
"小星".
"""
from __future__ import annotations

import argparse
import audioop
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from array import array

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.aliyun_short_asr import recognize_pcm16 as recognize_pcm16_aliyun  # noqa: E402
from src.services.mimo_tts import synthesize  # noqa: E402
from src.services.volc_tts import synthesize_stream as synthesize_volc_stream  # noqa: E402
from src.services.volc_realtime_asr import VolcStreamingRecognizer  # noqa: E402
from src.services.volc_realtime_asr import recognize_pcm16 as recognize_pcm16_volc  # noqa: E402
from src.services.voice_prompts import ensure_group, play_file, play_prompt  # noqa: E402


WAKE_WORDS = {
    "小星",
    "小新",
    "小兴",
    "小鑫",
    "小行",
    "小型",
    "小心",
    "小幸",
    "小明",
    "小鸣",
    "小名",
    "小红",
    "小机",
    "小鸡",
    "小宁",
    "小拧",
    "晓宁",
    "晓星",
    "晓新",
}
LEARNED_WAKE_PATH = ROOT / "data" / "generated" / "voice" / "wake_words.json"
IGNORABLE_VOICE_COMMANDS = {
    "\u55ef",
    "\u554a",
    "\u989d",
    "\u5443",
    "\u54e6",
    "\u597d",
    "\u597d\u7684",
    "\u884c",
    "\u53ef\u4ee5",
}
INVENTORY_QUERY_MISHEARS = (
    "\u7ec3\u4e60",
    "\u8054\u7cfb",
    "\u8fde\u7eed",
    "\u7ec3\u7ec3",
    "\u641c\u7d22",
)


def load_learned_wake_words() -> set[str]:
    try:
        data = json.loads(LEARNED_WAKE_PATH.read_text(encoding="utf-8"))
        words = data.get("words", []) if isinstance(data, dict) else data
        return {str(word).strip() for word in words if str(word).strip()}
    except FileNotFoundError:
        return set()
    except Exception as exc:
        print(f"WAKE_LEARN_LOAD_ERROR {exc}", flush=True)
        return set()


def all_wake_words() -> set[str]:
    return WAKE_WORDS | load_learned_wake_words()


def learn_wake_variants(text: str) -> None:
    candidates = set(re.findall(r"[小晓][\u4e00-\u9fff]", text or ""))
    candidates = {word for word in candidates if 2 <= len(word) <= 3}
    if not candidates:
        return
    existing = load_learned_wake_words()
    updated = sorted((existing | candidates) - WAKE_WORDS)
    if sorted(existing) == updated:
        return
    try:
        LEARNED_WAKE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEARNED_WAKE_PATH.write_text(json.dumps({"words": updated}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"WAKE_LEARNED {','.join(sorted(candidates))}", flush=True)
    except Exception as exc:
        print(f"WAKE_LEARN_SAVE_ERROR {exc}", flush=True)


def normalize_text(text: str) -> str:
    return re.sub(r"[\s，。！？、,.!?]+", "", text or "")


def is_wake_text(text: str) -> bool:
    normalized = normalize_text(text)
    return any(word in normalized for word in all_wake_words())


def strip_wake_words(text: str) -> str:
    value = text or ""
    for word in sorted(all_wake_words(), key=len, reverse=True):
        value = value.replace(word, "")
    value = re.sub(r"^[，。！？、,.!?\s]+", "", value)
    return value.strip()


def normalize_command_text(text: str) -> str:
    value = (text or "").strip()
    for word in sorted(all_wake_words(), key=len, reverse=True):
        value = re.sub(rf"^{re.escape(word)}[，。！？、,.!?\s]*", "", value)
    value = re.sub(r"^(帮我|帮忙|麻烦|请|去|给我|你去|帮我去)", "", value).strip()
    if "\u5e93\u5b58" in value:
        for misheard in INVENTORY_QUERY_MISHEARS:
            if value.startswith(misheard):
                value = "\u67e5\u8be2" + value[len(misheard) :]
                break
    return value


def is_ignorable_voice_command(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized in IGNORABLE_VOICE_COMMANDS or len(normalized) <= 1


def spoken_text(text: str, *, max_chars: int = 180) -> str:
    value = (text or "").strip()
    value = re.sub(r"https?://\S+", "", value)
    value = value.replace("```", "")
    lines = []
    for line in value.splitlines():
        clean = line.strip()
        if not clean or set(clean) <= {"|", "-", ":", " "}:
            continue
        clean = clean.strip("|").replace("|", "，")
        clean = re.sub(r"\s+", " ", clean)
        lines.append(clean)
    value = "。".join(lines) if lines else value
    value = re.sub(r"[#*_`>]+", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > max_chars:
        value = value[:max_chars].rstrip("，。；; ") + "。后面内容我已经查到，可以在网页里看完整结果。"
    return value or "处理完成。"


_AGENT = None


def run_agent_command(command: str, *, session_id: str) -> str:
    global _AGENT
    if _AGENT is None:
        from src.core.agent import Agent

        _AGENT = Agent()
    return _AGENT.run(command, user_id="orangepi_voice", session_id=session_id)


def record_wav(path: Path, *, device: str, seconds: float) -> None:
    subprocess.run(
        [
            "arecord",
            "-q",
            "-D",
            device,
            "-f",
            "S32_LE",
            "-r",
            "48000",
            "-c",
            "2",
            "-d",
            str(max(1, math.ceil(seconds))),
            str(path),
        ],
        check=True,
    )


def wav_to_pcm16(path: Path, *, gain: float = 1.0) -> tuple[bytes, int]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if channels >= 2:
        # INMP441 is wired to left channel (L/R -> GND).
        frames = audioop.tomono(frames, width, 1, 0)
        channels = 1
    if rate != 16000:
        frames, _ = audioop.ratecv(frames, width, channels, rate, 16000, None)
        rate = 16000
    if width != 2:
        frames = audioop.lin2lin(frames, width, 2)
        width = 2
    if gain and gain != 1.0:
        frames = audioop.mul(frames, width, gain)
    avg = audioop.avg(frames, width)
    if avg:
        frames = audioop.bias(frames, width, -avg)
    return frames, activity_rms(frames, width, rate)


def activity_rms(frames: bytes, width: int, rate: int, *, window_ms: int = 200) -> int:
    """Use short-window peak RMS so quick wake words do not get averaged away."""
    window_bytes = max(width, int(rate * window_ms / 1000) * width)
    if len(frames) <= window_bytes:
        return audioop.rms(frames, width)
    values = [
        audioop.rms(frames[offset : offset + window_bytes], width)
        for offset in range(0, len(frames) - window_bytes + 1, window_bytes)
    ]
    return max(values) if values else audioop.rms(frames, width)


def raw_to_pcm16(raw: bytes, *, gain: float, state) -> tuple[bytes, int, object]:
    """Convert INMP441 S32_LE stereo 48k raw bytes to debiased PCM16 16k mono."""
    width = 4
    frames = audioop.tomono(raw, width, 1, 0)
    frames, state = audioop.ratecv(frames, width, 1, 48000, 16000, state)
    frames = audioop.lin2lin(frames, width, 2)
    if gain and gain != 1.0:
        frames = audioop.mul(frames, 2, gain)
    avg = audioop.avg(frames, 2)
    if avg:
        frames = audioop.bias(frames, 2, -avg)
    return frames, audioop.rms(frames, 2), state


def _normalize_vad_frame(pcm: bytes, frame_ms: int) -> bytes:
    expected = int(16000 * frame_ms / 1000) * 2
    if len(pcm) == expected:
        return pcm
    if len(pcm) > expected:
        return pcm[:expected]
    return pcm + (b"\x00" * (expected - len(pcm)))


def _open_webrtc_vad(args):
    if not args.vad_use_webrtc:
        return None
    try:
        import webrtcvad
    except ImportError:
        print("VAD_WARNING webrtcvad is not installed; falling back to energy VAD", flush=True)
        return None
    return webrtcvad.Vad(args.vad_mode)


class LocalWakeDetector:
    def process(self, pcm16: bytes) -> bool:
        return False


class PorcupineWakeDetector(LocalWakeDetector):
    def __init__(self, args) -> None:
        import pvporcupine

        access_key = args.porcupine_access_key
        if not access_key:
            raise RuntimeError("Porcupine needs --porcupine-access-key or PICOVOICE_ACCESS_KEY")
        keyword_paths = [p for p in args.porcupine_keyword_path if p]
        if not keyword_paths:
            raise RuntimeError("Porcupine needs --porcupine-keyword-path /path/to/xiaoxing.ppn")
        self.engine = pvporcupine.create(
            access_key=access_key,
            keyword_paths=keyword_paths,
            sensitivities=[args.porcupine_sensitivity] * len(keyword_paths),
        )
        self.frame_length = self.engine.frame_length
        self.buffer = array("h")
        print(f"local_wake=porcupine frame_length={self.frame_length}", flush=True)

    def process(self, pcm16: bytes) -> bool:
        samples = array("h")
        samples.frombytes(pcm16)
        self.buffer.extend(samples)
        detected = False
        while len(self.buffer) >= self.frame_length:
            frame = self.buffer[: self.frame_length]
            del self.buffer[: self.frame_length]
            if self.engine.process(frame) >= 0:
                detected = True
        return detected


class OpenWakeWordDetector(LocalWakeDetector):
    def __init__(self, args) -> None:
        from openwakeword.model import Model

        model_paths = [p for p in args.openwakeword_model_path if p]
        if not model_paths:
            raise RuntimeError("openWakeWord needs --openwakeword-model-path /path/to/model.onnx")
        self.model = Model(wakeword_models=model_paths)
        self.threshold = args.openwakeword_threshold
        self.buffer = array("h")
        print(f"local_wake=openwakeword threshold={self.threshold}", flush=True)

    def process(self, pcm16: bytes) -> bool:
        import numpy as np

        samples = array("h")
        samples.frombytes(pcm16)
        self.buffer.extend(samples)
        detected = False
        # openWakeWord expects 1280 samples (80 ms at 16 kHz) per prediction.
        while len(self.buffer) >= 1280:
            frame = self.buffer[:1280]
            del self.buffer[:1280]
            prediction = self.model.predict(np.array(frame, dtype=np.int16))
            if prediction and max(float(v) for v in prediction.values()) >= self.threshold:
                print(f"LOCAL_WAKE_SCORE {prediction}", flush=True)
                detected = True
        return detected


class SherpaKeywordWakeDetector(LocalWakeDetector):
    def __init__(self, args) -> None:
        import numpy as np
        import sherpa_onnx

        self.np = np
        model_dir = Path(args.sherpa_model_dir)
        if not model_dir.is_absolute():
            model_dir = ROOT / model_dir
        keywords_file = Path(args.sherpa_keywords_file)
        if not keywords_file.is_absolute():
            keywords_file = ROOT / keywords_file

        self.min_rms = args.sherpa_min_rms
        chunk = args.sherpa_chunk
        encoder_name = f"encoder-epoch-13-avg-2-chunk-{chunk}-left-64"
        joiner_name = f"joiner-epoch-13-avg-2-chunk-{chunk}-left-64"
        if args.sherpa_int8:
            encoder_name += ".int8"
            joiner_name += ".int8"

        self.spotter = sherpa_onnx.KeywordSpotter(
            tokens=str(model_dir / "tokens.txt"),
            encoder=str(model_dir / f"{encoder_name}.onnx"),
            decoder=str(model_dir / f"decoder-epoch-13-avg-2-chunk-{chunk}-left-64.onnx"),
            joiner=str(model_dir / f"{joiner_name}.onnx"),
            keywords_file=str(keywords_file),
            num_threads=args.sherpa_num_threads,
            max_active_paths=args.sherpa_max_active_paths,
            keywords_score=args.sherpa_keywords_score,
            keywords_threshold=args.sherpa_keywords_threshold,
            num_trailing_blanks=args.sherpa_num_trailing_blanks,
            provider="cpu",
        )
        self.stream = self.spotter.create_stream()
        print(
            f"local_wake=sherpa model={model_dir.name} keywords={keywords_file} "
            f"chunk={chunk} int8={args.sherpa_int8}",
            flush=True,
        )

    def process(self, pcm16: bytes) -> bool:
        if audioop.rms(pcm16, 2) < self.min_rms:
            return False
        samples = self.np.frombuffer(pcm16, dtype=self.np.int16).astype(self.np.float32) / 32768.0
        self.stream.accept_waveform(16000, samples)
        detected = False
        while self.spotter.is_ready(self.stream):
            self.spotter.decode_stream(self.stream)
            result = self.spotter.get_result(self.stream)
            if result:
                print(f"LOCAL_WAKE_SHERPA {result}", flush=True)
                self.spotter.reset_stream(self.stream)
                detected = True
        return detected


def _open_local_wake_detector(args) -> LocalWakeDetector | None:
    if args.local_wake_provider == "none":
        return None
    try:
        if args.local_wake_provider == "porcupine":
            return PorcupineWakeDetector(args)
        if args.local_wake_provider == "openwakeword":
            return OpenWakeWordDetector(args)
        if args.local_wake_provider == "sherpa":
            return SherpaKeywordWakeDetector(args)
    except Exception as exc:
        print(f"LOCAL_WAKE_WARNING {exc}", flush=True)
    return None


def _capture_arecord(args, raw_frame_bytes: int):
    process = subprocess.Popen(
        [
            "arecord",
            "-q",
            "-D",
            args.input_device,
            "-f",
            "S32_LE",
            "-r",
            "48000",
            "-c",
            "2",
            "-t",
            "raw",
        ],
        stdout=subprocess.PIPE,
        bufsize=raw_frame_bytes * 4,
    )
    if not process.stdout:
        raise RuntimeError("arecord stdout is not available")
    while True:
        raw = process.stdout.read(raw_frame_bytes)
        if not raw:
            raise RuntimeError("arecord stopped")
        yield raw


def _capture_alsa(args, period_size: int):
    try:
        import alsaaudio
    except ImportError as exc:
        raise RuntimeError("pyalsaaudio is not installed") from exc

    capture = alsaaudio.PCM(
        type=alsaaudio.PCM_CAPTURE,
        mode=alsaaudio.PCM_NORMAL,
        device=args.input_device,
    )
    capture.setchannels(2)
    capture.setrate(48000)
    capture.setformat(alsaaudio.PCM_FORMAT_S32_LE)
    capture.setperiodsize(period_size)
    while True:
        length, raw = capture.read()
        if length <= 0:
            continue
        yield raw


def recognize(args, pcm: bytes) -> str:
    if args.asr_provider == "aliyun":
        return recognize_pcm16_aliyun(
            pcm,
            sample_rate=16000,
            timeout=args.asr_timeout,
            enable_voice_detection=not args.no_cloud_vad,
        )
    return recognize_pcm16_volc(pcm, timeout=args.asr_timeout)


def _start_stream_player(args):
    if not args.stream_tts_play:
        return None
    player = args.stream_tts_player
    if not player:
        player = "mpg123" if args.tts_provider == "volc" else "aplay"
    cmd = [player]
    if player == "mpg123":
        cmd.extend(["-q", "-o", "alsa"])
        if args.output_device:
            cmd.extend(["-a", args.output_device])
        cmd.append("-")
    elif player == "ffplay":
        cmd.extend(["-nodisp", "-autoexit", "-loglevel", "quiet", "-"])
    else:
        return None
    try:
        return subprocess.Popen(cmd, stdin=subprocess.PIPE)
    except FileNotFoundError:
        print(f"TTS_STREAM_WARNING player not found: {player}", flush=True)
        return None


def _finish_stream_player(process) -> None:
    if not process:
        return False
    try:
        if process.stdin:
            process.stdin.close()
        return process.wait(timeout=20) == 0
    except Exception:
        process.kill()
        return False


def _play_mp3_file(path: Path, args) -> None:
    wav_path = path.with_suffix(".wav")
    subprocess.run(["mpg123", "-q", "-w", str(wav_path), str(path)], check=True)
    try:
        play_file(wav_path, device=args.output_device)
    finally:
        try:
            wav_path.unlink()
        except OSError:
            pass


def play_prompt_async(group: str, *, device: str = "") -> None:
    threading.Thread(target=lambda: play_prompt(group, device=device), name=f"voice-prompt-{group}", daemon=True).start()


def speak_text(args, text: str, *, stem: str = "response") -> None:
    if not args.speak_results:
        return
    message = spoken_text(text, max_chars=args.tts_max_chars)
    player = None
    try:
        out_dir = ROOT / "data" / "generated" / "voice" / "responses"
        out_dir.mkdir(parents=True, exist_ok=True)
        if args.tts_provider == "volc":
            path = out_dir / f"{stem}_{int(time.time())}.mp3"
            player = _start_stream_player(args)

            def on_chunk(audio: bytes) -> None:
                if player and player.stdin:
                    try:
                        player.stdin.write(audio)
                        player.stdin.flush()
                    except BrokenPipeError:
                        pass

            audio_path = synthesize_volc_stream(message, path, chunk_callback=on_chunk if player else None)
            stream_ok = _finish_stream_player(player) if player else False
            player = None
            if not stream_ok:
                _play_mp3_file(audio_path, args)
        else:
            path = out_dir / f"{stem}_{int(time.time())}.wav"
            audio_path = synthesize(message, path, context="你是桌面机器人小星，请用自然中文普通话播报业务查询结果。")
            play_file(audio_path, device=args.output_device)
    except Exception as exc:
        print(f"TTS_ERROR {exc}", flush=True)
        if args.tts_provider == "volc":
            try:
                path = out_dir / f"{stem}_{int(time.time())}_fallback.wav"
                audio_path = synthesize(message, path, context="你是桌面机器人小星，请用自然中文普通话播报业务查询结果。")
                play_file(audio_path, device=args.output_device)
            except Exception as fallback_exc:
                print(f"TTS_FALLBACK_ERROR {fallback_exc}", flush=True)
    finally:
        _finish_stream_player(player)


def handle_command(args, command: str) -> None:
    command = normalize_command_text(command)
    if not command:
        play_prompt("failed", device=args.output_device)
        return
    if is_wake_text(command):
        print(f"COMMAND_WAKE_IGNORED {command}", flush=True)
        return
    if is_ignorable_voice_command(command):
        print(f"COMMAND_IGNORED {command}", flush=True)
        return
    print(f"COMMAND {command}", flush=True)
    if args.processing_prompt:
        play_prompt_async("processing", device=args.output_device)
    try:
        result = run_agent_command(command, session_id=args.agent_session_id)
    except Exception as exc:
        result = f"处理异常：{exc}"
    print(f"AGENT {result}", flush=True)
    speak_text(args, result)


def run_once(args) -> bool:
    with tempfile.TemporaryDirectory(prefix="sjagent-wake-") as tmp:
        wav_path = Path(tmp) / "chunk.wav"
        record_wav(wav_path, device=args.input_device, seconds=args.chunk_seconds)
        pcm, rms = wav_to_pcm16(wav_path, gain=args.gain)
    if args.verbose:
        print(f"rms={rms}")
    if rms < args.rms_threshold:
        return False

    try:
        text = recognize(args, pcm)
    except Exception as exc:
        print(f"ASR_ERROR {exc}", flush=True)
        return False

    print(f"ASR {text}", flush=True)
    if is_wake_text(text):
        play_prompt("wake", device=args.output_device)
        return True
    return False


def _vad_threshold(noise_floor: float, args) -> float:
    return max(args.vad_min_rms, noise_floor * args.vad_start_ratio + args.vad_start_margin)


def run_stream(args) -> None:
    frame_seconds = args.vad_frame_ms / 1000
    period_size = int(48000 * frame_seconds)
    raw_frame_bytes = period_size * 2 * 4
    if args.capture_backend == "alsa":
        raw_frames = _capture_alsa(args, period_size)
    else:
        raw_frames = _capture_arecord(args, raw_frame_bytes)
    vad = _open_webrtc_vad(args)
    local_wake = _open_local_wake_detector(args)

    print(f"wake listener stream started backend={args.capture_backend}", flush=True)
    state = None
    noise_floor = 0.0
    speaking = False
    speech_frames: list[bytes] = []
    pre_roll: list[bytes] = []
    silence_frames = 0
    speech_frames_count = 0
    active_streak = 0
    max_pre_roll = max(1, int(args.vad_pre_roll_ms / args.vad_frame_ms))
    end_silence_frames = max(1, int(args.vad_end_silence_ms / args.vad_frame_ms))
    max_speech_frames = max(1, int(args.vad_max_seconds / frame_seconds))
    min_speech_frames = max(1, int(args.vad_min_speech_ms / args.vad_frame_ms))
    start_speech_frames = max(1, args.vad_start_frames)
    calibration_frames = max(1, int(args.vad_calibration_ms / args.vad_frame_ms))
    calibration: list[int] = []
    waiting_command_until = 0.0
    ignore_audio_until = 0.0
    streaming_asr: VolcStreamingRecognizer | None = None
    expecting_command_utterance = False

    while True:
        if waiting_command_until and not speaking and time.monotonic() > waiting_command_until:
            waiting_command_until = 0.0
            if args.verbose:
                print("command_window=timeout", flush=True)
        raw = next(raw_frames)
        pcm, rms, state = raw_to_pcm16(raw, gain=args.gain, state=state)
        if ignore_audio_until and time.monotonic() < ignore_audio_until:
            continue
        ignore_audio_until = 0.0
        if calibration_frames:
            calibration.append(rms)
            calibration_frames -= 1
            if not calibration_frames:
                values = sorted(calibration)
                noise_floor = values[len(values) // 2]
                if args.verbose:
                    print(f"calibrated_noise={int(noise_floor)}", flush=True)
            continue
        if not noise_floor:
            noise_floor = rms
        if not speaking:
            noise_floor = noise_floor * 0.94 + rms * 0.06

        if local_wake and not waiting_command_until and local_wake.process(pcm):
            print("LOCAL_WAKE detected", flush=True)
            waiting_command_until = time.monotonic() + args.command_window_seconds
            print("command_window=opened", flush=True)
            play_prompt_async("wake", device=args.output_device)
            ignore_audio_until = time.monotonic() + args.wake_reply_ignore_seconds
            pre_roll.clear()
            speaking = False
            speech_frames = []
            silence_frames = 0
            speech_frames_count = 0
            active_streak = 0
            expecting_command_utterance = False
            continue

        threshold = _vad_threshold(noise_floor, args)
        energy_active = rms >= threshold
        vad_active = False
        if vad:
            vad_frame = _normalize_vad_frame(pcm, args.vad_frame_ms)
            vad_active = vad.is_speech(vad_frame, 16000) and rms >= args.vad_min_rms
        active = vad_active if vad else energy_active
        if args.verbose:
            print(
                f"rms={rms} noise={int(noise_floor)} threshold={int(threshold)} "
                f"vad={int(vad_active)} active={int(active)}",
                flush=True,
            )

        if not speaking:
            pre_roll.append(pcm)
            if len(pre_roll) > max_pre_roll:
                pre_roll.pop(0)
            if active:
                active_streak += 1
            else:
                active_streak = 0
            if active_streak >= start_speech_frames:
                speaking = True
                speech_frames = list(pre_roll)
                expecting_command_utterance = bool(waiting_command_until)
                if expecting_command_utterance and args.asr_provider == "volc" and args.stream_command_asr:
                    streaming_asr = VolcStreamingRecognizer(timeout=args.asr_timeout)
                    for frame in speech_frames:
                        streaming_asr.feed(frame)
                pre_roll.clear()
                silence_frames = 0
                speech_frames_count = active_streak
                active_streak = 0
            continue

        speech_frames.append(pcm)
        if streaming_asr is not None:
            streaming_asr.feed(pcm)
        speech_frames_count += 1
        if active:
            silence_frames = 0
        else:
            silence_frames += 1

        should_end = silence_frames >= end_silence_frames or speech_frames_count >= max_speech_frames
        if not should_end:
            continue

        speaking = False
        if speech_frames_count < min_speech_frames:
            speech_frames = []
            expecting_command_utterance = False
            continue

        utterance = b"".join(speech_frames)
        speech_frames = []
        if local_wake and not waiting_command_until:
            # Pure local wake mode: do not spend cloud ASR calls before the
            # local wake engine opens the command window.
            streaming_asr = None
            expecting_command_utterance = False
            continue
        try:
            if streaming_asr is not None:
                text = streaming_asr.finish()
                streaming_asr = None
            else:
                text = recognize(args, utterance)
        except Exception as exc:
            streaming_asr = None
            print(f"ASR_ERROR {exc}", flush=True)
            continue

        print(f"ASR {text}", flush=True)
        if waiting_command_until or expecting_command_utterance:
            waiting_command_until = 0.0
            expecting_command_utterance = False
            handle_command(args, text)
            continue

        woke = is_wake_text(text)
        command_tail = strip_wake_words(text) if woke else ""
        if woke:
            learn_wake_variants(text)
            if command_tail:
                play_prompt_async("wake", device=args.output_device)
                ignore_audio_until = time.monotonic() + args.wake_reply_ignore_seconds
                handle_command(args, command_tail)
            elif args.assistant_mode:
                waiting_command_until = time.monotonic() + args.command_window_seconds
                print("command_window=opened", flush=True)
                play_prompt_async("wake", device=args.output_device)
                ignore_audio_until = time.monotonic() + args.wake_reply_ignore_seconds
            if not waiting_command_until:
                time.sleep(args.cooldown)


def main() -> None:
    load_dotenv(dotenv_path=ROOT / ".env")
    parser = argparse.ArgumentParser(description="Listen for 小星 and play a wake reply")
    parser.add_argument("--input-device", default="hw:CARD=ahubi2s3,DEV=0")
    parser.add_argument("--output-device", default="")
    parser.add_argument("--chunk-seconds", type=float, default=2.2)
    parser.add_argument("--cooldown", type=float, default=2.5)
    parser.add_argument("--rms-threshold", type=int, default=120)
    parser.add_argument("--gain", type=float, default=8.0, help="PCM gain before ASR")
    parser.add_argument("--no-cloud-vad", action="store_true", help="Disable Aliyun endpoint VAD")
    parser.add_argument("--asr-provider", choices=["volc", "aliyun"], default="volc")
    parser.add_argument("--asr-timeout", type=int, default=15)
    parser.add_argument("--stream-command-asr", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--once", action="store_true", help="Record and process one chunk")
    parser.add_argument("--stream-vad", action="store_true", help="Use continuous local VAD before ASR")
    parser.add_argument("--assistant-mode", action="store_true", help="After wake word, listen for one command")
    parser.add_argument("--command-window-seconds", type=float, default=8.0)
    parser.add_argument("--wake-reply-ignore-seconds", type=float, default=0.8)
    parser.add_argument("--agent-session-id", default="orangepi_voice")
    parser.add_argument("--speak-results", action="store_true")
    parser.add_argument("--processing-prompt", action="store_true")
    parser.add_argument("--tts-provider", choices=["mimo", "volc"], default="mimo")
    parser.add_argument("--tts-max-chars", type=int, default=180)
    parser.add_argument("--stream-tts-play", action="store_true")
    parser.add_argument("--stream-tts-player", default="mpg123")
    parser.add_argument("--capture-backend", choices=["alsa", "arecord"], default="arecord")
    parser.add_argument("--local-wake-provider", choices=["none", "porcupine", "openwakeword", "sherpa"], default="none")
    parser.add_argument("--porcupine-access-key", default=os.getenv("PICOVOICE_ACCESS_KEY", ""))
    parser.add_argument("--porcupine-keyword-path", action="append", default=[])
    parser.add_argument("--porcupine-sensitivity", type=float, default=0.65)
    parser.add_argument("--openwakeword-model-path", action="append", default=[])
    parser.add_argument("--openwakeword-threshold", type=float, default=0.55)
    parser.add_argument(
        "--sherpa-model-dir",
        default="models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20",
    )
    parser.add_argument("--sherpa-keywords-file", default="models/xiaoxing_keywords.txt")
    parser.add_argument("--sherpa-chunk", type=int, default=8, choices=[8, 16])
    parser.add_argument("--sherpa-int8", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--sherpa-num-threads", type=int, default=1)
    parser.add_argument("--sherpa-max-active-paths", type=int, default=8)
    parser.add_argument("--sherpa-keywords-score", type=float, default=3.5)
    parser.add_argument("--sherpa-keywords-threshold", type=float, default=0.15)
    parser.add_argument("--sherpa-num-trailing-blanks", type=int, default=1)
    parser.add_argument("--sherpa-min-rms", type=int, default=60)
    parser.add_argument("--vad-frame-ms", type=int, default=30, choices=[10, 20, 30])
    parser.add_argument("--vad-use-webrtc", action="store_true")
    parser.add_argument("--vad-mode", type=int, default=2, choices=[0, 1, 2, 3])
    parser.add_argument("--vad-pre-roll-ms", type=int, default=300)
    parser.add_argument("--vad-start-frames", type=int, default=3)
    parser.add_argument("--vad-min-speech-ms", type=int, default=350)
    parser.add_argument("--vad-end-silence-ms", type=int, default=600)
    parser.add_argument("--vad-max-seconds", type=float, default=4.0)
    parser.add_argument("--vad-calibration-ms", type=int, default=1000)
    parser.add_argument("--vad-start-ratio", type=float, default=1.04)
    parser.add_argument("--vad-start-margin", type=int, default=350)
    parser.add_argument("--vad-min-rms", type=int, default=9500)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    ensure_group("wake")
    if args.once:
        raise SystemExit(0 if run_once(args) else 1)
    if args.stream_vad:
        run_stream(args)
        return

    print("wake listener started", flush=True)
    while True:
        woke = run_once(args)
        if woke:
            time.sleep(args.cooldown)


if __name__ == "__main__":
    main()
