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

This repository uses **1Password Environments** — see `../docs/secrets-management.md` for the full
picture. Short version:

1. One-time setup — export the bootstrap secret in your shell profile:
   ```bash
   echo 'export OP_SERVICE_ACCOUNT_TOKEN="ops-YOUR-TOKEN-HERE"' >> ~/.bashrc
   source ~/.bashrc
   op read "op://AI Wedge/Unraid GraphQL - Wedge/credential"  # smoke test
   ```

2. Run playbooks that need secrets through the wrapper script instead of `ansible-playbook`
   directly:
   ```bash
   ./scripts/run-playbook.sh unraid-mcp playbooks/mcp/deploy-unraid-mcp.yml
   ```
   `unraid-mcp` here is a slug mapping to `ansible/envs/unraid-mcp.env` — see
   `../docs/secrets-management.md` for the full slug table. Playbooks with no secrets are
   unaffected and keep running via plain `ansible-playbook ...`.

3. Override a resolved secret for testing:
   ```bash
   UNRAID_API_KEY="test-key" ./scripts/run-playbook.sh unraid-mcp playbooks/mcp/deploy-unraid-mcp.yml
   ```

Roles read credentials via `lookup('ansible.builtin.env', 'VAR_NAME')` with no fallback — a
missing/misnamed 1Password reference fails the role's assert immediately instead of deploying with
an empty secret.

## Agent runbook

Use `../docs/agents/ansible-playbook-agent.md` for the standard check → dry-run → apply → verify loop for all playbooks here (including required env vars and post-run service checks).

## Inventory

Hosts are defined in `inventory/hosts.yml`. Current hosts/groups:
- **unraid**: `unraid-server` (192.168.20.14, root, key `~/.ssh/id_ed25519_homelab`)
- **windows_gpu**: `spraycheese` (192.168.20.50, ssh as james)
- **pve**: `pve-01` (192.168.20.100, root), `pve-02` (192.168.20.101, root)
- **edge_devices**: `jetson.lab` (192.168.20.169, james, ssh key)
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
./scripts/run-playbook.sh homelab-mcp playbooks/mcp/deploy-homelab-mcp.yml
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
./scripts/run-playbook.sh unraid-mcp playbooks/mcp/deploy-unraid-mcp.yml
```

**Target:** 192.168.20.14:6970
**Image:** ghcr.io/havartibard/unraid-mcp:latest
**Last Updated:** 2026-01-06 (Tag: 1c13de8)

### deploy-npm.yml

Deploys Nginx Proxy Manager on Unraid with a dedicated macvlan/ipvlan IP and optional ACME issuer. The playbook creates required directories, templated `docker-compose.yml`, pulls images, and performs a health check via the dedicated IP/port.

```bash
./scripts/run-playbook.sh npm playbooks/platform/deploy-npm.yml
```

**Notes:** Update `ansible/group_vars/unraid.yml` with the desired `npm_*` variables before running. The playbook relies on the `unraid` host group and expects SSH access as configured in `inventory/hosts.yml`. If the Unraid host lacks `docker compose`, the role will download a pinned `docker-compose` binary to `{{ compose_bin_path }}`. Optional: enable `npm_manage_proxies` / `npm_manage_dns` and place per-service configs in `ansible/files/npm/services/` to create proxy hosts and Technitium DNS records using the NPM API.

**Proxy/DNS template:** Copy `ansible/files/npm/templates/_template.yml` to a new filename under `ansible/files/npm/services/`, set domains/targets/cert name, and rerun this playbook. The role will reuse existing certs when domain sets match (to avoid duplicate wildcards) and manage both NPM proxy hosts and Technitium DNS.

### deploy-gitea.yml

Deploys Gitea on Unraid using a Postgres backend plus the built-in container registry. The service runs on the same macvlan segment as NPM, so keep `gitea_ip` and `gitea_network_*` aligned with the VLAN20 plan and route TLS through Nginx Proxy Manager.

```bash
./scripts/run-playbook.sh gitea playbooks/platform/deploy-gitea.yml
```

**Notes:** Secrets (`GITEA_DB_PASSWORD` from `Gitea DB Credentials`, `GITEA_ADMIN_PASSWORD` from `Gitea Service Credentials`) resolve from 1Password via `ansible/envs/gitea.env` — see `../docs/secrets-management.md`. Update `ansible/group_vars/unraid/unraid.yml` if you need to change the dedicated IP/domain. See `docs/services/gitea.md` for full architecture, DNS, and registry guidance.
After deploying Gitea, run `ansible-playbook playbooks/services/update-gitea-proxy.yml` so the `code.klsll.com` and `registry.klsll.com` proxy hosts + DNS records are created via the npm role. Re-run the playbook whenever the endpoints or IPs change.

### deploy-sprite-smith.yml

Deploys the Sprite Smith web app on Unraid and points it at the ComfyUI backend on the Windows GPU host.

```bash
ansible-playbook playbooks/platform/deploy-sprite-smith.yml
```

**Target:** 192.168.20.14:3001
**ComfyUI:** `http://spraycheese.lab.klsll.com:8188`

