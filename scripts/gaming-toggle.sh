#!/bin/bash
# gaming-toggle.sh
# Quick toggle for GPU worker stack - stop for gaming, start when done
#
# Usage:
#   ./gaming-toggle.sh start   # Start GPU workloads
#   ./gaming-toggle.sh stop    # Stop GPU workloads for gaming
#   ./gaming-toggle.sh status  # Check current status

set -euo pipefail

STACK_DIR="${GPU_WORKER_STACK_DIR:-$HOME/homelab-infra/stacks/gpu-worker}"
COMPOSE_FILE="${STACK_DIR}/compose.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_usage() {
    echo "Gaming Toggle - Control GPU Worker Stack"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  start   Start GPU workloads (Ollama, Open WebUI)"
    echo "  stop    Stop GPU workloads for gaming"
    echo "  status  Show current container status"
    echo "  restart Restart all GPU workloads"
    echo ""
    echo "Environment Variables:"
    echo "  GPU_WORKER_STACK_DIR  Path to gpu-worker stack (default: ~/homelab-infra/stacks/gpu-worker)"
    exit 1
}

check_compose_file() {
    if [[ ! -f "${COMPOSE_FILE}" ]]; then
        log_error "Compose file not found: ${COMPOSE_FILE}"
        log_info "Set GPU_WORKER_STACK_DIR or ensure repo is cloned to ~/homelab-infra"
        exit 1
    fi
}

# Get current status
get_status() {
    log_info "GPU Worker Stack Status"
    echo "========================"
    echo ""
    
    cd "${STACK_DIR}"
    
    if docker compose ps --format json 2>/dev/null | grep -q .; then
        docker compose ps
        echo ""
        
        # Check if any containers are running
        local running=$(docker compose ps --format '{{.State}}' 2>/dev/null | grep -c "running" || echo "0")
        
        if [[ "${running}" -gt 0 ]]; then
            echo -e "${GREEN}● GPU workloads are RUNNING${NC}"
            echo -e "${YELLOW}  Run '$0 stop' before gaming${NC}"
        else
            echo -e "${CYAN}○ GPU workloads are STOPPED${NC}"
            echo -e "${GREEN}  GPU is free for gaming!${NC}"
        fi
    else
        echo -e "${CYAN}○ No containers found${NC}"
        echo -e "  Run '$0 start' to start GPU workloads"
    fi
}

# Stop workloads
stop_workloads() {
    cd "${STACK_DIR}"
    
    log_info "Stopping GPU workloads..."
    
    # Graceful stop
    docker compose stop
    
    echo ""
    echo -e "${GREEN}✓ GPU workloads stopped${NC}"
    echo -e "${GREEN}✓ GPU is now free for gaming!${NC}"
    echo ""
    log_info "Run '$0 start' when done gaming"
}

# Start workloads
start_workloads() {
    cd "${STACK_DIR}"
    
    log_info "Starting GPU workloads..."
    
    # Check if containers exist
    if docker compose ps -a --format '{{.Name}}' 2>/dev/null | grep -q .; then
        # Containers exist, just start them
        docker compose start
    else
        # No containers, need to create them
        log_info "Containers not found, creating..."
        docker compose up -d
    fi
    
    echo ""
    echo -e "${GREEN}✓ GPU workloads started${NC}"
    echo ""
    
    # Show status
    docker compose ps
}

# Restart workloads
restart_workloads() {
    cd "${STACK_DIR}"
    
    log_info "Restarting GPU workloads..."
    docker compose restart
    
    echo ""
    echo -e "${GREEN}✓ GPU workloads restarted${NC}"
    docker compose ps
}

# Main
main() {
    if [[ $# -lt 1 ]]; then
        show_usage
    fi
    
    check_compose_file
    
    case "${1}" in
        start)
            start_workloads
            ;;
        stop)
            stop_workloads
            ;;
        status)
            get_status
            ;;
        restart)
            restart_workloads
            ;;
        *)
            log_error "Unknown command: ${1}"
            show_usage
            ;;
    esac
}

main "$@"
