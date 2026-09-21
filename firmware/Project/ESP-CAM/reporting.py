"""Pure helpers for stable camera report construction."""


def error_info(stage, exc):
    if exc is None:
        return None
    return {
        "stage": stage,
        "type": exc.__class__.__name__,
        "message": str(exc),
    }


def make_report(device_id, sequence, capture_uptime_ms, trigger,
                width=0, height=0, decoded_pixels=0, selected_pixels=0,
                blue_value=None, analysis_status="not_run", error=None,
                timing_ms=None, memory_bytes=None):
    return {
        "device_id": device_id,
        "sequence": sequence,
        "capture_uptime_ms": capture_uptime_ms,
        "trigger": trigger,
        "width": width,
        "height": height,
        "decoded_pixels": decoded_pixels,
        "selected_pixels": selected_pixels,
        "blue_value": blue_value,
        "analysis_status": analysis_status,
        "error": error,
        "timing_ms": timing_ms or {},
        "memory_bytes": memory_bytes or {},
    }

