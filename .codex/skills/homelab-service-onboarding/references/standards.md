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
- Never hardcode secrets — roles read them via `lookup('ansible.builtin.env', 'VAR_NAME')` (no
  fallback), resolved at invocation time from `ansible/envs/<name>.env` via `op run`. See
  `docs/secrets-management.md`.
- No plaintext secrets in repo; committed env files hold only `KEY=op://vault/item/field`
  references, enforced by CI (`env-guard`)

## Container configuration
- Set `TZ: America/Phoenix` in compose env for all containers
- Unraid icon: set `net.unraid.docker.icon` label — source icon URL from `https://dashboardicons.com/`
- Stateful volumes at `/mnt/user/appdata/<name>` (Unraid default until issue #31 is resolved)

## Documentation
- Rollback: document exact rollback command in Obsidian catalog entry
