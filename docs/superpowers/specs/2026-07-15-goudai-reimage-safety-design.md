# Goudai Reimage Safety — Design

**Date:** 2026-07-15
**Status:** Approved, pending implementation plan
**Author:** Claude (with James)

## Context

`goudai` (192.168.20.150, Strix Halo gfx1151) is being reimaged from Ubuntu 26.04 ("resolute") to Ubuntu 24.04 ("noble"). The move is specifically to unblock AMD's ROCm apt repo, which supports `noble`/`jammy` but not `resolute` — the current host-setup playbook explicitly skips host-level ROCm and falls back to Vulkan/Mesa RADV for llama.cpp as a result. The end goal driving the reimage is better ROCm support for LoRA/LoKr training (image models — currently targeting Krea 2, possibly SDXL/Flux later; and LLMs) — that training stack itself is **out of scope for this spec** and will be brainstormed separately once this host is in a known-good, redeployable state.

This spec covers only: making sure everything currently running on goudai comes back cleanly and correctly after the OS reimage, plus laying the ROCm host-package foundation the future training work will need.

### Current goudai inventory (established via research)

| Layer | Playbook | Notes |
|---|---|---|
| Host bootstrap | `ansible/playbooks/bootstrap/setup-goudai-host.yml` | NFS mount, build tools, Vulkan, llama.cpp built from source, native Ollama, LM Studio CLI, Docker CE |
| llama-swap | `ansible/playbooks/ai/deploy-llama-swap.yml` | Canonical LLM endpoint, port 8010 |
| Open WebUI | `ansible/playbooks/ai/deploy-open-webui.yml` | Docker compose, talks to native Ollama via `host.docker.internal` |
| Qdrant | `ansible/playbooks/ai/deploy-qdrant.yml` | Docker compose, no special host deps |
| ComfyUI (LTX) | `ansible/playbooks/ai/deploy-comfyui-ltx-goudai.yml` | Custom `docker/comfyui-gfx1151` image, ROCm 7.2/PyTorch 2.9.1 **containerized** |
| SwarmUI | `ansible/playbooks/ai/deploy-swarmui.yml` | CPU-only portal, built from source |
| immich-ml | `ansible/playbooks/platform/deploy-immich.yml` (`--limit goudai` portion) | ML inference container, no goudai-side secrets |
| Observability agents | `ansible/playbooks/observability/deploy-observability-agents.yml` | node_exporter, promtail, cadvisor |
| Docker log rotation | `ansible/playbooks/bootstrap/configure-docker-log-rotation.yml` | `docker-daemon` role |
| Generic Ubuntu prep | `ansible/playbooks/bootstrap/bootstrap-ubuntu.yml` | zsh, 1Password CLI, SSH key, timezone — must be invoked with `-e target_hosts=goudai`, not automatic |

`deploy-personal-agent-llm.yml` (legacy, pre-llama-swap) is intentionally **not** part of the redeploy — superseded, kept only for reference/rollback.

### Gaps identified

1. No task installs host-level ROCm packages — today's playbook skips this entirely because of the 26.04/apt-repo mismatch this reimage is meant to fix.
2. `ansible/files/goudai/comfyui-ltx/docker-compose.yml` hardcodes `group_add: ["44", "991"]` for `video`/`render` GIDs. GID 44 (`video`) is a stable Debian/Ubuntu default; GID 991 (`render`) is dynamically allocated and **not guaranteed** to match on a fresh install.
3. `ansible/playbooks/platform/seed-netbox.yml` hardcodes goudai's NetBox platform record as `Ubuntu 26.04` — will be stale post-reimage.
4. Two docs describe an abandoned ROCm approach and reference a playbook invocation (`deploy-comfyui.yml --limit goudai`) that no longer applies to goudai:
   - `docs/plans/2026-06-19-open-webui-comfyui-image-generation-plan.md`
   - `docs/runbooks/open-webui-comfyui-image-generation.md`
5. `bootstrap-ubuntu.yml` isn't chained into any goudai-specific playbook — easy to forget after a reimage.
6. No single command runs the full redeploy in the correct order.
7. `open_webui_openai_api_key` is sourced from `vault_litellm_master_key` — the only real secret goudai's stack currently touches. Candidate for the 1Password Environments pilot (see below).

## Architecture

One new orchestration playbook, `ansible/playbooks/bootstrap/reimage-goudai.yml`, that `import_playbook`s the existing pieces in dependency order. Run once against a freshly-imaged Ubuntu 24.04 box with `--limit goudai`. No new services or roles are introduced beyond targeted fixes — every sub-playbook remains independently runnable for future partial redeploys/updates; the orchestration playbook is a convenience wrapper only.

**Order:**

