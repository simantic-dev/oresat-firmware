#!/bin/sh
# Records the run the video is built from: the demo scenario with --record, keeping only what collect.py
# reads: every CAN frame a card sent (runs/can.jsonl, virtual-time stamped) and the CANopen master's log.
# Needs sim 0.10.3 or newer (SIM=/path/to/sim to pick one). Then ./make.sh.
set -eu
HERE=$(cd -- "$(dirname -- "$0")" && pwd)
SIM=${SIM:-sim}
REC=$(mktemp -d)
mkdir -p "$HERE/runs"
"$SIM" --version > "$HERE/runs/sim-version.txt"
( cd "$HERE/.." && "$SIM" run --scenario sim/scenario.yaml --timeout 11 --record "$REC" ) > "$REC/console.txt" 2>&1
grep '^\[c3\]' "$REC/console.txt" > "$HERE/runs/c3.log"
python3 -c '
import json, sys
for ln in open(sys.argv[1]):
    if "\"protocol\":\"can\"" in ln:
        f = json.loads(ln)
        if f["direction"] == "tx":
            print(json.dumps({k: f[k] for k in ("t", "machine", "id", "data")}))
' "$REC/frame.jsonl" > "$HERE/runs/can.jsonl"
rm -rf "$REC"
wc -l "$HERE/runs/can.jsonl" "$HERE/runs/c3.log"
