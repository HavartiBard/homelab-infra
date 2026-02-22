# IronClaw First-Class Service Upgrade

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade IronClaw from a utility deployment (port 8090 on Unraid host) to a proper first-class service with a dedicated macvlan IP, NPM reverse proxy, DNS record, and Homepage dashboard card.

**Architecture:** IronClaw gets macvlan IP `192.168.20.56` on `br0` (same pattern as Gitea at .52). Postgres stays on an internal bridge network (no LAN exposure). The ironclaw container attaches to both networks — macvlan for LAN reachability, internal bridge to reach postgres by container name. NPM at 192.168.20.50 proxies `ironclaw.klsll.com` → `192.168.20.56:3000`.

**Tech Stack:** Ansible raw tasks (Unraid has no Python), Docker macvlan + bridge networking, Nginx Proxy Manager via `npm` Ansible role, Technitium DNS via npm role, Jinja2 templates.

**Branch:** `feature/ironclaw` — all work goes here. Do NOT commit to main.

---

## Context

The `feature/ironclaw` branch already has:
- `ansible/roles/ironclaw/` — full role (defaults, tasks, templates)
- `ansible/playbooks/misc/deploy-ironclaw.yml` — deploy playbook
- IronClaw running live on Unraid at 192.168.20.14:8090

What it's missing (required for first-class class per `.codex/skills/homelab-service-onboarding/`):
- Dedicated macvlan IP (192.168.20.56)
- NPM proxy host + DNS record
- Homepage dashboard card

The existing `ironclaw-net` bridge network will be replaced by:
1. `ironclaw-macvlan` — macvlan on br0, gives ironclaw its own LAN IP
2. `ironclaw-internal` — internal bridge for ironclaw↔postgres communication

**Reference files to study before implementing:**
- `ansible/roles/gitea/defaults/main.yml` — macvlan var pattern (gitea_ip, gitea_parent_iface, etc.)
- `ansible/files/npm/services/gitea.yml` — NPM service file format
- `ansible/playbooks/services/update-homepage-proxy.yml` — proxy playbook pattern
- `stacks/platform/homepage/config/services.yaml` — homepage card format
- `.codex/skills/homelab-service-onboarding/references/npm-service-template.yml` — NPM template

---

## Task 1: Update role defaults — replace port with macvlan vars

**Files:**
- Modify: `ansible/roles/ironclaw/defaults/main.yml`

**Step 1:** Replace `ironclaw_port: 8090` and `ironclaw_network: ironclaw-net` with macvlan vars. The new `defaults/main.yml` content:

```yaml
---
ironclaw_ip: 192.168.20.56
ironclaw_container_port: 3000
ironclaw_container_name: ironclaw
ironclaw_postgres_container: ironclaw-postgres
ironclaw_image: ironclaw:local
ironclaw_appdata_dir: /mnt/user/appdata/ironclaw
ironclaw_compose_dir: /opt/docker/ironclaw
ironclaw_macvlan_network: ironclaw-macvlan
ironclaw_internal_network: ironclaw-internal
ironclaw_parent_iface: br0
ironclaw_subnet: 192.168.20.0/23
ironclaw_gateway: 192.168.20.1
ironclaw_source_repo: https://github.com/nearai/ironclaw.git
ironclaw_source_tmp: /tmp/ironclaw-build
ironclaw_ollama_base_url: http://192.168.20.50:11434
ironclaw_ollama_model: llama3.1:8b-instruct-q4_K_M
ironclaw_agent_name: ironclaw
ironclaw_agent_max_parallel_jobs: 5
ironclaw_icon: https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/ai.png
timezone: America/Phoenix
```

**Step 2:** Verify the file looks correct:
```bash
cat ansible/roles/ironclaw/defaults/main.yml
```

**Step 3:** Commit:
```bash
cd /home/james/projects/homelab-infra
git add ansible/roles/ironclaw/defaults/main.yml
git commit -m "feat(ironclaw): replace port binding with macvlan IP vars"
```

---

## Task 2: Rewrite docker-compose template — macvlan + internal bridge

**Files:**
- Modify: `ansible/roles/ironclaw/templates/docker-compose.yml.j2`

**Step 1:** Replace the entire file with this content:

