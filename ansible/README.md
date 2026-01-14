# Homelab Ansible Playbooks

Infrastructure automation for homelab services.

## Prerequisites

```bash
# Install Ansible
sudo apt install ansible

# Install required collections
ansible-galaxy collection install community.docker community.general
```

## Agent runbook

Use `../docs/agents/ansible-playbook-agent.md` for the standard check → dry-run → apply → verify loop for all playbooks here (including required env vars and post-run service checks).

## Inventory

Hosts are defined in `inventory/hosts.yml`. Current hosts:
- **unraid-server** (192.168.20.14) - Main Unraid server

## Playbooks

### deploy-homelab-mcp.yml

Deploys the Homelab MCP server (Orbi, NPM, Pi-hole tools).

```bash
export ORBI_PASSWORD='<from 1Password: Orbi Login>'
ansible-playbook playbooks/deploy-homelab-mcp.yml
```

### deploy-onepassword-mcp.yml

Deploys the 1Password MCP server.

```bash
export OP_SERVICE_ACCOUNT_TOKEN='<from 1Password>'
ansible-playbook playbooks/deploy-onepassword-mcp.yml
```

### deploy-unraid-mcp.yml

Deploys the Unraid MCP server (GraphQL-based Unraid management).

```bash
export UNRAID_API_KEY='<from 1Password: Unraid GraphQL - Wedge → credential>'
ansible-playbook playbooks/deploy-unraid-mcp.yml
```

**Target:** 192.168.20.14:6970
**Image:** ghcr.io/havartibard/unraid-mcp:latest
**Last Updated:** 2026-01-06 (Tag: 1c13de8)

### provision-dns-dhcp.yml

Provisions the four DNS/DHCP VMs (tt1/tt2/agh1/agh2) on Proxmox using the IP plan in `group_vars/all/dns_dhcp.yml`.

```bash
# Set Proxmox API values (from 1Password; token secret not in git)
export PROXMOX_API_HOST=192.168.20.100
export PROXMOX_API_USER='root@pam'
export PROXMOX_API_TOKEN_ID='root@pam!ansible'
export PROXMOX_API_TOKEN_SECRET='<from 1Password>'

# Optional: toggle guest VLAN NICs for AdGuard in group_vars/all/dns_dhcp.yml
ansible-playbook playbooks/provision-dns-dhcp.yml
```

Assumptions: cloud-init Debian template VMID is set (`dns_dhcp_vm_defaults.template_vmid`), VLAN-aware bridge is `vmbr0`, and VLAN tags 1/20/30 (and optional 40) are trunked to pve-01/pve-02.

## Roles

| Role | Description | Config |
|------|-------------|--------|
| `homelab-mcp` | Orbi, NPM, Pi-hole MCP server | Jinja2 template |
| `onepassword-mcp` | 1Password secrets MCP server | Env vars only |
| `unraid-mcp` | Unraid GraphQL management MCP server | Env vars only |

**Note:** Uses `raw` commands since Unraid lacks Python.
