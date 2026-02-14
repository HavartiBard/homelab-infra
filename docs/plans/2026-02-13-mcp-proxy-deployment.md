# mcp-proxy Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy mcp-proxy on Unraid to expose SoulLayer's stdio MCP interface over HTTP/SSE, enabling multi-machine access.

**Architecture:** mcp-proxy container with Docker socket access executes into soullayer container on-demand, translating HTTP/SSE requests to stdio MCP protocol. JSON config defines stdio servers to expose.

**Tech Stack:** Docker, mcp-proxy (sparfenyuk/mcp-proxy:v0.3.2-alpine), Ansible, JSON config

---

## Task 1: Create Ansible Role Structure

**Files:**
- Create: `ansible/roles/mcp-proxy/tasks/main.yml`
- Create: `ansible/roles/mcp-proxy/defaults/main.yml`
- Create: `ansible/roles/mcp-proxy/templates/servers.json.j2`
- Create: `ansible/roles/mcp-proxy/handlers/main.yml`

**Step 1: Create role directory structure**

```bash
cd /home/james/projects/homelab-infra/ansible
mkdir -p roles/mcp-proxy/{tasks,defaults,templates,handlers}
```

**Step 2: Create defaults/main.yml with variables**

File: `ansible/roles/mcp-proxy/defaults/main.yml`

```yaml
---
# mcp-proxy default variables

# Container settings
mcp_proxy_image: "ghcr.io/sparfenyuk/mcp-proxy:v0.3.2-alpine"
mcp_proxy_container_name: "mcp-proxy"
mcp_proxy_port: 6980
mcp_proxy_icon: >-
  https://raw.githubusercontent.com/sparfenyuk/mcp-proxy/main/icon.png
mcp_proxy_webui_url: >-
  http://{{ ansible_host }}:{{ mcp_proxy_port }}/servers/soullayer/sse

# Paths
mcp_proxy_appdata_dir: "/mnt/user/appdata/mcp-proxy"

# Server settings
mcp_proxy_host: "0.0.0.0"

# MCP servers to expose
mcp_proxy_servers:
  - name: soullayer
    command: docker
    args:
      - exec
      - -i
      - soullayer
      - soullayer
      - serve
    transport_type: stdio

# Timezone
timezone: "America/Phoenix"
```

**Step 3: Create servers.json.j2 template**

File: `ansible/roles/mcp-proxy/templates/servers.json.j2`

```json
{
  "mcpServers": {
{% for server in mcp_proxy_servers %}
    "{{ server.name }}": {
      "command": "{{ server.command }}",
      "args": {{ server.args | to_json }},
      "transportType": "{{ server.transport_type }}"
    }{% if not loop.last %},{% endif %}

{% endfor %}
  }
}
```

**Step 4: Create empty handlers file**

File: `ansible/roles/mcp-proxy/handlers/main.yml`

```yaml
---
# mcp-proxy handlers (placeholder for future use)
```

**Step 5: Verify directory structure**

```bash
tree roles/mcp-proxy
```

Expected output:
```
roles/mcp-proxy
├── defaults
│   └── main.yml
├── handlers
│   └── main.yml
├── tasks
└── templates
    └── servers.json.j2
```

**Step 6: Commit role skeleton**

```bash
git add roles/mcp-proxy
git commit -m "feat(mcp-proxy): Add Ansible role skeleton

Initialize mcp-proxy role structure with defaults and templates.
Configures stdio-to-HTTP bridge for SoulLayer and future stdio MCPs.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Implement Deployment Tasks

**Files:**
- Modify: `ansible/roles/mcp-proxy/tasks/main.yml`

**Step 1: Write tasks for directory creation and image pull**

File: `ansible/roles/mcp-proxy/tasks/main.yml`

```yaml
---
# Using raw/shell commands since Unraid lacks Python

- name: Create appdata directory
  ansible.builtin.raw: mkdir -p {{ mcp_proxy_appdata_dir }}
  changed_when: false

- name: Create config directory
  ansible.builtin.raw: mkdir -p {{ mcp_proxy_appdata_dir }}/config
  changed_when: false

