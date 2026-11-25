# 个人 Mac AI 网关部署参考（GLM 示例）

这份文档描述如何把一台个人 Mac 部署成局域网内的 AI API 反向代理，让公司电脑上的 Claude Code 或 Trae IDE 通过这台个人 Mac 访问 GLM。本仓库的示例脚本只适配 Anthropic Messages 协议；Codex 使用的 Responses 协议不在这一版范围内。

## 目标架构

```text
公司 Mac（Claude Code / Trae）
  ↓
http://<个人Mac IP>:443
  ↓
个人 Mac GLM Anthropic Proxy
  ↓
https://open.bigmodel.cn/api/anthropic
```

个人 Mac 负责：

- 接收公司 Mac 发来的 Anthropic Messages 请求。
- 在本机读取 GLM API Key。
- 转发请求到 GLM Anthropic 兼容接口。
- 保持服务常驻运行。

公司 Mac 只需要：

- 能访问个人 Mac 的局域网 IP。
- 配置 Claude Code 或 Trae 的 `ANTHROPIC_BASE_URL`。
- 不需要安装 VPN，也不需要修改系统代理。

## 适用范围

适合：

- 家用或可信办公局域网内的一对一使用。
- 已经获得公司安全审批，允许通过个人设备中转 AI API 请求。
- 只需要让 Claude Code 或 Trae IDE 使用 GLM 这类 Anthropic 兼容模型。

不适合：

- 公网暴露或多人共享。若要共享，应增加访问令牌或 IP 白名单。
- 未经审批绕过公司安全管控。
- 把 Clash 的 `7890` 端口当作模型 API 入口。`7890` 是系统代理端口，不是 Anthropic Messages 接口。
- 直接支持 Codex。Codex 使用 OpenAI Responses 协议，需要单独的网关或后续统一路由层。

## 部署步骤

以下命令都在个人 Mac 上执行。

### 1. 准备 API Key

网关会按顺序读取 API Key：

1. 环境变量 `GLM_API_KEY`
2. `~/.claude/settings.json` 里的 `env.ANTHROPIC_AUTH_TOKEN`

如果你已经在个人 Mac 上配置过 Claude Code 直连 GLM，通常不需要额外操作。检查方法：

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path.home() / ".claude" / "settings.json"
d = json.loads(p.read_text())
print(d.get("env", {}).get("ANTHROPIC_AUTH_TOKEN", ""))
PY
```

如果输出为空，请先把 GLM API Key 写入 `~/.claude/settings.json`：

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "<你的 GLM API Key>"
  }
}
```

### 2. 安装网关服务

```bash
cd /path/to/personal-ai-gateway
bash scripts/install-glm-anthropic-proxy.sh
```

安装脚本会：

- 把 `scripts/glm_anthropic_proxy.py` 复制到 `~/Library/Application Support/GLMAnthropicProxy/`。
- 安装 LaunchAgent `com.jinbo.glm-anthropic-proxy`。
- 在 `0.0.0.0:443` 启动服务。
- 设置开机自启和异常自动重启。

### 3. 查看个人 Mac IP

```bash
ipconfig getifaddr en0
```

假设输出是 `192.168.0.102`，公司电脑就使用：

```text
http://192.168.0.102:443
```

### 4. 验证网关

在个人 Mac 上：

```bash
curl -i http://127.0.0.1:443/health
```

预期返回：

```json
{"status":"ok"}
```

再执行一次完整请求：

```bash
curl -i --max-time 180 http://127.0.0.1:443/v1/messages \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  --data '{
    "model": "glm-4.7",
    "max_tokens": 64,
    "messages": [
      {
        "role": "user",
        "content": "Reply with exactly: LOCAL_GATEWAY_OK"
      }
    ]
  }'
```

返回 `HTTP/1.1 200 OK` 且内容包含 `LOCAL_GATEWAY_OK`，说明网关工作正常。

## 公司电脑接入

以下命令在公司 Mac 上执行。

