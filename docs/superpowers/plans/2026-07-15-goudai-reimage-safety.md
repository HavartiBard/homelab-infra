# Goudai Reimage Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every service currently running on `goudai` redeployable via Ansible against a freshly-imaged Ubuntu 24.04 host, add the host-level ROCm foundation the reimage is meant to unlock, and pilot 1Password Environments for goudai's one real secret.

**Architecture:** Targeted edits to existing playbooks/roles/files (no new services), plus one new orchestration playbook (`ansible/playbooks/bootstrap/reimage-goudai.yml`) that chains the existing goudai playbooks in dependency order via `import_playbook`.

**Tech Stack:** Ansible (apt, systemd, docker modules), Jinja2 templates, Docker Compose, 1Password CLI (`op run`).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-15-goudai-reimage-safety-design.md`
- Target OS: Ubuntu 24.04 ("noble") — the ROCm host-install task must assert this and fail loudly on any other release.
- No new services or roles beyond the listed edits — every sub-playbook must remain independently runnable.
- `deploy-personal-agent-llm.yml` is explicitly excluded from the orchestration playbook (superseded by llama-swap).
- Secrets: no plaintext secret material may be committed. The 1Password Environments pilot is scoped to goudai's Open WebUI deployment only — no other vault-based secret in the repo changes.
- goudai is reachable today (still running the old OS) — use it to validate everything that doesn't require the reimage to already have happened (syntax checks, `--check --diff` against the current host where the change doesn't depend on the OS version).

---

### Task 1: Host-level ROCm install in `setup-goudai-host.yml`

**Files:**
- Modify: `ansible/playbooks/bootstrap/setup-goudai-host.yml`

**Interfaces:**
- Produces: ROCm apt repo + `rocminfo`/`rocm-smi` on the host, consumed manually (verification only) and by the future (out-of-scope) training-stack work.

- [ ] **Step 1: Update the file header and vars comment to drop the "ROCm skipped" framing**

Replace lines 2–16 (the header comment block) with:

```yaml
# =============================================================================
# Setup goudai AI workstation — host platform layer
#
# Installs everything that runs natively on the host:
#   - ROCm host packages (rocminfo, rocm-smi, HIP runtime) — noble/jammy only,
#     per AMD's apt repo support matrix. Playbook asserts the host is
#     Ubuntu 24.04 (noble) and fails loudly otherwise.
#   - Vulkan runtime (Mesa RADV — fallback GPU compute backend)
#   - llama.cpp (built from source, Vulkan backend only)
#   - Ollama (native systemd service)
#   - LM Studio CLI (lms, for Link feature)
#   - Docker CE (container runtime for the service layer)
#
# GPU: Radeon 8060S (gfx1151 RDNA 3.5, 80 CUs)
# Memory: 128GB LPDDR5 unified — 64GB VRAM + ~31GB GTT ≈ 95GB GPU-accessible
#
# Run:
#   ansible-playbook playbooks/bootstrap/setup-goudai-host.yml \
#     --vault-password-file ~/.vault-pass --limit goudai
#
# Force llama.cpp rebuild:
#   ... -e llama_cpp_force_rebuild=true
# =============================================================================
```

- [ ] **Step 2: Update the `vars:` ROCm comment block**

Replace lines 33–36 (inside `vars:`):

```yaml
    # ROCm — host packages installed below (noble/jammy apt repo support).
    # llama.cpp still uses the Vulkan backend (Mesa RADV) as a proven fallback;
    # both backends coexisting is harmless.
    # HSA override is kept for Ollama's bundled runtime and LM Studio's llmster.
    amdgpu_gfx_override: "11.0.0"
```

- [ ] **Step 3: Add a `noble`-only guard to `pre_tasks`**

In `pre_tasks:` (currently just "Refresh apt cache"), add before it:

```yaml
  pre_tasks:
    - name: Verify host is Ubuntu 24.04 (noble) — required for ROCm apt repo
      ansible.builtin.assert:
        that:
          - ansible_distribution == 'Ubuntu'
          - ansible_distribution_release == 'noble'
        fail_msg: >-
          Host {{ inventory_hostname }} is {{ ansible_distribution }}
          {{ ansible_distribution_release }}; this playbook requires Ubuntu 24.04 (noble)
          for AMD's ROCm apt repo. Reimage the host first.

    - name: Refresh apt cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600
