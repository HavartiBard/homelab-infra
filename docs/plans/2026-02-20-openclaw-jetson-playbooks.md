# OpenClaw Jetson Playbooks Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Revamp the OpenClaw Ansible deploy playbook to match live state, and create a self-contained Jetson bootstrap playbook.

**Architecture:** Two playbooks — `bootstrap-jetson.yml` takes a fresh Jetson to fully operational (Docker CE + NVIDIA toolkit + zsh + dirs + env); `deploy-openclaw.yml` deploys or upgrades OpenClaw with seed config backup strategy. vLLM container stays separate and is not touched.

**Tech Stack:** Ansible, Docker Compose, Jinja2 templates. SSH key: `~/.ssh/id_ed25519` for jetson.lab (192.168.20.169). Inventory group: `edge_devices`.

**Design doc:** `docs/plans/2026-02-20-openclaw-jetson-deploy-design.md`

---

## Pre-flight

Verify target is reachable and gather current state:

```bash
cd ansible
ssh -i ~/.ssh/id_ed25519 192.168.20.169 "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

Expected: `openclaw` and `vllm-qwen` both Up.

Required env vars for deploy tasks (source from `.env_container` or 1Password):
```bash
export OPENCLAW_GATEWAY_TOKEN=$(op read "op://AI Wedge/OpenClaw Gateway/credential" 2>/dev/null || echo "$OPENCLAW_GATEWAY_TOKEN")
export SLACK_BOT_TOKEN=$(op read "op://AI Wedge/OpenClaw Slack Bot Token/credential" 2>/dev/null || echo "$SLACK_BOT_TOKEN")
export SLACK_APP_TOKEN=$(op read "op://AI Wedge/OpenClaw Slack App Token/credential" 2>/dev/null || echo "$SLACK_APP_TOKEN")
export LMSTUDIO_API_KEY=$(op read "op://AI Wedge/LM Studio API Key/credential" 2>/dev/null || echo "$LMSTUDIO_API_KEY")
```

> Note: if 1Password paths differ, use `op item list --vault "AI Wedge"` to find them. The values are also in `.env_container` on the Jetson itself (ssh in and `cat ~/.env_container`).

---

## Task 1: Create feature branch

**Step 1: Branch from main**
```bash
cd /home/james/projects/homelab-infra
git checkout main && git pull
git checkout -b feature/openclaw-jetson-playbooks
```

**Step 2: Verify clean state**
```bash
git status
```
Expected: `nothing to commit, working tree clean` on new branch.

---

## Task 2: Fix docker-compose.yml

**Files:**
- Modify: `ansible/files/jetson/openclaw/docker-compose.yml`

**Current problems:** container named `openclaw-gateway`, depends on dead `llama-server` service, double-mounted state dir.

**Step 1: Replace the file entirely**

Write `ansible/files/jetson/openclaw/docker-compose.yml`:

```yaml
services:
  openclaw:
    image: ghcr.io/openclaw/openclaw:latest
    container_name: openclaw
    restart: unless-stopped
    network_mode: host
    command:
      - node
      - dist/index.js
      - gateway
      - --port
      - "18789"
      - --bind
      - lan
    volumes:
      - /home/james/.openclaw:/root/.openclaw
      - /home/james/bots/raclette:/workspace
    env_file:
      - .env
    environment:
      - OPENCLAW_STATE_DIR=/root/.openclaw
