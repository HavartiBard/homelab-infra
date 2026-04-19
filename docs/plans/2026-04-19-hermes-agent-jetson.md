# Hermes Agent Jetson Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy Hermes Agent on `jetson.lab` as a Docker service alongside OpenClaw, using spraycheese Ollama (primary) or Codex (secondary) as the LLM backend, exposed via web UI, SSH CLI, Slack Socket Mode, and stdio MCP.

**Architecture:** New Ansible role `jetson-hermes` + compose file in `ansible/files/jetson/hermes/`, following the identical pattern as `jetson-reasoning-llm`. Hermes runs as a persistent container on `jetson.lab`; all LLM inference routes to `spraycheese.lab.klsll.com:11434`. Slack uses Socket Mode (outbound WebSocket — no public endpoint). MCP is stdio via SSH.

**Tech Stack:** Ansible, Docker Compose, Hermes Agent (`ghcr.io/nousresearch/hermes-agent`), Ollama on spraycheese, Jinja2 templates, 1Password for secrets.

**Reference pattern:** `ansible/roles/jetson-reasoning-llm/` and `ansible/files/jetson/openclaw/` — copy this structure exactly.

**SSH key for jetson.lab:** `~/.ssh/id_ed25519` (not the homelab key)

---

### Task 0: Pre-flight checks

**Purpose:** Verify spraycheese Ollama is reachable from the Jetson and has a 64k-capable model. Hermes requires ≥64k context — this must be confirmed before deploying.

**Step 1: Check spraycheese Ollama is reachable from Jetson**

```bash
ssh -i ~/.ssh/id_ed25519 james@192.168.20.169 \
  "curl -s http://spraycheese.lab.klsll.com:11434/api/tags | python3 -m json.tool"
```

Expected: JSON list of models. If connection refused, spraycheese Ollama isn't LAN-accessible — stop and fix before continuing.

**Step 2: Identify a 64k-capable model**

Look for a model in the output above with sufficient parameter count. Models that support 64k context on spraycheese's VRAM (typically 24GB+):
- `qwen2.5-coder:32b` — good choice if present
- `llama3.1:70b-instruct-q4_K_M` — works if VRAM allows
- Any 32B+ model or a model explicitly configured with large context

Note the exact model name — you'll use it in Task 7 as `hermes_model_default`.

**Step 3: Check Hermes Docker image exists**

```bash
docker manifest inspect ghcr.io/nousresearch/hermes-agent:latest 2>&1 | head -5
```

Expected: JSON manifest. If 404/not found, check GitHub packages at https://github.com/NousResearch/hermes-agent/pkgs/container/hermes-agent for the correct image name and update Task 3 accordingly.

**Step 4: Discover Hermes web UI port**

```bash
docker run --rm ghcr.io/nousresearch/hermes-agent:latest hermes web --help 2>&1 || \
docker inspect ghcr.io/nousresearch/hermes-agent:latest 2>&1 | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('Exposed ports:', list(d[0]['Config']['ExposedPorts'].keys()) if d[0]['Config']['ExposedPorts'] else 'none')
"
```

Note the web UI port — update `hermes_web_port` in Task 2. Default assumption: `3333`.

---

### Task 1: Scaffold role directory structure

**Files to create (empty for now):**
- `ansible/roles/jetson-hermes/defaults/main.yml`
- `ansible/roles/jetson-hermes/tasks/main.yml`
- `ansible/files/jetson/hermes/docker-compose.yml`
- `ansible/files/jetson/hermes/.env.j2`
- `ansible/files/jetson/hermes/config/hermes.yaml.j2`
- `ansible/playbooks/misc/deploy-jetson-hermes.yml`

**Step 1: Create directories**

```bash
mkdir -p ansible/roles/jetson-hermes/{defaults,tasks}
mkdir -p ansible/files/jetson/hermes/config
```

**Step 2: Verify structure**

```bash
find ansible/roles/jetson-hermes ansible/files/jetson/hermes -type d
```

Expected output:
```
ansible/roles/jetson-hermes
ansible/roles/jetson-hermes/defaults
ansible/roles/jetson-hermes/tasks
ansible/files/jetson/hermes
ansible/files/jetson/hermes/config
```

---

### Task 2: Create role defaults

**File:** `ansible/roles/jetson-hermes/defaults/main.yml`

