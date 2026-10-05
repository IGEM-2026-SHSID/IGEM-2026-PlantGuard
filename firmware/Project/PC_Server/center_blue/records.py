"""Read the latest C3 sensor snapshot and append one local photo record."""
from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.parse
import urllib.request


DEFAULT_RECORDS_FILE = Path(__file__).resolve().parent / "measurements.jsonl"


def state_url(camera_url):
    parts = urllib.parse.urlsplit(camera_url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("C3 URL must be an HTTP(S) URL")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/api/v1/state", "", ""))


def fetch_sensor(camera_url):
    request = urllib.request.Request(state_url(camera_url), headers={"Accept": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=5) as response:
        state = json.load(response)
    if not isinstance(state, dict):
        raise ValueError("C3 state must be a JSON object")
    sensor = state.get("sensor")
    age = state.get("sensor_age_ms")
    if sensor is not None and not isinstance(sensor, dict):
        raise ValueError("C3 sensor must be a JSON object or null")
    if age is not None and (isinstance(age, bool) or not isinstance(age, int) or age < 0):
        raise ValueError("C3 sensor_age_ms must be a non-negative integer or null")
    return sensor, age


def save_record(path, report, sensor, sensor_age_ms, sensor_error=None):
    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "camera": report,
        "sensor": sensor,
        "sensor_age_ms": sensor_age_ms,
        "sensor_error": sensor_error,
    }
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    with Path(path).open("a", encoding="utf-8", newline="\n") as output:
        output.write(line)
    return record