```yaml
services:
  ironclaw:
    image: "{{ ironclaw_image }}"
    container_name: "{{ ironclaw_container_name }}"
    restart: unless-stopped
    labels:
      net.unraid.docker.icon: "{{ ironclaw_icon }}"
      net.unraid.docker.webui: "https://ironclaw.klsll.com"
    env_file:
      - "{{ ironclaw_compose_dir }}/ironclaw.env"
    networks:
      {{ ironclaw_macvlan_network }}:
        ipv4_address: "{{ ironclaw_ip }}"
      {{ ironclaw_internal_network }}:
    depends_on:
      ironclaw-postgres:
        condition: service_healthy

  ironclaw-postgres:
    image: pgvector/pgvector:pg16
    container_name: "{{ ironclaw_postgres_container }}"
    restart: unless-stopped
    environment:
      POSTGRES_DB: ironclaw
      POSTGRES_USER: ironclaw
      POSTGRES_PASSWORD: "{{ ironclaw_pg_password }}"
      TZ: "{{ timezone }}"
    volumes:
      - "{{ ironclaw_appdata_dir }}/postgres:/var/lib/postgresql/data"
    networks:
      - "{{ ironclaw_internal_network }}"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ironclaw"]
      interval: 5s
      timeout: 3s
      retries: 5

networks:
  {{ ironclaw_macvlan_network }}:
    driver: macvlan
    driver_opts:
      parent: "{{ ironclaw_parent_iface }}"
    ipam:
      config:
        - subnet: "{{ ironclaw_subnet }}"
          gateway: "{{ ironclaw_gateway }}"
  {{ ironclaw_internal_network }}:
    driver: bridge
    internal: true
```

Key changes from old template:
- Removed `ports: - "{{ ironclaw_port }}:3000"` (no host port binding)
- ironclaw attaches to both macvlan (gets 192.168.20.56) and internal bridge
- postgres attaches only to internal bridge (no LAN exposure)
- macvlan network definition uses parent iface, subnet, gateway

**Step 2:** Validate the template renders correctly (dry-run):
```bash
cd ansible
ansible-playbook playbooks/misc/deploy-ironclaw.yml --limit unraid-server --check --diff 2>&1 | grep -E 'TASK|ok:|changed:|failed:|skipping'
```
Expected: no failures, all tasks ok or skipped (image already exists).

**Step 3:** Commit:
```bash
cd /home/james/projects/homelab-infra
git add ansible/roles/ironclaw/templates/docker-compose.yml.j2
git commit -m "feat(ironclaw): switch to macvlan+internal-bridge network topology"
```

---

## Task 3: Update role tasks — fix health check for macvlan

**Files:**
- Modify: `ansible/roles/ironclaw/tasks/main.yml`

The current health check does `curl http://localhost:{{ ironclaw_port }}/health`. With macvlan, there's no host port — the host can't reach the container's macvlan IP directly via localhost. Use `docker exec` instead.

**Step 1:** Find the health check task. It looks like:
```yaml
- name: Wait for IronClaw to be healthy (up to 60s)
  ansible.builtin.raw: |
    for i in $(seq 1 12); do
      if curl -sf http://localhost:{{ ironclaw_port }}/health > /dev/null 2>&1; then
```

**Step 2:** Replace just the health check loop body (the curl command):
```yaml
- name: Wait for IronClaw to be healthy (up to 60s)
  ansible.builtin.raw: |
    for i in $(seq 1 12); do
      if docker exec {{ ironclaw_container_name }} curl -sf http://localhost:{{ ironclaw_container_port }}/health > /dev/null 2>&1; then
        echo "healthy"; exit 0
      fi
      sleep 5
    done
    echo "timeout waiting for ironclaw" >&2; exit 1
  changed_when: false
```

Also: the deploy task currently does `docker compose up -d --remove-orphans`. Since we're changing network topology (old `ironclaw-net` bridge → new macvlan+internal), the old containers and networks won't be removed cleanly. Change the deploy task to `docker compose down && docker compose up -d` so the old bridge network is properly removed:

Find:
```yaml
- name: Deploy compose stack
  ansible.builtin.raw: |
    cd {{ ironclaw_compose_dir }} && docker compose up -d --remove-orphans
  changed_when: true
```

Replace with:
```yaml
- name: Deploy compose stack (down then up to ensure clean network transition)
  ansible.builtin.raw: |
    cd {{ ironclaw_compose_dir }} && docker compose down && docker compose up -d
  changed_when: true
```