```yaml
---
# Defaults for the Hermes Agent deployment role.
# Hermes runs on jetson.lab; LLM inference routes to spraycheese or Codex.

# Deployment paths
hermes_deploy_dir: /home/james/docker/hermes
hermes_state_dir: /home/james/.hermes
hermes_codex_auth_file: /home/james/.codex/auth.json

# Container settings
hermes_image: ghcr.io/nousresearch/hermes-agent:latest
hermes_container_name: hermes
hermes_web_port: 3333   # update if Task 0 Step 4 found a different port

# File paths (derived)
hermes_compose_file: "{{ hermes_deploy_dir }}/docker-compose.yml"
hermes_env_file: "{{ hermes_deploy_dir }}/.env"
hermes_config_file: "{{ hermes_deploy_dir }}/config/hermes.yaml"

# Docker compose command
hermes_docker_compose_command: "docker compose"

# LLM configuration (spraycheese Ollama primary)
hermes_model_provider: custom
hermes_model_base_url: http://spraycheese.lab.klsll.com:11434/v1
hermes_model_default: qwen2.5-coder:32b   # update from Task 0 Step 2
hermes_model_context_length: 65536
hermes_model_api_key: ollama
```

**Step 1: Write the file**

Create `ansible/roles/jetson-hermes/defaults/main.yml` with the content above.

**Step 2: Verify YAML is valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('ansible/roles/jetson-hermes/defaults/main.yml'))" && echo OK
```

Expected: `OK`

---

### Task 3: Create docker-compose.yml

**File:** `ansible/files/jetson/hermes/docker-compose.yml`

```yaml
services:
  hermes:
    image: {{ hermes_image }}
    container_name: {{ hermes_container_name }}
    restart: unless-stopped
    network_mode: host
    stdin_open: true
    tty: true
    volumes:
      - {{ hermes_state_dir }}:/home/node/.hermes
      - {{ hermes_config_file }}:/home/node/.hermes/config.yaml:ro
      - {{ hermes_codex_auth_file }}:/home/node/.codex/auth.json:ro
    env_file:
      - {{ hermes_env_file }}
    environment:
      - HERMES_STATE_DIR=/home/node/.hermes
```

**Note on volumes:** The config is mounted read-only into the state dir so Hermes sees it as `~/.hermes/config.yaml`. Codex auth is mounted read-only from the host. If `hermes_codex_auth_file` doesn't exist on the Jetson yet (first deploy before Codex auth), add `: optional` to that volume line (Docker Compose v2 syntax) or create an empty file as a placeholder.

**Step 1: Write the file** — create `ansible/files/jetson/hermes/docker-compose.yml` with the above content.

**Step 2: Verify Jinja2 syntax is plausible**

```bash
python3 -c "
content = open('ansible/files/jetson/hermes/docker-compose.yml').read()
assert '{{ hermes_image }}' in content
assert '{{ hermes_container_name }}' in content
assert 'network_mode: host' in content
print('OK')
"
```

Expected: `OK`

---

### Task 4: Create .env.j2

**File:** `ansible/files/jetson/hermes/.env.j2`

```jinja2
{% for key, value in hermes_env | dictsort %}
{{ key }}={{ value }}
{% endfor %}
```

This follows the identical pattern as `ansible/files/jetson/openclaw/.env.j2`. Secrets are injected via `hermes_env` in group_vars (Task 7).

**Step 1: Write the file**

Create `ansible/files/jetson/hermes/.env.j2` with the content above.

---

### Task 5: Create hermes.yaml.j2

**File:** `ansible/files/jetson/hermes/config/hermes.yaml.j2`

```jinja2
model:
  provider: {{ hermes_model_provider }}
  base_url: {{ hermes_model_base_url }}
  default: {{ hermes_model_default }}
  context_length: {{ hermes_model_context_length }}
  api_key: {{ hermes_model_api_key }}

messaging:
  slack:
    enabled: true
    allowed_users: "{{ hermes_env.SLACK_ALLOWED_USERS }}"

terminal:
  backend: local

web:
  port: {{ hermes_web_port }}
  bind: 0.0.0.0
```

**Step 1: Write the file**

Create `ansible/files/jetson/hermes/config/hermes.yaml.j2` with the content above.

---

### Task 6: Create role tasks

**File:** `ansible/roles/jetson-hermes/tasks/main.yml`

```yaml
---
- name: Ensure Hermes deploy directory exists
  ansible.builtin.file:
    path: "{{ hermes_deploy_dir }}"
    state: directory
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0755'

- name: Ensure Hermes config directory exists
  ansible.builtin.file:
    path: "{{ hermes_deploy_dir }}/config"
    state: directory
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0755'

- name: Ensure Hermes state directory exists
  ansible.builtin.file:
    path: "{{ hermes_state_dir }}"
    state: directory
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0700'

- name: Ensure Codex auth directory exists
  ansible.builtin.file:
    path: "{{ hermes_codex_auth_file | dirname }}"
    state: directory
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0700'

- name: Render .env for Hermes container
  ansible.builtin.template:
    src: "{{ playbook_dir }}/../../files/jetson/hermes/.env.j2"
    dest: "{{ hermes_env_file }}"
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0600'

