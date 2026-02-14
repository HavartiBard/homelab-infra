# SoulLayer HTTP Access via mcp-proxy

**Date:** 2026-02-13
**Status:** Implemented (2026-02-13)
**Owner:** James (with Claude Code)

## Problem Statement

SoulLayer MCP server uses stdio transport, which only works from machines with access to Unraid's Docker socket (currently just dev-box). Other machines (jetson nano, spraycheese, laptop) cannot access the soul, preventing multi-machine AI agent coordination.

## Solution

Deploy **mcp-proxy** (upstream from sparfenyuk) to bridge stdio MCP servers to HTTP/SSE transport. This provides centralized access to SoulLayer from any machine on the network.

## Architecture

### Component Layout

```
┌─────────────────────────────────────────────────────┐
│  Clients (dev-box, jetson nano, spraycheese, etc.)  │
│  - Claude Code, Codex, OpenCode                     │
│  - Director MCP                                      │
└────────────────┬────────────────────────────────────┘
                 │ HTTP/SSE
                 │ http://192.168.20.14:6980/servers/soullayer/sse
┌────────────────▼────────────────────────────────────┐
│  mcp-proxy Container (Unraid)                       │
│  - Image: ghcr.io/sparfenyuk/mcp-proxy:v0.3.2-alpine│
│  - Port 6980                                        │
│  - Reads servers.json config                        │
│  - Routes /servers/<name>/sse to stdio commands     │
│  - Docker socket mounted for exec access            │
└────────────────┬────────────────────────────────────┘
                 │ docker exec -i soullayer soullayer serve
┌────────────────▼────────────────────────────────────┐
│  soullayer Container (Unraid)                       │
│  - CMD: sleep infinity                              │
│  - Execed into by mcp-proxy for each request        │
│  - Reads /data/soul.md (git-backed)                 │
│  - Writes .soullayer/memories.db (SQLite)           │
└─────────────────────────────────────────────────────┘
```

### Why mcp-proxy?

**Considered alternatives:**
1. **Custom HTTP wrapper** - Rejected: Don't reinvent the wheel
2. **mcp-bridge** (brrock) - Rejected: No Docker support, requires UI + PostgreSQL + Redis
3. **mcp-proxy** (sparfenyuk) - **Selected**: Docker-ready, CLI/JSON config, lightweight, multi-server support

**Decision factors:**
- Existing Docker images (`ghcr.io/sparfenyuk/mcp-proxy:v0.3.2-alpine`)
- JSON configuration (Ansible-friendly)
- No database dependencies (lightweight)
- Multi-server support (future-proof for other stdio MCPs)
- Active development (99 commits, 2.3k stars)

## Components

### 1. mcp-proxy Container

**Deployment:**
- Location: Unraid (`/mnt/user/appdata/mcp-proxy`)
- Port: 6980 (matches existing MCP pattern)
- Image: `ghcr.io/sparfenyuk/mcp-proxy:v0.3.2-alpine` (pinned)
- Network: Port mapping (not macvlan)

**Volumes:**
- `./servers.json:/config/servers.json:ro` - MCP server configuration
- `/var/run/docker.sock:/var/run/docker.sock:ro` - Docker exec access

**Command:**
```bash
--port=6980 --host=0.0.0.0 --named-server-config=/config/servers.json
```

### 2. servers.json Configuration

Multi-server JSON config (Ansible template):

```json
{
  "mcpServers": {
    "soullayer": {
      "command": "docker",
      "args": ["exec", "-i", "soullayer", "soullayer", "serve"],
      "transportType": "stdio"
    }
  }
}
```

**Future extensibility:** Additional stdio MCP servers added as new keys in `mcpServers`.

### 3. SoulLayer Container (No Changes)

Existing deployment remains unchanged:
- CMD: `sleep infinity` (keeps container running)
- mcp-proxy execs into it on-demand
- No direct network exposure needed

## Data Flow

**Request Lifecycle:**

1. Client sends HTTP request to `http://192.168.20.14:6980/servers/soullayer/sse`
2. mcp-proxy receives request, looks up "soullayer" in `servers.json`
3. mcp-proxy executes: `docker exec -i soullayer soullayer serve`
4. mcp-proxy writes request payload to soullayer's stdin
5. SoulLayer processes MCP request (reads soul.md, queries memories.db)
6. SoulLayer writes response to stdout
7. mcp-proxy reads stdout, returns as SSE/HTTP response to client

**Transport:** Server-Sent Events (SSE) over HTTP

## Deployment

### Ansible Structure

**Playbook:** `ansible/playbooks/mcp/deploy-mcp-proxy.yml`
- Follows existing MCP playbook pattern (see: `deploy-portainer-mcp.yml`)
- Uses Ansible role: `roles/mcp-proxy`

**Role tasks:**
1. Create `/mnt/user/appdata/mcp-proxy` directory
2. Pull `ghcr.io/sparfenyuk/mcp-proxy:v0.3.2-alpine`
3. Template `servers.json` from Ansible vars
4. Stop/remove existing container
5. Deploy mcp-proxy container with docker run
6. Wait for container health
7. Verify `/servers/soullayer/sse` endpoint responds

