import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diff(a, b):
    return a - b


def test_gpio_priority_and_merge():
    scheduler = load("scheduler")
    assert scheduler.choose_trigger(True, True) == "gpio"
    assert scheduler.choose_trigger(False, True) == "timer"
    assert scheduler.choose_trigger(False, False) is None


def test_debounce():
    scheduler = load("scheduler")
    assert scheduler.debounce_accept(100, None, 250, diff)
    assert not scheduler.debounce_accept(200, 100, 250, diff)
    assert scheduler.debounce_accept(350, 100, 250, diff)


def test_analyzer_is_explicitly_unconfigured():
    module = load("blue_analyzer")
    analyzer = module.BlueAnalyzer()
    analyzer.consume(0, 0, 0x1122FF)
    result = analyzer.result()
    assert result == {"blue_value": None, "status": "algorithm_not_configured",
                      "decoded_pixels": 1, "selected_pixels": 0}


def test_report_schema():
    reporting = load("reporting")
    report = reporting.make_report("cam", 2, 123, "gpio")
    required = {"device_id", "sequence", "capture_uptime_ms", "trigger",
                "width", "height", "decoded_pixels", "selected_pixels",
                "blue_value", "error"}
    assert required <= set(report)

