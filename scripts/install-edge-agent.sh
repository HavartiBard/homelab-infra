#!/bin/bash
# install-edge-agent.sh
# Installs Portainer Edge Agent for on-demand workers (WSL2, remote hosts)
#
# Usage: ./install-edge-agent.sh <EDGE_ID> <EDGE_KEY> [PORTAINER_URL]
#
# Get EDGE_ID and EDGE_KEY from Portainer:
# 1. Go to Environments → Add Environment → Edge Agent
# 2. Copy the values from the generated docker command

set -euo pipefail

AGENT_VERSION="${PORTAINER_AGENT_VERSION:-2.21.4}"
CONTAINER_NAME="portainer-edge-agent"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

show_usage() {
    echo "Usage: $0 <EDGE_ID> <EDGE_KEY> [PORTAINER_URL]"
    echo ""
    echo "Arguments:"
    echo "  EDGE_ID       The Edge ID from Portainer (UUID format)"
    echo "  EDGE_KEY      The Edge Key from Portainer (long string)"
    echo "  PORTAINER_URL Optional. Portainer server URL (default: prompt)"
    echo ""
    echo "Get these values from Portainer:"
    echo "  1. Go to Environments → Add Environment → Edge Agent"
    echo "  2. Copy EDGE_ID and EDGE_KEY from the generated command"
    exit 1
}

# Check arguments
if [[ $# -lt 2 ]]; then
    show_usage
fi

EDGE_ID="$1"
EDGE_KEY="$2"
PORTAINER_URL="${3:-}"

# Check Docker access
check_docker_access() {
    if ! docker info &>/dev/null; then
        log_error "Cannot access Docker. Ensure Docker is running."
        log_info "In WSL2, run: sudo service docker start"
        exit 1
    fi
}

# Check if agent already exists
check_existing_agent() {
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_warn "Edge Agent container already exists."
        read -p "Remove and reinstall? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Removing existing agent..."
            docker rm -f "${CONTAINER_NAME}" || true
            docker volume rm portainer_agent_data 2>/dev/null || true
        else
            log_info "Keeping existing agent. Exiting."
            exit 0
        fi
    fi
}

# Get Portainer URL if not provided
get_portainer_url() {
    if [[ -z "${PORTAINER_URL}" ]]; then
        read -p "Enter Portainer Server URL (e.g., https://192.168.1.100:9443): " PORTAINER_URL
    fi
    
    # Validate URL format
    if [[ ! "${PORTAINER_URL}" =~ ^https?:// ]]; then
        log_error "Invalid URL format. Must start with http:// or https://"
        exit 1
    fi
}

# Detect if running in WSL2
detect_wsl2() {
    if grep -qi microsoft /proc/version 2>/dev/null; then
        return 0
    fi
    return 1
}

# Install Edge Agent
install_edge_agent() {
    log_info "Installing Portainer Edge Agent v${AGENT_VERSION}..."
    
    local extra_opts=""
    
    # WSL2-specific considerations
    if detect_wsl2; then
        log_info "WSL2 environment detected"
        extra_opts="-e EDGE_INSECURE_POLL=1"
    fi

    docker run -d \
        --name "${CONTAINER_NAME}" \
        --restart always \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v /var/lib/docker/volumes:/var/lib/docker/volumes \
        -v /:/host \
        -v portainer_agent_data:/data \
        -e EDGE=1 \
        -e EDGE_ID="${EDGE_ID}" \
        -e EDGE_KEY="${EDGE_KEY}" \
        ${extra_opts} \
        "portainer/agent:${AGENT_VERSION}"

    # Wait for container to start
    sleep 5

    # Verify agent is running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "Edge Agent installed successfully!"
        log_info ""
        log_info "The agent will connect to Portainer automatically."
        log_info "Check the Environments page in Portainer for status."
        log_info ""
        log_info "View logs: docker logs ${CONTAINER_NAME}"
    else
        log_error "Agent failed to start. Check logs:"
        docker logs "${CONTAINER_NAME}" 2>&1 | tail -20
        exit 1
    fi
}

# Check GPU availability (for WSL2 workers)
check_gpu() {
    if detect_wsl2; then
        log_info "Checking NVIDIA GPU availability..."
        if command -v nvidia-smi &>/dev/null; then
            if nvidia-smi &>/dev/null; then
                log_info "NVIDIA GPU detected and accessible"
                log_info "GPU workloads should work correctly"
            else
                log_warn "nvidia-smi found but GPU not accessible"
                log_warn "Ensure NVIDIA drivers are installed on Windows host"
            fi
        else
            log_warn "nvidia-smi not found"
            log_warn "Install nvidia-container-toolkit for GPU workloads"
        fi
    fi
}

# Main
main() {
    log_info "Portainer Edge Agent Installation Script"
    log_info "========================================"
    
    check_docker_access
    check_existing_agent
    get_portainer_url
    install_edge_agent
    check_gpu
    
    log_info ""
    log_info "Installation complete!"
    log_info ""
    log_info "To stop workloads for gaming:"
    log_info "  docker stop \$(docker ps -q)"
    log_info ""
    log_info "To restart workloads:"
    log_info "  docker start \$(docker ps -aq)"
}

main