### deploy-personal-agent-llm.yml

Deploys a dedicated Qwen3.6 MTP `llama-server` endpoint on goudai for personal coding agents. This is separate from native Ollama, which remains focused on Open WebUI.

```bash
ansible-playbook playbooks/ai/deploy-personal-agent-llm.yml --limit goudai -v
```

**Target:** 192.168.20.150:8010/v1
**Model:** `ggml-org/Qwen3.6-27B-MTP-GGUF:BF16`
**LiteLLM alias:** `qwen/qwen3.6-27b-mtp`

### deploy-phoenix.yml

Deploys Arize Phoenix on Unraid for LLM traces, datasets, experiments, and eval score history.

```bash
ansible-playbook playbooks/ai/deploy-phoenix.yml --limit unraid -v
```

**Target:** 192.168.20.14:6006
**OTLP gRPC:** 192.168.20.14:4317

### deploy-promptfoo.yml

Deploys Promptfoo on Unraid for custom prompt/model/use-case comparison runs.

```bash
ansible-playbook playbooks/ai/deploy-promptfoo.yml --limit unraid -v
```

**Target:** 192.168.20.14:15500

### deploy-lm-eval-harness.yml

Deploys a persistent EleutherAI lm-evaluation-harness runner on Unraid for standardized model/settings baselines. It exposes no host port; configs, results, and cache live under `/mnt/user/appdata/lm-eval-harness`.

```bash
ansible-playbook playbooks/ai/deploy-lm-eval-harness.yml --limit unraid -v
```

**Runner:** `docker exec -it lm-eval-harness bash`

### 1Password item naming

When adding a new service, pick a clear, purpose-specific 1Password item name, tag it `Ansible`,
and add a matching `ansible/envs/<service>.env` (see the pattern in any existing role's
`defaults/main.yml`). See `../docs/secrets-management.md` for the complete, current slug → env
file → item mapping — don't duplicate that table here, it goes stale fast.

### provision-dns-dhcp.yml

Provisions the four DNS/DHCP VMs (tt1/tt2/agh1/agh2) on Proxmox using the IP plan in `group_vars/all/dns_dhcp.yml`.

```bash
# Optional: toggle guest VLAN NICs for AdGuard in group_vars/all/dns_dhcp.yml
./scripts/run-playbook.sh dns-dhcp playbooks/dns/provision-dns-dhcp.yml
```

Assumptions: cloud-init Debian template VMID is set (`dns_dhcp_vm_defaults.template_vmid`), VLAN-aware bridge is `vmbr0`, and VLAN tags 1/20/30 (and optional 40) are trunked to pve-01/pve-02.

## Roles

| Role | Description | Config |
|------|-------------|--------|
| `homelab-mcp` | Orbi, NPM, Pi-hole MCP server | Jinja2 template |
| `onepassword-mcp` | 1Password secrets MCP server | Env vars only |
| `unraid-mcp` | Unraid GraphQL management MCP server | Env vars only |
| `searxng-mcp` | Deploy SearXNG metasearch engine + MCP adapter | unraid |
| `phoenix` | Arize Phoenix LLM observability and eval store | unraid |
| `promptfoo` | Promptfoo custom model/prompt comparison UI | unraid |
| `lm-eval-harness` | EleutherAI benchmark runner for model/settings baselines | unraid |

**Note:** Uses `raw` commands since Unraid lacks Python.

## Director Fragment Export

Export MCP endpoints from homelab-infra role defaults into the
`director-playbooks` repo as a generated fragment:

```bash
ansible/scripts/export-director-mcp-fragment.py
```

Default output:
- `../director-playbooks/director/config/fragments/15-homelab-mcps.generated.yaml`

Useful overrides:

```bash
ansible/scripts/export-director-mcp-fragment.py \\
  --output /path/to/director-playbooks/director/config/fragments/15-homelab-mcps.generated.yaml \\
  --unraid-host 192.168.20.14
```
