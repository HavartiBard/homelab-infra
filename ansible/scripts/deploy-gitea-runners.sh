#!/bin/bash
# Quick deployment script for Gitea Runners
# Usage: ./deploy-gitea-runners.sh [OPTIONS]

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Defaults
RUNNER_COUNT=2
DRY_RUN=false
VERBOSE=false
HOST_LIMIT="unraid"

print_help() {
  cat <<EOF
Usage: $0 [OPTIONS]

Deploy Gitea Runners to your homelab infrastructure.

OPTIONS:
  -t, --token TOKEN         Runner registration token (required)
  -c, --count NUM           Number of concurrent runners (default: 2)
  -h, --host HOST           Target host group (default: unraid)
  -m, --memory SIZE         Memory limit per runner (e.g., 4g, 8g)
  -p, --cpus NUM            CPU limit per runner (e.g., 2, 4)
  -l, --labels LABELS       Comma-separated labels (e.g., ubuntu-latest,docker)
  --dry-run                 Show what would be executed (don't apply)
  -v, --verbose             Verbose ansible output
  --help                    Show this help message

EXAMPLES:
  # Deploy 2 runners to Unraid (default)
  $0 --token xxxxx

  # Deploy 4 runners with more resources
  $0 --token xxxxx --count 4 --memory 8g --cpus 4

  # Deploy to Proxmox host
  $0 --token xxxxx --host pve-01 --count 3

  # Dry run to preview changes
  $0 --token xxxxx --dry-run

PREREQUISITES:
  1. Gitea instance running at https://gitea.klsll.com
  2. Generate token: https://gitea.klsll.com/admin/runners → Create New Runner
  3. Ansible configured with SSH access to target host

EOF
}

# Parse arguments
RUNNER_TOKEN=""
MEMORY_LIMIT=""
CPUS_LIMIT=""
LABELS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--token)
      RUNNER_TOKEN="$2"
      shift 2
      ;;
    -c|--count)
      RUNNER_COUNT="$2"
      shift 2
      ;;
    -h|--host)
      HOST_LIMIT="$2"
      shift 2
      ;;
    -m|--memory)
      MEMORY_LIMIT="$2"
      shift 2
      ;;
    -p|--cpus)
      CPUS_LIMIT="$2"
      shift 2
      ;;
    -l|--labels)
      LABELS="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -v|--verbose)
      VERBOSE=true
      shift
      ;;
    --help)
      print_help
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      print_help
      exit 1
      ;;
  esac
done

# Validation
if [[ -z "$RUNNER_TOKEN" ]]; then
  echo -e "${RED}Error: Runner token is required${NC}"
  echo -e "${YELLOW}Usage: $0 --token XXXXX${NC}"
  print_help
  exit 1
fi

# Check prerequisites
if ! command -v ansible-playbook &> /dev/null; then
  echo -e "${RED}Error: ansible-playbook not found${NC}"
  echo "Install: pip install ansible"
  exit 1
fi

# Verify in ansible directory
if [[ ! -f "ansible/playbooks/platform/deploy-gitea-runners.yml" ]]; then
  echo -e "${RED}Error: Must run from homelab-infra repository root${NC}"
  exit 1
fi

echo -e "${BLUE}═════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Gitea Runner Deployment${NC}"
echo -e "${BLUE}═════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Runners:        $RUNNER_COUNT"
echo "  Target Host:    $HOST_LIMIT"
if [[ -n "$MEMORY_LIMIT" ]]; then echo "  Memory:         $MEMORY_LIMIT"; fi
if [[ -n "$CPUS_LIMIT" ]]; then echo "  CPUs:           $CPUS_LIMIT"; fi
if [[ -n "$LABELS" ]]; then echo "  Labels:         $LABELS"; fi
echo "  Dry Run:        $DRY_RUN"
echo ""

# Build playbook command
cd ansible

PLAYBOOK_CMD="ansible-playbook playbooks/platform/deploy-gitea-runners.yml"
PLAYBOOK_CMD="$PLAYBOOK_CMD --limit $HOST_LIMIT"
PLAYBOOK_CMD="$PLAYBOOK_CMD -e gitea_runner_count=$RUNNER_COUNT"

if [[ -n "$MEMORY_LIMIT" ]]; then
  PLAYBOOK_CMD="$PLAYBOOK_CMD -e gitea_runner_memory_limit=$MEMORY_LIMIT"
fi

if [[ -n "$CPUS_LIMIT" ]]; then
  PLAYBOOK_CMD="$PLAYBOOK_CMD -e gitea_runner_cpus_limit=$CPUS_LIMIT"
fi

if [[ -n "$LABELS" ]]; then
  PLAYBOOK_CMD="$PLAYBOOK_CMD -e gitea_runner_labels='[\"${LABELS//,/\",\"}\"]'"
fi

if [[ "$VERBOSE" == true ]]; then
  PLAYBOOK_CMD="$PLAYBOOK_CMD -v"
fi

# Step 1: Syntax check
echo -e "${BLUE}Step 1: Syntax check${NC}"
$PLAYBOOK_CMD --syntax-check
if [[ $? -ne 0 ]]; then
  echo -e "${RED}Syntax check failed${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Syntax check passed${NC}"
echo ""

# Step 2: Dry run
echo -e "${BLUE}Step 2: Dry run (no changes)${NC}"
$PLAYBOOK_CMD --check --diff
if [[ $? -ne 0 ]]; then
  echo -e "${RED}Dry run failed${NC}"
  exit 1
fi
echo ""

# Step 3: Apply (unless --dry-run)
if [[ "$DRY_RUN" == true ]]; then
  echo -e "${YELLOW}Dry run complete. Run without --dry-run to apply changes.${NC}"
  exit 0
fi

# Confirm deployment
echo -e "${YELLOW}Ready to deploy. Continue? (y/n)${NC}"
read -r CONFIRM
if [[ "$CONFIRM" != "y" ]]; then
  echo "Deployment cancelled"
  exit 0
fi

echo -e "${BLUE}Step 3: Deploying runners${NC}"
GITEA_RUNNER_TOKEN="$RUNNER_TOKEN" $PLAYBOOK_CMD --diff

if [[ $? -eq 0 ]]; then
  echo ""
  echo -e "${GREEN}═════════════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}✓ Gitea Runners deployed successfully!${NC}"
  echo -e "${GREEN}═════════════════════════════════════════════════════════${NC}"
  echo ""
  echo -e "${BLUE}Next steps:${NC}"
  echo "  1. Verify runners are online:"
  echo "     https://gitea.klsll.com/admin/runners"
  echo ""
  echo "  2. Create a test workflow in a repository:"
  echo "     Create .gitea/workflows/test.yml"
  echo ""
  echo "  3. Monitor runner logs (SSH to Unraid):"
  echo "     ssh root@192.168.20.14"
  echo "     cd /mnt/user/appdata/gitea-runner/stacks"
  echo "     docker compose logs -f"
  echo ""
  echo "Documentation: $PWD/../docs/GITEA_RUNNERS.md"
  echo ""
else
  echo -e "${RED}✗ Deployment failed${NC}"
  exit 1
fi
