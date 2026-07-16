# Deployment Quickstart Guide

This guide provides quick commands for common deployment scenarios across the homelab infrastructure.

---

## Jetson Reasoning LLM

**Status:** ✅ Deployed (Ollama + GGUF)
**Last Validated:** 2026-02-08
**Endpoint:** jetson.lab:11434 (192.168.20.169)

**Models Available:**
- `llama3.1:8b-instruct-q4_K_M` - General reasoning
- `qwen2.5-coder:7b-instruct-q4_K_M` - Code generation

### Quick Commands

```bash
# Check Ollama status
ssh james@jetson.lab "systemctl status ollama"

# List models
ssh james@jetson.lab "ollama list"

# Test inference
ssh james@jetson.lab "ollama run llama3.1:8b-instruct-q4_K_M 'What is 2+2?'"

# View memory usage
ssh james@jetson.lab "free -h"
```

### Performance

- **Speed:** 9-12 tokens/sec
- **Latency:** 15-25s per reasoning chain (with gateway overhead)
- **Suitable for:** Agent loops, code generation, analysis
- **Not suitable for:** Real-time chat, interactive debugging

### Enable Remote Access

Currently API is localhost-only. To enable LAN access for OpenClaw integration:

```bash
# Configure remote access
ssh james@jetson.lab "sudo systemctl edit ollama.service"

# Add this in the editor:
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"

# Save and restart
ssh james@jetson.lab "sudo systemctl restart ollama.service"

# Verify from remote host
curl http://192.168.20.169:11434/api/tags
```

### Rollback

N/A - No deployment changes made. This is validation of existing Ollama service.

### Documentation

- **Full validation report:** `docs/jetson-ollama-validation.md`
- **Architecture overview:** `docs/jetson-reasoning-llm.md`

---

## DNS Infrastructure (Technitium + AdGuard)

**Status:** ✅ Production
**Hosts:** tt1, tt2 (Technitium), agh1, agh2 (AdGuard Home)

Secrets below resolve from 1Password via `op run` — see `docs/secrets-management.md`. No manual
`export` needed; use `./scripts/run-playbook.sh <slug> <playbook> <args>` instead of bare
`ansible-playbook`.

### Deploy DNS/DHCP LXCs

```bash
cd /home/james/projects/homelab-infra/ansible

# Syntax check
ansible-playbook playbooks/dns/provision-dns-dhcp.yml --syntax-check

# Dry-run
./scripts/run-playbook.sh dns-dhcp playbooks/dns/provision-dns-dhcp.yml --check --diff

# Deploy
./scripts/run-playbook.sh dns-dhcp playbooks/dns/provision-dns-dhcp.yml --diff -v
```

### Deploy DNS/DHCP Services

```bash
./scripts/run-playbook.sh dns-dhcp playbooks/dns/provision-dns-dhcp-services.yml --diff -v
```

### Deploy AdGuard Configuration

```bash
./scripts/run-playbook.sh adguard playbooks/dns/deploy-adguard-config.yml --diff -v
```

---

## MCP Servers (Unraid)

**Status:** ✅ Production
**Host:** unraid-server (192.168.20.14)

### Deploy All MCP Servers

```bash
cd /home/james/projects/homelab-infra/ansible

# OP_SERVICE_ACCOUNT_TOKEN must already be in your shell env (see docs/secrets-management.md) -
# it's the one bootstrap secret, not an op:// reference.

# Deploy Unraid MCP
./scripts/run-playbook.sh unraid-mcp playbooks/mcp/deploy-unraid-mcp.yml --limit unraid-server --diff -v

# Deploy Homelab MCP
./scripts/run-playbook.sh homelab-mcp playbooks/mcp/deploy-homelab-mcp.yml --limit unraid-server --diff -v

# Deploy 1Password MCP
ansible-playbook playbooks/mcp/deploy-onepassword-mcp.yml --limit unraid-server --diff -v

# Deploy Proxmox MCP
./scripts/run-playbook.sh proxmox-mcp playbooks/mcp/deploy-proxmox-mcp.yml --limit unraid-server --diff -v
```

### Verify MCP Servers

