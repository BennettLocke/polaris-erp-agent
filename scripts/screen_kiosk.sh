#!/usr/bin/env bash
set -euo pipefail

URL="${SJ_SCREEN_URL:-http://127.0.0.1:8080/screen}"

export GDK_BACKEND=x11
export WEBKIT_DISABLE_COMPOSITING_MODE=1
export LIBGL_ALWAYS_SOFTWARE=1

xset s off -dpms s noblank >/dev/null 2>&1 || true
xsetroot -solid black >/dev/null 2>&1 || true
openbox >/tmp/sjagent-openbox.log 2>&1 &
unclutter -idle 0.1 -root >/tmp/sjagent-unclutter.log 2>&1 &

exec surf -F "${URL}"