```

- [ ] **Step 4: Add the ROCm host-package install block**

Insert a new section directly after the "GPU access" section (after the "Ensure apt keyrings directory exists" task, before the "llama.cpp" section comment), so it reuses the `/etc/apt/keyrings` directory already created there:

```yaml
    # ── ROCm host packages ───────────────────────────────────────────────────

    - name: Download ROCm apt GPG key
      ansible.builtin.get_url:
        url: https://repo.radeon.com/rocm/rocm.gpg.key
        dest: /tmp/rocm.gpg.key
        mode: '0644'

    - name: Dearmor ROCm apt GPG key
      ansible.builtin.command: >
        gpg --batch --yes --dearmor -o /etc/apt/keyrings/rocm.gpg /tmp/rocm.gpg.key
      args:
        creates: /etc/apt/keyrings/rocm.gpg

    - name: Add ROCm apt repository
      ansible.builtin.apt_repository:
        repo: >
          deb [arch=amd64 signed-by=/etc/apt/keyrings/rocm.gpg]
          https://repo.radeon.com/rocm/apt/latest noble main
        filename: rocm
        state: present

    - name: Install ROCm host packages
      ansible.builtin.apt:
        name:
          - rocm-hip-libraries
          - rocminfo
          - rocm-smi-lib
        state: present
        update_cache: true
```

- [ ] **Step 5: Syntax-check**

Run: `cd ansible && ansible-playbook playbooks/bootstrap/setup-goudai-host.yml --syntax-check`
Expected: `playbook: playbooks/bootstrap/setup-goudai-host.yml` with no errors.

- [ ] **Step 6: Verify the noble guard fires correctly against the current (pre-reimage) host**

Run: `cd ansible && ansible-playbook playbooks/bootstrap/setup-goudai-host.yml --check --diff --limit goudai`
Expected: play fails at the "Verify host is Ubuntu 24.04 (noble)" assert, with the `fail_msg` naming the host's actual release (currently `resolute`). This confirms the guard works and prevents accidentally running ROCm-repo tasks against the wrong OS — it is **expected** to fail until goudai is reimaged.

- [ ] **Step 7: Commit**

```bash
git add ansible/playbooks/bootstrap/setup-goudai-host.yml
git commit -m "Add host-level ROCm install and noble guard to goudai host setup"
```

---

### Task 2: Dynamic GID templating for ComfyUI-LTX compose file

**Files:**
- Modify: `ansible/playbooks/ai/deploy-comfyui-ltx-goudai.yml`
- Rename: `ansible/files/goudai/comfyui-ltx/docker-compose.yml` → `ansible/files/goudai/comfyui-ltx/docker-compose.yml.j2`

**Interfaces:**
- Produces: `comfyui_video_gid`, `comfyui_render_gid` facts consumed only within this playbook.

- [ ] **Step 1: Rename the compose file to a template**

```bash
git mv ansible/files/goudai/comfyui-ltx/docker-compose.yml ansible/files/goudai/comfyui-ltx/docker-compose.yml.j2
```

- [ ] **Step 2: Parameterize the GIDs in the template**

In `ansible/files/goudai/comfyui-ltx/docker-compose.yml.j2`, replace:

```yaml
    group_add:
      - "44"   # video
      - "991"  # render
```

with:

```yaml
    group_add:
      - "{{ comfyui_video_gid }}"   # video
      - "{{ comfyui_render_gid }}"  # render
```

- [ ] **Step 3: Gather the live GIDs and deploy via template in the playbook**

In `ansible/playbooks/ai/deploy-comfyui-ltx-goudai.yml`, add a new task block right after "Ensure service and build directories exist" and before "Copy Dockerfile for the gfx1151 image":

```yaml
    - name: Look up host video group GID
      ansible.builtin.getent:
        database: group
        key: video
      failed_when: false

    - name: Look up host render group GID
      ansible.builtin.getent:
        database: group
        key: render
      failed_when: false

    - name: Set ComfyUI GPU group GID facts
      ansible.builtin.set_fact:
        comfyui_video_gid: "{{ ansible_facts.getent_group.video[1] | default('44') }}"
        comfyui_render_gid: "{{ ansible_facts.getent_group.render[1] | default('991') }}"
```

Then replace the existing "Deploy docker-compose.yml" task:

```yaml
    - name: Deploy docker-compose.yml
      ansible.builtin.copy:
        src: ../../files/goudai/comfyui-ltx/docker-compose.yml
        dest: "{{ comfyui_service_dir }}/docker-compose.yml"
        mode: "0644"
      register: compose_copy