- name: Pull container image
  ansible.builtin.raw: docker pull {{ mcp_proxy_image }}
  register: pull_result
  changed_when: "'Downloaded newer image' in pull_result.stdout or 'Pull complete' in pull_result.stdout"

- name: Template servers.json configuration
  ansible.builtin.template:
    src: servers.json.j2
    dest: "{{ mcp_proxy_appdata_dir }}/config/servers.json"
    mode: "0644"
  delegate_to: localhost
  register: config_template

- name: Copy servers.json to Unraid
  ansible.builtin.copy:
    src: "{{ config_template.dest }}"
    dest: "{{ mcp_proxy_appdata_dir }}/config/servers.json"
    mode: "0644"
```

**Step 2: Add container stop/remove tasks**

Append to `ansible/roles/mcp-proxy/tasks/main.yml`:

```yaml
- name: Stop existing container (if running)
  ansible.builtin.raw: docker stop {{ mcp_proxy_container_name }} 2>/dev/null || true
  changed_when: false

- name: Remove existing container (if exists)
  ansible.builtin.raw: docker rm {{ mcp_proxy_container_name }} 2>/dev/null || true
  changed_when: false
```

**Step 3: Add container deployment task**

Append to `ansible/roles/mcp-proxy/tasks/main.yml`:

```yaml
- name: Deploy mcp-proxy container
  ansible.builtin.raw: |
    docker run -d \
      --name {{ mcp_proxy_container_name }} \
      --restart unless-stopped \
      --label net.unraid.docker.icon='{{ mcp_proxy_icon }}' \
      --label net.unraid.docker.webui='{{ mcp_proxy_webui_url }}' \
      -p {{ mcp_proxy_port }}:{{ mcp_proxy_port }} \
      -v {{ mcp_proxy_appdata_dir }}/config/servers.json:/config/servers.json:ro \
      -v /var/run/docker.sock:/var/run/docker.sock:ro \
      -e TZ={{ timezone }} \
      {{ mcp_proxy_image }} \
      --port={{ mcp_proxy_port }} \
      --host={{ mcp_proxy_host }} \
      --named-server-config=/config/servers.json
  register: deploy_result
  changed_when: true
```

**Step 4: Add health check tasks**

Append to `ansible/roles/mcp-proxy/tasks/main.yml`:

```yaml
- name: Wait for container to start
  ansible.builtin.raw: sleep 5
  changed_when: false

- name: Check container is running
  ansible.builtin.raw: docker ps --filter "name={{ mcp_proxy_container_name }}" --filter "status=running" -q
  register: container_check
  failed_when: container_check.stdout | trim == ""
  changed_when: false

- name: Get container logs
  ansible.builtin.raw: docker logs --tail 20 {{ mcp_proxy_container_name }}
  register: container_logs
  changed_when: false

- name: Display container logs
  ansible.builtin.debug:
    msg: "{{ container_logs.stdout_lines }}"
```

**Step 5: Verify tasks file syntax**

```bash
cd /home/james/projects/homelab-infra/ansible
ansible-playbook --syntax-check roles/mcp-proxy/tasks/main.yml
```

Expected: `playbook: roles/mcp-proxy/tasks/main.yml` (no errors)

**Step 6: Commit deployment tasks**

```bash
git add roles/mcp-proxy/tasks/main.yml
git commit -m "feat(mcp-proxy): Implement deployment tasks

Deploy mcp-proxy container with:
- Docker socket mount for exec access
- JSON config for stdio server definitions
- Port 6980 exposure
- Health checks and logging

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Create Deployment Playbook

**Files:**
- Create: `ansible/playbooks/mcp/deploy-mcp-proxy.yml`

**Step 1: Create playbook file**

File: `ansible/playbooks/mcp/deploy-mcp-proxy.yml`

