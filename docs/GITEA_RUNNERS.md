# Gitea Runners Deployment Guide

This guide covers deploying and managing Gitea Runners (act-based CI/CD workers) for your homelab infrastructure.

## Overview

Gitea Runners are self-hosted agents that execute GitHub Actions-compatible workflows from Gitea Actions. They enable:

- **Local CI/CD**: Run workflows without external dependencies
- **Custom Labels**: Target specific hardware (e.g., `gpu`, `build-optimized`)
- **Container Builds**: Docker-in-Docker support for building and pushing images
- **Cost Control**: No external SaaS billing for CI runs

The observability smoke workflow in `.gitea/workflows/observability-smoke.yml` expects a self-hosted runner with Docker access and network reachability to the Unraid observability stack, because it validates live Grafana/Loki/Prometheus/Alertmanager endpoints in addition to static config.

## Prerequisites

1. **Gitea Instance**: Must be deployed and accessible at `https://gitea.klsll.com`
   - Verify: `curl -I https://gitea.klsll.com`

2. **Ansible Environment**: Run playbooks from the `ansible/` directory
   - SSH key: `~/.ssh/id_ed25519_homelab`
   - Python 3.11+ on target host

3. **Docker**: Latest Docker and Docker Compose on target host
   - Tested with Docker 24.0+

## Getting Started

### Step 1: Generate Runner Registration Token

1. **Access Gitea Admin Panel**:
   - Navigate to `https://gitea.klsll.com/admin/runners`
   - Log in as admin user (e.g., HavartiBard)

2. **Create New Runner Token**:
   - Click "Create New Runner"
   - Copy the registration token (valid for 1 hour)
   - This token is used only during registration

### Step 2: Deploy Single Runner

Deploy a runner to Unraid with default configuration:

```bash
cd ansible

# Set runner token (must be obtained above)
export GITEA_RUNNER_TOKEN="your_token_here_xxxx..."

# Syntax check
ansible-playbook playbooks/platform/deploy-gitea-runners.yml --syntax-check

# Dry run
ansible-playbook playbooks/platform/deploy-gitea-runners.yml --check --diff

# Deploy
ansible-playbook playbooks/platform/deploy-gitea-runners.yml --diff -v
```

The playbook will:
- Create `/mnt/user/appdata/gitea-runner/` on Unraid
- Build and start 2 runner containers
- Register runners with your Gitea instance
- Display deployment info and instructions

### Step 3: Verify Deployment

Check runners are online:

```bash
# Via Gitea web UI
# Visit: https://gitea.klsll.com/admin/runners
# Should show 2 runners in "online" state

# Via CLI (SSH to Unraid)
ssh root@192.168.20.14
cd /mnt/user/appdata/gitea-runner/stacks
docker compose ps
docker compose logs -f gitea-runner-1
```

## Configuration

### Runner Count (Scaling)

Deploy 4 concurrent runners instead of 2:

```bash
ansible-playbook playbooks/platform/deploy-gitea-runners.yml \
  -e gitea_runner_count=4
```

- **1-2 runners**: For light workflows (lint, test on small repos)
- **3-5 runners**: Typical small team (~5 repos, moderate activity)
- **6-10 runners**: Multiple projects or heavy builds
- **10+ runners**: Consider dedicated VM or multi-host deployment

### Resource Limits

Adjust memory/CPU per runner (defaults: 4GB mem, 2 CPU):

```bash
ansible-playbook playbooks/platform/deploy-gitea-runners.yml \
  -e gitea_runner_count=3 \
  -e gitea_runner_memory_limit=8g \
  -e gitea_runner_cpus_limit=4
```

### Custom Labels

Add labels to target specific runners in workflows:

```bash
ansible-playbook playbooks/platform/deploy-gitea-runners.yml \
  -e gitea_runner_labels='["ubuntu-latest","linux","docker","gpu","build"]'
```

Then use in workflows:

