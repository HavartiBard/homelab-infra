# Migration: Vault Files → 1Password Service Account

**Date**: January 24, 2026
**Status**: Completed

## What Changed

- ✅ Eliminated Ansible vault files (`group_vars/*/vault.yml`)
- ✅ Removed vault password management (`ansible-vault-password.sh`, `setup-vault-helper-env.sh`)
- ✅ Deprecated vault sync script (`sync-1password-to-vault.py`)
- ✅ Migrated to 1Password Service Account with direct credential lookups
- ✅ All 10 Ansible roles now use `op read` for direct 1Password lookups

## Why

**Problems with old approach**:
- Required `op signin` before every playbook run
- Vault files could drift from 1Password source of truth
- AI agents (Claude/Codex) couldn't access credentials
- Complex workflow with multiple authentication steps
- Manual credential export tedious

**Benefits of new approach**:
- ✅ Single source of truth (1Password only)
- ✅ No manual signin needed (service account auto-authenticates)
- ✅ AI agents can read credentials programmatically
- ✅ Simpler developer workflow
- ✅ Immediate access to new credentials (no sync step)

## New Workflow

**Before** (old):
```bash
eval $(op signin)
source ansible/scripts/setup-vault-helper-env.sh
export NOTION_TOKEN=$(op read "op://AI Wedge/Notion MCP Integration/credential")
ansible-playbook playbooks/mcp/deploy-notion-mcp-public.yml
```

**After** (new):
```bash
ansible-playbook playbooks/mcp/deploy-notion-mcp-public.yml
```

That's it! Credentials are automatically fetched via service account.

## Setup Instructions

### Verify Service Account Token

Ensure `OP_SERVICE_ACCOUNT_TOKEN` is in your environment:

```bash
# Check it's set
echo $OP_SERVICE_ACCOUNT_TOKEN
# Should output: ops-... (service account token)

# Test it works without signin
bash -c 'op read "op://AI Wedge/Notion MCP Integration/credential"'
# Should output the Notion token without prompting
```

### Running Playbooks

All playbooks work identically - credentials are auto-fetched:

```bash
cd ansible

# Run normally - no setup required
ansible-playbook playbooks/mcp/deploy-notion-mcp-public.yml --check

# Credentials are automatically available
ansible-playbook playbooks/mcp/deploy-notion-mcp-public.yml --diff
```

### Override Credentials for Testing

```bash
# Override a specific credential via environment variable
NOTION_TOKEN="test-token" \
  ansible-playbook playbooks/mcp/deploy-notion-mcp-public.yml --check
```

## Rollback Procedure

If you need to rollback to vault files:

```bash
# Find the most recent backup
BACKUP_DIR=$(ls -td ~/.ansible-vault-backup-* | head -1)
echo "Using backup: $BACKUP_DIR"

# Restore vault files
cp "$BACKUP_DIR"/*.yml ansible/group_vars/*/
cp "$BACKUP_DIR"/.ansible_vault_password ~/

# Restore helper scripts from git history
git log --all --full-history -- ansible/scripts/setup-vault-helper-env.sh
git checkout <commit-hash> -- ansible/scripts/setup-vault-helper-env.sh
git checkout <commit-hash> -- ansible/scripts/ansible-vault-password.sh

# Revert role defaults
git checkout <commit-hash> -- ansible/roles/*/defaults/main.yml

# Use old workflow
source ansible/scripts/setup-vault-helper-env.sh
ansible-playbook playbooks/...
```

Backup vault files are kept in `~/.ansible-vault-backup-YYYYMMDD-HHMMSS/` directories for 30 days.

## Troubleshooting

### Error: "unauthorized" when running playbook

```bash
# Verify OP_SERVICE_ACCOUNT_TOKEN is set
echo $OP_SERVICE_ACCOUNT_TOKEN
# Should output ops-... token

# Test service account can read credentials
op read "op://AI Wedge/Notion MCP Integration/credential"
# Should succeed without signin

# Reload shell to pick up new env vars
source ~/.bashrc
```

### Error: "item not found"

```bash
# Verify item exists in 1Password
op item list --tags Ansible

# Check item is in "AI Wedge" vault
op vault list | grep "AI Wedge"

# Verify item is tagged "Ansible"
op item get "Notion MCP Integration" --tags
```

### Claude/Codex can't read credentials

```bash
# Verify OP_SERVICE_ACCOUNT_TOKEN is in environment
echo $OP_SERVICE_ACCOUNT_TOKEN

# Claude Code inherits environment from parent shell
# Restart Claude Code session if token was just added
```

### Playbook fails with empty credential

```bash
# This means the OP lookup failed silently (returned empty string)
# Check:
1. Service account has access to "AI Wedge" vault
2. Item exists and is tagged "Ansible"
3. OP_SERVICE_ACCOUNT_TOKEN is set
4. Network connectivity to 1Password
```

## Service Account Details

