#!/usr/bin/env bash
set -euo pipefail

TUNNEL_NAME="dev-vm"
SERVICE_NAME="vscode-tunnel.service"
DOWNLOAD_URL="${VSCODE_CLI_DOWNLOAD_URL:-https://update.code.visualstudio.com/latest/cli-linux-x64/stable}"
CLI_DIR="${HOME}/.local/share/vscode-cli"
CLI_BIN="${CLI_DIR}/bin/code"
USER_BIN="${HOME}/.local/bin/code"
AGENT_DIR="${HOME}/.vscode-tunnel"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_SOURCE="${REPO_ROOT}/systemd/${SERVICE_NAME}"
WORK_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

log() {
  echo "[+] $*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

is_vscode_server_cli() {
  local bin="$1"
  local target
  target="$(readlink -f "${bin}" 2>/dev/null || echo "${bin}")"
  [[ "${target}" == *"/.vscode-server/cli/"* ]]
}

is_tunnel_capable() {
  local bin="$1"
  if is_vscode_server_cli "${bin}"; then
    return 1
  fi

  "${bin}" tunnel --help >/dev/null 2>&1
}

fetch() {
  local url="$1"
  local dest="$2"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "${url}" -o "${dest}"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "${dest}" "${url}"
  else
    echo "Install curl or wget to download the VS Code CLI." >&2
    exit 1
  fi
}

ensure_non_root() {
  if [ "$(id -u)" -eq 0 ]; then
    echo "Run this script as the non-root tunnel user (e.g., james)." >&2
    exit 1
  fi
}

enable_lingering() {
  local status
  status="$(loginctl show-user "$USER" -p Linger --value 2>/dev/null || true)"
  if [ "${status}" = "yes" ]; then
    log "systemd lingering already enabled for ${USER}"
    return
  fi

  log "Enabling systemd lingering for ${USER} (allows user service at boot; requires sudo)"
  sudo loginctl enable-linger "${USER}"
}

install_cli_from_download() {
  log "Installing VS Code CLI into ${CLI_DIR}"
  local archive="${WORK_DIR}/vscode-cli.tar.gz"
  fetch "${DOWNLOAD_URL}" "${archive}"

  mkdir -p "${WORK_DIR}/extract"
  tar -xzf "${archive}" -C "${WORK_DIR}/extract"

  local code_candidate
  code_candidate="$(find "${WORK_DIR}/extract" -type f -name code -perm -u+x | head -n 1 || true)"
  if [ -z "${code_candidate}" ]; then
    echo "Unable to locate the VS Code CLI binary in the downloaded archive." >&2
    exit 1
  fi

  rm -rf "${CLI_DIR}"
  mkdir -p "${CLI_DIR}/bin"
  cp "${code_candidate}" "${CLI_DIR}/bin/code"
  chmod +x "${CLI_DIR}/bin/code"

  if [ ! -x "${CLI_BIN}" ]; then
    echo "VS Code CLI binary missing after install (${CLI_BIN})." >&2
    exit 1
  fi

  mkdir -p "$(dirname "${USER_BIN}")"
  ln -sf "${CLI_BIN}" "${USER_BIN}"
  log "VS Code CLI installed at ${CLI_BIN}"
}

ensure_cli() {
  mkdir -p "${CLI_DIR}" "${AGENT_DIR}" "$(dirname "${USER_BIN}")"

  if [ -x "${CLI_BIN}" ]; then
    if is_tunnel_capable "${CLI_BIN}"; then
      log "VS Code CLI already present at ${CLI_BIN}"
      ln -sf "${CLI_BIN}" "${USER_BIN}"
      return
    else
      log "Existing CLI at ${CLI_BIN} is not tunnel-capable; reinstalling official CLI"
      rm -rf "${CLI_DIR}"
    fi
  fi

  if command -v code >/dev/null 2>&1; then
    local existing
    existing="$(command -v code)"
    if is_tunnel_capable "${existing}"; then
      log "Using existing VS Code command at ${existing}"
      mkdir -p "$(dirname "${CLI_BIN}")"
      ln -sf "${existing}" "${CLI_BIN}"
      ln -sf "${existing}" "${USER_BIN}"
      return
    else
      log "Existing VS Code command at ${existing} is not tunnel-capable; installing standalone CLI"
    fi
  fi

  install_cli_from_download
}

install_systemd_unit() {
  if [ ! -f "${SERVICE_SOURCE}" ]; then
    echo "Systemd unit template not found at ${SERVICE_SOURCE}" >&2
    exit 1
  fi

  mkdir -p "${SYSTEMD_USER_DIR}"
  ln -sf "${SERVICE_SOURCE}" "${SYSTEMD_USER_DIR}/${SERVICE_NAME}"
  log "Linked systemd unit to ${SYSTEMD_USER_DIR}/${SERVICE_NAME}"
}

enable_service() {
  systemctl --user daemon-reload

  set +e
  systemctl --user enable --now "${SERVICE_NAME}"
  local enable_status=$?
  set -e

  if [ "${enable_status}" -ne 0 ]; then
    echo
    echo "The service failed to start (likely needs initial device login)." >&2
    echo "Run the login once interactively, then restart the service:" >&2
    echo "  VSCODE_AGENT_FOLDER=\"${AGENT_DIR}\" ${CLI_BIN} tunnel user login --provider github" >&2
    echo "After login, you can switch providers with --provider microsoft if desired." >&2
    echo "After login, run: systemctl --user restart ${SERVICE_NAME}" >&2
    exit "${enable_status}"
  fi

  systemctl --user restart "${SERVICE_NAME}"
}

print_status() {
  echo
  log "Service status (systemctl --user status ${SERVICE_NAME}):"
  systemctl --user status "${SERVICE_NAME}" --no-pager --full || true

  echo
  log "Key commands:"
  echo "  Check status: systemctl --user status ${SERVICE_NAME}"
  echo "  View logs:    journalctl --user -u ${SERVICE_NAME} -f"
  echo "  Restart:      systemctl --user restart ${SERVICE_NAME}"
  echo "  Stop:         systemctl --user stop ${SERVICE_NAME}"
  echo "  Re-run setup: ${REPO_ROOT}/scripts/$(basename "$0")"
  echo "  Connect:      https://vscode.dev/tunnel/${TUNNEL_NAME}"
}

main() {
  ensure_non_root
  require_cmd systemctl
  require_cmd loginctl
  require_cmd sudo
  require_cmd tar

  ensure_cli
  enable_lingering
  install_systemd_unit
  enable_service
  print_status
}

main "$@"
