# Gitea Git + Registry

Gitea is our lightweight Git host with a built-in container registry and simple build hooks. The service lives on Unraid so it can talk directly to the private macvlan network and offer SSH, HTTP, and Docker registry endpoints without exposing the host itself.

**Version note:** the role now deploys `gitea/gitea:1.25.4` so we keep pace with the latest CLI tooling and security fixes.

## Architecture
- **Host**: Unraid (`ansible/playbooks/platform/deploy-gitea.yml`) using the `gitea` role. The stack runs on a dedicated macvlan subnet (typically `192.168.20.0/23`).
- **Services**: PostgreSQL handles metadata/state, while the official `gitea/gitea` container receives HTTP/SSH requests and proxies registry traffic.
- **Registry**: Gitea's built-in registry is enabled (`GITEA__registry__ENABLED=true`) and mounted under `/data/registry`. Keep the registry domain (`registry.klsll.com`) behind Nginx Proxy Manager for TLS.
- **Build Integration**: Gitea webhooks can trigger existing CI/CD tooling (Docker Desktop/Windows GPU build agents, Ollama workers, etc.). For simple container builds, push to `registry.klsll.com` and have the build server pull the image via authenticated `docker login` (registry auth is the same as a Git user).

## Networking & TLS
1. Reserve `192.168.20.52` for Gitea and `192.168.20.53` for the registry if you need separate IPs; the playbook currently uses `192.168.20.52` for everything.
2. Pin the PostgreSQL container to `192.168.20.53` so it stays on VLAN20 together with the web/registry services; confirm with `docker network inspect br0`.
3. Update DNS so `code.klsll.com` resolves to the NPM host IP (`192.168.20.50`); NPM will proxy it to `192.168.20.52:3000`. Create two proxy hosts in Nginx Proxy Manager:
   - `code.klsll.com` → `http://192.168.20.52:3000`
   - `registry.klsll.com` → `http://192.168.20.52:5000`
4. Point DNS (Technitium) entries for each hostname at the Unraid macvlan gateway so clients reach the correct service.
4. Run `ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/services/update-gitea-proxy.yml` to publish the proxy hosts and DNS records via the npm role; re-run whenever the host, IP, or domains change.

## Secrets
Store the following fields in a 1Password item named **Gitea Service Credentials** (tag `Ansible`):
- `db_password` – Postgres service password (exported to `GITEA_DB_PASSWORD`).
- `admin_password` – initial Gitea administrator password (exported to `GITEA_ADMIN_PASSWORD`).

Run the sync helper to update `ansible/group_vars/unraid/vault.yml` with those values, or export them as env vars before running the playbook. The role defaults look for `GITEA_DB_PASSWORD`/`GITEA_ADMIN_PASSWORD` first and fall back to the `op` commands.

## Deploy / Run
1. `eval "$(op signin <subdomain>.1password.com <email>)"` (if needed for vault access).
2. `source ansible/scripts/setup-vault-helper-env.sh` to surface `ANSIBLE_VAULT_PASSWORD_FILE`.
3. From the repo root:
   ```bash
   export ANSIBLE_ROLES_PATH=./ansible/roles
   ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/platform/deploy-gitea.yml
   ```
4. Sync proxies/DNS:
   ```bash
   ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/services/update-gitea-proxy.yml
   ```
5. Once finished, configure Nginx Proxy Manager to cover the `code.klsll.com` and `registry.klsll.com` hostnames so TLS is guaranteed.

## Verify
- `curl -fsSL https://code.klsll.com/` should return the login page HTML (or a `200` response).
- `docker exec gitea curl -fsSL http://localhost:3000/api/v1/version` (or similar) on Unraid.
- `curl -fsSL https://registry.klsll.com/v2/_catalog` should return JSON (empty list when no images exist).
- `docker exec --user git gitea gitea admin user list` should show `gitea-admin`; the role now auto-creates the admin user when it’s missing.
- `docker inspect gitea-db | jq -r '.NetworkSettings.Networks.br0.IPAddress'` should return `192.168.20.53`.
- Note: SSH is disabled by default to avoid host port conflicts; rely on HTTPS for Git operations or re-enable/adjust the SSH port later.
- Ensure the proxy hosts exist in Nginx Proxy Manager and Technitium DNS records for `code.klsll.com`/`registry.klsll.com` point to `192.168.20.52` after running `update-gitea-proxy.yml`.

## Rollback
- `ssh root@192.168.20.14 "cd /mnt/user/appdata/stacks/gitea && docker compose down"`
- Optionally delete `/mnt/user/appdata/gitea` contents if you want a clean slate (back up `/mnt/user/appdata/gitea/data` first).
- Re-run the Ansible playbook after fixing configuration or secrets.

## Troubleshooting
- View container logs: `docker logs gitea` / `docker logs gitea-db` on Unraid.
- Confirm DNS/proxy host records match `code.klsll.com` and `registry.klsll.com`.
- Ensure `GITEA_DB_PASSWORD`/`GITEA_ADMIN_PASSWORD` are sourced via the `op` helper when running Ansible.
- If the registry returns `401`, log in with `docker login registry.klsll.com` using a Gitea account before pushing/pulling images.

## Repository Migration Workflow

Use Gitea as the new source of truth for homelab-infra and mirror changes back to GitHub:

1. **Create the repo on Gitea** – log into `https://code.klsll.com`, create a new repository named `homelab-infra`, and choose the same permissions/visibility you need. Record the SSH/HTTPS clone URL shown on the repo home.
2. **Push the existing history** from this workspace:
   ```bash
   git remote add gitea git@code.klsll.com:<your-username>/homelab-infra.git
   git push --all gitea
   git push --tags gitea
   ```
   Replace `<your-username>` with the account you created on `code.klsll.com`. If you prefer HTTPS, use that clone URL and authenticate interactively or via credential helper.
3. **Point GitHub at Gitea** – in the newly created Gitea repo, open **Settings → Mirroring** and configure a push mirror to the GitHub `git@github.com:HavartiBard/homelab-infra.git` (or whichever GitHub target). This keeps GitHub in sync with Gitea while Gitea remains canonical.
4. **Update local remotes** so you work against Gitea by default:
   ```bash
   git remote set-url origin git@code.klsll.com:<your-username>/homelab-infra.git
   git remote add upstream git@github.com:HavartiBard/homelab-infra.git
   ```
   Use `origin` for the Gitea repo and `upstream` (or `github`) as the mirror target if you still want to inspect GitHub history locally.
5. **Verify and monitor** – after pushing, ensure `code.klsll.com/homelab-infra` shows your commits. Watch the mirror log in Gitea to confirm GitHub pushes succeed, and update any CI/webhook integrations to the new Gitea URLs (e.g., `https://code.klsll.com/api/v1/...`).

Keep the mirrored GitHub repo for external collaborators or as an archive, but run CI/builds against `code.klsll.com` moving forward so everything stays consistent with your self-hosted registry and secrets workflows.

## Preferred Remote

Clone/push via `ssh://git@gitea.klsll.com:2222/Homelab/homelab-infra.git` so all local work targets the self-hosted Gitea instance directly. Update your `origin` remote if it still points at `github.com` or `localhost:2222`, and treat GitHub only as the downstream mirror.

> **Proxy TLS note**: NPM presents `https://code.klsll.com/` using the `klsll-wildcard` certificate while speaking plain `http` on the backend to `192.168.20.52:3000`. The role now sets `scheme: http` but attaches the wildcard cert with `ssl_forced: true`, which keeps the public endpoint secure without forcing Gitea itself to run HTTPS internally.
