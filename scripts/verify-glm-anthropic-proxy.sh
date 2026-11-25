#!/usr/bin/env bash
set -euo pipefail

base="${GLM_PROXY_TEST_URL:-http://127.0.0.1:443}"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

health="$(curl -sS --max-time 5 -o "$tmp_dir/health.json" -w '%{http_code}' "$base/health")"

status="$(curl -sS --max-time 180 -o "$tmp_dir/message.json" -w '%{http_code}' \
  "$base/v1/messages" \
  -H 'anthropic-version: 2023-06-01' \
  -H 'content-type: application/json' \
  --data '{"model":"glm-4.7","max_tokens":32,"messages":[{"role":"user","content":"Reply with exactly: OK"}]}')"

reply="$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(" ".join(b.get("text","") for b in d.get("content",[]) if isinstance(b,dict)))' "$tmp_dir/message.json")"

stream_status="$(curl -sS --max-time 180 -N -o "$tmp_dir/stream.txt" -w '%{http_code}' \
  "$base/v1/messages" \
  -H 'anthropic-version: 2023-06-01' \
  -H 'content-type: application/json' \
  --data '{"model":"glm-4.7","max_tokens":32,"stream":true,"messages":[{"role":"user","content":"Reply with exactly: STREAM_OK"}]}')"

stream_events="$(grep -c '^event:' "$tmp_dir/stream.txt" || true)"
stream_data="$(grep -c '^data:' "$tmp_dir/stream.txt" || true)"

printf 'health=%s message=%s reply=%s stream=%s stream_events=%s stream_data=%s\n' \
  "$health" "$status" "$reply" "$stream_status" "$stream_events" "$stream_data"

[[ "$health" == "200" ]]
[[ "$status" == "200" ]]
[[ "$reply" == *"OK"* ]]
[[ "$stream_status" == "200" ]]
[[ "$stream_events" -gt 0 ]]
[[ "$stream_data" -gt 0 ]]
