# Homelab Ansible Playbooks

Infrastructure automation for homelab services.

## Prerequisites

```bash
# Install Ansible
sudo apt install ansible

# Install required collections
ansible-galaxy collection install community.docker community.general
```

## Credential Management

This repository uses a 1Password Service Account for automated credential access. No vault files or manual `op signin` required.

### One-time Setup

1. Ensure `OP_SERVICE_ACCOUNT_TOKEN` is exported in your `~/.bashrc`:
   ```bash
   echo 'export OP_SERVICE_ACCOUNT_TOKEN="ops-YOUR-TOKEN-HERE"' >> ~/.bashrc
   source ~/.bashrc
   ```

2. Verify the service account works:
   ```bash
   op read "op://AI Wedge/Notion MCP Integration/credential"
   # Should output the token without prompting for signin
   ```

### Usage

All playbooks automatically read credentials from 1Password. Just run them:

```bash
# Credentials are automatically fetched from 1Password
ansible-playbook playbooks/mcp/deploy-notion-mcp-public.yml
```

### Override Credentials for Testing

```bash
# Override a specific credential via environment variable
NOTION_TOKEN="test-token" ansible-playbook playbooks/mcp/deploy-notion-mcp-public.yml
```

### How It Works

Roles use a two-tier fallback pattern:
1. **Environment variable** (e.g., `NOTION_TOKEN`) - highest priority
2. **Direct 1Password lookup** via `op read` - automatic via service account
3. **Empty fallback** - role fails with clear error if credential missing

No vault files, no sync script, no manual credential export needed.

## Agent runbook

Use `../docs/agents/ansible-playbook-agent.md` for the standard check → dry-run → apply → verify loop for all playbooks here (including required env vars and post-run service checks).

## Inventory

Hosts are defined in `inventory/hosts.yml`. Current hosts/groups:
- **unraid**: `unraid-server` (192.168.20.14, root, key `~/.ssh/id_ed25519_homelab`)
- **windows_gpu**: `spraycheese` (192.168.20.50, ssh as james)
- **pve**: `pve-01` (192.168.20.100, root), `pve-02` (192.168.20.101, root)
- **edge_devices**: `jetson` (192.168.20.5, james, ssh key)
- **tt**: `tt1` (192.168.20.2), `tt2` (192.168.20.3) — python3.12, sudo
- **agh**: `agh1` (192.168.20.4), `agh2` (192.168.20.5) — python3.12, sudo

## Windows Playbooks

### setup-ssh.yml (Windows GPU Worker)

Enables OpenSSH Server on the Windows GPU worker (spraycheese) and configures it for SSH key-based authentication.

**Prerequisites:**
- WinRM must be enabled on the Windows system (default on Server, optional on Pro)
- `pywinrm` package installed: `pip install pywinrm`

```bash
# Set Windows credentials
export ANSIBLE_WINDOWS_USER='james'
export ANSIBLE_WINDOWS_PASSWORD='<your-password>'

# Run the SSH setup playbook
ansible-playbook playbooks/windows/setup-ssh.yml --limit spraycheese -v
```

**What it does:**
- ✅ Installs OpenSSH Server (Windows optional component)
- ✅ Starts and enables `sshd` service with auto-start
- ✅ Creates Windows Firewall rule allowing port 22
- ✅ Installs SSH public key from `~/.ssh/id_ed25519_homelab.pub`
- ✅ Configures key-based auth only (disables password authentication)
- ✅ Verifies SSH is listening and functional

**After setup, SSH access:**
```bash
ssh -i ~/.ssh/id_ed25519_homelab james@192.168.20.50
```

See `docs/windows-ssh-setup.md` for detailed setup and troubleshooting.

## Linux/Unraid Playbooks

### deploy-homelab-mcp.yml

Deploys the Homelab MCP server (Orbi, NPM, Pi-hole tools).

```bash
export ORBI_PASSWORD='<from 1Password: Orbi Login>'
ansible-playbook playbooks/mcp/deploy-homelab-mcp.yml
```

### deploy-onepassword-mcp.yml

Deploys the 1Password MCP server.

```bash
export OP_SERVICE_ACCOUNT_TOKEN='<from 1Password>'
ansible-playbook playbooks/mcp/deploy-onepassword-mcp.yml
```

### deploy-unraid-mcp.yml

