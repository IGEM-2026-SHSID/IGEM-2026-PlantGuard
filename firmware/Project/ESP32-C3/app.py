from compat import json, json_dumps, ticks_ms, ticks_diff
from calculation import calculate
from dashboard import DASHBOARD_HTML

CAMERA_FIELDS = ("device_id", "sequence", "capture_uptime_ms", "trigger", "width",
                 "height", "decoded_pixels", "selected_pixels", "blue_value", "error")

def validate_camera_reading(data):
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    missing = [x for x in CAMERA_FIELDS if x not in data]
    if missing:
        raise ValueError("missing fields: " + ",".join(missing))
    if not isinstance(data["device_id"], str) or not data["device_id"]:
        raise ValueError("device_id must be a non-empty string")
    for key in ("sequence", "capture_uptime_ms", "width", "height", "decoded_pixels", "selected_pixels"):
        if isinstance(data[key], bool) or not isinstance(data[key], int) or data[key] < 0:
            raise ValueError(key + " must be a non-negative integer")
    if data["trigger"] not in ("timer", "gpio"):
        raise ValueError("trigger must be timer or gpio")
    if data["blue_value"] is not None and (isinstance(data["blue_value"], bool) or not isinstance(data["blue_value"], (int, float))):
        raise ValueError("blue_value must be numeric or null")
    if data["error"] is not None and not isinstance(data["error"], str):
        raise ValueError("error must be string or null")
    return dict(data)

class Application:
    def __init__(self, sensor_history, camera_history, clock=ticks_ms):
        self.sensors = sensor_history
        self.cameras = camera_history
        self.clock = clock

    def state(self):
        sensor = self.sensors.latest()
        camera = self.cameras.latest()
        age = None if sensor is None else max(0, ticks_diff(self.clock(), sensor["uptime_ms"]))
        return {"sensor": sensor, "camera": camera,
                "calculation": calculate(sensor, self.cameras.to_list()),
                "sensor_age_ms": age}

    def route(self, method, path, body=b""):
        if path == "/":
            if method != "GET": return self._error(405, "method_not_allowed")
            return 200, "text/html; charset=utf-8", DASHBOARD_HTML.encode()
        known = ("/api/v1/state", "/api/v1/history/sensors", "/api/v1/history/camera", "/api/v1/camera/readings")
        if path not in known:
            return self._error(404, "not_found")
        if path == "/api/v1/camera/readings":
            if method != "POST": return self._error(405, "method_not_allowed")
            try:
                data = json.loads(body.decode("utf-8"))
                item = validate_camera_reading(data)
                item["received_uptime_ms"] = self.clock()
                self.cameras.append(item)
                return self._json(201, item)
            except (ValueError, TypeError, UnicodeError) as exc:
                return self._error(400, "invalid_request", str(exc))
        if method != "GET": return self._error(405, "method_not_allowed")
        if path == "/api/v1/state": return self._json(200, self.state())
        if path == "/api/v1/history/sensors": return self._json(200, self.sensors.to_list())
        return self._json(200, self.cameras.to_list())

    def _json(self, status, value):
        return status, "application/json", json_dumps(value).encode()

    def _error(self, status, code, detail=None):
        value = {"error": code}
        if detail: value["detail"] = detail
        return self._json(status, value)

