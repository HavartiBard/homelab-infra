#!/bin/bash
# backup-volumes.sh
# Backup Docker volumes for homelab stacks
#
# Usage:
#   ./backup-volumes.sh                    # Backup all known volumes
#   ./backup-volumes.sh <volume-name>      # Backup specific volume
#   ./backup-volumes.sh --restore <file>   # Restore from backup

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/docker-volumes}"
DATE_TAG=$(date +%Y%m%d_%H%M%S)

# Known volumes to backup
PLATFORM_VOLUMES=(
    "portainer-data"
    "npm-data"
    "npm-letsencrypt"
    "npm-db-data"
    "technitium-data"
    "kuma-data"
)

MONITORING_VOLUMES=(
    "prometheus-data"
    "grafana-data"
)

GPU_WORKER_VOLUMES=(
    "ollama-data"
    "webui-data"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_usage() {
    echo "Docker Volume Backup Script"
    echo ""
    echo "Usage:"
    echo "  $0                         Backup all known volumes"
    echo "  $0 <volume-name>           Backup specific volume"
    echo "  $0 --list                  List known volumes"
    echo "  $0 --restore <backup.tar.gz> <volume-name>"
    echo "                              Restore backup to volume"
    echo ""
    echo "Environment Variables:"
    echo "  BACKUP_DIR    Backup destination (default: ~/backups/docker-volumes)"
    echo ""
    echo "Backup files are saved as: <volume>_<timestamp>.tar.gz"
    exit 1
}

# Ensure backup directory exists
setup_backup_dir() {
    mkdir -p "${BACKUP_DIR}"
    log_info "Backup directory: ${BACKUP_DIR}"
}

# Check if volume exists
volume_exists() {
    docker volume ls --format '{{.Name}}' | grep -q "^${1}$"
}

# Backup a single volume
backup_volume() {
    local volume_name="$1"
    local backup_file="${BACKUP_DIR}/${volume_name}_${DATE_TAG}.tar.gz"
    
    if ! volume_exists "${volume_name}"; then
        log_warn "Volume '${volume_name}' does not exist, skipping"
        return 1
    fi
    
    log_info "Backing up ${volume_name}..."
    
    # Create backup using temporary container
    docker run --rm \
        -v "${volume_name}:/data:ro" \
        -v "${BACKUP_DIR}:/backup" \
        alpine \
        tar czf "/backup/${volume_name}_${DATE_TAG}.tar.gz" -C /data .
    
    local size=$(du -h "${backup_file}" | cut -f1)
    log_info "  → ${backup_file} (${size})"
    
    return 0
}

# Restore a volume from backup
restore_volume() {
    local backup_file="$1"
    local volume_name="$2"
    
    if [[ ! -f "${backup_file}" ]]; then
        log_error "Backup file not found: ${backup_file}"
        exit 1
    fi
    
    log_warn "This will REPLACE all data in volume '${volume_name}'"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled"
        exit 0
    fi
    
    # Create volume if it doesn't exist
    if ! volume_exists "${volume_name}"; then
        log_info "Creating volume ${volume_name}..."
        docker volume create "${volume_name}"
    fi
    
    log_info "Restoring ${volume_name} from ${backup_file}..."
    
    # Get absolute path for backup file
    local abs_backup=$(realpath "${backup_file}")
    local backup_dir=$(dirname "${abs_backup}")
    local backup_name=$(basename "${abs_backup}")
    
    # Restore using temporary container
    docker run --rm \
        -v "${volume_name}:/data" \
        -v "${backup_dir}:/backup:ro" \
        alpine \
        sh -c "cd /data && rm -rf * && tar xzf /backup/${backup_name}"
    
    log_info "Restore complete!"
}

# List known volumes and their status
list_volumes() {
    echo "Known Volumes"
    echo "============="
    echo ""
    
    echo "Platform Stack:"
    for vol in "${PLATFORM_VOLUMES[@]}"; do
        if volume_exists "${vol}"; then
            echo -e "  ${GREEN}●${NC} ${vol}"
        else
            echo -e "  ${YELLOW}○${NC} ${vol} (not created)"
        fi
    done
    
    echo ""
    echo "Monitoring Stack:"
    for vol in "${MONITORING_VOLUMES[@]}"; do
        if volume_exists "${vol}"; then
            echo -e "  ${GREEN}●${NC} ${vol}"
        else
            echo -e "  ${YELLOW}○${NC} ${vol} (not created)"
        fi
    done
    
    echo ""
    echo "GPU Worker Stack:"
    for vol in "${GPU_WORKER_VOLUMES[@]}"; do
        if volume_exists "${vol}"; then
            echo -e "  ${GREEN}●${NC} ${vol}"
        else
            echo -e "  ${YELLOW}○${NC} ${vol} (not created)"
        fi
    done
}

# Backup all known volumes
backup_all() {
    local backed_up=0
    local skipped=0
    
    log_info "Backing up all known volumes..."
    echo ""
    
    ALL_VOLUMES=("${PLATFORM_VOLUMES[@]}" "${MONITORING_VOLUMES[@]}" "${GPU_WORKER_VOLUMES[@]}")
    
    for vol in "${ALL_VOLUMES[@]}"; do
        if backup_volume "${vol}"; then
            ((backed_up++))
        else
            ((skipped++))
        fi
    done
    
    echo ""
    log_info "Backup complete!"
    log_info "  Backed up: ${backed_up}"
    log_info "  Skipped:   ${skipped}"
    echo ""
    log_info "Backups saved to: ${BACKUP_DIR}"
}

# Cleanup old backups (keep last N)
cleanup_old_backups() {
    local keep="${1:-5}"
    
    log_info "Cleaning up old backups (keeping last ${keep})..."
    
    for vol in "${PLATFORM_VOLUMES[@]}" "${MONITORING_VOLUMES[@]}" "${GPU_WORKER_VOLUMES[@]}"; do
        local count=$(ls -1 "${BACKUP_DIR}/${vol}_"*.tar.gz 2>/dev/null | wc -l || echo "0")
        
        if [[ "${count}" -gt "${keep}" ]]; then
            local to_delete=$((count - keep))
            log_info "  ${vol}: removing ${to_delete} old backup(s)"
            
            ls -1t "${BACKUP_DIR}/${vol}_"*.tar.gz 2>/dev/null | \
                tail -n "${to_delete}" | \
                xargs rm -f
        fi
    done
}

# Main
main() {
    setup_backup_dir
    
    if [[ $# -eq 0 ]]; then
        backup_all
        exit 0
    fi
    
    case "${1}" in
        --list)
            list_volumes
            ;;
        --restore)
            if [[ $# -lt 3 ]]; then
                log_error "Restore requires backup file and volume name"
                show_usage
            fi
            restore_volume "$2" "$3"
            ;;
        --cleanup)
            cleanup_old_backups "${2:-5}"
            ;;
        --help|-h)
            show_usage
            ;;
        *)
            # Assume it's a volume name
            if backup_volume "$1"; then
                log_info "Backup complete!"
            else
                exit 1
            fi
            ;;
    esac
}

main "$@"