1. `bootstrap-ubuntu.yml` (`-e target_hosts=goudai`) — zsh, 1Password CLI, SSH key, timezone
2. `setup-goudai-host.yml` — NFS mount, build tools, Vulkan, llama.cpp, Ollama, LM Studio CLI, Docker CE, **and now host-level ROCm**
3. `configure-docker-log-rotation.yml`
4. `deploy-llama-swap.yml`
5. `deploy-open-webui.yml` (env-var secret via 1Password Environment, see below)
6. `deploy-qdrant.yml`
7. `deploy-comfyui-ltx-goudai.yml` (dynamic GID templating, see below)
8. `deploy-swarmui.yml`
9. `deploy-immich.yml` (`--limit goudai` semantics preserved)
10. `deploy-observability-agents.yml`

If any step fails, every sub-playbook is independently idempotent, so re-running the orchestration playbook from the top is always safe (no partial-state cleanup logic needed).

## Components / changes

### 1. Host-level ROCm install (`setup-goudai-host.yml`)

Add a block that:
- Adds AMD's ROCm apt repository, scoped to `noble`
- Installs `rocm-hip-libraries`, `rocminfo`, `rocm-smi`, `hip-runtime-amd` (exact package list finalized during implementation against AMD's current noble docs)
- Is gated behind `ansible_distribution_release == 'noble'` with an explicit `assert`/fail message if run against any other release — fail loudly rather than silently skip, since silent-skip is exactly the bug this spec is fixing

Existing Vulkan/llama.cpp build path is left untouched — both backends coexisting is harmless and Vulkan remains the working fallback.

### 2. ComfyUI GID templating

Convert `ansible/files/goudai/comfyui-ltx/docker-compose.yml` to a Jinja2 template rendered by `deploy-comfyui-ltx-goudai.yml`. The playbook gathers the live `video`/`render` group GIDs from the target host (e.g. via `ansible.builtin.getent`) and renders them into `group_add`, replacing the hardcoded `["44", "991"]`. Falls back to `44`/`991` only if lookup somehow fails, with a warning.

### 3. NetBox platform record

`seed-netbox.yml`: update goudai's device platform from the hardcoded `Ubuntu 26.04` string to `Ubuntu 24.04` (both platform slugs already exist in NetBox per existing seed data).

### 4. Stale docs

Prepend a short superseded banner to both `docs/plans/2026-06-19-open-webui-comfyui-image-generation-plan.md` and `docs/runbooks/open-webui-comfyui-image-generation.md`, pointing readers at `deploy-comfyui-ltx-goudai.yml` as the current source of truth. Content otherwise left intact for history.

### 5. Orchestration playbook

New file: `ansible/playbooks/bootstrap/reimage-goudai.yml`. Chains steps 1–10 above via `import_playbook`. No custom error handling — relies on each sub-playbook's existing fail-fast behavior and idempotency.

### 6. 1Password Environments pilot (goudai/Open WebUI only)

Replace the `vault_litellm_master_key`-sourced `open_webui_openai_api_key` in `deploy-open-webui.yml` with an environment-variable lookup, e.g. `lookup('env', 'LITELLM_MASTER_KEY')`. The value is supplied by a 1Password Environment, invoked as:

```bash
op run --env-file=ansible/envs/goudai.env -- \
  ansible-playbook playbooks/ai/deploy-open-webui.yml --limit goudai
```

`ansible/envs/goudai.env` contains only `op://` references (committed — no secret material), resolved by `op run` into the process environment at execution time. No plaintext secret ever touches disk.

This is explicitly scoped to goudai's Open WebUI deployment only — no other vault-based secret in the repo changes. It's noted here as a pilot: if it proves out, it becomes a candidate to evaluate for broader `vault.yml` replacement in a future, separate design — not decided or scoped by this spec.

## Error handling / idempotency

- ROCm apt-repo/package tasks use standard `apt_repository`/`apt` module idempotency — safe to re-run.
- GID template re-renders identically when GIDs are unchanged — no spurious `docker compose up` restarts on repeat runs.
- Orchestration playbook has no bespoke error handling; each `import_playbook`'d file keeps its own existing failure behavior. Re-running from the top after any failure is always safe.

## Testing / verification

- `ansible-playbook playbooks/bootstrap/reimage-goudai.yml --syntax-check`
- `ansible-playbook playbooks/bootstrap/reimage-goudai.yml --check --diff --limit goudai` once goudai is reachable post-reimage
- Full apply: `ansible-playbook playbooks/bootstrap/reimage-goudai.yml --diff --limit goudai -v`
- Idempotence check: re-run with `--check --diff --limit goudai`, expect `changed=0`
- Manual verification:
  - `rocminfo` / `rocm-smi` on host — confirm ROCm sees the gfx1151 GPU
  - `docker compose ps` for each service (open-webui, qdrant, comfyui-ltx, swarmui, immich-ml)
  - Per-service health checks per AGENTS.md conventions
  - `getent group render` on the fresh host vs. what got templated into the ComfyUI compose file

## Out of scope

- The ROCm-based LoRA/LoKr training stack itself (tool selection, dataset/checkpoint layout, container images) — separate design, to follow this spec.
- Any vault.yml → 1Password Environments migration beyond the single goudai/Open WebUI pilot.
- Changes to `windows_gpu` (spraycheese) or any other host.
