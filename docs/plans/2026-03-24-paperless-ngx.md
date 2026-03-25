# Paperless-NGX Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy paperless-ngx on Unraid as a first-class service with PostgreSQL, Redis, iCloud IMAP email ingestion, and NPM reverse proxy at `paperless.klsll.com`.

**Architecture:** Ansible role (`ansible/roles/paperless/`) deployed via playbook to Unraid using `raw` tasks (no Python). Four containers on a single bridge network — redis, postgres, web, worker — with bind mounts to the existing `/mnt/user/paperless` share. Secrets stored in Ansible vault.

**Tech Stack:** paperless-ngx (ghcr.io/paperless-ngx/paperless-ngx:latest), PostgreSQL 16, Redis 7, Ansible (raw tasks), Ansible Vault, iCloud IMAP

---

## Pre-flight Checks

Before starting, verify:

```bash
# Confirm vault password is present
ls ~/.vault-pass

# Confirm SSH access to Unraid
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 "echo ok"

# Confirm 1Password CLI works
op read "op://AI Wedge/Apple - Paperless/credential"

# Confirm working directory
cd /home/james/projects/homelab-infra
```

---

### Task 1: Create Feature Branch

**Files:** none

**Step 1: Checkout main and pull latest**

```bash
git checkout main && git pull
```

**Step 2: Create feature branch**

```bash
git checkout -b feature/paperless-ngx
```

**Step 3: Verify**

```bash
git branch --show-current
# Expected: feature/paperless-ngx
```

---

### Task 2: Add Vault Entries

**Files:**
- Modify: `ansible/group_vars/all/vault.yml`

**Step 1: Read the iCloud app password from 1Password**

```bash
op read "op://AI Wedge/Apple - Paperless/credential"
# Copy the output — you'll paste it into the vault editor
```

**Step 2: Open vault for editing**

```bash
cd ansible
ansible-vault edit group_vars/all/vault.yml
```

**Step 3: Add these 6 entries at the bottom of the file**

```yaml
# Paperless-NGX
vault_paperless_secret_key: "CHANGEME_generate_with_openssl_rand_base64_50"
vault_paperless_db_password: "CHANGEME_generate_with_openssl_rand_base64_24"
vault_paperless_admin_password: "CHANGEME_strong_password_here"
vault_paperless_email_host: "imap.mail.me.com"
vault_paperless_email_user: "james@klsll.com"
vault_paperless_email_password: "PASTE_APP_PASSWORD_FROM_1PASSWORD_HERE"
```

**Step 4: Generate real values for the placeholders**

```bash
# Secret key (50 chars)
openssl rand -base64 50 | tr -dc 'a-zA-Z0-9' | head -c 50

# DB password (32 chars)
openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32

# Admin password — choose a strong password manually
```

Replace all `CHANGEME_*` values in the vault with the generated strings.

**Step 5: Verify vault is readable**

```bash
ansible-vault view group_vars/all/vault.yml | grep paperless
# Expected: 6 lines with vault_paperless_* keys (values visible in plaintext)
```

---

### Task 3: Create Role Skeleton

**Files:**
- Create: `ansible/roles/paperless/defaults/main.yml`
- Create: `ansible/roles/paperless/tasks/main.yml`
- Create: `ansible/roles/paperless/templates/docker-compose.yml.j2`
- Create: `ansible/roles/paperless/templates/paperless.env.j2`

**Step 1: Create directories**

```bash
mkdir -p ansible/roles/paperless/{defaults,tasks,templates}
```

**Step 2: Verify structure**

```bash
find ansible/roles/paperless -type d
# Expected:
# ansible/roles/paperless
# ansible/roles/paperless/defaults
# ansible/roles/paperless/tasks
# ansible/roles/paperless/templates
```

**Step 3: Commit skeleton**

```bash
git add ansible/roles/paperless/
git commit -m "feat(paperless): scaffold ansible role skeleton"
```

---

### Task 4: Write Role Defaults

**Files:**
- Create: `ansible/roles/paperless/defaults/main.yml`

