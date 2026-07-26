# Mem0 Memory for Hermes Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a self-hosted Mem0 server on Unraid, backed by goudai's llama-swap for LLM/embedding, and wire both jetson Hermes agents (Lyra, Raclette) to use it as their `memory.provider`.

**Architecture:** New Ansible role `mem0-server` deploys a 3-container Docker Compose stack (FastAPI API, Postgres+pgvector, Next.js dashboard) built from a pinned `mem0ai/mem0` commit, on Unraid, LAN-only. A new embedding model joins goudai's `llama-swap`. Lyra's and Raclette's `hermes.yaml` gain `memory.provider: mem0` plus a per-agent `mem0.json` pointing at the shared server with distinct `agent_id`/`user_id`.

**Tech Stack:** Ansible (raw commands — Unraid has no Python), Docker Compose, `pgvector/pgvector:pg17`, FastAPI (mem0 server), llama.cpp/llama-swap, 1Password (`op run`/`op://`).

This plan is a direct continuation of
`docs/superpowers/specs/2026-07-25-mem0-hermes-memory-design.md` — read that
first for the "why." Two details were refined during planning (verified
directly against the `mem0ai/mem0` source, commit `b357a5a1b03c299e`):

1. **No manual dashboard bootstrap needed for the LLM/embedder backend.**
   Mem0's OpenAI provider (used for both the LLM and the embedder) reads
   `OPENAI_BASE_URL` from the environment as a fallback
   (`mem0/llms/openai.py:51`, `mem0/embeddings/openai.py:22-25`). Setting it
   on the `mem0-api` container is sufficient to route both to llama-swap —
   the spec's "open risk" about a dashboard override is resolved.
2. **`ADMIN_API_KEY` is legacy/optional** — the real admin auth is an
   email+password account created via `/auth/register`, used once to mint
   per-agent API keys via `/api-keys`. Dropped from the secrets list.

## Global Constraints

- Unraid hosts have no Python — all Unraid-side Ansible tasks use
  `ansible.builtin.raw`, matching `ansible/roles/icloud-mcp`.
- Never hardcode secrets in git. New secrets go through 1Password
  (`op://AI Wedge/...`) referenced from `ansible/envs/mem0-server.env`, run
  via `ansible/scripts/run-playbook.sh mem0-server ...` — see
  `docs/secrets-management.md`.
- Lyra's and Raclette's own per-agent secrets (dashboard auth, API server
  keys, and now their Mem0 API keys) are **not** 1Password-managed — they
  go through `~/.env_container` on the controller, matching the existing
  `LYRA_API_SERVER_KEY` / `RACLETTE_API_SERVER_KEY` pattern (see
  `ansible/group_vars/edge_devices/jetson.lab.yml`).
- Docker network subnets on Unraid are pinned manually (auto-allocation
  pool is exhausted, issue #79). Next free `172.16.x` slot is `.14` (`.10`
  hister, `.11` crawl4ai, `.12` research-mcp, `.13` icloud-mcp).
- Free host ports on Unraid confirmed against `docs/network-ports.md`:
  `8888` (mem0 API) and `8889` (mem0 dashboard) are both unused.
