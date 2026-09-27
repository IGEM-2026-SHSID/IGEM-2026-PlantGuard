"""ESP32-CAM entry point: capture JPEG and delegate decoding to a PC."""
import gc
import time
import machine
import network
import camera

import config
from jpeg_transport import send_jpeg
from reporting import make_report
from scheduler import choose_trigger, debounce_accept, ticks_due
from wifi_manager import WifiManager

DEVICE_ID = "plantguard-cam-01"
WIFI_SSID = "PlantGuard"
WIFI_PASSWORD = "plantguard"
PC_HOST = "192.168.4.2"  # Replace with the PC address shown by ipconfig.
PC_PORT = 8765
CAPTURE_INTERVAL_MS = 300000
TRIGGER_PIN = 13
TRIGGER_DEBOUNCE_MS = 250

_gpio_pending = False
_gpio_edge_ms = 0


def _log(event, detail=""):
    if config.DEBUG_LOG:
        print("[CAM][%d] %s%s" % (
            time.ticks_ms(), event, (": " + str(detail)) if detail else ""))


def _trigger_irq(pin):
    global _gpio_pending, _gpio_edge_ms
    _gpio_edge_ms = time.ticks_ms()
    _gpio_pending = True


def main():
    global _gpio_pending
    _log("boot", "starting PlantGuard ESP-CAM")
    camera.init(0, format=camera.JPEG)
    _log("camera_ready")
    wlan = network.WLAN(network.STA_IF)
    wifi = WifiManager(wlan, WIFI_SSID, None, time.ticks_ms,
                       time.ticks_diff, time.sleep_ms, 15000, 5000)
    connected = wifi.connect(force=True)
    _log("wifi_initial", "connected" if connected else "unavailable")
    pin = machine.Pin(TRIGGER_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)
    pin.irq(trigger=machine.Pin.IRQ_RISING, handler=_trigger_irq)
    _log("gpio_trigger_ready", "gpio=%d debounce_ms=%d" % (
        TRIGGER_PIN, TRIGGER_DEBOUNCE_MS))
    sequence, last_gpio = 0, None
    next_capture = time.ticks_add(time.ticks_ms(), CAPTURE_INTERVAL_MS)
    try:
        while True:
            now, gpio = time.ticks_ms(), _gpio_pending
            edge = _gpio_edge_ms
            if gpio:
                _gpio_pending = False
                gpio = debounce_accept(edge, last_gpio, TRIGGER_DEBOUNCE_MS,
                                       time.ticks_diff)
                if gpio:
                    last_gpio = edge
                    _log("gpio_trigger_accepted")
                else:
                    _log("gpio_trigger_debounced")
            trigger = choose_trigger(gpio, ticks_due(now, next_capture,
                                                      time.ticks_diff))
            if trigger is None:
                wifi.connect()
                time.sleep_ms(20)
                continue
            next_capture = time.ticks_add(now, CAPTURE_INTERVAL_MS)
            sequence += 1
            _log("capture_start", "sequence=%d trigger=%s" % (sequence, trigger))
            image = None
            try:
                started = time.ticks_ms()
                image = camera.capture()
                if not image:
                    raise RuntimeError("camera.capture returned no JPEG data")
                report = make_report(DEVICE_ID, sequence, started, trigger,
                    timing_ms={"capture": time.ticks_diff(time.ticks_ms(), started)})
                _log("capture_done", "bytes=%d elapsed_ms=%d" % (
                    len(image), report["timing_ms"]["capture"]))
                if not wifi.connect():
                    _log("upload_skipped", "Wi-Fi unavailable")
                    raise OSError("Wi-Fi unavailable")
                upload_started = time.ticks_ms()
                _log("upload_start", "host=%s:%d" % (PC_HOST, PC_PORT))
                send_jpeg(PC_HOST, PC_PORT, image, report)
                _log("upload_ok", "elapsed_ms=%d" % time.ticks_diff(
                    time.ticks_ms(), upload_started))
                print("[CAM] frame %d acknowledged (%d bytes)" %
                      (sequence, len(image)))
            except Exception as exc:
                _log("frame_failed", "sequence=%d error=%s" % (sequence, exc))
                print("[CAM] frame %d failed: %s" % (sequence, exc))
            image = None
            gc.collect()
    finally:
        pin.irq(handler=None)
        _log("gpio_released")
        camera.deinit()
        _log("camera_released")


if __name__ == "__main__":
    main()
