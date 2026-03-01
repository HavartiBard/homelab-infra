# 1Password → Ansible Vault Migration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate all secrets from 1Password (tagged "Ansible") into `ansible/group_vars/all/vault.yml` and remove every `op read` call from the codebase.

**Architecture:** Create a single encrypted `group_vars/all/vault.yml` accessible to all host groups, populate it with secrets fetched from 1Password via a one-time script, then replace all `op read` / `lookup('pipe', 'op read ...')` patterns in roles, group_vars, and playbooks with direct `vault_*` variable references. The `group_vars/unraid/vault.yml` is migrated and removed.

**Tech Stack:** Ansible Vault (AES256), `op` CLI, Python 3 for the extraction script, `ansible-vault encrypt_string` / `ansible-vault encrypt`

---

## Vault Variable Naming Convention

All vault variables follow `vault_<service>_<field>` pattern.

| 1Password Item | Fields | Vault Variable(s) |
|---|---|---|
| AdGuard Admin | username, password | `vault_adguard_admin_username`, `vault_adguard_admin_password` |
| API dns-automation | username, credential | `vault_dns_automation_username`, `vault_dns_automation_credential` |
| Cloudflare DNS Token | credential | `vault_cloudflare_dns_token` |
| CouchDB Obsidian Admin | username, password | `vault_couchdb_admin_username`, `vault_couchdb_admin_password` |
| CouchDB Obsidian Sync User | username, password | `vault_couchdb_sync_username`, `vault_couchdb_sync_password` |
| DNS Automation Credential | credential | `vault_technitium_api_token` |
| GitHub Access Token | password | `vault_github_access_token` |
| Gitea DB Credentials | password | `vault_gitea_db_password` |
| Gitea MCP Token | credential | `vault_gitea_mcp_token` |
| Gitea Registry Credentials | password | `vault_gitea_registry_password` |
| Gitea Service Credentials | password | `vault_gitea_service_password` |
| Homelab SSH Key | private key | `vault_homelab_ssh_private_key` |
| IronClaw Gateway Auth Token | credential | `vault_ironclaw_gateway_auth_token` |
| IronClaw HTTP Webhook Secret | credential | `vault_ironclaw_http_webhook_secret` |
| IronClaw Postgres Password | credential | `vault_ironclaw_postgres_password` |
| IronClaw Secrets Master Key | credential | `vault_ironclaw_secrets_master_key` |
| IronClaw Slack App Token | credential | `vault_ironclaw_slack_app_token` |
| IronClaw Slack Bot Token | credential | `vault_ironclaw_slack_bot_token` |
| IronClaw Slack Signing Secret | credential | `vault_ironclaw_slack_signing_secret` |
| LMStudio Ironclaw API token | credential | `vault_ironclaw_lmstudio_api_key` |
| Nginx Proxy Manager Admin | username, password | `vault_npm_admin_username`, `vault_npm_admin_password` |
| OP_SERVICE_ACCOUNT_TOKEN | credential | `vault_op_service_account_token` |
| Orbi Login | username, password | `vault_orbi_username`, `vault_orbi_password` |
| Proxmox MCP Token | host, port, username, token_name, credential, allow_elevated | `vault_proxmox_mcp_host`, `vault_proxmox_mcp_port`, `vault_proxmox_mcp_user`, `vault_proxmox_mcp_token_name`, `vault_proxmox_mcp_token_value`, `vault_proxmox_mcp_allow_elevated` |
| Unraid GraphQL - Wedge | credential | `vault_unraid_api_key` |
| ai-agents-gitea-ssh | private key | `vault_ai_agents_ssh_private_key` |
| *(existing)* chiffon executor token | — | `vault_chiffon_executor_token` *(keep as-is)* |
| *(existing)* chiffon LMStudio key | — | `vault_chiffon_lmstudio_api_key` *(keep as-is)* |

> **Note:** `Gitea MCP Token` and `Gitea Registry Credentials` and `LMStudio Ironclaw API token` are used in code but not tagged "Ansible" in 1Password — include them in vault anyway to fully remove the `op read` dependency.

