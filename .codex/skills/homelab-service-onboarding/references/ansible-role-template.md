# Ansible Role Template

Standard role structure for services deployed to Unraid via Docker Compose.
Unraid has no Python — always use `ansible.builtin.raw` for file system operations.

## Directory layout

```
ansible/roles/<name>/
├── defaults/
│   └── main.yml    # All config vars with defaults; credential lookups via op read
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

# Credentials — ENV var override first, then 1Password lookup
# Never hardcode values; never commit secrets to git
<name>_api_key: "{{ lookup('env', 'SERVICE_API_KEY') or
  lookup('pipe', 'op read \"op://AI Wedge/<Item>/credential\"') }}"
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

Keep playbooks thin — all logic belongs in the role.

## Unraid-specific notes

- **No Python on Unraid** — use `ansible.builtin.raw` for all file system operations; `copy` module requires Python on the target
- SSH key: `~/.ssh/id_ed25519_homelab`
- Always use `--limit unraid` (or explicit hostname) — never run without `--limit`
- `docker compose` (V2 plugin) is available; do not use `docker-compose` (V1 binary)
- Playbook group: `mcp/` for MCP servers, `platform/` for first-class apps, `misc/` for utilities
