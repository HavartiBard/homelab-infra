# Homelab Service Onboarding Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite the homelab-service-onboarding skill to be class-aware and manifest-driven, then validate it by deploying SearXNG MCP as the first service through the full six-phase pipeline.

**Architecture:** The skill is rebuilt around a `service-manifest.yml` handoff artifact that captures all decisions upfront. A rewritten `SKILL.md` defines six phases (Intake → Validate → Generate → Document → Deploy → Monitor). New reference files provide templates and rules for each class. SearXNG MCP is deployed end-to-end as the skill's validation run.

**Tech Stack:** Ansible (roles, playbooks, raw tasks for Unraid), Docker Compose, 1Password CLI (`op read`), Gitea MCP, Obsidian MCP (via `http://192.168.20.14:6977/mcp`)

**Design doc:** `docs/plans/2026-02-20-homelab-service-onboarding-skill-design.md`

---

## Part A: Rebuild the Skill

### Task 1: Rewrite SKILL.md

**Files:**
- Rewrite: `.codex/skills/homelab-service-onboarding/SKILL.md`

The current `SKILL.md` only covers first-class services with NPM+DNS. It needs a complete rewrite to reflect the class-based, manifest-driven, six-phase design. Keep it lean — phases and entry conditions only; detail lives in `references/`.

**Step 1: Rewrite the file**

```markdown
---
name: homelab-service-onboarding
description: >
  Use when adding any new service to this homelab. Covers all service classes
  (first-class, mcp, utility, agent) via a manifest-driven six-phase pipeline.
  Supports two entry points: full run (Phase 1-6) or execution-only (Phase 2-6)
  when a manifest already exists on the feature branch.
---

# Homelab Service Onboarding

## Entry Points

**Full run (Phase 1 → 6):** Start from a service description. Produce the manifest, then execute all phases.

**Execution-only (Phase 2 → 6):** A `service-manifest.yml` already exists on the feature branch (produced by a human or coordinating agent). Read it from git and begin at Validate.

## Service Classes

See `references/class-rules.md` for full rules and decision guidance.

| Class | Own IP | NPM | DNS | Homepage | mcp-proxy | Director | Bootstrap |
|-------|--------|-----|-----|----------|-----------|----------|-----------|
| `first-class` | ✅ macvlan | ✅ | ✅ | ✅ | ❌ | optional | ❌ |
| `mcp` | ❌ | ❌ | ❌ | ❌ | if stdio | ✅ | ❌ |
| `utility` | ❌ | optional | optional | ❌ | ❌ | ❌ | ❌ |
| `agent` | ✅ macvlan | optional | ✅ | ❌ | optional | optional | ✅ |

## Phase 1 — Intake
*May be performed by a human, coordinating agent, or the same agent running phases 2–6.*

- [ ] Research service: Docker image, config, existing MCP adapters if applicable
- [ ] Open Gitea issue (`mcp__gitea__create_issue`)
- [ ] Create feature branch: `git checkout -b feature/deploy-<name>`
- [ ] Allocate port — see `references/port-registry-pattern.md`
- [ ] Produce `service-manifest.yml` — see `references/service-manifest-schema.yml`
- [ ] Commit manifest to feature branch

## Phase 2 — Validate

- [ ] Port not already in `docs/network-ports.md`
- [ ] Role name unique: `ls ansible/roles/`
- [ ] Class rules satisfied — see `references/class-rules.md`
- [ ] Docker image tag resolvable
- [ ] If `transport: stdio`: verify mcp-proxy is healthy — `curl -s http://192.168.20.14:6980/servers`

## Phase 3 — Generate

See `references/artifact-checklist.md` for per-class file list.

**All classes:**
- [ ] `ansible/roles/<name>/defaults/main.yml`
- [ ] `ansible/roles/<name>/tasks/main.yml`
- [ ] `ansible/files/<name>/docker-compose.yml`
- [ ] `ansible/playbooks/<group>/deploy-<name>.yml`

