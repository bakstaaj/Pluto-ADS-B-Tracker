#!/usr/bin/env bash
set -euo pipefail

IMAGE="pluto-adsb-tracker-cross:v0.39"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HOST_ROOT="$(cygpath -w "$ROOT_DIR" | sed 's#\\#/#g')"
HOST_DOCKERFILE="$(cygpath -w "$ROOT_DIR/docker/Dockerfile.cross" | sed 's#\\#/#g')"

NO_CACHE_ARGS=()
if [[ "${1:-}" == "--no-cache" ]]; then
  NO_CACHE_ARGS+=(--no-cache)
fi

echo "== Building Pluto ADS-B cross-compile image =="
echo "Image:      $IMAGE"
echo "Dockerfile: $HOST_DOCKERFILE"
echo

MSYS_NO_PATHCONV=1 docker build \
  "${NO_CACHE_ARGS[@]}" \
  -t "$IMAGE" \
  -f "$HOST_DOCKERFILE" \
  "$HOST_ROOT"

echo
echo "== Verifying cross compiler image =="
MSYS_NO_PATHCONV=1 docker run --rm "$IMAGE" bash -lc '
  set -e
  which arm-linux-gnueabihf-gcc
  arm-linux-gnueabihf-gcc --version | head -1
  test -d /opt/pluto/staging/usr/include
  echo "Pluto v0.39 sysroot present."
'

echo
echo "Docker cross-compile image is ready:"
echo "  $IMAGE"
