"""MAX17205 2-cell fuel gauge, one per battery pack (I2C1 = pack 1, I2C2 = pack 2). The part answers on two
7-bit addresses: 0x36 for registers 0x000-0x0FF and 0x0B for 0x100-0x1FF (the firmware sends an 8-bit register
number; the address picks the page). Registers are 16-bit little-endian and keep what the firmware writes, which
is how its read-back of the non-volatile settings comes out CORRECT. Defaults give a healthy pack at rest:
cells at `cell_mv` (VCell/AvgVCell/AvgCell1 LSB 78.125 uV, Batt LSB 1.25 mV), Temp1/Temp2/IntTemp in the
0.1 C-from-0 K form the firmware converts, discharge `current_ma` through the 10 mohm sense resistor
(LSB 1.5625 uV), and a 2600 mAh pack at 98 %. config: {"cell_mv", "temp_c", "current_ma"}."""


class Slave:
    def __init__(self, ctx):
        self.ctx = ctx
        c = ctx.config
        cell, temp, cur = int(c.get("cell_mv", 3700)), int(c.get("temp_c", 24)), int(c.get("current_ma", -150))
        raw_cell = cell * 64 // 5
        raw_temp = (temp + 273) * 10
        raw_cur = (cur * 100000 // 15625) & 0xFFFF
        self.regs = {
            0x009: raw_cell, 0x019: raw_cell, 0x0D4: raw_cell, 0x0DA: 2 * cell * 100 // 125,
            0x01B: (cell // 20) << 8 | (cell // 20) - 1,
            0x00A: raw_cur, 0x00B: raw_cur, 0x01C: 0x0000,
            0x134: raw_temp, 0x135: raw_temp, 0x137: raw_temp, 0x138: raw_temp, 0x139: raw_temp, 0x13B: raw_temp,
            0x01A: (temp + 1) << 8 | temp,
            0x035: 0x1450, 0x01F: 0x1400, 0x00F: 0x1400, 0x005: 0x1400,
            0x006: 98 * 256, 0x007: 0, 0x017: 12 * 16,
        }
        self.high = False
        self.reg = 0

    def on_address(self, addr, is_read):
        self.high = addr == 0x0B
        return True

    def on_write(self, data):
        if not data:
            return 0
        self.reg = data[0]
        if len(data) >= 3:
            self.regs[self.reg | (0x100 if self.high else 0)] = data[1] | (data[2] << 8)
        return len(data)

    def on_read(self, count):
        out, r = b"", self.reg | (0x100 if self.high else 0)
        while len(out) < count:
            v = self.regs.get(r, 0)
            out += bytes([v & 0xFF, v >> 8])
            r += 1
        return out[:count]

    def on_finish(self):
        pass
