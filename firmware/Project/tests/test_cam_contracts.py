from blue_analyzer import BlueAnalyzer
from reporting import make_report
from scheduler import choose_trigger, debounce_accept, ticks_due


def ticks_diff(a, b):
    return a - b


def test_trigger_merge_prioritizes_gpio_and_timer_remains_available():
    assert choose_trigger(True, True) == "gpio"
    assert choose_trigger(True, False) == "gpio"
    assert choose_trigger(False, True) == "timer"
    assert choose_trigger(False, False) is None


def test_debounce_and_due_helpers_use_wrap_safe_diff_callback():
    assert debounce_accept(1000, None, 250, ticks_diff)
    assert not debounce_accept(1100, 1000, 250, ticks_diff)
    assert debounce_accept(1250, 1000, 250, ticks_diff)
    assert not ticks_due(999, 1000, ticks_diff)
    assert ticks_due(1000, 1000, ticks_diff)


def test_upload_payload_contains_fixed_c3_contract_and_metadata():
    report = make_report(
        "cam-1", 2, 3000, "gpio", width=160, height=120,
        decoded_pixels=19200, selected_pixels=0, blue_value=None,
        analysis_status="algorithm_not_configured",
        timing_ms={"capture": 12}, memory_bytes={"before": 1000},
    )
    required = {
        "device_id", "sequence", "capture_uptime_ms", "trigger", "width",
        "height", "decoded_pixels", "selected_pixels", "blue_value", "error",
    }
    assert required <= report.keys()
    assert report["trigger"] == "gpio"
    assert report["timing_ms"]["capture"] == 12
    assert report["analysis_status"] == "algorithm_not_configured"


def test_blue_analyzer_placeholder_counts_pixels_and_returns_no_formula_value():
    analyzer = BlueAnalyzer()
    analyzer.consume(0, 0, 0x0000FF)
    analyzer.consume(1, 0, 0xFFFFFF)
    assert analyzer.result() == {
        "blue_value": None,
        "status": "algorithm_not_configured",
        "decoded_pixels": 2,
        "selected_pixels": 0,
    }
    analyzer.reset()
    assert analyzer.result()["decoded_pixels"] == 0

