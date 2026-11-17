#!/usr/bin/env python3
"""Writes data.js for the OreSat video from the recorded run (record.sh): every CAN frame the cards and the
CANopen master sent (runs/can.jsonl, virtual time) and the master's own log (runs/c3.log). Every number on
screen comes from here; the asserts check each claim the video makes against both sources.

  collect.py [data.js]
"""
import importlib.util, json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
frames = [json.loads(l) for l in open(HERE / "runs/can.jsonl")]
c3log = (HERE / "runs/c3.log").read_text()
spec = importlib.util.spec_from_file_location("c3_peer", HERE.parent / "sim/c3_peer.py")
c3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(c3)   # SCRIPT: labels, units, signedness
out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data.js"

STATE = {0x00: "boot-up", 0x04: "stopped", 0x05: "operational", 0x7F: "pre-operational"}
NAMES = {0x0C: "solar", 0x04: "battery", 0x30: "protocard"}
le = lambda b, signed: int.from_bytes(b, "little", signed=signed)

hb = {n: [] for n in NAMES}            # node -> [(t, state)]
sdo, nmt, pdo, pend = [], [], [], {}
labels = {(node, a[0], a[1]): a for t, op, node, a in c3.SCRIPT if op == "sdo_read"}
for f in frames:
    cid, d, t = f["id"], bytes.fromhex(f["data"]), f["t"]
    fn, node = cid & 0x780, cid & 0x7F
    if cid == 0:
        nmt.append({"t": t, "cmd": {1: "start", 2: "stop"}.get(d[0], hex(d[0])), "node": d[1]})
    elif fn == 0x700:
        hb.setdefault(node, []).append((t, d[0]))
    elif fn == 0x600:                  # master -> card: SDO request
        pend[node] = (t, d)
    elif fn == 0x580:                  # card -> master: SDO reply
        tq, q = pend.pop(node)
        idx, sub = q[1] | q[2] << 8, q[3]
        if q[0] == 0x40:               # upload (read), expedited reply carries 4 - n bytes
            n = 4 - (d[0] >> 2 & 3)
            _, _, label, signed, unit = labels[(node, idx, sub)]
            sdo.append({"t": tq, "t_reply": t, "node": node, "op": "read", "idx": idx, "sub": sub, "label": label,
                        "value": le(d[4:4 + n], signed), "unit": unit})
        else:                          # download (write)
            n = 4 - (q[0] >> 2 & 3)
            sdo.append({"t": tq, "t_reply": t, "node": node, "op": "write", "idx": idx, "sub": sub,
                        "value": le(q[4:4 + n], False), "ok": d[0] == 0x60})
    elif fn in (0x180, 0x280, 0x380, 0x480) and any(d):
        pdo.append({"t": t, "node": node, "n": (fn >> 8), "data": f["data"]})

# --- what the video claims, checked
for n in NAMES:
    assert hb[n] and hb[n][0][1] == 0x00 and hb[n][0][0] < 0.01, f"node {n:#x} boot-up within 10 ms"
for s in [s for s in sdo if s["op"] == "read"]:
    unit = (" " + s["unit"]) if s["unit"] else " "
    want = f"SDO upload ok {c3.NAMES.get(s['node'], 'node')}(0x{s['node']:02X}) {s['idx']:04X}:{s['sub']:02X} {s['label']} = {s['value']}{unit}"
    assert want.rstrip() in c3log, f"decoded value not in the master's log: {want}"
w = next(s for s in sdo if s["op"] == "write")
assert w["node"] == 0x0C and w["idx"] == 0x1017 and w["value"] == 250 and w["ok"]
solar_hb = [t for t, _ in hb[0x0C]]
gaps = lambda a, b: [round((y - x) * 1000) for x, y in zip(solar_hb, solar_hb[1:]) if a <= x and y < b]
before, after = gaps(1, w["t_reply"]), gaps(w["t_reply"] + 0.3, nmt[0]["t"])
assert before and all(abs(g - 1000) <= 2 for g in before), before
assert after and all(abs(g - 250) <= 2 for g in after), after
stop, start = nmt
assert (stop["cmd"], stop["node"], start["cmd"], start["node"]) == ("stop", 0x0C, "start", 0x0C)
assert all(s == 0x04 for t, s in hb[0x0C] if stop["t"] < t < start["t"]), "stopped state between NMT stop and start"
assert not any(p["node"] == 0x0C and stop["t"] < p["t"] < start["t"] for p in pdo), "no solar PDOs while stopped"
resumed = [p for p in pdo if p["node"] == 0x0C and p["t"] > start["t"]]
r = bytes.fromhex(resumed[0]["data"])
vals = [le(r[i:i + 2], True) for i in (0, 2, 4)]
read = {s["label"]: s["value"] for s in sdo if s["op"] == "read" and s["node"] == 0x0C}
assert vals == [read["output.voltage"], read["output.current"], read["output.power"]], (vals, read)

kind = lambda i: {0: "nmt", 0x700: "heartbeat", 0x600: "sdo_request", 0x580: "sdo_reply"}.get(0 if i == 0 else i & 0x780, "pdo" if (i & 0x780) in (0x180, 0x280, 0x380, 0x480) else "other")
counts = {}
for f in frames:
    counts[kind(f["id"])] = counts.get(kind(f["id"]), 0) + 1
assert "other" not in counts and counts["sdo_request"] == counts["sdo_reply"] == len(sdo) and counts["nmt"] == len(nmt), counts

DATA = {
    "counts": counts,
    "sim": (HERE / "runs/sim-version.txt").read_text().strip(),
    "names": {f"{n}": v for n, v in NAMES.items()},
    "heartbeats": {f"{n}": [[round(t, 4), s] for t, s in v] for n, v in hb.items() if n in NAMES},
    "sdo": sdo, "nmt": nmt, "pdo_resumed": resumed[0], "pdo_resumed_values": vals,
    "frames": len(frames), "duration": round(frames[-1]["t"], 2),
    "gaps_before": before[:3], "gaps_after": after[:3],
}
out.write_text("// Written by collect.py from runs/. Do not edit by hand.\nwindow.DATA = " + json.dumps(DATA) + ";\n")
print(out, f"{len(frames)} frames, {len(sdo)} SDO, hb gaps {before[:2]} -> {after[:2]} ms, resumed PDO {vals}")
