# Secrets Management

This repo uses **1Password Environments** — `op run --env-file=<file> -- <command>` — as the
single mechanism for getting secrets into playbooks, containers, and AI agent sessions.
Every committed env file (`ansible/envs/*.env`, `stacks/*/op.env`, `docker/dev-environment/op.env`)
contains **only `KEY=op://vault/item/field` references**, never real secret values — `op run`
resolves them into the child process's environment at invocation time and never writes secret
material to disk. This is enforced by CI (`.gitea/workflows/env-guard.yml`).

## History

This is the third secrets architecture this repo has used:

1. **2026-01-24**: Ansible Vault files → direct `op read` via a 1Password service account
   (`docs/migration/vault-to-service-account.md`, now superseded).
2. **2026-03-01**: migrated back to Ansible Vault (`ansible/group_vars/all/vault.yml`, decrypted
   via `~/.vault-pass`) — `docs/plans/2026-03-01-vault-migration.md`.
3. **2026-06-12**: `vault.yml` was briefly committed in plaintext before a CI guard caught the
   class of mistake going forward. Secrets exposed at the time were rotated.
4. **2026-07 (this doc)**: standardized on 1Password Environments repo-wide, retiring
   `vault.yml`/`~/.vault-pass` entirely. The recurring problem with the first two approaches was
   an undocumented, unautomated way to get a second, non-1Password secret (the vault password)
   onto a new host or agent session. This approach has exactly one such secret instead of two.
   `vault.yml` and `.gitea/workflows/vault-guard.yml` have since been deleted — every consumer was
   confirmed migrated first (repo-wide grep for `vault_*` came back empty outside the file itself).

## The one bootstrap secret: `OP_SERVICE_ACCOUNT_TOKEN`

Every host or AI agent session that needs to run a playbook, deploy a stack, or look up an ad hoc
credential needs exactly one thing in its environment: `OP_SERVICE_ACCOUNT_TOKEN`.

- Service account: `ansible-automation-readonly`
- Scope: read-only (`read_items`), limited to the `AI Wedge` vault
- Revocable instantly from the 1Password console; no re-encryption or sync step needed elsewhere

### Setting up a new host

```bash
# Install the 1Password CLI
# Linux: handled automatically by ansible/playbooks/bootstrap/bootstrap-ubuntu.yml
# Windows/WSL2: see docs/windows-ssh-setup.md

echo 'export OP_SERVICE_ACCOUNT_TOKEN="ops-YOUR-TOKEN-HERE"' >> ~/.bashrc
source ~/.bashrc

# Smoke test — should print the value without prompting for signin
op read "op://AI Wedge/Unraid GraphQL - Wedge/credential"
```

### How this reaches AI agent sessions

Claude Code, Codex, and other coding agents inherit the environment of the shell that launched
them. Once `OP_SERVICE_ACCOUNT_TOKEN` is exported in a host's shell profile, every agent session
started from that shell gets it automatically — there is no separate per-agent credential file or
bootstrap step. If the token is added or rotated, **restart the agent session** to pick up the new
environment; an already-running session keeps whatever env it started with.

## Ad hoc credential lookups (for AI agents)

For one-off questions like "what's the Grafana admin password," agents use `op read` directly:

```bash
op read "op://AI Wedge/Grafana Admin/password"
```

This is unchanged from before this migration — it already followed the least-privilege,
resolve-at-use-time pattern 1Password recommends for AI agents. Only the surrounding docs
describing it were out of date, which this doc replaces.

## Running playbooks that need secrets

Use the wrapper script instead of invoking `ansible-playbook` directly:

```bash
cd ansible
./scripts/run-playbook.sh <slug> playbooks/<group>/<playbook>.yml --limit <host> --check --diff
```

`<slug>` maps to `ansible/envs/<slug>.env` — one file per playbook-invocation unit, containing the
`op://` references that playbook's role(s) need. Playbooks that don't need any secrets are
unaffected and keep running via plain `ansible-playbook ...` as before.

`ansible/envs/common.env` is merged into *every* invocation automatically, in addition to the
slug-specific file. It holds cross-cutting secrets needed by roles that many other
playbooks/roles include as a side effect — e.g. `netbox-service` (used by ~20 deploy playbooks to
register themselves in NetBox) needs `NETBOX_TOKEN`, which isn't specific to any one service.
Don't duplicate `common.env`'s contents into individual `<slug>.env` files.

