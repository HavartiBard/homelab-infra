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

| Slug | Env file | Used by |
|------|----------|---------|
| `goudai` | `ansible/envs/goudai.env` | `playbooks/ai/deploy-open-webui.yml --limit goudai` |

This table grows as more services are migrated off `vault.yml` (see
`docs/plans/2026-03-01-vault-migration.md` and its successor for migration status).

## Running Docker Compose stacks that need secrets

```bash
cd stacks/<name>
op run --env-file=op.env -- docker compose up -d
```

`op.env` (not `.env` — see below) is committed to git and contains only `op://` references.

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
