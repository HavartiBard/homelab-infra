# Observability Stack Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy a full observability stack (Loki + Prometheus + Grafana + syslog-ng + Alertmanager) on Unraid with Promtail/node_exporter/cAdvisor agents across all homelab hosts.

**Architecture:** Core services run as a Docker Compose stack on Unraid, managed by an Ansible role using `raw` commands (Unraid has no Python). Lightweight agents are deployed to each host via separate Ansible roles. Grafana is provisioned with Loki and Prometheus datasources on first boot via config files.

**Tech Stack:** Grafana Loki 3.3.2, Prometheus 2.54.1, Grafana 11.3.0, syslog-ng 4.8, Alertmanager 0.27, Promtail 3.3.2, node_exporter 1.8.2, cAdvisor 0.49.1, Ansible raw tasks (Unraid pattern)

**Gitea Issues:** #61 (core stack), #62 (agents), #63 (syslog), #64 (DNS logs), #65 (dashboards), #66 (alertmanager), #67 (NPM proxy)

---

## Task 1: Add vault vars for Grafana and Alertmanager

**Files:**
- Modify: `ansible/group_vars/all/vault.yml` (via ansible-vault)

**Step 1: Open vault for editing**

```bash
cd ansible
ansible-vault edit group_vars/all/vault.yml
```

**Step 2: Add these vars at the end**

```yaml
vault_grafana_admin_password: "CHANGEME_grafana_admin"
vault_alertmanager_slack_webhook_url: "CHANGEME_slack_webhook"
```

Replace `CHANGEME_grafana_admin` with a strong password (generate with `openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32`).

Replace `CHANGEME_slack_webhook` with the Slack incoming webhook URL for your alerts channel. You can reuse the IronClaw Slack app or create a new one.

**Step 3: Verify vault is readable**

```bash
ansible -i inventory/hosts.yml localhost -m debug \
  -a "msg={{ vault_grafana_admin_password }}" \
  -e "@group_vars/all/vault.yml" --vault-password-file ~/.vault-pass 2>/dev/null | grep -q CHANGEME \
  && echo "placeholder still set — update the vault values" || echo "vault vars readable"
```

**Step 4: Commit**

```bash
git add ansible/group_vars/all/vault.yml
git commit -m "feat(observability): add grafana and alertmanager vault vars"
```

---

## Task 2: Create the observability Docker Compose file

**Files:**
- Create: `ansible/files/observability/compose.yml`

**Step 1: Create directory**

```bash
mkdir -p ansible/files/observability/{loki,prometheus/rules,grafana/provisioning/{datasources,dashboards/json},syslog-ng,alertmanager}
```

**Step 2: Create `ansible/files/observability/compose.yml`**

```yaml
# Observability Stack — Unraid
# Managed by Ansible: ansible/playbooks/platform/deploy-observability.yml
# All services on observability-net (internal)
# Exposed: Grafana :3000, syslog-ng UDP/TCP :514

services:
  loki:
    image: grafana/loki:3.3.2
    container_name: loki
    restart: unless-stopped
    volumes:
      - ${OBSERVABILITY_APPDATA}/loki/config.yml:/etc/loki/config.yml:ro
      - loki-data:/loki
    command: -config.file=/etc/loki/config.yml
    networks:
      - observability-net
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:3100/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  prometheus:
    image: prom/prometheus:v2.54.1
    container_name: prometheus
    restart: unless-stopped
    volumes:
      - ${OBSERVABILITY_APPDATA}/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ${OBSERVABILITY_APPDATA}/prometheus/rules:/etc/prometheus/rules:ro
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    networks:
      - observability-net
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:9090/-/healthy"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  grafana:
    image: grafana/grafana:11.3.0
    container_name: grafana
    restart: unless-stopped
    depends_on:
      loki:
        condition: service_healthy
      prometheus:
        condition: service_healthy
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ${OBSERVABILITY_APPDATA}/grafana/provisioning:/etc/grafana/provisioning:ro
    environment:
      - TZ=America/Phoenix
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=https://grafana.klsll.com
    networks:
      - observability-net
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  syslog-ng:
    image: balabit/syslog-ng:4.8.0
    container_name: syslog-ng
    restart: unless-stopped
    ports:
      - "514:514/udp"
      - "514:514/tcp"
    volumes:
      - ${OBSERVABILITY_APPDATA}/syslog-ng/syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf:ro
    networks:
      - observability-net
    healthcheck:
      test: ["CMD", "syslog-ng-ctl", "stats"]
      interval: 30s
      timeout: 10s
      retries: 3

  alertmanager:
    image: prom/alertmanager:v0.27.0
    container_name: alertmanager
    restart: unless-stopped
    volumes:
      - ${OBSERVABILITY_APPDATA}/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager-data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    networks:
      - observability-net
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:9093/-/healthy"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  observability-net:
    driver: bridge
    name: observability-net

volumes:
  loki-data:
    name: loki-data
  prometheus-data:
    name: prometheus-data
  grafana-data:
    name: grafana-data
  alertmanager-data:
    name: alertmanager-data
```

