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
RUNTIME="$ROOT_DIR/tools/pluto_runtime.sh"
WEB_HTML="$ROOT_DIR/web/vrs_desktop.html"
AIRBAND_DATA="$ROOT_DIR/data/airband_frequencies.json"

for required in "$BIN" "$RUNTIME" "$WEB_HTML" "$AIRBAND_DATA"; do
  if [[ ! -f "$required" ]]; then
    echo "Missing required deploy file: $required"
    exit 1
  fi
done

if ! command -v sshpass >/dev/null 2>&1; then
  echo "Missing sshpass. Install it with:"
  echo "  pacman -S --needed sshpass"
  exit 1
fi

if [[ -z "$PLUTO_PASS" ]]; then
  echo "PLUTO_PASS is not set."
  exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
SSHPASS=(sshpass -p "$PLUTO_PASS")

echo "== Deploying Pluto ADS-B Tracker =="
echo "Target: ${PLUTO_USER}@${PLUTO_IP}:${DEPLOY_DIR}"

"${SSHPASS[@]}" ssh "${SSH_OPTS[@]}" "${PLUTO_USER}@${PLUTO_IP}" \
  "mkdir -p '$DEPLOY_DIR/web' '$DEPLOY_DIR/data'"

"${SSHPASS[@]}" scp -O "${SSH_OPTS[@]}" \
  "$BIN" "${PLUTO_USER}@${PLUTO_IP}:${DEPLOY_DIR}/pluto_adsb_tracker.tmp"

"${SSHPASS[@]}" scp -O "${SSH_OPTS[@]}" \
  "$RUNTIME" "${PLUTO_USER}@${PLUTO_IP}:${DEPLOY_DIR}/run_tracker.sh.tmp"

"${SSHPASS[@]}" scp -O "${SSH_OPTS[@]}" \
  "$WEB_HTML" "${PLUTO_USER}@${PLUTO_IP}:${DEPLOY_DIR}/web/vrs_desktop.html.tmp"

"${SSHPASS[@]}" scp -O "${SSH_OPTS[@]}" \
  "$AIRBAND_DATA" "${PLUTO_USER}@${PLUTO_IP}:${DEPLOY_DIR}/data/airband_frequencies.json.tmp"

"${SSHPASS[@]}" ssh "${SSH_OPTS[@]}" "${PLUTO_USER}@${PLUTO_IP}" "
  chmod +x '${DEPLOY_DIR}/pluto_adsb_tracker.tmp' '${DEPLOY_DIR}/run_tracker.sh.tmp' &&
  mv '${DEPLOY_DIR}/pluto_adsb_tracker.tmp' '${DEPLOY_DIR}/pluto_adsb_tracker' &&
  mv '${DEPLOY_DIR}/run_tracker.sh.tmp' '${DEPLOY_DIR}/run_tracker.sh' &&
  mv '${DEPLOY_DIR}/web/vrs_desktop.html.tmp' '${DEPLOY_DIR}/web/vrs_desktop.html' &&
  mv '${DEPLOY_DIR}/data/airband_frequencies.json.tmp' '${DEPLOY_DIR}/data/airband_frequencies.json' &&
  ls -lh '${DEPLOY_DIR}/pluto_adsb_tracker' \
         '${DEPLOY_DIR}/web/vrs_desktop.html' \
         '${DEPLOY_DIR}/data/airband_frequencies.json'
"

echo
echo "Deploy complete."
