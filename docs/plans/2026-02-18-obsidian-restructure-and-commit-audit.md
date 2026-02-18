# Obsidian Vault Restructure + Project Commit Audit

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize the Obsidian vault into a structure that works for both human browsing and agent tooling, and clean up stale commits/branches across all active projects.

**Architecture:** Shallow two-level folder structure (`homelab/`, `projects/`, `agents/`, `shared/`) with rich frontmatter for semantic querying. Existing notes migrate to new paths via MCP write tools (filesystem is read-only NFS). Project audit commits workflow files and scripts to stardew, migrates its docs to Obsidian, and closes out the stale chiffon branch via PR.

**Tech Stack:** Director MCP obsidian_* tools (write to vault), git, Gitea `tea` CLI or `gh`

---

## Task 1: Create Obsidian top-level folder README notes

**Files:**
- Create (via MCP): `homelab/README.md`
- Create (via MCP): `projects/README.md`
- Create (via MCP): `agents/README.md`
- Create (via MCP): `shared/README.md`

**Step 1: Write homelab/README.md**

Use `obsidian_write_note` with path `homelab/README.md`:
```markdown
---
type: index
section: homelab
tags: [homelab, index]
---

# Homelab

Documentation for all homelab infrastructure.

## Sections

- [[homelab/services/]] — Service catalog (one note per service)
- [[homelab/networking/]] — DNS, VLANs, network topology
- [[homelab/hosts/]] — Per-host documentation
- [[homelab/infrastructure/]] — Ansible patterns, Docker conventions
```

**Step 2: Write projects/README.md**

Use `obsidian_write_note` with path `projects/README.md`:
```markdown
---
type: index
section: projects
tags: [projects, index]
---

# Projects

Documentation for all active development projects.

## Projects

- [[projects/stardew-sprite-generator/]] — AI-powered Stardew Valley portrait generator
- [[projects/chiffon/]] — Skills-based local LLM executor
- [[projects/quota-proxy/]] — CLI quota monitoring for OpenAI/Claude
- [[projects/soullayer/]] — Persistent memory layer for AI agents
- [[projects/director-playbooks/]] — Director MCP playbook library
```

**Step 3: Write agents/README.md**

Use `obsidian_write_note` with path `agents/README.md`:
```markdown
---
type: index
section: agents
tags: [agents, index]
---

# Agent Scratch Spaces

Each folder is a scratch space for a specific agent role. Notes here are working
memory — brainstorming, findings, in-progress plans, implementation logs.

## Roles

- [[agents/researcher/]] — Research findings, source links, discovery notes
- [[agents/planner/]] — Designs, specs, proposals
- [[agents/executor/]] — Implementation logs, task tracking, progress notes
- [[agents/architect/]] — Architectural decisions (ADRs), design rationale

## Conventions

- Use `type: agent-scratch` in frontmatter
- Include `agent-role` and optionally `project`
- Include `date` for temporal context
- Notes are working space — clean up when a project is done
```

**Step 4: Write shared/README.md**

Use `obsidian_write_note` with path `shared/README.md`:
```markdown
---
type: index
section: shared
tags: [shared, index]
---

# Shared Knowledge

Reusable technical resources for all agents and projects.

## Sections

- [[shared/patterns/]] — Reusable technical patterns agents have learned
- [[shared/templates/]] — Note templates (migrated from vault root templates/)
- [[shared/playbooks/]] — Step-by-step operational guides
- [[shared/decisions/]] — Cross-project architectural decision records (ADRs)

## Conventions

Use `type: pattern | playbook | template | decision` in frontmatter.
Soul/identity lives in Director — this space is for technical knowledge only.
```

**Step 5: Verify**

Use `obsidian_list_notes` and confirm `homelab/README.md`, `projects/README.md`, `agents/README.md`, `shared/README.md` appear.

---

## Task 2: Migrate homelab services/ → homelab/services/

**Files:**
- Read from: `/mnt/obsidian/services/*.md`
- Write to (via MCP): `homelab/services/*.md`

**Step 1: List existing service notes**

Use `obsidian_list_notes` with folder `services`. Note all file paths.

**Step 2: For each service note, read and re-write at new path**

For each note at `services/foo.md`, use `obsidian_read_note` to get content, then `obsidian_write_note` at `homelab/services/foo.md`.

