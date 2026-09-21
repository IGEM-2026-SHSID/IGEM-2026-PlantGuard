"""Pure trigger scheduling helpers, importable by CPython tests."""


def ticks_due(now_ms, deadline_ms, ticks_diff):
    return ticks_diff(now_ms, deadline_ms) >= 0


def choose_trigger(gpio_pending, timer_due):
    """Merge simultaneous events into one capture; GPIO has priority."""
    if gpio_pending:
        return "gpio"
    if timer_due:
        return "timer"
    return None


def debounce_accept(edge_ms, last_edge_ms, debounce_ms, ticks_diff):
    if last_edge_ms is None:
        return True
    return ticks_diff(edge_ms, last_edge_ms) >= debounce_ms

