#!/usr/bin/env bash

# Exports the ANSIBLE_VAULT_* helpers so playbook runs automatically read the
# encrypted group vars via the 1Password-backed helper password file.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export ANSIBLE_VAULT_PASSWORD_FILE="${ANSIBLE_VAULT_PASSWORD_FILE:-$repo_root/scripts/ansible-vault-password.sh}"
export ANSIBLE_VAULT_OP_ITEM="${ANSIBLE_VAULT_OP_ITEM:-Ansible Vault Password}"
export ANSIBLE_VAULT_OP_VAULT="${ANSIBLE_VAULT_OP_VAULT:-AI Wedge}"