**Files:**
- `roles/mcp-proxy/tasks/main.yml` - Deployment tasks
- `roles/mcp-proxy/defaults/main.yml` - Default variables
- `roles/mcp-proxy/templates/servers.json.j2` - Server config template

### Configuration Variables

```yaml
# roles/mcp-proxy/defaults/main.yml
mcp_proxy_image: "ghcr.io/sparfenyuk/mcp-proxy:v0.3.2-alpine"
mcp_proxy_container_name: "mcp-proxy"
mcp_proxy_port: 6980
mcp_proxy_appdata_dir: "/mnt/user/appdata/mcp-proxy"
mcp_proxy_icon: "https://raw.githubusercontent.com/sparfenyuk/mcp-proxy/main/icon.png"

# MCP servers to expose (extensible)
mcp_proxy_servers:
  - name: soullayer
    command: docker
    args:
      - exec
      - -i
      - soullayer
      - soullayer
      - serve
```

## Error Handling

**Failure Modes:**

1. **SoulLayer container not running**
   - mcp-proxy will fail docker exec
   - Client receives 500 error with stderr output
   - Fix: Ensure soullayer container is running

2. **Docker socket not accessible**
   - Container startup fails
   - Fix: Verify socket mount in docker-compose

3. **Invalid servers.json**
   - mcp-proxy fails to start
   - Fix: Validate JSON syntax in Ansible template

4. **Port 6980 conflict**
   - Container fails to bind port
   - Fix: Check for port conflicts (`lsof -i :6980`)

**Health Checks:**
- Container status: `docker ps --filter name=mcp-proxy`
- Endpoint test: `curl http://localhost:6980/servers/soullayer/sse`
- Logs: `docker logs mcp-proxy -f`

## Testing & Verification

**Post-deployment checks:**

1. **Container running:**
   ```bash
   docker ps | grep mcp-proxy
   ```

2. **Endpoint accessible:**
   ```bash
   curl -v http://192.168.20.14:6980/servers/soullayer/sse
   ```

3. **MCP protocol test:**
   - Configure Claude Code with SSE endpoint
   - Test `soul_read` tool
   - Verify response contains soul.md content

4. **Multi-machine test:**
   - Connect from dev-box (local)
   - Connect from jetson nano (remote)
   - Verify both can access the same soul

## Client Configuration

### Claude Code

**Location:** Project-specific `.mcp.json` or global `~/.mcp.json`

**Configuration:**
```json
{
  "mcpServers": {
    "soullayer": {
      "url": "http://192.168.20.14:6980/servers/soullayer/sse"
    }
  }
}
```

**Verification:**
```bash
# Validate JSON syntax
jq . .mcp.json

# Test connection (requires Claude Code restart after config change)
# Check for soul_read, memory_search, memory_store, lessons_check tools
# Call soul_read to verify connection
```

**Status:** ✅ Verified working in `/home/james/projects/agent-flow/.mcp.json`

### Codex

**Location:** `~/.codex/config.toml`

**Configuration:**
```toml
[mcp_servers.soullayer]
url = "http://192.168.20.14:6980/servers/soullayer/sse"
```

**Status:** ⏳ Pending (Task 6)

### Director Integration

**Status:** ⏳ Planned (Task 9)

- Add to Director's MCP server registry
- Accessible via Director's MCP aggregation
- Makes SoulLayer available to all clients without per-project config

## Rollback Plan

**If deployment fails:**

1. Stop mcp-proxy container:
   ```bash
   docker stop mcp-proxy && docker rm mcp-proxy
   ```

2. Clients revert to stdio connection (dev-box only):
   ```toml
   [mcp_servers.soullayer]
   command = "ssh"
   args = ["root@192.168.20.14", "docker", "exec", "-i", "soullayer", "soullayer", "serve"]
   ```

3. No changes to SoulLayer container (unchanged)

## Future Enhancements

1. **Additional stdio MCPs:**
   - Add entries to `servers.json`
   - Each becomes `/servers/<name>/sse`

2. **Authentication:**
   - mcp-proxy supports `--headers` for bearer tokens
   - Add if needed for security

3. **Monitoring:**
   - Add Prometheus metrics if mcp-proxy supports it
   - Monitor request latency and error rates

## Success Criteria

- ✅ mcp-proxy container running on Unraid
- ✅ SoulLayer accessible via HTTP from any machine
- ✅ Claude Code, Codex, OpenCode can connect from dev-box
- ✅ Jetson nano can connect to SoulLayer
- ✅ All MCP tools (soul_read, memory_store, etc.) work via HTTP
- ✅ No changes required to existing SoulLayer deployment

## Deployment Notes

Successfully deployed on 2026-02-13:
- mcp-proxy container running on Unraid:6980
- SoulLayer accessible via HTTP/SSE from all machines
- Claude Code and Codex clients configured and tested
- Memory operations verified working

## References

- [mcp-proxy GitHub](https://github.com/sparfenyuk/mcp-proxy)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- Existing MCP playbooks: `ansible/playbooks/mcp/deploy-portainer-mcp.yml`
