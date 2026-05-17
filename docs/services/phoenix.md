---
service: phoenix
type: utility
host: unraid
ports: [6006, 4317]
status: planned
---

# Phoenix

## Overview

Arize Phoenix stores LLM traces, datasets, prompt experiments, and eval scores for the agent self-improvement loop. It should remain separate from ACP, with ACP and other agents emitting traces into Phoenix and linking back to Phoenix run details.

## Configuration

- Host: `unraid-server` (`192.168.20.14`)
- UI / HTTP traces: `http://192.168.20.14:6006`
- OTLP gRPC traces: `192.168.20.14:4317`
- Data: `/mnt/user/appdata/phoenix`
- Compose: `/opt/docker/phoenix/docker-compose.yml`
- Role defaults: `ansible/roles/phoenix/defaults/main.yml`

## Deployment

```bash
cd ansible
ansible-playbook playbooks/ai/deploy-phoenix.yml --syntax-check
ansible-playbook playbooks/ai/deploy-phoenix.yml --check --diff --limit unraid
ansible-playbook playbooks/ai/deploy-phoenix.yml --diff --limit unraid -v
```

## Health Check

```bash
curl -sf http://192.168.20.14:6006/
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep phoenix
docker logs phoenix -f
```

## Troubleshooting

If the UI is unavailable, inspect the compose directory and logs:

```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14
cd /opt/docker/phoenix
docker compose ps
docker compose logs -f
```
