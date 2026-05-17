---
service: promptfoo
type: utility
host: unraid
ports: [15500]
status: planned
---

# Promptfoo

## Overview

Promptfoo provides custom evals for chief-of-staff, coding assistant, researcher, and sub-agent workflows. Use it for model/prompt/settings comparisons that reflect personal workflows rather than generic leaderboard tasks.

## Configuration

- Host: `unraid-server` (`192.168.20.14`)
- UI: `http://192.168.20.14:15500`
- Data: `/mnt/user/appdata/promptfoo`
- Compose: `/opt/docker/promptfoo/docker-compose.yml`
- Role defaults: `ansible/roles/promptfoo/defaults/main.yml`

## Deployment

```bash
cd ansible
ansible-playbook playbooks/ai/deploy-promptfoo.yml --syntax-check
ansible-playbook playbooks/ai/deploy-promptfoo.yml --check --diff --limit unraid
ansible-playbook playbooks/ai/deploy-promptfoo.yml --diff --limit unraid -v
```

## Health Check

```bash
curl -sf http://192.168.20.14:15500/
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep promptfoo
docker logs promptfoo -f
```

## Troubleshooting

```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14
cd /opt/docker/promptfoo
docker compose ps
docker compose logs -f
```
