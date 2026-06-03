---
service: llm-bench
type: utility
host: unraid
ports: [15600]
status: active
---

# llm-bench

## Overview

LLM endpoint benchmarking platform: capability catalog, orchestrator CLI, and read-only Streamlit leaderboard. Runs against any OpenAI-compatible endpoint (goudai's `personal-agent-llm`, Ollama, LM Studio, etc.).

## Configuration

- Host: `unraid-server` (`192.168.20.14`)
- Container: `llm-bench`
- Dashboard: `http://192.168.20.14:15600`
- Appdata: `/mnt/user/appdata/llm-bench`
- Compose: `/opt/docker/llm-bench/docker-compose.yml`
- Spec: `projects/homelab-infra/llm-bench-design.md` (Obsidian vault)
- Plan: `projects/homelab-infra/llm-bench-plan.md` (Obsidian vault)

## Deployment

```bash
cd ansible
ansible-playbook playbooks/ai/deploy-llm-bench.yml --syntax-check
ansible-playbook playbooks/ai/deploy-llm-bench.yml --check --diff --limit unraid
ansible-playbook playbooks/ai/deploy-llm-bench.yml --diff --limit unraid -v
```

## Running a Benchmark

```bash
ssh root@192.168.20.14 'docker exec llm-bench bench run \
  --endpoint http://goudai.lab.klsll.com:8010/v1 \
  --model qwen/qwen3.6-27b-mtp \
  --runtime llama.cpp \
  --host goudai \
  --suite tier1 \
  --notes "first MTP baseline"'
```

## Health Check

```bash
curl -sf http://192.168.20.14:15600/_stcore/health
docker ps --format "table {{.Names}}\t{{.Status}}" | grep llm-bench
```

## Troubleshooting

```bash
ssh root@192.168.20.14
cd /opt/docker/llm-bench
docker compose ps
docker compose logs -f
docker exec -it llm-bench bash
```
