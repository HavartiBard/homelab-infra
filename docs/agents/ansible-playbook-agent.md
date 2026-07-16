# Ansible Playbook Agent

Agent runbook for linting, dry-running, applying, and verifying Ansible playbooks in this repo. Keep runs scoped, repeatable, and idempotent.

## Scope and responsibilities
- Operate from `ansible/` using `inventory/hosts.yml`.
- Run syntax check (and lint when available), then check mode with `--diff`, then apply.
- Limit impact with `--limit` to explicit hosts/groups; never run broad plays without confirmation.
- Verify services after apply (ports up, containers running) and re-run in check mode to ensure no drift.

## Pre-flight
- Requirements: `ansible`, `community.docker`, `community.general`; optional `ansible-lint`.
- Secrets resolve from 1Password via `op run` — see `docs/secrets-management.md` for the full
  picture. One bootstrap secret must already be in your shell env: `OP_SERVICE_ACCOUNT_TOKEN`.
  Playbooks that need other secrets are run through `./scripts/run-playbook.sh <slug> <playbook>
  <args>` instead of bare `ansible-playbook` — see the table below for each playbook's slug.
- Ensure SSH key at `~/.ssh/id_ed25519_homelab` for targets that use it.
- Change into the playbook root: `cd ansible`.

## Standard workflow
1) Pick playbook + limit target:
   - `ansible-playbook playbooks/<group>/<playbook>.yml --list-hosts`
   - `ansible-playbook playbooks/<group>/<playbook>.yml --list-tasks` (sanity check)
2) Syntax/lint:
   - `ansible-playbook playbooks/<group>/<playbook>.yml --syntax-check`
   - `ansible-lint playbooks/<group>/<playbook>.yml` (if installed)
3) Dry-run with diffs (prefix with `./scripts/run-playbook.sh <slug>` if the playbook needs secrets):
   `ansible-playbook playbooks/<group>/<playbook>.yml --check --diff --limit <host_or_group>`
4) Apply:  
   `ansible-playbook playbooks/<group>/<playbook>.yml --diff --limit <host_or_group> -v`
5) Verify + idempotence:
   - Re-run check mode expecting `changed=0`:  
     `ansible-playbook playbooks/<group>/<playbook>.yml --check --diff --limit <host_or_group>`
   - Service checks from the table below (use the inventory hostname; replace ports if overridden):
     - `ansible -i inventory/hosts.yml <unraid-host> -m wait_for -a "port=<port> state=started timeout=10"`
     - `ansible -i inventory/hosts.yml <unraid-host> -m shell -a "docker ps --filter 'name=<container>' --format '{{.Names}} {{.Status}}'"`  
     - HTTP services: `curl -fsS http://<ansible_host>:<port>/health` (or `/mcp` for MCP servers)

## Playbook quick reference
| Playbook | Target (inventory) | Secrets slug (`run-playbook.sh <slug>`) | Verify hints |
| --- | --- | --- | --- |
| `ansible/playbooks/mcp/deploy-unraid-mcp.yml` | `unraid`/`unraid-server` | `unraid-mcp` | `wait_for port=6970`, `docker ps` for `unraid-mcp`, `curl http://<host>:6970/mcp` |
| `ansible/playbooks/mcp/deploy-homelab-mcp.yml` | `unraid`/`unraid-server` | `homelab-mcp` | `wait_for port=6971`, `docker ps` for `homelab-mcp`, `curl http://<host>:6971/mcp` |
| `ansible/playbooks/mcp/deploy-onepassword-mcp.yml` | `unraid`/`unraid-server` | none — needs `OP_SERVICE_ACCOUNT_TOKEN` directly (it's the bootstrap secret itself) | `docker ps` for `onepassword-mcp` and `mcp-proxy`, `curl -H 'Accept: application/json' -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"verify","version":"1"}}}' http://<host>:6980/servers/onepassword/mcp` |
| `ansible/playbooks/mcp/deploy-proxmox-mcp.yml` | `unraid-server` | `proxmox-mcp` | `wait_for port=6974`, `docker ps` for `mcp-proxmox` |
| `ansible/playbooks/platform/deploy-openhands.yml` | `unraid`/`unraid-server` | `.env` with `OPENHANDS_SECRET_KEY`, `OLLAMA_HOST_IP` (not yet migrated) | `wait_for port=3000`, `docker ps` for `openhands`, `curl http://<host>:3000/health` |
| `ansible/playbooks/platform/deploy-ollama.yml` | `windows-gpu` hosts | `.env` on target, copied from example (not yet migrated) | `curl http://<host>:11434/api/tags`, `docker ps` for `ollama-windows` |
| `ansible/playbooks/dns/provision-dns-dhcp.yml` | `localhost` (Proxmox API) | `dns-dhcp` | Check VMs exist with `pvesh`/`qm list` on Proxmox; rerun play in `--check` after changes |
| `ansible/playbooks/misc/deploy-ssh-keys.yml` | `target_hosts` var (defaults to `unraid`) | none — SSH public key at `~/.ssh/id_ed25519_homelab.pub` | Confirm login: `ssh -i ~/.ssh/id_ed25519_homelab <user>@<host>` |

## Logging and rollback
- Capture `ansible-playbook` output; for containers, `ansible -i inventory/hosts.yml <host> -m shell -a "docker logs --tail 100 <container>"`.
- If a run misconfigures a service, revert the env/vars change, re-run the last known-good play in check mode, then apply with the corrected vars. For containerized roles, stopping/removing the container and re-running the playbook is safe because data paths live on host volumes.
