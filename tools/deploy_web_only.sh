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
WEB_HTML="$ROOT_DIR/web/vrs_desktop.html"

if [[ ! -f "$WEB_HTML" ]]; then
  echo "Missing web page: $WEB_HTML"
  exit 1
fi

if [[ -z "$PLUTO_PASS" ]]; then
  echo "PLUTO_PASS is not set."
  exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
SSHPASS=(sshpass -p "$PLUTO_PASS")

"${SSHPASS[@]}" ssh "${SSH_OPTS[@]}" "${PLUTO_USER}@${PLUTO_IP}" \
  "mkdir -p '$DEPLOY_DIR/web'"

"${SSHPASS[@]}" scp -O "${SSH_OPTS[@]}" \
  "$WEB_HTML" "${PLUTO_USER}@${PLUTO_IP}:${DEPLOY_DIR}/web/vrs_desktop.html.tmp"

"${SSHPASS[@]}" ssh "${SSH_OPTS[@]}" "${PLUTO_USER}@${PLUTO_IP}" \
  "mv '${DEPLOY_DIR}/web/vrs_desktop.html.tmp' '${DEPLOY_DIR}/web/vrs_desktop.html'"

echo "Updated web interface:"
echo "  http://${PLUTO_IP}:8080/VirtualRadar/"
