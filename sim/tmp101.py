"""TMP101 temperature sensor (cell 1 at 0x48, cell 2 at 0x4A on the solar card's I2C2). Register 0 is the
temperature, 12 bit left aligned in a big-endian 16-bit word: the high byte is whole degrees C, which is
all the firmware keeps. config: {"celsius": N}."""


class Slave:
    def __init__(self, ctx):
        self.ctx = ctx
        self.c = int(ctx.config.get("celsius", 20))
        self.reg = 0

    def on_address(self, addr, is_read):
        return True

    def on_write(self, data):
        if data:
            self.reg = data[0]
        return len(data)

    def on_read(self, count):
        word = [self.c & 0xFF, 0x00] if self.reg == 0 else [0x00, 0x00]
        return bytes(word)[:count].ljust(count, b"\0")

    def on_finish(self):
        pass
