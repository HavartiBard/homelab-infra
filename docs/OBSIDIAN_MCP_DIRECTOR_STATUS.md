# Obsidian MCP Director Integration Status

## Current State

**Date:** 2026-02-15
**Status:** Partial Success - HTTP Transport Working, Director Connection Issue

## What Works

1. **Obsidian MCP Server** - Fully functional
   - Running on Unraid at `192.168.20.14:6977`
   - HTTP transport mode operational
   - Health endpoint responsive: `http://192.168.20.14:6977/health`
   - Successfully establishes SSE connections
   - Logs show multiple successful HTTP connections

2. **Infrastructure**
   - CouchDB backend deployed and healthy
   - Obsidian vault mounted at `/mnt/user/appdata/obsidian/vaults/homelab`
   - Docker networking functional
   - All Ansible roles deployed successfully

3. **Director Configuration**
   - Docker socket properly mounted (`/var/run/docker.sock`)
   - Config file contains obsidian-mcp in both `dev-core` and `global-core` playbooks
   - Configuration syntax is valid

## What Doesn't Work

### Director Not Connecting to Obsidian MCP

Director successfully connects to other MCP servers but silently skips obsidian-mcp:

**Connecting:**
- unraid-mcp (6970)
- homelab-mcp (6971)
- onepassword-mcp (6975)
- portainer-mcp (6972)
- gitea-mcp (6976)
- soullayer (6980)
- onepass (6975)

**Not Connecting:**
- **obsidian-mcp (6977)**
- proxmox-mcp (6974)
- notion-mcp-public (3000)

All three missing servers are reachable and return HTTP 200. No errors in Director logs.

## Original Spec vs Reality

### Spec Requirement (stdio transport)

```yaml
- name: obsidian-mcp
  command: docker
  args:
    - exec
    - -i
    - obsidian-mcp
    - node
    - src/index.js
  type: stdio
```

### Why This Doesn't Work

The Director container image (`barnaby/director:1.1.1`) does not include the Docker CLI. Attempting to run `docker exec` from within Director fails:

```
OCI runtime exec failed: exec failed: unable to start container process:
exec: "docker": executable file not found in $PATH: unknown
```

### Workaround (HTTP transport)

We implemented HTTP transport instead:

```yaml
- name: obsidian-mcp
  url: http://192.168.20.14:6977/mcp
  type: http
```

The Obsidian MCP server supports both transports via the `TRANSPORT_MODE` environment variable.

## Files Modified

### Ansible

- `/home/james/projects/homelab-infra/.worktrees/obsidian-migration/ansible/roles/obsidian-mcp/defaults/main.yml`
  - `obsidian_mcp_transport_mode: "http"`

- `/home/james/projects/homelab-infra/.worktrees/obsidian-migration/ansible/playbooks/mcp/`:
  - `deploy-obsidian-stack.yml` - Main deployment playbook
  - `update-director-obsidian-config.yml` - Attempted stdio config (doesn't work)
  - `revert-director-obsidian-to-http.yml` - Reverts to HTTP (current)
  - `fix-director-obsidian-playbook.yml` - Adds obsidian-mcp to dev-core

### Docker

- `/home/james/projects/homelab-infra/.worktrees/obsidian-migration/ansible/files/director/docker-compose.yml`
  - Added: `- /var/run/docker.sock:/var/run/docker.sock`

- `/home/james/projects/homelab-infra/.worktrees/obsidian-migration/docker/obsidian-mcp-server/src/index.js`
  - Supports both HTTP and stdio transports
  - Reads `TRANSPORT_MODE` env var

## Next Steps

### Investigation Needed

1. **Director Connection Issue** - Why is Director silently skipping 3 configured servers?
   - Check Director source code or documentation
   - Look for rate limiting, connection pool limits, or startup timing issues
   - Test with Director in debug/verbose mode if available
   - Check if there's a configuration ordering or validation issue

2. **stdio Transport** - To properly support stdio with docker exec:
   - Build custom Director image with Docker CLI included
   - OR use a sidecar pattern with Docker socket proxy
   - OR continue using HTTP transport (simpler, working)

### Testing

Once Director connects:

1. Verify MCP tools are accessible via Director
2. Test read operations from Obsidian vault
3. Test write operations (if enabled)
4. Verify search functionality
5. Test via actual AI agent (Claude Code with Director config)

## Deployment Commands

### Redeploy Obsidian Stack
```bash
cd /home/james/projects/homelab-infra/.worktrees/obsidian-migration/ansible
ansible-playbook playbooks/mcp/deploy-obsidian-stack.yml --diff --limit unraid-server
```

### Update Director Config
```bash
cd /home/james/projects/homelab-infra/.worktrees/obsidian-migration/ansible
ansible-playbook playbooks/mcp/fix-director-obsidian-playbook.yml --diff --limit unraid-server
```

### Verify Status
```bash
# Check Obsidian MCP
curl http://192.168.20.14:6977/health

# Check Director logs
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 "docker logs director --tail 50"

# Check Obsidian MCP logs
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 "docker logs obsidian-mcp --tail 50"
```

## Conclusion

The Obsidian MCP server is fully functional and ready to serve requests. The blocker is Director's connection behavior, which appears to be a Director-specific issue unrelated to our implementation.

**Recommendation:** Continue investigation into Director's connection logic or consider alternative MCP aggregation solutions if needed.