| Slug | Env file | Used by |
|------|----------|---------|
| `adguard` | `ansible/envs/adguard.env` | `playbooks/dns/deploy-adguard-config.yml` |
| `agent-cp` | `ansible/envs/agent-cp.env` | `playbooks/ai/deploy-agent-cp.yml` |
| `camofox-browser` | `ansible/envs/camofox-browser.env` | `playbooks/jetson/deploy-camofox-browser.yml` |
| `dns-dhcp` | `ansible/envs/dns-dhcp.env` | `playbooks/dns/provision-dns-dhcp.yml`, `provision-dns-dhcp-services.yml` |
| `gitea` | `ansible/envs/gitea.env` | `playbooks/platform/deploy-gitea.yml` |
| `gitea-mcp` | `ansible/envs/gitea-mcp.env` | `playbooks/mcp/deploy-gitea-mcp.yml` |
| `gitea-runner` | `ansible/envs/gitea-runner.env` | `playbooks/platform/deploy-gitea-runners.yml` |
| `goudai` | `ansible/envs/goudai.env` | `playbooks/ai/deploy-open-webui.yml --limit goudai` |
| `homelab-mcp` | `ansible/envs/homelab-mcp.env` | `playbooks/mcp/deploy-homelab-mcp.yml` |
| `homepage` | `ansible/envs/homepage.env` | `playbooks/services/deploy-homepage.yml` |
| `icloud-mcp` | `ansible/envs/icloud-mcp.env` | `playbooks/mcp/deploy-icloud-mcp.yml` |
| `immich` | `ansible/envs/immich.env` | `playbooks/platform/deploy-immich.yml` |
| `litellm` | `ansible/envs/litellm.env` | `playbooks/ai/deploy-litellm.yml` (DB password still a TODO — no 1Password item yet) |
| `netbox` | `ansible/envs/netbox.env` | `playbooks/platform/deploy-netbox.yml`, `seed-netbox.yml` (DB password/secret key still TODOs) |
| `npm` | `ansible/envs/npm.env` | `playbooks/platform/deploy-npm.yml`, `services/update-npm-proxy-host.yml` |
| `observability` | `ansible/envs/observability.env` | `playbooks/observability/deploy-observability.yml` |
| `obsidian` | `ansible/envs/obsidian.env` | `playbooks/mcp/deploy-obsidian-stack.yml` |
| `paperless` | `ansible/envs/paperless.env` | `playbooks/services/deploy-paperless.yml` |
| `paperless-ai` | `ansible/envs/paperless-ai.env` | `playbooks/services/deploy-paperless-ai.yml` |
| `proxmox-mcp` | `ansible/envs/proxmox-mcp.env` | `playbooks/mcp/deploy-proxmox-mcp.yml` |
| `restic-backup` | `ansible/envs/restic-backup.env` | `playbooks/platform/deploy-restic-backup.yml` |
| `soullayer` | `ansible/envs/soullayer.env` | `playbooks/mcp/deploy-soullayer.yml` |
| `technitium` | `ansible/envs/technitium.env` | `playbooks/dns/configure-technitium-settings.yml` |
| `unraid-mcp` | `ansible/envs/unraid-mcp.env` | `playbooks/mcp/deploy-unraid-mcp.yml`, `services/deploy-homepage.yml` |
| `webtrees` | `ansible/envs/webtrees.env` | `playbooks/platform/deploy-webtrees.yml` |

`ansible/envs/common.env` isn't in this table since it's merged automatically into every
invocation (see above), not selected via a slug.

A handful of secrets above are intentionally left unresolved (commented out with a `TODO` in
their env file) because no 1Password item exists for them yet — `agent-cp` (5 of 8 secrets),
`litellm` (DB password), `netbox` (DB password, Django secret key). Those services fail closed
with a clear assert message until the item is created; check the env file itself for the exact
gap.

## Running Docker Compose stacks that need secrets

```bash
cd stacks/<name>
op run --env-file=op.env -- docker compose up -d
```

`op.env` (not `.env` — see below) is committed to git and contains only `op://` references.
`stacks/platform`, `stacks/gpu-worker`, and `docker/dev-environment` each have a couple of secrets
left as TODOs the same way (no 1Password item yet) — check each `op.env` for specifics.

### Why `op.env`, not `.env`

This repo's `.gitignore` ignores any file literally named `.env` (to protect a human's local,
filled-in secrets), with an exception only for `*.env.example` templates. A file named `op.env` is
a different basename, so it's trackable in git with zero `.gitignore` changes — and the name
itself signals "op:// references only, safe to commit," distinct from a real `.env` a human might
still hold locally for non-secret overrides.

### Why not `op inject`

`op inject` materializes a plaintext `.env` snapshot on disk from a template. That snapshot goes
stale silently if the underlying 1Password value is rotated, and re-creates the exact "a file that's
supposed to be safe but can be accidentally committed" risk that caused the 2026-06-12 incident.
`op run` resolves secrets into the subprocess environment only, for the lifetime of that one
invocation, and never writes them to disk.

## Rotating a secret

Change the value in 1Password. The next `op run` or `op read` invocation picks it up immediately —
no vault re-encryption, no sync script, no redeploy of a "secrets" service required.
