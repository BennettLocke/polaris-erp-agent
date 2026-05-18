#!/usr/bin/env bash
set -euo pipefail

URL="${SJ_SCREEN_URL:-http://127.0.0.1:8080/screen}"

xset s off -dpms s noblank >/dev/null 2>&1 || true
xsetroot -solid black >/dev/null 2>&1 || true
openbox >/tmp/sjagent-openbox.log 2>&1 &
unclutter -idle 0.1 -root >/tmp/sjagent-unclutter.log 2>&1 &

exec surf -F "${URL}"
