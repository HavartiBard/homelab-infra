# Port Registry Pattern

## How to allocate a port

1. Open `docs/network-ports.md`
2. Find the relevant range for your service class (table below)
3. Identify the highest allocated port in that range
4. Take the next available one
5. Add the new row to `docs/network-ports.md` **in Phase 4** — this is the source of truth

## Port ranges (Unraid / 192.168.20.14)

| Range | Purpose |
|-------|---------|
| 6970–6989 | MCP servers |
| 6980 | mcp-proxy (reserved) |
| 6990–6999 | Overflow / future MCP |

## Current MCP allocations

Update this table when adding a service (also update `docs/network-ports.md`):

| Port | Service |
|------|---------|
| 6970 | unraid-mcp |
| 6971 | homelab-mcp |
| 6974 | proxmox-mcp |
| 6975 | onepassword-mcp |
| 6976 | gitea-mcp |
| 6977 | obsidian-mcp |
| 6978 | *(next available)* |
| 6980 | mcp-proxy |

## Validation — confirm port is free on host

Run before proceeding past Phase 2:

```bash
ssh -i ~/.ssh/id_ed25519_homelab unraid-server "ss -tlnp | grep :<port>"
# Expected: no output (port is free)
```

## network-ports.md row format

```
| <port> | <Service Name> | <host> (<ip>) | HTTP | <brief description> |
```

Example:
```
| 6978 | SearXNG MCP | unraid (192.168.20.14) | HTTP | MCP server — metasearch |
```
