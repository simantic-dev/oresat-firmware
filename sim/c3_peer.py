"""OreSat C3 stand-in: the CANopen master of the card bus, as a scripted CAN node (node id 0x01).

OreSat's C3 is a Linux card (oresat-c3-software, not firmware), so it is played here. It watches the NMT
boot-up and heartbeat of each card, then runs SCRIPT at its virtual times: SDO expedited reads and writes
(CiA 301 7.2.4) and NMT commands (7.2.8). Every step and every answer is logged as `[c3] ...`."""

SOLAR, BATT = 0x0C, 0x04
NAMES = {SOLAR: "solar_1", BATT: "battery_1"}
NMT_STATE = {0x00: "boot-up", 0x04: "stopped", 0x05: "operational", 0x7F: "pre-operational"}

# (time s, op, node, args). sdo_read: index, subindex, label, signed, unit.
SCRIPT = [
    (1.5, "sdo_read", SOLAR, (0x1000, 0, "device_type", False, "")),
    (1.6, "sdo_read", SOLAR, (0x4000, 1, "output.voltage", False, "mV")),
    (1.7, "sdo_read", SOLAR, (0x4000, 2, "output.current", True, "mA")),
    (1.8, "sdo_read", SOLAR, (0x4000, 3, "output.power", False, "mW")),
    (1.9, "sdo_read", SOLAR, (0x4001, 1, "cell_1.temperature", True, "C")),
    (2.0, "sdo_read", SOLAR, (0x4002, 1, "cell_2.temperature", True, "C")),
    (4.0, "sdo_read", BATT, (0x4000, 0x01, "pack_1.vbatt", False, "mV")),
    (4.1, "sdo_read", BATT, (0x4000, 0x04, "pack_1.vcell", False, "mV")),
    (4.2, "sdo_read", BATT, (0x4000, 0x08, "pack_1.current", True, "mA")),
    (4.3, "sdo_read", BATT, (0x4000, 0x12, "pack_1.temperature", True, "C")),
    (4.4, "sdo_read", BATT, (0x4000, 0x11, "pack_1.reported_state_of_charge", False, "%")),
    (4.5, "sdo_read", BATT, (0x4001, 0x04, "pack_2.vcell", False, "mV")),
    (4.6, "sdo_read", BATT, (0x4001, 0x12, "pack_2.temperature", True, "C")),
    (5.0, "sdo_read", SOLAR, (0x1017, 0, "producer_heartbeat_time", False, "ms")),
    (5.1, "sdo_write", SOLAR, (0x1017, 0, 250, 2, "producer_heartbeat_time")),
    (5.2, "sdo_read", SOLAR, (0x1017, 0, "producer_heartbeat_time", False, "ms")),
    (8.0, "nmt", SOLAR, (0x02, "stop")),
    (9.0, "nmt", SOLAR, (0x01, "start")),
    (10.2, "sdo_read", SOLAR, (0x4000, 1, "output.voltage", False, "mV")),
]


class Node:
    def __init__(self, ctx):
        self.ctx = ctx
        self.todo = list(SCRIPT)
        self.pending = {}
        self.state = {}
        self.tpdos = {}
        self.last_hb, self.period = {}, {}
        self._arm()

    def _arm(self):
        if self.todo:
            self.ctx.schedule_oneshot(max(1, int(self.todo[0][0] * 1e6) - self.ctx.now_us))

    def on_timer(self):
        while self.todo and int(self.todo[0][0] * 1e6) <= self.ctx.now_us:
            _, op, node, args = self.todo.pop(0)
            getattr(self, op)(node, *args)
        self._arm()

    def _name(self, node):
        return "%s(0x%02X)" % (NAMES.get(node, "node"), node)

    def sdo_read(self, node, idx, sub, label, signed, unit):
        self.pending[node] = ("r", idx, sub, label, signed, unit)
        self.ctx.info("SDO upload %s %04X:%02X %s" % (self._name(node), idx, sub, label))
        self.ctx.send(0x600 + node, bytes([0x40, idx & 0xFF, idx >> 8, sub, 0, 0, 0, 0]))

    def sdo_write(self, node, idx, sub, val, size, label):
        self.pending[node] = ("w", idx, sub, label, False, "")
        self.ctx.info("SDO download %s %04X:%02X %s = %d" % (self._name(node), idx, sub, label, val))
        cmd = 0x23 | ((4 - size) << 2)
        self.ctx.send(0x600 + node, bytes([cmd, idx & 0xFF, idx >> 8, sub]) + val.to_bytes(4, "little"))

    def nmt(self, node, cmd, label):
        self.ctx.info("NMT %s %s" % (label, self._name(node)))
        self.ctx.send(0x000, bytes([cmd, node]))

    def on_frame(self, f):
        cid, d = f["id"], bytes(f["data"])
        if f["extended"] or f["remote"]:
            return
        fn, node = cid & 0x780, cid & 0x7F
        if fn == 0x700 and d:
            st = d[0] & 0x7F
            if self.state.get(node) != st:
                self.state[node] = st
                self.ctx.info("NMT %s %s" % (self._name(node), NMT_STATE.get(st, hex(st))))
            if st == 5:
                last = self.last_hb.get(node)
                if last is not None:
                    period = round((self.ctx.now_us - last) / 10000) * 10
                    if self.period.get(node) != period:
                        self.period[node] = period
                        self.ctx.info("heartbeat %s every %d ms" % (self._name(node), period))
                self.last_hb[node] = self.ctx.now_us
        elif fn == 0x580 and node in self.pending and len(d) == 8:
            kind, idx, sub, label, signed, unit = self.pending.pop(node)
            if d[0] == 0x80:
                self.ctx.info("SDO abort %s %04X:%02X code=0x%08X" % (self._name(node), idx, sub, int.from_bytes(d[4:], "little")))
            elif kind == "w" and d[0] == 0x60:
                self.ctx.info("SDO download ok %s %04X:%02X" % (self._name(node), idx, sub))
            elif kind == "r":
                size = 4 - ((d[0] >> 2) & 3) if d[0] & 1 else 4
                v = int.from_bytes(d[4:4 + size], "little", signed=signed)
                self.ctx.info("SDO upload ok %s %04X:%02X %s = %d %s" % (self._name(node), idx, sub, label, v, unit))
        elif fn in (0x180, 0x280, 0x380, 0x480) and node in NAMES:
            key = (cid, d)
            self.ctx.info("TPDO%d %s data=%s" % ((fn >> 8) & 7, self._name(node), d.hex())) if key not in self.tpdos else None
            self.tpdos[key] = 1