```yaml
---
# Deploy mcp-proxy (stdio-to-HTTP bridge) to Unraid
- name: Deploy mcp-proxy
  hosts: unraid
  gather_facts: false

  roles:
    - mcp-proxy

  post_tasks:
    - name: Display access information
      ansible.builtin.debug:
        msg: |
          mcp-proxy deployed successfully!

          SoulLayer MCP URL: http://{{ ansible_host }}:6980/servers/soullayer/sse
          Transport: SSE (Server-Sent Events)

          Configure your IDE with:
          {
            "mcpServers": {
              "soullayer": {
                "url": "http://{{ ansible_host }}:6980/servers/soullayer/sse"
              }
            }
          }

          Test endpoint:
          curl -v http://{{ ansible_host }}:6980/servers/soullayer/sse
```

**Step 2: Validate playbook syntax**

```bash
cd /home/james/projects/homelab-infra/ansible
ansible-playbook playbooks/mcp/deploy-mcp-proxy.yml --syntax-check
```

Expected: `playbook: playbooks/mcp/deploy-mcp-proxy.yml` (no errors)

**Step 3: Run playbook in check mode**

```bash
ansible-playbook playbooks/mcp/deploy-mcp-proxy.yml --check --diff --limit unraid
```

Expected: Shows changes that would be made (create directories, pull image, deploy container)

**Step 4: Commit playbook**

```bash
git add playbooks/mcp/deploy-mcp-proxy.yml
git commit -m "feat(mcp-proxy): Add deployment playbook

Create playbook for deploying mcp-proxy to Unraid.
Exposes stdio MCP servers (starting with SoulLayer) over HTTP/SSE.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Deploy to Unraid

**Files:**
- N/A (runtime deployment)

**Step 1: Run deployment playbook**

```bash
cd /home/james/projects/homelab-infra/ansible
ansible-playbook playbooks/mcp/deploy-mcp-proxy.yml --diff --limit unraid -v
```

Expected output:
- Creates `/mnt/user/appdata/mcp-proxy` directory
- Pulls `ghcr.io/sparfenyuk/mcp-proxy:v0.3.2-alpine`
- Templates and copies `servers.json`
- Deploys mcp-proxy container
- Container status: running
- Logs show successful startup

**Step 2: Verify container is running**

```bash
ssh root@192.168.20.14 "docker ps | grep mcp-proxy"
```

Expected: Container with status "Up" and port mapping `0.0.0.0:6980->6980/tcp`

**Step 3: Check container logs**

```bash
ssh root@192.168.20.14 "docker logs mcp-proxy --tail 20"
```

Expected: No errors, shows mcp-proxy listening on port 6980

**Step 4: Verify servers.json was created**

```bash
ssh root@192.168.20.14 "cat /mnt/user/appdata/mcp-proxy/config/servers.json"
```

Expected output:
```json
{
  "mcpServers": {
    "soullayer": {
      "command": "docker",
      "args": ["exec", "-i", "soullayer", "soullayer", "serve"],
      "transportType": "stdio"
    }
  }
}
```

**Step 5: Test endpoint responds**

```bash
curl -v http://192.168.20.14:6980/servers/soullayer/sse
```

Expected: HTTP response (even if error, confirms routing works)

**Step 6: Verify deployment is idempotent**

```bash
ansible-playbook playbooks/mcp/deploy-mcp-proxy.yml --diff --limit unraid -v
```

Expected: `changed=0`, no modifications made on second run

---

## Task 5: Configure Claude Code Client

**Files:**
- Create: `/home/james/projects/agent-flow/.mcp.json`

**Step 1: Create .mcp.json in agent-flow project**

File: `/home/james/projects/agent-flow/.mcp.json`

```json
{
  "mcpServers": {
    "soullayer": {
      "url": "http://192.168.20.14:6980/servers/soullayer/sse"
    }
  }
}
```

**Step 2: Verify .mcp.json is valid JSON**

```bash
cd /home/james/projects/agent-flow
jq . .mcp.json
```

Expected: Pretty-printed JSON (no errors)

**Step 3: Add .mcp.json to git (if not gitignored)**

Check if MCP configs should be committed:
```bash
git check-ignore .mcp.json || echo "Not ignored, safe to commit"
```

If safe to commit:
```bash
git add .mcp.json
git commit -m "feat: Add SoulLayer MCP via HTTP/SSE

Configure Claude Code to access SoulLayer through mcp-proxy bridge.
Enables multi-machine access to soul.md and memories.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Step 4: Test MCP connection in Claude Code**

