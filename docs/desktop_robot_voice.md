# Desktop Robot Voice Feedback

The Orange Pi desktop robot uses cached short voice prompts for fast local
feedback, then synthesizes final business results only when the answer is ready.

## Flow

1. Wake word detected: play a random `wake` prompt immediately.
2. Listen for the command and start running sjagent.
3. If the result is fast, speak the result directly.
4. If the task is still running after about 3 seconds, play one `processing`
   prompt.
5. If it is still running after about 8 seconds, play one `slow_8s` prompt.
6. If it is still running after about 25 seconds, play one `slow_25s` prompt.
7. On failure, play one `failed` prompt.

This keeps short tasks from being interrupted by "processing" speech while still
making slow ERP/database operations feel alive.

## Prompt Groups

- `wake`: 在呢 / 我在 / 嗯，我在 / 来了 / 在，您说 / 我听着呢 / 小星在
- `processing`: 收到啦，正在给你处理 / 好的，我来处理
- `slow_8s`: 还在查，稍等一下 / 我还在处理，稍等
- `slow_25s`: 这个稍微慢一点，我继续看 / 系统响应有点慢，我继续处理
- `failed`: 刚才没处理成功，你再说一遍 / 这个我没处理好，再试一次

## Commands

Generate all cached prompt audio:

```bash
cd /home/orangepi/sjagent
.venv/bin/python scripts/voice_prompts.py all --ensure
```

Play one random wake prompt:

```bash
.venv/bin/python scripts/voice_prompts.py wake --play
```

List prompt text and cached file names:

```bash
.venv/bin/python scripts/voice_prompts.py all --list
```
