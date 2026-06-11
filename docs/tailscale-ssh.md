# Tailscale SSH Bootstrap

Use this when you want remote SSH access without exposing port `22` on the Orbi.

There are three supported paths in this repo:

- a real Ubuntu VM or workstation: use `ansible/playbooks/bootstrap/deploy-tailscale.yml`
- a dedicated Proxmox subnet-router LXC: use `ansible/playbooks/bootstrap/provision-tailscale-router.yml`
- the containerized `dev-box` environment on Unraid: use the Tailscale sidecar profile in `docker/dev-environment/docker-compose.yml`

## What it does

`ansible/playbooks/bootstrap/deploy-tailscale.yml`:

- adds the official Tailscale apt repository for Ubuntu
- installs `tailscale` and `tailscale-archive-keyring`
- enables and starts `tailscaled`
- optionally runs `tailscale up --ssh` when `TAILSCALE_AUTH_KEY` is provided

The playbook is intentionally scoped by `target_hosts` so it only touches the host you name.

## Prerequisites

1. Add the VM to `ansible/inventory/hosts.yml`.
2. Ensure the target host is reachable over LAN SSH first.
3. Use a host with `systemd` and a working TUN device.

## Inventory example

```yaml
workstations:
  hosts:
    dev-box:
      ansible_host: 192.168.20.60
      ansible_user: james
      ansible_connection: ssh
      ansible_ssh_private_key_file: ~/.ssh/id_ed25519_homelab
      ansible_python_interpreter: /usr/bin/python3
```

## Run it

### Real Ubuntu VM or workstation

Interactive login flow:

```bash
cd ansible
ansible-playbook playbooks/bootstrap/deploy-tailscale.yml \
  --limit dev-box \
  -e target_hosts=dev-box
```

Then on the VM:

```bash
sudo tailscale up --ssh --hostname dev-box
```

Non-interactive login with an auth key:

```bash
cd ansible
TAILSCALE_AUTH_KEY=tskey-... \
ansible-playbook playbooks/bootstrap/deploy-tailscale.yml \
  --limit dev-box \
  -e target_hosts=dev-box
```

### Dedicated Proxmox subnet router

The default inventory target is `ts-router-01`. Its Proxmox and network settings live in
`ansible/inventory/host_vars/ts-router-01.yml`.

Interactive login flow:

```bash
cd ansible
ansible-playbook playbooks/bootstrap/provision-tailscale-router.yml
```

Non-interactive login with an auth key:

```bash
cd ansible
TAILSCALE_AUTH_KEY=tskey-... \
ansible-playbook playbooks/bootstrap/provision-tailscale-router.yml
```

After `tailscale up` succeeds, approve the advertised routes in the Tailscale admin UI. The
default router host advertises a minimal route set (see `ansible/inventory/host_vars/ts-router-01.yml`):

- `192.168.20.4/32`, `192.168.20.5/32` — AdGuard DNS
- `192.168.20.50/32` — Platform VM (NPM, all `*.klsll.com` portals)

To make web portals work with the same URLs as on the LAN, also add a **split DNS** rule in
the admin console (DNS → Nameservers → Custom): domain `klsll.com` → `192.168.20.4` and
`192.168.20.5`. Remote clients then run with `--accept-routes --accept-dns` (mobile apps:
enable "Use Tailscale DNS") and every NPM-fronted portal resolves and loads with its
existing certificate. NPM remains the only web proxy; no other LAN host runs Tailscale.

### Containerized `dev-box` on Unraid

Populate `docker/dev-environment/.env` with:

```bash
DEV_COMPOSE_PROFILES=tailscale
TAILSCALE_AUTHKEY=tskey-...
TAILSCALE_HOSTNAME=dev-box
TAILSCALE_EXTRA_ARGS=--ssh
```

Then deploy:

```bash
cd ansible
DEV_COMPOSE_PROFILES=tailscale \
ansible-playbook playbooks/bootstrap/deploy-dev-environment.yml --limit unraid
```

The Tailscale sidecar shares the `dev-environment` network namespace, so remote SSH lands on the existing SSH daemon running in `dev-environment`.

## Verify

On the VM:

```bash
systemctl is-active tailscaled
tailscale status
tailscale ip -4
```

From another device on your tailnet:

```bash
ssh james@dev-box
```

For the sidecar deployment on Unraid, also check:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}" | grep dev-environment
docker logs dev-environment-tailscale --tail 50
```

## Rollback

To disconnect the node but keep the package installed:

```bash
sudo tailscale down
```

To remove Tailscale entirely:

```bash
sudo apt-get remove -y tailscale tailscale-archive-keyring
sudo rm -f /etc/apt/sources.list.d/tailscale.list
sudo rm -f /usr/share/keyrings/tailscale-archive-keyring.gpg
```
