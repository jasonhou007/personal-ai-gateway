# Personal AI Gateway

这是一个独立的个人 Mac AI 网关仓库，用来把公司电脑上的 Claude Code 或 Trae IDE 请求转发到个人 Mac，再由个人 Mac 访问外部 AI 服务。

当前版本以 GLM 为例，提供 Anthropic Messages 协议的反向代理。它不包含公司项目代码，也不依赖 DevAgent 主仓库。

## 快速开始

1. 在个人 Mac 上准备 GLM API Key。
2. 执行安装脚本：

```bash
bash scripts/install-glm-anthropic-proxy.sh
```

3. 查看个人 Mac 的局域网 IP：

```bash
ipconfig getifaddr en0
```

4. 在公司电脑上配置 Claude Code：

```bash
export ANTHROPIC_BASE_URL="http://<个人Mac IP>:443"
export ANTHROPIC_AUTH_TOKEN="local-gateway"
```

详细步骤见 [docs/personal-ai-gateway.md](docs/personal-ai-gateway.md)。

## 仓库结构

```text
personal-ai-gateway/
├── README.md
├── deployment/
│   └── glm-anthropic-proxy.launch-agent.plist
├── scripts/
│   ├── glm_anthropic_proxy.py
│   ├── install-glm-anthropic-proxy.sh
│   └── verify-glm-anthropic-proxy.sh
└── docs/
    └── personal-ai-gateway.md
```

## 适用范围

- Claude Code
- Trae IDE
- Anthropic Messages 协议
- 可信局域网内的一对一使用

## 不适用范围

- Codex / OpenAI Responses 协议
- 公网暴露
- 多人共享
- 绕过公司安全审批

## 安全提醒

- 不要把 API Key 提交到仓库。
- 不要把 443 服务暴露到公网。
- 如果需要共享，请先增加访问令牌或 IP 白名单。