**Step 1: Write the file**

```yaml
---
# Paperless-NGX role defaults

# Paths
paperless_appdata_dir: /mnt/user/paperless
paperless_compose_dir: /opt/docker/paperless

# Container config
paperless_port: 8000
paperless_web_container: paperless-web
paperless_worker_container: paperless-worker
paperless_redis_container: paperless-redis
paperless_db_container: paperless-db
paperless_network: paperless-net

# Application config
paperless_admin_user: admin
paperless_time_zone: America/Phoenix
paperless_ocr_language: eng
paperless_url: https://paperless.klsll.com

# Email ingestion (IMAP)
paperless_email_port: 993
paperless_email_security: SSL
paperless_email_from_email: james@klsll.com

# Database
paperless_db_name: paperless
paperless_db_user: paperless

# Unraid labels
paperless_icon: https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/paperless-ngx.png
```

**Step 2: Commit**

```bash
git add ansible/roles/paperless/defaults/main.yml
git commit -m "feat(paperless): add role defaults"
```

---

### Task 5: Write Docker Compose Template

**Files:**
- Create: `ansible/roles/paperless/templates/docker-compose.yml.j2`

**Step 1: Write the template**

```yaml
services:
  {{ paperless_redis_container }}:
    image: redis:7-alpine
    container_name: {{ paperless_redis_container }}
    restart: unless-stopped
    networks:
      - {{ paperless_network }}
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  {{ paperless_db_container }}:
    image: postgres:16-alpine
    container_name: {{ paperless_db_container }}
    restart: unless-stopped
    environment:
      POSTGRES_DB: {{ paperless_db_name }}
      POSTGRES_USER: {{ paperless_db_user }}
      POSTGRES_PASSWORD: "{{ vault_paperless_db_password }}"
      TZ: {{ paperless_time_zone }}
    volumes:
      - {{ paperless_appdata_dir }}/data/pgdata:/var/lib/postgresql/data
    networks:
      - {{ paperless_network }}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U {{ paperless_db_user }}"]
      interval: 10s
      timeout: 5s
      retries: 5

  {{ paperless_web_container }}:
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    container_name: {{ paperless_web_container }}
    restart: unless-stopped
    depends_on:
      {{ paperless_db_container }}:
        condition: service_healthy
      {{ paperless_redis_container }}:
        condition: service_healthy
    ports:
      - "{{ paperless_port }}:8000"
    env_file:
      - {{ paperless_compose_dir }}/paperless.env
    volumes:
      - {{ paperless_appdata_dir }}/data:/usr/src/paperless/data
      - {{ paperless_appdata_dir }}/media:/usr/src/paperless/media
      - {{ paperless_appdata_dir }}/consume:/usr/src/paperless/consume
      - {{ paperless_appdata_dir }}/export:/usr/src/paperless/export
    networks:
      - {{ paperless_network }}
    labels:
      net.unraid.docker.icon: "{{ paperless_icon }}"
      net.unraid.docker.webui: "{{ paperless_url }}"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  {{ paperless_worker_container }}:
    image: ghcr.io/paperless-ngx/paperless-ngx:latest
    container_name: {{ paperless_worker_container }}
    restart: unless-stopped
    depends_on:
      {{ paperless_db_container }}:
        condition: service_healthy
      {{ paperless_redis_container }}:
        condition: service_healthy
    command: celery --app paperless worker --loglevel INFO
    env_file:
      - {{ paperless_compose_dir }}/paperless.env
    volumes:
      - {{ paperless_appdata_dir }}/data:/usr/src/paperless/data
      - {{ paperless_appdata_dir }}/media:/usr/src/paperless/media
      - {{ paperless_appdata_dir }}/consume:/usr/src/paperless/consume
      - {{ paperless_appdata_dir }}/export:/usr/src/paperless/export
    networks:
      - {{ paperless_network }}

networks:
  {{ paperless_network }}:
    driver: bridge
    name: {{ paperless_network }}
```

**Step 2: Commit**

