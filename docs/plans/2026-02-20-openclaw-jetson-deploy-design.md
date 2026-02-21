# OpenClaw Jetson Deploy Design

**Date:** 2026-02-20
**Status:** Approved
**Related issue:** Gitea #26 (backup strategy)

## Context

OpenClaw was deployed to the Jetson Orin Nano haphazardly. The live state drifts from the
Ansible repo in several ways:

- Container name is `openclaw`, Ansible expected `openclaw-gateway`
- Live compose has no `llama-server` (removed), Ansible compose still depends on it
- `vllm-qwen` (functiongemma-270m tool-calling model) runs as a separate container, not
  managed by the OpenClaw compose
- State dir is double-mounted (`/home/node/.openclaw` AND `/root/.openclaw`) — workaround bug
- The Ansible `openclaw.json.j2` template is stale (lmstudio only, no vllm provider)
- No Jetson-specific bootstrap playbook exists

## Goals

1. A repeatable `deploy-openclaw.yml` playbook that deploys or upgrades OpenClaw correctly
2. A `bootstrap-jetson.yml` playbook that takes a freshly-flashed Jetson to fully operational
3. The OpenClaw config is seeded with enough to be useful on a fresh install (models, gateway,
   Slack) but runtime state (memory, agents, oauth) is left to OpenClaw to manage

## Out of Scope

