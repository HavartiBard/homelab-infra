# Homepage (gethomepage.dev)

Landing page for homelab services. Runs on the Platform stack alongside Portainer/NPM/Kuma.

## Config

Configuration files live in `stacks/platform/homepage/config/` and are mounted to `/app/config`.

1. Copy the sample files from the official docs if you want a head start: https://gethomepage.dev/en/configs
2. Common files:
   - `settings.yaml` (title/theme/layout)
   - `services.yaml` (service cards)
   - `bookmarks.yaml` (links)
   - `widgets.yaml` (uptime, resources)
3. Docker/Portainer widgets can read from the mounted Docker socket; disable the socket mount if not needed.

## Environment

Set these in `stacks/platform/.env` (Platform VM deployment):

```
HOMEPAGE_PORT=3002
HOMEPAGE_PUID=1000
HOMEPAGE_PGID=1000
HOMEPAGE_LOG_LEVEL=info
```

When running the homepage stack on Unraid, the Ansible playbook overrides this with `HOMEPAGE_IP=192.168.20.55` and `HOMEPAGE_NETWORK_NAME=br0` so the container is pinned to the VLAN br0 network instead of publishing a host port.

## Networking notes

- Running `docker compose up` from `stacks/platform/` creates the default `homepage_default` network for the Platform stack and exposes the service via `HOMEPAGE_PORT` (3002 by default) so NPM can proxy to `http://homepage:3000`.
- The Unraid playbook instead writes `ansible/files/homepage/docker-compose.yml`, where the `homepage-net` network is marked as external and its `name` is set from `HOMEPAGE_NETWORK_NAME` (defaults to `br0`). Compose therefore connects the container to the br0 VLAN and uses the `HOMEPAGE_IP` (192.168.20.55) so the service keeps a fixed IP that does not collide with Unraid itself (.14).
- Because the container always still listens on port 3000, only the IP changes; the NPM proxy entry for `home.klsll.com` points directly at `http://192.168.20.55:3000`. If you ever need a different VLAN or IP, update the Ansible vars before running `deploy-homepage.yml`.

## Deploy

From `stacks/platform/`:

```bash
docker compose pull homepage
docker compose up -d homepage
```

Port forward/proxy `http://<platform-host>:3002` (platform host) or, when deploying on Unraid, the NPM hostname `home.klsll.com` targets `http://192.168.20.55:3000` via the VLAN br0 bridge.

Ansible deploy to Unraid:

```bash
ansible-playbook ansible/playbooks/services/deploy-homepage.yml
```

## Validate config

Run a quick YAML parse on homepage configs:

```bash
./scripts/test-homepage-config.sh
```

## DNS / Proxy

1. Add a DNS record `home.klsll.com` pointing to the Platform host (Technitium/AdGuard).
2. In NPM, create a Proxy Host:
   - Domain: `home.klsll.com`
   - Forward to:
     - `http://homepage:3000` when the Platform stack is hosting the service
     - `http://192.168.20.55:3000` when the Unraid stack is hosting it (the Ansible proxy sync playbook still points the domain at 192.168.20.55)
   - Access list: optional (LAN/VPN only recommended)
   - SSL: enable Let's Encrypt/internal certificate if desired

Automation: `ansible-playbook ansible/playbooks/services/update-homepage-proxy.yml` will upsert the DNS + proxy entries defined in `ansible/files/npm/services/homepage.yml`.
