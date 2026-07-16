# Obsidian Stack

The Obsidian stack provides a self-hosted knowledge base with bidirectional sync and AI agent access via MCP (Model Context Protocol).

## Architecture

### Components

1. **CouchDB** - Backend database for Obsidian LiveSync plugin
   - Version: 3.3
   - Stores vault snapshots and sync state
   - Handles conflict resolution
   - Admin and sync user credentials managed via 1Password

2. **Obsidian Vault** - Markdown note storage
   - Location: `/mnt/user/appdata/obsidian/vaults/homelab`
   - Stores notes, templates, and attachments
   - Synced via LiveSync plugin to CouchDB
   - Mounted read-only into MCP server container

3. **Obsidian MCP Server** - Agent access layer
   - Custom Node.js MCP server
   - HTTP transport on port 6977
   - Exposes vault operations to AI agents
   - Read-only access (write operations available but not exposed to agents)

4. **Desktop Clients** - Obsidian desktop applications
   - Windows, macOS, Linux clients
   - Connect to CouchDB via LiveSync plugin
   - Real-time bidirectional sync

### Data Flow

```
Desktop Client <--> CouchDB <--> Obsidian MCP Server <--> AI Agents
                      ^                   |
                      |                   v
                      +------------ Vault Files
```

## Topology

### Hosts and Ports

| Component | Host | Port | Container Name |
|-----------|------|------|----------------|
| CouchDB | Unraid (192.168.20.14) | 5984 | couchdb-obsidian |
| Obsidian MCP | Unraid (192.168.20.14) | 6977 | obsidian-mcp |
| Vault Files | Unraid | - | /mnt/user/appdata/obsidian/vaults/homelab |

### Network Configuration

- Both containers use the `homelab` Docker network
- CouchDB port 5984 exposed for LiveSync client access
- MCP server port 6977 for LAN-only agent access
- No public internet exposure

### Storage Paths

```
/mnt/user/appdata/couchdb/
├── data/              # CouchDB database files
├── config/            # CouchDB configuration
└── docker-compose.yml

/mnt/user/appdata/obsidian/
└── vaults/
    └── homelab/       # Vault root
        ├── services/  # Service documentation
        ├── templates/ # Note templates
        └── .obsidian/ # Obsidian config

/mnt/user/appdata/obsidian-mcp/
└── docker-compose.yml
```

## Deployment

### Prerequisites

Secrets resolve from 1Password at invocation time via `ansible/envs/obsidian.env` (see
`docs/secrets-management.md`) — no manual sync step needed. Backing items in the "AI Wedge" vault:
- `CouchDB Obsidian Admin` (username + password)
- `CouchDB Obsidian Sync User` (username + password)

### Deploy Complete Stack

```bash
cd ~/projects/homelab-infra/ansible
ansible-playbook playbooks/mcp/deploy-obsidian-stack.yml --syntax-check
./scripts/run-playbook.sh obsidian playbooks/mcp/deploy-obsidian-stack.yml --check --diff --limit unraid-server
./scripts/run-playbook.sh obsidian playbooks/mcp/deploy-obsidian-stack.yml --diff --limit unraid-server -v
```

This playbook:
1. Creates CouchDB directories and config
2. Deploys CouchDB container with admin credentials
3. Waits for CouchDB to be healthy
4. Creates Obsidian vault directories
5. Deploys Obsidian MCP server container
6. Waits for MCP server to be ready

### Variables

Key variables from `ansible/group_vars/unraid/obsidian.yml`:

```yaml
# CouchDB
couchdb_version: "3.3"
couchdb_port: 5984
couchdb_container_name: "couchdb-obsidian"
couchdb_admin_user: "{{ vault_couchdb_admin_user }}"
couchdb_admin_password: "{{ vault_couchdb_admin_password }}"
couchdb_sync_user: "{{ vault_couchdb_sync_user }}"
couchdb_sync_password: "{{ vault_couchdb_sync_password }}"

# Obsidian MCP
obsidian_mcp_port: 6977
obsidian_mcp_container_name: "obsidian-mcp"
obsidian_mcp_transport_mode: "http"
obsidian_vault_path: "/mnt/user/appdata/obsidian/vaults/homelab"
```

