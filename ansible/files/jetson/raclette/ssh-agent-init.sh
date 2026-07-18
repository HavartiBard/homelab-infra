#!/command/with-contenv sh
# Homelab-specific cont-init.d addition (not part of the upstream hermes-agent
# image): provisions the mounted id_ed25519_homelab key into a persistent
# ssh-agent so Raclette — and the terminal sandboxes it spawns via the
# `docker` terminal backend — can SSH into other homelab hosts.
#
# Runs after the image's own 01-hermes-setup (stage2-hook.sh) and
# 02-reconcile-profiles, as /etc/cont-init.d/03-ssh-agent-setup.sh. Mounted
# in read-only via docker-compose.yml.j2 rather than baked into the image,
# since the image's own cont-init.d scripts are the supported extension
# point for this (avoids overriding ENTRYPOINT, which the image warns
# against — see docker/main-wrapper.sh).
set -eu

HERMES_HOME="${HERMES_HOME:-/opt/data}"
SRC_SSH_DIR="$HERMES_HOME/ssh"
DEST_SSH_DIR="/opt/data/.ssh"
AGENT_SOCK="$HERMES_HOME/agent.sock"

if [ ! -f "$SRC_SSH_DIR/id_ed25519_homelab" ]; then
    echo "[ssh-agent-setup] no homelab key at $SRC_SSH_DIR, skipping"
    exit 0
fi

mkdir -p "$DEST_SSH_DIR"
cp "$SRC_SSH_DIR/id_ed25519_homelab" "$DEST_SSH_DIR/id_ed25519_homelab"
cp "$SRC_SSH_DIR/id_ed25519_homelab" "$DEST_SSH_DIR/id_ed25519"
[ -f "$SRC_SSH_DIR/config" ] && cp "$SRC_SSH_DIR/config" "$DEST_SSH_DIR/config"
chown -R hermes:hermes "$DEST_SSH_DIR"
chmod 700 "$DEST_SSH_DIR"
chmod 600 "$DEST_SSH_DIR/id_ed25519_homelab" "$DEST_SSH_DIR/id_ed25519"

rm -f "$AGENT_SOCK"
s6-setuidgid hermes env HOME=/opt/data ssh-agent -a "$AGENT_SOCK" >/dev/null
chmod 666 "$AGENT_SOCK"
s6-setuidgid hermes env HOME=/opt/data SSH_AUTH_SOCK="$AGENT_SOCK" \
    ssh-add "$DEST_SSH_DIR/id_ed25519" 2>/dev/null || true

echo "[ssh-agent-setup] ssh-agent ready at $AGENT_SOCK"
