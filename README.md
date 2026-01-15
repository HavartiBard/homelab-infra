# Homelab Infrastructure

Portainer-managed Docker infrastructure for hybrid homelab: Unraid, Proxmox VMs, and WSL2 GPU workers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           LAN / VPN Only                            │
├─────────────────────────────────────────────────────────────────────┤
│   Platform VM (Proxmox)          Endpoints                          │
│   ├── Portainer Server ◄──────── Unraid (Agent)                     │
│   ├── Nginx Proxy Manager        Proxmox VMs (Agent)                │
│   └── Uptime Kuma                WSL2 Workers (Edge Agent)          │
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
4. **Add Agents** on Unraid and other Docker hosts
5. **Deploy GPU Workers** on WSL2 with Edge Agent

## Repository Structure

```
homelab-infra/
├── stacks/                    # Docker Compose stacks (source of truth)
│   ├── platform/              # Core infra: Portainer, NPM, Kuma
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
| **platform** | Portainer, NPM, Uptime Kuma | Platform VM |
| **gpu-worker** | Ollama, Open WebUI | WSL2 GPU workers |
| **monitoring** | Prometheus, Grafana, Node Exporter | Platform VM |

## Ansible Roles

| Role | Purpose |
|------|---------|
| **adguard** | Configure AdGuard Home (DNS filtering, upstreams) |
| **technitium** | Configure Technitium DNS (zones, DHCP) |
| **unraid-mcp** | Deploy Unraid MCP server container |
| **proxmox-mcp** | Deploy Proxmox MCP server container |
| **notion-mcp** | Deploy Notion MCP server container |
| **onepassword-mcp** | Deploy 1Password MCP server container |
| **homelab-mcp** | Deploy Homelab MCP aggregator container |

## Ansible Playbooks

| Playbook | Purpose |
|----------|---------|
| **provision-dns-dhcp.yml** | Create DNS/DHCP LXCs on Proxmox (tt1/tt2/agh1/agh2) |
| **provision-dns-dhcp-services.yml** | Deploy Docker + Technitium/AdGuard in LXCs |
| **deploy-adguard-config.yml** | Configure AdGuard upstreams and filters |
| **deploy-*-mcp.yml** | Deploy MCP server containers to Unraid |

## Key Principles

- **Git as Source of Truth** - Portainer deploys stacks from this repo
- **LAN-Only Access** - Management interfaces never exposed publicly
- **Secrets via env + vault** - Credentials never committed in plaintext; 1Password is source of truth, sync into encrypted vaults or export env vars before runs
- **Agent Architecture** - Standard agents for always-on, Edge for on-demand

## Documentation

- [**Runbook**](docs/runbook.md) - Complete deployment guide from zero to working
- [**Plan**](docs/plan.md) - Architecture decisions and design
- [**Network Ports**](docs/network-ports.md) - Port reference and firewall rules
- [**Checklist**](docs/checklist.md) - Deployment verification and smoke tests

## Deploy a Stack

### From Portainer (Recommended)

1. Add Environment → Select endpoint
2. Stacks → Add Stack → Repository
3. Enter repo URL, branch, compose path
4. Add environment variables from `.env.example`
5. Deploy

### From Command Line

```bash
cd stacks/<stack-name>
cp .env.example .env
# Edit .env with your values
docker compose up -d
```

## Scripts

### Secrets & Vault helper
- `ansible/scripts/sync-1password-to-vault.py`: Sync Ansible-tagged 1Password items into encrypted vaults (env → vault at runtime; no live `op` calls).
  - Write to unraid vault with backup + prompt:
    ```bash
    ANSIBLE_VAULT_PASSWORD_FILE=ansible/scripts/ansible-vault-password.sh \
    ansible/scripts/sync-1password-to-vault.py --group unraid
    ```
  - Print-only:
    ```bash
    ansible/scripts/sync-1password-to-vault.py --group unraid --print-only
    ```

```bash
# Install Portainer Agent on Linux hosts
./scripts/install-portainer-agent.sh

# Install Edge Agent for WSL2/remote workers
./scripts/install-edge-agent.sh <EDGE_ID> <EDGE_KEY>

# Backup Docker volumes
./scripts/backup-volumes.sh
```

## Security

- Docker sockets never exposed publicly
- Portainer accessible only via LAN/VPN
- Agent ports restricted via firewall
- Credentials stored in 1Password, loaded via `.env`
- TLS for production services via NPM

## License

Private repository - internal use only.