## Verify

### 1. Check Container Status

```bash
cd ~/projects/homelab-infra/ansible
ansible unraid -m raw -a "docker ps | grep -E 'couchdb|obsidian|CONTAINER'"
```

Expected: Both `couchdb-obsidian` and `obsidian-mcp` are running.

### 2. Verify CouchDB Health

```bash
# Health check endpoint
curl -f http://192.168.20.14:5984/_up

# Admin login
curl -u admin:password http://192.168.20.14:5984/_all_dbs
```

Expected: `_up` returns HTTP 200, `_all_dbs` returns database list.

### 3. Verify MCP Server

```bash
# Health endpoint
curl http://192.168.20.14:6977/health

# Check container logs
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 "docker logs obsidian-mcp --tail 20"
```

Expected:
- Health endpoint returns `{"status":"healthy","mode":"http","server":"obsidian-mcp-server"}`
- Logs show "Obsidian MCP Server running on HTTP mode at port 6977"

### 4. Verify Vault Structure

```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 \
  "ls -la /mnt/user/appdata/obsidian/vaults/homelab"
```

Expected: Directories exist with `nobody:users` ownership and `775` permissions.

### 5. Test MCP Tools

```bash
# List available tools (requires MCP client)
curl -X POST http://192.168.20.14:6977/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'
```

Expected: Returns list of tools: `obsidian_list_notes`, `obsidian_read_note`, `obsidian_write_note`, `obsidian_search`.

## Desktop Client Setup

### 1. Install Obsidian

Download from https://obsidian.md

### 2. Create Local Vault

1. Open Obsidian
2. Create new vault or open existing
3. Install "Self-hosted LiveSync" plugin from Community Plugins

### 3. Configure LiveSync Plugin

**Setup Wizard:**

1. Settings → Community Plugins → Self-hosted LiveSync → Setup Wizard
2. **Remote Database Configuration:**
   - URI: `http://192.168.20.14:5984`
   - Database name: `obsidian_homelab` (create new or use existing)
   - Username: `<sync_user>` (from 1Password: "CouchDB Obsidian Sync User")
   - Password: `<sync_password>`
   - Test connection

3. **Encryption Settings:**
   - Enable end-to-end encryption (recommended)
   - Set passphrase (store in 1Password)

4. **Sync Settings:**
   - Sync on save: Enabled
   - Periodic sync: Every 60 seconds
   - Fetch on startup: Enabled

5. **Initial Sync:**
   - Click "Replicate now" to perform initial sync
   - Watch for "All done!" message

### Known Issue: Sync User Creation

**BLOCKER:** The sync user is not automatically created in CouchDB. The admin credentials work, but using them in LiveSync clients is a security risk.

**Temporary Workaround:** Use admin credentials until sync user is created.

**Proper Solution:** Create sync user manually or via playbook:

```bash
# Manual creation (SSH to Unraid):
curl -X PUT http://localhost:5984/_users/org.couchdb.user:obsidian_sync \
  -u admin:admin_password \
  -H "Content-Type: application/json" \
  -d '{
    "name": "obsidian_sync",
    "password": "sync_password",
    "roles": [],
    "type": "user"
  }'
```

## Agent Access

### Available MCP Tools

The Obsidian MCP server exposes these tools to AI agents:

1. **obsidian_list_notes**
   - List all notes in vault or specific folder
   - Parameters: `folder` (optional, relative path)
   - Returns: Array of note names and paths

2. **obsidian_read_note**
   - Read note content with frontmatter parsing
   - Parameters: `path` (required, relative to vault root)
   - Returns: Frontmatter, content, and raw markdown

3. **obsidian_write_note**
   - Create or update a note
   - Parameters: `path`, `content`, `frontmatter` (optional)
   - Returns: Success status and creation flag

4. **obsidian_search**
   - Full-text search across vault
   - Parameters: `query` (required, case-insensitive)
   - Returns: Matching notes with line previews

### Usage Examples

**List all service docs:**
```json
{
  "tool": "obsidian_list_notes",
  "arguments": {
    "folder": "services"
  }
}
```

