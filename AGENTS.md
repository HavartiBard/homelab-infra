# AGENTS.md

This file provides guidance for all AI coding agents (Claude Code, Codex, OpenCode) working in this repository. `CLAUDE.md` is a symlink to this file.

## Session Start

When beginning a new session without a specific task, offer to review open Gitea issues:

```bash
curl -s "https://code.klsll.com/api/v1/repos/Homelab/homelab-infra/issues?state=open&type=issues&limit=20" \
  -H "Authorization: token $GITEA_TOKEN" | jq '.[] | {number, title, labels: [.labels[].name]}'
```

Present the issues as a numbered list and ask which one to work on. If the user already has a task, skip this.

## Agent Behavior

- You are an **execution-focused coding agent**. Default to implementation, not discussion.
- Make reasonable assumptions when safe. If ambiguity affects safety (data loss, secrets, network exposure), stop and ask.
- Keep changes small, verifiable, and reversible.
- If reasoning starts looping, reduce scope to the smallest testable step and provide a concrete action + verification command. Do not repeat the same analysis more than once without new evidence.

**Priority order when instructions conflict:**
1. Safety / data-loss prevention
2. Rules in this file
3. User instructions in the current chat/task
4. Tool/extension constraints

## Agent Skills Governance

Use the AgentSkills framework (https://agentskills.io/) for any skill design.

### When a skill should be **repo-specific**
- Depends on this repo’s layout, conventions, or tooling (Ansible layout, Portainer stacks, playbooks)
- Encodes domain knowledge unique to this repo (service topology, naming, deployment flow)
- Requires repo-local assets/scripts/templates or inventory/config schemas
- Changes frequently alongside this repo
- Has security boundaries tied to this repo (internal URLs, secrets access patterns)

### When a skill should be **global**
- Applies across multiple repos or is an org-wide standard
- Is tool-centric rather than repo-centric (e.g., Gitea MCP workflows)
- Encodes stable best practices that rarely change
- Does not rely on repo files or layout

### Escalation rule
If a repo-specific skill becomes useful in ≥2 repos or >70% reusable, split it into:
- A global skill for shared core
- A repo-specific skill for repo deltas/overrides

### Authoring rules (AgentSkills-aligned)
- Keep SKILL.md lean; put deep detail in `references/`
- Bundle deterministic logic in `scripts/`
- Avoid extra docs inside skills (no README/installation guides)

## Repository Overview

This is an Ansible-managed Docker infrastructure for a hybrid homelab spanning Unraid, Proxmox VMs/LXCs, and WSL2 GPU workers. Ansible is the primary deployment mechanism for services requiring dynamic configuration (MCP servers, DNS infrastructure). Docker Compose stacks in `stacks/` serve as reference deployments for simpler services.

## Architecture

- **Unraid** (192.168.20.14): Long-running services, MCP servers, Nginx Proxy
  Manager (br0 macvlan container with its own LAN IP, 192.168.20.50)
- **WSL2 GPU Workers** (spraycheese): Ollama, Open WebUI
- **DNS LXCs** (Proxmox): tt1/tt2 (Technitium), agh1/agh2 (AdGuard Home)

### DNS Infrastructure

IP plan: `192.168.{1,20,30}.{2,3}` for Technitium, `.{4,5}` for AdGuard (per-VLAN addresses).

```
Client → AdGuard (.4/.5) ─┬─ klsll.com zones ──→ Technitium (.2/.3)
                          └─ external queries ──→ DoH (Cloudflare/Quad9)
```

- **AdGuard Home** (agh1/agh2): Client-facing DNS with filtering, hands off local zones to Technitium
- **Technitium** (tt1/tt2): Authoritative for `klsll.com` subdomains, DHCP server (primary on tt1)

## Key Services

Full service inventory with Obsidian docs at `/mnt/user/appdata/obsidian/vaults/homelab/services/`.
Dependency map: `services/homelab-dependency-map.md`.

### Platform / Infrastructure (Unraid: 192.168.20.14)

| Service | Port | URL | Notes |
|---------|------|-----|-------|
| Nginx Proxy Manager | 80/443/81 | `npm.klsll.com` | Reverse proxy, HTTPS termination |
| Gitea | — | `code.klsll.com` | Git, CI/CD, container registry |
| NetBox | 8001 | `netbox.klsll.com` | IPAM + device inventory |
| Paperless-ngx | 8000 | `paperless.klsll.com` | Document management + OCR |
| Homepage | — | `home.klsll.com` | Dashboard |
| CouchDB | 5984 | LAN-only | Obsidian LiveSync backend |
| mcp-proxy | 6980 | LAN-only | stdio→SSE bridge (SoulLayer) |

### AI / Agent Services (Unraid)

| Service | Port | URL | Notes |
|---------|------|-----|-------|
| Agent Control Plane | 3101 (UI), 3100 (API) | `agent-cp.klsll.com` | LLM agent dashboard + approvals |
| Codex App Server | 10101 | LAN-only (ws://) | OpenAI Codex CLI server mode |
| LiteLLM | 4000 | `litellm.klsll.com` | Multi-provider LLM proxy |
| Director | 8080 | LAN-only | MCP aggregator/proxy |
| Chiffon Executor | — | — | Background AI task executor |
| SoulLayer | via mcp-proxy | `…:6980/servers/soullayer/sse` | Personality/memory MCP |

### MCP Servers (Unraid)

| Service | Port | Notes |
|---------|------|-------|
| Unraid MCP | 6970 | Unraid system management |
| Homelab MCP | 6971 | Homelab-specific tools |
| Proxmox MCP | 6974 | Proxmox VM/LXC management |
| Gitea MCP | 6976 | Gitea issues, PRs, repos |
| Obsidian MCP | 6977 | Vault read/write/search |
| SearXNG MCP | 6978 | Web search via SearXNG |
| GSuite MCP | 8092 | Google Workspace tools |
| 1Password MCP | internal | Secret retrieval (read-only) |
| iCloud MCP | 6983 | LAN-only — Mail/Calendar/Contacts, app-specific password |

### Observability (Unraid)

| Service | Port | Notes |
|---------|------|-------|
| Grafana | 3030 | `grafana.klsll.com` — dashboards |
| Prometheus | 9090 | Metrics collection (internal) |
| Alertmanager | 9093 | Alert routing (internal) |
| Loki | 3100 | Log aggregation (internal) |
| cAdvisor | 8081 | Container metrics |
| node_exporter | — | Host metrics |
| syslog-ng | 5514 | Syslog receiver → Loki |

### External Hosts

| Service | Host | Port | URL | Health Check |
|---------|------|------|-----|-------------|
| NPM | Unraid (br0 macvlan, 192.168.20.50) | 80/443/81 | `npm.klsll.com` | `curl http://192.168.20.50:81/api/` |
| Ollama | spraycheese | 11434 | `ollama.klsll.com` | `curl http://spraycheese:11434/api/tags` |
| Open WebUI | spraycheese | 8080 | `chat.klsll.com` | `curl http://localhost:8080/health` |
| Raclette | Jetson (192.168.20.169) | 9119 | `raclette.klsll.com` | `curl http://192.168.20.169:9119/` |

### DNS Infrastructure (Proxmox LXCs)

| Service | Hosts | Purpose |
|---------|-------|---------|
| Technitium | tt1/tt2 | Authoritative DNS for `klsll.com`, DHCP |
| AdGuard Home | agh1/agh2 | Client-facing DNS with filtering |

## Directory Structure

```
homelab-infra/
├── ansible/
│   ├── playbooks/
│   │   ├── bootstrap/      # Host provisioning: ubuntu init, SSH keys, goudai setup
│   │   ├── dns/            # Technitium + AdGuard
│   │   ├── jetson/         # Jetson device-specific: bootstrap, TRT, model conversion
│   │   ├── mcp/            # MCP servers + Director + SoulLayer
│   │   ├── ai/             # AI inference + agent services: ollama, open-webui, qdrant,
│   │   │                   #   openhands, litellm, agent-cp, codex, sprite-smith
│   │   ├── observability/  # Prometheus, Grafana, Loki, alerting, exporters
│   │   ├── platform/       # Core infra: gitea, gitea-runners, npm, netbox, seed-netbox
│   │   ├── services/       # User-facing services (paperless) + NPM proxy registrations
│   │   └── windows/        # Windows-specific
│   ├── roles/              # Service-specific roles
│   ├── files/              # Compose files for Ansible deployments
│   │   ├── dns/            # Technitium/AdGuard compose templates
│   │   ├── goudai/         # goudai AI workstation compose files
│   │   ├── openhands/      # OpenHands compose + config
│   │   └── ollama/         # Ollama (Windows) compose
│   └── inventory/          # Host definitions
├── stacks/                 # Docker Compose reference stacks (secondary)
│   ├── platform/           # NPM, Uptime Kuma, Homepage
│   ├── gpu-worker/         # Ollama + Open WebUI
│   └── monitoring/         # Prometheus, Grafana
├── docker/                 # Custom Dockerfiles only
│   └── obsidian-mcp-server/ # Obsidian MCP HTTP server
└── docs/                   # Documentation
```

**Deployment ownership:**
- `ansible/` → Primary deployment mechanism (MCP servers, DNS, AI services, observability)
- `stacks/` → Reference Docker Compose stacks (Platform VM services)
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

Playbooks that need secrets are run through `./scripts/run-playbook.sh <slug> <playbook> <args>`
instead of bare `ansible-playbook` — secrets resolve from 1Password via `ansible/envs/<slug>.env`.
See `docs/secrets-management.md` for the complete slug table and the one bootstrap secret
(`OP_SERVICE_ACCOUNT_TOKEN`) every host/session needs.

Common playbooks and their secrets slug:

**DNS Infrastructure:**
- `ansible/playbooks/dns/provision-dns-dhcp.yml` → `dns-dhcp`
- `ansible/playbooks/dns/provision-dns-dhcp-services.yml` → `dns-dhcp`
- `ansible/playbooks/dns/deploy-adguard-config.yml` → `adguard`

**MCP Servers:**
- `ansible/playbooks/mcp/deploy-unraid-mcp.yml` → `unraid-mcp`
- `ansible/playbooks/mcp/deploy-homelab-mcp.yml` → `homelab-mcp`
- `ansible/playbooks/mcp/deploy-onepassword-mcp.yml` → none — needs `OP_SERVICE_ACCOUNT_TOKEN` directly (it's the bootstrap secret itself)
- `ansible/playbooks/mcp/deploy-proxmox-mcp.yml` → `proxmox-mcp`
- `ansible/playbooks/mcp/deploy-icloud-mcp.yml` → `icloud-mcp`



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
- **Windows GPU hosts** (spraycheese): Heavy LLM inference (Ollama)
- **Proxmox VMs**: Platform services, DNS/DHCP (tt1/tt2/agh1/agh2)

Docker Desktop on WSL2 behaves differently from Linux Docker — don't assume `host.docker.internal` works cross-platform. Avoid designs requiring containers on one host to reach `host.docker.internal` on another host.

### Container Networking

- Use a **single named Docker network per deployment** for tightly coupled services
- Prefer LAN DNS + reverse proxy over container-to-host hacks
- If OpenHands spawns worker/agent containers, ensure they can reach the OpenHands server:
  - Prefer explicit network attachment if supported
  - Otherwise expose OpenHands on a stable LAN hostname + port
- Past failure mode: OpenHands spawned agent containers in default `bridge` network while OpenHands lived on a custom network — containers couldn't communicate

### OpenHands & MCP Rules

- Always include a `config.toml` for OpenHands deployments and mount it read-only
- Do not rely on OpenHands defaults like `http://host.docker.internal:3000/mcp/mcp`
- MCP servers should be reachable via stable hostnames: prefer `https://mcp-<name>.<lan-domain>/mcp`
- MCP endpoints must be secured (at least one of): reverse proxy auth, network isolation, IP allowlists

### Local LLM Runtime

- Prefer stable, pinned versions for inference runtimes (avoid `latest` for critical services)
- If a model pull fails due to version incompatibility, upgrade the runtime or pin the model
- Use realistic defaults: keep-alive not infinite, max loaded models 1 unless multi-user
- When tuning performance, report: prompt eval rate, eval rate, VRAM usage, context length (`num_ctx`) and truncation warnings

### Secrets

- Never hardcode secrets in git — use `.env` files (gitignored) or 1Password
- Mark placeholders as `CHANGEME_*`
- Required env var names use `:?` syntax in compose files to error if missing

### Credential Access for AI Agents

See `docs/secrets-management.md` for the full picture: the one bootstrap secret (`OP_SERVICE_ACCOUNT_TOKEN`), how it reaches agent sessions, running playbooks/stacks via `ansible/scripts/run-playbook.sh`, and ad hoc lookups (`op read "op://AI Wedge/<item>/<field>"`).

### Ansible Notes

- Unraid lacks Python — roles use `raw` commands
- SSH key: `~/.ssh/id_ed25519_homelab`
- Inventory: `ansible/inventory/hosts.yml`
- Always use `--limit` to scope playbook runs

### Tooling Preferences

**Preferred:**
- `docker compose` for deployment units
- Ansible for provisioning/config changes
- Terraform for infrastructure provisioning (VMs, etc.)
- Makefiles or `taskfile.yml` for repeatable commands

**Avoid:**
- "Clickops" instructions without also providing an IaC equivalent

### Quality Bar

- Prefer simple, maintainable code over cleverness
- Don't introduce new dependencies without justification
- Set service timezones to `America/Phoenix` where applicable

## Inventory Groups

| Group | Hosts | Purpose |
|-------|-------|---------|
| `unraid` | unraid-server | Main NAS, MCP servers |
| `pve` | pve-01, pve-02 | Proxmox hypervisors |
| `tt` | tt1, tt2 | Technitium DNS (primary/secondary) |
| `agh` | agh1, agh2 | AdGuard Home |
| `windows_gpu` | spraycheese | WSL2 GPU workers |

## When to Stop and Ask

Stop and ask if:
- A step risks data loss (volumes, home directories, NAS shares)
- A step would expose services broadly on the LAN/WAN
- Secrets are required and not provided
- You're about to modify multiple repos and aren't sure that's intended

## Service Catalog Workflow

The homelab service catalog is maintained in **Obsidian**, synced via **CouchDB**, and accessible to AI agents via the **Obsidian MCP server**.

### Architecture

```
Obsidian Desktop (LiveSync) ←→ CouchDB (192.168.20.14:5984) ←→ Obsidian MCP (HTTP :6977)
                                                                      ↓
                                                            Director MCP (pending)
                                                                      ↓
                                                            AI Agents (Claude Code, etc.)
```

### Vault Location

- Path: `/mnt/user/appdata/obsidian/vaults/homelab/`
- Service docs: `services/*.md` (one file per service)
- Templates: `templates/service-catalog.md`

### Agent Usage

**For any documentation task (service catalog entries, project notes, design docs), prefer the Obsidian MCP tools (`mcp__obsidian__*`, configured in `.mcp.json`) over direct filesystem/NFS access to the vault.** This keeps writes going through a single path that's safe alongside Obsidian LiveSync's CouchDB sync, and avoids sync conflicts from editing vault files out-of-band.

**Creating/updating service entries:**

Use the Obsidian MCP tools:
- `obsidian_write_note` - Create or update a service entry
- `obsidian_read_note` - Read existing service documentation
- `obsidian_search` - Search across the service catalog
- `obsidian_list_notes` - List all service entries

**Template structure** (`templates/service-catalog.md`):
```markdown
---
service: <service-name>
type: <service-type>
host: <hostname>
ports: [<port-list>]
status: <active|deprecated>
---

# <Service Name>

## Overview
Brief description of the service.

## Configuration
Key configuration details, file locations, etc.

## Deployment
How the service is deployed (Ansible playbook, Docker Compose stack, etc.)

## Health Check
```bash
# Health check command
```

## Troubleshooting
Common issues and solutions.
```

**Desktop access:**
- Obsidian app with Obsidian LiveSync plugin
- CouchDB endpoint: `http://192.168.20.14:5984`
- Credentials: In 1Password "AI Wedge" vault ("CouchDB Admin")

**Note:** Director MCP integration for Obsidian is pending due to a connection issue. Until resolved, access the Obsidian MCP via direct HTTP at `http://192.168.20.14:6977/mcp`.

## Common Troubleshooting

### Service Health Checks
```bash
# NPM admin
curl http://localhost:81/api/

# Ollama
curl http://spraycheese:11434/api/tags

# Container status
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Container logs
docker compose logs -f <service>
```

### mcp-proxy Not Responding
```bash
# Check container status
docker ps | grep mcp-proxy

# Check logs
docker logs mcp-proxy -f

# Verify servers.json
docker exec mcp-proxy cat /config/servers.json

# Test endpoint
curl -v http://localhost:6980/servers/soullayer/sse
```

### Port Conflicts
```bash
sudo lsof -i :<port>
sudo netstat -tulpn | grep <port>
```

## Git Workflow

- Git SSH remote: `git@gitea.klsll.com:Homelab/homelab-infra.git`
- Gitea web UI: `https://code.klsll.com/Homelab/homelab-infra`
- Base branch: `main`
- Do not force-push unless explicitly requested

### Gitea MCP

A Gitea MCP server is available and should be **preferred over raw `curl`/`gh` commands** for all Gitea interactions: listing/creating issues, creating PRs, managing labels, browsing repo contents, etc. Use the `mcp__gitea__*` tools directly. Fall back to `curl` or the Gitea API only if the MCP tool doesn't cover the operation.

**Setup:** The project `.mcp.json` should auto-configure the Gitea MCP for Claude Code sessions. If the `mcp__gitea__*` tools are not available at session start:

1. Verify the MCP server is reachable:
   ```bash
   curl -s http://192.168.20.14:6976/mcp -o /dev/null -w "%{http_code}"
   ```
2. For **Claude Code**, add to `~/.claude.json` under `mcpServers`:
   ```json
   {
     "gitea": {
       "type": "http",
       "url": "http://192.168.20.14:6976/mcp"
     }
   }
   ```
3. For **other agents** (Codex, OpenCode), use the Gitea REST API directly with `$GITEA_TOKEN`:
   ```bash
   curl -s "https://code.klsll.com/api/v1/repos/Homelab/homelab-infra/issues" \
     -H "Authorization: token $GITEA_TOKEN" -H "Accept: application/json"
   ```

If the MCP server is down, deploy it: `cd ansible && ansible-playbook playbooks/mcp/deploy-gitea-mcp.yml --limit unraid`

### Never Commit Directly to Main

**All work must happen on feature branches.** Do not commit directly to `main`.

- Create a feature branch before starting work: `git checkout -b feature/<short-name>`
- Use git worktrees (`git worktree add`) when you need isolation from the current workspace or when multiple streams of work are in progress
- Push the feature branch and create a PR via the Gitea MCP (`mcp__gitea__create_pull_request`)
- Merge through the PR process, not by pushing directly to `main`

### Post-Merge Cleanup

After a PR is merged, clean up the branch and any associated worktree:

```bash
# Delete the remote branch (or use Gitea's "delete branch after merge" option)
git push origin --delete feature/<branch-name>

# Delete the local branch
git branch -d feature/<branch-name>

# If a worktree was used, remove it
git worktree remove <worktree-path>

# Prune stale worktree references
git worktree prune
```

Stale remote branches clutter the repo — always clean up after merge.

## Output Format

When finishing a task, end with:
- **Summary**: What changed
- **Deploy/Run**: Exact commands
- **Verify**: Exact checks (curl endpoints, docker ps, logs)
- **Rollback**: How to revert safely
- **Notes**: Any assumptions or follow-ups

## Secrets

- Never commit secrets
- Use `.env` (gitignored) or documented env vars
- Include env var names in docs, never values
