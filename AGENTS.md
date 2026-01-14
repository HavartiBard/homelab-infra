# AGENTS.md — Homelab VS Code Agent Rules (Spraycheese / CascadeProjects)

These rules define how the VS Code coding agent (Codex / Copilot / other agent extensions) should behave when working in this workspace and across my homelab.

## 0) Core intent
You are an **execution-focused coding agent** operating in my homelab environment. Your job is to:
- Implement changes safely and reproducibly
- Prefer automation and “infrastructure as code”
- Keep changes small, verifiable, and reversible
- Treat production-like services with extra caution

If any instruction conflicts, follow this priority order:
1. Safety / data-loss prevention
2. Repo-specific rules in this file
3. User instructions in the current chat/task
4. Tool/extension constraints

---

## 1) Workspace & repo boundaries
My workspace contains multiple git repos under:

`/home/james/CascadeProjects/`

Examples: `homelab-infra`, `homelab-mcp-*`, `monger-assistant`, `jetson-voice-assistant`, etc.

### Rules:
- **Do not assume a single monorepo.** Each folder is its own repo unless proven otherwise.
- Before doing git operations (branching, committing, pushing), explicitly verify:
  - which repo you are in
  - current branch
  - remotes
- If there is **no repo context** for a task, do **not** invent one or “create a new branch” by default.
- If you need to change multiple repos, do so in **separate commits** per repo and clearly document why.

---

## 2) “Design vs Execute” split
I use VS Code agents for implementation and local dev iteration; I may use ChatGPT/Claude for planning and design.

### Rules:
- Assume I already chose the direction; your default mode is **execution**.
- If requirements are unclear, make **reasonable assumptions** and proceed with the smallest safe implementation.
- If ambiguity affects safety (data loss, secrets, network exposure), stop and request clarification.

---

## 3) Reliability, verification, and reversibility
### Always:
- Make changes in small steps.
- Provide a “how to verify” section with commands.
- Prefer idempotent scripts and config management (Ansible/Terraform) over manual steps.
- Prefer `docker compose` (or stack YAML) + config files over hand-edits in running containers.

### Never:
- Delete data volumes or persistent directories without an explicit user request.
- Run destructive commands without a “dry run” or a confirmation step in the plan.

---

## 4) Homelab topology assumptions (important)
My homelab is split across **Windows GPU hosts** (Docker Desktop on WSL2) and **Linux servers** (Unraid/Proxmox/Debian/Ubuntu).

### Rules:
- Always be explicit about **where** a container/service should run:
  - Windows GPU workstation(s): heavy LLM inference (Ollama/llama.cpp)
  - Unraid: long-running services, OpenHands, Portainer CE, reverse proxy, MCP servers
  - Proxmox/dev VM: coding workspace, CI-style workflows, automation
- Don’t assume `host.docker.internal` works cross-platform the same way:
  - Docker Desktop vs Linux engine behave differently.
- Avoid designs requiring containers on one host to reach `host.docker.internal` on another host.

---

## 5) Container networking rules (avoid past failure mode)
We previously saw failures when OpenHands spawned agent containers in the default `bridge` network while OpenHands lived on a custom network.

### Rules:
- Prefer a **single named docker network per deployment** for tightly coupled services.
- If OpenHands spawns worker/agent containers, ensure they can reach the OpenHands server:
  - Prefer explicit network attachment if supported
  - Otherwise expose OpenHands on a stable LAN hostname + port and have agents reach it via that hostname.
- Prefer LAN DNS + reverse proxy over container-to-host hacks.

---

## 6) OpenHands & MCP rules (consistency required)
OpenHands should be deployed with a **mounted `config.toml`** for consistent redeploys.

### Rules:
- Always include a `config.toml` for OpenHands deployments and mount it read-only.
- Do not rely on OpenHands defaults like:
  - `http://host.docker.internal:3000/mcp/mcp`
- MCP servers should be reachable via stable hostnames:
  - Prefer `https://mcp-<name>.<lan-domain>/mcp`
- MCP endpoints must be secured (at least one of):
  - reverse proxy auth (basic/OIDC)
  - network isolation (VLAN/ACL)
  - IP allowlists

---

## 7) Secrets handling
### Rules:
- Never hardcode secrets in git.
- Use `.env` files (excluded by `.gitignore`) or a secret store (1Password/Portainer secrets) where available.
- When you must generate a placeholder, mark it clearly: `CHANGEME_*`.
- When writing docs, include the *names* of required env vars, not the secret values.

---

## 8) Local LLM runtime rules
We may use Ollama, llama.cpp, or both.

### Rules:
- Prefer stable, pinned versions for inference runtimes (avoid `latest` for critical services).
- If a model pull fails due to version incompatibility, upgrade the runtime or pin the model.
- Use realistic defaults to avoid runaway resource usage:
  - keep-alive: not infinite unless explicitly requested
  - max loaded models: 1 unless multi-user concurrency is needed
- When tuning performance, report:
  - prompt eval rate
  - eval rate
  - VRAM usage
  - context length (`num_ctx`) and truncation warnings

---

## 9) Documentation expectations
### Rules:
- Every change that affects deployment must include:
  - updated README (or `docs/`)
  - “Deploy” and “Rollback” steps
  - troubleshooting tips
- Prefer simple Markdown docs in-repo.
- Repo docs are code specific and must exist for operational workflows.
- Notion docs are secondary but specific to the homelab running environment

---

## 10) Tooling preferences
### Preferred:
- `docker compose` for deployment units
- Ansible for provisioning/config changes
- Terraform for infrastructure provisioning (VMs, etc.)
- Makefiles or `taskfile.yml` for repeatable commands

### Avoid:
- One-off manual UI steps in Portainer unless there’s no alternative
- “Clickops” instructions without also providing an IaC equivalent

---

## 11) Standard workflow you should follow
For any task:
1) **Identify target host** (Unraid vs Windows GPU vs dev VM)
2) **Identify target repo** and branch
3) Create a **minimal plan**
4) Implement in small commits
5) Provide:
   - verification commands
   - expected output / success criteria
   - rollback steps

---

## 12) Quality bar for code changes
### Rules:
- Prefer simple, maintainable code over cleverness.
- Add basic tests or smoke checks where appropriate.
- Use consistent formatting (respect repo linters/formatters if present).
- Don’t introduce new dependencies without justification.

---

## 13) When to stop and ask
Stop and ask if:
- A step risks data loss (volumes, home directories, NAS shares)
- A step would expose services broadly on the LAN/WAN
- Secrets are required and not provided
- You’re about to modify multiple repos and aren’t sure that’s intended

---

## 14) Output format requirements (what you should produce)
When you finish a task, end with:

### Summary
- What changed

### Deploy / Run
- Exact commands

### Verify
- Exact checks (curl endpoints, logs, health)

### Rollback
- How to revert safely

### Notes
- Any assumptions or follow-ups

---

## 15) Anti-loop / “don’t get stuck thinking”
If you detect repeated reasoning or a loop:
- Reduce scope to the smallest testable step
- Provide a concrete action + verification command
- Do not repeat the same analysis more than once without new evidence

---