**Step 3:** Run dry-run to verify no syntax errors:
```bash
cd ansible
ansible-playbook playbooks/misc/deploy-ironclaw.yml --limit unraid-server --syntax-check
```
Expected: `playbook: playbooks/misc/deploy-ironclaw.yml` with no errors.

**Step 4:** Commit:
```bash
cd /home/james/projects/homelab-infra
git add ansible/roles/ironclaw/tasks/main.yml
git commit -m "fix(ironclaw): use docker exec for health check, down+up for network transition"
```

---

## Task 4: Create NPM service file

**Files:**
- Create: `ansible/files/npm/services/ironclaw.yml`

**Step 1:** Study `ansible/files/npm/services/gitea.yml` for format, then create:

```yaml
---
proxy_hosts:
  - name: ironclaw
    domains:
      - ironclaw.klsll.com
    forward_host: 192.168.20.56
    forward_port: 3000
    scheme: http
    websocket: true
    certificate: klsll-wildcard
    ssl_forced: true
    hsts: true
    http2: true

dns_records:
  - name: ironclaw.klsll.com
    type: A
    value: 192.168.20.50
    ttl: 3600
```

Note: `forward_host` is the macvlan IP (192.168.20.56), `forward_port` is IronClaw's container port (3000). DNS A record points to NPM at 192.168.20.50, not to the macvlan IP — NPM handles SSL termination.

**Step 2:** Confirm the file looks correct:
```bash
cat ansible/files/npm/services/ironclaw.yml
```

**Step 3:** Commit:
```bash
cd /home/james/projects/homelab-infra
git add ansible/files/npm/services/ironclaw.yml
git commit -m "feat(ironclaw): add NPM proxy host and DNS record config"
```

---

## Task 5: Create NPM proxy deploy playbook

**Files:**
- Create: `ansible/playbooks/services/update-ironclaw-proxy.yml`

**Step 1:** Study `ansible/playbooks/services/update-homepage-proxy.yml` for pattern, then create:

```yaml
---
- name: Sync IronClaw proxy and DNS into Nginx Proxy Manager
  hosts: unraid
  gather_facts: false
  vars:
    npm_proxy_config_paths:
      - "{{ playbook_dir }}/../../files/npm/services/certificates.yml"
      - "{{ playbook_dir }}/../../files/npm/services/ironclaw.yml"
    npm_manage_proxies: true
    npm_manage_dns: true
  roles:
    - npm
```

**Step 2:** Syntax check:
```bash
cd ansible
ansible-playbook playbooks/services/update-ironclaw-proxy.yml --syntax-check
```
Expected: no errors.

**Step 3:** Commit:
```bash
cd /home/james/projects/homelab-infra
git add ansible/playbooks/services/update-ironclaw-proxy.yml
git commit -m "feat(ironclaw): add NPM proxy deploy playbook"
```

---

## Task 6: Add Homepage dashboard card

**Files:**
- Modify: `stacks/platform/homepage/config/services.yaml`

**Step 1:** Read the current file to understand the group structure. The file uses a YAML list of groups. Add an "AI" group at the end (before or after DevOps — check the current content for best placement).

**Step 2:** Append this block at the end of `stacks/platform/homepage/config/services.yaml`:

```yaml

- AI:
    - IronClaw:
        icon: https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/ai.png
        href: https://ironclaw.klsll.com
        description: Local AI assistant — web UI, Slack, webhooks (Unraid)
```

**Step 3:** Verify YAML is valid:
```bash
python3 -c "import yaml; yaml.safe_load(open('stacks/platform/homepage/config/services.yaml'))" && echo "YAML valid"
```
Expected: `YAML valid`

**Step 4:** Commit:
```bash
cd /home/james/projects/homelab-infra
git add stacks/platform/homepage/config/services.yaml
git commit -m "feat(ironclaw): add IronClaw card to Homepage AI group"
```

---

## Task 7: Update port registry docs

**Files:**
- Modify: `docs/network-ports.md`

**Step 1:** Find the IronClaw row. Currently it says:
```
| **IronClaw** | 8090 | TCP | 🌐 Proxied | AI assistant — web UI, webhooks, Slack (Unraid) |
```