---

## Files Modified

- **Create:** `ansible/group_vars/all/vault.yml`
- **Delete:** `ansible/group_vars/unraid/vault.yml` (vars move to `all/vault.yml`)
- **Modify:** `ansible/group_vars/unraid/unraid.yml`
- **Modify:** `ansible/group_vars/unraid/obsidian.yml`
- **Modify:** `ansible/roles/homelab-mcp/defaults/main.yml`
- **Modify:** `ansible/roles/onepassword-mcp/defaults/main.yml`
- **Modify:** `ansible/roles/proxmox-mcp/defaults/main.yml`
- **Modify:** `ansible/roles/unraid-mcp/defaults/main.yml`
- **Modify:** `ansible/roles/adguard/defaults/main.yml`
- **Modify:** `ansible/roles/gitea/defaults/main.yml`
- **Modify:** `ansible/roles/gitea-runner/defaults/main.yml`
- **Modify:** `ansible/roles/gitea-mcp/defaults/main.yml`
- **Modify:** `ansible/roles/npm/defaults/main.yml`
- **Modify:** `ansible/playbooks/misc/deploy-ironclaw.yml`
- **Modify:** `ansible/playbooks/platform/deploy-soullayer.yml`

---

## Task 1: Create feature branch

**Step 1: Create branch**

```bash
cd /home/james/projects/homelab-infra
git checkout -b feature/vault-migration
```

**Step 2: Verify**

```bash
git branch --show-current
```
Expected: `feature/vault-migration`

---

## Task 2: Generate and encrypt `group_vars/all/vault.yml`

Write a Python script, run it to extract all secrets from 1Password, then encrypt the output with ansible-vault.

**Step 1: Write the extraction script**

Create `/tmp/gen_vault.py`:

