#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/tools/build_pluto_v0_39.sh" "$@"
"$ROOT_DIR/tools/deploy_to_pluto.sh"

echo
echo "Build and deploy complete."
echo "Run the tracker with:"
echo "  ./tools/run_on_pluto.sh"
