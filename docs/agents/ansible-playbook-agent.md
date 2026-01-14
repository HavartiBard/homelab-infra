# Ansible Playbook Agent

Agent runbook for linting, dry-running, applying, and verifying Ansible playbooks in this repo. Keep runs scoped, repeatable, and idempotent.

## Scope and responsibilities
- Operate from `ansible/` using `inventory/hosts.yml`.
- Run syntax check (and lint when available), then check mode with `--diff`, then apply.
- Limit impact with `--limit` to explicit hosts/groups; never run broad plays without confirmation.
- Verify services after apply (ports up, containers running) and re-run in check mode to ensure no drift.

## Pre-flight
- Requirements: `ansible`, `community.docker`, `community.general`; optional `ansible-lint`.
- Secrets/env to export before runs (from 1Password): `UNRAID_API_KEY`, `ORBI_PASSWORD`, `OP_SERVICE_ACCOUNT_TOKEN`, `PORTAINER_TOKEN`, `NOTION_TOKEN`, `PROXMOX_API_TOKEN_SECRET`, `PROXMOX_API_HOST`, `PROXMOX_API_USER`, `PROXMOX_API_TOKEN_ID`. Ensure SSH key at `~/.ssh/id_ed25519_homelab` for targets that use it.
- Change into the playbook root: `cd ansible`.

## Standard workflow
1) Pick playbook + limit target:
   - `ansible-playbook playbooks/<playbook>.yml --list-hosts`
   - `ansible-playbook playbooks/<playbook>.yml --list-tasks` (sanity check)
2) Syntax/lint:
   - `ansible-playbook playbooks/<playbook>.yml --syntax-check`
   - `ansible-lint playbooks/<playbook>.yml` (if installed)
3) Dry-run with diffs:  
   `ansible-playbook playbooks/<playbook>.yml --check --diff --limit <host_or_group>`
4) Apply:  
   `ansible-playbook playbooks/<playbook>.yml --diff --limit <host_or_group> -v`
5) Verify + idempotence:
   - Re-run check mode expecting `changed=0`:  
     `ansible-playbook playbooks/<playbook>.yml --check --diff --limit <host_or_group>`
   - Service checks from the table below (use the inventory hostname; replace ports if overridden):
     - `ansible -i inventory/hosts.yml <unraid-host> -m wait_for -a "port=<port> state=started timeout=10"`
     - `ansible -i inventory/hosts.yml <unraid-host> -m shell -a "docker ps --filter 'name=<container>' --format '{{.Names}} {{.Status}}'"`  
     - HTTP services: `curl -fsS http://<ansible_host>:<port>/health` (or `/mcp` for MCP servers)

## Playbook quick reference
| Playbook | Target (inventory) | Required env/vars | Verify hints |
| --- | --- | --- | --- |
| `deploy-unraid-mcp.yml` | `unraid`/`unraid-server` | `UNRAID_API_KEY` | `wait_for port=6970`, `docker ps` for `unraid-mcp`, `curl http://<host>:6970/mcp` |
| `deploy-homelab-mcp.yml` | `unraid`/`unraid-server` | `ORBI_PASSWORD` | `wait_for port=6971`, `docker ps` for `homelab-mcp`, `curl http://<host>:6971/mcp` |
| `deploy-onepassword-mcp.yml` | `unraid`/`unraid-server` | `OP_SERVICE_ACCOUNT_TOKEN` | `wait_for port=6975`, `docker ps` for `onepassword-mcp`, `curl http://<host>:6975/mcp` |
| `deploy-portainer-mcp.yml` | `unraid`/`unraid-server` | `PORTAINER_TOKEN` | `wait_for port=6972`, `docker ps` for `portainer-mcp`, `curl http://<host>:6972/mcp` |
| `deploy-proxmox-mcp.yml` | `unraid-server` | `group_vars/unraid/vault.yml` values set (Proxmox host/user/token) | `wait_for port=6974`, `docker ps` for `mcp-proxmox` |
| `deploy-notion-mcp-public.yml` | `unraid`/`unraid-server` | `NOTION_TOKEN` (auth token comes from defaults/vars) | `wait_for port=3000`, `docker ps` for `notion-mcp-public`, `curl http://<host>:3000/mcp` |
| `deploy-openhands.yml` | `unraid`/`unraid-server` | `.env` with `OPENHANDS_SECRET_KEY`, `OLLAMA_HOST_IP` | `wait_for port=3000`, `docker ps` for `openhands`, `curl http://<host>:3000/health` |
| `deploy-ollama.yml` | `windows-gpu` hosts | `.env` on target (copied from example) | `curl http://<host>:11434/api/tags`, `docker ps` for `ollama-windows` |
| `provision-dns-dhcp.yml` | `localhost` (Proxmox API) | `PROXMOX_API_HOST`, `PROXMOX_API_USER`, `PROXMOX_API_TOKEN_ID`, `PROXMOX_API_TOKEN_SECRET` | Check VMs exist with `pvesh`/`qm list` on Proxmox; rerun play in `--check` after changes |
| `deploy-ssh-keys.yml` | `target_hosts` var (defaults to `unraid`) | SSH public key at `~/.ssh/id_ed25519_homelab.pub` | Confirm login: `ssh -i ~/.ssh/id_ed25519_homelab <user>@<host>` |

## Logging and rollback
- Capture `ansible-playbook` output; for containers, `ansible -i inventory/hosts.yml <host> -m shell -a "docker logs --tail 100 <container>"`.
- If a run misconfigures a service, revert the env/vars change, re-run the last known-good play in check mode, then apply with the corrected vars. For containerized roles, stopping/removing the container and re-running the playbook is safe because data paths live on host volumes.
