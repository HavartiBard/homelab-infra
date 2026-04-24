# Deployment Checklist

## Pre-Deployment Verification

### Repository
- [ ] All compose files validate: `docker compose config`
- [ ] No secrets committed: `git grep -i password`
- [ ] `.env.example` files exist for all stacks
- [ ] Scripts are executable: `ls -la scripts/`

### Infrastructure
- [ ] Proxmox host accessible
- [ ] Unraid accessible with Docker enabled
- [ ] Static DHCP reservations configured
- [ ] Network connectivity between all hosts

---

## Smoke Tests

### Platform VM
```bash
# Docker running
docker ps

# NPM responding
curl http://localhost:81/api/

# Technitium DNS responding
dig @localhost google.com

# Uptime Kuma responding
curl http://localhost:3001/api/info
```

### GPU Worker (WSL2)
```bash
# Docker running in WSL2
docker ps

# NVIDIA GPU accessible
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi

# Ollama responding
curl http://localhost:11434/api/tags

# Open WebUI responding
curl http://localhost:8080/health
```

### Monitoring
```bash
# Prometheus targets healthy
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Grafana responding
curl http://localhost:3000/api/health
```

### Observability Smoke Harness
```bash
# Static config validation (Ansible-managed observability tree)
python scripts/test-observability-alerting.py static

# Live external checks
python scripts/test-observability-alerting.py live

# Full check set, including Loki/Prometheus/Alertmanager via docker exec
python scripts/test-observability-alerting.py full --docker-exec
```

---

## Failure Modes & Troubleshooting

### Container Won't Start
```bash
# Check logs
docker compose logs <service>
docker inspect <container>

# Check resources
docker system df
df -h
```

### Port Already in Use
```bash
sudo lsof -i :<port>
sudo netstat -tulpn | grep <port>
```

### DNS Not Resolving
```bash
# Check Technitium is running
docker logs technitium-dns

# Test directly
dig @localhost example.com

# Check host resolv.conf
cat /etc/resolv.conf
```

### GPU Not Detected
```bash
# Host nvidia-smi works?
nvidia-smi

# Docker NVIDIA runtime configured?
docker info | grep -i nvidia

# Restart Docker
sudo service docker restart
```

---

## Rollback Procedures

### Stack Rollback
```bash
# Stop current stack
docker compose down

# Checkout previous version
git log --oneline -5
git checkout <commit> -- stacks/<stack>/

# Redeploy
docker compose up -d
```

### Volume Restore
```bash
# List available backups
ls -la ~/backups/docker-volumes/

# Restore specific volume
./scripts/backup-volumes.sh --restore <backup.tar.gz> <volume-name>
```

### Full Platform Rollback
1. Stop all stacks on Platform VM
2. Restore volumes from backup
3. Checkout last known-good commit
4. Redeploy stacks in order: platform → monitoring

---

## Post-Deployment Verification

### Acceptance Criteria
- [ ] `docs/runbook.md` exists and is executable without missing steps
- [ ] All compose files validate with `.env` populated
- [ ] No secrets committed to git
- [ ] Platform stack deploys successfully
- [ ] Monitoring stack deploys successfully
- [ ] GPU-worker stack deploys to WSL2 successfully
- [ ] Gaming toggle works (stop/start GPU workloads)

### Security Verification
- [ ] Management interfaces not accessible from internet (test from mobile data)
- [ ] UFW enabled on all Linux hosts
- [ ] All admin passwords changed from defaults
- [ ] Credentials stored in 1Password

### Monitoring Verification
- [ ] Prometheus scraping all configured targets
- [ ] Grafana dashboards showing data
- [ ] Uptime Kuma monitors configured and green
- [ ] Alerts configured (optional)

---

## Maintenance Schedule

### Weekly
- [ ] Review Uptime Kuma alerts
- [ ] Check Grafana for anomalies
- [ ] `git pull` latest changes

### Monthly
- [ ] Update container images: `docker compose pull && docker compose up -d`
- [ ] Backup all volumes: `./scripts/backup-volumes.sh`
- [ ] Review and rotate passwords if needed
- [ ] Test restore procedure

### Quarterly
- [ ] Review firewall rules
- [ ] Update base OS: `apt update && apt upgrade`
- [ ] Clean up unused resources: `docker system prune -af`
