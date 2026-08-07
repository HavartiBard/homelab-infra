# Dev Environment Setup Checklist

Run this right after cloning `homelab-infra` onto a new machine (dev VM, fresh container, etc.)
and starting an agent session there. Each item has a concrete check — run it, don't assume.
Stop and ask the user for anything that fails and isn't yours to fix (private keys, tokens).

## 1. Git identity

A fresh machine has no default — commits will fail without this.

```bash
git config user.name && git config user.email
```
If either is empty: ask the user what to set (`git config user.name "..."` /
`git config user.email "..."`, local to this repo unless they say otherwise).

## 2. Git push capability

```bash
git remote -v
```
Then confirm you can actually push. Two ways this repo has worked in practice:
- **SSH**: `ssh -T git@gitea.klsll.com` succeeds (needs `~/.ssh/id_ed25519_homelab` or an
  equivalent key registered with Gitea).
- **HTTPS + token**: `GITEA_TOKEN` is set (e.g. sourced from `~/.env`), used as
  `git -c http.extraHeader="Authorization: token ${GITEA_TOKEN}" push ...`.

If neither works, ask the user which they want to set up — don't guess or skip straight to one.

## 3. 1Password CLI + the one bootstrap secret

```bash
which op
op read "op://AI Wedge/Unraid GraphQL - Wedge/credential" > /dev/null && echo OK
```
If `op` is missing: install it (Linux install steps are in
`ansible/playbooks/bootstrap/bootstrap-ubuntu.yml`; Windows/WSL2 steps are in
`docs/windows-ssh-setup.md`).
If the read fails: `OP_SERVICE_ACCOUNT_TOKEN` isn't set or is wrong — ask the user for it (from
1Password, service account `ansible-automation-readonly`), export it in the shell profile
(`~/.bashrc`/`~/.zshrc`), and re-test. See `docs/secrets-management.md` for the full picture —
this is the *only* secret that needs to exist outside 1Password itself.

**Note:** there is no `~/.vault-pass` requirement anymore — `vault.yml` was decommissioned. If you
see a doc or your own memory mention it, it's stale.

## 4. Ansible + collections

```bash
ansible-playbook --version
ansible-galaxy collection list 2>/dev/null | grep -E "community.docker|community.general"
```
If missing:
```bash
sudo apt install ansible
ansible-galaxy collection install community.docker community.general
```

## 5. SSH key for managed hosts

```bash
ls -la ~/.ssh/id_ed25519_homelab
```
This is the private key Ansible uses to reach Unraid/Proxmox/DNS hosts (`inventory/hosts.yml`).
It is **not** an `op://`-resolvable secret in this repo's current setup — get it from the user or
copy it from an existing trusted machine. Don't generate a new one; it needs to already be
authorized on the target hosts.

## 6. Docker + Compose plugin (only if you'll run/test `stacks/*` or `docker/dev-environment`)

```bash
docker compose version
```
Not needed for pure Ansible/playbook work.

## 7. Network reachability

```bash
curl -sf -o /dev/null -w "%{http_code}\n" http://192.168.20.14:6976/mcp
```
Confirms LAN/VPN connectivity to the `192.168.20.x` range, where the Gitea/GSuite MCP servers and
every managed host live. A non-2xx/expected response here usually means you're not on the LAN or
VPN, not a repo config problem.

## Summary table

| # | Check | Command | If it fails |
|---|-------|---------|-------------|
| 1 | Git identity | `git config user.name && git config user.email` | Ask user, set locally |
| 2 | Git push | `ssh -T git@gitea.klsll.com` or `GITEA_TOKEN` set | Ask user which to set up |
| 3 | 1Password | `op read "op://AI Wedge/Unraid GraphQL - Wedge/credential"` | Install `op`, ask for `OP_SERVICE_ACCOUNT_TOKEN` |
| 4 | Ansible | `ansible-playbook --version` | `apt install ansible` + collections |
| 5 | Homelab SSH key | `ls ~/.ssh/id_ed25519_homelab` | Ask user, don't generate new |
| 6 | Docker (optional) | `docker compose version` | Install if testing stacks locally |
| 7 | Network | `curl http://192.168.20.14:6976/mcp` | Confirm LAN/VPN |
