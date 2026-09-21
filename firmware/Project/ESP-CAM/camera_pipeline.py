"""Capture, streaming JPEG decode, analysis, and metadata construction."""

import gc

from blue_analyzer import BlueAnalyzer
from reporting import error_info, make_report


def _mem_free():
    fn = getattr(gc, "mem_free", None)
    return fn() if fn else None


def run_capture(camera, jpeg_factory, ticks_ms, device_id, sequence, trigger,
                decoder_quality=8):
    capture_uptime = ticks_ms()
    timing = {}
    memory = {"before_capture": _mem_free()}
    report = make_report(device_id, sequence, capture_uptime, trigger,
                         timing_ms=timing, memory_bytes=memory)
    image = None
    analyzer = BlueAnalyzer()
    try:
        started = ticks_ms()
        image = camera.capture()
        timing["capture"] = ticks_ms() - started
        memory["after_capture"] = _mem_free()
        if not image:
            raise RuntimeError("camera.capture returned no JPEG data")

        started = ticks_ms()
        renderer = jpeg_factory(image, quality=decoder_quality,
                                callback=analyzer.consume, cache=False)
        width, height, _depth = renderer.getMeta()
        # getMeta() parses a fresh BytesIO; render() remains valid afterwards.
        renderer.render()
        timing["decode"] = ticks_ms() - started
        memory["after_decode"] = _mem_free()

        result = analyzer.result()
        report.update({
            "width": width,
            "height": height,
            "decoded_pixels": result["decoded_pixels"],
            "selected_pixels": result["selected_pixels"],
            "blue_value": result["blue_value"],
            "analysis_status": result["status"],
        })
    except Exception as exc:
        stage = "capture" if image is None else "decode"
        report["error"] = error_info(stage, exc)
        report["analysis_status"] = "failed"
    finally:
        image = None
        gc.collect()
        memory["after_gc"] = _mem_free()
    return report

