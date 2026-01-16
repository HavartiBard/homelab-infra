# Container Build, Test, and Deploy Process

Standard operating procedures for building, testing, and deploying containerized services in the homelab infrastructure.

## Overview

This document defines the workflow for container image development, local testing, and production deployment to Unraid. Following these rules ensures consistent, reliable deployments.

---

## Phase 1: Development & Build

### 1.1 Code Changes
- Make changes in the source repository (e.g., `~/CascadeProjects/<project-name>`)
- Update `Dockerfile` as needed
- Create/update `.dockerignore` to exclude unnecessary files from build context

### 1.2 Build Image Locally
```bash
cd ~/CascadeProjects/<project-name>
sudo docker build -t ghcr.io/havartibard/<image-name>:latest \
  --build-arg VERSION=$(git describe --tags --always) \
  --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --build-arg COMMIT=$(git rev-parse --short HEAD) \
  .
```

### 1.3 Push to GHCR
```bash
sudo docker push ghcr.io/havartibard/<image-name>:latest
```

### 1.4 Ensure Package Visibility
GHCR packages are **private by default**, even if the repository is public. Verify and set visibility:

```bash
# Check current visibility
gh api user/packages/container/<image-name> --jq '.visibility'

# If private, make public (required for Unraid to pull without auth)
# Note: This must be done via GitHub UI: Settings > Packages > Package Settings > Change visibility
```

**Alternative**: Configure GHCR authentication on Unraid (one-time setup):
```bash
ssh root@192.168.20.14 "docker login ghcr.io -u HavartiBard --password-stdin" < <(gh auth token)
```

---

## Phase 2: Local Testing (Dev VM)

### 2.1 Test Container Locally
Local testing on the dev VM is for **quick validation only**. Do NOT leave test containers running.

```bash
cd ~/CascadeProjects/homelab-infra/docker/<service-name>
sudo docker-compose up -d
```

### 2.2 Verify Functionality
```bash
# Health check
curl -s http://localhost:<port>/health | jq

# Service-specific tests
curl -s -X POST http://localhost:<port>/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}'
```

### 2.3 Cleanup Local Test
**Always remove local test containers before production deployment:**
```bash
sudo docker-compose down -v
```

---

## Phase 3: Production Deployment (Unraid)

### 3.1 Deploy via Ansible
Production deployments use Ansible playbooks from the `homelab-infra` repository.

```bash
cd ~/CascadeProjects/homelab-infra

# Set required secrets (get from 1Password)
export PORTAINER_TOKEN=$(op read "op://Personal/Portainer Homelab API/credential")

# Run deployment
ANSIBLE_ROLES_PATH=./ansible/roles ansible-playbook \
  -i ansible/inventory/hosts.yml \
  ansible/playbooks/<group>/<playbook>.yml
```

### 3.2 Verify Production Deployment
```bash
# Health check against Unraid
curl -s http://192.168.20.14:<port>/health

# Check container status
ssh root@192.168.20.14 "docker ps | grep <container-name>"

# Check logs if needed
ssh root@192.168.20.14 "docker logs --tail 20 <container-name>"
```

---

## Rules Summary

| Rule | Description |
|------|-------------|
| **R1** | Always build locally on dev VM, never directly on production |
| **R2** | Push images to GHCR before deploying to production |
| **R3** | Ensure GHCR package is public OR Unraid has GHCR auth configured |
| **R4** | Local testing is for validation only - always cleanup after |
| **R5** | Production deployment MUST use Ansible playbooks |
| **R6** | Secrets come from 1Password, passed via environment variables |
| **R7** | Always verify deployment via health endpoint after deploy |
| **R8** | Never deploy via `scp` or manual `docker run` on production |

---

## Troubleshooting

### GHCR Pull Denied
```
Error response from daemon: denied: denied
```
**Solution**: Either make the GHCR package public or ensure Unraid is authenticated to GHCR.

### Container Exits Immediately
Check logs: `docker logs <container-name>`
Common causes:
- Missing required flags/environment variables
- Invalid configuration
- Dependency services unavailable

### Ansible Role Not Found
```
ERROR! the role 'xxx' was not found
```
**Solution**: Set `ANSIBLE_ROLES_PATH=./ansible/roles` or run from `ansible/` directory.

### Token/Secret Not Passed
Ensure environment variables are exported before running Ansible:
```bash
export PORTAINER_TOKEN="..."
```

---

## MCP Server Specific Notes

For MCP (Model Context Protocol) servers:
- Default endpoint path: `/mcp`
- Default transport: `streamable-http`
- Health endpoint: `/health`
- Typical ports: 6970-6979 range

MCP config for IDE (Windsurf/Cursor):
```json
{
  "mcpServers": {
    "<service-name>": {
      "url": "http://192.168.20.14:<port>/mcp"
    }
  }
}
```
