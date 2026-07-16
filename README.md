# Homelab Infrastructure

Ansible-managed Docker infrastructure for hybrid homelab: Unraid, Proxmox VMs, and WSL2 GPU workers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           LAN / VPN Only                            │
├─────────────────────────────────────────────────────────────────────┤
│   Platform VM (Proxmox)                                             │
│   ├── Nginx Proxy Manager                                           │
│   └── Uptime Kuma                                                   │
│                                                                     │
│   Unraid (192.168.20.14)         WSL2 GPU Workers                  │
│   ├── MCP Servers                └── Ollama + Open WebUI           │
│   └── Long-running services                                         │
│                                                                     │
│   DNS Infrastructure (LXCs)      Query Flow                         │
│   ├── agh1/agh2 (AdGuard)  ←──── Clients (DHCP-assigned DNS)        │
│   │   └── .4/.5 per VLAN         ├── local → Technitium             │
│   └── tt1/tt2 (Technitium)       └── external → DoH (CF/Quad9)      │
│       └── .2/.3 per VLAN                                            │
└─────────────────────────────────────────────────────────────────────┘
```

### DNS Query Flow
```
Client → AdGuard (.4/.5) ─┬─ klsll.com zones ──→ Technitium (.2/.3)
                          └─ external queries ──→ DoH (Cloudflare/Quad9)
```

## Quick Start

1. **Read the runbook:** [`docs/runbook.md`](docs/runbook.md)
2. **Deploy Platform VM** on Proxmox with Docker
3. **Deploy Platform Stack** from `stacks/platform/`
4. **Deploy GPU Workers** on WSL2

## Repository Structure

```
homelab-infra/
├── stacks/                    # Docker Compose stacks (source of truth)
│   ├── platform/              # Core infra: NPM, Kuma, Homepage
│   ├── gpu-worker/            # AI/ML: Ollama, Open WebUI
│   └── monitoring/            # Observability: Prometheus, Grafana
├── ansible/                   # Ansible automation
│   ├── playbooks/             # Deployment playbooks
│   ├── roles/                 # Service roles (adguard, technitium, MCP servers)
│   ├── inventory/             # Host inventory (hosts.yml)
│   └── group_vars/            # Host group variables
├── docker/                    # Standalone compose files and Dockerfiles
├── scripts/                   # Helper scripts
└── docs/                      # Documentation
    ├── runbook.md             # Step-by-step deployment guide
    └── agents/                # Agent-specific runbooks
```

## Stacks

| Stack | Purpose | Deploy To |
|-------|---------|-----------|
| **platform** | NPM, Uptime Kuma, Homepage | Platform VM |
| **gpu-worker** | Ollama, Open WebUI | WSL2 GPU workers |
| **monitoring** | Prometheus, Grafana, Node Exporter | Platform VM |

## Ansible Roles

| Role | Purpose |
|------|---------|
| **adguard** | Configure AdGuard Home (DNS filtering, upstreams) |
| **technitium** | Configure Technitium DNS (zones, DHCP) |
| **unraid-mcp** | Deploy Unraid MCP server container |
| **proxmox-mcp** | Deploy Proxmox MCP server container |
| **onepassword-mcp** | Deploy 1Password MCP server container |
| **homelab-mcp** | Deploy Homelab MCP aggregator container |

## Ansible Playbooks

Playbooks are grouped by service area inside `ansible/playbooks/` to keep the root tidy:

- `ansible/playbooks/mcp/` – MCP deployments (`deploy-*-mcp.yml`), including Proxmox, OnePassword, and Homelab.
- `ansible/playbooks/dns/` – DNS and DHCP provisioning plus AdGuard/Technitium config (`provision-dns-dhcp*.yml`, `deploy-adguard-config.yml`).
- `ansible/playbooks/services/` – Service vanity host automation via NPM + Technitium (`update-*-proxy.yml`).
- `ansible/playbooks/platform/` – Platform services such as NPM, Ollama, and OpenHands.
- `ansible/playbooks/platform/` – Platform services such as NPM, Ollama, OpenHands, and Director.
- `ansible/playbooks/misc/` – Utility helpers (e.g., `deploy-ssh-keys.yml`).

See `ansible/playbooks/README.md` for more detail on each playbook.

Recent additions:
- `ansible/playbooks/platform/deploy-director.yml`
- `ansible/playbooks/services/update-director-proxy.yml`

## Key Principles

- **Git as Source of Truth** - All infrastructure defined in this repo
- **LAN-Only Access** - Management interfaces never exposed publicly
- **Secrets via 1Password Environments** - Credentials never committed in plaintext; 1Password is the sole source of truth, resolved at runtime via `op run` (see `docs/secrets-management.md`)

## Documentation

- [**Runbook**](docs/runbook.md) - Complete deployment guide from zero to working
- [**Plan**](docs/plan.md) - Architecture decisions and design
- [**Network Ports**](docs/network-ports.md) - Port reference and firewall rules
- [**Checklist**](docs/checklist.md) - Deployment verification and smoke tests
- [**Director Service**](docs/services/director.md) - Director deployment, proxy, DNS, verify, rollback

## Deploy a Stack

Most infrastructure now deploys through Ansible playbooks, with the observability stack living under `ansible/files/observability` and the deployment entrypoint at `ansible/playbooks/observability/deploy-observability.yml`.

```bash
cd ansible
ansible-playbook playbooks/observability/deploy-observability.yml --syntax-check
./scripts/run-playbook.sh observability playbooks/observability/deploy-observability.yml --diff
```

For the observability smoke harness, run:

```bash
python scripts/test-observability-alerting.py static
python scripts/test-observability-alerting.py live --docker-exec
python scripts/test-observability-alerting.py full --docker-exec
```

## Scripts

### Secrets
- `ansible/scripts/run-playbook.sh`: wraps `ansible-playbook` with `op run --env-file=ansible/envs/<slug>.env`, resolving secrets from 1Password at invocation time. See `docs/secrets-management.md` for the full picture and the slug → env file mapping.
- `ansible/scripts/sync-1password-to-vault.py.DEPRECATED`: leftover from a since-reverted Ansible Vault approach — kept for historical reference only, not part of the current workflow.

```bash
# Backup Docker volumes
./scripts/backup-volumes.sh
```

## Security

- Docker sockets never exposed publicly
- Management interfaces accessible only via LAN/VPN
- Credentials stored in 1Password, resolved at runtime via `op run` (see `docs/secrets-management.md`)
- TLS for production services via NPM

## License

Private repository - internal use only.
