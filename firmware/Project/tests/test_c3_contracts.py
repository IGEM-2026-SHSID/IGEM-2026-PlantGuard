import json

import config
from app import Application, validate_camera_reading
from calculation import calculate
from history import RingHistory
from sensors import SensorSampler


def camera_reading(**overrides):
    value = {
        "device_id": "cam-1",
        "sequence": 7,
        "capture_uptime_ms": 1234,
        "trigger": "timer",
        "width": 160,
        "height": 120,
        "decoded_pixels": 19200,
        "selected_pixels": 0,
        "blue_value": None,
        "error": None,
    }
    value.update(overrides)
    return value


def test_config_centralizes_plan_defaults():
    assert config.TSL2591_SDA_PIN == 4
    assert config.TSL2591_SCL_PIN == 5
    assert config.DHT11_PIN == 3
    assert config.SAMPLE_INTERVAL_MS == 300_000
    assert config.HISTORY_CAPACITY == 60
    assert config.MAX_BODY_BYTES > 0


def test_ring_history_is_bounded_and_ordered():
    history = RingHistory(3)
    for item in range(5):
        history.append(item)
    assert len(history) == 3
    assert history.to_list() == [2, 3, 4]
    assert history.latest() == 4


def test_ring_history_rejects_invalid_capacity_and_empty_latest():
    assert RingHistory(1).latest() is None
    for capacity in (0, -1, 1.5, True):
        try:
            RingHistory(capacity)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid capacity accepted: %r" % (capacity,))


def test_calculation_is_explicitly_not_configured():
    assert calculate({"lux": 1}, [{"blue_value": 2}]) == {
        "value": None,
        "status": "not_configured",
    }


def test_camera_json_validation_accepts_contract_without_mutating_input():
    original = camera_reading()
    validated = validate_camera_reading(original)
    assert validated == original
    assert validated is not original


def test_camera_json_validation_rejects_missing_wrong_types_and_bad_trigger():
    invalid = [
        {},
        camera_reading(sequence=True),
        camera_reading(width=-1),
        camera_reading(trigger="button"),
        camera_reading(blue_value="blue"),
        camera_reading(error=3),
    ]
    for value in invalid:
        try:
            validate_camera_reading(value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid reading accepted: %r" % (value,))


def test_http_routes_status_codes_and_camera_storage():
    sensors = RingHistory(2)
    cameras = RingHistory(2)
    sensors.append({"uptime_ms": 900, "temperature_c": 20})
    app = Application(sensors, cameras, clock=lambda: 1000)

    assert app.route("GET", "/")[0] == 200
    assert app.route("GET", "/api/v1/state")[0] == 200
    assert app.route("GET", "/api/v1/history/sensors")[0] == 200
    assert app.route("GET", "/api/v1/history/camera")[0] == 200
    assert app.route("GET", "/missing")[0] == 404
    assert app.route("POST", "/api/v1/state")[0] == 405
    assert app.route("GET", "/api/v1/camera/readings")[0] == 405
    assert app.route("POST", "/api/v1/camera/readings", b"not-json")[0] == 400

    status, content_type, body = app.route(
        "POST", "/api/v1/camera/readings", json.dumps(camera_reading()).encode()
    )
    assert status == 201
    assert content_type == "application/json"
    assert json.loads(body)["received_uptime_ms"] == 1000
    assert cameras.latest()["sequence"] == 7


class GoodDht:
    def measure(self):
        pass

    def temperature(self):
        return 24

    def humidity(self):
        return 55


class BrokenDht:
    def measure(self):
        raise OSError("dht disconnected")


class GoodLight:
    def read(self):
        return {"lux": 12.5, "full_spectrum": 20, "infrared": 3, "visible": 17}


class BrokenLight:
    def read(self):
        raise OSError("i2c disconnected")


def test_sensor_single_failure_does_not_block_other_sensor():
    dht_failed = SensorSampler(BrokenDht(), GoodLight(), clock=lambda: 42).sample()
    assert dht_failed["dht_status"] == "error"
    assert dht_failed["tsl2591_status"] == "ok"
    assert dht_failed["lux"] == 12.5
    assert "dht11" in dht_failed["errors"]

    light_failed = SensorSampler(GoodDht(), BrokenLight(), clock=lambda: 43).sample()
    assert light_failed["dht_status"] == "ok"
    assert light_failed["temperature_c"] == 24
    assert light_failed["tsl2591_status"] == "error"
    assert "tsl2591" in light_failed["errors"]

