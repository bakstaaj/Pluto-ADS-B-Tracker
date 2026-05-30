#!/usr/bin/env bash
set -euo pipefail

IMAGE="pluto-adsb-tracker-cross:v0.39"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_ROOT="$(cygpath -w "$ROOT_DIR" | sed 's#\\#/#g')"

REBUILD_IMAGE=0
CLEAN_BUILD=0

usage() {
  cat <<USAGE
Usage: $0 [options]

Options:
  --rebuild-image   Rebuild the Docker toolchain/sysroot image first.
  --clean           Run make clean before compiling.
  --help            Show this help.

Normal use:
  $0

After changing docker/Dockerfile.cross:
  $0 --rebuild-image

For a clean source rebuild:
  $0 --clean
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild-image)
      REBUILD_IMAGE=1
      ;;
    --clean)
      CLEAN_BUILD=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

cd "$ROOT_DIR"

if [[ "$REBUILD_IMAGE" -eq 1 ]]; then
  "$ROOT_DIR/tools/build_cross_image.sh"
elif ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Docker image $IMAGE does not exist. Building it now."
  "$ROOT_DIR/tools/build_cross_image.sh"
else
  echo "Using existing Docker cross-compile image:"
  echo "  $IMAGE"
fi

echo
echo "== Cross-compiling Pluto ADS-B Tracker =="

CLEAN_COMMAND=":"
if [[ "$CLEAN_BUILD" -eq 1 ]]; then
  CLEAN_COMMAND="make clean || true"
fi

MSYS_NO_PATHCONV=1 docker run --rm \
  -v "${HOST_ROOT}:/work" \
  -w /work \
  "$IMAGE" \
  bash -lc "
    set -euo pipefail

    export TOOLCHAIN_DIR=/opt/toolchains/gcc-linaro-7.5.0-2019.12-x86_64_arm-linux-gnueabihf
    export PATH=\"\$TOOLCHAIN_DIR/bin:\$PATH\"
    export CC=arm-linux-gnueabihf-gcc
    export PLUTO_SYSROOT=/opt/pluto/staging

    echo '== Compiler =='
    arm-linux-gnueabihf-gcc --version | head -1
    echo

    $CLEAN_COMMAND

    make \
      CC=arm-linux-gnueabihf-gcc \
      CFLAGS=\"--sysroot=/opt/pluto/staging -I/opt/pluto/staging/usr/include -O2 -g -Wall -W\" \
      LDFLAGS=\"--sysroot=/opt/pluto/staging -L/opt/pluto/staging/usr/lib\"

    mkdir -p dist
    cp dump1090 dist/pluto_adsb_tracker
    arm-linux-gnueabihf-strip dist/pluto_adsb_tracker || true

    echo
    echo '== Built binary =='
    file dist/pluto_adsb_tracker
    ls -lh dist/pluto_adsb_tracker
  "

echo
echo "Build complete:"
echo "  $ROOT_DIR/dist/pluto_adsb_tracker"