**Step 3: Validate locally**

```bash
cd ansible/files/observability
OBSERVABILITY_APPDATA=/tmp/obs-test GRAFANA_ADMIN_PASSWORD=test docker compose config
```

Expected: Full resolved config printed with no errors.

**Step 4: Commit**

```bash
git add ansible/files/observability/compose.yml
git commit -m "feat(observability): add core stack compose file"
```

---

## Task 3: Loki configuration

**Files:**
- Create: `ansible/files/observability/loki/config.yml`

**Step 1: Create `ansible/files/observability/loki/config.yml`**

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 2160h  # 90 days

compactor:
  working_directory: /loki/compactor
  retention_enabled: true
  retention_delete_delay: 2h

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

ruler:
  alertmanager_url: http://alertmanager:9093

analytics:
  reporting_enabled: false
```

**Step 2: Commit**

```bash
git add ansible/files/observability/loki/config.yml
git commit -m "feat(observability): add Loki config (90d retention, filesystem storage)"
```

---

## Task 4: Prometheus configuration and alert rules

**Files:**
- Create: `ansible/files/observability/prometheus/prometheus.yml`
- Create: `ansible/files/observability/prometheus/rules/alerts.yml`

**Step 1: Create `ansible/files/observability/prometheus/prometheus.yml`**

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: homelab

rule_files:
  - /etc/prometheus/rules/*.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: node_exporter
    static_configs:
      - targets:
          - '192.168.20.14:9100'   # unraid-server
          - '192.168.20.100:9100'  # pve-01
          - '192.168.20.101:9100'  # pve-02
          - '192.168.20.2:9100'    # tt1
          - '192.168.20.3:9100'    # tt2
          - '192.168.20.4:9100'    # agh1
          - '192.168.20.5:9100'    # agh2
          - '192.168.20.169:9100'  # jetson.lab
          - '192.168.20.50:9100'   # spraycheese

  - job_name: cadvisor
    static_configs:
      - targets:
          - '192.168.20.14:8081'   # unraid-server
          - '192.168.20.169:8081'  # jetson.lab
          - '192.168.20.50:8081'   # spraycheese
```

**Step 2: Create `ansible/files/observability/prometheus/rules/alerts.yml`**

```yaml
groups:
  - name: homelab.rules
    rules:
      - alert: HostDown
        expr: up{job="node_exporter"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Host {{ $labels.instance }} is down"
          description: "node_exporter on {{ $labels.instance }} has been unreachable for more than 5 minutes."

      - alert: DiskSpaceCritical
        expr: (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay|squashfs"} / node_filesystem_size_bytes) * 100 < 20
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low disk space on {{ $labels.instance }}"
          description: "Filesystem {{ $labels.mountpoint }} on {{ $labels.instance }} has less than 20% free space."

      - alert: ContainerRestartLoop
        expr: rate(container_last_seen{name!=""}[10m]) > 0 and delta(container_start_time_seconds{name!=""}[10m]) > 3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Container {{ $labels.name }} is restarting frequently"
          description: "Container {{ $labels.name }} on {{ $labels.instance }} has restarted more than 3 times in 10 minutes."
```

**Step 3: Commit**

```bash
git add ansible/files/observability/prometheus/
git commit -m "feat(observability): add Prometheus config and alert rules"
```

---

## Task 5: syslog-ng configuration

**Files:**
- Create: `ansible/files/observability/syslog-ng/syslog-ng.conf`

**Step 1: Create `ansible/files/observability/syslog-ng/syslog-ng.conf`**

```
@version: 4.8
@include "scl.conf"

options {
  keep_hostname(yes);
  use_dns(no);
  time_reopen(10);
};

# Accept syslog over UDP and TCP (RFC3164 + RFC5424)
source s_network {
  syslog(
    transport("udp")
    port(514)
    flags(no-parse)
  );
  syslog(
    transport("tcp")
    port(514)
    flags(no-parse)
  );
  network(
    transport("udp")
    port(514)
  );
  network(
    transport("tcp")
    port(514)
  );
};

# Forward to Loki via HTTP
destination d_loki {
  http(
    url("http://loki:3100/loki/api/v1/push")
    method("POST")
    headers("Content-Type: application/json")
    body('{"streams":[{"stream":{"job":"syslog","host":"${HOST}","facility":"${FACILITY}","severity":"${LEVEL}","program":"${PROGRAM}"},"values":[["${UNIXTIME}000000000","${MSG}"]]}]}')
    timeout(10)
    retries(3)
  );
};

log {
  source(s_network);
  destination(d_loki);
};
```