```bash
# Check all MCP containers
ssh -i ~/.ssh/id_ed25519_homelab root@unraid-server "docker ps | grep mcp"

# Check specific MCP logs
ssh -i ~/.ssh/id_ed25519_homelab root@unraid-server "docker logs mcp-unraid"
ssh -i ~/.ssh/id_ed25519_homelab root@unraid-server "docker logs mcp-homelab"
ssh -i ~/.ssh/id_ed25519_homelab root@unraid-server "docker logs mcp-onepassword"
ssh -i ~/.ssh/id_ed25519_homelab root@unraid-server "docker logs mcp-proxmox"
```

---

## Platform Services (NPM, Uptime Kuma)

**Status:** ✅ Production
**Host:** Platform VM (Proxmox)

### Deploy via Docker Compose

Secrets resolve from 1Password via `op.env` (committed, `op://` references only) — see
`docs/secrets-management.md`. `.env` is still copied for non-secret config (ports, TZ).

```bash
cd /home/james/projects/homelab-infra/stacks/platform

# Create .env file for non-secret config
cp .env.example .env
# Edit .env with non-secret values

# Validate compose file
op run --env-file=op.env -- docker compose config

# Deploy stack
op run --env-file=op.env -- docker compose up -d

# View logs
docker compose logs -f
```

### Update Platform Services

```bash
cd /home/james/projects/homelab-infra/stacks/platform

# Pull latest images
docker compose pull

# Recreate containers
op run --env-file=op.env -- docker compose up -d

# Clean up old images
docker image prune -f
```

---

## GPU Workers (Ollama + Open WebUI)

**Status:** ✅ Production
**Host:** spraycheese (WSL2, 192.168.20.50)

### Deploy Ollama + Open WebUI

Secrets resolve from 1Password via `op.env` — see `docs/secrets-management.md`.

```bash
cd /home/james/projects/homelab-infra/stacks/gpu-worker

# Create .env file for non-secret config
cp .env.example .env

# Validate
op run --env-file=op.env -- docker compose config

# Deploy
op run --env-file=op.env -- docker compose up -d

# Check GPU access
docker exec ollama nvidia-smi
```

### Verify GPU Inference

```bash
# Test Ollama
curl http://spraycheese.klsll.com:11434/api/tags

# Test Open WebUI
curl http://spraycheese.klsll.com:8080
```

---

## Common Operations

### Ansible Validation Workflow

```bash
# Standard workflow for any playbook
ansible-playbook <playbook>.yml --syntax-check
ansible-playbook <playbook>.yml --check --diff --limit <host>
ansible-playbook <playbook>.yml --diff --limit <host> -v

# Verify idempotence (expect changed=0)
ansible-playbook <playbook>.yml --check --diff --limit <host>
```

### Generate Secure Passwords

```bash
# 32-character alphanumeric
openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32

# 24-character with special characters
openssl rand -base64 32 | head -c 24
```

### Access 1Password Credentials (AI Agents)

```bash
# Read credential
op read "op://AI Wedge/<credential-name>/credential"

# List available credentials
op item list --vault "AI Wedge" --tags Ansible
```

---

## Troubleshooting

### Ansible Connection Issues

```bash
# Test SSH connectivity
ansible <host> -m ping

# Test with specific SSH key
ansible <host> -m ping --private-key ~/.ssh/id_ed25519_homelab

# Verbose debug
ansible-playbook <playbook>.yml -vvvv
```

### Docker Issues

```bash
# Check Docker daemon
systemctl status docker

# View Docker logs
journalctl -u docker -f

# Restart Docker
sudo systemctl restart docker

# Clean up Docker resources
docker system prune -af --volumes
```

### Network Connectivity

```bash
# Test DNS resolution
dig @192.168.20.2 example.klsll.com
nslookup example.klsll.com 192.168.20.2

# Test DHCP
sudo dhclient -v <interface>

# Check firewall rules
sudo iptables -L -n -v
```

---

## Additional Documentation

- **Full documentation:** `/home/james/projects/homelab-infra/docs/`
- **Ansible roles:** `/home/james/projects/homelab-infra/ansible/roles/`
- **Project README:** `/home/james/projects/homelab-infra/README.md`
- **CLAUDE.md:** Repository guidance for AI agents
