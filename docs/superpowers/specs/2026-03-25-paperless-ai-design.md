# Paperless-AI Deployment Design

**Date:** 2026-03-25
**Status:** Approved

## Overview

Deploy [paperless-ai](https://github.com/clusterzx/paperless-ai) alongside the existing paperless-ngx instance on Unraid. paperless-ai automatically analyzes new documents ingested by paperless-ngx and uses an LLM to assign titles, tags, correspondents, and document types. A RAG-based chat interface is also available.

## Architecture

```
paperless-ai (Unraid :3090)
  ├── → paperless-ngx API (http://192.168.20.14:8000/api)  [document data]
  └── → LM Studio (http://192.168.20.50:1234/v1)           [AI inference]

https://paperless-ai.klsll.com → NPM → Unraid:3090
```

paperless-ai polls paperless-ngx on a cron schedule, fetches new documents, sends content to LM Studio for analysis, and writes back structured metadata (title, tags, correspondent, document type) via the paperless-ngx API.

## Components

### Docker Container
- **Image:** `clusterzx/paperless-ai` (latest — no stable tags published)
- **Host port:** 3090 (port 3000 is occupied by notion-mcp-public on Unraid)
- **Data volume:** named volume `paperless-ai-data` (stores ChromaDB RAG index + config)
- **Network:** bridge (no shared Docker network needed — connects to paperless-ngx via LAN IP)
- **Deployed to:** Unraid (`/opt/docker/paperless-ai/`)

### AI Backend
- **Provider:** `custom` (OpenAI-compatible)
- **URL:** `http://192.168.20.50:1234/v1` (LM Studio on spraycheese)
- **Model:** `qwen/qwen3-14b`
- **API key:** `vault_ironclaw_lmstudio_api_key` (reused from IronClaw — same LM Studio instance)

### Paperless-ngx Connection
- **API URL:** `http://192.168.20.14:8000/api`
- **Auth:** dedicated API user `paperless-ai` with token stored in vault
- **Vault key:** `vault_paperless_ai_api_token` (sourced from 1Password "Paperless AI API")

### Processing Config
- `SCAN_INTERVAL=*/30 * * * *` — poll every 30 minutes
- `ACTIVATE_TAGGING=yes`
- `ACTIVATE_CORRESPONDENTS=yes`
- `ACTIVATE_DOCUMENT_TYPE=yes`
- `ACTIVATE_TITLE=yes`
- `ADD_AI_PROCESSED_TAG=yes` / `AI_PROCESSED_TAG_NAME=ai-processed` — marks processed docs
- `RESTRICT_TO_EXISTING_TAGS=no` — allow new tags (AI creates them as needed)
- `RAG_SERVICE_ENABLED=true` — enables `/chat` interface

## Secrets

| Vault Key | Source | Purpose |
|-----------|--------|---------|
| `vault_paperless_ai_api_token` | 1Password "Paperless AI API" | paperless-ngx API token |
| `vault_ironclaw_lmstudio_api_key` | Already in vault | LM Studio auth (reused) |

## Ansible Role Structure

```
ansible/roles/paperless-ai/
  defaults/main.yml         — ports, URLs, model, processing flags
  tasks/main.yml            — dirs, compose, env, pull, deploy, health
  templates/
    paperless-ai.env.j2     — env file (secrets injected at deploy time)
```

## Files Created

```
ansible/roles/paperless-ai/
ansible/playbooks/misc/deploy-paperless-ai.yml
ansible/files/npm/services/paperless-ai.yml
ansible/playbooks/services/update-paperless-ai-proxy.yml
```

## NPM Proxy / DNS

- **Domain:** `paperless-ai.klsll.com`
- **Forward:** `192.168.20.14:3090`
- **TLS:** `klsll-wildcard`, SSL forced, HSTS, HTTP/2
- **DNS:** A record → `192.168.20.50` (NPM host)

## Vault Update

Before deployment, sync `vault_paperless_ai_api_token` from 1Password into `ansible/group_vars/all/vault.yml`.

## Rollback

```bash
ssh root@192.168.20.14 "cd /opt/docker/paperless-ai && docker compose down"
```

The paperless-ngx instance is unaffected — paperless-ai only writes metadata back via API, it does not touch the document store directly.