**Step 2: Commit**

```bash
git add ansible/files/observability/syslog-ng/syslog-ng.conf
git commit -m "feat(observability): add syslog-ng config (UDP/TCP 514 → Loki)"
```

---

## Task 6: Alertmanager configuration

**Files:**
- Create: `ansible/roles/observability/templates/alertmanager.yml.j2`

Note: alertmanager.yml contains the Slack webhook secret so it must be templated (not a static file).

**Step 1: Create directory**

```bash
mkdir -p ansible/roles/observability/templates
```

**Step 2: Create `ansible/roles/observability/templates/alertmanager.yml.j2`**

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'instance']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: slack

receivers:
  - name: slack
    slack_configs:
      - api_url: '{{ vault_alertmanager_slack_webhook_url }}'
        channel: '#homelab-alerts'
        send_resolved: true
        title: '{{ "{{" }} .GroupLabels.alertname {{ "}}" }}'
        text: '{{ "{{" }} range .Alerts {{ "}}" }}{{ "{{" }} .Annotations.description {{ "}}" }}{{ "{{" }} end {{ "}}" }}'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['instance']
```

**Step 3: Commit**

```bash
git add ansible/roles/observability/templates/alertmanager.yml.j2
git commit -m "feat(observability): add Alertmanager config template with Slack routing"
```

---

## Task 7: Grafana provisioning configs

**Files:**
- Create: `ansible/files/observability/grafana/provisioning/datasources/datasources.yml`
- Create: `ansible/files/observability/grafana/provisioning/dashboards/dashboards.yml`

**Step 1: Create `ansible/files/observability/grafana/provisioning/datasources/datasources.yml`**

```yaml
apiVersion: 1

datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    isDefault: false
    jsonData:
      maxLines: 1000

  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      timeInterval: 15s
```

**Step 2: Create `ansible/files/observability/grafana/provisioning/dashboards/dashboards.yml`**

```yaml
apiVersion: 1

providers:
  - name: homelab
    folder: Homelab
    type: file
    disableDeletion: false
    updateIntervalSeconds: 60
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards/json
```

**Step 3: Create placeholder dashboard directory**

```bash
touch ansible/files/observability/grafana/provisioning/dashboards/json/.gitkeep
```

Note: Full dashboard JSON files (node metrics, container metrics, log explorer, DNS logs) are beyond the scope of this task. Grafana will start with an empty "Homelab" folder. Dashboards can be created in the UI and exported as JSON to this path later. Track as issue #65.

**Step 4: Commit**

```bash
git add ansible/files/observability/grafana/
git commit -m "feat(observability): add Grafana provisioning (Loki + Prometheus datasources)"
```

---

## Task 8: Observability Ansible role and playbook

**Files:**
- Create: `ansible/roles/observability/defaults/main.yml`
- Create: `ansible/roles/observability/tasks/main.yml`
- Create: `ansible/roles/observability/templates/observability.env.j2`
- Create: `ansible/playbooks/platform/deploy-observability.yml`

**Step 1: Create `ansible/roles/observability/defaults/main.yml`**

```yaml
---
observability_compose_dir: /mnt/user/appdata/observability
observability_appdata_dir: /mnt/user/appdata/observability/config
observability_port_grafana: 3000
observability_port_syslog_udp: 514
observability_port_syslog_tcp: 514
```

**Step 2: Create `ansible/roles/observability/templates/observability.env.j2`**

```
OBSERVABILITY_APPDATA={{ observability_appdata_dir }}
GRAFANA_ADMIN_PASSWORD={{ vault_grafana_admin_password }}
```

**Step 3: Create `ansible/roles/observability/tasks/main.yml`**

```yaml
---
# Deploy observability stack — all tasks use raw since Unraid lacks Python

- name: Create observability directories
  ansible.builtin.raw: |
    mkdir -p {{ observability_appdata_dir }}/loki
    mkdir -p {{ observability_appdata_dir }}/prometheus/rules
    mkdir -p {{ observability_appdata_dir }}/grafana/provisioning/datasources
    mkdir -p {{ observability_appdata_dir }}/grafana/provisioning/dashboards/json
    mkdir -p {{ observability_appdata_dir }}/syslog-ng
    mkdir -p {{ observability_appdata_dir }}/alertmanager
    mkdir -p {{ observability_compose_dir }}
  changed_when: false

