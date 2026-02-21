# Artifact Checklist (Phase 3)

Generated from `service-manifest.yml`. Use this as the authoritative per-class file list.
Check off each item as it is created. All paths use the service `<name>` slug.

---

## All classes

- [ ] `ansible/roles/<name>/defaults/main.yml`
- [ ] `ansible/roles/<name>/tasks/main.yml`
- [ ] `ansible/files/<name>/docker-compose.yml`
- [ ] `ansible/playbooks/<group>/deploy-<name>.yml`
  - `<group>` = `mcp` for MCP servers, `platform` for first-class apps, `misc` for utilities

---

## mcp class additionally

- [ ] If `mcp_proxy.enabled: true`:
  - [ ] Add server entry to `ansible/roles/mcp-proxy/defaults/main.yml` servers list
  - [ ] Redeploy mcp-proxy: `ansible-playbook playbooks/mcp/deploy-mcp-proxy.yml --diff --limit unraid`
  - [ ] Verify mcp-proxy lists the new server: `curl -s http://192.168.20.14:6980/servers`
  - [ ] Only proceed to Director wiring after this is confirmed
- [ ] Add entry to `ROLE_MAP` in `ansible/scripts/export-director-mcp-fragment.py`:
  ```python
  {
      "role": "<name>",
      "name": "<name>",
      "port_var": "<name>_port",
      "path": "/mcp",
  },
  ```

---

## first-class class additionally

- [ ] `ansible/files/npm/services/<name>.yml` — from `references/npm-service-template.yml`
- [ ] `ansible/playbooks/services/update-<name>-proxy.yml` — from `references/update-proxy-playbook-template.yml`
- [ ] Technitium DNS task: A record `<name>.klsll.com → NPM IP (192.168.20.50)`
- [ ] Homepage card in `stacks/platform/homepage/config/services.yaml`:
  ```yaml
  - name: <Display Name>
    href: https://<name>.klsll.com
    icon: <name>.png
    description: <one line>
    group: <Group>
  ```

---

## agent class additionally

- [ ] macvlan IP allocated and documented in `ansible/inventory/host_vars/<name>.yml`
- [ ] DNS A record: `<name>.lab.klsll.com → <macvlan-ip>` added to Technitium
- [ ] Bootstrap tasks in `ansible/roles/<name>/tasks/main.yml`:
  - [ ] Install zsh
  - [ ] Install oh-my-zsh + Pure theme
  - [ ] Install op (1Password CLI)
  - [ ] Install tea (Gitea CLI)
  - [ ] Deploy `.env_container` with API keys retrieved from 1Password
  - [ ] Deploy standard SSH key (`id_ed25519_homelab`)
  - [ ] Set default shell to zsh for the service user

---

## Phase 4 documentation checklist

- [ ] Port row added to `docs/network-ports.md`
- [ ] Obsidian catalog entry written at `services/<name>.md` using `templates/service-catalog.md`
- [ ] `ansible/README.md` roles table updated
- [ ] `ansible/playbooks/README.md` updated
- [ ] If first-class: homepage card verified present in `stacks/platform/homepage/config/services.yaml`
