#!/usr/bin/env bash
# Install tools/pluto_autorun.sh onto the Pluto persistent boot-script location.
# Version: install-autorun-v30
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$ROOT_DIR/.pluto.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.pluto.env"
fi

PLUTO_IP="${PLUTO_IP:-192.168.2.1}"
PLUTO_USER="${PLUTO_USER:-root}"
PLUTO_PASS="${PLUTO_PASS:-}"
LOCAL_AUTORUN="${ROOT_DIR}/tools/pluto_autorun.sh"
REMOTE_AUTORUN="/mnt/jffs2/autorun.sh"

if [[ ! -f "$LOCAL_AUTORUN" ]]; then
  echo "Missing local autorun file: $LOCAL_AUTORUN" >&2
  exit 1
fi

if ! command -v sshpass >/dev/null 2>&1; then
  echo "Missing sshpass. Install it with: pacman -S --needed sshpass" >&2
  exit 1
fi

if [[ -z "$PLUTO_PASS" ]]; then
  echo "PLUTO_PASS is not set in .pluto.env or the environment." >&2
  exit 1
fi

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)
SSHPASS=(sshpass -p "$PLUTO_PASS")

echo "Installing Pluto ADS-B Tracker boot launcher..."
echo "Target: ${PLUTO_USER}@${PLUTO_IP}:${REMOTE_AUTORUN}"

"${SSHPASS[@]}" scp -O "${SSH_OPTS[@]}"   "$LOCAL_AUTORUN" "${PLUTO_USER}@${PLUTO_IP}:${REMOTE_AUTORUN}.tmp"

"${SSHPASS[@]}" ssh "${SSH_OPTS[@]}" "${PLUTO_USER}@${PLUTO_IP}" "
  chmod +x '${REMOTE_AUTORUN}.tmp' &&
  mv '${REMOTE_AUTORUN}.tmp' '${REMOTE_AUTORUN}' &&
  sync &&
  ls -l '${REMOTE_AUTORUN}' &&
  echo &&
  sed -n '1,14p' '${REMOTE_AUTORUN}'
"

echo
echo "Installed. The tracker will auto-start after the next Pluto reboot."
echo "Boot log after reboot: /tmp/pluto_adsb_tracker_autorun.log"
echo "Web UI after startup: http://${PLUTO_IP}:8080/VirtualRadar/"
