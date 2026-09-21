try:
    import ujson as json
except ImportError:
    import json

try:
    from time import ticks_ms, ticks_diff, sleep_ms
except ImportError:
    import time
    def ticks_ms():
        return int(time.monotonic() * 1000)
    def ticks_diff(a, b):
        return a - b
    def sleep_ms(ms):
        time.sleep(ms / 1000.0)

def json_dumps(value):
    try:
        return json.dumps(value, separators=(",", ":"))
    except TypeError:  # ujson lacks separators
        return json.dumps(value)