- name: Copy compose file
  ansible.builtin.raw: |
    cat > {{ observability_compose_dir }}/compose.yml << 'EOFCOMPOSE'
    {{ lookup('file', role_path + '/../../../files/observability/compose.yml') }}
    EOFCOMPOSE
  changed_when: true

- name: Copy Loki config
  ansible.builtin.raw: |
    cat > {{ observability_appdata_dir }}/loki/config.yml << 'EOFCONF'
    {{ lookup('file', role_path + '/../../../files/observability/loki/config.yml') }}
    EOFCONF
  changed_when: true

- name: Copy Prometheus config
  ansible.builtin.raw: |
    cat > {{ observability_appdata_dir }}/prometheus/prometheus.yml << 'EOFCONF'
    {{ lookup('file', role_path + '/../../../files/observability/prometheus/prometheus.yml') }}
    EOFCONF
  changed_when: true

- name: Copy Prometheus alert rules
  ansible.builtin.raw: |
    cat > {{ observability_appdata_dir }}/prometheus/rules/alerts.yml << 'EOFCONF'
    {{ lookup('file', role_path + '/../../../files/observability/prometheus/rules/alerts.yml') }}
    EOFCONF
  changed_when: true

- name: Copy syslog-ng config
  ansible.builtin.raw: |
    cat > {{ observability_appdata_dir }}/syslog-ng/syslog-ng.conf << 'EOFCONF'
    {{ lookup('file', role_path + '/../../../files/observability/syslog-ng/syslog-ng.conf') }}
    EOFCONF
  changed_when: true

- name: Generate Alertmanager config
  ansible.builtin.set_fact:
    _alertmanager_config: "{{ lookup('template', role_path + '/templates/alertmanager.yml.j2') }}"

- name: Write Alertmanager config (no_log to protect webhook URL)
  ansible.builtin.raw: |
    cat > {{ observability_appdata_dir }}/alertmanager/alertmanager.yml << 'EOFCONF'
    {{ _alertmanager_config }}
    EOFCONF
    chmod 600 {{ observability_appdata_dir }}/alertmanager/alertmanager.yml
  changed_when: true
  no_log: true

- name: Copy Grafana datasources provisioning
  ansible.builtin.raw: |
    cat > {{ observability_appdata_dir }}/grafana/provisioning/datasources/datasources.yml << 'EOFCONF'
    {{ lookup('file', role_path + '/../../../files/observability/grafana/provisioning/datasources/datasources.yml') }}
    EOFCONF
  changed_when: true

- name: Copy Grafana dashboards provisioning
  ansible.builtin.raw: |
    cat > {{ observability_appdata_dir }}/grafana/provisioning/dashboards/dashboards.yml << 'EOFCONF'
    {{ lookup('file', role_path + '/../../../files/observability/grafana/provisioning/dashboards/dashboards.yml') }}
    EOFCONF
  changed_when: true

- name: Generate observability.env
  ansible.builtin.set_fact:
    _observability_env: "{{ lookup('template', role_path + '/templates/observability.env.j2') }}"

- name: Write observability.env (no_log to protect secrets)
  ansible.builtin.raw: |
    cat > {{ observability_compose_dir }}/observability.env << 'EOFENV'
    {{ _observability_env }}
    EOFENV
    chmod 600 {{ observability_compose_dir }}/observability.env
  changed_when: true
  no_log: true

- name: Pull observability images
  ansible.builtin.raw: |
    cd {{ observability_compose_dir }} && docker compose --env-file observability.env pull
  changed_when: true

- name: Deploy observability stack
  ansible.builtin.raw: |
    cd {{ observability_compose_dir }} && docker compose --env-file observability.env up -d
  changed_when: true

- name: Wait for Grafana to be healthy (up to 90s)
  ansible.builtin.raw: |
    for i in $(seq 1 18); do
      if curl -sf http://localhost:{{ observability_port_grafana }}/api/health > /dev/null 2>&1; then
        echo "healthy"; exit 0
      fi
      sleep 5
    done
    echo "timeout waiting for grafana" >&2; exit 1
  changed_when: false

- name: Show container status
  ansible.builtin.raw: |
    docker ps --filter name=loki --filter name=prometheus --filter name=grafana \
      --filter name=syslog-ng --filter name=alertmanager \
      --format "table {{.Names}}\t{{.Status}}"
  register: obs_status
  changed_when: false

- name: Display container status
  ansible.builtin.debug:
    msg: "{{ obs_status.stdout_lines | default([]) }}"
