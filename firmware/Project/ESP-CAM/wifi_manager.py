"""Small reconnecting station wrapper for MicroPython network.WLAN."""


class WifiManager:
    def __init__(self, wlan, ssid, password, ticks_ms, ticks_diff, sleep_ms,
                 connect_timeout_ms, retry_interval_ms):
        self.wlan = wlan
        self.ssid = ssid
        self.password = password
        self.ticks_ms = ticks_ms
        self.ticks_diff = ticks_diff
        self.sleep_ms = sleep_ms
        self.connect_timeout_ms = connect_timeout_ms
        self.retry_interval_ms = retry_interval_ms
        self._last_attempt_ms = None

    def connected(self):
        return bool(self.wlan.isconnected())

    def connect(self, force=False):
        if self.connected():
            return True
        now = self.ticks_ms()
        if (not force and self._last_attempt_ms is not None and
                self.ticks_diff(now, self._last_attempt_ms) < self.retry_interval_ms):
            return False
        self._last_attempt_ms = now
        self.wlan.active(True)
        try:
            self.wlan.disconnect()
        except Exception:
            pass
        self.wlan.connect(self.ssid, self.password)
        started = self.ticks_ms()
        while not self.connected():
            if self.ticks_diff(self.ticks_ms(), started) >= self.connect_timeout_ms:
                return False
            self.sleep_ms(100)
        return True