**Step 2:** Replace it with:
```
| **IronClaw** | 3000 (macvlan) | TCP | 🌐 Proxied | AI assistant — web UI, webhooks, Slack; macvlan 192.168.20.56, proxied via ironclaw.klsll.com |
```

Also update the NPM hostname table. Find the ironclaw row:
```
| `ironclaw.klsll.com` | http://192.168.20.14:8090 | Built-in | Unraid IronClaw AI assistant |
```
Replace with:
```
| `ironclaw.klsll.com` | http://192.168.20.56:3000 | Built-in | IronClaw AI assistant (macvlan) |
```

**Step 3:** Commit:
```bash
cd /home/james/projects/homelab-infra
git add docs/network-ports.md
git commit -m "docs: update IronClaw port registry to reflect macvlan deployment"
```

---

## Task 8: Deploy updated IronClaw stack to Unraid

**Step 1:** Full deploy playbook — this will bring down the old stack and bring up the new one with macvlan networking:
```bash
cd ansible
ansible-playbook playbooks/misc/deploy-ironclaw.yml --diff --limit unraid-server -v 2>&1 | grep -E 'TASK|ok:|changed:|failed:|PLAY RECAP'
```

Expected:
- Clone/patch/build tasks: SKIPPED (image already exists)
- "Deploy compose stack (down then up)": changed
- "Wait for IronClaw to be healthy": ok (docker exec curl succeeds)
- PLAY RECAP: `failed=0`

**Step 2:** Verify containers have correct IPs:
```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 "docker inspect ironclaw | python3 -c \"import sys,json; n=json.load(sys.stdin)[0]['NetworkSettings']['Networks']; print({k: v.get('IPAddress') for k,v in n.items()})\""
```
Expected: `{'ironclaw-macvlan': '192.168.20.56', 'ironclaw-internal': '<bridge-ip>'}`

**Step 3:** Verify health endpoint is reachable from macvlan IP:
```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 "docker exec ironclaw curl -sf http://localhost:3000/health && echo OK"
```
Expected: `OK`

**Step 4:** Verify old bridge network `ironclaw-net` is gone:
```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 "docker network ls | grep ironclaw"
```
Expected: shows `ironclaw-macvlan` and `ironclaw-internal`, no `ironclaw-net`.

---

## Task 9: Deploy NPM proxy config

**Step 1:** Syntax check first:
```bash
cd ansible
ansible-playbook playbooks/services/update-ironclaw-proxy.yml --syntax-check
```

**Step 2:** Dry-run:
```bash
ansible-playbook playbooks/services/update-ironclaw-proxy.yml --check --diff --limit unraid-server 2>&1 | tail -20
```

**Step 3:** Apply:
```bash
ansible-playbook playbooks/services/update-ironclaw-proxy.yml --diff --limit unraid-server -v 2>&1 | grep -E 'TASK|ok:|changed:|failed:|PLAY RECAP'
```
Expected: `failed=0`, DNS and proxy tasks changed or ok.

**Step 4:** Verify proxy host exists in NPM:
```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 "curl -s http://192.168.20.50:81/api/nginx/proxy-hosts | python3 -c \"import sys,json; hosts=json.load(sys.stdin); print([h['domain_names'] for h in hosts if any('ironclaw' in d for d in h['domain_names'])])\""
```
Expected: `[['ironclaw.klsll.com']]`

**Step 5:** Test HTTPS access (DNS must have propagated to AdGuard):
```bash
curl -sk https://ironclaw.klsll.com/health && echo "HTTPS OK"
```
Expected: `HTTPS OK`

---

## Task 10: Idempotence check + PR update

**Step 1:** Re-run deploy playbook with `--check`, expect `changed=0`:
```bash
cd ansible
ansible-playbook playbooks/misc/deploy-ironclaw.yml --check --diff --limit unraid-server 2>&1 | tail -5
```
Expected: `changed=0 failed=0`

**Step 2:** Re-run NPM proxy playbook with `--check`, expect `changed=0`:
```bash
ansible-playbook playbooks/services/update-ironclaw-proxy.yml --check --diff --limit unraid-server 2>&1 | tail -5
```
Expected: `changed=0 failed=0`

**Step 3:** Push branch and update PR #40:
```bash
cd /home/james/projects/homelab-infra
git push origin feature/ironclaw
```
Then add a comment to PR #40 via Gitea MCP (`mcp__gitea__create_comment`) summarizing the first-class upgrade additions.