```

Key changes:
- Service + container name: `openclaw` (matches live)
- No `llama-server`, no `depends_on`
- Single mount: `~/.openclaw:/root/.openclaw` only (root is the user in the container)
- Workspace mount preserved: `~/bots/raclette:/workspace`
- `OPENCLAW_STATE_DIR` updated to `/root/.openclaw`

**Step 2: Validate**
```bash
# Validate syntax locally (no remote needed)
docker compose -f ansible/files/jetson/openclaw/docker-compose.yml config
```
Expected: valid YAML printed with no errors.

**Step 3: Commit**
```bash
git add ansible/files/jetson/openclaw/docker-compose.yml
git commit -m "fix(openclaw): correct compose file to match live state"
```

---

## Task 3: Update .env.j2

**Files:**
- Modify: `ansible/files/jetson/openclaw/.env.j2`

**Current state:** renders all keys from `jetson_openclaw_env` dict. Fine, but the dict needs more vars.

**Step 1: Verify template is still correct**

The template at `ansible/files/jetson/openclaw/.env.j2` should be:
```jinja2
{% for key, value in jetson_openclaw_env | dictsort %}
{{ key }}={{ value }}
{% endfor %}
```
No changes needed to the template itself — only the vars dict changes in Task 5.

---

## Task 4: Update openclaw.json.j2 seed config

**Files:**
- Modify: `ansible/files/jetson/openclaw/config/openclaw.json.j2`

This is the light seed deployed on first install. Slack tokens and gateway token come from env vars (already in `.env_container` on Jetson and sourced at playbook run time).

**Step 1: Replace the file entirely**

Write `ansible/files/jetson/openclaw/config/openclaw.json.j2`:

```json
{
  "models": {
    "providers": {
      "lmstudio": {
        "baseUrl": "{{ jetson_lmstudio_base_url }}",
        "apiKey": "{{ lookup('env', 'LMSTUDIO_API_KEY') | default('sk-local', true) }}",
        "api": "openai-completions",
        "models": [
          {
            "id": "qwen3-coder-30b-a3b-instruct",
            "name": "Qwen3 Coder 30B A3B Instruct",
            "reasoning": true,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 262144,
            "maxTokens": 8192
          },
          {
            "id": "openai/gpt-oss-20b",
            "name": "gpt-oss-20b",
            "reasoning": true,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 131072,
            "maxTokens": 4096
          }
        ]
      },
      "vllm": {
        "baseUrl": "{{ jetson_vllm_base_url }}",
        "apiKey": "vllm-local",
        "api": "openai-completions",
        "models": [
          {
            "id": "google/functiongemma-270m-it",
            "name": "FunctionGemma 270M IT (local vLLM)",
            "reasoning": false,
            "input": ["text"],
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            "contextWindow": 32768,
            "maxTokens": 1024
          }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "lmstudio/openai/gpt-oss-20b",
        "fallbacks": [
          "vllm/google/functiongemma-270m-it"
        ]
      },
      "memorySearch": {
        "enabled": false
      },
      "compaction": {
        "memoryFlush": {
          "enabled": false
        }
      }
    }
  },
  "gateway": {
    "port": {{ jetson_openclaw_port }},
    "mode": "local",
    "auth": {
      "mode": "token",
      "token": "{{ lookup('env', 'OPENCLAW_GATEWAY_TOKEN') | default('CHANGEME_SET_OPENCLAW_GATEWAY_TOKEN', true) }}"
    }
  },
  "channels": {
    "slack": {
      "mode": "socket",
      "enabled": true,
      "botToken": "{{ lookup('env', 'SLACK_BOT_TOKEN') | default('CHANGEME_SET_SLACK_BOT_TOKEN', true) }}",
      "appToken": "{{ lookup('env', 'SLACK_APP_TOKEN') | default('CHANGEME_SET_SLACK_APP_TOKEN', true) }}",
      "userTokenReadOnly": true,
      "allowBots": true,
      "groupPolicy": "open",
      "actions": {
        "messages": true,
        "channelInfo": true,
        "emojiList": true
      }
    }
  },
  "plugins": {
    "entries": {
      "slack": {
        "enabled": true
      }
    }
  },
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {
        "session-memory": {"enabled": true},
        "command-logger": {"enabled": true},
        "boot-md": {"enabled": true}
      }
    }
  },
  "skills": {
    "install": {
      "nodeManager": "npm"
    }
  }
}
```

**Step 2: Commit**
```bash
git add ansible/files/jetson/openclaw/config/openclaw.json.j2
git commit -m "fix(openclaw): update seed config with vllm provider and Slack"
```

---

## Task 5: Update group_vars

**Files:**
- Modify: `ansible/group_vars/edge_devices/jetson.lab.yml`

**Step 1: Update the file**

Replace the `jetson_openclaw_env` block and add missing vars. Full new content of `ansible/group_vars/edge_devices/jetson.lab.yml`:

```yaml
---
trtllm_models_host_dir: /home/james/models/tensorrt_llm
trtllm_cache_host_dir: /home/james/.cache/huggingface
trtllm_app_dir: /opt/trtllm

# OpenClaw
jetson_openclaw_deploy_dir: /home/james/docker/openclaw
jetson_openclaw_state_dir: /home/james/.openclaw
jetson_openclaw_workspace_dir: /home/james/bots/raclette
jetson_openclaw_image: ghcr.io/openclaw/openclaw:latest
jetson_openclaw_port: 18789

# Model provider endpoints
jetson_vllm_base_url: http://127.0.0.1:8000/v1
jetson_lmstudio_base_url: "{{ lookup('env', 'LMSTUDIO_BASE_URL') | default('http://spraycheese.lab.klsll.com:1234/v1', true) }}"