**mcp additionally:**
- [ ] If `mcp_proxy.enabled`: update mcp-proxy servers config, redeploy, verify before Director wiring
- [ ] Add to `ROLE_MAP` in `ansible/scripts/export-director-mcp-fragment.py`

**first-class additionally:**
- [ ] `ansible/files/npm/services/<name>.yml` — see `references/npm-service-template.yml`
- [ ] `ansible/playbooks/services/update-<name>-proxy.yml` — see `references/update-proxy-playbook-template.yml`
- [ ] Technitium DNS A record task
- [ ] Homepage card in `stacks/platform/homepage/config/services.yaml`

**agent additionally:**
- [ ] Bootstrap tasks: zsh + oh-my-zsh, op, tea, homebrew, `.env_container`, SSH key

## Phase 4 — Document

- [ ] Add port row to `docs/network-ports.md`
- [ ] Write Obsidian catalog entry via MCP (`obsidian_write_note`) or vault directly at `/mnt/user/appdata/obsidian/vaults/homelab/services/<name>.md`
- [ ] Update `ansible/README.md` roles table
- [ ] Update `ansible/playbooks/README.md`
- [ ] If first-class: confirm homepage card added

## Phase 5 — Deploy

```bash
cd ansible
ansible-playbook playbooks/<group>/deploy-<name>.yml --syntax-check
ansible-playbook playbooks/<group>/deploy-<name>.yml --check --diff --limit <host>
ansible-playbook playbooks/<group>/deploy-<name>.yml --diff --limit <host> -v
```

- [ ] Verify: container running, port responding
- [ ] For mcp: `curl -s http://192.168.20.14:<port>/mcp` returns valid response
- [ ] Idempotence: rerun `--check`, expect `changed=0`
- [ ] Open PR via `mcp__gitea__create_pull_request`, link to issue
- [ ] Merge, delete branch

## Phase 6 — Monitor *(placeholder — blocked on issue #30)*

- [ ] Add to Obsidian catalog entry: "Uptime Kuma monitor pending — see issue #30"

## Standards (all classes)

