# Handoff Notes — 2026-02-28

## Context

Raclette (OpenClaw agent on Jetson) had several blockers preventing it from deploying a research dashboard. This session fixed the infrastructure issues and unblocked raclette. Raclette is now working on `feature/deploy-research-dashboard` in this repo.

## What Was Fixed This Session

### 1. `.env_container` not surviving container restarts (PR #52, merged)
- **Problem:** `.env_container` was copied into the container via `docker cp` on each deploy — lost on every container restart/image update.
- **Fix:** Mounted `/home/james/.env_container:/home/node/.env_container:ro` as a volume in `docker-compose.yml`. Host file is managed by `bootstrap-jetson.yml`.
- **Files:** `ansible/files/jetson/openclaw/docker-compose.yml`, `ansible/playbooks/jetson/deploy-openclaw.yml`

### 2. New OpenClaw image required `gateway.controlUi` config (PR #53, merged)
- **Problem:** New upstream image version broke on start: `non-loopback Control UI requires gateway.controlUi.allowedOrigins`.
- **Fix:** Added `"controlUi": {"dangerouslyAllowHostHeaderOriginFallback": true}` to `openclaw.json.j2` seed template, and patched live config in-place.
- **Files:** `ansible/files/jetson/openclaw/config/openclaw.json.j2`

### 3. `.vault-pass` missing from container (PR #54, merged)
- **Problem:** Ansible vault commands inside the container failed — `/home/node/.vault-pass` didn't exist.
- **Fix:** Mounted `/home/james/.vault-pass:/home/node/.vault-pass:ro` as a volume. Added deployment task to `bootstrap-jetson.yml` to write it from the controller's `~/.vault-pass`.
- **Note:** If the host file is replaced (not edited in-place), the container needs `docker compose restart openclaw` to re-bind the mount.
- **Files:** `ansible/files/jetson/openclaw/docker-compose.yml`, `ansible/playbooks/jetson/bootstrap-jetson.yml`

### 4. mcporter baked into image (not tracked in a PR — run manually)
- **Problem:** `docker compose pull` overwrites the local image tag, wiping the mcporter layer. After each image update, `add-mcporter-to-openclaw.yml` must be re-run.
- **Fix (this session):** Ran `ansible-playbook playbooks/services/add-mcporter-to-openclaw.yml --limit jetson.lab -v`.
- **Ongoing:** This must be re-run after every `docker compose pull`. Consider integrating it into `deploy-openclaw.yml` after the pull step.

### 5. Gitea `feature/deploy-research-dashboard` branch created
- Raclette couldn't push a new branch (push-to-create disabled on Gitea).
- Branch created via API: `feature/deploy-research-dashboard` off `main`.

## Current State of Jetson / OpenClaw

| Check | Status |
|-------|--------|
| Container running | `openclaw` Up, `ghcr.io/openclaw/openclaw:latest` |
| mcporter version | 0.7.3 |
| `/home/node/.env_container` | ✅ mounted from host |
| `/home/node/.vault-pass` | ✅ mounted from host (updated this session) |
| `/home/node/.ssh/id_ed25519_homelab` | ✅ present |
| `tools.exec.host` | `gateway` |
| Slack | Connected (socket mode) |

## Volume Mounts (docker-compose.yml)

```
/home/james/.openclaw        → /home/node/.openclaw
/home/james/bots/raclette    → /workspace
/var/run/docker.sock         → /var/run/docker.sock
/home/james/.env_container   → /home/node/.env_container   (ro)
/home/james/.vault-pass      → /home/node/.vault-pass      (ro)
```

## Raclette's In-Progress Work

Raclette is working on `feature/deploy-research-dashboard` in this repo. It has:
- Pushed commits to that branch
- Needs to open a PR when done

## Known Issues / Watch-Outs

### mcporter wiped by image updates
Every `docker compose pull` in `deploy-openclaw.yml` replaces the local image, losing the mcporter layer. After any image update run:
```bash
cd ansible
ansible-playbook playbooks/services/add-mcporter-to-openclaw.yml --limit jetson.lab -v
```

### Director sets `tools.exec.host=sandbox` during sessions
Director may push `tools.exec.host=sandbox` when starting an agent session, overriding `gateway` mode. The deploy playbook enforces `gateway` mode, but only at deploy time. The sandbox container (`openclaw-sandbox:bookworm-slim`) does not have mcporter. If raclette reports exec failures, re-run:
```bash
ansible-playbook playbooks/jetson/deploy-openclaw.yml --limit jetson.lab --skip-tags image -v
```

### `.vault-pass` bind mount inode behaviour
If the vault-pass file on the Jetson is replaced (e.g. `echo x > ~/.vault-pass`), the container's bind mount points to the old inode. Restart openclaw after any vault-pass rotation:
```bash
ssh james@192.168.20.169 "cd /home/james/docker/openclaw && docker compose restart openclaw"
```

## Key Playbooks

| Task | Command |
|------|---------|
| Full deploy (image pull) | `ansible-playbook playbooks/jetson/deploy-openclaw.yml --limit jetson.lab -v` |
| Config-only deploy (no pull) | `ansible-playbook playbooks/jetson/deploy-openclaw.yml --limit jetson.lab --skip-tags image -v` |
| Re-add mcporter after image update | `ansible-playbook playbooks/services/add-mcporter-to-openclaw.yml --limit jetson.lab -v` |
| Bootstrap Jetson (first-time or re-run) | `ansible-playbook playbooks/jetson/bootstrap-jetson.yml -e target_hosts=jetson.lab --limit jetson.lab -v` |
