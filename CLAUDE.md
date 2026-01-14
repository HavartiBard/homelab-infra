# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a Portainer-managed Docker infrastructure for a hybrid homelab spanning Unraid, Proxmox VMs, and WSL2 GPU workers. Git is the source of truth—Portainer deploys stacks from this repo.

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

## Key Commands

### Ansible Playbooks

All playbook operations run from the `ansible/` directory:

```bash
cd ansible

# Standard workflow: syntax → dry-run → apply → verify
ansible-playbook playbooks/<playbook>.yml --syntax-check
ansible-playbook playbooks/<playbook>.yml --check --diff --limit <host>
ansible-playbook playbooks/<playbook>.yml --diff --limit <host> -v

# Verify idempotence (expect changed=0)
ansible-playbook playbooks/<playbook>.yml --check --diff --limit <host>
```

Common playbooks and their required env vars:

**DNS Infrastructure:**
- `provision-dns-dhcp.yml` → `PROXMOX_API_HOST`, `PROXMOX_API_USER`, `PROXMOX_API_TOKEN_ID`, `PROXMOX_API_TOKEN_SECRET`
- `provision-dns-dhcp-services.yml` → Same Proxmox vars + optional `TECHNITIUM_ADMIN_PASSWORD`
- `deploy-adguard-config.yml` → `ADGUARD_ADMIN_PASSWORD` (or via `op read`)

**MCP Servers:**
- `deploy-unraid-mcp.yml` → `UNRAID_API_KEY`
- `deploy-homelab-mcp.yml` → `ORBI_PASSWORD`
- `deploy-onepassword-mcp.yml` → `OP_SERVICE_ACCOUNT_TOKEN`
- `deploy-proxmox-mcp.yml` → Uses `group_vars/unraid/vault.yml`

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
