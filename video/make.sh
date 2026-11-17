#!/usr/bin/env bash
# Builds the OreSat demo video: fetches the Simantic video kit into .kit/ (needs access to the simulator's
# repository), writes data.js from runs/ (record.sh), renders oresat-demo.mp4, or stills with --stills 3 20 ...
# env: PYRITE (simulator checkout, default ~/dev/simantic/pyrite), PY (python with playwright + imageio-ffmpeg)
set -euo pipefail
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
PYRITE=${PYRITE:-$HOME/dev/simantic/pyrite} PY=${PY:-python3}
rm -rf "$HERE/.kit" && mkdir -p "$HERE/.kit"
git -C "$PYRITE" archive origin/main docs/video/assets docs/video/render.py | tar -x -C "$HERE/.kit" --strip-components=2
"$PY" "$HERE/collect.py" "$HERE/data.js"
"$PY" "$HERE/.kit/render.py" "$HERE/video.html" "$HERE/oresat-demo.mp4" "$@"