```

**Step 4: Create `ansible/playbooks/platform/deploy-observability.yml`**

```yaml
---
- name: Deploy observability stack on Unraid
  hosts: unraid
  gather_facts: false
  vars_files:
    - "{{ playbook_dir }}/../../group_vars/all/vault.yml"
  roles:
    - observability
```

**Step 5: Syntax check**

```bash
cd ansible
ansible-playbook playbooks/platform/deploy-observability.yml --syntax-check
```

Expected: `playbook: playbooks/platform/deploy-observability.yml` with no errors.

**Step 6: Dry run**

```bash
ansible-playbook playbooks/platform/deploy-observability.yml \
  --check --diff --limit unraid-server \
  --vault-password-file ~/.vault-pass
```

Expected: Tasks show as changed (raw tasks always show changed in check mode). No failures.

**Step 7: Commit**

```bash
git add ansible/roles/observability/ ansible/playbooks/platform/deploy-observability.yml
git commit -m "feat(observability): add observability Ansible role and playbook"
```

---

## Task 9: Deploy core stack to Unraid

**Step 1: Apply playbook**

```bash
cd ansible
ansible-playbook playbooks/platform/deploy-observability.yml \
  --diff --limit unraid-server \
  --vault-password-file ~/.vault-pass -v
```

Expected: All tasks complete green/yellow (changed). Final output shows 5 containers in `Up` status.

**Step 2: Verify all containers healthy**

```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 \
  "docker ps --filter name=loki --filter name=prometheus --filter name=grafana \
   --filter name=syslog-ng --filter name=alertmanager \
   --format 'table {{.Names}}\t{{.Status}}'"
```

Expected: All 5 containers show `Up` and `(healthy)`.

**Step 3: Verify Grafana UI**

```bash
curl -sf http://192.168.20.14:3000/api/health | python3 -m json.tool
```

Expected: `{"database": "ok"}` (or similar healthy response).

**Step 4: Verify Loki ready**

```bash
curl -sf http://192.168.20.14:3100/ready
```

Expected: `ready`

**Step 5: Verify Prometheus ready**

```bash
curl -sf http://192.168.20.14:9090/-/healthy
```

Expected: `Prometheus Server is Healthy.`

**Step 6: Verify idempotence**

```bash
ansible-playbook playbooks/platform/deploy-observability.yml \
  --check --diff --limit unraid-server \
  --vault-password-file ~/.vault-pass
```

Expected: `changed=0` (note: raw tasks on Unraid report `changed` even in check mode — this is expected. The key check is that no task exits with an error.)

---

## Task 10: node_exporter Ansible role

**Files:**
- Create: `ansible/roles/node_exporter/defaults/main.yml`
- Create: `ansible/roles/node_exporter/tasks/main.yml`

**Step 1: Create `ansible/roles/node_exporter/defaults/main.yml`**

```yaml
---
node_exporter_version: "v1.8.2"
node_exporter_port: 9100
node_exporter_compose_dir: /opt/node_exporter
```

**Step 2: Create `ansible/roles/node_exporter/tasks/main.yml`**

```yaml
---
# node_exporter — runs on all homelab hosts
# Uses raw throughout for Unraid compatibility

- name: Create node_exporter compose dir
  ansible.builtin.raw: |
    mkdir -p {{ node_exporter_compose_dir }}
  changed_when: false

- name: Write node_exporter compose file
  ansible.builtin.raw: |
    cat > {{ node_exporter_compose_dir }}/compose.yml << 'EOFCOMPOSE'
    services:
      node_exporter:
        image: prom/node-exporter:{{ node_exporter_version }}
        container_name: node_exporter
        restart: unless-stopped
        pid: host
        ports:
          - "{{ node_exporter_port }}:9100"
        volumes:
          - /proc:/host/proc:ro
          - /sys:/host/sys:ro
          - /:/rootfs:ro
        command:
          - '--path.procfs=/host/proc'
          - '--path.sysfs=/host/sys'
          - '--path.rootfs=/rootfs'
          - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
        network_mode: host
    EOFCOMPOSE
  changed_when: true

- name: Pull node_exporter image
  ansible.builtin.raw: |
    cd {{ node_exporter_compose_dir }} && docker compose pull
  changed_when: true

- name: Deploy node_exporter
  ansible.builtin.raw: |
    cd {{ node_exporter_compose_dir }} && docker compose up -d
  changed_when: true