Deploys the Unraid MCP server (GraphQL-based Unraid management).

```bash
export UNRAID_API_KEY='<from 1Password: Unraid GraphQL - Wedge → credential>'
ansible-playbook playbooks/mcp/deploy-unraid-mcp.yml
```

### deploy-n8n.yml

Deploys N8N on Unraid (macvlan) and optionally creates NPM + Technitium DNS entries.

```bash
export NPM_IDENTITY='<npm-email>'
export NPM_SECRET='<npm-password>'
export TECHNITIUM_USER='<technitium-user>'
export TECHNITIUM_PASSWORD='<technitium-password>'
ansible-playbook playbooks/deploy-n8n.yml
```

**Target:** 192.168.20.14:6970
**Image:** ghcr.io/havartibard/unraid-mcp:latest
**Last Updated:** 2026-01-06 (Tag: 1c13de8)

### deploy-npm-unraid.yml

Deploys Nginx Proxy Manager on Unraid with a dedicated macvlan/ipvlan IP and optional ACME issuer. The playbook creates required directories, templated `docker-compose.yml`, pulls images, and performs a health check via the dedicated IP/port.

```bash
ansible-playbook playbooks/platform/deploy-npm-unraid.yml
```

**Notes:** Update `ansible/group_vars/unraid.yml` with the desired `npm_*` variables before running. The playbook relies on the `unraid` host group and expects SSH access as configured in `inventory/hosts.yml`. If the Unraid host lacks `docker compose`, the role will download a pinned `docker-compose` binary to `{{ compose_bin_path }}`. Optional: enable `npm_manage_proxies` / `npm_manage_dns` and place per-service configs in `ansible/files/npm/services/` to create proxy hosts and Technitium DNS records using the NPM API.

**Proxy/DNS template:** Copy `ansible/files/npm/templates/_template.yml` to a new filename under `ansible/files/npm/services/`, set domains/targets/cert name, and rerun this playbook. The role will reuse existing certs when domain sets match (to avoid duplicate wildcards) and manage both NPM proxy hosts and Technitium DNS.

### deploy-gitea.yml

Deploys Gitea on Unraid using a Postgres backend plus the built-in container registry. The service runs on the same macvlan segment as NPM, so keep `gitea_ip` and `gitea_network_*` aligned with the VLAN20 plan and route TLS through Nginx Proxy Manager.

```bash
ansible-playbook playbooks/platform/deploy-gitea.yml
```

**Notes:** Supply secrets via the new `Gitea Service Credentials` 1Password item (fields `db_password` and `admin_password`) or set `GITEA_DB_PASSWORD`/`GITEA_ADMIN_PASSWORD` in the shell before running. Update `ansible/group_vars/unraid/unraid.yml` if you need to change the dedicated IP/domain. See `docs/services/gitea.md` for full architecture, DNS, and registry guidance.
After deploying Gitea, run `ansible-playbook playbooks/services/update-gitea-proxy.yml` so the `code.klsll.com` and `registry.klsll.com` proxy hosts + DNS records are created via the npm role. Re-run the playbook whenever the endpoints or IPs change.

### deploy-sprite-smith.yml

Deploys the Sprite Smith web app on Unraid and points it at the ComfyUI backend on the Windows GPU host.

```bash
ansible-playbook playbooks/platform/deploy-sprite-smith.yml
```

**Target:** 192.168.20.14:3001
**ComfyUI:** `http://spraycheese.lab.klsll.com:8188`

### 1Password item naming (avoid breakage)

Playbooks and roles assume stable 1Password item names but only consume them via env or pre-populated vault values. Keep these items consistent so the sync helper can populate vault vars:
- `Nginx Proxy Manager Admin` (fields: `username`, `password`)
- `DNS Automation Credential` (Technitium API token; field: `credential`/`password` token)
- `Cloudflare DNS Token` (field: `credential`/API token)
- `AdGuard Admin` (fields: `username`, `password`)
- `Orbi Login` (fields: `username`, `password`)
- `Notion MCP Integration` (field: `credential`)
- `OP_SERVICE_ACCOUNT_TOKEN` (field: `credential`)
- `Portainer API Token` (field: `credential`)
- `Proxmox MCP Token` (fields: `host`, `port`, `username`, `token_name`, `credential`, `allow_elevated`)
- `Unraid GraphQL - Wedge` (field: `credential`)