```

with:

```yaml
    - name: Deploy docker-compose.yml
      ansible.builtin.template:
        src: ../../files/goudai/comfyui-ltx/docker-compose.yml.j2
        dest: "{{ comfyui_service_dir }}/docker-compose.yml"
        mode: "0644"
      register: compose_copy
```

Note: this playbook has `gather_facts: false` at the play level, but the `getent` module works without `gather_facts` since it populates `ansible_facts` as its own action — no change needed there.

- [ ] **Step 4: Syntax-check**

Run: `cd ansible && ansible-playbook playbooks/ai/deploy-comfyui-ltx-goudai.yml --syntax-check`
Expected: no errors.

- [ ] **Step 5: Verify against the current (still-reachable) host**

Run: `cd ansible && ansible-playbook playbooks/ai/deploy-comfyui-ltx-goudai.yml --check --diff --limit goudai`
Expected: the "Deploy docker-compose.yml" diff shows the rendered `group_add` values are `44` and `991` (matching the live host's current GIDs, confirmed via `getent group render video` → `render:x:991:...`, `video:x:44:...`), so the templated file is byte-identical to the previous static one and the task reports no meaningful change to that block.

- [ ] **Step 6: Commit**

```bash
git add ansible/playbooks/ai/deploy-comfyui-ltx-goudai.yml ansible/files/goudai/comfyui-ltx/docker-compose.yml.j2
git commit -m "Template ComfyUI-LTX compose file to pin live video/render GIDs"
```

---

### Task 3: NetBox platform record update

**Files:**
- Modify: `ansible/playbooks/platform/seed-netbox.yml:295`

**Interfaces:** None (leaf change).

- [ ] **Step 1: Update goudai's platform field**

Change:

```yaml
        - { name: goudai,      device_type: AI Workstation 300,  device_role: GPU Workstation, platform: Ubuntu 26.04, location: Desk }
```

to:

```yaml
        - { name: goudai,      device_type: AI Workstation 300,  device_role: GPU Workstation, platform: Ubuntu 24.04, location: Desk }
```

The `Ubuntu 24.04` platform record already exists in NetBox (created at line 106 of the same file, slug `ubuntu-24-04`), so no platform-creation task changes are needed.

- [ ] **Step 2: Syntax-check**

Run: `cd ansible && ansible-playbook playbooks/platform/seed-netbox.yml --syntax-check`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add ansible/playbooks/platform/seed-netbox.yml
git commit -m "Update goudai NetBox platform record to Ubuntu 24.04"
```

Note: don't run this playbook for real until after the reimage — running it now would prematurely mark goudai as Ubuntu 24.04 in NetBox while it's still on the old OS. It's safe to leave the code change committed and unapplied.

---

### Task 4: Mark stale ComfyUI/Open WebUI docs as superseded

**Files:**
- Modify: `docs/plans/2026-06-19-open-webui-comfyui-image-generation-plan.md`
- Modify: `docs/runbooks/open-webui-comfyui-image-generation.md`

**Interfaces:** None (docs only).

- [ ] **Step 1: Add a superseded banner to the plan doc**

At the very top of `docs/plans/2026-06-19-open-webui-comfyui-image-generation-plan.md`, before the `# Open WebUI + ComfyUI Image Generation Plan` heading, insert:

```markdown
> **Superseded note (2026-07-15):** The "ROCm path on goudai fails (PyTorch/ComfyUI
> segfaults even with HSA override)" finding below is outdated. A working ROCm
> ComfyUI pipeline now runs on goudai via `ansible/playbooks/ai/deploy-comfyui-ltx-goudai.yml`
> (custom `docker/comfyui-gfx1151` image, ROCm 7.2 / PyTorch 2.9.1) — it serves the
> LTX2_SM video-generation workflow, not the FLUX image-gen use case this doc covers.
> The spraycheese-based Open WebUI image-generation pipeline described below is still
> current and unaffected by the goudai reimage.

```

- [ ] **Step 2: Add a superseded banner to the runbook**

At the very top of `docs/runbooks/open-webui-comfyui-image-generation.md`, before the `# Open WebUI + ComfyUI Image Generation` heading, insert:

```markdown
> **Superseded note (2026-07-15):** The line below stating that `deploy-comfyui.yml`
> configures goudai for a ROCm container with a HIP preflight is outdated —
> `deploy-comfyui.yml` targets only `unraid` and `windows_gpu` (spraycheese) today.
> goudai's ROCm ComfyUI pipeline is a separate playbook,
> `ansible/playbooks/ai/deploy-comfyui-ltx-goudai.yml`, serving a different
> (LTX2_SM video-gen) use case. The rest of this runbook (spraycheese ComfyUI +
> Open WebUI wiring) is still current.

```