Manual test:
1. Restart Claude Code session
2. Check available MCP tools
3. Verify `soul_read`, `memory_search`, `lessons_check` appear
4. Call `soul_read` and verify response contains soul.md content

**Step 5: Document client configuration**

Update: `/home/james/projects/homelab-infra/docs/plans/2026-02-13-soullayer-http-access-design.md`

Add section under "Client Configuration" with verified working config.

---

## Task 6: Configure Codex Client

**Files:**
- Modify: `/home/james/.codex/config.toml`

**Step 1: Update Codex MCP server config**

Current config has:
```toml
[mcp_servers.soullayer]
command = "ssh"
args = ["root@192.168.20.14", "docker", "exec", "-i", "soullayer", "soullayer", "serve"]
```

Replace with:
```toml
[mcp_servers.soullayer]
url = "http://192.168.20.14:6980/servers/soullayer/sse"
```

**Step 2: Validate TOML syntax**

```bash
python3 -c "import tomli; tomli.load(open('/home/james/.codex/config.toml', 'rb'))"
```

Expected: No output (valid TOML)

**Step 3: Test Codex MCP connection**

Manual test:
1. Start new Codex session
2. Check MCP tools are available
3. Verify SoulLayer tools work via HTTP

**Step 4: Document successful migration**

Note: This completes the migration from SSH stdio to HTTP/SSE transport.

---

## Task 7: Update AGENTS.md Documentation

**Files:**
- Modify: `/home/james/projects/homelab-infra/AGENTS.md`

**Step 1: Add mcp-proxy to services table**

Locate the "Key Services" table and add:

```markdown
| mcp-proxy | Unraid | 6980 | - | stdio-to-HTTP MCP bridge |
```

**Step 2: Document SoulLayer HTTP endpoint**

Update SoulLayer entry in services table:

```markdown
| SoulLayer | Unraid | 6980 | `http://192.168.20.14:6980/servers/soullayer/sse` | MCP personality/memory (via mcp-proxy) |
```

**Step 3: Add troubleshooting section**

Add under "Common Troubleshooting":

```markdown
### mcp-proxy Not Responding
```bash
# Check container status
docker ps | grep mcp-proxy

# Check logs
docker logs mcp-proxy -f

# Verify servers.json
docker exec mcp-proxy cat /config/servers.json

# Test endpoint
curl -v http://localhost:6980/servers/soullayer/sse
```

**Step 4: Commit documentation updates**

```bash
cd /home/james/projects/homelab-infra
git add AGENTS.md
git commit -m "docs: Document mcp-proxy deployment and usage

Add mcp-proxy to services table and troubleshooting guide.
Update SoulLayer access pattern from SSH to HTTP/SSE.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Integration Testing

**Files:**
- N/A (runtime testing)

**Step 1: Test from dev-box**

```bash
curl -X POST http://192.168.20.14:6980/servers/soullayer/sse \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

Expected: JSON response with list of SoulLayer MCP tools

**Step 2: Test soul_read tool**

Via Claude Code or Codex, call the `soul_read` tool.

Expected: Returns content from `/mnt/user/appdata/soullayer/data/soul.md`

**Step 3: Test memory operations**

Via Claude Code or Codex:
1. Call `memory_store` to save a test memory
2. Call `memory_search` to retrieve it
3. Verify memories persist in `.soullayer/memories.db`

**Step 4: Verify multi-machine access**

If jetson nano is available:
1. Configure jetson nano with same HTTP endpoint
2. Test connection from jetson nano
3. Verify same soul.md content accessible

**Step 5: Check Docker socket permissions**

```bash
ssh root@192.168.20.14 "docker exec mcp-proxy docker ps"
```

Expected: Output shows docker command works (proves socket access)

**Step 6: Document test results**

Create test report in `/home/james/projects/homelab-infra/docs/plans/2026-02-13-mcp-proxy-test-results.md`

Include:
- ✅ Container deployment successful
- ✅ HTTP endpoint responding
- ✅ SoulLayer tools accessible
- ✅ Memory operations working
- ✅ Multi-machine access confirmed (if tested)

