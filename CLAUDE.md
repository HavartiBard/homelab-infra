# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is an Ansible-managed Docker infrastructure for a hybrid homelab spanning Unraid, Proxmox VMs/LXCs, and WSL2 GPU workers. Ansible is the primary deployment mechanism for services requiring dynamic configuration (MCP servers, DNS infrastructure). Portainer stacks in `stacks/` serve as reference deployments for simpler services.

## Architecture

- **Platform VM** (Proxmox): Portainer Server, Nginx Proxy Manager, Uptime Kuma
- **Unraid**: Long-running services, MCP servers, Portainer Agent
- **WSL2 GPU Workers**: Ollama, Open WebUI via Edge Agent
- **DNS LXCs** (Proxmox): tt1/tt2 (Technitium), agh1/agh2 (AdGuard Home)

### DNS Infrastructure

IP plan: `192.168.{1,20,30}.{2,3}` for Technitium, `.{4,5}` for AdGuard (per-VLAN addresses).

```
Client → AdGuard (.4/.5) ─┬─ klsll.com zones ──→ Technitium (.2/.3)
                          └─ external queries ──→ DoH (Cloudflare/Quad9)
```

- **AdGuard Home** (agh1/agh2): Client-facing DNS with filtering, hands off local zones to Technitium
- **Technitium** (tt1/tt2): Authoritative for `klsll.com` subdomains, DHCP server (primary on tt1)

## Directory Structure

```
homelab-infra/
├── ansible/
│   ├── playbooks/          # Deployment orchestration
│   ├── roles/              # Service-specific roles (MCP servers, etc.)
│   ├── files/              # Compose files for Ansible deployments
│   │   ├── dns/            # Technitium/AdGuard compose templates
│   │   ├── openhands/      # OpenHands compose + config
│   │   └── ollama/         # Ollama (Windows) compose
│   └── inventory/          # Host definitions
├── stacks/                 # Portainer reference stacks (secondary)
│   ├── platform/           # Portainer, NPM, Uptime Kuma
│   ├── gpu-worker/         # Ollama + Open WebUI
│   └── monitoring/         # Prometheus, Grafana
├── docker/                 # Custom Dockerfiles only
│   ├── notion-mcp-server/  # Notion MCP custom build
│   └── portainer-mcp/      # Portainer MCP custom build
└── docs/                   # Documentation
```

**Deployment ownership:**
- `ansible/` → Primary deployment mechanism (MCP servers, DNS, OpenHands, Ollama)
- `stacks/` → Reference stacks for Portainer (Platform VM services)
- `docker/` → Custom Dockerfiles only (no compose files)

## Key Commands

### Ansible Playbooks

All playbook operations run from the `ansible/` directory:

```bash
cd ansible

# Standard workflow: syntax → dry-run → apply → verify
ansible-playbook playbooks/<group>/<playbook>.yml --syntax-check
ansible-playbook playbooks/<group>/<playbook>.yml --check --diff --limit <host>
ansible-playbook playbooks/<group>/<playbook>.yml --diff --limit <host> -v

# Verify idempotence (expect changed=0)
ansible-playbook playbooks/<group>/<playbook>.yml --check --diff --limit <host>
```

Common playbooks and their required env vars:

**DNS Infrastructure:**
- `ansible/playbooks/dns/provision-dns-dhcp.yml` → `PROXMOX_API_HOST`, `PROXMOX_API_USER`, `PROXMOX_API_TOKEN_ID`, `PROXMOX_API_TOKEN_SECRET`
- `ansible/playbooks/dns/provision-dns-dhcp-services.yml` → Same Proxmox vars + optional `TECHNITIUM_ADMIN_PASSWORD`
- `ansible/playbooks/dns/deploy-adguard-config.yml` → `ADGUARD_ADMIN_PASSWORD` (or via `op read`)

**MCP Servers:**
- `ansible/playbooks/mcp/deploy-unraid-mcp.yml` → `UNRAID_API_KEY`
- `ansible/playbooks/mcp/deploy-homelab-mcp.yml` → `ORBI_PASSWORD`
- `ansible/playbooks/mcp/deploy-onepassword-mcp.yml` → `OP_SERVICE_ACCOUNT_TOKEN`
- `ansible/playbooks/mcp/deploy-proxmox-mcp.yml` → Uses `group_vars/unraid/vault.yml`

### Docker Compose Stacks

```bash
cd stacks/<stack-name>
cp .env.example .env           # Create env file from template
docker compose config          # Validate compose file
docker compose up -d           # Deploy
docker compose logs -f         # Watch logs
docker compose pull && docker compose up -d  # Update
```

Stacks: `platform/`, `gpu-worker/`, `monitoring/`

### Validation

```bash
# Validate compose file
docker compose config

# Check for missing required env vars
docker compose config 2>&1 | grep -i error

# Generate secure passwords
openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32
```

## Important Conventions

### Topology Awareness

Always be explicit about where services run:
- **Unraid** (192.168.20.14): MCP servers, long-running services
- **Windows GPU hosts**: Heavy LLM inference (Ollama)
- **Proxmox VMs**: Platform services, DNS/DHCP (tt1/tt2/agh1/agh2)

Docker Desktop on WSL2 behaves differently from Linux Docker—don't assume `host.docker.internal` works cross-platform.

### Container Networking

- Use a single named Docker network per deployment for tightly coupled services
- Prefer LAN DNS + reverse proxy over container-to-host hacks
- OpenHands requires mounted `config.toml` for consistent redeploys

### Secrets

- Never hardcode secrets in git—use `.env` files (gitignored) or 1Password
- Mark placeholders as `CHANGEME_*`
- Required env var names use `:?` syntax in compose files to error if missing

### Credential Access for AI Agents

Claude Code and AI agents can read credentials directly from 1Password using the service account:

```bash
# Read a credential via op read
op read "op://AI Wedge/Notion MCP Integration/credential"

# Example in Python
import subprocess
result = subprocess.run(
    ['op', 'read', 'op://AI Wedge/Unraid GraphQL - Wedge/credential'],
    capture_output=True, text=True, check=True
)
api_key = result.stdout.strip()
```

**Available credentials**: All items in the "AI Wedge" vault tagged "Ansible" are accessible. See `ansible/scripts/sync-1password-to-vault.py.DEPRECATED` for the complete mapping.

**Note**: AI agents have read-only access to 1Password via the service account (`OP_SERVICE_ACCOUNT_TOKEN`). To create new credentials, manually add them to 1Password and tag them "Ansible" or "Generated".

### Ansible Notes

- Unraid lacks Python—roles use `raw` commands
- SSH key: `~/.ssh/id_ed25519_homelab`
- Inventory: `ansible/inventory/hosts.yml`
- Always use `--limit` to scope playbook runs

## Inventory Groups

| Group | Hosts | Purpose |
|-------|-------|---------|
| `unraid` | unraid-server | Main NAS, MCP servers |
| `pve` | pve-01, pve-02 | Proxmox hypervisors |
| `tt` | tt1, tt2 | Technitium DNS (primary/secondary) |
| `agh` | agh1, agh2 | AdGuard Home |
| `windows_gpu` | spraycheese | WSL2 GPU workers |

## Output Format

When completing tasks, provide:
- **Summary**: What changed
- **Deploy/Run**: Exact commands
- **Verify**: Health checks (curl endpoints, docker ps, logs)
- **Rollback**: How to revert safely
