# Homelab Ansible Playbooks

Infrastructure automation for homelab services.

## Prerequisites

```bash
# Install Ansible
sudo apt install ansible

# Install Docker collection
ansible-galaxy collection install community.docker
```

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

## Roles

| Role | Description | Config |
|------|-------------|--------|
| `homelab-mcp` | Orbi, NPM, Pi-hole MCP server | Jinja2 template |
| `onepassword-mcp` | 1Password secrets MCP server | Env vars only |
| `unraid-mcp` | Unraid GraphQL management MCP server | Env vars only |

**Note:** Uses `raw` commands since Unraid lacks Python.