- Run from a feature branch — never `main`
- Never hardcode secrets — use `op read "op://AI Wedge/<item>/<field>"` in `defaults/main.yml`
- Set `TZ: America/Phoenix` in compose env
- Use `restart: unless-stopped`
- For Unraid targets: use `ansible.builtin.raw` (no Python available)
- Stateful volumes at `/mnt/user/appdata/<name>` (Unraid default until issue #31 resolved)
- Unraid icon: set `net.unraid.docker.icon` label — source from `https://dashboardicons.com/`
- Resource limits: always set `deploy.resources.limits` in compose
- Idempotence gate: rerun `--check --diff` expecting `changed=0`
- Security gate: no plaintext secrets; placeholders use `CHANGEME_*`
- Rollback: document exact rollback command in Obsidian catalog entry

## References

- Manifest template: `references/service-manifest-schema.yml`
- Class rules: `references/class-rules.md`
- Port allocation: `references/port-registry-pattern.md`
- Ansible role structure: `references/ansible-role-template.md`
- Per-class artifact checklist: `references/artifact-checklist.md`
- NPM service template: `references/npm-service-template.yml`
- Proxy playbook template: `references/update-proxy-playbook-template.yml`
- Deploy playbook template: `references/deploy-playbook-template.yml`
```

**Step 2: Verify it matches the design doc phases and class rules exactly**

Compare against `docs/plans/2026-02-20-homelab-service-onboarding-skill-design.md` — phases, class table, and entry points must match.

**Step 3: Commit**

```bash
git add .codex/skills/homelab-service-onboarding/SKILL.md
git commit -m "feat(skill): rewrite homelab-service-onboarding SKILL.md for class-based manifest-driven design"
```

---

### Task 2: Create service-manifest-schema.yml

**Files:**
- Create: `.codex/skills/homelab-service-onboarding/references/service-manifest-schema.yml`

Annotated manifest template covering all four service classes. This is what Phase 1 produces.

**Step 1: Create the file**

```yaml
# service-manifest-schema.yml
# Annotated template — copy and fill in for each new service.
# Commit to feature branch at end of Phase 1.
# All subsequent phases derive their actions from this file.

service:
  name: <slug>               # lowercase-hyphenated, used for role/dir/playbook names
  display_name: "<Name>"     # human-readable, used in Obsidian catalog and homepage
  description: "<one line>"

  # Service class — determines which artifacts are generated and which phases apply.
  # first-class: user-facing app with own IP, NPM proxy, DNS, homepage card
  # mcp:         AI agent tool, shared IP + port, registered in Director
  # utility:     internal support service, no Director, no homepage
  # agent:       interactive container (SSH), own IP, full shell bootstrap
  class: <first-class|mcp|utility|agent>

  host: unraid               # unraid | proxmox | jetson | spraycheese

networking:
  port: <NNNN>               # Allocated from docs/network-ports.md — no conflicts
                             # MCP range: 6970-6989. First-class: allocate in 6990+
                             # or use macvlan with no port binding.

  # http: Director connects directly to http://<host>:<port>/mcp
  # stdio: mcp-proxy bridges stdio→HTTP; must update mcp-proxy before Director wiring
  transport: <http|stdio>    # mcp class only; omit for other classes

  shared_ip: true            # false for first-class and agent (macvlan)
  # ip: 192.168.20.XX        # Required if shared_ip: false — allocate from DHCP range

  mcp_proxy:                 # mcp class only
    enabled: false           # true only if transport: stdio
    name: <slug>             # key registered in mcp-proxy servers.json

  director:                  # mcp class only
    enabled: true
    playbook: dev-core       # Director playbook: dev-core | global-core | other

container:
  image: <org/image:tag>     # Prefer pinned tags for production services
  interactive_shell: false   # true = agent class: deploy zsh, oh-my-zsh, op, tea, homebrew
  stateful: true             # true = volume at /mnt/user/appdata/<name> (Unraid default)
  # Unraid Docker icon — find at https://dashboardicons.com/
  # Use homarr-labs CDN: https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/<name>.png
  unraid_icon_url: "<url>"

# first-class only — omit entirely for mcp / utility / agent
# reverse_proxy:
#   domain: <name>.klsll.com
#   npm_upstream_port: <port>
#   npm_proxy: true
#   homepage_card: true
#   homepage_group: "<Group>"   # e.g. "Media", "Infrastructure", "AI"

# Credentials required by this service — document here, implement via op read in defaults/main.yml
# credentials:
#   - name: API_KEY
#     op_path: "op://AI Wedge/<Item Name>/credential"
```

**Step 2: Verify**

Check that all four classes can be represented using this schema. Run through the SearXNG manifest mentally — all fields should resolve cleanly.

**Step 3: Commit**

```bash
git add .codex/skills/homelab-service-onboarding/references/service-manifest-schema.yml
git commit -m "feat(skill): add service-manifest-schema.yml reference"
```

---

### Task 3: Create class-rules.md

**Files:**
- Create: `.codex/skills/homelab-service-onboarding/references/class-rules.md`

Decision guide for choosing a service class. Written so an agent can reason through it autonomously.

**Step 1: Create the file**

```markdown
# Class Rules

## How to choose a service class

Answer these questions in order:

**1. Does a human or AI agent SSH into this container interactively?**
→ Yes: `agent`
→ No: continue

**2. Is this an MCP server consumed by AI agents via Director?**
→ Yes: `mcp`
→ No: continue

**3. Does a human access this via a browser or mobile app on the LAN?**
→ Yes, primary use is end-user UI: `first-class`
→ No, it's a backend dependency: `utility`

---

## first-class rules

- Requires a dedicated macvlan IP — allocate from VLAN 20 range (192.168.20.X)
- Must have a DNS A record in Technitium: `<name>.klsll.com → <macvlan-ip>`
- Must have an NPM proxy host using `klsll-wildcard` cert
  - `ssl_forced: true`, `hsts: true`, `http2: true`
  - DNS record value → NPM IP (192.168.20.50), not the macvlan IP directly
- Must have a Homepage dashboard card
- No mcp-proxy or Director wiring needed (unless also an MCP server — rare)

## mcp rules

- Shared Unraid IP (192.168.20.14), port-based access
- Port must be in the MCP range: 6970–6989 (check `docs/network-ports.md`)
- Must be registered in Director under the correct playbook
- `transport: http` → Director connects directly to `http://192.168.20.14:<port>/mcp`
- `transport: stdio` → Register in mcp-proxy first, then Director connects to
  `http://192.168.20.14:6980/servers/<name>/sse`
  - Update `ansible/roles/mcp-proxy/defaults/main.yml` servers list
  - Redeploy mcp-proxy and verify BEFORE configuring Director
- Add to `ROLE_MAP` in `ansible/scripts/export-director-mcp-fragment.py`
- No NPM proxy, no DNS, no homepage card

## utility rules

- Shared Unraid IP, port-based access (or Docker network internal only)
- No Director, no homepage, no NPM (unless the service also has a management UI)
- DNS and NPM are optional — only add if the service needs to be reached by name

## agent rules

- Requires a dedicated macvlan IP — allocate from VLAN 20 range
- Must have DNS A record: `<name>.lab.klsll.com → <macvlan-ip>` (use `.lab.` subdomain for agents)
- Full shell bootstrap required:
  - zsh + oh-my-zsh (Pure theme)
  - 1Password CLI (`op`)
  - Gitea CLI (`tea`)
  - Standard SSH key (`~/.ssh/id_ed25519_homelab`)
  - `.env_container` with API keys from 1Password
- Director and mcp-proxy optional (only if agent also exposes an MCP endpoint)
```

**Step 2: Verify**

Run through SearXNG (should resolve to `mcp`) and OpenClaw (should resolve to `agent`) using the decision tree.

**Step 3: Commit**

```bash
git add .codex/skills/homelab-service-onboarding/references/class-rules.md
git commit -m "feat(skill): add class-rules.md reference"
```

---

### Task 4: Create port-registry-pattern.md

**Files:**
- Create: `.codex/skills/homelab-service-onboarding/references/port-registry-pattern.md`

**Step 1: Create the file**

```markdown
# Port Registry Pattern

## How to allocate a port

1. Open `docs/network-ports.md`
2. Find the relevant range for your service class (see below)
3. Identify the highest allocated port in that range
4. Take the next one
5. Add the new row to `docs/network-ports.md` **before generating any artifacts** — this is the source of truth

## Port ranges (Unraid / 192.168.20.14)

| Range | Purpose |
|-------|---------|
| 6970–6989 | MCP servers (homelab-managed) |
| 6990–6999 | Reserved / overflow MCP |

Current allocations (update this list when adding a service — also update `docs/network-ports.md`):

| Port | Service |
|------|---------|
| 6970 | unraid-mcp |
| 6971 | homelab-mcp |
| 6974 | proxmox-mcp |
| 6975 | onepassword-mcp |
| 6976 | gitea-mcp |
| 6977 | obsidian-mcp |
| 6978 | *(next available)* |
| 6980 | mcp-proxy |

## Validation step

Before proceeding past Phase 2, confirm the port is free on the host:

```bash
ssh unraid-server "ss -tlnp | grep :<port>"
# Expected: no output (port is free)
```

## network-ports.md row format

```
| <port> | <Service Name> | <host> | <Protocol> | <Notes> |
```
```

**Step 2: Commit**

```bash
git add .codex/skills/homelab-service-onboarding/references/port-registry-pattern.md
git commit -m "feat(skill): add port-registry-pattern.md reference"
```

---

### Task 5: Create ansible-role-template.md

**Files:**
- Create: `.codex/skills/homelab-service-onboarding/references/ansible-role-template.md`

Concrete role structure with annotated examples for Unraid targets. Replaces the existing `deploy-playbook-template.yml` as the primary role reference.

**Step 1: Create the file**

````markdown
# Ansible Role Template

Standard role structure for services deployed to Unraid via Docker Compose.

## Directory layout

```
ansible/roles/<name>/
├── defaults/
│   └── main.yml    # All config vars with defaults; credential lookups via op read
└── tasks/
    └── main.yml    # Compose deploy + container lifecycle
```

Handlers are optional — use only if restart-on-change semantics are needed.

## defaults/main.yml pattern

```yaml
---
# Config vars — override via host_vars or -e flags
<name>_port: 6978
<name>_image: "org/image:tag"
<name>_appdata: "/mnt/user/appdata/<name>"
<name>_compose_dir: "/opt/docker/<name>"

# Credentials — ENV override first, then 1Password lookup
# Never hardcode values; never commit secrets
<name>_api_key: "{{ lookup('env', 'SERVICE_API_KEY') or
  lookup('pipe', 'op read \"op://AI Wedge/<Item>/credential\"') }}"
