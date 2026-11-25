#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
uid="$(id -u)"
label="com.jinbo.glm-anthropic-proxy"
domain="gui/${uid}"
runtime_dir="${HOME}/Library/Application Support/GLMAnthropicProxy"
destination="${HOME}/Library/LaunchAgents/${label}.plist"

mkdir -p "${runtime_dir}" "${HOME}/Library/LaunchAgents"
/usr/bin/install -m 0755 "${repo}/scripts/glm_anthropic_proxy.py" "${runtime_dir}/glm_anthropic_proxy.py"
/usr/bin/install -m 0644 "${repo}/deployment/glm-anthropic-proxy.launch-agent.plist" "${destination}"

launchctl bootout "${domain}/${label}" >/dev/null 2>&1 || true
launchctl bootstrap "${domain}" "${destination}"
launchctl kickstart -k "${domain}/${label}"

for _ in {1..30}; do
  status="$(curl -sS --max-time 1 -o /dev/null -w '%{http_code}' http://127.0.0.1:443/health 2>/dev/null || true)"
  if [[ "${status}" == "200" ]]; then
    echo "GLM Anthropic proxy installed and running on port 443"
    exit 0
  fi
  sleep 0.2
done

echo "GLM Anthropic proxy was installed but did not become healthy" >&2
launchctl print "${domain}/${label}" >&2 || true
exit 1
