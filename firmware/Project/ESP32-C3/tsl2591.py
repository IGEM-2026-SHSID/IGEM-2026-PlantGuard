"""Small TSL2591 driver with explicit raw-channel and overflow handling."""
from compat import sleep_ms

ADDRESS = 0x29
COMMAND = 0xA0
ENABLE = 0x00
CONTROL = 0x01
CH0_LOW = 0x14
CH1_LOW = 0x16

INTEGRATION_CODES = {100: 0, 200: 1, 300: 2, 400: 3, 500: 4, 600: 5}
GAIN_CODES = {1: 0x00, 25: 0x10, 428: 0x20, 9876: 0x30}

class TSL2591:
    def __init__(self, i2c, address=ADDRESS, integration_ms=100, gain=1):
        if integration_ms not in INTEGRATION_CODES:
            raise ValueError("integration_ms must be 100..600 in 100 ms steps")
        if gain not in GAIN_CODES:
            raise ValueError("unsupported gain")
        self.i2c = i2c
        self.address = address
        self.integration_ms = integration_ms
        self.gain = gain
        self._write(ENABLE, 0x03)
        self._write(CONTROL, INTEGRATION_CODES[integration_ms] | GAIN_CODES[gain])

    def _write(self, register, value):
        self.i2c.writeto_mem(self.address, COMMAND | register, bytes((value,)))

    def _read_u16(self, register):
        data = self.i2c.readfrom_mem(self.address, COMMAND | register, 2)
        if len(data) != 2:
            raise OSError("short TSL2591 register read")
        return data[0] | (data[1] << 8)

    def read(self):
        sleep_ms(self.integration_ms + 20)
        full = self._read_u16(CH0_LOW)
        infrared = self._read_u16(CH1_LOW)
        visible = max(0, full - infrared)
        if full >= 0xFFFF or infrared >= 0xFFFF:
            raise OverflowError("TSL2591 saturated")
        lux = self._lux(full, infrared)
        return {"full_spectrum": full, "infrared": infrared,
                "visible": visible, "lux": lux}

    def _lux(self, full, infrared):
        if full <= 0 or infrared < 0 or infrared > full:
            return None
        atime_ms = float(self.integration_ms)
        again = float(self.gain)
        cpl = (atime_ms * again) / 408.0
        if cpl <= 0 or infrared > full:
            return None
        lux1 = (full - 1.64 * infrared) / cpl
        lux2 = (0.59 * full - 0.86 * infrared) / cpl
        lux = max(lux1, lux2)
        if lux < 0 or lux != lux or lux == float("inf"):
            return None
        return round(lux, 3)