```bash
git add ansible/roles/paperless/templates/docker-compose.yml.j2
git commit -m "feat(paperless): add compose template"
```

---

### Task 6: Write Environment Template

**Files:**
- Create: `ansible/roles/paperless/templates/paperless.env.j2`

**Step 1: Write the template**

```ini
# Django
PAPERLESS_SECRET_KEY={{ vault_paperless_secret_key }}
PAPERLESS_URL={{ paperless_url }}
PAPERLESS_TIME_ZONE={{ paperless_time_zone }}
PAPERLESS_OCR_LANGUAGE={{ paperless_ocr_language }}

# Database
PAPERLESS_DBHOST={{ paperless_db_container }}
PAPERLESS_DBNAME={{ paperless_db_name }}
PAPERLESS_DBUSER={{ paperless_db_user }}
PAPERLESS_DBPASS={{ vault_paperless_db_password }}

# Redis broker
PAPERLESS_REDIS=redis://{{ paperless_redis_container }}:6379

# Admin account (first-run bootstrap only)
PAPERLESS_ADMIN_USER={{ paperless_admin_user }}
PAPERLESS_ADMIN_PASSWORD={{ vault_paperless_admin_password }}

# Email ingestion (IMAP)
PAPERLESS_EMAIL_TASK_CRON=*/10 * * * *
PAPERLESS_APPS=paperless_mail

# Misc
USERMAP_UID=1000
USERMAP_GID=1000
```

> **Note:** IMAP mail account credentials are configured post-deploy via the web UI (Admin → Mail Accounts). The `paperless_mail` app enables the mail ingestion pipeline; the actual IMAP connection is stored in the database.

**Step 2: Commit**

```bash
git add ansible/roles/paperless/templates/paperless.env.j2
git commit -m "feat(paperless): add env template"
```

---

### Task 7: Write Role Tasks

**Files:**
- Create: `ansible/roles/paperless/tasks/main.yml`

**Step 1: Write the tasks**

```yaml
---
# Deploy Paperless-NGX — all tasks use raw since Unraid lacks Python

- name: Create appdata directories
  ansible.builtin.raw: |
    mkdir -p {{ paperless_appdata_dir }}/data/pgdata
    mkdir -p {{ paperless_appdata_dir }}/media
    mkdir -p {{ paperless_appdata_dir }}/consume
    mkdir -p {{ paperless_appdata_dir }}/export
    mkdir -p {{ paperless_compose_dir }}
  changed_when: false

- name: Generate docker-compose.yml content
  ansible.builtin.set_fact:
    _paperless_compose_content: "{{ lookup('template', role_path + '/templates/docker-compose.yml.j2') }}"

- name: Write docker-compose.yml
  ansible.builtin.raw: |
    cat > {{ paperless_compose_dir }}/docker-compose.yml << 'EOFCOMPOSE'
    {{ _paperless_compose_content }}
    EOFCOMPOSE
  changed_when: true

- name: Generate paperless.env content
  ansible.builtin.set_fact:
    _paperless_env_content: "{{ lookup('template', role_path + '/templates/paperless.env.j2') }}"

- name: Write paperless.env (no_log to protect secrets)
  ansible.builtin.raw: |
    cat > {{ paperless_compose_dir }}/paperless.env << 'EOFENV'
    {{ _paperless_env_content }}
    EOFENV
    chmod 600 {{ paperless_compose_dir }}/paperless.env
  changed_when: true
  no_log: true

- name: Pull latest paperless-ngx images
  ansible.builtin.raw: |
    cd {{ paperless_compose_dir }} && docker compose pull
  changed_when: true

- name: Deploy compose stack
  ansible.builtin.raw: |
    cd {{ paperless_compose_dir }} && docker compose down && docker compose up -d
  changed_when: true

- name: Wait for Paperless-NGX web to be healthy (up to 90s)
  ansible.builtin.raw: |
    for i in $(seq 1 18); do
      if curl -sf http://localhost:{{ paperless_port }}/ > /dev/null 2>&1; then
        echo "healthy"; exit 0
      fi
      sleep 5
    done
    echo "timeout waiting for paperless" >&2; exit 1
  changed_when: false

- name: Display container status
  ansible.builtin.raw: |
    docker ps --filter name=paperless --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>&1
  register: paperless_ps
  changed_when: false

- name: Show container status
  ansible.builtin.debug:
    msg: "{{ paperless_ps.stdout_lines | default([]) }}"
```