- vLLM / functiongemma container (managed separately — see existing jetson playbooks)
- Point-in-time backup of `~/.openclaw/` (tracked in issue #26)
- nostream-proxy.py (leftover from Ollama era, not used in current setup)

---

## Architecture

```
Jetson Orin Nano (192.168.20.169)
├── openclaw container (host network, port 18789)
│   ├── reads/writes ~/.openclaw/openclaw.json  (seed + runtime state)
│   ├── workspace mount: ~/bots/raclette → /workspace
│   └── env: OPENAI_BASE_URL=http://127.0.0.1:8000/v1  (vllm-qwen local)
│
└── vllm-qwen container (separate stack, host network, port 8000)
    └── managed independently, not touched by openclaw playbook
```

`~/.openclaw/` layout (on host):
```
~/.openclaw/
├── openclaw.json          ← Ansible seeds, OpenClaw manages at runtime
├── openclaw.json.bak.<ts> ← Ansible creates before each deploy
├── agents/
├── memory/
├── logs/
└── ...
```

---

## Playbook 1: bootstrap-jetson.yml

**File:** `ansible/playbooks/jetson/bootstrap-jetson.yml`
**Target:** `edge_devices` (always requires `--limit jetson.lab`)
**Idempotent:** yes — safe to re-run

### Tasks

1. Safety guard: assert `target_hosts` var is set, skip if host not in list
2. Apt update + base packages: git, zsh, curl, ca-certificates, gnupg, lsb-release,
   software-properties-common, python3-pip, openssh-server
3. 1Password CLI — same pattern as `bootstrap-ubuntu.yml`
4. Docker CE (idempotent):
   - Add Docker GPG key + apt repo
   - Install docker-ce, docker-ce-cli, containerd.io, docker-compose-plugin
   - Add `james` to `docker` group
5. NVIDIA Container Toolkit (idempotent):
   - Add NVIDIA container toolkit apt repo + GPG key
   - Install nvidia-container-toolkit
   - `nvidia-ctk runtime configure --runtime=docker`
   - Set nvidia as default runtime in `/etc/docker/daemon.json`
   - Restart docker
6. Oh My Zsh + Pure theme + zsh-autosuggestions + zsh-syntax-highlighting
7. Deploy SSH authorized key (`id_ed25519_homelab.pub`)
8. Set timezone to `America/Phoenix`
9. Standard directories (owned by james):
   - `~/docker/`
   - `~/models/`
   - `~/bots/`
   - `~/.openclaw/`
   - `~/projects/`
10. CUDA PATH in `.bashrc` and `.zshrc` via `blockinfile` (idempotent):
    ```bash
    export PATH=/usr/local/cuda/bin:$PATH
    export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
    ```
11. Deploy `.env_container` from vault template (same as bootstrap-ubuntu pattern)
12. Go PATH in `.bashrc` via `blockinfile`

### Secrets source

- `.env_container` contents come from `group_vars/edge_devices/vault.yml` (existing)
- Bootstrap public key: `~/.ssh/id_ed25519_homelab.pub` (local controller)

---

## Playbook 2: deploy-openclaw.yml

**File:** `ansible/playbooks/jetson/deploy-openclaw.yml` (revamp of existing)
**Target:** `edge_devices` (always requires `--limit jetson.lab`)
**Idempotent:** yes

### Vars (in `group_vars/edge_devices/jetson.lab.yml`)

```yaml
jetson_openclaw_deploy_dir: /home/james/docker/openclaw
jetson_openclaw_state_dir: /home/james/.openclaw
jetson_openclaw_workspace_dir: /home/james/bots/raclette
jetson_openclaw_image: ghcr.io/openclaw/openclaw:latest
jetson_openclaw_port: 18789

# Model providers
jetson_vllm_base_url: http://127.0.0.1:8000/v1
jetson_lmstudio_base_url: http://spraycheese.lab.klsll.com:1234/v1

# Secrets — sourced from env vars at playbook run time
jetson_openclaw_env:
  OPENCLAW_GATEWAY_TOKEN: "{{ lookup('env', 'OPENCLAW_GATEWAY_TOKEN') | default('CHANGEME') }}"
  SLACK_BOT_TOKEN:        "{{ lookup('env', 'SLACK_BOT_TOKEN') }}"
  SLACK_APP_TOKEN:        "{{ lookup('env', 'SLACK_APP_TOKEN') }}"
  LMSTUDIO_API_KEY:       "{{ lookup('env', 'LMSTUDIO_API_KEY') }}"
  LMSTUDIO_BASE_URL:      "{{ jetson_lmstudio_base_url }}"
  OPENAI_BASE_URL:        "{{ jetson_vllm_base_url }}"
```

### Tasks

1. Ensure deploy dir exists (`~/docker/openclaw/`)
2. Ensure state dir exists (`~/.openclaw/`)
3. Ensure workspace dir exists (`~/bots/raclette/`)
4. Deploy `docker-compose.yml` from template
5. Deploy `.env` from template (mode 0600)
6. **Backup live config** (always runs):
   ```
   cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak.<epoch>
   ```
   Uses `stat` to check existence first; skips gracefully if absent.
7. **Deploy seed config** (only when absent OR `force_config=true`):
   - Uses `creates: ~/.openclaw/openclaw.json` — does not overwrite on upgrades
   - Override: `-e force_config=true` backs up then overwrites
8. Pull OpenClaw image — **tagged `image`** (skip with `--skip-tags image`)
9. `docker compose up -d --remove-orphans` — **tagged `image`**
10. Health check: `curl -sf http://localhost:18789` with retries

### Tags

```bash
# Full upgrade (pull new image + restart + config if absent)
ansible-playbook playbooks/jetson/deploy-openclaw.yml --limit jetson.lab -v

# Config update only, no image pull
ansible-playbook playbooks/jetson/deploy-openclaw.yml --limit jetson.lab --skip-tags image -v

# Force seed config overwrite (use after openclaw.json is corrupted or lost)
ansible-playbook playbooks/jetson/deploy-openclaw.yml --limit jetson.lab -e force_config=true -v
```

---

## Files Changed

| File | Action |
|------|--------|
| `ansible/playbooks/jetson/bootstrap-jetson.yml` | Create |
| `ansible/playbooks/jetson/deploy-openclaw.yml` | Revamp (replace) |
| `ansible/files/jetson/openclaw/docker-compose.yml` | Fix (container name, remove llama-server, fix mounts) |
| `ansible/files/jetson/openclaw/config/openclaw.json.j2` | Update (light seed: models, gateway, Slack, agent defaults) |
| `ansible/files/jetson/openclaw/.env.j2` | Minor update (add OPENAI_BASE_URL, SLACK tokens) |
| `ansible/group_vars/edge_devices/jetson.lab.yml` | Add vllm + Slack vars |

### docker-compose.yml fixes

- Container name: `openclaw` (was `openclaw-gateway`)
- Remove `llama-server` service + `depends_on`
- Fix mount: `/home/james/.openclaw:/root/.openclaw` only (drop duplicate `/home/node/` mount)
- Add workspace mount: `/home/james/bots/raclette:/workspace`
- `OPENAI_BASE_URL` from env (points to local vllm on port 8000)

### Seed config scope (openclaw.json.j2)

Included in seed:
- `models.providers` — lmstudio (spraycheese) + vllm (local)
- `agents.defaults` — primary model + fallback
- `gateway` — port, mode, auth token
- `channels.slack` — mode, botToken, appToken, groupPolicy, enabled
- `plugins.entries.slack.enabled`
- `hooks.internal` — session-memory, command-logger, boot-md

Not in seed (OpenClaw manages):
- `auth.profiles` (OAuth state)
- `wizard` (run history)
- `meta` (version tracking)
- `messages`, `commands` (user preferences, set via portal)

---

## Rollback

```bash
# Roll back openclaw.json to most recent backup
ssh james@192.168.20.169
ls -lt ~/.openclaw/openclaw.json.bak.* | head -3
cp ~/.openclaw/openclaw.json.bak.<ts> ~/.openclaw/openclaw.json
cd ~/docker/openclaw && docker compose restart openclaw
```