```

## tasks/main.yml pattern

```yaml
---
- name: Ensure compose directory exists
  ansible.builtin.raw: mkdir -p <name>_compose_dir

- name: Write docker-compose.yml
  ansible.builtin.copy:
    content: "{{ lookup('template', 'files/<name>/docker-compose.yml') }}"
    dest: "{{ <name>_compose_dir }}/docker-compose.yml"
  # Note: Unraid has no Python — use raw for file ops when copy module unavailable

- name: Pull image
  ansible.builtin.raw: docker pull {{ <name>_image }}
  tags: [image]

- name: Deploy compose stack
  ansible.builtin.raw: |
    cd {{ <name>_compose_dir }}
    docker compose up -d --remove-orphans

- name: Wait for service to be healthy
  ansible.builtin.raw: |
    for i in $(seq 1 12); do
      if curl -sf http://localhost:{{ <name>_port }}/health > /dev/null 2>&1; then
        echo "healthy"; exit 0
      fi
      sleep 5
    done
    echo "timeout" >&2; exit 1
  changed_when: false
```

## compose file pattern (ansible/files/<name>/docker-compose.yml)

```yaml
services:
  <name>:
    image: "{{ <name>_image }}"
    container_name: <name>
    restart: unless-stopped
    labels:
      net.unraid.docker.icon: "<unraid_icon_url>"
      net.unraid.docker.webui: "http://192.168.20.14:{{ <name>_port }}"
    environment:
      TZ: America/Phoenix
      # Add service-specific env vars here
    ports:
      - "{{ <name>_port }}:8080"   # map container port to allocated host port
    volumes:
      - "{{ <name>_appdata }}:/data"
    deploy:
      resources:
        limits:
          memory: 512m
          cpus: "1.0"
