#!/usr/bin/env bash
set -euo pipefail

IMAGE="pluto-adsb-tracker-cross:v0.39"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

HOST_ROOT="$(cygpath -w "$ROOT_DIR" | sed 's#\\#/#g')"
HOST_DOCKERFILE="$(cygpath -w "$ROOT_DIR/docker/Dockerfile.cross" | sed 's#\\#/#g')"

cd "$ROOT_DIR"

echo "== Path check =="
echo "MSYS ROOT_DIR:      $ROOT_DIR"
echo "Docker HOST_ROOT:   $HOST_ROOT"
echo "Dockerfile:         $HOST_DOCKERFILE"
echo

echo "== Building Docker cross-compile image =="
MSYS_NO_PATHCONV=1 docker build --no-cache \
  -t "$IMAGE" \
  -f "$HOST_DOCKERFILE" \
  "$HOST_ROOT"

echo
echo "== Cross-compiling dump1090 for Pluto+ =="
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "${HOST_ROOT}:/work" \
  -w /work \
  "$IMAGE" \
  bash -lc '
    set -euo pipefail

    export TOOLCHAIN_DIR=/opt/toolchains/gcc-linaro-7.5.0-2019.12-x86_64_arm-linux-gnueabihf
    export PATH="$TOOLCHAIN_DIR/bin:$PATH"
    export CC=arm-linux-gnueabihf-gcc
    export PLUTO_SYSROOT=/opt/pluto/staging

    echo "== Compiler check =="
    which arm-linux-gnueabihf-gcc
    arm-linux-gnueabihf-gcc --version
    echo

    make clean || true

    make \
      CC=arm-linux-gnueabihf-gcc \
      CFLAGS="--sysroot=/opt/pluto/staging -I/opt/pluto/staging/usr/include -O2 -g -Wall -W" \
      LDFLAGS="--sysroot=/opt/pluto/staging -L/opt/pluto/staging/usr/lib"

    mkdir -p dist
    cp dump1090 dist/pluto_adsb_tracker
    arm-linux-gnueabihf-strip dist/pluto_adsb_tracker || true

    echo
    echo "== Built binary =="
    file dist/pluto_adsb_tracker
    ls -lh dist/pluto_adsb_tracker
  '

echo
echo "Build complete:"
echo "  $ROOT_DIR/dist/pluto_adsb_tracker"
