# OpenHands + Ollama Verification Steps

## Prerequisites

1. Windows GPU host IP known (e.g., 192.168.1.100)
2. Unraid IP known (e.g., 192.168.1.10)
3. Both services deployed

## Verification Commands

### 1. Ollama Health Check (from any LAN machine)
```bash
curl http://<WINDOWS_IP>:11434/api/tags
# Expected: List of available models
```

### 2. OpenHands Health Check (from any LAN machine)
```bash
curl http://<UNRAID_IP>:3000/health
# Expected: {"status": "healthy"}
```

### 3. OpenHands to Ollama Connectivity
```bash
# From OpenHands container
docker exec openhands curl http://<WINDOWS_IP>:11434/api/tags
# Expected: List of available models
```

### 4. Config.toml Validation
```bash
# Check config is mounted
docker exec openhands ls -la /openhands/config/config.toml

# Check config content
docker exec openhands cat /openhands/config/config.toml

# Check logs for config loading
docker logs openhands | grep -i "config"
# Should NOT see "config.toml not found"
```

### 5. Network Verification
```bash
# Check oh-net network exists
docker network inspect oh-net

# Check OpenHands IP on oh-net
docker exec openhands ip addr show eth0
# Should be in 172.20.0.x range

# Check for host.docker.internal references
docker logs openhands | grep "host.docker.internal"
# Should return nothing
```

### 6. Agent Container Test
```bash
# Start a simple OpenHands session
# Through web UI at http://<UNRAID_IP>:3000
# Send: "List files in current directory"

# Find spawned agent container
docker ps | grep oh-agent-server

# From agent container, test OpenHands connectivity
docker exec <agent-container-id> curl http://172.20.0.2:3000/health
# Expected: {"status": "healthy"}
```

### 7. End-to-End LLM Test
```bash
# Through OpenHands UI, send:
# "Write a Python hello world script"

# Verify:
# - Agent container spawns
# - No timeout errors
# - Script is generated
# - No MCP errors in logs
```

## Expected Results

✅ All health checks return 200 OK
✅ Config.toml loads without errors
✅ Agent containers reach OpenHands on oh-net
✅ No host.docker.internal references
✅ LLM responses complete successfully
✅ Overnight runs remain stable

## Common Issues and Fixes

### Connection Refused
- Check Windows firewall
- Verify Ollama binds to 0.0.0.0
- Confirm IP addresses

### Config Not Found
- Verify mount path in docker-compose.yml
- Check file permissions
- Restart container

### Agent Cannot Reach OpenHands
- Update openhands_address in config.toml
- Check oh-net subnet
- Verify agent is on correct network
