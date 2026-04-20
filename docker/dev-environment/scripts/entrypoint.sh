#!/bin/bash
set -e

DEV_USER="${DEV_USER:-james}"
HOME_DIR="/home/$DEV_USER"
DEV_SAFE_MODE="${DEV_SAFE_MODE:-true}"
DEV_MANAGE_HOME_CONFIGS="${DEV_MANAGE_HOME_CONFIGS:-false}"

is_true() {
    case "${1,,}" in
        1|true|yes|on) return 0 ;;
        *) return 1 ;;
    esac
}

# =============================================================================
# Fix Docker socket permissions
# =============================================================================
if [ -S /var/run/docker.sock ]; then
    SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
    # Update the docker group GID to match the host socket
    if getent group docker > /dev/null 2>&1; then
        groupmod -g "$SOCK_GID" docker 2>/dev/null || true
    else
        groupadd -g "$SOCK_GID" docker
    fi
    usermod -aG docker "$DEV_USER" 2>/dev/null || true
fi

if ! is_true "$DEV_SAFE_MODE"; then
    # =========================================================================
    # Ensure home directory ownership
    # =========================================================================
    # Only fix top-level ownership to avoid slow recursive chown on large volumes
    chown "$DEV_USER:$DEV_USER" "$HOME_DIR"

    # Ensure .ssh directory exists with correct perms
    mkdir -p "$HOME_DIR/.ssh"
    chmod 700 "$HOME_DIR/.ssh"
    chown "$DEV_USER:$DEV_USER" "$HOME_DIR/.ssh"

    # Fix authorized_keys permissions if it exists
    if [ -f "$HOME_DIR/.ssh/authorized_keys" ]; then
        chmod 600 "$HOME_DIR/.ssh/authorized_keys" 2>/dev/null || true
    fi

    # =========================================================================
    # Ensure projects directory exists
    # =========================================================================
    mkdir -p "$HOME_DIR/projects"
    chown "$DEV_USER:$DEV_USER" "$HOME_DIR/projects"

    # =========================================================================
    # Ensure config directories exist
    # =========================================================================
    mkdir -p "$HOME_DIR/.config/opencode"
    mkdir -p "$HOME_DIR/.cache/opencode"
    mkdir -p "$HOME_DIR/.codex"
    chown "$DEV_USER:$DEV_USER" "$HOME_DIR/.config" "$HOME_DIR/.config/opencode" \
        "$HOME_DIR/.cache" "$HOME_DIR/.cache/opencode" "$HOME_DIR/.codex"

    # =========================================================================
    # 1Password SSH agent socket directory
    # =========================================================================
    OP_SOCK_DIR="$HOME_DIR/.1password"
    mkdir -p "$OP_SOCK_DIR"
    chown "$DEV_USER:$DEV_USER" "$OP_SOCK_DIR"

    # Create oh-my-zsh cache dir in home for persistence
    mkdir -p "$HOME_DIR/.cache/oh-my-zsh"
    chown "$DEV_USER:$DEV_USER" "$HOME_DIR/.cache/oh-my-zsh"
else
    echo "DEV_SAFE_MODE enabled: skipping home ownership/permission/directory writes."
fi

if is_true "$DEV_MANAGE_HOME_CONFIGS"; then
    # =========================================================================
    # Managed shell config in persistent home (opt-in)
    # =========================================================================
    cp /etc/skel/.zshrc "$HOME_DIR/.zshrc"
    chown "$DEV_USER:$DEV_USER" "$HOME_DIR/.zshrc"

    ENV_FILE="$HOME_DIR/.env_container"
    cat > "$ENV_FILE" <<'ENVEOF'
# Container environment - sourced by shell rc
ENVEOF

    for var in OPENROUTER_API_KEY LMSTUDIO_API_KEY LMSTUDIO_BASE_URL OP_SERVICE_ACCOUNT_TOKEN NOTION_MCP_TOKEN GITEA_TOKEN CODEX_CONFIG_FILE TZ; do
        if [ -n "${!var}" ]; then
            echo "export $var=\"${!var}\"" >> "$ENV_FILE"
        fi
    done

    chown "$DEV_USER:$DEV_USER" "$ENV_FILE"
    chmod 600 "$ENV_FILE"

    BASHRC="$HOME_DIR/.bashrc"
    if [ ! -f "$BASHRC" ] || ! grep -q '.env_container' "$BASHRC" 2>/dev/null; then
        cat >> "$BASHRC" <<'BASHEOF'
# Container environment
[ -f ~/.env_container ] && source ~/.env_container

# Go
export GOPATH="$HOME/go"
export PATH="$GOPATH/bin:/usr/local/go/bin:$PATH"
BASHEOF
        chown "$DEV_USER:$DEV_USER" "$BASHRC"
    fi
else
    echo "DEV_MANAGE_HOME_CONFIGS disabled: leaving .zshrc/.env_container/.bashrc untouched."
fi

# =============================================================================
# VS Code Remote Tunnel (background)
# =============================================================================
VSCODE_DATA="$HOME_DIR/.vscode-cli"
if ! is_true "$DEV_SAFE_MODE"; then
    mkdir -p "$VSCODE_DATA"
    chown "$DEV_USER:$DEV_USER" "$VSCODE_DATA"
fi

if command -v code &> /dev/null; then
    TUNNEL_NAME="${VSCODE_TUNNEL_NAME:-dev-box}"
    echo "Starting VS Code tunnel as '$TUNNEL_NAME'..."
    su - "$DEV_USER" -c "code tunnel --accept-server-license-terms --name '$TUNNEL_NAME' &" \
        >> /var/log/vscode-tunnel.log 2>&1 &
fi

# =============================================================================
# Start SSH server (PID 1)
# =============================================================================
echo "Starting SSH server..."
exec /usr/sbin/sshd -D -e
