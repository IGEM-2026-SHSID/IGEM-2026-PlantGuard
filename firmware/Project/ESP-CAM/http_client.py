"""JSON upload adapter with explicit cleanup and timing metadata."""

try:
    import ujson as json
except ImportError:
    import json


def upload_report(requests, url, report, timeout_seconds, ticks_ms):
    started = ticks_ms()
    response = None
    try:
        response = requests.post(
            url,
            data=json.dumps(report),
            headers={"Content-Type": "application/json"},
            timeout=timeout_seconds,
        )
        status = getattr(response, "status_code", None)
        if status not in (200, 201):
            raise OSError("HTTP upload failed with status {}".format(status))
        return {"ok": True, "status_code": status,
                "elapsed_ms": ticks_ms() - started, "error": None}
    except Exception as exc:
        return {"ok": False, "status_code": None,
                "elapsed_ms": ticks_ms() - started,
                "error": {"stage": "upload", "type": exc.__class__.__name__,
                          "message": str(exc)}}
    finally:
        if response is not None:
            response.close()

