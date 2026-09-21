import config
from compat import ticks_ms, ticks_diff, sleep_ms
from history import RingHistory
from sensors import SensorSampler
from app import Application
from http_server import HTTPServer

def init_hardware():
    import machine, dht, network
    from tsl2591 import TSL2591
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=config.AP_SSID, password=config.AP_PASSWORD)
    try:
        ap.ifconfig((config.AP_ADDRESS, "255.255.255.0", config.AP_ADDRESS, config.AP_ADDRESS))
    except Exception:
        pass
    i2c = machine.I2C(config.I2C_ID, sda=machine.Pin(config.TSL2591_SDA_PIN), scl=machine.Pin(config.TSL2591_SCL_PIN), freq=config.I2C_FREQUENCY_HZ)
    light = None
    try:
        light = TSL2591(i2c, config.TSL2591_ADDRESS, config.TSL2591_INTEGRATION_MS, config.TSL2591_GAIN)
    except Exception:
        pass
    dht_sensor = dht.DHT11(machine.Pin(config.DHT11_PIN, machine.Pin.IN, machine.Pin.PULL_UP))
    return SensorSampler(dht_sensor, light)

def run():
    sensor_history = RingHistory(config.HISTORY_CAPACITY)
    camera_history = RingHistory(config.HISTORY_CAPACITY)
    sampler = init_hardware()
    app = Application(sensor_history, camera_history)
    server = HTTPServer(app)
    last_sample = ticks_ms() - config.SAMPLE_INTERVAL_MS
    while True:
        now = ticks_ms()
        if ticks_diff(now, last_sample) >= config.SAMPLE_INTERVAL_MS:
            try:
                sensor_history.append(sampler.sample())
            except Exception:
                pass
            last_sample = now
        try:
            server.poll()
        except Exception:
            sleep_ms(50)

if __name__ == "__main__":
    run()