**Read a specific note:**
```json
{
  "tool": "obsidian_read_note",
  "arguments": {
    "path": "services/gitea.md"
  }
}
```

**Search for "deployment":**
```json
{
  "tool": "obsidian_search",
  "arguments": {
    "query": "deployment"
  }
}
```

### Director Integration

**Status:** Pending (connection issue)

The Obsidian MCP server is configured in Director but not currently connecting. See [OBSIDIAN_MCP_DIRECTOR_STATUS.md](/home/james/projects/homelab-infra/.worktrees/obsidian-migration/docs/OBSIDIAN_MCP_DIRECTOR_STATUS.md) for details.

**Configuration:**
```yaml
# In Director playbook config
- name: obsidian-mcp
  url: http://192.168.20.14:6977/mcp
  type: http
```

**Issue:** Director connects to 6 other MCP servers but silently skips obsidian-mcp (and 2 others). No errors in logs.

**Next Steps:**
- Investigate Director connection logic
- Check for rate limiting or startup timing issues
- Consider debug/verbose mode for Director

## Rollback

### Stop Services

```bash
cd ~/projects/homelab-infra/ansible

# Stop both services
ansible unraid -m raw -a "cd /mnt/user/appdata/obsidian-mcp && docker compose down"
ansible unraid -m raw -a "cd /mnt/user/appdata/couchdb && docker compose down"
```

### Restore Previous State

If you need to restore from backup:

```bash
# Restore CouchDB data
cd ~/projects/homelab-infra
./scripts/backup-volumes.sh --restore backups/couchdb_<timestamp>.tar.gz couchdb_data

# Restore vault files
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 \
  "tar -xzf /mnt/user/backups/obsidian_vault_<timestamp>.tar.gz -C /mnt/user/appdata/obsidian/vaults/"
```

### Remove Stack Completely

```bash
# Remove containers
ansible unraid -m raw -a "docker rm -f couchdb-obsidian obsidian-mcp"

# Remove data (WARNING: Data loss!)
ansible unraid -m raw -a "rm -rf /mnt/user/appdata/couchdb"
ansible unraid -m raw -a "rm -rf /mnt/user/appdata/obsidian"
ansible unraid -m raw -a "rm -rf /mnt/user/appdata/obsidian-mcp"
```

## Backup

### Manual Backup

**CouchDB data:**
```bash
cd ~/projects/homelab-infra
./scripts/backup-volumes.sh couchdb_data
```

**Vault files:**
```bash
ssh -i ~/.ssh/id_ed25519_homelab root@192.168.20.14 \
  "tar -czf /mnt/user/backups/obsidian_vault_$(date +%Y%m%d_%H%M%S).tar.gz \
   -C /mnt/user/appdata/obsidian/vaults homelab"
```

### Automated Backup

Add to Unraid User Scripts or cron (when implemented):

```bash
#!/bin/bash
# Daily at 2 AM - Backup Obsidian stack
0 2 * * * /mnt/user/scripts/backup-obsidian-stack.sh
```

### Restore Procedure

1. Stop containers
2. Restore CouchDB volume
3. Restore vault files
4. Start containers
5. Verify health checks
6. Trigger LiveSync replication on clients

## Troubleshooting

### Sync Issues

**Problem:** LiveSync fails to connect

**Checks:**
1. Verify CouchDB is running: `docker ps | grep couchdb`
2. Test CouchDB connectivity: `curl http://192.168.20.14:5984/_up`
3. Check LiveSync credentials match 1Password
4. Review CouchDB logs: `docker logs couchdb-obsidian`

**Solution:** Recreate database or reset sync settings in plugin.

---

**Problem:** Sync user authentication fails

**Checks:**
1. Verify sync user exists in CouchDB
2. Check credentials in 1Password "AI Wedge" vault

**Solution:** Create sync user manually (see "Desktop Client Setup" section above).

---

**Problem:** Conflict detection on every sync

**Checks:**
1. Check if multiple clients have different encryption passphrases
2. Verify system clocks are synchronized

**Solution:** Use same encryption passphrase across all clients; check NTP sync.

### Agent Access Issues

