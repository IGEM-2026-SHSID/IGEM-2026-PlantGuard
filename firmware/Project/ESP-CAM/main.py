"""PlantGuard ESP32-CAM MicroPython entry point."""

import gc
import time
import machine
import network
import camera
import urequests

import config
from camera_pipeline import run_capture
from http_client import upload_report
from JPEGdecoder import jpeg
from scheduler import choose_trigger, debounce_accept, ticks_due
from wifi_manager import WifiManager


_gpio_pending = False
_gpio_edge_ms = 0

def _log(event, detail=""):
    if config.DEBUG_LOG:
        print("[CAM][%d] %s%s" % (
            time.ticks_ms(), event, (": " + str(detail)) if detail else ""))


def _trigger_irq(pin):
    # ISR intentionally performs no allocation, capture, decode, or networking.
    global _gpio_pending, _gpio_edge_ms
    _gpio_edge_ms = time.ticks_ms()
    _gpio_pending = True


def _camera_init():
    kwargs = {"format": camera.JPEG, "fb_location": camera.PSRAM}
    frame = getattr(camera, config.FRAME_SIZE, None)
    if frame is not None:
        kwargs["framesize"] = frame
    # Firmware ports differ on whether quality is accepted; preserve baseline
    # init compatibility and retry without optional tuning.
    kwargs["quality"] = config.CAMERA_JPEG_QUALITY
    try:
        camera.init(0, **kwargs)
        _log("camera_ready", kwargs)
    except TypeError:
        _log("camera_quality_unsupported", "retrying without quality")
        kwargs.pop("quality", None)
        camera.init(0, **kwargs)
        _log("camera_ready", kwargs)


def main():
    global _gpio_pending
    _log("boot", "starting PlantGuard ESP-CAM")
    _camera_init()
    wlan = network.WLAN(network.STA_IF)
    wifi = WifiManager(wlan, config.WIFI_SSID, config.WIFI_PASSWORD,
                       time.ticks_ms, time.ticks_diff, time.sleep_ms,
                       config.WIFI_CONNECT_TIMEOUT_MS,
                       config.WIFI_RETRY_INTERVAL_MS)
    connected = wifi.connect(force=True)
    _log("wifi_initial", "connected" if connected else "unavailable")

    trigger_pin = machine.Pin(config.TRIGGER_PIN, machine.Pin.IN, machine.Pin.PULL_DOWN)
    trigger_pin.irq(trigger=machine.Pin.IRQ_RISING, handler=_trigger_irq)
    _log("gpio_trigger_ready", "gpio=%d debounce_ms=%d" % (
        config.TRIGGER_PIN, config.TRIGGER_DEBOUNCE_MS))

    sequence = 0
    last_gpio_ms = None
    next_capture = time.ticks_add(time.ticks_ms(), config.CAPTURE_INTERVAL_MS)
    try:
        while True:
            now = time.ticks_ms()
            gpio = _gpio_pending
            edge_ms = _gpio_edge_ms
            if gpio:
                _gpio_pending = False
                gpio = debounce_accept(edge_ms, last_gpio_ms,
                                       config.TRIGGER_DEBOUNCE_MS, time.ticks_diff)
                if gpio:
                    last_gpio_ms = edge_ms
                    _log("gpio_trigger_accepted")
                else:
                    _log("gpio_trigger_debounced")
            due = ticks_due(now, next_capture, time.ticks_diff)
            trigger = choose_trigger(gpio, due)
            if trigger is None:
                wifi.connect()
                time.sleep_ms(config.LOOP_SLEEP_MS)
                continue

            # Any capture services a simultaneous timer event.
            next_capture = time.ticks_add(now, config.CAPTURE_INTERVAL_MS)
            sequence += 1
            _log("capture_start", "sequence=%d trigger=%s" % (sequence, trigger))
            report = run_capture(camera, jpeg, time.ticks_ms, config.DEVICE_ID,
                                 sequence, trigger, config.JPEG_QUALITY)
            _log("capture_done", "size=%sx%s pixels=%s status=%s" % (
                report["width"], report["height"], report["decoded_pixels"],
                report["analysis_status"]))
            if report["error"] is not None:
                _log("capture_error", report["error"])
            if wifi.connect():
                upload = upload_report(urequests, config.UPLOAD_URL, report,
                                       config.HTTP_TIMEOUT_SECONDS, time.ticks_ms)
                report["timing_ms"]["upload"] = upload["elapsed_ms"]
                if not upload["ok"]:
                    report["error"] = upload["error"]
                    _log("upload_failed", upload["error"])
                else:
                    _log("upload_ok", "elapsed_ms=%s" % upload["elapsed_ms"])
            elif report["error"] is None:
                report["error"] = {"stage": "wifi", "type": "ConnectionError",
                                   "message": "Wi-Fi unavailable; report not uploaded"}
                _log("upload_skipped", report["error"])
            gc.collect()
    except KeyboardInterrupt:
        _log("stopped", "keyboard interrupt")
    finally:
        try:
            trigger_pin.irq(handler=None)
        except Exception as exc:
            _log("gpio_release_failed", exc)
        try:
            deinit = getattr(camera, "deinit", None)
            if deinit is not None:
                deinit()
        except Exception as exc:
            _log("camera_release_failed", exc)
        _log("camera_released")


if __name__ == "__main__":
    main()