```yaml
jobs:
  build:
    runs-on: build  # Run on runners with "build" label
```

### Registry Credentials

For pushing images to `registry.klsll.com`:

```bash
# Store credentials in 1Password first:
# 1. Create item: "Gitea Registry Credentials"
# 2. Add field: "password" with auth token

export REGISTRY_USERNAME=myuser
export REGISTRY_PASSWORD=$(op read "op://AI Wedge/Gitea Registry Credentials/password")

ansible-playbook playbooks/platform/deploy-gitea-runners.yml
```

Credentials are mounted to `/etc/docker/config.json` in runner containers.

## Usage Examples

### Example 1: Simple Test Workflow

Create `.gitea/workflows/test.yml`:

```yaml
name: Test

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          echo "Running tests..."
          # npm test
          # pytest
```

### Example 2: Build and Push Docker Image

```yaml
name: Build Image

on:
  push:
    tags: ["v*"]

jobs:
  build:
    runs-on: docker
    steps:
      - uses: actions/checkout@v4
      - name: Build and push
        run: |
          docker build -t registry.klsll.com/myapp:latest .
          docker push registry.klsll.com/myapp:latest
```

### Example 3: Multi-Runner Matrix Build

```yaml
name: Matrix Build

jobs:
  build:
    runs-on: [ubuntu-latest]
    strategy:
      matrix:
        node-version: [18, 20]
        python-version: [3.11, 3.12]
    steps:
      - uses: actions/checkout@v4
      - name: Run with Node {{ matrix.node-version }}
        run: node --version
```

## Troubleshooting

### Runners Show "Offline"

1. **Check registration token validity** (tokens expire after 1 hour)
2. **Verify network connectivity**:
   ```bash
   docker exec gitea-runner-1 curl -I https://gitea.klsll.com
   ```
3. **View registration logs**:
   ```bash
   docker logs gitea-runner-1 2>&1 | grep -i "register\|error"
   ```
4. **Re-register** with new token if necessary

### Jobs Fail to Start

1. **Check runner logs**:
   ```bash
   docker logs gitea-runner-1
   ```

2. **Verify Docker socket access**:
   ```bash
   docker exec gitea-runner-1 ls -la /var/run/docker.sock
   ```

3. **Check runner config**:
   ```bash
   docker exec gitea-runner-1 cat /data/config.yml
   ```

### Memory/Resource Issues

- **Symptom**: Jobs killed unexpectedly or slow execution
- **Solution**: Increase resource limits or reduce concurrent runners

```bash
# Reduce to 1 runner with higher resources
ansible-playbook playbooks/platform/deploy-gitea-runners.yml \
  -e gitea_runner_count=1 \
  -e gitea_runner_memory_limit=8g \
  -e gitea_runner_cpus_limit=4
```

### Docker Build Failures in Workflow

- **Symptom**: `docker: command not found` in workflow
- **Solution**: This is expected (no docker client in runner by default)
- **Workaround**: Use Docker socket binding (already configured)

```yaml
# Workflows run with Docker socket available
- name: Build image
  run: |
    docker build -t myapp:latest .
    docker push registry.klsll.com/myapp:latest
```

## Scaling & Deployment Strategies

### Strategy 1: Single Large Runner (Unraid)

Best for: Small teams, light workloads

```bash
# Deploy 1-2 runners on Unraid
ansible-playbook playbooks/platform/deploy-gitea-runners.yml \
  -e gitea_runner_count=2
```

### Strategy 2: Dedicated VM Runner (Proxmox)

Best for: Heavy builds, isolation, multiple projects

```bash
# 1. Create Ubuntu 20.04 LXC on pve-01
# 2. Install Docker
# 3. Deploy runners
ansible-playbook playbooks/platform/deploy-gitea-runners.yml \
  --limit proxmox-runner-1 \
  -e gitea_runner_count=4
```

### Strategy 3: Multi-Host Runners

Best for: Redundancy, parallel processing, different workloads

