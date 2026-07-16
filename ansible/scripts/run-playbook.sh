#!/usr/bin/env bash
# Run an ansible-playbook invocation with secrets resolved from 1Password at
# runtime via `op run`, using ansible/envs/<slug>.env (op:// references only,
# never literal secret values).
#
# Usage: ./scripts/run-playbook.sh <envfile-slug> <ansible-playbook-args...>
# Example: ansible/scripts/run-playbook.sh adguard playbooks/dns/deploy-adguard-config.yml --limit agh --check --diff

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <envfile-slug> <ansible-playbook-args...>" >&2
  exit 1
fi

slug="$1"
shift

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
common_env_file="${script_dir}/../envs/common.env"
env_file="${script_dir}/../envs/${slug}.env"

if [[ ! -f "$env_file" ]]; then
  echo "Error: no such env file: $env_file" >&2
  exit 1
fi

if ! command -v op &> /dev/null; then
  echo "Error: 1Password CLI ('op') not found. See docs/secrets-management.md for setup." >&2
  exit 1
fi

# common.env (cross-cutting secrets like NETBOX_TOKEN, needed by roles that
# many other playbooks include) is merged in on every invocation, in addition
# to the slug-specific file.
exec op run --env-file="$common_env_file" --env-file="$env_file" -- ansible-playbook "$@"