- Set service timezone to `America/Phoenix` (matches every other Unraid
  role's `timezone` default).
- New Unraid services get a `netbox-service` role registration in their
  playbook, matching `icloud-mcp`/`raclette`.
- LAN-only: no NPM proxy entries for the mem0 API or dashboard.
- Standard verification workflow for every Ansible change in this repo:
  `--syntax-check` → `--check --diff` → apply → verify (curl/docker ps).

---

## File Structure

```
ansible/roles/mem0-server/
  defaults/main.yml          # ports, subnet, image tags, llama-swap URL, secrets lookups
  tasks/main.yml              # fetch pinned source, build images, render compose, deploy, verify
  templates/docker-compose.yml.j2

ansible/playbooks/ai/
  deploy-mem0-server.yml      # hosts: unraid

ansible/envs/
  mem0-server.env             # op:// references for JWT_SECRET, POSTGRES_PASSWORD, admin password

ansible/roles/llama-swap/defaults/main.yml   # + nomic-embed-text model, + mem0-embedder group

ansible/files/jetson/hermes-lyra/config/
  hermes.yaml.j2               # memory.memory_enabled/provider edit
  mem0.json.j2                 # new

ansible/files/jetson/raclette/config/
  hermes.yaml.j2               # memory.provider edit (memory_enabled already true)
  mem0.json.j2                 # new

ansible/roles/jetson-hermes-lyra/tasks/main.yml   # + MEM0_API_KEY guard, + mem0.json render (both profile paths)
ansible/roles/jetson-raclette/tasks/main.yml      # + MEM0_API_KEY guard, + mem0.json render

ansible/group_vars/edge_devices/jetson.lab.yml    # + MEM0_API_KEY in lyra_env and raclette_env
```

---

### Task 1: Add an embedding model to goudai's llama-swap

**Files:**
- Modify: `ansible/roles/llama-swap/defaults/main.yml`

**Interfaces:**
- Produces: an OpenAI-compatible embeddings endpoint at
  `http://192.168.20.150:8010/v1/embeddings`, model alias
  `nomic-embed-text`, consumed by Task 3's `mem0_default_embedder_model`.

- [ ] **Step 1: Add the model entry**

Add this entry to the `llama_swap_models` dict in
`ansible/roles/llama-swap/defaults/main.yml`, alongside the existing
`"glm/glm-4.5-air-q4"` entry (same indentation level):

```yaml
  # ── Embedding model — backs the mem0 memory server's fact extraction
  # and semantic search (both LLM chat calls and embeddings route through
  # llama-swap; this is the embeddings half). Small (~280MB Q8_0), kept in
  # its own group below so it doesn't perturb the agent-stack's VRAM budget.
  "nomic-embed-text":
    hf: "nomic-ai/nomic-embed-text-v1.5-GGUF:Q8_0"
    alias: "nomic-embed-text"
    flags:
      - "--embedding"
      - "--pooling mean"
      - "--ctx-size 8192"
      - "-ngl 99"
      - "--threads 32"
    ttl: 3600
```

- [ ] **Step 2: Add its own persistent group**

Add a second entry to `llama_swap_groups` (below the existing
`"agent-stack"` entry, same dict):

```yaml
  "mem0-embedder":
    persistent: true
    swap: false
    exclusive: false
    members:
      - "nomic-embed-text"
```

- [ ] **Step 3: Syntax-check and dry-run**

Run: `cd ansible && ansible-playbook playbooks/ai/deploy-llama-swap.yml --syntax-check`
Expected: `playbook: playbooks/ai/deploy-llama-swap.yml` (no errors)

Run: `cd ansible && ansible-playbook playbooks/ai/deploy-llama-swap.yml --check --diff --limit goudai`
Expected: diff shows the new model + group added to `config.yaml`, `changed=1` (the config template), no errors.

- [ ] **Step 4: Apply**

Run: `cd ansible && ansible-playbook playbooks/ai/deploy-llama-swap.yml --diff --limit goudai -v`
Expected: `changed=1` (config render), llama-swap restart handler fires, final "Verify llama-swap responds" task passes with status 200.

- [ ] **Step 5: Verify the embeddings endpoint directly**

Run:
```bash
curl -s http://192.168.20.150:8010/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model": "nomic-embed-text", "input": "hello world"}' | head -c 300
```
Expected: JSON with a top-level `"data"` array containing an `"embedding"` field (a long float array) — not an error/model-not-found response. If it 404s, check `curl http://192.168.20.150:8010/v1/models` lists `nomic-embed-text`; if it lists but fails to load, check `journalctl -u llama-swap -n 50` on goudai for a download/GGUF-loading error and re-verify the HF repo/quant name.

- [ ] **Step 6: Commit**

```bash
git add ansible/roles/llama-swap/defaults/main.yml
git commit -m "feat(goudai): add nomic-embed-text embedding model to llama-swap for mem0"
```

---

### Task 2: Provision mem0-server secrets in 1Password

**Files:**
- Create: `ansible/envs/mem0-server.env`

**Interfaces:**
- Produces: `MEM0_JWT_SECRET`, `MEM0_POSTGRES_PASSWORD` environment
  variables (via `op run`), consumed by Task 3's
  `ansible/roles/mem0-server/defaults/main.yml` lookups. Also creates an
  admin account password for the mem0 dashboard, consumed by Task 4.

- [ ] **Step 1: Generate the secrets**

```bash
JWT_SECRET=$(openssl rand -base64 48)
POSTGRES_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9')
ADMIN_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9')
echo "jwt_secret=$JWT_SECRET"
echo "postgres_password=$POSTGRES_PASSWORD"
echo "admin_password=$ADMIN_PASSWORD"
```

- [ ] **Step 2: Store them in the "AI Wedge" 1Password vault**

The `OP_SERVICE_ACCOUNT_TOKEN` used by `run-playbook.sh` is read-only
(`docs/secrets-management.md`), so this step needs an interactive,
full-access `op` session (`op signin`) or the 1Password app/web UI — not
the automation token. Create one new item:

```bash
op item create --category="API Credential" --title="mem0-server" --vault="AI Wedge" \
  "jwt_secret[password]=$JWT_SECRET" \
  "postgres_password[password]=$POSTGRES_PASSWORD" \
  "admin_email[text]=james@klsll.com" \
  "admin_password[password]=$ADMIN_PASSWORD"
```

If `op item create` isn't available in your session, create the item
manually in the 1Password app instead, with the same title/vault/field
names — the exact field names matter, `ansible/envs/mem0-server.env`
(next step) references them by name.

- [ ] **Step 3: Create the env file**

Create `ansible/envs/mem0-server.env`:

```bash
MEM0_JWT_SECRET=op://AI Wedge/mem0-server/jwt_secret
MEM0_POSTGRES_PASSWORD=op://AI Wedge/mem0-server/postgres_password
```

- [ ] **Step 4: Verify resolution**

Run: `op run --env-file=ansible/envs/mem0-server.env -- env | grep MEM0_`
Expected: both `MEM0_JWT_SECRET=...` and `MEM0_POSTGRES_PASSWORD=...` print
with real (non-`op://`) values.

- [ ] **Step 5: Commit**

```bash
git add ansible/envs/mem0-server.env
git commit -m "feat(mem0-server): add 1Password env file for JWT/Postgres secrets"
```

---

### Task 3: Build and deploy the mem0-server Ansible role

**Files:**
- Create: `ansible/roles/mem0-server/defaults/main.yml`
- Create: `ansible/roles/mem0-server/tasks/main.yml`
- Create: `ansible/roles/mem0-server/templates/docker-compose.yml.j2`
- Create: `ansible/playbooks/ai/deploy-mem0-server.yml`

**Interfaces:**
- Consumes: `MEM0_JWT_SECRET`, `MEM0_POSTGRES_PASSWORD` env vars (Task 2).
  `http://192.168.20.150:8010/v1` + `nomic-embed-text` model alias (Task 1).
- Produces: mem0 API reachable at `http://192.168.20.14:8888`
  (`/auth/*`, `/api-keys`, `/memories`, `/search`), dashboard at
  `http://192.168.20.14:8889`. Consumed by Task 4 (admin bootstrap) and
  Tasks 5/6 (`mem0.json` `host` field).

- [ ] **Step 1: Write `defaults/main.yml`**

Create `ansible/roles/mem0-server/defaults/main.yml`:

```yaml
---
# mem0-server: self-hosted Mem0 (mem0ai/mem0, server/ subtree), built from
# a pinned commit — no published Docker image exists upstream, matching
# icloud-mcp's build-from-pinned-source pattern. Bump mem0_source_commit
# deliberately — re-check server/requirements.txt and server/main.py's
# BUNDLED_*_PROVIDERS before doing so.

mem0_source_commit: "b357a5a1b03c299ec8229c268e63cfac0f7c6566"
mem0_api_image: "local/mem0-api:{{ mem0_source_commit[:12] }}"
mem0_dashboard_image: "local/mem0-dashboard:{{ mem0_source_commit[:12] }}"

mem0_api_container_name: mem0-api
mem0_dashboard_container_name: mem0-dashboard
mem0_postgres_container_name: mem0-postgres

mem0_api_port: 8888
mem0_dashboard_port: 8889

mem0_appdata_dir: /mnt/user/appdata/mem0-server
mem0_build_dir: /tmp/mem0-server-build
mem0_env_file: "{{ mem0_appdata_dir }}/mem0-server.env"

# Pinned subnet: Docker's auto-allocation pools are exhausted on Unraid
# (issue #79). .10=hister .11=crawl4ai .12=research-mcp .13=icloud-mcp
# .14=mem0-server
mem0_net_subnet: "172.16.14.0/24"

# LLM + embedder both route through goudai's llama-swap (OpenAI-compatible).
# mem0's OpenAI provider reads OPENAI_BASE_URL as a fallback base URL for
# both chat and embeddings (mem0/llms/openai.py, mem0/embeddings/openai.py)
# — no per-provider config needed beyond these env vars.
mem0_llm_base_url: "http://192.168.20.150:8010/v1"
mem0_llm_api_key: "local-no-auth-required"
mem0_default_llm_model: "qwen/qwen3.6-35b-uncensored"
mem0_default_embedder_model: "nomic-embed-text"

mem0_jwt_secret: "{{ lookup('ansible.builtin.env', 'MEM0_JWT_SECRET') }}"
mem0_postgres_password: "{{ lookup('ansible.builtin.env', 'MEM0_POSTGRES_PASSWORD') }}"

timezone: "America/Phoenix"
```

- [ ] **Step 2: Write `templates/docker-compose.yml.j2`**

Create `ansible/roles/mem0-server/templates/docker-compose.yml.j2`:

```yaml
services:
  {{ mem0_postgres_container_name }}:
    image: pgvector/pgvector:pg17
    container_name: {{ mem0_postgres_container_name }}
    restart: unless-stopped
    shm_size: "128mb"
    env_file:
      - {{ mem0_env_file }}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -q -d postgres -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    volumes:
      - mem0_postgres_data:/var/lib/postgresql/data
      - {{ mem0_appdata_dir }}/init-db.sh:/docker-entrypoint-initdb.d/init-db.sh
    networks:
      - mem0-net

  {{ mem0_api_container_name }}:
    image: "{{ mem0_api_image }}"
    container_name: {{ mem0_api_container_name }}
    restart: unless-stopped
    command: sh -c "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"
    env_file:
      - {{ mem0_env_file }}
    ports:
      - "{{ mem0_api_port }}:8000"
    depends_on:
      {{ mem0_postgres_container_name }}:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 512m
          cpus: "1.0"
    networks:
      - mem0-net

  {{ mem0_dashboard_container_name }}:
    image: "{{ mem0_dashboard_image }}"
    container_name: {{ mem0_dashboard_container_name }}
    restart: unless-stopped
    environment:
      NEXT_PUBLIC_API_URL: "http://{{ ansible_host }}:{{ mem0_api_port }}"
      API_INTERNAL_URL: "http://{{ mem0_api_container_name }}:8000"
      NEXT_PUBLIC_INSTANCE_NAME: "Mem0 (homelab)"
    ports:
      - "{{ mem0_dashboard_port }}:3000"
    depends_on:
      - {{ mem0_api_container_name }}
    deploy:
      resources:
        limits:
          memory: 256m
          cpus: "0.5"
    networks:
      - mem0-net

volumes:
  mem0_postgres_data:

networks:
  mem0-net:
    driver: bridge
    ipam:
      config:
        - subnet: {{ mem0_net_subnet }}
```

- [ ] **Step 3: Write `tasks/main.yml`**

Create `ansible/roles/mem0-server/tasks/main.yml`:

```yaml
---
# mem0-server: FastAPI + pgvector + dashboard, built from a pinned
# mem0ai/mem0 commit (server/ subtree). Uses raw commands throughout —
# Unraid has no Python.

- name: Assert mem0-server secrets are provided
  ansible.builtin.assert:
    that:
      - mem0_jwt_secret | length > 0
      - mem0_postgres_password | length > 0
    fail_msg: >-
      Set MEM0_JWT_SECRET/MEM0_POSTGRES_PASSWORD (from 1Password "mem0-server"
      item) via ansible/envs/mem0-server.env.

- name: Create appdata directory
  ansible.builtin.raw: mkdir -p {{ mem0_appdata_dir }}
  changed_when: false

- name: Write mem0-server .env file
  ansible.builtin.raw: |
    cat > {{ mem0_env_file }} << 'EOFENV'
    OPENAI_API_KEY={{ mem0_llm_api_key }}
    OPENAI_BASE_URL={{ mem0_llm_base_url }}
    MEM0_DEFAULT_LLM_MODEL={{ mem0_default_llm_model }}
    MEM0_DEFAULT_EMBEDDER_MODEL={{ mem0_default_embedder_model }}
    POSTGRES_HOST=postgres
    POSTGRES_PORT=5432
    POSTGRES_DB=postgres
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD={{ mem0_postgres_password }}
    POSTGRES_COLLECTION_NAME=memories
    JWT_SECRET={{ mem0_jwt_secret }}
    AUTH_DISABLED=false
    DASHBOARD_URL=http://{{ ansible_host }}:{{ mem0_dashboard_port }}
    APP_DB_NAME=mem0_app
    MEM0_TELEMETRY=false
    EOFENV
    chmod 600 {{ mem0_env_file }}
  changed_when: true
  no_log: true

- name: Create build directory
  ansible.builtin.raw: |
    rm -rf {{ mem0_build_dir }} && mkdir -p {{ mem0_build_dir }}
  changed_when: false

- name: Fetch pinned mem0 source
  ansible.builtin.raw: |
    curl -fsSL https://codeload.github.com/mem0ai/mem0/tar.gz/{{ mem0_source_commit }} \
      | tar xz -C {{ mem0_build_dir }} --strip-components=1
  changed_when: false

- name: Build mem0 API image
  ansible.builtin.raw: |
    cd {{ mem0_build_dir }}/server && docker build -t {{ mem0_api_image }} .
  register: mem0_api_build
  changed_when: mem0_api_build.rc == 0

- name: Build mem0 dashboard image
  ansible.builtin.raw: |
    cd {{ mem0_build_dir }}/server/dashboard && docker build -t {{ mem0_dashboard_image }} .
  register: mem0_dashboard_build
  changed_when: mem0_dashboard_build.rc == 0

- name: Copy Postgres init script into appdata directory
  ansible.builtin.raw: cp {{ mem0_build_dir }}/server/init-db.sh {{ mem0_appdata_dir }}/init-db.sh
  changed_when: false

- name: Copy docker-compose.yml
  ansible.builtin.template:
    src: docker-compose.yml.j2
    dest: "{{ mem0_appdata_dir }}/docker-compose.yml"

- name: Deploy compose stack
  ansible.builtin.raw: |
    cd {{ mem0_appdata_dir }} && docker compose up -d --remove-orphans
  changed_when: true

- name: Wait for mem0 API
  ansible.builtin.raw: |
    for i in $(seq 1 24); do
      code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:{{ mem0_api_port }}/docs)
      if [ "$code" = "200" ]; then echo healthy; exit 0; fi
      sleep 5
    done
    echo "timeout waiting for mem0 API" >&2; exit 1
  changed_when: false

- name: Wait for mem0 dashboard
  ansible.builtin.raw: |
    for i in $(seq 1 24); do
      code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:{{ mem0_dashboard_port }}/api/health)
      if [ "$code" = "200" ]; then echo healthy; exit 0; fi
      sleep 5
    done
    echo "timeout waiting for mem0 dashboard" >&2; exit 1
  changed_when: false

- name: Show mem0 API logs
  ansible.builtin.raw: docker logs --tail 30 {{ mem0_api_container_name }} 2>&1
  register: mem0_api_logs
  changed_when: false
  when: not ansible_check_mode

- name: Display mem0 API logs
  ansible.builtin.debug:
    msg: "{{ mem0_api_logs.stdout_lines }}"
  when: not ansible_check_mode
```

- [ ] **Step 4: Write the playbook**

Create `ansible/playbooks/ai/deploy-mem0-server.yml`:

```yaml
---
# Deploy the self-hosted Mem0 memory server on Unraid — shared memory
# backend for the jetson Hermes agents (Lyra, Raclette). LAN-only, no NPM
# proxy — matches icloud-mcp/comfyui-mcp.
#
# Usage:
#   ansible/scripts/run-playbook.sh mem0-server playbooks/ai/deploy-mem0-server.yml \
#     --limit unraid

- name: Deploy mem0-server on Unraid
  hosts: unraid
  gather_facts: false

  roles:
    - role: mem0-server
    - role: netbox-service
      vars:
        netbox_services:
          - name: mem0-server
            cluster: unraid-docker
            role: Memory Server
            comments: "Self-hosted Mem0 (FastAPI+pgvector) for Hermes agents (LAN-only) — API http://{{ ansible_host }}:{{ mem0_api_port }}, dashboard http://{{ ansible_host }}:{{ mem0_dashboard_port }}"

  post_tasks:
    - name: Display deployment info
      ansible.builtin.debug:
        msg: |
          mem0-server deployed.
          API:       http://{{ ansible_host }}:{{ mem0_api_port }} (LAN-only, no NPM proxy)
          Dashboard: http://{{ ansible_host }}:{{ mem0_dashboard_port }} (LAN-only, no NPM proxy)
          Next: bootstrap the admin account and issue per-agent API keys (see plan Task 4).
```

- [ ] **Step 5: Syntax-check and dry-run**

Run: `cd ansible && ansible-playbook playbooks/ai/deploy-mem0-server.yml --syntax-check`
Expected: no errors.

Run: `ansible/scripts/run-playbook.sh mem0-server playbooks/ai/deploy-mem0-server.yml --limit unraid --check --diff`
Expected: shows the compose file and `.env` being created, no fatal errors. (Note: `--check` mode skips the `raw`-command build/deploy/wait tasks since they're guarded implicitly by `ansible_check_mode` where noted — the `template`/`assert` tasks still validate.)

- [ ] **Step 6: Apply**

Run: `ansible/scripts/run-playbook.sh mem0-server playbooks/ai/deploy-mem0-server.yml --limit unraid -v`
Expected: `PLAY RECAP` shows no failures; final debug task prints the API/dashboard URLs.

- [ ] **Step 7: Verify**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.20.14:8888/docs        # expect 200
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.20.14:8889/api/health  # expect 200
curl -s http://192.168.20.14:8888/auth/setup-status                            # expect {"needsSetup":true,...}
docker -H ssh://james@192.168.20.14 ps --filter name=mem0 --format 'table {{.Names}}\t{{.Status}}'
```
Expected: all three mem0 containers `Up`, both HTTP checks 200, setup-status reports `needsSetup: true` (no admin account yet — that's Task 4).

- [ ] **Step 8: Commit**

```bash
git add ansible/roles/mem0-server ansible/playbooks/ai/deploy-mem0-server.yml
git commit -m "feat(unraid): deploy self-hosted mem0-server for Hermes agent memory"
```

---

### Task 4: Bootstrap the mem0 admin account and issue per-agent API keys

This is a one-time, manually-run provisioning step (not an idempotent
Ansible task) — repeating it would mint duplicate API keys, same reasoning
as why `LYRA_API_SERVER_KEY` is manually exported rather than
playbook-generated.

**Files:** none (pure API calls)

**Interfaces:**
- Consumes: `http://192.168.20.14:8888` (Task 3), `admin_password` from the
  "mem0-server" 1Password item (Task 2).
- Produces: `LYRA_MEM0_API_KEY`, `RACLETTE_MEM0_API_KEY` values, consumed
  by Tasks 5/6 via `~/.env_container`.

- [ ] **Step 1: Register the admin account**

```bash
ADMIN_PASSWORD=$(op read "op://AI Wedge/mem0-server/admin_password")

curl -s -X POST http://192.168.20.14:8888/auth/register \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"James\",\"email\":\"james@klsll.com\",\"password\":\"${ADMIN_PASSWORD}\"}"
```
Expected: JSON containing `"access_token"`. (If it instead returns an
error saying an account already exists, skip to Step 2 — registration
already happened, e.g. from a prior partial run.)

- [ ] **Step 2: Log in and capture the access token**

```bash
LOGIN_RESP=$(curl -s -X POST http://192.168.20.14:8888/auth/login \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"james@klsll.com\",\"password\":\"${ADMIN_PASSWORD}\"}")
TOKEN=$(echo "$LOGIN_RESP" | grep -oE '"access_token":"[^"]*"' | cut -d'"' -f4)
echo "token acquired: ${TOKEN:+yes}"
```
Expected: `token acquired: yes`. If empty, print `$LOGIN_RESP` and check
the password matches what's stored in 1Password.

- [ ] **Step 3: Create Lyra's API key**

```bash
LYRA_KEY_RESP=$(curl -s -X POST http://192.168.20.14:8888/api-keys \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"label": "lyra"}')
LYRA_MEM0_API_KEY=$(echo "$LYRA_KEY_RESP" | grep -oE '"key":"[^"]*"' | cut -d'"' -f4)
echo "LYRA_MEM0_API_KEY=${LYRA_MEM0_API_KEY}"
```
Expected: a non-empty key printed (format like `mem0_...`). This value is
shown only once — copy it now.

- [ ] **Step 4: Create Raclette's API key**

```bash
RACLETTE_KEY_RESP=$(curl -s -X POST http://192.168.20.14:8888/api-keys \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"label": "raclette"}')
RACLETTE_MEM0_API_KEY=$(echo "$RACLETTE_KEY_RESP" | grep -oE '"key":"[^"]*"' | cut -d'"' -f4)
echo "RACLETTE_MEM0_API_KEY=${RACLETTE_MEM0_API_KEY}"
```
Expected: a second, different non-empty key printed.

- [ ] **Step 5: Add both keys to `~/.env_container`**

Append to `~/.env_container` on the controller (the file Lyra's/Raclette's
deploy playbooks already source for `LYRA_API_SERVER_KEY` etc.):

```bash
echo "export LYRA_MEM0_API_KEY='${LYRA_MEM0_API_KEY}'" >> ~/.env_container
echo "export RACLETTE_MEM0_API_KEY='${RACLETTE_MEM0_API_KEY}'" >> ~/.env_container
```

- [ ] **Step 6: Verify a key works end-to-end**

```bash
curl -s http://192.168.20.14:8888/memories \
  -H "X-API-Key: ${LYRA_MEM0_API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Test memory from plan Task 4"}],"user_id":"lyra","agent_id":"lyra"}'
```
Expected: a `2xx` JSON response (not `401`/`provider_auth_failed`). A
`provider_auth_failed` here means Task 1/3's `OPENAI_BASE_URL` wiring to
llama-swap isn't working — check `docker logs mem0-api` on Unraid before
proceeding to Tasks 5/6.

No commit for this task (no files changed).

---

### Task 5: Wire Lyra to mem0

**Files:**
- Modify: `ansible/files/jetson/hermes-lyra/config/hermes.yaml.j2:217-224`
- Create: `ansible/files/jetson/hermes-lyra/config/mem0.json.j2`
- Modify: `ansible/group_vars/edge_devices/jetson.lab.yml` (`lyra_env`)
- Modify: `ansible/roles/jetson-hermes-lyra/tasks/main.yml`

**Interfaces:**
- Consumes: `http://192.168.20.14:8888` (Task 3), `LYRA_MEM0_API_KEY` env
  var (Task 4).
- Produces: a live Lyra gateway with working `mem0_search`/`mem0_add`
  tools.

- [ ] **Step 1: Flip Lyra's memory config**

In `ansible/files/jetson/hermes-lyra/config/hermes.yaml.j2`, replace:

```yaml
memory:
  memory_enabled: false
  user_profile_enabled: false
  memory_char_limit: 2200
  user_char_limit: 1375
  provider: ''
  nudge_interval: 10
  flush_min_turns: 6
```

with:

```yaml
memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200
  user_char_limit: 1375
  provider: mem0
  nudge_interval: 10
  flush_min_turns: 6
```

- [ ] **Step 2: Create `mem0.json.j2`**

Create `ansible/files/jetson/hermes-lyra/config/mem0.json.j2`:

```json
{
  "mode": "selfhosted",
  "host": "http://{{ mem0_api_host }}:{{ mem0_api_port }}",
  "user_id": "lyra",
  "agent_id": "lyra"
}
```

- [ ] **Step 3: Add `mem0_api_host`/`mem0_api_port` defaults**

Add to `ansible/roles/jetson-hermes-lyra/defaults/main.yml` (near the top,
alongside the other constants):

```yaml
# Shared mem0-server on Unraid (ansible/roles/mem0-server) — same values
# Raclette's role uses.
mem0_api_host: "192.168.20.14"
mem0_api_port: 8888
```

- [ ] **Step 4: Add `MEM0_API_KEY` to `lyra_env`**

In `ansible/group_vars/edge_devices/jetson.lab.yml`, add to the `lyra_env`
dict (after `API_SERVER_KEY`):

```yaml
  MEM0_API_KEY: >-
    {{ lookup('env', 'LYRA_MEM0_API_KEY') | default('CHANGEME_LYRA_MEM0_API_KEY', true) }}
```

- [ ] **Step 5: Add the CHANGEME guard**

In `ansible/roles/jetson-hermes-lyra/tasks/main.yml`, after the existing
"Fail when Lyra API server key is not configured" task, add:

```yaml
- name: Fail when Lyra Mem0 API key is not configured
  ansible.builtin.fail:
    msg: |
      Mem0 API key not set for Lyra. Bootstrap it first (see
      docs/superpowers/plans/2026-07-25-mem0-hermes-memory.md Task 4), then
      export LYRA_MEM0_API_KEY before running.
  when: lyra_env.MEM0_API_KEY == 'CHANGEME_LYRA_MEM0_API_KEY'
```

- [ ] **Step 6: Render `mem0.json` to both profile paths**

The existing "Render Lyra config.yaml" tasks render `hermes.yaml.j2` to
*both* `{{ lyra_state_dir }}/config.yaml` (root profile) and
`{{ lyra_state_dir }}/profiles/lyra/config.yaml` (the named profile that's
actually running — see the comment above those tasks explaining why).
`mem0.json` needs the same treatment. Add these two tasks immediately
after the "Render Lyra config.yaml (named "lyra" profile...)" task:

```yaml
- name: Render Lyra mem0.json (root/default profile)
  ansible.builtin.template:
    src: "{{ playbook_dir }}/../../files/jetson/hermes-lyra/config/mem0.json.j2"
    dest: "{{ lyra_state_dir }}/mem0.json"
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0644'

- name: Render Lyra mem0.json (named "lyra" profile — the one actually running)
  ansible.builtin.template:
    src: "{{ playbook_dir }}/../../files/jetson/hermes-lyra/config/mem0.json.j2"
    dest: "{{ lyra_state_dir }}/profiles/lyra/mem0.json"
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0644'
```

- [ ] **Step 7: Syntax-check and dry-run**

Run: `cd ansible && ansible-playbook playbooks/jetson/deploy-hermes-lyra.yml --syntax-check`
Expected: no errors.

Run:
```bash
source ~/.env_container
cd ansible && ansible-playbook playbooks/jetson/deploy-hermes-lyra.yml --limit jetson.lab --check --diff
```
Expected: diff shows `memory.provider`/`memory_enabled` changes in both
rendered `config.yaml`s, plus two new `mem0.json` files being created. No
`CHANGEME` failures (confirms Task 4's key made it into the environment).

- [ ] **Step 8: Apply**

Run:
```bash
source ~/.env_container
cd ansible && ansible-playbook playbooks/jetson/deploy-hermes-lyra.yml --limit jetson.lab --diff -v
```
Expected: `PLAY RECAP` no failures; the "Restart Lyra's named-profile
gateway" task runs (may report failure harmlessly if the gateway wasn't
already running — see its existing comment).

- [ ] **Step 9: Verify**

```bash
ssh james@192.168.20.169 "cat /home/james/.hermes-lyra/profiles/lyra/mem0.json"
# expect: {"mode": "selfhosted", "host": "http://192.168.20.14:8888", "user_id": "lyra", "agent_id": "lyra"}

ssh james@192.168.20.169 "docker exec hermes-lyra grep -A3 '^memory:' /home/node/.hermes/profiles/lyra/config.yaml"
# expect: memory_enabled: true, provider: mem0
```

Then, from a live Lyra session (dashboard or gateway), issue a prompt that
should trigger `mem0_add` (e.g. "remember that my favorite color is
teal") followed by one that should trigger `mem0_search` (e.g. "what's my
favorite color?") and confirm she recalls it correctly.

- [ ] **Step 10: Commit**

```bash
git add ansible/files/jetson/hermes-lyra/config/hermes.yaml.j2 \
        ansible/files/jetson/hermes-lyra/config/mem0.json.j2 \
        ansible/roles/jetson-hermes-lyra/defaults/main.yml \
        ansible/roles/jetson-hermes-lyra/tasks/main.yml \
        ansible/group_vars/edge_devices/jetson.lab.yml
git commit -m "feat(jetson-lyra): enable mem0-backed memory for Lyra"
```

---

### Task 6: Wire Raclette to mem0

Same shape as Task 5, for Raclette. Raclette already has
`memory_enabled: true` — only `provider` changes.

**Files:**
- Modify: `ansible/files/jetson/raclette/config/hermes.yaml.j2:238-244`
- Create: `ansible/files/jetson/raclette/config/mem0.json.j2`
- Modify: `ansible/group_vars/edge_devices/jetson.lab.yml` (`raclette_env`)
- Modify: `ansible/roles/jetson-raclette/tasks/main.yml`
- Modify: `ansible/roles/jetson-raclette/defaults/main.yml`

**Interfaces:**
- Consumes: `http://192.168.20.14:8888` (Task 3), `RACLETTE_MEM0_API_KEY`
  env var (Task 4).
- Produces: a live Raclette gateway with working
  `mem0_search`/`mem0_add` tools, using `agent_id: raclette` so her
  memories stay separate from Lyra's in the shared store.

- [ ] **Step 1: Update Raclette's memory provider**

In `ansible/files/jetson/raclette/config/hermes.yaml.j2`, replace:

```yaml
memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200
  user_char_limit: 1375
  provider: ''
  nudge_interval: 10
  flush_min_turns: 6
```

with:

```yaml
memory:
  memory_enabled: true
  user_profile_enabled: true
  memory_char_limit: 2200
  user_char_limit: 1375
  provider: mem0
  nudge_interval: 10
  flush_min_turns: 6
```

- [ ] **Step 2: Create `mem0.json.j2`**

Create `ansible/files/jetson/raclette/config/mem0.json.j2`:

```json
{
  "mode": "selfhosted",
  "host": "http://{{ mem0_api_host }}:{{ mem0_api_port }}",
  "user_id": "raclette",
  "agent_id": "raclette"
}
```

- [ ] **Step 3: Add `mem0_api_host`/`mem0_api_port` defaults**

Add to `ansible/roles/jetson-raclette/defaults/main.yml` (same values as
Task 5 Step 3 — each role keeps its own copy, matching how these roles
already duplicate rather than share defaults):

```yaml
# Shared mem0-server on Unraid (ansible/roles/mem0-server).
mem0_api_host: "192.168.20.14"
mem0_api_port: 8888
```

- [ ] **Step 4: Add `MEM0_API_KEY` to `raclette_env`**

In `ansible/group_vars/edge_devices/jetson.lab.yml`, add to the
`raclette_env` dict (after `API_SERVER_KEY`, before `CAMOFOX_URL`):

```yaml
  MEM0_API_KEY: >-
    {{ lookup('env', 'RACLETTE_MEM0_API_KEY') | default('CHANGEME_RACLETTE_MEM0_API_KEY', true) }}
```

- [ ] **Step 5: Add the CHANGEME guard**

In `ansible/roles/jetson-raclette/tasks/main.yml`, after the existing
"Fail when API server key is not configured" task, add:

```yaml
- name: Fail when Raclette Mem0 API key is not configured
  ansible.builtin.fail:
    msg: |
      Mem0 API key not set for Raclette. Bootstrap it first (see
      docs/superpowers/plans/2026-07-25-mem0-hermes-memory.md Task 4), then
      export RACLETTE_MEM0_API_KEY before running.
  when: raclette_env.MEM0_API_KEY == 'CHANGEME_RACLETTE_MEM0_API_KEY'
```

- [ ] **Step 6: Render `mem0.json`**

Raclette has a single profile (no root-vs-named-profile split like Lyra).
Add this task in `ansible/roles/jetson-raclette/tasks/main.yml`
immediately after the existing "Render raclette config.yaml" task:

```yaml
- name: Render raclette mem0.json
  ansible.builtin.template:
    src: "{{ playbook_dir }}/../../files/jetson/raclette/config/mem0.json.j2"
    dest: "{{ raclette_state_dir }}/mem0.json"
    owner: "{{ ansible_user }}"
    group: "{{ ansible_user }}"
    mode: '0644'
```

- [ ] **Step 7: Syntax-check and dry-run**

Run: `cd ansible && ansible-playbook playbooks/jetson/deploy-raclette.yml --syntax-check`
Expected: no errors.

Run (per `docs/raclette-deploy-quirks` — needs `~/.env_container` and a
vault password file):
```bash
source ~/.env_container
cd ansible && ansible-playbook playbooks/jetson/deploy-raclette.yml --limit jetson.lab --check --diff --vault-password-file ~/.vault-pass
```
Expected: diff shows the `provider: mem0` change and the new `mem0.json`
file. No `CHANGEME` failures.

- [ ] **Step 8: Apply**

Run:
```bash
source ~/.env_container
cd ansible && ansible-playbook playbooks/jetson/deploy-raclette.yml --limit jetson.lab --diff -v --vault-password-file ~/.vault-pass
```
Expected: `PLAY RECAP` no failures.

- [ ] **Step 9: Verify**

```bash
ssh james@192.168.20.169 "docker exec raclette cat /home/node/.hermes/mem0.json"
# expect: {"mode": "selfhosted", "host": "http://192.168.20.14:8888", "user_id": "raclette", "agent_id": "raclette"}

ssh james@192.168.20.169 "docker exec raclette grep -A3 '^memory:' /home/node/.hermes/config.yaml"
# expect: memory_enabled: true, provider: mem0
```

Then, from a live Raclette session, repeat Task 5 Step 9's
remember/recall smoke test, and confirm via the mem0 dashboard
(`http://192.168.20.14:8889`) that Lyra's and Raclette's memories show up
as separate entries (different `agent_id`), not mixed together.

- [ ] **Step 10: Commit**

```bash
git add ansible/files/jetson/raclette/config/hermes.yaml.j2 \
        ansible/files/jetson/raclette/config/mem0.json.j2 \
        ansible/roles/jetson-raclette/defaults/main.yml \
        ansible/roles/jetson-raclette/tasks/main.yml \
        ansible/group_vars/edge_devices/jetson.lab.yml
git commit -m "feat(jetson-raclette): enable mem0-backed memory for Raclette"
```

---

## Rollout Summary

Run tasks in order — each depends on the previous:

1. Task 1 (llama-swap embedding model) — independent, can run any time.
2. Task 2 (1Password secrets) — independent, can run any time.
3. Task 3 (mem0-server deploy) — needs Tasks 1 + 2.
4. Task 4 (admin bootstrap + API keys) — needs Task 3.
5. Task 5 (Lyra wiring) — needs Task 4.
6. Task 6 (Raclette wiring) — needs Task 4. Independent of Task 5.

After all six: update `AGENTS.md`'s service tables (Unraid platform
services: add `mem0-server`; note the change isn't in this plan's scope —
flag it as a quick follow-up commit) and `docs/network-ports.md` (add
`8888`/`8889`).
