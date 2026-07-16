# Ansible Role Template

Standard role structure for services deployed to Unraid via Docker Compose.
Unraid has no Python — always use `ansible.builtin.raw` for file system operations.

## Directory layout

```
ansible/roles/<name>/
├── defaults/
│   └── main.yml    # All config vars with defaults; credentials via lookup('env', ...)
└── tasks/
    └── main.yml    # Compose deploy + container lifecycle
```

Handlers are optional — use only if restart-on-change semantics are needed.

## defaults/main.yml pattern

```yaml
---
# Config vars — override via host_vars or -e flags at deploy time
<name>_port: <NNNN>
<name>_image: "org/image:tag"
<name>_appdata: "/mnt/user/appdata/<name>"
<name>_compose_dir: "/opt/docker/<name>"

# Credentials resolve from 1Password via `op run` at invocation time — see
# docs/secrets-management.md. No fallback: a missing/misnamed reference
# should fail loudly, not deploy with an empty secret.
<name>_api_key: "{{ lookup('ansible.builtin.env', 'SERVICE_API_KEY') | default('', true) }}"
```

Add a matching `ansible/envs/<name>.env` with the `op://` reference(s) this role needs:
```
SERVICE_API_KEY=op://AI Wedge/<Item>/credential
```
and a fail-closed assert in `tasks/main.yml`:
```yaml
- name: Assert <name> credentials are provided
  ansible.builtin.assert:
    that:
      - <name>_api_key | length > 0
    fail_msg: "Set SERVICE_API_KEY env var (from 1Password), e.g. via ansible/envs/<name>.env"
```

## tasks/main.yml pattern

```yaml
---
- name: Ensure appdata directory exists
  ansible.builtin.raw: mkdir -p {{ <name>_appdata }}

- name: Ensure compose directory exists
  ansible.builtin.raw: mkdir -p {{ <name>_compose_dir }}

- name: Write docker-compose.yml
  ansible.builtin.copy:
    content: "{{ lookup('file', '../files/<name>/docker-compose.yml') }}"
    dest: "{{ <name>_compose_dir }}/docker-compose.yml"

- name: Pull image
  ansible.builtin.raw: docker pull {{ <name>_image }}
  tags: [image]

- name: Deploy compose stack
  ansible.builtin.raw: |
    cd {{ <name>_compose_dir }}
    docker compose up -d --remove-orphans

- name: Wait for service to be healthy
  ansible.builtin.raw: |
    for i in $(seq 1 12); do
      if curl -sf http://localhost:{{ <name>_port }}/health > /dev/null 2>&1; then
        echo "healthy"; exit 0
      fi
      sleep 5
    done
    echo "timeout waiting for <name>" >&2; exit 1
  changed_when: false
```

## docker-compose.yml pattern (ansible/files/<name>/docker-compose.yml)

```yaml
services:
  <name>:
    image: "{{ <name>_image }}"
    container_name: <name>
    restart: unless-stopped
    labels:
      net.unraid.docker.icon: "<unraid_icon_url>"
      net.unraid.docker.webui: "http://192.168.20.14:{{ <name>_port }}"
    environment:
      TZ: America/Phoenix
      # Add service-specific env vars here
    ports:
      - "{{ <name>_port }}:<container_port>"
    volumes:
      - "{{ <name>_appdata }}:/data"
    deploy:
      resources:
        limits:
          memory: 512m
          cpus: "1.0"
```

## deploy playbook pattern (ansible/playbooks/<group>/deploy-<name>.yml)

```yaml
---
- name: Deploy <Display Name>
  hosts: unraid
  gather_facts: false
  roles:
    - role: <name>
```

Keep playbooks thin — all logic belongs in the role. Run with
`./scripts/run-playbook.sh <name> playbooks/<group>/deploy-<name>.yml` so secrets resolve from
`ansible/envs/<name>.env`.

## Unraid-specific notes

- **No Python on Unraid** — use `ansible.builtin.raw` for all file system operations; `copy` module requires Python on the target
- SSH key: `~/.ssh/id_ed25519_homelab`
- Always use `--limit unraid` (or explicit hostname) — never run without `--limit`
- `docker compose` (V2 plugin) is available; do not use `docker-compose` (V1 binary)
- Playbook group: `mcp/` for MCP servers, `platform/` for first-class apps, `misc/` for utilities
