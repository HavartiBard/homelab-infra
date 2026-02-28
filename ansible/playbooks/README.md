# Playbook Layout

Playbooks are organized by service domain to keep the root directory uncluttered:

| Directory | Description |
|-----------|-------------|
| `mcp/` | MCP deployments (Proxmox, OnePassword, Homelab aggregator, Obsidian, SearXNG, etc.) |
| `dns/` | DNS/DHCP provisioning and AdGuard/Technitium config |
| `services/` | Service vanity host automation via NPM + Technitium (`update-*-proxy.yml`) |
| `platform/` | Platform VM services such as Nginx Proxy Manager, Ollama, OpenHands, Director, and Sprite Smith |
| `misc/` | Supporting utilities (currently `deploy-ssh-keys.yml`) |

Each playbook can be run from the repo root like:

```bash
cd ansible
ansible-playbook playbooks/<group>/<playbook>.yml --limit <host-or-group>
```

Update this README whenever playbooks are added, moved, or removed so it stays a current guide for the agent workflow.

Recent platform/service additions:
- `platform/deploy-research-dashboard.yml`
- `services/update-research-dashboard-proxy.yml`
- `platform/deploy-director.yml`
- `services/update-director-proxy.yml`
