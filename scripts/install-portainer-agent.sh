#!/bin/bash
# install-portainer-agent.sh
# Installs Portainer Agent on a Linux Docker host
#
# Usage: ./install-portainer-agent.sh [--unraid]
#
# Options:
#   --unraid    Use Unraid-specific paths for volume mounts

set -euo pipefail

AGENT_VERSION="${PORTAINER_AGENT_VERSION:-2.21.4}"
AGENT_PORT="${PORTAINER_AGENT_PORT:-9001}"
CONTAINER_NAME="portainer-agent"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root or with docker access
check_docker_access() {
    if ! docker info &>/dev/null; then
        log_error "Cannot access Docker. Run with sudo or add user to docker group."
        exit 1
    fi
}

# Check if agent is already running
check_existing_agent() {
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_warn "Portainer Agent container already exists."
        read -p "Remove and reinstall? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Removing existing agent..."
            docker rm -f "${CONTAINER_NAME}" || true
        else
            log_info "Keeping existing agent. Exiting."
            exit 0
        fi
    fi
}

# Detect if running on Unraid
detect_unraid() {
    if [[ -f /etc/unraid-version ]] || [[ "$1" == "--unraid" ]]; then
        return 0
    fi
    return 1
}

# Install agent with appropriate volume mounts
install_agent() {
    local volumes_path="/var/lib/docker/volumes"
    
    # Check for Unraid
    if detect_unraid "${1:-}"; then
        log_info "Detected Unraid - using Unraid-specific configuration"
        # Unraid typically uses /mnt/user/appdata for persistent storage
        # but Docker volumes are still in /var/lib/docker/volumes
    fi

    log_info "Installing Portainer Agent v${AGENT_VERSION}..."
    
    docker run -d \
        --name "${CONTAINER_NAME}" \
        --restart always \
        -p "${AGENT_PORT}:9001" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "${volumes_path}:${volumes_path}" \
        "portainer/agent:${AGENT_VERSION}"

    # Wait for container to start
    sleep 3

    # Verify agent is running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "Portainer Agent installed successfully!"
        log_info "Agent is listening on port ${AGENT_PORT}"
        log_info ""
        log_info "Next steps:"
        log_info "1. In Portainer, go to Environments → Add Environment"
        log_info "2. Select 'Agent' and enter: $(hostname -I | awk '{print $1}'):${AGENT_PORT}"
        log_info "3. Click Connect"
    else
        log_error "Agent failed to start. Check logs with: docker logs ${CONTAINER_NAME}"
        exit 1
    fi
}

# Configure firewall (if UFW is available)
configure_firewall() {
    if command -v ufw &>/dev/null; then
        log_info "UFW detected. Configure firewall to restrict agent access?"
        read -p "Enter Platform VM IP (or 'skip'): " platform_ip
        
        if [[ "${platform_ip}" != "skip" ]]; then
            log_info "Allowing port ${AGENT_PORT} from ${platform_ip} only..."
            sudo ufw allow from "${platform_ip}" to any port "${AGENT_PORT}" proto tcp
            log_info "Firewall rule added."
        fi
    fi
}

# Main
main() {
    log_info "Portainer Agent Installation Script"
    log_info "===================================="
    
    check_docker_access
    check_existing_agent
    install_agent "${1:-}"
    configure_firewall
    
    log_info ""
    log_info "Installation complete!"
}

main "$@"
