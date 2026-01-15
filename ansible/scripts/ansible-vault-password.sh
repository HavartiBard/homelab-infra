#!/usr/bin/env bash
set -euo pipefail

# Outputs the Ansible vault password stored in 1Password so it can be
# consumed via ANSIBLE_VAULT_PASSWORD_FILE. Adjust the item/vault names via
# ANSIBLE_VAULT_OP_ITEM and ANSIBLE_VAULT_OP_VAULT if your vault layout differs.

ANSIBLE_VAULT_OP_ITEM="${ANSIBLE_VAULT_OP_ITEM:-Ansible Vault Password}"
ANSIBLE_VAULT_OP_VAULT="${ANSIBLE_VAULT_OP_VAULT:-}"

if ! command -v op >/dev/null 2>&1; then
  echo "op CLI is not installed or not in PATH" >&2
  exit 1
fi

cmd=(op item get "$ANSIBLE_VAULT_OP_ITEM" --fields password --reveal)
if [[ -n "$ANSIBLE_VAULT_OP_VAULT" ]]; then
  cmd+=(--vault "$ANSIBLE_VAULT_OP_VAULT")
fi

"${cmd[@]}"