# .env rendered into ~/docker/openclaw/.env
# Secrets sourced from env vars (present in ~/.env_container on Jetson,
# and required as env vars on the Ansible controller at playbook run time)
jetson_openclaw_env:
  LMSTUDIO_API_KEY: >-
    {{ lookup('env', 'LMSTUDIO_API_KEY') | default('CHANGEME_LMSTUDIO_API_KEY', true) }}
  LMSTUDIO_BASE_URL: "{{ jetson_lmstudio_base_url }}"
  OPENAI_BASE_URL: "{{ jetson_vllm_base_url }}"
  OPENCLAW_GATEWAY_MODE: local
  OPENCLAW_GATEWAY_BIND: lan
  OPENCLAW_GATEWAY_TOKEN: >-
    {{ lookup('env', 'OPENCLAW_GATEWAY_TOKEN') | default('CHANGEME_OPENCLAW_GATEWAY_TOKEN', true) }}
  SLACK_BOT_TOKEN: >-
    {{ lookup('env', 'SLACK_BOT_TOKEN') | default('CHANGEME_SLACK_BOT_TOKEN', true) }}
  SLACK_APP_TOKEN: >-
    {{ lookup('env', 'SLACK_APP_TOKEN') | default('CHANGEME_SLACK_APP_TOKEN', true) }}
```

**Step 2: Commit**
```bash
git add ansible/group_vars/edge_devices/jetson.lab.yml
git commit -m "fix(openclaw): add vllm and Slack vars to jetson group_vars"
```

---

## Task 6: Revamp deploy-openclaw.yml

**Files:**
- Modify: `ansible/playbooks/jetson/deploy-openclaw.yml`

**Step 1: Replace the playbook entirely**

Write `ansible/playbooks/jetson/deploy-openclaw.yml`:

```yaml
---
# Deploy or upgrade OpenClaw gateway on Jetson.
#
# Required env vars (sourced from ~/.env_container or set manually):
#   OPENCLAW_GATEWAY_TOKEN, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, LMSTUDIO_API_KEY
#
# Usage:
#   Full upgrade (pull image + restart):
#     ansible-playbook playbooks/jetson/deploy-openclaw.yml --limit jetson.lab -v
#
#   Config update only (no image pull):
#     ansible-playbook playbooks/jetson/deploy-openclaw.yml --limit jetson.lab --skip-tags image -v
#
#   Force seed config overwrite (e.g. after corruption):
#     ansible-playbook playbooks/jetson/deploy-openclaw.yml --limit jetson.lab -e force_config=true -v

- name: Deploy OpenClaw gateway on Jetson
  hosts: edge_devices
  gather_facts: false
  vars:
    force_config: false

  tasks:
    - name: Ensure OpenClaw deploy directory exists
      ansible.builtin.file:
        path: "{{ jetson_openclaw_deploy_dir }}"
        state: directory
        owner: james
        group: james
        mode: '0755'

    - name: Ensure OpenClaw state directory exists
      ansible.builtin.file:
        path: "{{ jetson_openclaw_state_dir }}"
        state: directory
        owner: james
        group: james
        mode: '0755'

    - name: Ensure OpenClaw workspace directory exists
      ansible.builtin.file:
        path: "{{ jetson_openclaw_workspace_dir }}"
        state: directory
        owner: james
        group: james
        mode: '0755'

    - name: Deploy docker-compose.yml
      ansible.builtin.copy:
        src: "{{ playbook_dir }}/../../files/jetson/openclaw/docker-compose.yml"
        dest: "{{ jetson_openclaw_deploy_dir }}/docker-compose.yml"
        owner: james
        group: james
        mode: '0644'

    - name: Deploy .env file
      ansible.builtin.template:
        src: "{{ playbook_dir }}/../../files/jetson/openclaw/.env.j2"
        dest: "{{ jetson_openclaw_deploy_dir }}/.env"
        owner: james
        group: james
        mode: '0600'

    - name: Check if live openclaw.json exists
      ansible.builtin.stat:
        path: "{{ jetson_openclaw_state_dir }}/openclaw.json"
      register: openclaw_config_stat

    - name: Get timestamp for config backup
      ansible.builtin.command: date +%s
      register: backup_timestamp
      changed_when: false
      when: openclaw_config_stat.stat.exists

    - name: Backup live openclaw.json before deploy
      ansible.builtin.copy:
        src: "{{ jetson_openclaw_state_dir }}/openclaw.json"
        dest: "{{ jetson_openclaw_state_dir }}/openclaw.json.bak.{{ backup_timestamp.stdout }}"
        remote_src: true
        owner: james
        group: james
        mode: '0600'
      when: openclaw_config_stat.stat.exists

    - name: Deploy seed openclaw.json (only if absent or force_config=true)
      ansible.builtin.template:
        src: "{{ playbook_dir }}/../../files/jetson/openclaw/config/openclaw.json.j2"
        dest: "{{ jetson_openclaw_state_dir }}/openclaw.json"
        owner: james
        group: james
        mode: '0600'
      when: not openclaw_config_stat.stat.exists or (force_config | bool)

    - name: Pull OpenClaw image
      ansible.builtin.command:
        cmd: docker compose pull
        chdir: "{{ jetson_openclaw_deploy_dir }}"
      tags: [image]

    - name: Start or restart OpenClaw stack
      ansible.builtin.command:
        cmd: docker compose up -d --remove-orphans
        chdir: "{{ jetson_openclaw_deploy_dir }}"
      tags: [image]

    - name: Wait for OpenClaw gateway to become available
      ansible.builtin.uri:
        url: "http://127.0.0.1:{{ jetson_openclaw_port }}"
        status_code: [200, 401, 403, 404]
      register: openclaw_health
      retries: 10
      delay: 3
      until: openclaw_health.status in [200, 401, 403, 404]
      tags: [image]

    - name: Report OpenClaw container status
      ansible.builtin.command:
        cmd: docker ps --filter name=openclaw --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
      register: container_status
      changed_when: false

    - name: Show container status
      ansible.builtin.debug:
        msg: "{{ container_status.stdout_lines }}"
