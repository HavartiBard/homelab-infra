# Design: Homelab Service Onboarding Skill

**Date**: 2026-02-20
**Status**: Approved
**Validated against**: SearXNG MCP deployment

## Problem

Deploying a new homelab service requires coordinating across many concerns —
Ansible roles, compose files, DNS, NPM, mcp-proxy, Director, Obsidian catalog,
port registry, git workflow — with no consistent process. The result is
inconsistency across services and cognitive overhead every time something new is
added.

## Goal

A repo-specific agent skill that guides any agent (or human) through deploying a
new homelab service consistently, end-to-end. The skill must work equally well
when driven interactively by a human, autonomously by a single agent, or as a
pipeline where a coordinating agent handles intake and a separate agent handles
execution.

## Design

### Core Artifact: The Service Manifest

Every deployment begins with a `service-manifest.yml`. This is the formal
handoff artifact between whoever decides (human, coordinating agent) and whoever
deploys (execution agent). It captures all decisions upfront so that phases 2–6
are fully deterministic from it.

The manifest is committed to the feature branch at the end of Phase 1. Any agent
picking up at Phase 2 reads it from git — no in-band passing required.

```yaml
service:
  name: searxng-mcp            # slug — used for role/playbook/dir names
  display_name: "SearXNG MCP"
  description: "Privacy-respecting metasearch engine with MCP interface"
  class: mcp                   # first-class | mcp | utility | agent
  host: unraid                 # unraid | proxmox | jetson | spraycheese

networking:
  port: 6978                   # allocated from docs/network-ports.md
  transport: http              # http | stdio
  shared_ip: true              # false = own macvlan IP (first-class/agent only)
  mcp_proxy:
    enabled: false             # true if transport: stdio
    name: searxng              # key in mcp-proxy servers config
  director:
    enabled: true
    playbook: dev-core         # Director playbook to register under

container:
  image: searxng/searxng:latest
  interactive_shell: false     # true = deploy zsh + oh-my-zsh + standard tools
  stateful: true               # true = appdata volume at /mnt/user/appdata/<name>
  unraid_icon_url: "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/searxng.png"

# first-class only — omit for mcp/utility
# reverse_proxy:
#   domain: searxng.klsll.com
#   npm_proxy: true
#   homepage_card: true
```

### Service Classes

| Class | Own IP | NPM | DNS | Homepage | mcp-proxy | Director | Bootstrap |
|-------|--------|-----|-----|----------|-----------|----------|-----------|
| `first-class` | ✅ macvlan | ✅ | ✅ | ✅ | ❌ | optional | ❌ |
| `mcp` | ❌ | ❌ | ❌ | ❌ | if stdio | ✅ | ❌ |
| `utility` | ❌ | optional | optional | ❌ | ❌ | ❌ | ❌ |
| `agent` | ✅ macvlan | optional | ✅ | ❌ | optional | optional | ✅ |

**first-class**: Long-running user-facing services (Gitea, Immich, SearXNG UI).
Own macvlan IP, reverse proxy, DNS entry, Homepage dashboard card.

**mcp**: MCP servers consumed by AI agents via Director. Shared Unraid IP +
port. Registered in Director. If stdio transport, must go through mcp-proxy
before Director can wire it in.

**utility**: Supporting services not exposed to agents or users directly (e.g.
CouchDB backing Obsidian). Shared IP, no Director config, no homepage card.

**agent**: Interactive containers where humans or AI agents SSH in (OpenClaw,
dev-environment). Own macvlan IP, full shell bootstrap (zsh, oh-my-zsh, op,
tea, homebrew, standard SSH keys, `.env_container`).

### mcp-proxy Wiring

- `transport: http` → Director connects directly to `http://<host>:<port>/mcp`.
  mcp-proxy registration skipped.
- `transport: stdio` → mcp-proxy bridges stdio → HTTP. Director connects to
  `http://<host>:6980/servers/<name>/sse`. mcp-proxy `servers.json` must be
  updated and mcp-proxy restarted **before** Director is configured.

---

## The Six Phases

### Phase 1 — Intake
*Input: service description (from human or coordinating agent)*
*Output: `service-manifest.yml` committed to feature branch*

This phase may be performed by a human, a coordinating agent, or the same agent
that runs phases 2–6. Phases 2–6 treat the manifest as a given.

- [ ] Research the service: Docker image, config requirements, existing MCP adapters
- [ ] Open Gitea issue to track the deployment
- [ ] Create feature branch: `feature/deploy-<name>`
- [ ] Scan `docs/network-ports.md` for the next free port in the appropriate range
- [ ] Produce `service-manifest.yml` and commit to feature branch

