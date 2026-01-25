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

Set these in `stacks/platform/.env`:

```
HOMEPAGE_PORT=3002
HOMEPAGE_PUID=1000
HOMEPAGE_PGID=1000
HOMEPAGE_LOG_LEVEL=info
```

## Deploy

From `stacks/platform/`:

```bash
docker compose pull homepage
docker compose up -d homepage
```

Port forward/proxy `http://<platform-host>:3002` or via NPM hostname (e.g., `home.klsll.com`).

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
   - Forward to: `http://homepage:3000`
   - Access list: optional (LAN/VPN only recommended)
   - SSL: enable Let's Encrypt/internal certificate if desired

Automation: `ansible-playbook ansible/playbooks/services/update-homepage-proxy.yml` will upsert the DNS + proxy entries defined in `ansible/files/npm/services/homepage.yml`.