### 1. 先做连通性测试

```bash
curl -i --max-time 10 http://192.168.0.102:443/health
```

如果能返回 `{"status":"ok"}`，说明公司电脑可以访问个人 Mac 网关。

### 2. 配置 Claude Code

Claude Code 只需要改两个环境变量：

```bash
export ANTHROPIC_BASE_URL="http://192.168.0.102:443"
export ANTHROPIC_AUTH_TOKEN="local-gateway"
```

说明：

- `ANTHROPIC_BASE_URL` 指向个人 Mac 网关。
- `ANTHROPIC_AUTH_TOKEN` 在当前网关中不做校验，只是 Claude Code 客户端自身需要一个非空值。你可以使用占位符。
- 如果要长期生效，可以把这两行写入 shell 配置文件或 Claude Code 的配置文件。

验证：

```bash
curl -i --max-time 180 http://192.168.0.102:443/v1/messages \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -H "Authorization: Bearer local-gateway" \
  --data '{
    "model": "glm-4.7",
    "max_tokens": 64,
    "messages": [
      {
        "role": "user",
        "content": "Reply with exactly: COMPANY_GATEWAY_OK"
      }
    ]
  }'
```

### 3. 配置 Trae IDE

在模型供应商或自定义模型配置里：

- 协议选择 `Anthropic Messages`
- Base URL 填 `http://192.168.0.102:443`
- API Key 填任意非空值，例如 `local-gateway`
- 模型名填 GLM 提供的模型名，例如 `glm-4.7`

## 切换到其他模型

当前示例脚本的上游固定为：

```text
https://open.bigmodel.cn/api/anthropic
```

如果其他模型服务商也提供 Anthropic Messages 兼容接口，可以复制这份脚本和 LaunchAgent，然后修改两处：

1. `GLM_ANTHROPIC_UPSTREAM` 指向新的上游地址。
2. API Key 改为读取新的服务商密钥。

如果需要同时支持 GLM、Kimi、DeepSeek、Claude、OpenAI 或 Codex，建议改为使用 LiteLLM 或自建统一路由层，而不是继续扩展这个单一上游脚本。

## 运维与排障

### 查看服务状态

```bash
launchctl print gui/$(id -u)/com.jinbo.glm-anthropic-proxy
```

### 查看监听端口

```bash
lsof -nP -iTCP:443 -sTCP:LISTEN
```

### 查看日志

```bash
tail -n 100 "$HOME/Library/Application Support/GLMAnthropicProxy/glm-anthropic-proxy.log"
```

### 重启服务

```bash
launchctl kickstart -k gui/$(id -u)/com.jinbo.glm-anthropic-proxy
```

### 常见问题

| 现象 | 可能原因 | 处理方式 |
|------|----------|----------|
| 公司电脑访问 `/health` 超时 | 局域网不通或防火墙拦截 | 确认两台电脑在同一网段，允许个人 Mac 的 443 入站 |
| 本机 `/health` 正常但公司电脑不通 | 公司网络策略或 IP 变化 | 重新查看个人 Mac IP，确认公司电脑未被系统代理接管 |
| 公司电脑“全局没网” | 系统代理指向个人 Mac 的 7890 | 关闭公司电脑的系统代理，只保留 `ANTHROPIC_BASE_URL` |
| 请求返回 401 | 上游 API Key 无效或未读取到 | 检查 `~/.claude/settings.json` 或 `GLM_API_KEY` |
| 服务重启后仍不通 | LaunchAgent 未启动或端口被占用 | 查看 `launchctl print` 和 `lsof` |

## 安全建议

- 只在可信局域网内使用。
- 不要把这台个人 Mac 或 443 服务暴露到公网。
- 如果同事要复用，建议增加访问令牌或 IP 白名单。
- 不要把 API Key 提交到仓库。
- 保持个人 Mac 开机和网络稳定；个人 Mac 睡眠会导致公司电脑请求失败。