Update frontmatter: ensure `type: service` is present. Add any missing standard fields.

**Step 3: Write redirect notes at old paths**

For each original `services/foo.md`, overwrite with:
```markdown
---
type: redirect
moved-to: homelab/services/foo
---

> This note has moved to [[homelab/services/foo]].
```

**Step 4: Verify**

Use `obsidian_list_notes` with folder `homelab/services` and confirm all notes appear.

---

## Task 3: Migrate networking/DNS docs → homelab/networking/

**Files:**
- Read from: `/mnt/obsidian/services/DNS Architecture Specification.md`
- Read from: `/mnt/obsidian/services/DNS Migration Plan Router → Technitium + AdGuard.md`
- Read from: `/mnt/obsidian/services/Home Network Documentation.md`
- Read from: `/mnt/obsidian/services/VLAN 20 - Network Devices.md`
- Write to (via MCP): `homelab/networking/`

**Step 1: Read each networking note**

Use `obsidian_read_note` for each of the four files listed above.

**Step 2: Write to homelab/networking/**

Write each to the corresponding path under `homelab/networking/`:
- `homelab/networking/dns-architecture.md`
- `homelab/networking/dns-migration-plan.md`
- `homelab/networking/home-network.md`
- `homelab/networking/vlan-20-devices.md`

Add or update frontmatter with `type: infrastructure`, `category: networking`, relevant tags.

**Step 3: Write redirect notes at old paths**

Overwrite each original with a redirect note (same pattern as Task 2).

**Step 4: Write homelab/networking/README.md**

```markdown
---
type: index
section: homelab/networking
tags: [homelab, networking, index]
---

# Networking

DNS architecture, VLANs, and network topology documentation.

- [[homelab/networking/dns-architecture]] — Technitium + AdGuard DNS design
- [[homelab/networking/dns-migration-plan]] — Migration from router DNS
- [[homelab/networking/home-network]] — Full home network documentation
- [[homelab/networking/vlan-20-devices]] — VLAN 20 device list
```

---

## Task 4: Migrate project docs → projects/{name}/

**Files:**
- Read from: `/mnt/obsidian/services/Chiffon — Architecture & Roadmap.md`
- Read from: `/mnt/obsidian/services/Homelab MCP - Service Documentation.md`
- Read from: `/mnt/obsidian/services/Homelab MCP Deployment.md`
- Write to (via MCP): `projects/chiffon/`, `projects/director-playbooks/` (or `homelab/`)

**Step 1: Read the Chiffon note**

Use `obsidian_read_note` for `services/Chiffon — Architecture & Roadmap.md`.

**Step 2: Write to projects/chiffon/**

Write to `projects/chiffon/architecture-and-roadmap.md` with frontmatter:
```yaml
---
type: project-note
project: chiffon
category: architecture
status: active
tags: [chiffon, architecture, agents]
---
```

**Step 3: Handle Homelab MCP docs**

Read both Homelab MCP notes. These are homelab infrastructure docs, not project docs. Write to:
- `homelab/services/homelab-mcp.md`
- `homelab/infrastructure/homelab-mcp-deployment.md`

**Step 4: Write redirect notes at old paths**

**Step 5: Write projects/chiffon/README.md**

```markdown
---
type: index
section: projects/chiffon
project: chiffon
tags: [chiffon, index]
---

# Chiffon

Skills-based local LLM executor architecture.

**Repo:** [HavartiBard/chiffon](https://gitea.klsll.com/HavartiBard/chiffon)
**Stack:** Python, Poetry, FastAPI

## Notes

- [[projects/chiffon/architecture-and-roadmap]]
```

---

## Task 5: Migrate templates/ → shared/templates/

**Files:**
- Read from: `/mnt/obsidian/templates/service-catalog.md`
- Write to (via MCP): `shared/templates/service-catalog.md`

**Step 1: Read existing template**

Use `obsidian_read_note` for `templates/service-catalog.md`.

**Step 2: Write to shared/templates/**

Write to `shared/templates/service-catalog.md`. Update frontmatter to add `type: template`.

**Step 3: Add agent-scratch template**

Write `shared/templates/agent-scratch.md`:
```markdown
---
type: template
category: agent
tags: [template, agent]
---

# Agent Scratch Note Template

---
type: agent-scratch
agent-role: researcher | planner | executor | architect
project:          # optional
date: YYYY-MM-DD
tags: []
---

## Context

What are you working on?

## Notes

Working space...

## Findings / Decisions

Key takeaways to preserve.
```

**Step 4: Write redirect at old templates/service-catalog.md path**

---

## Task 6: Create agent role README notes

**Files (via MCP):**
- `agents/researcher/README.md`
- `agents/planner/README.md`
- `agents/executor/README.md`
- `agents/architect/README.md`

**Step 1: Write agents/researcher/README.md**

```markdown
---
type: index
agent-role: researcher
tags: [agents, researcher]
---

# Researcher Scratch Space

Working notes for the researcher role: findings, source analysis, discovery.

## Usage

Use template: [[shared/templates/agent-scratch]]

Set `agent-role: researcher` in frontmatter.
```

**Step 2: Write agents/planner/README.md**

```markdown
---
type: index
agent-role: planner
tags: [agents, planner]
---

# Planner Scratch Space

Working notes for the planner role: designs, specs, proposals, approach comparisons.

## Usage

Use template: [[shared/templates/agent-scratch]]

Set `agent-role: planner` in frontmatter.
```

**Step 3: Write agents/executor/README.md**

```markdown
---
type: index
agent-role: executor
tags: [agents, executor]
---

# Executor Scratch Space

Working notes for the executor role: implementation logs, task tracking, blockers, progress.

## Usage

Use template: [[shared/templates/agent-scratch]]

Set `agent-role: executor` in frontmatter.
```

**Step 4: Write agents/architect/README.md**

```markdown
---
type: index
agent-role: architect
tags: [agents, architect]
---

# Architect Scratch Space

Working notes for the architect role: ADRs, design decisions, trade-off analysis.

## Usage

Use template: [[shared/templates/agent-scratch]]

Set `agent-role: architect` in frontmatter.

## Format for ADRs

```
## Decision: [title]
**Date:** YYYY-MM-DD
**Status:** proposed | accepted | superseded

### Context
[Why this decision was needed]

### Decision
[What was decided]

### Consequences
[What this means going forward]
```
```

---

## Task 7: Seed shared/patterns/ and shared/playbooks/

**Files (via MCP):**
- `shared/playbooks/service-health-checks.md`
- `shared/playbooks/ansible-workflow.md`
- `shared/patterns/frontmatter-schema.md`

**Step 1: Write shared/playbooks/service-health-checks.md**

Distill the health check commands from AGENTS.md into a clean playbook:

```markdown
---
type: playbook
category: operations
tags: [homelab, health-checks, operations]
---

# Service Health Checks

## Core Services

### Portainer
curl -k https://localhost:9443/api/system/status

### NPM Admin
curl http://localhost:81/api/

### Ollama (on spraycheese)
curl http://spraycheese:11434/api/tags

### Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

## Container Operations

### Status overview
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

### Logs
docker compose logs -f <service>

## Port Conflicts
sudo lsof -i :<port>
```

**Step 2: Write shared/playbooks/ansible-workflow.md**

```markdown
---
type: playbook
category: deployment
tags: [ansible, deployment, homelab]
---

# Ansible Deployment Workflow

Always run in order. Never skip steps.

## Standard Steps

1. Syntax check
   ansible-playbook playbooks/<group>/<playbook>.yml --syntax-check

2. Dry run with diff
   ansible-playbook playbooks/<group>/<playbook>.yml --check --diff --limit <host>

3. Apply with diff
   ansible-playbook playbooks/<group>/<playbook>.yml --diff --limit <host> -v

4. Verify idempotence (re-run step 3, confirm no changes)

## Notes

- Always scope with --limit
- SSH key: ~/.ssh/id_ed25519_homelab
- Unraid lacks Python — roles must use raw commands
- Inventory: ansible/inventory/hosts.yml
```

**Step 3: Write shared/patterns/frontmatter-schema.md**

Reference document for the vault's standard frontmatter types (content from design doc Section 2).

---

## Task 8: Stardew — commit workflow JSONs and scripts

**Repo:** `~/projects/stardew-sprite-generator`

**Files to commit:**
- `workflows/stardew-portrait-2x3-pony.json` (modified)
- `workflows/stardew-portrait-2x3-sdxl-fixed.json` (modified)
- `workflows/stardew-portrait-harry-styles-with-ipadapter.json` (modified)
- `workflows/stardew-portrait-pony-expressions.json` (modified)
- `workflows/stardew-portrait-harry-styles-optimized.json` (new)
- `workflows/stardew-portrait-harry-styles-with-ipadapter-fixed.json` (new)
- `workflows/stardew-portrait-pony-api.json` (new)
- `workflows/stardew-portrait-pony-optimized.json` (new)
- `workflows/stardew-portrait-pony-ui-working.json` (new)
- `workflows/stardew-sprites-harry-styles-4x4.json` (new)
- `workflows/test-api-minimal.json` (new)
- `workflows/test-save-simple.json` (new)
- `scripts/api_to_ui_converter.py` (new)
- `scripts/generate_portrait_workflow.py` (new)
- `scripts/validate_workflow.py` (if present)
- `examples/` directory (new)

**Step 1: Stage and review workflow files**

```bash
cd ~/projects/stardew-sprite-generator
git add workflows/*.json scripts/*.py examples/
git diff --staged --stat
```

Verify the staged files look correct (no unexpected binaries, etc).

**Step 2: Commit**

```bash
git commit -m "feat: add optimized workflow variants, scripts, and examples

- Add Harry Styles optimized and fixed IP-Adapter workflows
- Add Pony Diffusion API, optimized, and UI-working variants
- Add 4x4 Harry Styles sprite sheet workflow
- Add api_to_ui_converter.py and generate_portrait_workflow.py scripts
- Add example character directories"
```

---

## Task 9: Stardew — migrate documentation to Obsidian

**Source:** `~/projects/stardew-sprite-generator/*.md` (untracked markdown files)
**Destination (via MCP):** `projects/stardew-sprite-generator/`

**Step 1: Write projects/stardew-sprite-generator/README.md** (via MCP)

```markdown
---
type: index
section: projects/stardew-sprite-generator
project: stardew-sprite-generator
tags: [stardew, comfyui, index]
---

# Stardew Sprite Generator

AI-powered Stardew Valley sprite and portrait generator using ComfyUI.

**Repo:** [HavartiBard/stardew-sprite-generator](https://gitea.klsll.com/HavartiBard/stardew-sprite-generator)
**Stack:** ComfyUI, SDXL, Pony Diffusion, IP-Adapter

## Notes

- [[projects/stardew-sprite-generator/comfyui-setup]]
- [[projects/stardew-sprite-generator/workflow-guide]]
- [[projects/stardew-sprite-generator/harry-styles-reference]]
- [[projects/stardew-sprite-generator/ip-adapter-integration]]
- [[projects/stardew-sprite-generator/model-comparison]]
- [[projects/stardew-sprite-generator/prompt-templates]]
```

**Step 2: Migrate key documentation files**

For each file below, read its content from the repo path and write to Obsidian via MCP:

| Source file | Obsidian path |
|-------------|---------------|
| `COMFYUI_SETUP_GUIDE.md` | `projects/stardew-sprite-generator/comfyui-setup.md` |
| `WORKFLOW_README.md` + `WORKFLOW_GENERATION.md` | `projects/stardew-sprite-generator/workflow-guide.md` (merge) |
| `HARRY_STYLES_WORKFLOW_GUIDE.md` | `projects/stardew-sprite-generator/harry-styles-reference.md` |
| `IPADAPTER_INTEGRATION_SUMMARY.md` | `projects/stardew-sprite-generator/ip-adapter-integration.md` |
| `COMFYUI_MODEL_COMPARISON.md` | `projects/stardew-sprite-generator/model-comparison.md` |
| `PROMPT_TEMPLATE.md` | `projects/stardew-sprite-generator/prompt-templates.md` |

Add frontmatter to each migrated note:
```yaml
---
type: project-note
project: stardew-sprite-generator
category: documentation
status: active
tags: [stardew, comfyui]
---
```

**Step 3: Delete source markdown files from repo**

The following files are documentation-only and have been migrated to Obsidian. Delete them:
```bash
cd ~/projects/stardew-sprite-generator
rm 00_START_HERE.md COMFYUI_DOCUMENTATION_INDEX.md COMFYUI_HARRY_STYLES_SETUP.md \
   COMFYUI_IMPLEMENTATION_SUMMARY.md COMFYUI_INDEX.md \
   COMFYUI_MODEL_COMPARISON.md COMFYUI_QUICK_START_CHECKLIST.md \
   COMFYUI_SETUP_CHECKLIST.md COMFYUI_SETUP_GUIDE.md \
   DELIVERABLES.md DELIVERABLES_SUMMARY.txt \
   HARRY_STYLES_IMPLEMENTATION_SUMMARY.md HARRY_STYLES_INDEX.md \
   HARRY_STYLES_QUICK_REFERENCE.md HARRY_STYLES_WORKFLOW_GUIDE.md \
   IPADAPTER_FIX_LOG.md IPADAPTER_INTEGRATION_SUMMARY.md IP_ADAPTER_FIX_INDEX.md \
   PROMPT_TEMPLATE.md RESEARCH_SUMMARY.md SETUP_COMPLETE.md SETUP_HARRY_STYLES.md \
   WORKFLOW_CUSTOMIZATION_EXAMPLES.md WORKFLOW_GENERATION.md WORKFLOW_README.md \
   WORKFLOW_SYSTEM_INDEX.md
rm workflows/FLUX_IP_ADAPTER_6_EXPRESSIONS_EXAMPLE.md \
   workflows/IPADAPTER_QUICK_REFERENCE.md \
   workflows/IP_ADAPTER_CORRECTIONS.md
```

Also delete the install script (not needed in repo):
```bash
rm COMFYUI_INSTALL_SCRIPT.sh
```

**Step 4: Commit the deletions**

```bash
cd ~/projects/stardew-sprite-generator
git add -u
git commit -m "chore: migrate documentation to Obsidian vault

Documentation moved to projects/stardew-sprite-generator/ in Obsidian.
Keeps repo focused on code and workflow files only."
```

**Step 5: Verify clean state**

```bash
git status
```
Expected: clean working tree with no untracked files.

---

## Task 10: Chiffon — clean up feature branch and open PR

**Repo:** `~/projects/chiffon`
**Branch:** `chiffon/task-7/20260202-205042`

**Step 1: Handle the deleted .fuse_hidden file**

The `.fuse_hidden000229a7000000e0` file is a kernel temp file that can be safely discarded:
```bash
cd ~/projects/chiffon
git checkout -- .claude/   # discard the deletion — nothing to commit here
```

Actually, check if `.claude/` dir needs any update:
```bash
ls .claude/
```
If the only change is the deleted fuse file, just restore it or omit it from staging.

**Step 2: Commit pyproject.toml fix**

The change adds `{include = "chiffon", from = "src"}` to packages — this is a valid fix. Stage and commit:
```bash
git add pyproject.toml
git commit -m "fix: add chiffon package include to pyproject.toml"
```

**Step 3: Commit the untracked plan doc**

```bash
git add docs/plans/2026-02-02-executor-worker-agent.md
git commit -m "docs(plans): add executor worker agent design plan"
```

**Step 4: Open a PR**

```bash
git push origin chiffon/task-7/20260202-205042
```

Then open PR via Gitea web UI or `tea pr create`:
- Title: `feat(task-7): executor worker agent`
- Base: `main`
- Include summary of what task-7 accomplished

**Step 5: Verify**

Check PR appears on Gitea at `https://code.klsll.com/HavartiBard/chiffon/pulls`.

---

## Task 11: Update MEMORY.md with vault conventions

**File:** `~/.claude/projects/-home-james-projects-agent-flow/memory/MEMORY.md`

**Step 1: Add vault structure section**

Append to MEMORY.md:

```markdown
## Obsidian Vault Structure

Vault at `/mnt/obsidian/` (read-only NFS). Write via `mcp__director__obsidian_write_note`.

```
homelab/          ← infrastructure, services, networking, hosts
projects/         ← one subfolder per project
agents/           ← role-based scratch spaces (researcher, planner, executor, architect)
shared/           ← patterns, templates, playbooks, decisions
```

- Soul/identity → Director MCP
- Project memory → `~/.claude/projects/*/memory/MEMORY.md`
- Technical knowledge → Obsidian `shared/`
- Scratch → Obsidian `agents/{role}/`
```

**Step 2: Verify MEMORY.md is under 200 lines**

```bash
wc -l ~/.claude/projects/-home-james-projects-agent-flow/memory/MEMORY.md
```

Trim if over 200 lines.
