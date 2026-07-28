#!/bin/sh
set -eu

media_pid=""
backend_pid=""

stop_stack() {
  if [ -n "$backend_pid" ]; then
    kill -TERM "$backend_pid" 2>/dev/null || true
  fi
  if [ -n "$media_pid" ]; then
    kill -TERM "$media_pid" 2>/dev/null || true
  fi
}

trap stop_stack INT TERM EXIT

if [ "${EMBEDDED_MEDIAMTX:-true}" = "true" ]; then
  mkdir -p /app/logs /recordings
  /usr/local/bin/mediamtx /app/infrastructure/mediamtx.yml \
    >>/app/logs/mediamtx.log 2>&1 &
  media_pid=$!

  attempts=0
  until curl --fail --silent --max-time 1 \
    "${MEDIAMTX_API_URL:-http://127.0.0.1:9997}/v3/paths/list" >/dev/null
  do
    if ! kill -0 "$media_pid" 2>/dev/null; then
      echo "MediaMTX exited before becoming ready." >&2
      tail -n 50 /app/logs/mediamtx.log >&2 || true
      exit 1
    fi
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 30 ]; then
      echo "MediaMTX did not become ready within 30 seconds." >&2
      tail -n 50 /app/logs/mediamtx.log >&2 || true
      exit 1
    fi
    sleep 1
  done
  echo "MediaMTX ready on RTSP 8554, API 9997, HLS 8888, WebRTC 8889."
fi

"$@" &
backend_pid=$!
wait "$backend_pid"
status=$?
backend_pid=""
exit "$status"
