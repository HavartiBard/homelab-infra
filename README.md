# Homelab Infrastructure

Portainer-managed Docker infrastructure for hybrid homelab: Unraid, Proxmox VMs, and WSL2 GPU workers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                           LAN / VPN Only                             │
├─────────────────────────────────────────────────────────────────────┤
│   Platform VM (Proxmox)          Endpoints                           │
│   ├── Portainer Server ◄──────── Unraid (Agent)                     │
│   ├── Nginx Proxy Manager        Proxmox VMs (Agent)                │
│   ├── Technitium DNS             WSL2 Workers (Edge Agent)          │
│   └── Uptime Kuma                                                    │
└─────────────────────────────────────────────────────────────────────┘
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
│   ├── platform/              # Core infra: Portainer, NPM, DNS, Kuma
│   ├── gpu-worker/            # AI/ML: Ollama, Open WebUI
│   └── monitoring/            # Observability: Prometheus, Grafana
├── ansible/                   # Ansible automation
│   ├── playbooks/             # Deployment playbooks
│   └── roles/                 # MCP server roles (unraid, proxmox, notion, etc.)
├── docker/                    # Standalone compose files and Dockerfiles
├── configs/                   # IDE/tool configuration files
├── portainer/                 # Portainer stack templates
├── scripts/                   # Helper scripts
│   ├── install-portainer-agent.sh
│   ├── install-edge-agent.sh
│   ├── gaming-toggle.sh
│   └── backup-volumes.sh
└── docs/                      # Documentation
    ├── runbook.md             # Step-by-step deployment guide
    ├── plan.md                # Architecture and design
    ├── network-ports.md       # Port reference
    └── checklist.md           # Deployment verification checklist
```

## Stacks

| Stack | Purpose | Deploy To |
|-------|---------|-----------|
| **platform** | Portainer, NPM, Technitium DNS, Uptime Kuma | Platform VM |
| **gpu-worker** | Ollama, Open WebUI | WSL2 GPU workers |
| **monitoring** | Prometheus, Grafana, Node Exporter | Platform VM |

## Ansible Roles

| Role | Purpose |
|------|---------|  
| **unraid-mcp** | Deploy Unraid MCP server container |
| **proxmox-mcp** | Deploy Proxmox MCP server container |
| **notion-mcp** | Deploy Notion MCP server container |
| **onepassword-mcp** | Deploy 1Password MCP server container |
| **homelab-mcp** | Deploy Homelab MCP aggregator container |

## Key Principles

- **Git as Source of Truth** - Portainer deploys stacks from this repo
- **LAN-Only Access** - Management interfaces never exposed publicly
- **Secrets via .env** - Credentials never committed to Git
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

```bash
# Install Portainer Agent on Linux hosts
./scripts/install-portainer-agent.sh

# Install Edge Agent for WSL2/remote workers
./scripts/install-edge-agent.sh <EDGE_ID> <EDGE_KEY>

# Toggle GPU workloads for gaming
./scripts/gaming-toggle.sh stop   # Before gaming
./scripts/gaming-toggle.sh start  # After gaming

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
