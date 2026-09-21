import importlib.util
from pathlib import Path

import pytest


def test_micropython_jpeg_decoder_cpython_import_status():
    """Document why the fixed-JPEG contract cannot run in ordinary CPython yet."""
    path = Path(__file__).resolve().parents[1] / "ESP-CAM" / "lib" / "JPEGdecoder.py"
    spec = importlib.util.spec_from_file_location("plantguard_jpegdecoder", path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (NameError, ImportError) as exc:
        pytest.xfail(
            "decoder uses MicroPython-only micropython.viper/native semantics: %s" % exc
        )
    pytest.skip("decoder imported, but no repository-owned fixed JPEG sample exists yet")
