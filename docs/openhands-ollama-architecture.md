# OpenHands + Ollama Architecture

## Overview

This architecture implements a reliable, reproducible OpenHands deployment on Unraid with Ollama as the LLM provider on a Windows GPU host. The design prioritizes deterministic networking, configuration-as-code, and long-running stability.

## Architecture Diagram

```
┌─────────────────┐         ┌─────────────────┐
│   Windows PC    │         │   Unraid NAS    │
│  (GPU Host)     │         │  (Control Plane)│
│                 │         │                 │
│  ┌───────────┐  │         │  ┌───────────┐  │
│  │ Docker    │  │         │  │ Docker    │  │
│  │ Desktop   │  │         │  │ Engine    │  │
│  └─────┬─────┘  │         │  └─────┬─────┘  │
│        │        │         │        │        │
│  ┌─────▼─────┐  │         │  ┌─────▼─────┐  │
│  │  Ollama   │◄─┼─────────┼──►│ OpenHands │  │
│  │ 0.0.0.0:  │  │  LAN    │  │ :3000     │  │
│  │ 11434     │  │         │  │ oh-net    │  │
│  └───────────┘  │         │  └─────┬─────┘  │
│                 │         │         │        │
│                 │         │  ┌─────▼─────┐  │
│                 │         │  │  Agent    │  │
│                 │         │  │Containers │  │
│                 │         │  │oh-net     │  │
│                 │         │  └───────────┘  │
└─────────────────┘         └─────────────────┘
```

## Design Decisions

### 1. LAN-Reachable Networking
- **Why**: Eliminates Docker magic hostnames (`host.docker.internal`) that cause intermittent failures
- **Benefits**: 
  - Deterministic IP addresses
  - Works across multiple Docker engines
  - Easier troubleshooting
  - Supports multi-instance deployments

### 2. Dedicated Bridge Network (oh-net)
- **Why**: Isolates OpenHands and its agents from default Docker networks
- **Benefits**:
  - Predictable IP range (172.20.0.0/24)
  - No conflicts with other services
  - Agent containers can reliably reach OpenHands

### 3. Configuration-as-Code (config.toml)
- **Why**: Ensures reproducible deployments and preserves behavior across recreates
- **Benefits**:
  - Version controlled configuration
  - No UI clicks required
  - Immediate validation of config loading

### 4. Explicit GPU Passthrough
- **Why**: Maximizes LLM inference performance
- **Benefits**:
  - Direct GPU access
  - No virtualization overhead
  - Supports larger models

## Component Details

### OpenHands on Unraid
- **Image**: `ghcr.io/all-hands-ai/openhands:0.28.1`
- **Network**: `oh-net` (172.20.0.0/24)
- **Port**: 3000 (exposed to LAN)
- **Storage**: Named volume `openhands-data`
- **Config**: Read-only mount at `/openhands/config/config.toml`

### Ollama on Windows
- **Image**: `ollama/ollama:0.4.7`
- **Binding**: `0.0.0.0:11434` (LAN accessible)
- **GPU**: NVIDIA with all devices
- **Keep-alive**: 24h for overnight runs

## Deployment Guide

### 1. Prepare Windows GPU Host
```bash
# Clone repository
git clone <repo>
cd homelab-infra

# Configure Ollama
cp docker/ollama-windows/.env.example docker/ollama-windows/.env
# Edit .env if needed (defaults work for most)

# Deploy Ollama
cd docker/ollama-windows
docker-compose up -d

# Pull models (optional)
docker exec ollama-windows ollama pull llama3.2:3b
```

### 2. Deploy OpenHands on Unraid
```bash
# Configure OpenHands
cp docker/openhands-unraid/.env.example docker/openhands-unraid/.env

# Edit .env with:
# - OPENHANDS_SECRET_KEY (generate: openssl rand -hex 32)
# - OLLAMA_HOST_IP (Windows PC IP)
# - OLLAMA_MODEL (chosen model name)

# Deploy
cd docker/openhands-unraid
docker-compose up -d
```

### 3. Verify Deployment
```bash
# From any LAN machine
curl http://<UNRAID_IP>:3000/health

# From OpenHands container
docker exec openhands curl http://<WINDOWS_IP>:11434/api/tags

# Check config loading
docker exec openhands cat /openhands/config/config.toml
```

## Troubleshooting

### Agent Cannot Reach OpenHands
**Symptoms**: Agent containers timeout, show connection errors

**Solutions**:
1. Check if OpenHands is on oh-net:
   ```bash
   docker network inspect oh-net
   ```
2. Verify OpenHands IP:
   ```bash
   docker exec openhands ip addr show eth0
   ```
3. Update `openhands_address` in config.toml if needed

### Ollama Connection Fails
**Symptoms**: LLM requests timeout, "connection refused"

**Solutions**:
1. Verify Ollama binds to 0.0.0.0:
   ```bash
   docker exec ollama-windows ss -tlnp | grep 11434
   ```
2. Check Windows firewall:
   - Allow port 11434 inbound
   - Allow Docker Desktop through firewall
3. Test from Unraid:
   ```bash
   curl -v http://<WINDOWS_IP>:11434/api/tags
   ```

### Config.toml Not Loaded
**Symptoms**: "config.toml not found" in logs, default values used

**Solutions**:
1. Verify mount:
   ```bash
   docker exec openhands ls -la /openhands/config/
   ```
2. Check permissions:
   ```bash
   docker exec openhands cat /openhands/config/config.toml
   ```
3. Restart after fixing:
   ```bash
   docker-compose restart
   ```

### MCP Timeout Errors
**Symptoms**: "MCP timeout" in logs, agent stalls

**Solutions**:
1. MCP is disabled by default - this should not occur
2. If you enable MCP, use LAN URLs, not host.docker.internal
3. Check MCP server is accessible from Unraid

## Common Failure Modes

### 1. IP Address Changes
**Problem**: Windows PC gets new IP, breaking OpenHands connection

**Fix**:
- Use DHCP reservation for Windows PC
- Or update OLLAMA_HOST_IP in .env and restart

### 2. Docker Desktop Updates
**Problem**: Windows update resets Docker network settings

**Fix**:
- Restart Ollama container
- Verify 0.0.0.0 binding
- Check Windows firewall rules

### 3. Unraid Updates
**Problem**: Docker version changes affect socket mounting

**Fix**:
- Verify /var/run/docker.sock mount
- Check OpenHands logs for permission errors
- Restart OpenHands service

## Validation Checklist

- [ ] OpenHands health endpoint returns 200
- [ ] Ollama API accessible from Unraid
- [ ] Config.toml loaded without errors
- [ ] Agent containers spawn on oh-net
- [ ] Agents can reach OpenHands at configured IP
- [ ] No host.docker.internal references in logs
- [ ] Models load and respond to prompts
- [ ] Overnight runs complete without timeout

## Scaling Considerations

### Multiple OpenHands Instances
- Use different ports (3001, 3002, etc.)
- Create separate networks (oh-net-2, oh-net-3)
- Update agent network config accordingly

### Multiple GPU Hosts
- Deploy Ollama on multiple Windows PCs
- Use load balancer or round-robin DNS
- Configure OpenHands with base_url pointing to balancer

### High Availability
- Run multiple Ollama instances with same model
- Use nginx or HAProxy for failover
- Monitor health and auto-failover

## Security Notes

- OpenHands exposes port 3000 to LAN - consider VPN access
- Ollama exposes port 11434 - restrict to trusted IPs
- Use strong secret keys for OpenHands
- Regularly update container images
- Monitor logs for unauthorized access attempts
