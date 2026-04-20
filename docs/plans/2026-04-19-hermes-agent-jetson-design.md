# Hermes Agent on Jetson — Design

**Date:** 2026-04-19
**Status:** Approved — ready for implementation planning

## Overview

Deploy Hermes Agent (Nous Research, MIT, v2026.4.x) on `jetson.lab` alongside the existing OpenClaw gateway. Hermes provides interactive + autonomous agent capabilities with persistent memory, self-improving skills, Slack integration, and MCP server exposure. The Jetson hosts the process only; all LLM inference runs on spraycheese or Codex (OpenAI).

## Architecture

**Host:** `jetson.lab` (192.168.20.169, Jetson Orin Nano, 8GB VRAM)

**LLM backends:**
- Primary: spraycheese Ollama — `http://spraycheese.lab.klsll.com:11434/v1` (private/offline)
- Secondary: Codex (OpenAI) — device-code auth, credentials pre-seeded from `~/.codex/auth.json`

The Jetson's local Ollama is intentionally NOT used as the Hermes backend. Hermes requires ≥64k token context; running an 8B model at 64k context would exhaust all 8GB VRAM. spraycheese has sufficient VRAM for a capable model at full context.

**Access surfaces:**

| Surface | Method |
|---|---|
| Interactive CLI | `ssh james@jetson.lab` → `docker exec -it hermes hermes` |
| Web UI | NPM reverse proxy → `hermes.klsll.com` |
| MCP (Claude Code) | stdio via SSH: `ssh james@jetson.lab docker exec -i hermes hermes mcp serve` |
| Slack | Socket Mode outbound (no public endpoint required) |

**MCP note:** Hermes MCP transport is stdio-only (no HTTP MCP as of v2026.4.x). Claude Code and other agents connect via an SSH command entry in `~/.claude.json`:
```json
"hermes": {
  "type": "stdio",
  "command": "ssh",
  "args": ["james@jetson.lab", "docker", "exec", "-i", "hermes", "hermes", "mcp", "serve"]
}
```

## File Structure

New files follow the existing OpenClaw pattern exactly:

```
ansible/
├── roles/
│   └── jetson-hermes/
│       ├── defaults/main.yml
│       └── tasks/main.yml
├── files/
│   └── jetson/
│       └── hermes/
│           ├── docker-compose.yml
│           ├── .env.j2
│           └── config/
│               └── hermes.yaml.j2
├── playbooks/
│   └── misc/
│       └── deploy-jetson-hermes.yml
└── group_vars/
    └── edge_devices/
        └── jetson.lab.yml             # add hermes_* vars
```

## Key Configuration

**`hermes.yaml` (templated):**
```yaml
model:
  provider: custom
  base_url: http://spraycheese.lab.klsll.com:11434/v1
  default: qwen2.5-coder:32b          # confirm 64k-capable model on spraycheese
  context_length: 65536
  api_key: ollama

messaging:
  slack:
    enabled: true
    allowed_users: "{{ hermes_slack_allowed_users }}"

terminal:
  backend: local
```

**`docker-compose.yml` highlights:**
- Image: `ghcr.io/nousresearch/hermes-agent:latest` (pin to digest at deploy time)
- `network_mode: host`
- `restart: unless-stopped`
- Volumes: `/home/james/.hermes` (state), `/home/james/.codex/auth.json:ro` (Codex creds)
- `env_file: .env` for Slack tokens

**Secrets (from 1Password via `op read` at deploy time):**
- `SLACK_BOT_TOKEN` — `xoxb-` bot token
- `SLACK_APP_TOKEN` — `xapp-` Socket Mode app token
- `SLACK_ALLOWED_USERS` — comma-separated Slack member IDs

## Slack App Requirements

Create a Slack app at https://api.slack.com/apps with Socket Mode enabled.

Required OAuth scopes: `chat:write`, `app_mentions:read`, `channels:history`, `channels:read`,
`groups:history`, `im:history`, `im:read`, `im:write`, `users:read`, `files:read`, `files:write`

Required event subscriptions: `message.im`, `message.channels`, `message.groups`, `app_mention`

## Out of Scope

- Creating the Slack app (manual step in api.slack.com)
- Codex device-code auth (interactive first-run step after deploy)
- NPM proxy rule creation (manual or separate PR)

## Pre-Implementation Checks

1. Confirm Docker image name from GitHub packages: `ghcr.io/nousresearch/hermes-agent`
2. Run `ssh james@jetson.lab ollama list` on spraycheese to confirm a 64k-capable model is available
3. Confirm spraycheese hostname resolves from Jetson: `ssh james@jetson.lab curl -s http://spraycheese.lab.klsll.com:11434/api/tags`
