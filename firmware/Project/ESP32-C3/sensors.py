from compat import ticks_ms

class SensorSampler:
    def __init__(self, dht_sensor=None, light_sensor=None, clock=ticks_ms):
        self.dht = dht_sensor
        self.light = light_sensor
        self.clock = clock

    def sample(self):
        record = {"uptime_ms": self.clock(), "temperature_c": None,
                  "air_humidity_pct": None, "lux": None,
                  "full_spectrum": None, "infrared": None, "visible": None,
                  "dht_status": "unavailable", "tsl2591_status": "unavailable",
                  "errors": {}}
        if self.dht is not None:
            try:
                self.dht.measure()
                record["temperature_c"] = self.dht.temperature()
                record["air_humidity_pct"] = self.dht.humidity()
                record["dht_status"] = "ok"
            except Exception as exc:
                record["dht_status"] = "error"
                record["errors"]["dht11"] = str(exc)
        if self.light is not None:
            try:
                values = self.light.read()
                for key in ("lux", "full_spectrum", "infrared", "visible"):
                    record[key] = values.get(key)
                record["tsl2591_status"] = "ok" if record["lux"] is not None else "invalid"
            except Exception as exc:
                record["tsl2591_status"] = "error"
                record["errors"]["tsl2591"] = str(exc)
        return record