```

## deploy playbook pattern (ansible/playbooks/<group>/deploy-<name>.yml)

```yaml
---
- name: Deploy <Name>
  hosts: unraid
  gather_facts: false
  roles:
    - role: <name>
```

Keep playbooks thin — all logic lives in the role.

## Unraid-specific notes

- Unraid has no Python — prefer `ansible.builtin.raw` for file system operations
- SSH key: `~/.ssh/id_ed25519_homelab`
- Always use `--limit unraid` (or explicit hostname) — never run broad plays
- `docker compose` (V2) is available; do not use `docker-compose` (V1)
````

**Step 2: Commit**

```bash
git add .codex/skills/homelab-service-onboarding/references/ansible-role-template.md
git commit -m "feat(skill): add ansible-role-template.md reference"
```

---

### Task 6: Create artifact-checklist.md

**Files:**
- Create: `.codex/skills/homelab-service-onboarding/references/artifact-checklist.md`

Per-class artifact checklist for Phase 3. Quick reference for what needs to be generated for each class.

**Step 1: Create the file**

```markdown
# Artifact Checklist (Phase 3)

Generated from `service-manifest.yml`. Check off as each file is created.

## All classes

- [ ] `ansible/roles/<name>/defaults/main.yml`
- [ ] `ansible/roles/<name>/tasks/main.yml`
- [ ] `ansible/files/<name>/docker-compose.yml`
- [ ] `ansible/playbooks/<group>/deploy-<name>.yml`
  - `<group>` = `mcp` for MCP servers, `platform` for first-class, `misc` for utility

## mcp class additionally

