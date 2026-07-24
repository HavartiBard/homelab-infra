# Playbook Layout

Playbooks are organized by service domain to keep the root directory uncluttered:

| Directory | Description |
|-----------|-------------|
| `mcp/` | MCP deployments (Proxmox, OnePassword, Homelab aggregator, Obsidian, SearXNG, etc.) |
| `dns/` | DNS/DHCP provisioning and AdGuard/Technitium config |
| `services/` | Service vanity host automation via NPM + Technitium (`update-*-proxy.yml`) |
| `platform/` | Platform VM services such as Nginx Proxy Manager, Ollama, OpenHands, Director, and Sprite Smith |
| `ai/` | AI inference, agent services, and LLM evaluation utilities such as Ollama, Open WebUI, LiteLLM, Qdrant, Personal Agent LLM, Phoenix, Promptfoo, and lm-eval-harness |
| `bootstrap/` | Host bootstrap and workstation setup such as Ubuntu defaults, dev environment, SSH keys, and Tailscale |

Each playbook can be run from the repo root like:

```bash
cd ansible
ansible-playbook playbooks/<group>/<playbook>.yml --limit <host-or-group>
```

Update this README whenever playbooks are added, moved, or removed so it stays a current guide for the agent workflow.

Recent platform/service additions:
- `platform/deploy-director.yml`
- `services/update-director-proxy.yml`
- `ai/deploy-personal-agent-llm.yml`
- `ai/deploy-phoenix.yml`
- `ai/deploy-promptfoo.yml`
- `ai/deploy-lm-eval-harness.yml`
- `bootstrap/deploy-tailscale.yml`
- `bootstrap/provision-tailscale-router.yml`
- `mcp/deploy-crawl4ai.yml`
- `mcp/deploy-hister-archive-mcp.yml`
