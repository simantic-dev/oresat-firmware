"""INA226 power monitor at 0x40 on the solar card's I2C2: the panel string as seen through the 0.1 ohm shunt.
Registers are 16-bit big-endian (datasheet 7.1). Bus voltage 4.80 V (LSB 1.25 mV), current 150 mA (the firmware
programs CAL for 20 uA/bit). Writing CONFIG with RST (bit 15) resets and the bit self-clears; CVRF (MASK/ENABLE
bit 3) reads 1 as a conversion is always already done."""

VBUS_MV, I_MA, LSB_UA = 4800, 150, 20


class Slave:
    def __init__(self, ctx):
        self.ctx = ctx
        self.reg = 0
        self.cfg = 0x4127
        self.cal = 0
        self.mask = 0x0008
        self.writes = 0

    def on_address(self, addr, is_read):
        return True

    def on_write(self, data):
        if not data:
            return 0
        self.reg = data[0]
        if len(data) >= 3:
            val = (data[1] << 8) | data[2]
            if self.reg == 0:
                self.cfg = 0x4127 if val & 0x8000 else val
            elif self.reg == 5:
                self.cal = val
                self.ctx.info("INA226 CAL=%d" % val)
            self.writes += 1
        return len(data)

    def value(self):
        r = self.reg
        if r == 0:
            return self.cfg
        if r == 2:
            return VBUS_MV * 1000 // 1250
        if r == 4:
            return I_MA * 1000 // LSB_UA
        if r == 5:
            return self.cal
        if r == 6:
            return self.mask
        if r == 0xFE:
            return 0x5449
        if r == 0xFF:
            return 0x2260
        return 0

    def on_read(self, count):
        v = self.value()
        return bytes([v >> 8, v & 0xFF])[:count].ljust(count, b"\0")

    def on_finish(self):
        pass