- [ ] If `mcp_proxy.enabled: true`:
  - [ ] Add server entry to `ansible/roles/mcp-proxy/defaults/main.yml` servers list
  - [ ] Redeploy mcp-proxy: `ansible-playbook playbooks/mcp/deploy-mcp-proxy.yml --diff --limit unraid`
  - [ ] Verify: `curl -s http://192.168.20.14:6980/servers` includes `<name>`
- [ ] Add to `ROLE_MAP` in `ansible/scripts/export-director-mcp-fragment.py`:
  ```python
  {
      "role": "<name>",
      "name": "<name>",
      "port_var": "<name>_port",
      "path": "/mcp",
  },
  ```

## first-class additionally

- [ ] `ansible/files/npm/services/<name>.yml` — from `references/npm-service-template.yml`
- [ ] `ansible/playbooks/services/update-<name>-proxy.yml` — from `references/update-proxy-playbook-template.yml`
- [ ] Technitium DNS task (A record: `<name>.klsll.com → <macvlan-ip>`)
- [ ] Homepage card in `stacks/platform/homepage/config/services.yaml`:
  ```yaml
  - name: <Display Name>
    href: https://<name>.klsll.com
    icon: <name>.png
    description: <one line>
  ```

## agent additionally

- [ ] Bootstrap tasks added to `ansible/roles/<name>/tasks/main.yml`:
  - [ ] Install zsh
  - [ ] Install oh-my-zsh + Pure theme
  - [ ] Install op (1Password CLI)
  - [ ] Install tea (Gitea CLI)
  - [ ] Deploy `.env_container` with API keys from 1Password
  - [ ] Deploy standard SSH key (`id_ed25519_homelab`)
  - [ ] Set default shell to zsh for the service user

## Phase 4 documentation checklist

- [ ] Port row added to `docs/network-ports.md`
- [ ] Obsidian catalog entry written at `services/<name>.md` (template: `templates/service-catalog.md`)
- [ ] `ansible/README.md` roles table updated
- [ ] `ansible/playbooks/README.md` updated
```

**Step 2: Commit**

```bash
git add .codex/skills/homelab-service-onboarding/references/artifact-checklist.md
git commit -m "feat(skill): add artifact-checklist.md reference"
```

---

## Part B: Deploy SearXNG MCP (Skill Validation Run)

> Run the skill's six phases against SearXNG. This is not just a deployment — it's a live validation that the skill works end-to-end. Note any gaps and fix the skill references as you go.

### Task 7: Phase 1 — SearXNG Intake

**Files:**
- Create: `service-manifest.yml` (repo root of feature branch, temporary — deleted after merge)

**Step 1: Research SearXNG MCP**

Identify the MCP adapter for SearXNG. Options to evaluate:
- Check Docker Hub for `searxng/searxng` — the web app with JSON API at `/search?format=json`
- Search for an existing MCP server wrapper (npm: `mcp-server-searxng`, or similar)
- If no suitable adapter exists, SearXNG's JSON API may be wrapped by a lightweight MCP server

Document the chosen adapter image/approach in the manifest.

**Step 2: Open a Gitea issue**

```python
# Use mcp__gitea__create_issue tool:
owner="Homelab", repo="homelab-infra",
title="Deploy SearXNG MCP server",
body="Deploy SearXNG + MCP adapter as the first service through the new onboarding skill. Tracks issue for branch feature/deploy-searxng-mcp."
```

**Step 3: Create feature branch**

```bash
git checkout main && git pull
git checkout -b feature/deploy-searxng-mcp
```

**Step 4: Allocate port**

Scan `docs/network-ports.md` — next available in MCP range after 6977 is **6978**.

**Step 5: Write service-manifest.yml**

```yaml
service:
  name: searxng-mcp
  display_name: "SearXNG MCP"
  description: "Privacy-respecting metasearch engine with MCP interface"
  class: mcp
  host: unraid

networking:
  port: 6978
  transport: http
  shared_ip: true
  mcp_proxy:
    enabled: false
  director:
    enabled: true
    playbook: dev-core

