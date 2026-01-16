# Nginx Proxy Manager (Unraid Dedicated IP)

Allows deploying Nginx Proxy Manager with a host-grade macvlan/ipvlan IP so the UI and proxy ports never touch the default bridge network.

## Network requirements

- Use a dedicated IP inside the `192.168.20.0/23` subnet (netmask `255.255.254.0`). The VLAN20 gateway is `192.168.20.1`, and every host from `192.168.20.1` through `192.168.21.254` shares it.
- Attach the container to the existing VLAN20 `br0` macvlan network, which already claims `192.168.20.0/23`; do not create another overlapping network.
- The stack expects this dedicated network to exist already (see the Ansible playbook). Set `NPM_NETWORK_NAME` to match the driver-managed network and provide a static `NPM_IP` inside the `/23`.

## Configuration

Copy `.env.example` to `.env` and customize the following values:

| Variable | Description |
|----------|-------------|
| `NPM_NETWORK_NAME` | External Docker network name (e.g., `br0`). |
| `NPM_IP` | Static IP for NPM inside `192.168.20.0/23`. Must not be the network or broadcast address. |
| `NPM_APPDATA_ROOT` | Host path for `data`, `letsencrypt`, and any custom certs. Defaults to `/mnt/user/appdata/npm`. |
| `NPM_TIMEZONE` | Timezone for the container (`America/Phoenix`). |
| `NPM_UI_PORT` | HTTP UI port (default `81`). Used for the health check only. |
| `NPM_DNS_PRIMARY` | Primary DNS resolver for ACME/DNS lookups (default `1.1.1.1`). |
| `NPM_DNS_SECONDARY` | Secondary DNS resolver (default `1.0.0.1`). |
| `NPM_ICON` | Unraid UI icon URL (e.g., a hosted PNG). |
| `NPM_WEBUI_URL` | Unraid UI link target (e.g., `http://192.168.20.50:81`). |

If you plan to use an external issuer service for DNS-01 certificates, point it at `${NPM_APPDATA_ROOT}/certs` so NPM can import the PEM/KEY pair directly.

## Proxy host automation (NPM API + Technitium)

This playbook can create NPM proxy hosts (with certs) and DNS records in Technitium.

1. Copy `ansible/files/npm/services/npm.yml.example` to `ansible/files/npm/services/npm.yml` and edit it.
2. Export credentials on the controller:
   - `export NPM_ADMIN_EMAIL='admin@example.com'`
   - `export NPM_ADMIN_PASSWORD='CHANGEME'`
   - `export TECHNITIUM_ADMIN_PASSWORD='CHANGEME'`
3. Ensure `npm_manage_proxies: true` and `npm_manage_dns: true` in `ansible/group_vars/unraid.yml`.
4. Run `ansible-playbook playbooks/platform/deploy-npm-unraid.yml`.

Notes:
- NPM API base URL defaults to `http://<npm_ip>:<npm_ui_port>/api`.
- Technitium API URL defaults to `http://192.168.20.2:5380`; override if your primary DNS differs.
- Proxy hosts in the config are upserted: existing hosts with matching primary domain are updated.
- Create one YAML file per service in `ansible/files/npm/services/` to keep ownership clear.

## Deploy

1. Confirm the VLAN20 `br0` network exists on Unraid (`docker network inspect br0`); the playbook will reuse it.
2. Reserve a free `192.168.20.x` IP via Technitium so `npm_ip` can anchor to that address and you avoid collisions.
3. Set `NPM_ICON` to a reachable icon URL and `NPM_WEBUI_URL` to the NPM UI address for Unraid UI metadata.
4. Update `.env` with your subnet IP, network name, and appdata paths.
5. `docker compose pull`
6. `docker compose up -d`

### Inventory snippet

This stack expects the Unraid host to be defined in `ansible/inventory/hosts.yml`:

```yaml
unraid-server:
  ansible_host: 192.168.20.14
  ansible_user: root
  ansible_ssh_private_key_file: ~/.ssh/id_ed25519_homelab
```

## Verify

- `ping <NPM_IP>` (e.g., `ping 192.168.20.50`)
- `curl http://<NPM_IP>:${NPM_UI_PORT:-81}/`
- `docker compose ps`
- `docker network inspect ${NPM_NETWORK_NAME}`

## Backups

Copy the `data`, `letsencrypt`, and `certs` directories off the Unraid server. They store SQLite state, rendered certs, and any external issuer output.

## Known caveats

- Macvlan networks isolate the host from containers; prefer ipvlan if you need host↔container networking.
- The parent interface (usually `br0`) must be trunked to the LAN and free of conflicting IPs.
- Do not rely on Technitium’s internal DNS zone for ACME TXT records; public DNS providers (e.g., Cloudflare) must serve the `_acme-challenge` entry for the wildcard.
- When `enable_external_acme_issuer` is enabled via the Ansible role, the optional issuer container publishes certs to the shared `certs/` directory, which NPM can import using the “Custom Certificate” flow.

## Next steps for certificates

1. Use NPM’s built-in ACME (DNS-01) option with `*.klsll.com`. DNS-01 lets you issue wildcard certs without opening inbound HTTP ports.
2. Update `_acme-challenge.klsll.com` through your **public** authoritative DNS provider—AdGuard/Technitium internal zones are not publicly visible and will cause ACME failures.
3. Optionally, enable the Ansible `enable_external_acme_issuer` variable to run a lego/acme.sh container that writes PEM files into `certs/`. Point NPM’s Custom Certificate dialog at those files after issuance.