- name: Render hermes.yaml config
  ansible.builtin.template:
    src: "{{ playbook_dir }}/../../files/jetson/hermes/config/hermes.yaml.j2"
    dest: "{{ hermes_config_file }}"
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0600'

- name: Render Docker Compose definition
  ansible.builtin.template:
    src: "{{ playbook_dir }}/../../files/jetson/hermes/docker-compose.yml"
    dest: "{{ hermes_compose_file }}"
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0644'

- name: Deploy Hermes stack with Docker Compose
  ansible.builtin.shell: |
    set -euo pipefail
    cd "{{ hermes_deploy_dir }}"
    {{ hermes_docker_compose_command }} pull
    {{ hermes_docker_compose_command }} up -d
  register: hermes_deploy
  args:
    executable: /bin/bash

- name: Validate Hermes container is running
  ansible.builtin.shell: |
    set -euo pipefail
    docker inspect -f {{ '{{.State.Running}}' }} {{ hermes_container_name }}
  register: hermes_running
  failed_when: hermes_running.stdout | trim != 'true'
  changed_when: false
  args:
    executable: /bin/bash
```

**Step 1: Write the file**

Create `ansible/roles/jetson-hermes/tasks/main.yml` with the content above.

**Step 2: Verify YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('ansible/roles/jetson-hermes/tasks/main.yml'))" && echo OK
```

Expected: `OK`

---

### Task 7: Update group_vars

**File:** `ansible/group_vars/edge_devices/jetson.lab.yml`

Add the following block at the end of the existing file (do not remove existing content):

```yaml

# Hermes Agent
hermes_env:
  SLACK_BOT_TOKEN: >-
    {{ lookup('env', 'SLACK_BOT_TOKEN') | default('CHANGEME_SLACK_BOT_TOKEN', true) }}
  SLACK_APP_TOKEN: >-
    {{ lookup('env', 'SLACK_APP_TOKEN') | default('CHANGEME_SLACK_APP_TOKEN', true) }}
  SLACK_ALLOWED_USERS: >-
    {{ lookup('env', 'SLACK_ALLOWED_USERS') | default('CHANGEME_SLACK_MEMBER_IDS', true) }}
```

**Step 1: Read the current file**

```bash
cat ansible/group_vars/edge_devices/jetson.lab.yml
```

**Step 2: Append the hermes block**

Use Edit to append the block above to the end of `ansible/group_vars/edge_devices/jetson.lab.yml`.

**Step 3: Verify YAML is still valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('ansible/group_vars/edge_devices/jetson.lab.yml'))" && echo OK
```

Expected: `OK`

---

### Task 8: Create playbook

**File:** `ansible/playbooks/misc/deploy-jetson-hermes.yml`

```yaml
---
# Deploy Hermes Agent to jetson.lab
#
# Hermes is a self-improving AI agent (Nous Research) with persistent memory,
# Slack integration, and MCP server support. LLM inference routes to spraycheese.
#
# Required environment variables:
#   SLACK_BOT_TOKEN    - xoxb- bot token from Slack app
#   SLACK_APP_TOKEN    - xapp- Socket Mode token from Slack app
#   SLACK_ALLOWED_USERS - comma-separated Slack member IDs
#
# Usage:
#   SLACK_BOT_TOKEN=xoxb-... SLACK_APP_TOKEN=xapp-... SLACK_ALLOWED_USERS=U... \
#     ansible-playbook playbooks/misc/deploy-jetson-hermes.yml --limit jetson.lab
#
# Verify:
#   ssh james@192.168.20.169 "docker ps | grep hermes"
#   ssh james@192.168.20.169 "docker logs hermes --tail 20"

- name: Deploy Hermes Agent to Jetson
  hosts: jetson.lab
  gather_facts: no
  become: false
  roles:
    - jetson-hermes
```

**Step 1: Write the file**

Create `ansible/playbooks/misc/deploy-jetson-hermes.yml` with the content above.

---

### Task 9: Syntax check

**Step 1: Run syntax check from ansible/ directory**

```bash
cd ansible && ansible-playbook playbooks/misc/deploy-jetson-hermes.yml --syntax-check
```

Expected: `playbook: playbooks/misc/deploy-jetson-hermes.yml` with no errors.

**If you see errors:** Fix the YAML or template path issues before continuing. Common mistakes:
- Indentation errors in YAML
- `src:` paths not matching actual file locations
- Missing `---` at start of YAML files

---

### Task 10: Dry run

**Step 1: Export placeholder secrets**

```bash
export SLACK_BOT_TOKEN=xoxb-placeholder
export SLACK_APP_TOKEN=xapp-placeholder
export SLACK_ALLOWED_USERS=UPLACEHOLDER
```

**Step 2: Run check mode**

```bash
cd ansible && ansible-playbook playbooks/misc/deploy-jetson-hermes.yml \
  --check --diff --limit jetson.lab -v