container:
  image: <resolved in Step 1>
  interactive_shell: false
  stateful: true
  unraid_icon_url: "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/searxng.png"
```

**Step 6: Commit manifest**

```bash
git add service-manifest.yml
git commit -m "feat(searxng-mcp): Phase 1 — service manifest"
```

---

### Task 8: Phase 2 — Validate SearXNG Manifest

**Step 1: Check port is free in docs**

```bash
grep "6978" ansible/../docs/network-ports.md
# Expected: no output
```

**Step 2: Check role name is unique**

```bash
ls ansible/roles/ | grep searxng
# Expected: no output
```

**Step 3: Verify class rules satisfied**

- `class: mcp` requires `director.enabled: true` ✅
- `shared_ip: true` ✅
- `mcp_proxy.enabled: false` (transport: http, no proxy needed) ✅

**Step 4: Verify image is resolvable**

```bash
docker pull <image>:<tag> --dry-run 2>&1 | head -5
# or: curl -s https://hub.docker.com/v2/repositories/<org>/<image>/tags/<tag>/ | jq .name
```

**Step 5: Commit validation note**

```bash
git commit --allow-empty -m "feat(searxng-mcp): Phase 2 — manifest validated"
```

---

### Task 9: Phase 3 — Generate SearXNG Ansible Artifacts

**Files:**
- Create: `ansible/roles/searxng-mcp/defaults/main.yml`
- Create: `ansible/roles/searxng-mcp/tasks/main.yml`
- Create: `ansible/files/searxng-mcp/docker-compose.yml`
- Create: `ansible/playbooks/mcp/deploy-searxng-mcp.yml`
- Modify: `ansible/scripts/export-director-mcp-fragment.py` (add to ROLE_MAP)

**Step 1: Create defaults/main.yml**

```yaml
---
searxng_mcp_port: 6978
searxng_mcp_image: "<resolved image>"
searxng_mcp_appdata: "/mnt/user/appdata/searxng-mcp"
searxng_mcp_compose_dir: "/opt/docker/searxng-mcp"
```

**Step 2: Create tasks/main.yml**

Follow pattern from `references/ansible-role-template.md`. Include:
- Ensure appdata and compose dirs exist
- Write docker-compose.yml
- Pull image (tagged: `image`)
- `docker compose up -d --remove-orphans`
- Health check against `/mcp` or `/search` endpoint

**Step 3: Create docker-compose.yml**

Follow compose pattern from `references/ansible-role-template.md`. Key fields:
- `container_name: searxng-mcp`
- `restart: unless-stopped`
- `net.unraid.docker.icon` label with SearXNG icon URL
- `TZ: America/Phoenix`
- Port mapping: `{{ searxng_mcp_port }}:<container_port>`
- Volume: `{{ searxng_mcp_appdata }}:/data` (or appropriate path)
- Resource limits: memory 512m, cpus 1.0

**Step 4: Create deploy playbook**

```yaml
---
- name: Deploy SearXNG MCP
  hosts: unraid
  gather_facts: false
  roles:
    - role: searxng-mcp
```

**Step 5: Add to export-director-mcp-fragment.py ROLE_MAP**

```python
{
    "role": "searxng-mcp",
    "name": "searxng-mcp",
    "port_var": "searxng_mcp_port",
    "path": "/mcp",
},
```

**Step 6: Syntax check**

```bash
cd ansible
ansible-playbook playbooks/mcp/deploy-searxng-mcp.yml --syntax-check
# Expected: no errors
```

**Step 7: Commit**

```bash
git add ansible/roles/searxng-mcp/ ansible/files/searxng-mcp/ \
        ansible/playbooks/mcp/deploy-searxng-mcp.yml \
        ansible/scripts/export-director-mcp-fragment.py
