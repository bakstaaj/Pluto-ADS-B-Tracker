#!/bin/sh
# Pluto ADS-B Tracker boot launcher
# Installed as: /mnt/jffs2/autorun.sh
# Version: autorun-v30
#
# Pluto firmware v0.39 sources /mnt/jffs2/autorun.sh during startup.
# Keep this script safe when sourced: it starts the tracker in the background
# and does not call exit.

PLUTO_ADSB_DEPLOY_DIR="/mnt/jffs2/pluto_adsb_tracker"
PLUTO_ADSB_RUNNER="${PLUTO_ADSB_DEPLOY_DIR}/run_tracker.sh"
PLUTO_ADSB_LOG="/tmp/pluto_adsb_tracker_autorun.log"

pluto_adsb_tracker_is_running() {
    ps 2>/dev/null |
        grep -E 'pluto_adsb_tracker|pluto_adsb_trac|dump1090' |
        grep -v grep >/dev/null 2>&1
}

pluto_adsb_tracker_autorun() {
    {
        echo "== Pluto ADS-B Tracker autorun-v30 =="
        echo "Boot launch request: $(date -u 2>/dev/null || echo unknown-time)"
        echo "Application directory: ${PLUTO_ADSB_DEPLOY_DIR}"

        if [ ! -x "${PLUTO_ADSB_RUNNER}" ]; then
            echo "ERROR: Missing executable runtime launcher: ${PLUTO_ADSB_RUNNER}"
            return 1
        fi

        if pluto_adsb_tracker_is_running; then
            echo "Tracker already appears to be running; not starting a duplicate."
            return 0
        fi

        # Run in a background shell so a sourced autorun file never blocks boot.
        # --net provides the web UI/endpoints without continuously rendering the
        # terminal aircraft table into a boot log.
        (
            sleep 5
            if pluto_adsb_tracker_is_running; then
                echo "Tracker was started by another process during boot delay."
            else
                echo "Starting Pluto ADS-B Tracker in network/web mode..."
                PLUTO_DEPLOY_DIR="${PLUTO_ADSB_DEPLOY_DIR}"                     "${PLUTO_ADSB_RUNNER}" -- --net
            fi
        ) >> "${PLUTO_ADSB_LOG}" 2>&1 &

        echo "Startup scheduled in background. Runtime log: ${PLUTO_ADSB_LOG}"
    } >> "${PLUTO_ADSB_LOG}" 2>&1
}

pluto_adsb_tracker_autorun

# Avoid leaving helper function names in the shell that sourced autorun.sh.
unset -f pluto_adsb_tracker_autorun pluto_adsb_tracker_is_running 2>/dev/null || true