```

Expected: All tasks show `ok` or `changed` (check mode). The `Deploy Hermes stack` and `Validate container` tasks will likely show as skipped or failed in check mode (they run shell commands) — this is acceptable.

**If template tasks fail:** The error will show which variable is undefined. Check group_vars and defaults for the missing variable.

---

### Task 11: Commit skeleton (before live deploy)

```bash
git add \
  ansible/roles/jetson-hermes/ \
  ansible/files/jetson/hermes/ \
  ansible/playbooks/misc/deploy-jetson-hermes.yml \
  ansible/group_vars/edge_devices/jetson.lab.yml

git commit -m "feat(jetson): Add Hermes Agent deployment role and playbook"
```

---

### Task 12: Add secrets to 1Password and deploy

**Step 1: Create Slack app** (manual — do this before deploying)

1. Go to https://api.slack.com/apps → Create New App → From scratch
2. Enable Socket Mode → generate App-Level Token with `connections:write` scope → save as `SLACK_APP_TOKEN`
3. OAuth & Permissions → add scopes: `chat:write`, `app_mentions:read`, `channels:history`, `channels:read`, `groups:history`, `im:history`, `im:read`, `im:write`, `users:read`, `files:read`, `files:write`
4. Event Subscriptions → enable → subscribe to: `message.im`, `message.channels`, `message.groups`, `app_mention`
5. Install to workspace → copy Bot User OAuth Token → save as `SLACK_BOT_TOKEN`
6. Get your Slack member ID: click your profile → "Copy member ID" → save as `SLACK_ALLOWED_USERS`

**Step 2: Read tokens via op**

```bash
export SLACK_BOT_TOKEN=$(op read "op://AI Wedge/Hermes Slack Bot/bot_token")
export SLACK_APP_TOKEN=$(op read "op://AI Wedge/Hermes Slack Bot/app_token")
export SLACK_ALLOWED_USERS=$(op read "op://AI Wedge/Hermes Slack Bot/allowed_users")
```

(If you haven't added these to 1Password yet, use the env vars directly and add them to 1Password afterward.)

**Step 3: Deploy**

```bash
cd ansible && ansible-playbook playbooks/misc/deploy-jetson-hermes.yml \
  --diff --limit jetson.lab -v
```

Expected: All tasks `ok` or `changed`. Final task "Validate Hermes container is running" must show `ok`.

**Step 4: Verify container is up**

```bash
ssh -i ~/.ssh/id_ed25519 james@192.168.20.169 "docker ps | grep hermes"
```

Expected: One line showing `hermes` container with `Up` status.

**Step 5: Check logs for successful startup**

```bash
ssh -i ~/.ssh/id_ed25519 james@192.168.20.169 "docker logs hermes --tail 30"
```

Expected: Hermes startup messages, model connection confirmation, Slack Socket Mode connected.

**Step 6: Test CLI**

```bash
ssh -i ~/.ssh/id_ed25519 james@192.168.20.169 "docker exec -it hermes hermes --version"
```

Expected: Version string.

---

### Task 13: Configure MCP in Claude Code

**File:** `~/.claude.json`

Add the following entry under `mcpServers`:

```json
"hermes": {
  "type": "stdio",
  "command": "ssh",
  "args": ["-i", "~/.ssh/id_ed25519", "james@192.168.20.169", "docker", "exec", "-i", "hermes", "hermes", "mcp", "serve"]
}
```

**Step 1: Open ~/.claude.json and add the entry under mcpServers**

**Step 2: Verify MCP connection**

Restart Claude Code and check that `hermes` appears in the MCP server list. Run:

```
/mcp
```

Expected: `hermes` listed as connected.

---

### Task 14: Final commit

```bash
git add ~/.claude.json 2>/dev/null || true   # only if you want to track this
git commit --allow-empty -m "docs: Hermes Agent Jetson deployment complete" \
  --allow-empty
```

Or just verify the prior commit covers all files:

```bash
git log --oneline -3
git show --stat HEAD
```

---

## Post-Deploy Verification Checklist

```bash
# Container running
ssh james@192.168.20.169 "docker ps | grep hermes"

# Hermes can reach spraycheese Ollama
ssh james@192.168.20.169 "docker exec hermes curl -s http://spraycheese.lab.klsll.com:11434/api/tags | python3 -m json.tool | head -10"

# Web UI reachable (update port if different)
curl -s http://192.168.20.169:3333 | head -5

# Slack: send the bot a DM in Slack — it should respond

# MCP: test from Claude Code
# Run /mcp and confirm hermes is listed
```

## Rollback

```bash
ssh -i ~/.ssh/id_ed25519 james@192.168.20.169 \
  "cd /home/james/docker/hermes && docker compose down"
```

State is preserved in `/home/james/.hermes` — container can be brought back up with `docker compose up -d`.