---

## Task 9: Director Integration (Optional)

**Files:**
- Modify: `/home/james/projects/homelab-infra/ansible/files/director/docker-compose.yml` (if needed)

**Step 1: Check if Director needs mcp-proxy registration**

Review Director's MCP server configuration:
```bash
cat /home/james/projects/homelab-infra/ansible/files/director/docker-compose.yml
```

**Step 2: Add SoulLayer to Director's MCP registry**

If Director supports dynamic MCP server registration via config/API, add:
```json
{
  "name": "soullayer",
  "url": "http://192.168.20.14:6980/servers/soullayer/sse",
  "transport": "sse"
}
```

**Step 3: Test SoulLayer access via Director**

Connect to Director and verify SoulLayer tools are available through aggregation.

**Step 4: Commit Director configuration**

If changes were made:
```bash
git add ansible/files/director/docker-compose.yml
git commit -m "feat(director): Register SoulLayer MCP via mcp-proxy

Add SoulLayer to Director's MCP server registry for centralized access.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Final Documentation and Cleanup

**Files:**
- Modify: `/home/james/projects/homelab-infra/docs/plans/2026-02-13-soullayer-http-access-design.md`

**Step 1: Update design doc with "Implemented" status**

Change status from "Approved" to "Implemented":
```markdown
**Status:** Implemented (2026-02-13)
```

**Step 2: Add deployment notes**

Add "Deployment Notes" section:
```markdown
## Deployment Notes

Successfully deployed on 2026-02-13:
- mcp-proxy container running on Unraid:6980
- SoulLayer accessible via HTTP/SSE from all machines
- Claude Code and Codex clients configured and tested
- Memory operations verified working
```

**Step 3: Create README for mcp-proxy role**

File: `ansible/roles/mcp-proxy/README.md`

```markdown
# mcp-proxy Ansible Role

Deploys mcp-proxy (stdio-to-HTTP bridge) for exposing stdio MCP servers over HTTP/SSE.

## Variables

See `defaults/main.yml` for full list.

## Usage

```bash
ansible-playbook playbooks/mcp/deploy-mcp-proxy.yml --limit unraid
```

## Adding New stdio MCP Servers

Edit `defaults/main.yml` and add to `mcp_proxy_servers` list:

```yaml
mcp_proxy_servers:
  - name: my-new-mcp
    command: docker
    args: [exec, -i, my-container, my-mcp-command]
    transport_type: stdio
```

Endpoint will be: `http://unraid:6980/servers/my-new-mcp/sse`
```

**Step 4: Commit final documentation**

```bash
git add docs/plans/2026-02-13-soullayer-http-access-design.md ansible/roles/mcp-proxy/README.md
git commit -m "docs: Mark SoulLayer HTTP access as implemented

Update design doc status and add deployment notes.
Include mcp-proxy role README for future reference.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

**Step 5: Push all commits**

```bash
cd /home/james/projects/homelab-infra
git log --oneline -10  # Review commits
git push origin main
```

Expected: All commits pushed successfully

---

## Success Criteria

- ✅ mcp-proxy container running on Unraid
- ✅ Port 6980 accessible from dev-box and other machines
- ✅ SoulLayer HTTP endpoint responds: `http://192.168.20.14:6980/servers/soullayer/sse`
- ✅ Claude Code configured and can call SoulLayer MCP tools
- ✅ Codex configured and can call SoulLayer MCP tools
- ✅ Memory operations (store/search) working via HTTP
- ✅ Deployment is idempotent (re-running playbook makes no changes)
- ✅ Documentation updated in AGENTS.md and design docs
- ✅ All commits pushed to git

## Rollback Procedure

If deployment fails:

```bash
# Stop and remove mcp-proxy container
ssh root@192.168.20.14 "docker stop mcp-proxy && docker rm mcp-proxy"

# Revert client configs to SSH stdio
# In .codex/config.toml:
[mcp_servers.soullayer]
command = "ssh"
args = ["root@192.168.20.14", "docker", "exec", "-i", "soullayer", "soullayer", "serve"]
```

No changes to SoulLayer container (unchanged by this deployment).