### Phase 2 — Validate
*Input: `service-manifest.yml`*
*Output: confirmed manifest, or list of errors to resolve before proceeding*

- [ ] Port not already assigned in `docs/network-ports.md`
- [ ] Role name unique in `ansible/roles/`
- [ ] Class rules satisfied (e.g. `first-class` has `reverse_proxy` block, `mcp` has `director` block)
- [ ] Docker image tag resolvable
- [ ] If `transport: stdio`: verify mcp-proxy is deployed and healthy before continuing

### Phase 3 — Generate
*Input: validated manifest*
*Output: Ansible role, compose file, playbook, and any wiring config*

**All classes:**
- [ ] `ansible/roles/<name>/defaults/main.yml` — config vars, 1Password credential lookups via `op read`
- [ ] `ansible/roles/<name>/tasks/main.yml` — compose deploy, container lifecycle
- [ ] `ansible/files/<name>/docker-compose.yml` — Unraid icon label, resource limits, `restart: unless-stopped`, stateful volume at `/mnt/user/appdata/<name>` (if `stateful: true`)
- [ ] `ansible/playbooks/<group>/deploy-<name>.yml`

**mcp class additionally:**
- [ ] If `mcp_proxy.enabled: true`: update mcp-proxy `servers.json`, redeploy mcp-proxy, verify before Director wiring
- [ ] Add entry to `ROLE_MAP` in `ansible/scripts/export-director-mcp-fragment.py`

**first-class additionally:**
- [ ] `ansible/files/npm/services/<name>.yml` — NPM proxy config
- [ ] Technitium DNS entry (A record → macvlan IP)
- [ ] Homepage card in `stacks/platform/homepage/config/services.yaml`

**agent additionally:**
- [ ] Bootstrap tasks: zsh + oh-my-zsh, standard tools (op, tea, homebrew), `.env_container`, SSH key deploy
- [ ] macvlan IP assigned and documented

### Phase 4 — Document
*Input: manifest + generated files*
*Output: updated docs, Obsidian catalog entry*

- [ ] Add port row to `docs/network-ports.md`
- [ ] Write Obsidian service catalog entry at `services/<name>.md` using `templates/service-catalog.md`
- [ ] Update `ansible/README.md` roles table
- [ ] Update `ansible/playbooks/README.md`
- [ ] If first-class: confirm homepage card added

### Phase 5 — Deploy
*Input: all generated files committed to feature branch*
*Output: running service, merged PR*

- [ ] `ansible-playbook ... --syntax-check`
- [ ] `ansible-playbook ... --check --diff --limit <host>`
- [ ] `ansible-playbook ... --diff --limit <host> -v`
- [ ] Verify: container running, port responding
- [ ] For mcp: verify Director lists the new server in the correct playbook
- [ ] Idempotence: re-run `--check`, expect `changed=0`
- [ ] Open PR, link to Gitea issue
- [ ] Merge, delete branch

### Phase 6 — Monitor *(placeholder)*
*Blocked on issue #30 (Uptime Kuma deployment)*

- [ ] Note in Obsidian catalog entry: "Uptime Kuma monitor pending — see issue #30"
- [ ] No further action until Kuma is deployed

---

## Skill File Structure

```
.codex/skills/homelab-service-onboarding/
├── SKILL.md                          # Lean entry point — phases + entry conditions
└── references/
    ├── service-manifest-schema.yml   # Annotated manifest template
    ├── class-rules.md                # Full class rules and decision guidance
    ├── port-registry-pattern.md      # How to allocate ports, current ranges
    ├── ansible-role-template.md      # Standard role structure with examples
    └── artifact-checklist.md         # Per-class artifact generation checklist
```

`SKILL.md` stays lean — phase names, entry conditions, and links to `references/`
for depth. Heavy detail (templates, examples, rules) lives in `references/` so
the main file is scannable.

---

## Entry Points

The skill supports two entry points:

**Full run (Phase 1 → 6):** Agent or human starts from a service description,
produces the manifest, and runs all phases.

**Execution-only (Phase 2 → 6):** A manifest already exists on the feature
branch (produced by another agent or a human). The executing agent reads it from
git and begins at Validate.

---

## Open Items

- **Issue #30**: Uptime Kuma — Phase 6 is a placeholder until deployed
- **Issue #31**: Backup strategy — `stateful: true` is the safe default until a
  lab-wide backup approach exists; revisit Phase 3 volume handling once #31 is
  resolved
- **Coordinating agent**: Future work to build an agent that takes a natural
  language service description and produces a validated manifest autonomously
  (Phase 1 automation)