**Step 2: Commit**

```bash
git add ansible/roles/paperless/tasks/main.yml
git commit -m "feat(paperless): add role tasks"
```

---

### Task 8: Write Playbook

**Files:**
- Create: `ansible/playbooks/misc/deploy-paperless.yml`

**Step 1: Write the playbook**

```yaml
---
# Deploy Paperless-NGX document management on Unraid
#
# Prerequisites:
#   - vault.yml contains vault_paperless_* entries (see Task 2)
#   - /mnt/user/paperless share exists on Unraid
#
# After deployment:
#   Web UI:    http://192.168.20.14:8000    (direct)
#              https://paperless.klsll.com  (via NPM)
#   Login:     admin / vault_paperless_admin_password
#   Consume:   Drop files into /mnt/user/paperless/consume/
#   Email:     Configure IMAP in Admin → Mail Accounts (see Task 10)

- name: Deploy Paperless-NGX
  hosts: unraid
  gather_facts: false

  vars:
    vault_paperless_secret_key: "{{ vault_paperless_secret_key }}"
    vault_paperless_db_password: "{{ vault_paperless_db_password }}"
    vault_paperless_admin_password: "{{ vault_paperless_admin_password }}"

  roles:
    - role: paperless

  post_tasks:
    - name: Deployment summary
      ansible.builtin.debug:
        msg: |
          Paperless-NGX deployed successfully!
          Web UI:     http://{{ ansible_host }}:{{ paperless_port }}
          NPM proxy:  https://paperless.klsll.com (configure NPM separately)
          Login:      {{ paperless_admin_user }} / <vault_paperless_admin_password>
          Consume:    {{ paperless_appdata_dir }}/consume/
          Logs:       docker logs paperless-web -f
          Restart:    cd {{ paperless_compose_dir }} && docker compose restart
```

**Step 2: Commit**

```bash
git add ansible/playbooks/misc/deploy-paperless.yml
git commit -m "feat(paperless): add deploy playbook"
```

---

### Task 9: Write NPM Service Config

**Files:**
- Create: `ansible/files/npm/services/paperless.yml`

**Step 1: Write the file**

```yaml
---
proxy_hosts:
  - name: paperless
    domains:
      - paperless.klsll.com
    forward_host: 192.168.20.14
    forward_port: 8000
    scheme: http
    websocket: true
    certificate: klsll-wildcard
    ssl_forced: true
    hsts: true
    http2: true

dns_records:
  - name: paperless.klsll.com
    type: A
    value: 192.168.20.50
    ttl: 3600
```

**Step 2: Commit**

```bash
git add ansible/files/npm/services/paperless.yml
git commit -m "feat(paperless): add NPM proxy config"
```

---

### Task 10: Syntax Check

**Step 1: Run syntax check from ansible/ directory**

```bash
cd ansible
ansible-playbook playbooks/misc/deploy-paperless.yml --syntax-check
# Expected: playbook: playbooks/misc/deploy-paperless.yml (no errors)
```

**Step 2: Fix any errors before continuing**

Common issues:
- Indentation in YAML templates (use spaces, not tabs)
- Missing quotes around Jinja2 variables in docker-compose.yml.j2 that contain special chars

---

### Task 11: Dry Run

**Step 1: Run check mode**

```bash
ansible-playbook playbooks/misc/deploy-paperless.yml \
  --check --diff \
  --limit unraid-server \
  --vault-password-file ~/.vault-pass \
  -v
```

**Expected output:**
- All tasks show as `ok` or `changed` (would change)
- No `fatal` errors
- `--check` skips actual docker commands (raw tasks always show changed in check mode — this is expected)