```python
#!/usr/bin/env python3
"""Fetch secrets from 1Password and write ansible vault YAML to stdout."""
import subprocess, sys

def op(path):
    r = subprocess.run(['op', 'read', f'op://AI Wedge/{path}'], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"# ERROR reading {path}: {r.stderr.strip()}", file=sys.stderr)
        return ''
    return r.stdout.strip()

def op_item(item, field):
    return op(f'{item}/{field}')

lines = [
    '---',
    '# Ansible Vault — all secrets migrated from 1Password "AI Wedge" vault',
    '# DO NOT edit in plaintext. Use: ansible-vault edit ansible/group_vars/all/vault.yml',
    '',
    '# AdGuard Admin',
    f'vault_adguard_admin_username: "{op_item("AdGuard Admin", "username")}"',
    f'vault_adguard_admin_password: "{op_item("AdGuard Admin", "password")}"',
    '',
    '# API dns-automation',
    f'vault_dns_automation_username: "{op_item("API dns-automation", "username")}"',
    f'vault_dns_automation_credential: "{op_item("API dns-automation", "credential")}"',
    '',
    '# Cloudflare DNS Token',
    f'vault_cloudflare_dns_token: "{op_item("Cloudflare DNS Token", "credential")}"',
    '',
    '# CouchDB Obsidian Admin',
    f'vault_couchdb_admin_username: "{op_item("CouchDB Obsidian Admin", "username")}"',
    f'vault_couchdb_admin_password: "{op_item("CouchDB Obsidian Admin", "password")}"',
    '',
    '# CouchDB Obsidian Sync User',
    f'vault_couchdb_sync_username: "{op_item("CouchDB Obsidian Sync User", "username")}"',
    f'vault_couchdb_sync_password: "{op_item("CouchDB Obsidian Sync User", "password")}"',
    '',
    '# DNS Automation Credential (Technitium)',
    f'vault_technitium_api_token: "{op_item("DNS Automation Credential", "credential")}"',
    '',
    '# GitHub Access Token',
    f'vault_github_access_token: "{op_item("GitHub Access Token", "password")}"',
    '',
    '# Gitea DB Credentials',
    f'vault_gitea_db_password: "{op_item("Gitea DB Credentials", "password")}"',
    '',
    '# Gitea MCP Token (not tagged Ansible, but used in code)',
    f'vault_gitea_mcp_token: "{op_item("Gitea MCP Token", "credential")}"',
    '',
    '# Gitea Registry Credentials (not tagged Ansible, but used in code)',
    f'vault_gitea_registry_password: "{op_item("Gitea Registry Credentials", "password")}"',
    '',
    '# Gitea Service Credentials',
    f'vault_gitea_service_password: "{op_item("Gitea Service Credentials", "password")}"',
    '',
    '# Homelab SSH Key',
    "vault_homelab_ssh_private_key: |",
]

# Multi-line SSH key
homelab_key = op_item("Homelab SSH Key", "private key")
for line in homelab_key.splitlines():
    lines.append(f'  {line}')

lines += [
    '',
    '# IronClaw secrets',
    f'vault_ironclaw_gateway_auth_token: "{op_item("IronClaw Gateway Auth Token", "credential")}"',
    f'vault_ironclaw_http_webhook_secret: "{op_item("IronClaw HTTP Webhook Secret", "credential")}"',
    f'vault_ironclaw_postgres_password: "{op_item("IronClaw Postgres Password", "credential")}"',
    f'vault_ironclaw_secrets_master_key: "{op_item("IronClaw Secrets Master Key", "credential")}"',
    f'vault_ironclaw_slack_app_token: "{op_item("IronClaw Slack App Token", "credential")}"',
    f'vault_ironclaw_slack_bot_token: "{op_item("IronClaw Slack Bot Token", "credential")}"',
    f'vault_ironclaw_slack_signing_secret: "{op_item("IronClaw Slack Signing Secret", "credential")}"',
    f'vault_ironclaw_lmstudio_api_key: "{op_item("LMStudio Ironclaw API token", "credential")}"',
    '',
    '# Nginx Proxy Manager Admin',
    f'vault_npm_admin_username: "{op_item("Nginx Proxy Manager Admin", "username")}"',
    f'vault_npm_admin_password: "{op_item("Nginx Proxy Manager Admin", "password")}"',
    '',
    '# 1Password Service Account Token',
    f'vault_op_service_account_token: "{op_item("OP_SERVICE_ACCOUNT_TOKEN", "credential")}"',
    '',
    '# Orbi Login',
    f'vault_orbi_username: "{op_item("Orbi Login", "username")}"',
    f'vault_orbi_password: "{op_item("Orbi Login", "password")}"',
    '',
    '# Proxmox MCP Token',
    f'vault_proxmox_mcp_host: "{op_item("Proxmox MCP Token", "host")}"',
    f'vault_proxmox_mcp_port: "{op_item("Proxmox MCP Token", "port")}"',
    f'vault_proxmox_mcp_user: "{op_item("Proxmox MCP Token", "username")}"',
    f'vault_proxmox_mcp_token_name: "{op_item("Proxmox MCP Token", "token_name")}"',
    f'vault_proxmox_mcp_token_value: "{op_item("Proxmox MCP Token", "credential")}"',
    f'vault_proxmox_mcp_allow_elevated: "{op_item("Proxmox MCP Token", "allow_elevated")}"',
    '',
    '# Unraid GraphQL API key',
    f'vault_unraid_api_key: "{op_item("Unraid GraphQL - Wedge", "credential")}"',
    '',
    '# AI Agents Gitea SSH key',
    "vault_ai_agents_ssh_private_key: |",
]

# Multi-line SSH key
ai_agents_key = op_item("ai-agents-gitea-ssh", "private key")
for line in ai_agents_key.splitlines():
    lines.append(f'  {line}')

lines += [
    '',
    '# Chiffon Executor (migrated from group_vars/unraid/vault.yml)',
    f'vault_chiffon_executor_token: "{op_item("Chiffon Executor", "credential")}"',
    f'vault_chiffon_lmstudio_api_key: "{op_item("LMStudio Chiffon API token", "credential")}"',
]

print('\n'.join(lines))
```

