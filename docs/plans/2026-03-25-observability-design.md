# Observability Stack Design

**Date:** 2026-03-25
**Status:** Approved
**Branch:** feature/observability

---

## Overview

A full observability stack for the homelab covering logs, metrics, alerting, and syslog ingestion from network devices. All core services run on Unraid as a Docker Compose stack managed by Ansible. Lightweight agents are deployed to every host via Ansible roles.

---

## Stack Components

### Core Services (Unraid, Docker Compose)

| Service | Purpose | Port (LAN-exposed) |
|---------|---------|-------------------|
| Loki | Log storage and query backend | Internal only |
| Prometheus | Metrics storage and query backend | Internal only |
| Grafana | Unified visualization UI | 3000 → `grafana.klsll.com` |
| syslog-ng | Syslog receiver for network devices → Loki | 514 UDP/TCP |
| Alertmanager | Alert routing to Slack/IronClaw | Internal only |

All services share a single `observability-net` Docker network.
Grafana is proxied via NPM to `grafana.klsll.com`.
syslog-ng is the only service with a raw LAN port (required for network device syslog).

### Per-Host Agents (Ansible roles)

| Agent | Hosts | Purpose |
|-------|-------|---------|
| Promtail | All Linux hosts | Scrape Docker logs + systemd journal → Loki |
| node_exporter | All Linux hosts | Host CPU/memory/disk/network → Prometheus |
| cAdvisor | Docker hosts only | Per-container metrics → Prometheus |

**Docker hosts** (cAdvisor deployed): Unraid, spraycheese, Jetson, Platform VM
**DNS LXCs** (tt1/tt2, agh1/agh2): Promtail + node_exporter only, no cAdvisor

---

## Data Flow

```
Network devices (Unifi, router, switches)
  → syslog UDP/TCP 514 → syslog-ng (Unraid) → Loki HTTP API

Linux hosts (Unraid, Proxmox, tt1/tt2, agh1/agh2, Jetson, spraycheese)
  → Promtail → Loki HTTP API

All hosts
  → node_exporter → Prometheus scrape

Docker hosts
  → cAdvisor → Prometheus scrape

Grafana
  → Loki (log queries, LogQL)
  → Prometheus (metric queries, PromQL)
```

---

## Per-Host Configuration Notes

### Unraid
- No systemd journal — Promtail scrapes Docker socket logs only
- Hosts core observability stack (Loki, Prometheus, Grafana, syslog-ng, Alertmanager)
- Ansible uses `raw` commands (no Python)

### spraycheese (WSL2)
- Promtail scrapes Docker Desktop socket + WSL2 journal
- **Known gap:** Windows Event Logs not captured (no Windows-native agent)
- cAdvisor runs in WSL2 Docker context

### tt1/tt2 (Technitium DNS)
- Promtail scrapes Technitium query log files directly
- No cAdvisor

### agh1/agh2 (AdGuard Home)
- Promtail scrapes AdGuard query log files directly
- No cAdvisor

### Jetson (jetson.lab)
- ARM64 — all Grafana Labs images support ARM64 natively
- cAdvisor deployed (runs Ollama containers)

---

## Syslog Ingestion

syslog-ng on Unraid listens on UDP/TCP 514, parses RFC3164 and RFC5424, and forwards to Loki via HTTP with structured labels:

```
labels:
  job: syslog
  host: <source hostname>
  facility: <syslog facility>
  severity: <syslog severity>
```

Network devices to configure for syslog forwarding:
- Unifi controller / APs
- Router
- Managed switches

---

## DNS Query Log Ingestion

Promtail on the DNS hosts scrapes query log files to give visibility into DNS traffic patterns:
- **AdGuard** (`agh1`/`agh2`): `/opt/adguardhome/data/querylog.json`
- **Technitium** (`tt1`/`tt2`): Technitium log path TBD at deploy time

Use cases: top queried domains, blocked query rate, NXDOMAIN spikes, per-client traffic.

---

## Grafana Provisioning

Grafana is provisioned via config files (no manual setup required):

**Datasources (auto-provisioned):**
- Loki: `http://loki:3100`
- Prometheus: `http://prometheus:9090`

**Baseline dashboards:**
- Node metrics (CPU, memory, disk, network per host)
- Container metrics (per-container resource usage via cAdvisor)
- Log explorer (Loki datasource, label-based filtering)
- DNS query logs (AdGuard + Technitium log panels)

---

## Alertmanager

Prometheus alert rules (initial set):
- Host unreachable (node_exporter scrape failure > 5 min)
- Disk usage > 80% on any host
- Container restart loop (> 5 restarts in 10 min)

Alert routing: Alertmanager → Slack via IronClaw webhook.

---

## Retention Policy

| Store | Retention |
|-------|-----------|
| Loki | 90 days |
| Prometheus | 30 days |

Unraid has sufficient storage for these defaults. Adjust via environment variables.

---

## Deployment Approach

All managed by Ansible:

- `ansible/playbooks/platform/deploy-observability.yml` — core stack on Unraid
- `ansible/roles/promtail/` — log agent, applied to all host groups
- `ansible/roles/node_exporter/` — metrics agent, applied to all host groups
- `ansible/roles/cadvisor/` — container metrics, applied to Docker host groups
- `ansible/playbooks/services/update-grafana-proxy.yml` — NPM proxy for `grafana.klsll.com`

Compose files: `ansible/files/observability/`

---

## Known Gaps / Follow-ups

- Windows Event Log ingestion on spraycheese (requires Windows-native agent, deferred)
- Technitium query log path must be confirmed at deploy time
- Homelab network/device inventory system (separate initiative, tracked separately)
