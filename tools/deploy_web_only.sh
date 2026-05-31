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
AIRBAND_DATA="$ROOT_DIR/data/airband_frequencies.json"

for required in "$WEB_HTML" "$AIRBAND_DATA"; do
  if [[ ! -f "$required" ]]; then
    echo "Missing required runtime asset:"
    echo "  $required"
    exit 1
  fi
done

if [[ -z "$PLUTO_PASS" ]]; then
  echo "PLUTO_PASS is not set."
  exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
SSHPASS=(sshpass -p "$PLUTO_PASS")

echo "== Local runtime assets =="
wc -c "$WEB_HTML" "$AIRBAND_DATA"
echo

echo "== Copying runtime assets to Pluto+ =="
"${SSHPASS[@]}" ssh "${SSH_OPTS[@]}" "${PLUTO_USER}@${PLUTO_IP}" \
  "mkdir -p '$DEPLOY_DIR/web' '$DEPLOY_DIR/data'"

"${SSHPASS[@]}" scp -O "${SSH_OPTS[@]}" \
  "$WEB_HTML" "${PLUTO_USER}@${PLUTO_IP}:${DEPLOY_DIR}/web/vrs_desktop.html.tmp"

"${SSHPASS[@]}" scp -O "${SSH_OPTS[@]}" \
  "$AIRBAND_DATA" "${PLUTO_USER}@${PLUTO_IP}:${DEPLOY_DIR}/data/airband_frequencies.json.tmp"

"${SSHPASS[@]}" ssh "${SSH_OPTS[@]}" "${PLUTO_USER}@${PLUTO_IP}" "
  mv '${DEPLOY_DIR}/web/vrs_desktop.html.tmp' '${DEPLOY_DIR}/web/vrs_desktop.html' &&
  mv '${DEPLOY_DIR}/data/airband_frequencies.json.tmp' '${DEPLOY_DIR}/data/airband_frequencies.json' &&
  sync &&
  echo '== Remote runtime assets ==' &&
  wc -c '${DEPLOY_DIR}/web/vrs_desktop.html' '${DEPLOY_DIR}/data/airband_frequencies.json' &&
  echo &&
  echo '== Remote HTML Airband marker ==' &&
  grep -n 'airband-listen-ui-v1' '${DEPLOY_DIR}/web/vrs_desktop.html'
"

echo
echo "Runtime asset deployment complete."