When adding a new service, pick a clear, purpose-specific item name, tag it `Ansible`, and add it to the sync helper map so vault vars can be refreshed from 1Password.

## Credential map (1Password)

| Env/var | 1Password item | Field(s) used | Playbooks/roles |
| --- | --- | --- | --- |
| `ORBI_PASSWORD` | Orbi Login | password | `ansible/playbooks/mcp/deploy-homelab-mcp.yml` (homelab-mcp role) |
| `OP_SERVICE_ACCOUNT_TOKEN` | OP_SERVICE_ACCOUNT_TOKEN | credential | `ansible/playbooks/mcp/deploy-onepassword-mcp.yml` |
| `UNRAID_API_KEY` | Unraid GraphQL - Wedge | credential | `ansible/playbooks/mcp/deploy-unraid-mcp.yml` |
| `NPM_ADMIN_EMAIL`/`NPM_ADMIN_PASSWORD` | Nginx Proxy Manager Admin | username, password | `ansible/playbooks/platform/deploy-npm-unraid.yml` (npm role) |
| `TECHNITIUM_API_TOKEN` / `TECHNITIUM_ADMIN_PASSWORD` | DNS Automation Credential | credential (token) and/or password | `deploy-npm-unraid.yml` (npm role, Technitium DNS) |
| `CLOUDFLARE_API_TOKEN` | Cloudflare DNS Token | credential | `deploy-npm-unraid.yml` (npm role, cert DNS challenge) |
| `PROXMOX_MCP_*` (HOST/PORT/USER/TOKEN_NAME/TOKEN_VALUE/ALLOW_ELEVATED) | Proxmox MCP Token | host, port, username, token_name, credential, allow_elevated | `deploy-proxmox-mcp.yml` |
| `PROXMOX_API_TOKEN_SECRET` (+ host/user/id envs) | Proxmox API (root@pam) | secret/token field | `provision-dns-dhcp.yml`, `provision-dns-dhcp-services.yml` |
| `NOTION_TOKEN` | Notion MCP Integration | credential/token | `deploy-notion-mcp-public.yml` |
| `ADGUARD_ADMIN_USER` / `ADGUARD_ADMIN_PASSWORD` | AdGuard Admin | username, password | `deploy-adguard-config.yml` |
| `ORBI_USERNAME` / `ORBI_PASSWORD` | Orbi Login | username, password | `deploy-homelab-mcp.yml` (read from 1Password item fields) |
| `PORTAINER_TOKEN` | Portainer API Token | credential | `deploy-portainer-mcp.yml` |
| `UNRAID_API_KEY` | Unraid GraphQL - Wedge | credential | `deploy-unraid-mcp.yml` |

Notes:
- Keep item names aligned with `*_op_item` in `group_vars`/defaults. If you rename an item, update the var and rerun the playbook.
- Some roles allow either a token (preferred) or a password login; provide the token when possible.

### provision-dns-dhcp.yml

Provisions the four DNS/DHCP VMs (tt1/tt2/agh1/agh2) on Proxmox using the IP plan in `group_vars/all/dns_dhcp.yml`.

```bash
# Set Proxmox API values (from 1Password; token secret not in git)
export PROXMOX_API_HOST=192.168.20.100
export PROXMOX_API_USER='root@pam'
export PROXMOX_API_TOKEN_ID='root@pam!ansible'
export PROXMOX_API_TOKEN_SECRET='<from 1Password>'

# Optional: toggle guest VLAN NICs for AdGuard in group_vars/all/dns_dhcp.yml
ansible-playbook playbooks/dns/provision-dns-dhcp.yml
```

Assumptions: cloud-init Debian template VMID is set (`dns_dhcp_vm_defaults.template_vmid`), VLAN-aware bridge is `vmbr0`, and VLAN tags 1/20/30 (and optional 40) are trunked to pve-01/pve-02.

## Roles

| Role | Description | Config |
|------|-------------|--------|
| `homelab-mcp` | Orbi, NPM, Pi-hole MCP server | Jinja2 template |
| `n8n-unraid` | N8N container on Unraid (macvlan) | Env vars + defaults |
| `onepassword-mcp` | 1Password secrets MCP server | Env vars only |
| `unraid-mcp` | Unraid GraphQL management MCP server | Env vars only |

**Note:** Uses `raw` commands since Unraid lacks Python.
