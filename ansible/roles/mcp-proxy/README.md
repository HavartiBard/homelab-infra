# mcp-proxy Ansible Role

Deploys mcp-proxy (stdio-to-HTTP bridge) for exposing stdio MCP servers over HTTP/SSE.

## Variables

See `defaults/main.yml` for full list.

## Usage

```bash
ansible-playbook playbooks/mcp/deploy-mcp-proxy.yml --limit unraid
```

## Adding New stdio MCP Servers

Edit `defaults/main.yml` and add to `mcp_proxy_servers` list:

```yaml
mcp_proxy_servers:
  - name: my-new-mcp
    command: docker
    args: [exec, -i, my-container, my-mcp-command]
    transport_type: stdio
```

Endpoint will be: `http://unraid:6980/servers/my-new-mcp/sse`
