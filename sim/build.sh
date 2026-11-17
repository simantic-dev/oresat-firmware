#!/bin/sh
# Rebuild the three ELFs from an unmodified checkout of oresat-firmware at the commit in UPSTREAM.md.
#   ./build.sh /path/to/oresat-firmware
# needs: arm-none-eabi-gcc, `git submodule update --init ext/ChibiOS ext/CANopenNode`, and
# `pip install oresat-configs==0.8.0` (provides oresat-gen-fw-files, which make calls for OD.c).
set -e
SRC=${1:?usage: build.sh /path/to/oresat-firmware}
HERE=$(cd "$(dirname "$0")" && pwd)
git -C "$SRC" checkout oresat05-master
for app in solar battery protocard; do
  cd "$SRC/src/f0/app_$app"
  make clean >/dev/null 2>&1 || true
  EXTRA=
  [ "$app" = battery ] && EXTRA=USE_COPT=-DDEBUG_PRINT
  make USE_BOOTLOADER=no $EXTRA >/dev/null 2>&1
  arm-none-eabi-strip -g -o "$HERE/app_$app.elf" build/app_$app.elf
done