git commit -m "feat(searxng-mcp): Phase 3 — Ansible role, compose, playbook"
```

---

### Task 10: Phase 4 — Document SearXNG

**Files:**
- Modify: `docs/network-ports.md`
- Create: Obsidian vault entry at `/mnt/user/appdata/obsidian/vaults/homelab/services/searxng-mcp.md`
- Modify: `ansible/README.md`
- Modify: `ansible/playbooks/README.md`

**Step 1: Add port to network-ports.md**

Add row to the MCP Servers section:
```
| 6978 | SearXNG MCP | unraid (192.168.20.14) | HTTP | MCP server — metasearch |
```

**Step 2: Write Obsidian service catalog entry**

Use the template at `/mnt/user/appdata/obsidian/vaults/homelab/templates/service-catalog.md`.
Write to `/mnt/user/appdata/obsidian/vaults/homelab/services/searxng-mcp.md`.

Include:
- Service name, type, host, ports, status
- Overview, Configuration, Deployment playbook
- Health check command
- Troubleshooting notes
- Rollback: `docker compose -f /opt/docker/searxng-mcp/docker-compose.yml down`
- "Uptime Kuma monitor pending — see issue #30"

**Step 3: Update ansible/README.md**

Add `searxng-mcp` row to the Ansible Roles table.

**Step 4: Update ansible/playbooks/README.md**

Note `deploy-searxng-mcp.yml` under the `mcp/` directory description.

**Step 5: Commit**

```bash
git add docs/network-ports.md ansible/README.md ansible/playbooks/README.md
git commit -m "feat(searxng-mcp): Phase 4 — port registry, Obsidian catalog, docs"
```

---

### Task 11: Phase 5 — Deploy SearXNG

**Step 1: Dry-run**

```bash
cd ansible
ansible-playbook playbooks/mcp/deploy-searxng-mcp.yml --check --diff --limit unraid-server
# Expected: no errors, shows planned changes
```

**Step 2: Apply**

```bash
ansible-playbook playbooks/mcp/deploy-searxng-mcp.yml --diff --limit unraid-server -v
# Expected: changed tasks for compose deploy, container start
```

**Step 3: Verify container running**

```bash
ssh unraid-server "docker ps | grep searxng-mcp"
# Expected: searxng-mcp Up X seconds
```

**Step 4: Verify MCP endpoint responds**

```bash
curl -s http://192.168.20.14:6978/mcp | head -20
# Expected: valid MCP response (tools list or health JSON)
```

**Step 5: Idempotence check**

```bash
ansible-playbook playbooks/mcp/deploy-searxng-mcp.yml --check --diff --limit unraid-server
# Expected: changed=0
```

**Step 6: Open PR**

```python
# Use mcp__gitea__create_pull_request:
title="feat(searxng-mcp): deploy SearXNG MCP server via onboarding skill",
body="""## Summary
- Deploys SearXNG MCP server on Unraid at port 6978
- First service deployed through the new homelab-service-onboarding skill
- Validates full six-phase pipeline end-to-end

## Test plan
- [x] --syntax-check passes
- [x] --check --diff shows correct plan
- [x] Applied successfully, container running
- [x] MCP endpoint responds at :6978/mcp
- [x] Idempotence: changed=0 on rerun
""",
head="feature/deploy-searxng-mcp", base="main"
```

**Step 7: Merge and clean up**

After PR merges:
```bash
git checkout main && git pull
git branch -d feature/deploy-searxng-mcp
git push origin --delete feature/deploy-searxng-mcp
```

---

### Task 12: Phase 6 — Monitor Placeholder

**Step 1: Confirm Obsidian entry has monitor note**

Verify `/mnt/user/appdata/obsidian/vaults/homelab/services/searxng-mcp.md` contains:
```
> Uptime Kuma monitor pending — see issue #30
```

No further action until issue #30 (Uptime Kuma) is resolved.

---

## Notes for the executing agent

- The skill references in Part A should be committed and pushed **before** beginning Part B — the skill is the tool, SearXNG is the first use of the tool
- Part A and Part B run on **separate feature branches**: `feature/homelab-service-onboarding-skill` (already exists) and `feature/deploy-searxng-mcp`
- If the SearXNG MCP adapter image is unclear after research, pause and ask before writing the compose file — wrong image = wasted deploy cycle
- Port 6978 is the planned allocation but confirm against `docs/network-ports.md` at time of execution