- [ ] **Step 3: Commit**

```bash
git add docs/plans/2026-06-19-open-webui-comfyui-image-generation-plan.md docs/runbooks/open-webui-comfyui-image-generation.md
git commit -m "Flag stale ROCm/goudai claims in image-generation docs as superseded"
```

---

### Task 5: 1Password Environments pilot for Open WebUI's LiteLLM key

**Files:**
- Create: `ansible/envs/goudai.env`
- Modify: `ansible/playbooks/ai/deploy-open-webui.yml:23`

**Interfaces:** None (leaf change — only affects how `open_webui_openai_api_key` gets its value).

Confirmed via `op item list --vault "AI Wedge"` and `op read`: the secret lives at `op://AI Wedge/LiteLLM  MASTER key/credential` (note: the item title has two spaces between "LiteLLM" and "MASTER" — must be reproduced exactly or the reference won't resolve).

- [ ] **Step 1: Create the op-run env file**

Create `ansible/envs/goudai.env`:

```
LITELLM_MASTER_KEY=op://AI Wedge/LiteLLM  MASTER key/credential
```

- [ ] **Step 2: Update `deploy-open-webui.yml` to read from the environment**

Change line 23 from:

```yaml
    open_webui_openai_api_key: "{{ vault_litellm_master_key | default('', true) }}"
```

to:

```yaml
    open_webui_openai_api_key: "{{ lookup('env', 'LITELLM_MASTER_KEY') | default('', true) }}"
```

- [ ] **Step 3: Update the playbook header comment with the new invocation**

Change the header comment block (lines 2–11) from:

```yaml
# =============================================================================
# Deploy Open WebUI on goudai
#
# Chat UI backed by native Ollama (port 11434 on the host).
# Ollama must already be running — see setup-goudai-host.yml.
#
# Run:
#   ansible-playbook playbooks/ai/deploy-open-webui.yml \
#     --vault-password-file ~/.vault-pass --limit goudai
# =============================================================================
```

to:

```yaml
# =============================================================================
# Deploy Open WebUI on goudai
#
# Chat UI backed by native Ollama (port 11434 on the host).
# Ollama must already be running — see setup-goudai-host.yml.
#
# LiteLLM API key is sourced from a 1Password Environment (pilot — see
# docs/superpowers/specs/2026-07-15-goudai-reimage-safety-design.md), not
# ansible-vault. Run via:
#   op run --env-file=../envs/goudai.env -- \
#     ansible-playbook playbooks/ai/deploy-open-webui.yml --limit goudai
# =============================================================================
```

- [ ] **Step 4: Syntax-check**

Run: `cd ansible && ansible-playbook playbooks/ai/deploy-open-webui.yml --syntax-check`
Expected: no errors.

- [ ] **Step 5: Verify the op reference resolves and the env var reaches Ansible**

Run:
```bash
cd ansible && op run --env-file=envs/goudai.env -- ansible-playbook playbooks/ai/deploy-open-webui.yml --check --diff --limit goudai
```
Expected: the play runs (no `op run` resolution error), and the templated compose diff shows the same non-empty `OPENAI_API_KEY`-equivalent value as before (previously sourced from `vault_litellm_master_key`, now from the env var) — confirming the swap is behavior-preserving. The task has `no_log: true` already, so the actual key value will not appear in output either way.

- [ ] **Step 6: Commit**

```bash
git add ansible/envs/goudai.env ansible/playbooks/ai/deploy-open-webui.yml
git commit -m "Pilot 1Password Environments for goudai Open WebUI's LiteLLM key"
```

---

### Task 6: Orchestration playbook

**Files:**
- Create: `ansible/playbooks/bootstrap/reimage-goudai.yml`

**Interfaces:**
- Consumes: all playbooks from Tasks 1–5 plus the pre-existing `bootstrap-ubuntu.yml`, `configure-docker-log-rotation.yml`, `deploy-llama-swap.yml`, `deploy-qdrant.yml`, `deploy-swarmui.yml`, `deploy-immich.yml`, `deploy-observability-agents.yml`.

- [ ] **Step 1: Write the orchestration playbook**

Create `ansible/playbooks/bootstrap/reimage-goudai.yml`:

```yaml
---
# =============================================================================
# Full redeploy of goudai after an OS reimage (Ubuntu 24.04 "noble")
#
# Chains every playbook goudai needs, in dependency order. Every sub-playbook
# remains independently runnable — this is a convenience wrapper only. If any
# step fails, fix the underlying issue and re-run this whole playbook; every
# step is idempotent so re-running from the top is always safe.
#
# deploy-personal-agent-llm.yml is intentionally NOT included — it is
# superseded by llama-swap and kept only for reference/rollback.
#
# Run:
#   cd ansible
#   ansible-playbook -e target_hosts=goudai playbooks/bootstrap/bootstrap-ubuntu.yml --limit goudai
#   ansible-playbook playbooks/bootstrap/reimage-goudai.yml --limit goudai --vault-password-file ~/.vault-pass
#
# (bootstrap-ubuntu.yml is run separately first since it targets `hosts: all`
# gated by -e target_hosts, not `hosts: goudai` — importing it here would
# require passing target_hosts through, which import_playbook vars don't
# propagate cleanly. Run it as its own explicit step before this playbook.)
# =============================================================================

- ansible.builtin.import_playbook: setup-goudai-host.yml
- ansible.builtin.import_playbook: configure-docker-log-rotation.yml
- ansible.builtin.import_playbook: ../ai/deploy-llama-swap.yml
- ansible.builtin.import_playbook: ../ai/deploy-open-webui.yml
- ansible.builtin.import_playbook: ../ai/deploy-qdrant.yml
- ansible.builtin.import_playbook: ../ai/deploy-comfyui-ltx-goudai.yml
- ansible.builtin.import_playbook: ../ai/deploy-swarmui.yml
- ansible.builtin.import_playbook: ../platform/deploy-immich.yml
- ansible.builtin.import_playbook: ../observability/deploy-observability-agents.yml
```

Note: `configure-docker-log-rotation.yml` targets `hosts: tt:agh:workstations` and `deploy-observability-agents.yml` targets multi-group host patterns — both already include goudai (via the `workstations` group) and will simply run fine with `--limit goudai` applied at the top-level invocation, since `--limit` intersects with each play's own host pattern.

- [ ] **Step 2: Syntax-check**

Run: `cd ansible && ansible-playbook playbooks/bootstrap/reimage-goudai.yml --syntax-check`
Expected: no errors, all imported playbooks resolve.

- [ ] **Step 3: Dry-run against the current (pre-reimage) host to confirm the chain wires up correctly**

Run: `cd ansible && ansible-playbook playbooks/bootstrap/reimage-goudai.yml --check --diff --limit goudai --vault-password-file ~/.vault-pass`
Expected: the play list shows all 9 imported plays in order; execution stops at the `setup-goudai-host.yml` noble-guard assert (same as Task 1 Step 6) since goudai hasn't been reimaged yet — this is expected and confirms the ordering and imports are structurally correct. Full end-to-end success is only possible post-reimage.

- [ ] **Step 4: Commit**

```bash
git add ansible/playbooks/bootstrap/reimage-goudai.yml
git commit -m "Add goudai reimage orchestration playbook"
```

---

## Post-reimage checklist (manual, not automatable now)

Once goudai has actually been reimaged to Ubuntu 24.04:

1. `ansible-playbook -e target_hosts=goudai playbooks/bootstrap/bootstrap-ubuntu.yml --limit goudai --vault-password-file ~/.vault-pass`
2. `op run --env-file=envs/goudai.env -- ansible-playbook playbooks/bootstrap/reimage-goudai.yml --limit goudai --vault-password-file ~/.vault-pass` (confirmed: `op run` sets a process-level env var that every play in the `import_playbook` chain inherits, so wrapping this single invocation is sufficient — `deploy-open-webui.yml` does NOT need to be run as a separate `op run`-wrapped step)
3. `rocminfo` / `rocm-smi` on host — confirm ROCm sees the gfx1151 GPU
4. `getent group render video` — confirm actual GIDs match what got templated into the ComfyUI compose file (re-run `deploy-comfyui-ltx-goudai.yml` if they differ; the templating in Task 2 already handles this automatically)
5. `docker compose ps` for each service (open-webui, qdrant, comfyui-ltx, swarmui, immich-ml)
6. Per-service health checks per AGENTS.md conventions
7. Re-run `ansible-playbook playbooks/bootstrap/reimage-goudai.yml --check --diff --limit goudai` a second time — expect `changed=0` across all plays (idempotence)
8. `ansible-playbook playbooks/platform/seed-netbox.yml --limit localhost` (or however it's normally invoked) to push the `Ubuntu 24.04` platform update from Task 3
