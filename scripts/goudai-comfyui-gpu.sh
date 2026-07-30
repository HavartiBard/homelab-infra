#!/usr/bin/env bash
set -euo pipefail

# Inspect and release ComfyUI's ROCm/PyTorch allocations on goudai.
# Recent history is only a best-effort indication of workflow model names.

target="${GOUDai_SSH_TARGET:-james@192.168.20.150}"
api="http://127.0.0.1:8188"

usage() {
  cat <<'EOF'
Usage: scripts/goudai-comfyui-gpu.sh <status|free|restart>

  status   Show ComfyUI device/PyTorch memory, queue, and recent model names
  free     Ask ComfyUI to unload cached models and release allocator memory
  restart  Restart ComfyUI (strongest cleanup; interrupts active work)

Set GOUDai_SSH_TARGET to override the SSH target.
EOF
}

remote_curl() {
  local path="$1"
  ssh -o BatchMode=yes "$target" "curl -fsS '${api}${path}'"
}

status() {
  local stats queue history
  stats="$(remote_curl /system_stats)"
  queue="$(remote_curl /queue)"
  history="$(remote_curl '/history?max_items=20')"

  jq -r '
    .devices[] |
    "device: \(.name)\n  VRAM: \((.vram_total / 1073741824) | floor) GiB total, \((.vram_free / 1073741824) | floor) GiB free\n  PyTorch: \((.torch_vram_total / 1073741824) | floor) GiB total, \((.torch_vram_free / 1073741824) | floor) GiB free"
  ' <<<"$stats"

  printf '\nqueue: '
  jq -r '"\(.queue_running | length) running, \(.queue_pending | length) pending"' <<<"$queue"

  printf '\nmodels seen in recent workflow history (best effort):\n'
  jq -r '
    [ .[]
      | .prompt[2][]?
      | .inputs? // {}
      | to_entries[]
      | select(.key | test("ckpt|unet|model|vae|clip"; "i"))
      | .value
      | select(type == "string")
    ] | unique[]?
  ' <<<"$history" | sed 's/^/  /'
}

free_memory() {
  ssh -o BatchMode=yes "$target" \
    "curl -fsS -X POST -H 'Content-Type: application/json' -d '{\"unload_models\":true,\"free_memory\":true}' '${api}/free'"
  printf '\nComfyUI cache release requested. Current state:\n\n'
  status
}

case "${1:-}" in
  status) status ;;
  free) free_memory ;;
  restart) ssh -o BatchMode=yes "$target" 'docker restart comfyui' ;;
  *) usage >&2; exit 2 ;;
esac
