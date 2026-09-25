import config
from compat import ticks_ms, ticks_diff, sleep_ms
from history import RingHistory
from sensors import SensorSampler
from app import Application
from http_server import HTTPServer

def _log(event, detail=""):
    if config.DEBUG_LOG:
        print("[C3][%d] %s%s" % (
            ticks_ms(), event, (": " + str(detail)) if detail else ""))

def init_hardware():
    import machine, dht, network
    from tsl2591 import TSL2591
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=config.AP_SSID, password=config.AP_PASSWORD)
    _log("wifi_ap_active", config.AP_SSID)
    try:
        ap.ifconfig((config.AP_ADDRESS, "255.255.255.0", config.AP_ADDRESS, config.AP_ADDRESS))
        _log("wifi_ap_address", config.AP_ADDRESS)
    except Exception as exc:
        _log("wifi_ap_address_failed", exc)
    i2c = machine.I2C(config.I2C_ID, sda=machine.Pin(config.TSL2591_SDA_PIN), scl=machine.Pin(config.TSL2591_SCL_PIN), freq=config.I2C_FREQUENCY_HZ)
    light = None
    try:
        light = TSL2591(i2c, config.TSL2591_ADDRESS, config.TSL2591_INTEGRATION_MS, config.TSL2591_GAIN)
        _log("tsl2591_ready", "address=0x%02x" % config.TSL2591_ADDRESS)
    except Exception as exc:
        _log("tsl2591_init_failed", exc)
    dht_sensor = dht.DHT11(machine.Pin(config.DHT11_PIN, machine.Pin.IN, machine.Pin.PULL_UP))
    _log("dht11_ready", "gpio=%d" % config.DHT11_PIN)
    return SensorSampler(dht_sensor, light)

def run():
    _log("boot", "starting PlantGuard C3")
    sensor_history = RingHistory(config.HISTORY_CAPACITY)
    camera_history = RingHistory(config.HISTORY_CAPACITY)
    sampler = init_hardware()
    app = Application(sensor_history, camera_history)
    server = HTTPServer(app)
    _log("http_ready", "%s:%d" % (config.HTTP_HOST, config.HTTP_PORT))
    last_sample = ticks_ms() - config.SAMPLE_INTERVAL_MS
    try:
        while True:
            now = ticks_ms()
            if ticks_diff(now, last_sample) >= config.SAMPLE_INTERVAL_MS:
                try:
                    record = sampler.sample()
                    sensor_history.append(record)
                    _log("sample", "dht=%s tsl2591=%s temp=%s humidity=%s lux=%s" % (
                        record["dht_status"], record["tsl2591_status"],
                        record["temperature_c"], record["air_humidity_pct"],
                        record["lux"]))
                    if record["errors"]:
                        _log("sample_warnings", record["errors"])
                except Exception as exc:
                    _log("sample_failed", exc)
                last_sample = now
            try:
                server.poll()
            except Exception as exc:
                _log("http_poll_failed", exc)
                sleep_ms(50)
    except KeyboardInterrupt:
        _log("stopped", "keyboard interrupt")
    finally:
        try:
            server.sock.close()
        except Exception as exc:
            _log("http_close_failed", exc)
        _log("http_closed")

if __name__ == "__main__":
    run()