- name: Verify node_exporter responds
  ansible.builtin.raw: |
    for i in $(seq 1 6); do
      if curl -sf http://localhost:{{ node_exporter_port }}/metrics > /dev/null 2>&1; then
        echo "healthy"; exit 0
      fi
      sleep 5
    done
    echo "timeout waiting for node_exporter" >&2; exit 1
  changed_when: false
```

**Step 3: Commit**

```bash
git add ansible/roles/node_exporter/
git commit -m "feat(observability): add node_exporter Ansible role"
```

---

## Task 11: cAdvisor Ansible role

**Files:**
- Create: `ansible/roles/cadvisor/defaults/main.yml`
- Create: `ansible/roles/cadvisor/tasks/main.yml`

**Step 1: Create `ansible/roles/cadvisor/defaults/main.yml`**

```yaml
---
cadvisor_version: "v0.49.1"
cadvisor_port: 8081
cadvisor_compose_dir: /opt/cadvisor
```

**Step 2: Create `ansible/roles/cadvisor/tasks/main.yml`**

```yaml
---
# cAdvisor — runs on Docker hosts only (Unraid, Jetson, spraycheese)
# Uses raw throughout for Unraid compatibility

- name: Create cAdvisor compose dir
  ansible.builtin.raw: |
    mkdir -p {{ cadvisor_compose_dir }}
  changed_when: false

- name: Write cAdvisor compose file
  ansible.builtin.raw: |
    cat > {{ cadvisor_compose_dir }}/compose.yml << 'EOFCOMPOSE'
    services:
      cadvisor:
        image: gcr.io/cadvisor/cadvisor:{{ cadvisor_version }}
        container_name: cadvisor
        restart: unless-stopped
        privileged: true
        ports:
          - "{{ cadvisor_port }}:8080"
        volumes:
          - /:/rootfs:ro
          - /var/run:/var/run:ro
          - /sys:/sys:ro
          - /var/lib/docker/:/var/lib/docker:ro
          - /dev/disk/:/dev/disk:ro
        devices:
          - /dev/kmsg
    EOFCOMPOSE
  changed_when: true

- name: Pull cAdvisor image
  ansible.builtin.raw: |
    cd {{ cadvisor_compose_dir }} && docker compose pull
  changed_when: true

- name: Deploy cAdvisor
  ansible.builtin.raw: |
    cd {{ cadvisor_compose_dir }} && docker compose up -d
  changed_when: true

- name: Verify cAdvisor responds
  ansible.builtin.raw: |
    for i in $(seq 1 6); do
      if curl -sf http://localhost:{{ cadvisor_port }}/healthz > /dev/null 2>&1; then
        echo "healthy"; exit 0
      fi
      sleep 5
    done
    echo "timeout waiting for cadvisor" >&2; exit 1
  changed_when: false
```

**Step 3: Commit**

```bash
git add ansible/roles/cadvisor/
git commit -m "feat(observability): add cAdvisor Ansible role"
```

---

## Task 12: Promtail Ansible role

**Files:**
- Create: `ansible/roles/promtail/defaults/main.yml`
- Create: `ansible/roles/promtail/tasks/main.yml`
- Create: `ansible/roles/promtail/templates/promtail-config.yml.j2`

**Step 1: Create `ansible/roles/promtail/defaults/main.yml`**

```yaml
---
promtail_version: "3.3.2"
promtail_compose_dir: /opt/promtail
loki_url: "http://192.168.20.14:3100"

# Set to true on hosts with systemd journal
promtail_scrape_journal: true

# Set to true on Unraid (no journal, Docker socket only)
promtail_unraid_mode: false

# DNS query log paths (set per host group in group_vars)
promtail_adguard_log_path: ""
promtail_technitium_log_path: ""
```

**Step 2: Create `ansible/roles/promtail/templates/promtail-config.yml.j2`**

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: {{ loki_url }}/loki/api/v1/push

scrape_configs:

  # Docker container logs (all Docker hosts)
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 15s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        target_label: container
      - source_labels: ['__meta_docker_container_id']
        target_label: container_id
      - replacement: {{ inventory_hostname }}
        target_label: host
      - replacement: docker
        target_label: job

{% if not promtail_unraid_mode and promtail_scrape_journal %}
  # Systemd journal (all Linux hosts except Unraid)
  - job_name: journal
    journal:
      max_age: 12h
      labels:
        job: journal
        host: {{ inventory_hostname }}
    relabel_configs:
      - source_labels: ['__journal__systemd_unit']
        target_label: unit
{% endif %}

{% if promtail_adguard_log_path %}
  # AdGuard Home query logs
  - job_name: adguard-queries
    static_configs:
      - targets:
          - localhost
        labels:
          job: adguard
          host: {{ inventory_hostname }}
          __path__: {{ promtail_adguard_log_path }}
{% endif %}

{% if promtail_technitium_log_path %}
  # Technitium DNS query logs
  - job_name: technitium-queries
    static_configs:
      - targets:
          - localhost
        labels:
          job: technitium
          host: {{ inventory_hostname }}
          __path__: {{ promtail_technitium_log_path }}
{% endif %}
```

