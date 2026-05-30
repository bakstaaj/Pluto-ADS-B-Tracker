#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$ROOT_DIR/.pluto.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.pluto.env"
fi

PLUTO_IP="${PLUTO_IP:-192.168.2.1}"
PLUTO_USER="${PLUTO_USER:-root}"
PLUTO_PASS="${PLUTO_PASS:-}"
DEPLOY_DIR="${PLUTO_DEPLOY_DIR:-/mnt/jffs2/pluto_adsb_tracker}"

BIN="$ROOT_DIR/dist/pluto_adsb_tracker"

if [[ ! -f "$BIN" ]]; then
  echo "Missing binary: $BIN"
  echo "Run ./tools/build_pluto_v0_39.sh first."
  exit 1
fi

if ! command -v sshpass >/dev/null 2>&1; then
  echo "Missing sshpass. Install it with:"
  echo "  pacman -S --needed sshpass"
  exit 1
fi

if [[ -z "$PLUTO_PASS" ]]; then
  echo "PLUTO_PASS is not set."
  echo "Create $ROOT_DIR/.pluto.env or export PLUTO_PASS before running."
  exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
SSHPASS=(sshpass -p "$PLUTO_PASS")

echo "== Deploying to Pluto+ =="
echo "Target: ${PLUTO_USER}@${PLUTO_IP}:${DEPLOY_DIR}"
echo

"${SSHPASS[@]}" ssh "${SSH_OPTS[@]}" "${PLUTO_USER}@${PLUTO_IP}" \
  "mkdir -p '$DEPLOY_DIR'"

"${SSHPASS[@]}" scp -O "${SSH_OPTS[@]}" \
  "$BIN" "${PLUTO_USER}@${PLUTO_IP}:${DEPLOY_DIR}/pluto_adsb_tracker.tmp"

"${SSHPASS[@]}" ssh "${SSH_OPTS[@]}" "${PLUTO_USER}@${PLUTO_IP}" "
  chmod +x '${DEPLOY_DIR}/pluto_adsb_tracker.tmp' &&
  mv '${DEPLOY_DIR}/pluto_adsb_tracker.tmp' '${DEPLOY_DIR}/pluto_adsb_tracker' &&
  ls -lh '${DEPLOY_DIR}/pluto_adsb_tracker'
"

echo
echo "Deploy complete."