**Step 2: Get the existing chiffon vault values** (they're already in the unraid vault, not 1Password)

```bash
ansible-vault decrypt --output=- ansible/group_vars/unraid/vault.yml
```

Note the values for `vault_chiffon_executor_token` and `vault_chiffon_lmstudio_api_key`.

**Step 3: Run the extraction script**

```bash
mkdir -p ansible/group_vars/all
python3 /tmp/gen_vault.py > /tmp/vault_plaintext.yml 2>/tmp/vault_errors.txt
cat /tmp/vault_errors.txt  # should be empty or show only non-critical warnings
```

**Step 4: Manually patch the chiffon vars** into `/tmp/vault_plaintext.yml` using the values from Step 2. Replace the placeholder lines at the bottom of the file:

```yaml
vault_chiffon_executor_token: "<value from unraid vault>"
vault_chiffon_lmstudio_api_key: "<value from unraid vault>"
```

**Step 5: Encrypt the vault file**

```bash
ansible-vault encrypt /tmp/vault_plaintext.yml --output=ansible/group_vars/all/vault.yml
```

**Step 6: Verify the file is encrypted**

```bash
head -1 ansible/group_vars/all/vault.yml
```
Expected: `$ANSIBLE_VAULT;1.1;AES256`

**Step 7: Verify vault decrypts correctly**

```bash
cd ansible && ansible-vault view group_vars/all/vault.yml | grep vault_unraid_api_key
```
Expected: one line showing the key value.

**Step 8: Clean up plaintext**

```bash
rm /tmp/vault_plaintext.yml /tmp/vault_errors.txt
```

**Step 9: Commit**

```bash
git add ansible/group_vars/all/vault.yml
git commit -m "feat(vault): create group_vars/all/vault.yml with all 1Password secrets"
```

---

## Task 3: Remove `group_vars/unraid/vault.yml`

**Step 1: Delete the old vault file**

```bash
rm ansible/group_vars/unraid/vault.yml
```

**Step 2: Commit**

```bash
git add -u ansible/group_vars/unraid/vault.yml
git commit -m "chore(vault): remove group_vars/unraid/vault.yml (migrated to all/vault.yml)"
```

---

## Task 4: Update `group_vars/unraid/unraid.yml`

Replace the entire MCP credentials section (lines 75–136) with direct vault variable references. Remove all `op read` lookups and the `op_vault`, `npm_op_item`, `technitium_op_item`, `cloudflare_op_item`, and the `*_op_command` vars (those were only used as intermediaries for the lookups).

**File:** `ansible/group_vars/unraid/unraid.yml`

Replace lines 33–62 and 75–136 with:

```yaml
op_vault: "AI Wedge"
npm_op_item: "Nginx Proxy Manager Admin"
technitium_op_item: "DNS Automation Credential"
cloudflare_op_item: "Cloudflare DNS Token"

npm_admin_email: "{{ vault_npm_admin_username }}"
npm_admin_password: "{{ vault_npm_admin_password }}"
technitium_api_url: "http://192.168.20.2:5380"
technitium_zone: klsll.com
technitium_admin_user: dns-automation
technitium_api_token: "{{ vault_technitium_api_token }}"
technitium_admin_password: "{{ vault_technitium_api_token }}"
cloudflare_dns_token: "{{ vault_cloudflare_dns_token }}"

# MCP credentials (from Ansible vault)
unraid_api_key: "{{ vault_unraid_api_key }}"
orbi_username: "{{ vault_orbi_username }}"
orbi_password: "{{ vault_orbi_password }}"
op_service_account_token: "{{ vault_op_service_account_token }}"
proxmox_host: "{{ vault_proxmox_mcp_host }}"
proxmox_port: "{{ vault_proxmox_mcp_port }}"
proxmox_user: "{{ vault_proxmox_mcp_user }}"
proxmox_token_name: "{{ vault_proxmox_mcp_token_name }}"
proxmox_token_value: "{{ vault_proxmox_mcp_token_value }}"
proxmox_allow_elevated: "{{ vault_proxmox_mcp_allow_elevated }}"
adguard_admin_user: "{{ vault_adguard_admin_username }}"
adguard_admin_password: "{{ vault_adguard_admin_password }}"
gitea_db_password: "{{ vault_gitea_db_password }}"
gitea_admin_password: "{{ vault_gitea_service_password }}"
gitea_mcp_token: "{{ vault_gitea_mcp_token }}"
```

**Step 1: Edit the file** per the diff above.

**Step 2: Verify no `op read` remains**

```bash
grep "op read\|lookup.*pipe.*op" ansible/group_vars/unraid/unraid.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/group_vars/unraid/unraid.yml
git commit -m "refactor(vault): replace op read lookups in group_vars/unraid/unraid.yml"
```

---

## Task 5: Update `group_vars/unraid/obsidian.yml`

**File:** `ansible/group_vars/unraid/obsidian.yml`

Replace the entire file content with:

```yaml
---
# Obsidian stack configuration
couchdb_admin_user: "{{ vault_couchdb_admin_username }}"
couchdb_admin_password: "{{ vault_couchdb_admin_password }}"
couchdb_sync_user: "{{ vault_couchdb_sync_username }}"
couchdb_sync_password: "{{ vault_couchdb_sync_password }}"

obsidian_vault_path: "/mnt/user/appdata/obsidian/vaults/homelab"
obsidian_mcp_port: 6977
obsidian_mcp_container_name: "obsidian-mcp"
```

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/group_vars/unraid/obsidian.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/group_vars/unraid/obsidian.yml
git commit -m "refactor(vault): replace op read lookups in group_vars/unraid/obsidian.yml"
```

---

## Task 6: Update role defaults — `homelab-mcp`

**File:** `ansible/roles/homelab-mcp/defaults/main.yml`

Replace the `orbi_username` and `orbi_password` vars:

```yaml
orbi_username: "{{ vault_orbi_username }}"
orbi_password: "{{ vault_orbi_password }}"
```

Remove the `orbi_op_item` line and the multiline `>-` / `lookup` / `| default` blocks for both vars.

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/roles/homelab-mcp/defaults/main.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/roles/homelab-mcp/defaults/main.yml
git commit -m "refactor(vault): replace op read lookups in homelab-mcp role"
```

---

## Task 7: Update role defaults — `onepassword-mcp`

**File:** `ansible/roles/onepassword-mcp/defaults/main.yml`

Replace:

```yaml
op_service_account_token: "{{ vault_op_service_account_token }}"
```

Remove the `op_service_account_item` line and the multiline lookup block.

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/roles/onepassword-mcp/defaults/main.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/roles/onepassword-mcp/defaults/main.yml
git commit -m "refactor(vault): replace op read lookup in onepassword-mcp role"
```

---

## Task 8: Update role defaults — `proxmox-mcp`

**File:** `ansible/roles/proxmox-mcp/defaults/main.yml`

Replace all 6 proxmox credential vars with direct vault references. Remove `proxmox_op_item` and all multiline lookup blocks.

```yaml
proxmox_host: "{{ vault_proxmox_mcp_host }}"
proxmox_port: "{{ vault_proxmox_mcp_port }}"
proxmox_user: "{{ vault_proxmox_mcp_user }}"
proxmox_token_name: "{{ vault_proxmox_mcp_token_name }}"
proxmox_token_value: "{{ vault_proxmox_mcp_token_value }}"
proxmox_allow_elevated: "{{ vault_proxmox_mcp_allow_elevated }}"
```

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/roles/proxmox-mcp/defaults/main.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/roles/proxmox-mcp/defaults/main.yml
git commit -m "refactor(vault): replace op read lookups in proxmox-mcp role"
```

---

## Task 9: Update role defaults — `unraid-mcp`

**File:** `ansible/roles/unraid-mcp/defaults/main.yml`

Replace:

```yaml
unraid_api_key: "{{ vault_unraid_api_key }}"
```

Remove `unraid_op_item` and multiline lookup block.

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/roles/unraid-mcp/defaults/main.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/roles/unraid-mcp/defaults/main.yml
git commit -m "refactor(vault): replace op read lookup in unraid-mcp role"
```

---

## Task 10: Update role defaults — `adguard`

**File:** `ansible/roles/adguard/defaults/main.yml`

Replace:

```yaml
adguard_admin_user: "{{ vault_adguard_admin_username }}"
adguard_admin_password: "{{ vault_adguard_admin_password }}"
```

Remove `adguard_op_item` and multiline lookup blocks.

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/roles/adguard/defaults/main.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/roles/adguard/defaults/main.yml
git commit -m "refactor(vault): replace op read lookups in adguard role"
```

---

## Task 11: Update role defaults — `gitea`

**File:** `ansible/roles/gitea/defaults/main.yml`

Replace the two op read lookups:

```yaml
gitea_db_password: "{{ vault_gitea_db_password }}"
gitea_admin_password: "{{ vault_gitea_service_password }}"
```

Remove multiline lookup blocks for both.

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/roles/gitea/defaults/main.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/roles/gitea/defaults/main.yml
git commit -m "refactor(vault): replace op read lookups in gitea role"
```

---

## Task 12: Update role defaults — `gitea-runner`

**File:** `ansible/roles/gitea-runner/defaults/main.yml`

Replace:

```yaml
registry_password: "{{ vault_gitea_registry_password }}"
```

Remove multiline lookup block (keep the `lookup('env', 'REGISTRY_PASSWORD')` env fallback if desired, or simplify to just vault var).

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/roles/gitea-runner/defaults/main.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/roles/gitea-runner/defaults/main.yml
git commit -m "refactor(vault): replace op read lookup in gitea-runner role"
```

---

## Task 13: Update role defaults — `gitea-mcp`

**File:** `ansible/roles/gitea-mcp/defaults/main.yml`

Replace the gitea token lookup with:

```yaml
gitea_mcp_token: "{{ vault_gitea_mcp_token }}"
```

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/roles/gitea-mcp/defaults/main.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/roles/gitea-mcp/defaults/main.yml
git commit -m "refactor(vault): replace op read lookup in gitea-mcp role"
```

---

## Task 14: Update role defaults — `npm`

**File:** `ansible/roles/npm/defaults/main.yml`

Replace:

```yaml
npm_admin_email: "{{ vault_npm_admin_username }}"
npm_admin_password: "{{ vault_npm_admin_password }}"
technitium_api_token: "{{ vault_technitium_api_token }}"
cloudflare_dns_token: "{{ vault_cloudflare_dns_token }}"
```

Remove multiline lookup blocks for all four.

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/roles/npm/defaults/main.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/roles/npm/defaults/main.yml
git commit -m "refactor(vault): replace op read lookups in npm role"
```

---

## Task 15: Update `playbooks/misc/deploy-ironclaw.yml`

Remove all 8 `pre_tasks` that fetch from 1Password and the `set_fact` that assembles them. Replace with a `vars` block at the play level that maps vault variables directly to the expected fact names (since the `ironclaw` role likely uses `ironclaw_pg_password` etc.).

**File:** `ansible/playbooks/misc/deploy-ironclaw.yml`

Replace the `pre_tasks` block (lines 28–95) with a `vars` section under the play:

```yaml
  vars:
    ironclaw_pg_password: "{{ vault_ironclaw_postgres_password }}"
    ironclaw_http_webhook_secret: "{{ vault_ironclaw_http_webhook_secret }}"
    ironclaw_slack_bot_token: "{{ vault_ironclaw_slack_bot_token }}"
    ironclaw_slack_app_token: "{{ vault_ironclaw_slack_app_token }}"
    ironclaw_slack_signing_secret: "{{ vault_ironclaw_slack_signing_secret }}"
    ironclaw_secrets_master_key: "{{ vault_ironclaw_secrets_master_key }}"
    ironclaw_gateway_auth_token: "{{ vault_ironclaw_gateway_auth_token }}"
    ironclaw_llm_api_key: "{{ vault_ironclaw_lmstudio_api_key }}"
```

Also update the playbook header comment to remove the 1Password prerequisites (replace with "Secrets sourced from Ansible vault (`group_vars/all/vault.yml`)").

**Step 1: Read the full playbook** to see the exact structure before editing:
```bash
cat ansible/playbooks/misc/deploy-ironclaw.yml
```

**Step 2: Edit the file.**

**Step 3: Verify**

```bash
grep "op read\|lookup.*pipe.*op\|ansible.builtin.command: op" ansible/playbooks/misc/deploy-ironclaw.yml
```
Expected: no output.

**Step 4: Commit**

```bash
git add ansible/playbooks/misc/deploy-ironclaw.yml
git commit -m "refactor(vault): replace op read pre_tasks in deploy-ironclaw.yml"
```

---

## Task 16: Update `playbooks/platform/deploy-soullayer.yml`

Replace the `op read` task that fetches the SSH key with a direct reference to `vault_ai_agents_ssh_private_key`.

**File:** `ansible/playbooks/platform/deploy-soullayer.yml`

Replace:

```yaml
    - name: Read AI-Agents SSH private key from 1Password (on dev-box)
      ansible.builtin.shell: op read "op://AI Wedge/ai-agents-gitea-ssh/private key"
      register: ssh_private_key
      delegate_to: localhost
      changed_when: false
      no_log: true
      environment:
        OP_SERVICE_ACCOUNT_TOKEN: "{{ lookup('env', 'OP_SERVICE_ACCOUNT_TOKEN') }}"

    - name: Deploy SSH private key to Unraid
      ansible.builtin.copy:
        content: "{{ ssh_private_key.stdout }}"
        dest: "{{ ssh_key_path }}"
        mode: "0600"
        owner: root
      no_log: true
```

With:

```yaml
    - name: Deploy SSH private key to Unraid
      ansible.builtin.copy:
        content: "{{ vault_ai_agents_ssh_private_key }}"
        dest: "{{ ssh_key_path }}"
        mode: "0600"
        owner: root
      no_log: true
```

**Step 1: Edit the file.**

**Step 2: Verify**

```bash
grep "op read\|lookup.*pipe.*op" ansible/playbooks/platform/deploy-soullayer.yml
```
Expected: no output.

**Step 3: Commit**

```bash
git add ansible/playbooks/platform/deploy-soullayer.yml
git commit -m "refactor(vault): replace op read SSH key fetch in deploy-soullayer.yml"
```

---

## Task 17: Final verification

**Step 1: Confirm zero `op read` calls remain in the ansible directory**

```bash
grep -r "op read\|lookup.*pipe.*op" ansible/ --include="*.yml"
```
Expected: **no output**.

**Step 2: Syntax check a representative playbook**

```bash
cd ansible
ansible-playbook playbooks/misc/deploy-ironclaw.yml --syntax-check
ansible-playbook playbooks/mcp/deploy-proxmox-mcp.yml --syntax-check
ansible-playbook playbooks/dns/deploy-adguard-config.yml --syntax-check
```
Expected: `playbook: ... (N plays)` with no errors.

**Step 3: Dry-run verify vault vars resolve (unraid target)**

```bash
ansible-playbook playbooks/mcp/deploy-unraid-mcp.yml --check --diff --limit unraid -v 2>&1 | grep -E "vault_|FAILED|ERROR" | head -20
```
Expected: no `vault_*` variable undefined errors.

**Step 4: Commit the plan doc**

```bash
cd ..
git add docs/plans/2026-03-01-vault-migration.md
git commit -m "docs: add vault migration plan"
```

---

## Task 18: Push branch and open PR

**Step 1: Push**

```bash
git push -u origin feature/vault-migration
```

**Step 2: Create PR via Gitea MCP**

Use `mcp__gitea__create_pull_request` with:
- title: `feat(vault): migrate all 1Password secrets to Ansible vault`
- body: summary of changes, list of files modified, verification steps
- base: `main`
- head: `feature/vault-migration`