**Step 3: Create `ansible/roles/promtail/tasks/main.yml`**

```yaml
---
# Promtail — runs on all homelab hosts

- name: Create Promtail compose dir
  ansible.builtin.raw: |
    mkdir -p {{ promtail_compose_dir }}
  changed_when: false

- name: Generate Promtail config
  ansible.builtin.set_fact:
    _promtail_config: "{{ lookup('template', role_path + '/templates/promtail-config.yml.j2') }}"

- name: Write Promtail config
  ansible.builtin.raw: |
    cat > {{ promtail_compose_dir }}/promtail-config.yml << 'EOFCONF'
    {{ _promtail_config }}
    EOFCONF
  changed_when: true

- name: Write Promtail compose file
  ansible.builtin.raw: |
    cat > {{ promtail_compose_dir }}/compose.yml << 'EOFCOMPOSE'
    services:
      promtail:
        image: grafana/promtail:{{ promtail_version }}
        container_name: promtail
        restart: unless-stopped
        volumes:
          - {{ promtail_compose_dir }}/promtail-config.yml:/etc/promtail/config.yml:ro
          - /var/run/docker.sock:/var/run/docker.sock:ro
          - /var/log/journal:/var/log/journal:ro
          - /run/log/journal:/run/log/journal:ro
          - /etc/machine-id:/etc/machine-id:ro
        command: -config.file=/etc/promtail/config.yml
        network_mode: host
    EOFCOMPOSE
  changed_when: true

- name: Pull Promtail image
  ansible.builtin.raw: |
    cd {{ promtail_compose_dir }} && docker compose pull
  changed_when: true

- name: Deploy Promtail
  ansible.builtin.raw: |
    cd {{ promtail_compose_dir }} && docker compose up -d
  changed_when: true

- name: Verify Promtail responds
  ansible.builtin.raw: |
    for i in $(seq 1 6); do
      if curl -sf http://localhost:9080/ready > /dev/null 2>&1; then
        echo "healthy"; exit 0
      fi
      sleep 5
    done
    echo "timeout waiting for promtail" >&2; exit 1
  changed_when: false
```

**Step 4: Set group_vars for Unraid (no journal) and DNS hosts (query logs)**

Create `ansible/group_vars/unraid.yml` (or add to existing):

```yaml
promtail_unraid_mode: true
promtail_scrape_journal: false
```

Create `ansible/group_vars/agh.yml`:

```yaml
promtail_adguard_log_path: "/opt/adguardhome/data/querylog.json"
```

Create `ansible/group_vars/tt.yml`:

```yaml
# Confirm the correct path on tt1 before deploying:
# ls /opt/technitium/data/logs/ or similar
promtail_technitium_log_path: ""  # TODO: confirm path at deploy time
```

**Step 5: Commit**

```bash
git add ansible/roles/promtail/ ansible/group_vars/
git commit -m "feat(observability): add Promtail role with per-host journal/DNS log config"
```

---

## Task 13: Agents deployment playbook

**Files:**
- Create: `ansible/playbooks/platform/deploy-observability-agents.yml`

**Step 1: Create `ansible/playbooks/platform/deploy-observability-agents.yml`**

```yaml
---
# Deploy observability agents to all homelab hosts
# node_exporter + promtail: all hosts
# cadvisor: Docker hosts only (unraid, edge_devices, windows_gpu)

- name: Deploy node_exporter to all hosts
  hosts: unraid:pve:tt:agh:edge_devices:windows_gpu
  gather_facts: false
  roles:
    - node_exporter

- name: Deploy Promtail to all hosts
  hosts: unraid:pve:tt:agh:edge_devices:windows_gpu
  gather_facts: false
  vars_files:
    - "{{ playbook_dir }}/../../group_vars/all/vault.yml"
  roles:
    - promtail

- name: Deploy cAdvisor to Docker hosts
  hosts: unraid:edge_devices:windows_gpu
  gather_facts: false
  roles:
    - cadvisor
```

**Step 2: Syntax check**

```bash
cd ansible
ansible-playbook playbooks/platform/deploy-observability-agents.yml --syntax-check
```

Expected: No errors.

**Step 3: Deploy agents — start with one host to validate**