```bash
# Deploy fast runners (tests) on Unraid
ansible-playbook playbooks/platform/deploy-gitea-runners.yml \
  --limit unraid \
  -e gitea_runner_count=3 \
  -e gitea_runner_labels='["ubuntu-latest","linux","test"]'

# Deploy slow runners (builds) on dedicated VM
ansible-playbook playbooks/platform/deploy-gitea-runners.yml \
  --limit proxmox-build \
  -e gitea_runner_count=2 \
  -e gitea_runner_labels='["ubuntu-latest","linux","docker","build"]'
```

Then target specific runners in workflows:

```yaml
jobs:
  test:
    runs-on: test

  build:
    runs-on: build
```

## Maintenance

### View Logs

```bash
# SSH to Unraid
ssh root@192.168.20.14

# Tail runner logs
cd /mnt/user/appdata/gitea-runner/stacks
docker compose logs -f gitea-runner-1

# All runners
docker compose logs -f

# Show last 100 lines
docker compose logs --tail 100
```

### Update Runner Image

```bash
cd /mnt/user/appdata/gitea-runner/stacks
docker compose pull
docker compose up -d  # Redeploy with new image
```

### Restart Runners

```bash
cd /mnt/user/appdata/gitea-runner/stacks

# Single runner
docker compose restart gitea-runner-1

# All runners
docker compose restart

# Full restart (tear down and rebuild)
docker compose down && docker compose up -d
```

### Increase Runner Count at Runtime

```bash
# SSH to Unraid
cd /mnt/user/appdata/gitea-runner/stacks

# Edit docker-compose.yml or regenerate via playbook
ansible-playbook playbooks/platform/deploy-gitea-runners.yml \
  -e gitea_runner_count=5
```

## Monitoring & Metrics

### Key Metrics

- **Runner Status**: https://gitea.klsll.com/admin/runners
  - Online, Idle, Running, Offline

- **Job History**: Repository → Actions → View job runs
  - Success/failure rates
  - Execution time

- **Resource Usage** (on Unraid):
  ```bash
  docker stats gitea-runner-1 gitea-runner-2
  ```

### Log Retention

Logs are retained for {{ gitea_runner_log_retention_days }} days (configured in defaults).

Archive important logs:

```bash
docker compose logs > /backup/runner-logs-$(date +%Y%m%d).log
```

## Security Considerations

1. **Runner Token**: Treat as sensitive as passwords
   - Expires 1 hour after generation
   - Cannot be recovered; generate new token if lost

2. **Docker Socket**: Runners have full Docker access
   - Workflows can build, push, and delete images
   - Use trusted repositories only

3. **Registry Credentials**: Stored in runner container
   - Mounted from host at deployment time
   - Never committed to git

4. **Network Isolation**: Runners talk to Gitea via HTTPS
   - Verify certificate: `curl -v https://gitea.klsll.com 2>&1 | grep SSL`

## References

- **Gitea Docs**: https://docs.gitea.com/usage/actions/
- **Act Runner**: https://gitea.com/gitea/act_runner
- **GitHub Actions**: https://docs.github.com/actions (syntax is compatible)
- **Docker-in-Docker**: https://docs.docker.com/engine/security/run/#runtime-privilege-and-linux-capabilities

## Rollback

If runners need to be removed:

```bash
# SSH to Unraid
ssh root@192.168.20.14
cd /mnt/user/appdata/gitea-runner/stacks

# Stop runners
docker compose down

# Remove data
rm -rf /mnt/user/appdata/gitea-runner

# Deregister from Gitea (Admin → Runners → select runner → delete)
```

## Support

For issues:

1. Check logs: `docker compose logs -f gitea-runner-1`
2. Verify Gitea is running: `curl -I https://gitea.klsll.com`
3. Check token is valid (regenerate if needed from Admin panel)
4. Review Gitea Actions docs: https://docs.gitea.com/usage/actions/