---

### Task 12: Deploy

**Step 1: Apply the playbook**

```bash
ansible-playbook playbooks/misc/deploy-paperless.yml \
  --diff \
  --limit unraid-server \
  --vault-password-file ~/.vault-pass \
  -v
```

**Step 2: Verify containers are running**

```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 \
  "docker ps --filter name=paperless --format 'table {{.Names}}\t{{.Status}}'"
# Expected: 4 containers (redis, db, web, worker) all "Up"
```

**Step 3: Verify web is reachable**

```bash
curl -sf http://192.168.20.14:8000/ -o /dev/null -w "%{http_code}\n"
# Expected: 200
```

**Step 4: Verify idempotence**

```bash
ansible-playbook playbooks/misc/deploy-paperless.yml \
  --check --diff \
  --limit unraid-server \
  --vault-password-file ~/.vault-pass
# Expected: All raw tasks show changed (expected for raw), no fatal errors
```

---

### Task 13: Configure NPM Proxy

**Step 1: Log into NPM admin UI**

Navigate to `http://npm.klsll.com` (or NPM admin URL) and log in.

**Step 2: Add proxy host**

Use the values from `ansible/files/npm/services/paperless.yml`:
- Domain: `paperless.klsll.com`
- Scheme: `http`
- Forward host: `192.168.20.14`
- Forward port: `8000`
- Enable: WebSockets, SSL (klsll-wildcard cert), Force SSL, HSTS, HTTP/2

**Step 3: Add DNS record in Technitium**

Navigate to Technitium DNS admin and add:
- Name: `paperless.klsll.com`
- Type: `A`
- Value: `192.168.20.50`
- TTL: `3600`

**Step 4: Verify HTTPS access**

```bash
curl -sf https://paperless.klsll.com/ -o /dev/null -w "%{http_code}\n"
# Expected: 200
```

---

### Task 14: Configure Email Ingestion

**Step 1: Log into Paperless-NGX**

Go to `https://paperless.klsll.com`, log in as `admin`.

**Step 2: Add mail account**

Navigate to Admin → Mail Accounts → Add:
- Name: `iCloud - james@klsll.com`
- IMAP server: `imap.mail.me.com`
- IMAP port: `993`
- Username: `james@klsll.com`
- Password: app password from 1Password (`Apple - Paperless`)
- Security: SSL
- Default owner: admin

**Step 3: Add mail rule**

Navigate to Admin → Mail Rules → Add:
- Account: `iCloud - james@klsll.com`
- Folder: `INBOX`
- Filter from: (leave blank to process all)
- Action: Mark as read + Move to folder `[paperless]` (create the folder in Mail.app first)
- Consumption scope: Attachments only

**Step 4: Test ingestion**

Send a test email with a PDF attachment to `james@klsll.com`, then check:

```bash
# Watch worker logs for ingestion activity
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 \
  "docker logs paperless-worker -f --tail 50"
```

Wait up to 10 minutes (polls every 10 minutes per cron). Document appears in Paperless inbox.

---

### Task 15: Final Commit and PR

**Step 1: Verify all files are committed**

```bash
cd /home/james/projects/homelab-infra
git status
# Expected: nothing to commit, working tree clean
```

**Step 2: Push branch**

```bash
git push -u origin feature/paperless-ngx
```

**Step 3: Create PR via Gitea MCP**

Use `mcp__gitea__create_pull_request` with:
- Title: `feat: deploy paperless-ngx document management`
- Base: `main`
- Body: Summary of what was deployed, NPM config instructions, mail setup notes

---

## Summary

| What | Value |
|------|-------|
| Web UI | `https://paperless.klsll.com` |
| Direct | `http://192.168.20.14:8000` |
| Consume folder | `/mnt/user/paperless/consume/` |
| Logs | `docker logs paperless-web -f` |
| Rollback | `cd /opt/docker/paperless && docker compose down` |
| Data safe on rollback? | Yes — all data in `/mnt/user/paperless/` |
