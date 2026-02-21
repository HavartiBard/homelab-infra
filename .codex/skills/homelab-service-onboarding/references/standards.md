<!-- This file defines constraints and rules, not a full procedure. See SKILL.md for the complete phase sequence. -->
# Homelab Service Standards (all classes)

These standards apply to every service regardless of class.

## Deployment
- Run from a feature branch — never `main`
- For Unraid targets: use `ansible.builtin.raw` (no Python available)
- Use `restart: unless-stopped` in all compose files
- Resource limits: always set `deploy.resources.limits` (memory + cpus)
- Idempotence gate: rerun `--check --diff` after apply, expect `changed=0`

## Secrets
- Never hardcode secrets — use `op read "op://AI Wedge/<item>/<field>"` in `defaults/main.yml`
- No plaintext secrets in repo; placeholders use `CHANGEME_*`

## Container configuration
- Set `TZ: America/Phoenix` in compose env for all containers
- Unraid icon: set `net.unraid.docker.icon` label — source icon URL from `https://dashboardicons.com/`
- Stateful volumes at `/mnt/user/appdata/<name>` (Unraid default until issue #31 is resolved)

## Documentation
- Rollback: document exact rollback command in Obsidian catalog entry
