# Director

Director provides playbook-based MCP orchestration and a web studio UI.

## Topology
- Host: Unraid (`192.168.20.14`)
- Local endpoint: `http://192.168.20.14:8080`
- Public LAN endpoint via NPM: `https://director.klsll.com`
- DNS: `director.klsll.com -> 192.168.20.50` (NPM)

## Deployment

```bash
cd ansible
ansible-playbook playbooks/platform/deploy-director.yml --syntax-check
ansible-playbook playbooks/platform/deploy-director.yml --check --diff --limit unraid
ansible-playbook playbooks/platform/deploy-director.yml --diff --limit unraid -v
```

## Proxy + DNS

```bash
cd ansible
ansible-playbook playbooks/services/update-director-proxy.yml --syntax-check
ansible-playbook playbooks/services/update-director-proxy.yml --check --diff --limit unraid
ansible-playbook playbooks/services/update-director-proxy.yml --diff --limit unraid -v
```

This proxy definition is stored in `ansible/files/npm/services/director.yml` and uses:
- `certificate: klsll-wildcard`
- `ssl_forced: true`
- `hsts: true`
- `http2: true`

## Verify

```bash
cd ansible
ansible unraid -m raw -a "docker ps | grep -E 'director|CONTAINER'"
curl -I https://director.klsll.com
curl -I https://director.klsll.com/studio
curl -sS http://192.168.20.14:8080/studio | head -n 5
```

Expected:
- Container `director` is running.
- `https://director.klsll.com` returns `302` to `/studio`.
- `https://director.klsll.com/studio` returns `200`.

## Rollback

```bash
cd ansible
ansible unraid -m raw -a "cd /mnt/user/appdata/director && docker compose down"
```

Then remove or disable `director.klsll.com` from `ansible/files/npm/services/director.yml` and re-run:

```bash
cd ansible
ansible-playbook playbooks/services/update-director-proxy.yml --diff --limit unraid -v
```

## Obsidian Service Catalog

After deployment changes merge, update the Homelab Obsidian service catalog entry for Director:
- Service name: Director
- Owner: Homelab Platform
- Host: Unraid (`192.168.20.14`)
- URL: `https://director.klsll.com`
- Playbooks:
  - `ansible/playbooks/platform/deploy-director.yml`
  - `ansible/playbooks/services/update-director-proxy.yml`
- Proxy cert: `klsll-wildcard`
- Verification commands and rollback command from this page
