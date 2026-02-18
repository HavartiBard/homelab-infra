# Obsidian Vault Restructure Design

**Date:** 2026-02-18
**Status:** Approved
**Scope:** Obsidian vault reorganization + project commit audit

---

## Context

The Obsidian vault was initially set up as a homelab service catalog with a flat `services/` folder. As usage grows — and with agents actively reading/writing to the vault — we need a structure that works equally well for human browsing in Obsidian desktop and for agent tooling with predictable paths.

This design also covers a project commit audit to clean up stale branches and uncommitted work across all active repos.

---

## Design

### Guiding Principles

- **Both human and agent consumers** — structure must be navigable in Obsidian graph view AND give agents predictable file paths
- **Shallow folders + rich frontmatter** — max 2-level folder depth; frontmatter carries semantic metadata for agent queries
- **Clean separation of concerns** — homelab infra docs, project docs, agent scratch, and shared knowledge are distinct namespaces
- **Soul stays in Director** — Director/soul handles identity and personality; Obsidian handles technical scaffolding and knowledge

### Vault Structure

```
homelab/
  services/       ← service catalog (migrated from current services/)
  networking/     ← DNS, VLANs, network topology
  hosts/          ← per-host documentation
  infrastructure/ ← Ansible patterns, Docker conventions

projects/
  stardew-sprite-generator/
  chiffon/
  quota-proxy/
  soullayer/
  director-playbooks/

agents/
  researcher/     ← findings, research notes, source links
  planner/        ← designs, specs, proposals
  executor/       ← implementation logs, task tracking
  architect/      ← architectural decisions (ADRs)

shared/
  patterns/       ← reusable technical patterns
  templates/      ← note templates (migrated from current templates/)
  playbooks/      ← step-by-step operational guides
  decisions/      ← cross-project ADRs
```

### Frontmatter Schema

**Service notes** (`homelab/services/`):
```yaml
---
type: service
service: portainer
host: platform-vm
port: 9443
url: https://portainer.klsll.com
status: active
tags: [homelab, monitoring, docker]
---
```

**Host notes** (`homelab/hosts/`):
```yaml
---
type: host
hostname: unraid
ip: 192.168.20.14
role: nas, docker-host
status: always-on
tags: [homelab, unraid]
---
```

**Project notes** (`projects/{name}/`):
```yaml
---
type: project-note
project: chiffon
category: architecture | decisions | status
status: active | draft | archived
tags: [chiffon, python, agents]
---
```

**Agent scratch notes** (`agents/{role}/`):
```yaml
---
type: agent-scratch
agent-role: researcher | planner | executor | architect
project: chiffon     # optional
date: 2026-02-18
tags: [...]
---
```

**Shared resources** (`shared/`):
```yaml
---
type: pattern | playbook | template | decision
category: debugging | deployment | architecture | workflow
tags: [...]
---
```

### Layer Separation

| Layer | Location | Purpose |
|-------|----------|---------|
| Soul/Identity | Director MCP | Who agents are — personality, values, communication style |
| Project memory | `~/.claude/projects/*/memory/MEMORY.md` | Per-project learned preferences (ephemeral) |
| Technical knowledge | Obsidian `shared/` | Reusable patterns, playbooks, architectural knowledge |
| Scratch | Obsidian `agents/{role}/` | Active working notes per agent role |
| Living docs | Obsidian `homelab/` + `projects/` | Human-readable documentation |

---

## Project Commit Audit

### stardew-sprite-generator
- **Problem:** ~35 untracked markdown files (ComfyUI/Harry Styles docs) + 4 modified workflow JSONs
- **Action:** Commit workflow JSONs; migrate doc markdown files to `projects/stardew-sprite-generator/` in Obsidian; delete originals from repo

### chiffon
- **Problem:** On stale feature branch `chiffon/task-7/20260202-205042`; minor uncommitted changes
- **Action:** Review `pyproject.toml` diff, commit plan doc, open PR to merge branch to main

### quota-proxy / soullayer / director-playbooks / homelab-infra
- **Status:** Clean — no action needed

---

## Migration Steps

1. Create new folder structure in Obsidian via MCP write tools
2. Move existing `services/` notes → `homelab/services/` (update frontmatter)
3. Move existing `templates/` notes → `shared/templates/`
4. Migrate Chiffon architecture note → `projects/chiffon/`
5. Migrate DNS/networking notes → `homelab/networking/`
6. Create README/index notes for each top-level folder
7. Execute project commit audit (stardew, chiffon)
8. Update `MEMORY.md` with new vault path conventions