**Problem:** MCP tools not accessible via Director

**Checks:**
1. Verify MCP server health: `curl http://192.168.20.14:6977/health`
2. Check Director logs: `docker logs director --tail 50`
3. Verify network connectivity from Director to MCP server
4. Review Director playbook configuration

**Solution:** See [OBSIDIAN_MCP_DIRECTOR_STATUS.md](/home/james/projects/homelab-infra/.worktrees/obsidian-migration/docs/OBSIDIAN_MCP_DIRECTOR_STATUS.md) for current investigation status.

---

**Problem:** MCP server returns "path outside vault" errors

**Checks:**
1. Verify path is relative to vault root (no leading `/`)
2. Check for path traversal attempts (`../`)

**Solution:** Use relative paths from vault root. Example: `services/gitea.md` not `/services/gitea.md`.

---

**Problem:** Search returns no results

**Checks:**
1. Verify vault has notes: `ls /mnt/user/appdata/obsidian/vaults/homelab`
2. Check search query syntax
3. Review file permissions

**Solution:** Ensure vault permissions are `775` with `nobody:users` ownership.

### Container Issues

**Problem:** CouchDB container won't start

**Checks:**
1. Check disk space: `df -h /mnt/user`
2. Review container logs: `docker logs couchdb-obsidian`
3. Verify data directory permissions

**Solution:**
```bash
ansible unraid -m raw -a "chown -R 5984:5984 /mnt/user/appdata/couchdb/data"
ansible unraid -m raw -a "cd /mnt/user/appdata/couchdb && docker compose up -d"
```

---

**Problem:** Obsidian MCP container crashes on startup

**Checks:**
1. Check vault path exists: `ls /mnt/user/appdata/obsidian/vaults/homelab`
2. Review container logs: `docker logs obsidian-mcp`
3. Verify Docker image is available

**Solution:**
```bash
# Rebuild image if needed
cd /home/james/projects/homelab-infra/docker/obsidian-mcp-server
docker build -t ghcr.io/havartibard/obsidian-mcp:latest .

# Redeploy
cd ~/projects/homelab-infra/ansible
ansible-playbook playbooks/mcp/deploy-obsidian-stack.yml --diff --limit unraid-server -v
```

## Migration Notes

### From Notion to Obsidian

The initial vault was populated from Notion service catalog export. See migration tasks in homelab-infra issue tracker.

**Import Process:**
1. Exported Notion pages via Notion API
2. Converted to markdown with frontmatter
3. Copied to vault `services/` directory
4. Synced to CouchDB via LiveSync

**Template Used:** `/home/james/projects/homelab-infra/.worktrees/obsidian-migration/docs/services/template.md`

## References

- **Playbooks:** `/home/james/projects/homelab-infra/ansible/playbooks/mcp/deploy-obsidian-stack.yml`
- **Roles:**
  - `ansible/roles/couchdb/`
  - `ansible/roles/obsidian-mcp/`
- **Docker Images:**
  - CouchDB: `couchdb:3.3`
  - Obsidian MCP: `ghcr.io/havartibard/obsidian-mcp:latest`
- **MCP Server Source:** `/home/james/projects/homelab-infra/docker/obsidian-mcp-server/`
- **Status Document:** [OBSIDIAN_MCP_DIRECTOR_STATUS.md](/home/james/projects/homelab-infra/.worktrees/obsidian-migration/docs/OBSIDIAN_MCP_DIRECTOR_STATUS.md)

## Security Notes

1. **CouchDB Credentials:**
   - Admin credentials stored in 1Password "AI Wedge" vault
   - Resolved at invocation time via `ansible/envs/obsidian.env` (see `docs/secrets-management.md`)
   - Never committed to git

2. **Network Exposure:**
   - CouchDB and MCP server are LAN-only (no NPM proxy)
   - No public internet access
   - All traffic within homelab network

3. **Vault Encryption:**
   - LiveSync supports end-to-end encryption
   - Recommended for sensitive content
   - Passphrase stored in 1Password

4. **MCP Access:**
   - Read-only access recommended for agents
   - Write operations available but not exposed via Director
   - Path traversal protection in MCP server