```bash
# Test on Unraid first
ansible-playbook playbooks/platform/deploy-observability-agents.yml \
  --diff --limit unraid-server \
  --vault-password-file ~/.vault-pass -v
```

Expected: node_exporter, promtail, and cadvisor containers Up on Unraid.

**Step 4: Verify Unraid agents**

```bash
# node_exporter
curl -sf http://192.168.20.14:9100/metrics | head -5

# promtail
curl -sf http://192.168.20.14:9080/ready

# cadvisor
curl -sf http://192.168.20.14:8081/healthz
```

**Step 5: Verify Prometheus can scrape Unraid agents**

```bash
curl -sf "http://192.168.20.14:9090/api/v1/targets" | \
  python3 -c "import sys,json; targets=json.load(sys.stdin)['data']['activeTargets']; \
  [print(t['labels']['instance'], t['health']) for t in targets]"
```

Expected: `192.168.20.14:9100 up` and `192.168.20.14:8081 up`.

**Step 6: Deploy to remaining hosts**

```bash
ansible-playbook playbooks/platform/deploy-observability-agents.yml \
  --diff --vault-password-file ~/.vault-pass -v
```

**Step 7: Commit**

```bash
git add ansible/playbooks/platform/deploy-observability-agents.yml
git commit -m "feat(observability): add agents deployment playbook (all hosts)"
```

---

## Task 14: NPM proxy for Grafana

**Files:**
- Create: `ansible/files/npm/services/grafana.yml`
- Create: `ansible/playbooks/services/update-grafana-proxy.yml`

**Step 1: Create `ansible/files/npm/services/grafana.yml`**

```yaml
proxy_hosts:
  - name: grafana
    domains:
      - grafana.klsll.com
    forward_host: 192.168.20.14
    forward_port: 3000
    scheme: http
    websocket: true
    certificate: klsll-wildcard
    ssl_forced: true
    hsts: true
    http2: true

dns_records:
  - name: grafana.klsll.com
    type: A
    value: 192.168.20.50  # Platform VM IP — confirm this matches your NPM host
    ttl: 3600
```

Note: Confirm the DNS A record value matches your NPM/Platform VM IP before running. Check the existing `ironclaw.yml` for the pattern.

**Step 2: Create `ansible/playbooks/services/update-grafana-proxy.yml`**

```yaml
---
- name: Sync Grafana proxy and DNS into Nginx Proxy Manager
  hosts: unraid
  gather_facts: false
  vars:
    npm_proxy_config_paths:
      - "{{ playbook_dir }}/../../files/npm/services/certificates.yml"
      - "{{ playbook_dir }}/../../files/npm/services/grafana.yml"
    npm_manage_proxies: true
    npm_manage_dns: true
  roles:
    - npm
```

**Step 3: Syntax check**

```bash
cd ansible
ansible-playbook playbooks/services/update-grafana-proxy.yml --syntax-check
```

**Step 4: Apply**

```bash
ansible-playbook playbooks/services/update-grafana-proxy.yml \
  --diff --limit unraid-server \
  --vault-password-file ~/.vault-pass -v
```

**Step 5: Verify**

```bash
curl -sf https://grafana.klsll.com/api/health | python3 -m json.tool
```

Expected: `{"database": "ok"}` over HTTPS.

**Step 6: Commit**

```bash
git add ansible/files/npm/services/grafana.yml \
        ansible/playbooks/services/update-grafana-proxy.yml
git commit -m "feat(observability): add NPM proxy playbook for grafana.klsll.com"
```

---

## Final Verification Checklist

```bash
# All 5 core containers healthy on Unraid
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 \
  "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'loki|prometheus|grafana|syslog-ng|alertmanager'"

# Grafana UI accessible
curl -sf https://grafana.klsll.com/api/health

# Prometheus scraping all targets
curl -sf "http://192.168.20.14:9090/api/v1/targets" | \
  python3 -c "import sys,json; [print(t['labels']['instance'], t['health']) \
  for t in json.load(sys.stdin)['data']['activeTargets']]"

# Loki receiving logs (check after agents are running ~5 min)
curl -sf "http://192.168.20.14:3100/loki/api/v1/labels" | python3 -m json.tool

# Send a test syslog message
logger -n 192.168.20.14 -P 514 --tcp "Test syslog message from $(hostname)"
```

---

## Known Gaps (Tracked as Issues)

- **#64**: Technitium query log path must be confirmed before deploying to tt1/tt2
- **#65**: Dashboard JSON files to be created in Grafana UI and exported to `ansible/files/observability/grafana/provisioning/dashboards/json/`
- **#68**: Windows Event Log ingestion on spraycheese (requires Windows-native agent, deferred)
