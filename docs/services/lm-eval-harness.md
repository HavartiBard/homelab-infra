---
service: lm-eval-harness
type: utility
host: unraid
ports: []
status: planned
---

# lm-eval-harness

## Overview

EleutherAI lm-evaluation-harness is the standardized benchmark runner for model/settings baselines. It runs on Unraid as an orchestration container and targets model endpoints on LiteLLM, Ollama, goudai, or other OpenAI-compatible runtimes.

## Configuration

- Host: `unraid-server` (`192.168.20.14`)
- Container: `lm-eval-harness`
- Configs: `/mnt/user/appdata/lm-eval-harness/configs`
- Results: `/mnt/user/appdata/lm-eval-harness/results`
- Cache: `/mnt/user/appdata/lm-eval-harness/cache`
- Compose: `/opt/docker/lm-eval-harness/docker-compose.yml`
- Role defaults: `ansible/roles/lm-eval-harness/defaults/main.yml`

## Deployment

```bash
cd ansible
ansible-playbook playbooks/ai/deploy-lm-eval-harness.yml --syntax-check
ansible-playbook playbooks/ai/deploy-lm-eval-harness.yml --check --diff --limit unraid
ansible-playbook playbooks/ai/deploy-lm-eval-harness.yml --diff --limit unraid -v
```

## Health Check

```bash
docker exec lm-eval-harness lm_eval --help >/dev/null
docker ps --format "table {{.Names}}\t{{.Status}}" | grep lm-eval-harness
```

## Troubleshooting

```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14
cd /opt/docker/lm-eval-harness
docker compose ps
docker compose logs -f
docker exec -it lm-eval-harness bash
```