```

**Step 2: Commit**
```bash
git add ansible/playbooks/jetson/deploy-openclaw.yml
git commit -m "feat(openclaw): revamp deploy playbook with backup strategy and correct config"
```

---

## Task 7: Validate and apply deploy-openclaw.yml

**Step 1: Syntax check**
```bash
cd ansible
ansible-playbook playbooks/jetson/deploy-openclaw.yml --syntax-check
```
Expected: `playbook: playbooks/jetson/deploy-openclaw.yml` with no errors.

**Step 2: Dry run**
```bash
ansible-playbook playbooks/jetson/deploy-openclaw.yml \
  --check --diff --limit jetson.lab -v
```
Expected output to review:
- Dirs exist → no change
- `docker-compose.yml` diff shows: service `openclaw` (was `openclaw-gateway`), no `llama-server`
- `.env` diff shows new `OPENAI_BASE_URL`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`
- Backup task: skipped (check mode can't run command)
- Seed config: skipped (file exists and `force_config=false`)
- Image pull + up: shown as would-change

**Step 3: Apply**
```bash
ansible-playbook playbooks/jetson/deploy-openclaw.yml \
  --diff --limit jetson.lab -v
```

**Step 4: Verify on Jetson**
```bash
ssh -i ~/.ssh/id_ed25519 192.168.20.169 \
  "docker ps --filter name=openclaw --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'"
```
Expected: `openclaw   Up X seconds   ghcr.io/openclaw/openclaw:latest`

**Step 5: Verify backup was created**
```bash
ssh -i ~/.ssh/id_ed25519 192.168.20.169 \
  "ls -lt ~/.openclaw/openclaw.json.bak.* | head -3"
```
Expected: at least one `.bak.<timestamp>` file.

**Step 6: Verify idempotence**
```bash
ansible-playbook playbooks/jetson/deploy-openclaw.yml \
  --check --diff --limit jetson.lab --skip-tags image -v
```
Expected: `changed=0` for all non-image tasks (dirs, compose, env, config).

**Step 7: Commit nothing** — playbook was already committed. If fixes were needed, commit them now.

---

## Task 8: Create bootstrap-jetson.yml

**Files:**
- Create: `ansible/playbooks/jetson/bootstrap-jetson.yml`

This playbook takes a freshly-flashed Jetson (Ubuntu 22.04, arm64) to fully operational. It reuses the existing templates in `ansible/templates/bootstrap-ubuntu/`.

**Step 1: Write the playbook**

Write `ansible/playbooks/jetson/bootstrap-jetson.yml`:

```yaml
---
# Bootstrap a Jetson Orin Nano from bare Ubuntu 22.04 to fully operational.
#
# Covers: base packages, 1Password CLI, Docker CE, NVIDIA Container Toolkit,
#         Oh My Zsh, SSH keys, timezone, standard directories, CUDA PATH, .env_container.
#
# Safe to re-run (idempotent). Does NOT touch vLLM or OpenClaw — use deploy-openclaw.yml.
#
# Usage:
#   ansible-playbook playbooks/jetson/bootstrap-jetson.yml \
#     -e target_hosts=jetson.lab --limit jetson.lab -v
#
# Required: SSH access as a user with sudo. Default user: james.

- name: Bootstrap Jetson Orin Nano
  hosts: edge_devices
  gather_facts: true
  become: true
  vars:
    bootstrap_user: james
    bootstrap_user_home: "/home/{{ bootstrap_user }}"
    bootstrap_timezone: America/Phoenix
    bootstrap_public_key: "{{ lookup('env','HOME') }}/.ssh/id_ed25519_homelab.pub"
    bootstrap_zsh_install_dir: /opt/oh-my-zsh
    bootstrap_zsh_theme: pure
    bootstrap_zsh_plugins:
      - git
      - docker
      - docker-compose
      - sudo
      - zsh-autosuggestions
      - zsh-syntax-highlighting
    bootstrap_packages:
      - git
      - zsh
      - curl
      - wget
      - ca-certificates
      - gnupg
      - lsb-release
      - software-properties-common
      - openssh-server
      - python3-pip
      - htop
      - vim
      - jq
    bootstrap_dirs:
      - "{{ bootstrap_user_home }}/docker"
      - "{{ bootstrap_user_home }}/models"
      - "{{ bootstrap_user_home }}/bots"
      - "{{ bootstrap_user_home }}/.openclaw"
      - "{{ bootstrap_user_home }}/projects"
      - "{{ bootstrap_user_home }}/.cache/oh-my-zsh"
    # env_container vars: sourced from group_vars/edge_devices vault
    # Uses the same template as bootstrap-ubuntu (ubuntu_env_container_vars)
    ubuntu_env_container_vars: "{{ jetson_env_container_vars | default({}) }}"

  pre_tasks:
    - name: Require target_hosts safety guard
      ansible.builtin.assert:
        that:
          - target_hosts is defined
          - inventory_hostname in (target_hosts | regex_replace('\\s+', '') | split(','))
        fail_msg: |
          target_hosts is not set or does not include {{ inventory_hostname }}.
          Run with: -e target_hosts=jetson.lab

    - name: Verify Ubuntu 22.04 (aarch64)
      ansible.builtin.assert:
        that:
          - ansible_distribution == 'Ubuntu'
          - ansible_architecture == 'aarch64'
        fail_msg: "Expected Ubuntu aarch64, got {{ ansible_distribution }} {{ ansible_architecture }}"

  handlers:
    - name: Restart Docker
      ansible.builtin.service:
        name: docker
        state: restarted

  tasks:
    # ── Base packages ──────────────────────────────────────────────────────────

    - name: Refresh apt cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600

    - name: Install base packages
      ansible.builtin.apt:
        name: "{{ bootstrap_packages }}"
        state: present

    - name: Determine dpkg architecture
      ansible.builtin.command: dpkg --print-architecture
      register: dpkg_arch
      changed_when: false

    # ── 1Password CLI ──────────────────────────────────────────────────────────

    - name: Ensure 1Password keyring directories exist
      ansible.builtin.file:
        path: "{{ item }}"
        state: directory
        mode: '0755'
      loop:
        - /usr/share/keyrings
        - /etc/debsig/policies/AC2D62742012EA22
        - /usr/share/debsig/keyrings/AC2D62742012EA22

    - name: Download 1Password public key
      ansible.builtin.get_url:
        url: https://downloads.1password.com/linux/keys/1password.asc
        dest: /tmp/1password.asc
        mode: '0644'

    - name: Create 1Password apt keyring
      ansible.builtin.command: >
        gpg --dearmor -o /usr/share/keyrings/1password-archive-keyring.gpg /tmp/1password.asc
      args:
        creates: /usr/share/keyrings/1password-archive-keyring.gpg

    - name: Install 1Password debsig policy
      ansible.builtin.get_url:
        url: https://downloads.1password.com/linux/debian/debsig/1password.pol
        dest: /etc/debsig/policies/AC2D62742012EA22/1password.pol
        mode: '0644'

    - name: Create 1Password debsig keyring
      ansible.builtin.command: >
        gpg --dearmor -o /usr/share/debsig/keyrings/AC2D62742012EA22/debsig.gpg /tmp/1password.asc
      args:
        creates: /usr/share/debsig/keyrings/AC2D62742012EA22/debsig.gpg

    - name: Add 1Password apt repository
      ansible.builtin.apt_repository:
        repo: "deb [arch={{ dpkg_arch.stdout }} signed-by=/usr/share/keyrings/1password-archive-keyring.gpg] https://downloads.1password.com/linux/debian/{{ dpkg_arch.stdout }} stable main"
        filename: 1password
        state: present

    - name: Install 1Password CLI
      ansible.builtin.apt:
        name: 1password-cli
        state: present
        update_cache: true

    - name: Remove temporary 1Password key material
      ansible.builtin.file:
        path: /tmp/1password.asc
        state: absent

    # ── Docker CE ──────────────────────────────────────────────────────────────

    - name: Ensure Docker keyring directory exists
      ansible.builtin.file:
        path: /etc/apt/keyrings
        state: directory
        mode: '0755'

    - name: Download Docker GPG key
      ansible.builtin.get_url:
        url: https://download.docker.com/linux/ubuntu/gpg
        dest: /etc/apt/keyrings/docker.asc
        mode: '0644'

    - name: Add Docker apt repository
      ansible.builtin.apt_repository:
        repo: "deb [arch={{ dpkg_arch.stdout }} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu {{ ansible_distribution_release }} stable"
        filename: docker
        state: present

    - name: Install Docker CE packages
      ansible.builtin.apt:
        name:
          - docker-ce
          - docker-ce-cli
          - containerd.io
          - docker-buildx-plugin
          - docker-compose-plugin
        state: present
        update_cache: true

    - name: Add {{ bootstrap_user }} to docker group
      ansible.builtin.user:
        name: "{{ bootstrap_user }}"
        groups: docker
        append: true

    - name: Ensure Docker service is enabled and running
      ansible.builtin.service:
        name: docker
        state: started
        enabled: true

    # ── NVIDIA Container Toolkit ───────────────────────────────────────────────

    - name: Ensure NVIDIA keyring directory exists
      ansible.builtin.file:
        path: /usr/share/keyrings
        state: directory
        mode: '0755'

    - name: Download NVIDIA container toolkit GPG key
      ansible.builtin.get_url:
        url: https://nvidia.github.io/libnvidia-container/gpgkey
        dest: /tmp/nvidia-ctk.gpg.asc
        mode: '0644'

    - name: Create NVIDIA container toolkit keyring
      ansible.builtin.command: >
        gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg /tmp/nvidia-ctk.gpg.asc
      args:
        creates: /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

    - name: Add NVIDIA container toolkit apt repository
      ansible.builtin.apt_repository:
        repo: "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/{{ dpkg_arch.stdout }} /"
        filename: nvidia-container-toolkit
        state: present

    - name: Install NVIDIA container toolkit
      ansible.builtin.apt:
        name: nvidia-container-toolkit
        state: present
        update_cache: true

    - name: Configure Docker to use nvidia runtime
      ansible.builtin.command:
        cmd: nvidia-ctk runtime configure --runtime=docker --set-as-default
      register: nvidia_ctk_result
      changed_when: "'already configured' not in nvidia_ctk_result.stdout"
      notify: Restart Docker

    - name: Remove temporary NVIDIA GPG key
      ansible.builtin.file:
        path: /tmp/nvidia-ctk.gpg.asc
        state: absent

    # ── User, SSH, timezone ────────────────────────────────────────────────────

    - name: Ensure bootstrap user exists
      ansible.builtin.user:
        name: "{{ bootstrap_user }}"
        shell: /bin/zsh
        home: "{{ bootstrap_user_home }}"
        create_home: true
        groups: sudo
        append: true

    - name: Ensure SSH directory exists
      ansible.builtin.file:
        path: "{{ bootstrap_user_home }}/.ssh"
        state: directory
        owner: "{{ bootstrap_user }}"
        group: "{{ bootstrap_user }}"
        mode: '0700'

    - name: Deploy authorized SSH key
      ansible.posix.authorized_key:
        user: "{{ bootstrap_user }}"
        key: "{{ lookup('file', bootstrap_public_key) }}"
        manage_dir: true
        state: present

    - name: Ensure SSH service is running
      ansible.builtin.service:
        name: ssh
        state: started
        enabled: true

    - name: Set timezone to {{ bootstrap_timezone }}
      ansible.builtin.command: timedatectl set-timezone {{ bootstrap_timezone }}
      changed_when: ansible_date_time.tz != bootstrap_timezone

    # ── Standard directories ───────────────────────────────────────────────────

    - name: Ensure standard directories exist
      ansible.builtin.file:
        path: "{{ item }}"
        state: directory
        owner: "{{ bootstrap_user }}"
        group: "{{ bootstrap_user }}"
        mode: '0755'
      loop: "{{ bootstrap_dirs }}"

    # ── Oh My Zsh ─────────────────────────────────────────────────────────────

    - name: Ensure Oh My Zsh base repository is present
      ansible.builtin.git:
        repo: https://github.com/ohmyzsh/ohmyzsh.git
        dest: "{{ bootstrap_zsh_install_dir }}"
        depth: 1
        update: true
        force: false

    - name: Ensure custom directories under Oh My Zsh exist
      ansible.builtin.file:
        path: "{{ item }}"
        state: directory
        owner: root
        group: root
        mode: '0755'
      loop:
        - "{{ bootstrap_zsh_install_dir }}/custom"
        - "{{ bootstrap_zsh_install_dir }}/custom/themes"
        - "{{ bootstrap_zsh_install_dir }}/custom/plugins"

    - name: Deploy Pure theme
      ansible.builtin.git:
        repo: https://github.com/sindresorhus/pure.git
        dest: "{{ bootstrap_zsh_install_dir }}/custom/themes/pure"
        depth: 1
        update: true

    - name: Link Pure theme helpers
      ansible.builtin.file:
        src: "{{ bootstrap_zsh_install_dir }}/custom/themes/pure/pure.zsh"
        dest: "{{ bootstrap_zsh_install_dir }}/custom/themes/pure.zsh-theme"
        state: link

    - name: Link Pure async helper
      ansible.builtin.file:
        src: "{{ bootstrap_zsh_install_dir }}/custom/themes/pure/async.zsh"
        dest: "{{ bootstrap_zsh_install_dir }}/custom/async.zsh"
        state: link

    - name: Clone zsh-autosuggestions
      ansible.builtin.git:
        repo: https://github.com/zsh-users/zsh-autosuggestions
        dest: "{{ bootstrap_zsh_install_dir }}/custom/plugins/zsh-autosuggestions"
        depth: 1
        update: true

    - name: Clone zsh-syntax-highlighting
      ansible.builtin.git:
        repo: https://github.com/zsh-users/zsh-syntax-highlighting
        dest: "{{ bootstrap_zsh_install_dir }}/custom/plugins/zsh-syntax-highlighting"
        depth: 1
        update: true

    - name: Deploy zshrc from template
      ansible.builtin.template:
        src: ../../templates/bootstrap-ubuntu/zshrc.j2
        dest: "{{ bootstrap_user_home }}/.zshrc"
        owner: "{{ bootstrap_user }}"
        group: "{{ bootstrap_user }}"
        mode: '0644'

    # ── CUDA PATH ─────────────────────────────────────────────────────────────

    - name: Ensure CUDA paths are in .bashrc
      ansible.builtin.blockinfile:
        path: "{{ bootstrap_user_home }}/.bashrc"
        marker: "# {mark} ANSIBLE MANAGED - CUDA paths"
        owner: "{{ bootstrap_user }}"
        group: "{{ bootstrap_user }}"
        block: |
          export PATH=/usr/local/cuda/bin:$PATH
          export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

    - name: Ensure CUDA paths are in .zshrc
      ansible.builtin.blockinfile:
        path: "{{ bootstrap_user_home }}/.zshrc"
        marker: "# {mark} ANSIBLE MANAGED - CUDA paths"
        block: |
          export PATH=/usr/local/cuda/bin:$PATH
          export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

    # ── .env_container ────────────────────────────────────────────────────────

    - name: Deploy .env_container from template
      ansible.builtin.template:
        src: ../../templates/bootstrap-ubuntu/env_container.j2
        dest: "{{ bootstrap_user_home }}/.env_container"
        owner: "{{ bootstrap_user }}"
        group: "{{ bootstrap_user }}"
        mode: '0600'

    - name: Ensure .bashrc sources .env_container
      ansible.builtin.blockinfile:
        path: "{{ bootstrap_user_home }}/.bashrc"
        marker: "# {mark} ANSIBLE MANAGED - env_container"
        owner: "{{ bootstrap_user }}"
        group: "{{ bootstrap_user }}"
        block: |
          [ -f ~/.env_container ] && source ~/.env_container
```

**Step 2: Commit**
```bash
git add ansible/playbooks/jetson/bootstrap-jetson.yml
git commit -m "feat(jetson): add self-contained bootstrap playbook"
```

---

## Task 9: Add jetson_env_container_vars to group_vars

The bootstrap uses `ubuntu_env_container_vars: "{{ jetson_env_container_vars | default({}) }}"` which needs to be defined somewhere. The Jetson `.env_container` currently contains these vars (verified live). They need to be in the vault.

**Files:**
- Modify: `ansible/inventory/host_vars/jetson.lab.yml` (encrypted vault — must use `ansible-vault edit`)

**Step 1: Check what's currently in the vault**
```bash
cd ansible
ansible-vault view inventory/host_vars/jetson.lab.yml
```

**Step 2: Add jetson_env_container_vars block**

Using `ansible-vault edit inventory/host_vars/jetson.lab.yml`, add:

```yaml
jetson_env_container_vars:
  CHIFFON_EXECUTOR01_TOKEN: "<value from 1Password>"
  CHIFFON_ORCHESTRATOR_TOKEN: "<value from 1Password>"
  CODEX_CONFIG_FILE: "<value from 1Password>"
  COMFYUI_SERVER: "<value from 1Password>"
  GITEA_TOKEN: "<value from 1Password>"
  LMSTUDIO_API_KEY: "<value from 1Password>"
  LMSTUDIO_BASE_URL: "http://spraycheese.lab.klsll.com:1234/v1"
  NOTION_TOKEN: "<value from 1Password>"
  SLACK_APP_TOKEN: "<value from 1Password>"
  SLACK_BOT_TOKEN: "<value from 1Password>"
  SLACK_SIGNING_SECRET: "<value from 1Password>"
  TZ: "America/Phoenix"
  HUGGINGFACE_HUB_TOKEN: "<value from 1Password>"
  OPENCLAW_GATEWAY_TOKEN: "<value from 1Password>"
```

To get current values from the live Jetson:
```bash
ssh -i ~/.ssh/id_ed25519 192.168.20.169 "cat ~/.env_container"
# Then look them up / copy them into vault
```

> Note: `OPENCLAW_GATEWAY_TOKEN` is in `~/.openclaw/openclaw.json` under `gateway.auth.token` on the Jetson if not in `.env_container` yet.

**Step 3: Commit vault (ansible-vault auto-encrypts on save)**
```bash
git add ansible/inventory/host_vars/jetson.lab.yml
git commit -m "chore(jetson): add jetson_env_container_vars to vault"
```

---

## Task 10: Validate bootstrap-jetson.yml

**Step 1: Syntax check**
```bash
cd ansible
ansible-playbook playbooks/jetson/bootstrap-jetson.yml --syntax-check
```
Expected: no errors.

**Step 2: Dry run (config tasks only, skip Docker install)**

The Docker/NVIDIA tasks will show as changes even if already installed. That's expected. Verify the playbook at least parses and the task names look right:

```bash
ansible-playbook playbooks/jetson/bootstrap-jetson.yml \
  --list-tasks -e target_hosts=jetson.lab
```
Expected: list of ~30 tasks, all named sensibly.

**Step 3: Note for live run**

The bootstrap playbook should only be run on a fresh Jetson. For the already-running Jetson, the Docker/NVIDIA sections are idempotent (apt will skip already-installed packages, `creates:` guards the GPG steps). Running it against the live Jetson is safe but unnecessary right now — skip until a reflash.

---

## Task 11: Push and open PR

**Step 1: Push branch**
```bash
git push -u origin feature/openclaw-jetson-playbooks
```

**Step 2: Create PR via Gitea MCP**

Use `mcp__gitea__create_pull_request` with:
- `owner`: Homelab
- `repo`: homelab-infra
- `head`: feature/openclaw-jetson-playbooks
- `base`: main
- `title`: feat(jetson): repeatable OpenClaw deploy + Jetson bootstrap playbooks

Body should summarize: what was fixed in deploy-openclaw.yml, what bootstrap-jetson.yml covers, and note that vault must be populated before bootstrap can run end-to-end.

---

## Rollback

If the deploy breaks OpenClaw:
```bash
ssh -i ~/.ssh/id_ed25519 192.168.20.169
# Roll back config to most recent backup
ls -lt ~/.openclaw/openclaw.json.bak.* | head -3
cp ~/.openclaw/openclaw.json.bak.<ts> ~/.openclaw/openclaw.json

# Roll back compose to original
cd ~/docker/openclaw
git diff  # if it's tracked, or just edit manually

# Restart
docker compose restart openclaw
docker logs openclaw -f
```
