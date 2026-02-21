# Docker Compose Stacks

This directory contains Docker Compose stacks for homelab infrastructure.

## Available Stacks

### Platform (`platform/`)
Core infrastructure services for the Platform VM:
- **Nginx Proxy Manager** - Reverse proxy with Let's Encrypt
- **Uptime Kuma** - Status monitoring
- **Homepage** - Landing page for homelab links/widgets

### GPU Worker (`gpu-worker/`)
AI/ML workloads for WSL2 GPU workers:
- **Ollama** - LLM inference server
- **Open WebUI** - Chat interface

Includes `compose.cpu.yml` override for CPU-only operation.

### Monitoring (`monitoring/`)
Observability stack:
- **Prometheus** - Metrics collection
- **Grafana** - Dashboards
- **Node Exporter** - Host metrics
- **cAdvisor** - Container metrics

## Deployment

```bash
cd stacks/<stack-name>
cp .env.example .env
nano .env  # Fill in required values
docker compose config  # Validate
docker compose up -d
```

## Environment Variables

Each stack has a `.env.example` template. **Never commit actual `.env` files.**

Required variables are marked with `:?` in compose files and will error if missing.

### Generating Secure Passwords

```bash
# Generate 32-character password
openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32

# Generate hex secret key
openssl rand -hex 32
```

## Stack Files

| File | Purpose |
|------|---------|
| `compose.yml` | Main compose definition |
| `.env.example` | Environment variable template |
| `compose.cpu.yml` | CPU-only override (gpu-worker) |
| `prometheus.yml` | Prometheus config (monitoring) |
| `grafana/` | Grafana provisioning (monitoring) |

## Validation

```bash
# Validate compose file syntax
docker compose config

# Dry run (shows what would be created)
docker compose config --services

# Check for required env vars
docker compose config 2>&1 | grep -i error
```

## Updating Stacks

```bash
git pull
docker compose pull
docker compose up -d
```

## Volume Management

Stacks use named volumes for persistence. See `scripts/backup-volumes.sh` for backup/restore.

```bash
# List volumes
docker volume ls | grep -E "(npm|technitium|kuma|prometheus|grafana|ollama)"

# Backup all volumes
../scripts/backup-volumes.sh

# Restore specific volume
../scripts/backup-volumes.sh --restore backup.tar.gz volume-name
```
