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
