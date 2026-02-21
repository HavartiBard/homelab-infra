# Class Rules

## Decision tree — choose a class in order

**1. Does a human or AI agent SSH into this container interactively (for work or troubleshooting)?**
→ Yes → `agent`
→ No → continue

**2. Is this an MCP server consumed by AI agents via Director?**
→ Yes → `mcp`
→ No → continue

**3. Does a human access this via a browser or mobile app on the LAN?**
→ Yes (primary use is a UI) → `first-class`
→ No (backend/support service only) → `utility`

---

## first-class rules

- Requires a dedicated macvlan IP — allocate from VLAN 20 range (192.168.20.X)
- DNS A record in Technitium: `<name>.klsll.com → NPM IP (192.168.20.50)`
  - DNS points to NPM, not to the macvlan IP directly
- NPM proxy host using `klsll-wildcard` cert: `ssl_forced: true`, `hsts: true`, `http2: true`
- Homepage dashboard card required (group by function: Media, Infrastructure, AI, etc.)
- Director wiring is optional (only if the service also exposes an MCP endpoint — rare)

## mcp rules

- Shared Unraid IP (192.168.20.14), port-based access
- Port must be in MCP range 6970–6989 — check `docs/network-ports.md` first
- Must be registered in Director under the correct playbook (`dev-core` default)
- `transport: http` → Director connects directly to `http://192.168.20.14:<port>/mcp`
- `transport: stdio` → Register in mcp-proxy **before** Director:
  1. Add server to `ansible/roles/mcp-proxy/defaults/main.yml`
  2. Redeploy mcp-proxy and verify: `curl -s http://192.168.20.14:6980/servers`
  3. Only then configure Director
- Add to `ROLE_MAP` in `ansible/scripts/export-director-mcp-fragment.py`
- No NPM, no DNS, no homepage card

## utility rules

- Shared Unraid IP, port-based access (or Docker-network-internal only)
- No Director, no homepage, no NPM by default
- DNS and NPM are optional — add only if the service needs to be reached by a stable name
- No Director wiring

## agent rules

- Requires a dedicated macvlan IP — allocate from VLAN 20 range (192.168.20.X)
- DNS A record: `<name>.lab.klsll.com → <macvlan-ip>` (use `.lab.` subdomain to distinguish agents from services)
- Full shell bootstrap required in the Ansible role:
  - zsh + oh-my-zsh (Pure theme)
  - 1Password CLI (`op`)
  - Gitea CLI (`tea`)
  - Standard SSH key deployed (`id_ed25519_homelab`)
  - `.env_container` populated with API keys from 1Password
- Director and mcp-proxy are optional (only if the agent container also exposes an MCP endpoint)
- macvlan IP must be documented in `ansible/inventory/host_vars/<name>.yml`

---

## Examples

| Service | Class | Reasoning |
|---------|-------|-----------|
| Gitea | first-class | Browser UI, user-facing |
| SearXNG MCP | mcp | MCP server for agents, no browser UI needed |
| CouchDB (Obsidian backend) | utility | Backend only, not user-accessed directly |
| OpenClaw (Jetson) | agent | SSH-in interactive AI agent environment |
| dev-environment | agent | SSH-in interactive developer environment |