- **Name**: `ansible-automation-readonly`
- **Vault**: `AI Wedge` only (no other vault access)
- **Permissions**: `read_items` only (cannot write/delete)
- **Token location**: `~/.bashrc` as `OP_SERVICE_ACCOUNT_TOKEN`
- **Expiry**: Can be revoked instantly in 1Password console

## Available Credentials

All items in "AI Wedge" vault tagged "Ansible":

| Credential | 1Password Item | Field | op:// Reference |
|------------|----------------|-------|-----------------|
| Notion Token | Notion MCP Integration | credential | `op://AI Wedge/Notion MCP Integration/credential` |
| OP Service Account | OP_SERVICE_ACCOUNT_TOKEN | credential | `op://AI Wedge/OP_SERVICE_ACCOUNT_TOKEN/credential` |
| Portainer Token | Portainer API Token | credential | `op://AI Wedge/Portainer API Token/credential` |
| Unraid API Key | Unraid GraphQL - Wedge | credential | `op://AI Wedge/Unraid GraphQL - Wedge/credential` |
| Orbi Username | Orbi Login | username | `op://AI Wedge/Orbi Login/username` |
| Orbi Password | Orbi Login | password | `op://AI Wedge/Orbi Login/password` |
| Proxmox Host | Proxmox MCP Token | host | `op://AI Wedge/Proxmox MCP Token/host` |
| Proxmox Port | Proxmox MCP Token | port | `op://AI Wedge/Proxmox MCP Token/port` |
| Proxmox User | Proxmox MCP Token | username | `op://AI Wedge/Proxmox MCP Token/username` |
| Proxmox Token Name | Proxmox MCP Token | token_name | `op://AI Wedge/Proxmox MCP Token/token_name` |
| Proxmox Token Value | Proxmox MCP Token | credential | `op://AI Wedge/Proxmox MCP Token/credential` |
| AdGuard Username | AdGuard Admin | username | `op://AI Wedge/AdGuard Admin/username` |
| AdGuard Password | AdGuard Admin | password | `op://AI Wedge/AdGuard Admin/password` |
| NPM Email | Nginx Proxy Manager Admin | username | `op://AI Wedge/Nginx Proxy Manager Admin/username` |
| NPM Password | Nginx Proxy Manager Admin | password | `op://AI Wedge/Nginx Proxy Manager Admin/password` |
| Cloudflare DNS Token | Cloudflare DNS Token | credential | `op://AI Wedge/Cloudflare DNS Token/credential` |
| Technitium API Token | DNS Automation Credential | credential | `op://AI Wedge/DNS Automation Credential/credential` |
| Gitea DB Password | Gitea DB Credentials | password | `op://AI Wedge/Gitea DB Credentials/password` |
| Gitea Admin Password | Gitea Service Credentials | password | `op://AI Wedge/Gitea Service Credentials/password` |

## What Was Removed

**Files deleted from git**:
- `ansible/group_vars/all/vault.yml` (never committed)
- `ansible/group_vars/agh/vault.yml`
- `ansible/group_vars/unraid/vault.yml`

**Scripts deleted**:
- `ansible/scripts/ansible-vault-password.sh`
- `ansible/scripts/setup-vault-helper-env.sh`
- `~/.ansible_vault_password` (local file)

**Deprecated (kept for reference)**:
- `ansible/scripts/sync-1password-to-vault.py.DEPRECATED` (renamed, no longer used)

## Documentation Updated

- ✅ `ansible/README.md` - Replaced vault setup with service account setup
- ✅ `CLAUDE.md` - Added AI agent credential access section
- ✅ `docs/migration/vault-to-service-account.md` - This file

## Verification Checklist

After migration:

- [ ] `OP_SERVICE_ACCOUNT_TOKEN` is in `~/.bashrc`
- [ ] Service account can read credentials: `op read "op://AI Wedge/Notion MCP Integration/credential"`
- [ ] All 10 role `defaults/main.yml` files use new pattern (ENV → OP lookup)
- [ ] Vault files removed from git: `git ls-files | grep vault.yml` returns nothing
- [ ] Vault backups exist: `ls ~/.ansible-vault-backup-*`
- [ ] All playbooks pass check mode without `op signin`
- [ ] Environment variable override works: `NOTION_TOKEN=test ansible-playbook ... --check`
- [ ] Claude/Codex can read credentials: `python3 -c "import subprocess; subprocess.run(['op', 'read', 'op://AI Wedge/Notion MCP Integration/credential'], check=True)"`

## Next Steps

1. **Verify credentials work** with a test playbook:
   ```bash
   cd ansible
   ansible-playbook playbooks/mcp/deploy-notion-mcp-public.yml --check --limit unraid-server
   ```

2. **Update any local documentation** that referenced vault setup

3. **Clean up old backups** after 30 days of successful operation:
   ```bash
   rm -rf ~/.ansible-vault-backup-*
   ```

## Questions?

Refer to:
- `ansible/README.md` - Credential management section
- `CLAUDE.md` - Credential access for AI agents section
- `ansible/scripts/sync-1password-to-vault.py.DEPRECATED` - Full mapping of 1Password items
