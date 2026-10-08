"""Offline synthetic tests; no connected CAM or C3 required."""
import io
import json
import socket
import struct

import pytest
from PIL import Image, ImageDraw

import server
from blue_analysis import analyze_blue, parse_roi


def synthetic_photo():
    image = Image.new("RGB", (100, 70), "#9a856c")  # approximate soil-like background
    draw = ImageDraw.Draw(image)
    draw.ellipse((30, 15, 52, 37), fill=(8, 25, 230))  # one blue bead
    draw.ellipse((78, 56, 79, 57), fill=(0, 0, 255))   # tiny false-positive speck
    draw.rectangle((5, 48, 24, 60), fill=(20, 165, 30))  # green: not blue
    return image


def as_jpeg(image):
    output = io.BytesIO()
    image.save(output, "JPEG", quality=98, subsampling=0)
    return output.getvalue()


def valid_metadata():
    return {"device_id": "cam", "sequence": 2, "capture_uptime_ms": 10,
            "trigger": "timer", "timing_ms": {"capture": 2}}


def test_identifies_one_large_blue_region_and_ignores_speck():
    result, mask = analyze_blue(synthetic_photo(), min_region_pixels=16, return_mask=True)
    assert result["analysis_status"] == "experimental_unvalidated"
    assert result["blue_region_count"] == 1
    assert result["selected_pixels"] >= 200
    assert 0.5 < result["blue_value"] <= 1
    assert mask.getpixel((40, 24)) == 255
    assert mask.getpixel((8, 53)) == 0  # green region is not blue
    assert mask.getpixel((78, 56)) == 0  # too few pixels


def test_roi_excludes_bead():
    result = analyze_blue(synthetic_photo(), roi=(0, 0.65, 0.30, 1),
                          min_region_pixels=16)
    assert result["selected_pixels"] == 0
    assert result["blue_value"] is None
    assert result["analysis_status"] == "no_blue_region"


def test_invalid_roi_and_min_region():
    with pytest.raises(ValueError):
        parse_roi("0.8,0,0.1,1")
    with pytest.raises(ValueError):
        analyze_blue(synthetic_photo(), min_region_pixels=0)


def test_existing_default_still_disabled():
    report = server.decode_report(valid_metadata(), as_jpeg(synthetic_photo()))
    assert report["analysis_status"] == "algorithm_not_configured"
    assert report["blue_value"] is None
    assert report["decoded_pixels"] == 7000
    assert report["selected_pixels"] == 0


def test_opt_in_prototype_sets_numeric_blue_value():
    report = server.decode_report(valid_metadata(), as_jpeg(synthetic_photo()),
                                  blue_prototype=True, min_region_pixels=16)
    assert report["analysis_status"] == "experimental_unvalidated"
    assert report["blue_region_count"] == 1
    assert isinstance(report["blue_value"], float)
    assert report["selected_pixels"] > 0
    assert report["timing_ms"]["capture"] == 2
    assert report["timing_ms"]["pc_decode"] >= 0


def test_protocol_to_ack_success_only_after_post(monkeypatch):
    sent = []
    monkeypatch.setattr(server, "post_report", lambda url, report: sent.append(report))
    sender, receiver = socket.socketpair()
    jpeg = as_jpeg(synthetic_photo())
    metadata = json.dumps(valid_metadata()).encode()
    try:
        sender.sendall(struct.pack("!4sII", b"PGJ1", len(metadata), len(jpeg)))
        sender.sendall(metadata + jpeg)
        report = server.handle_connection(receiver, ("127.0.0.1", 1234),
                                          "http://test/api", blue_prototype=True)
        assert sender.recv(1) == b"\x01"
        assert sent == [report]
        assert report["analysis_status"] == "experimental_unvalidated"
    finally:
        sender.close()


def test_failed_post_does_not_ack_success(monkeypatch):
    def fail(url, report):
        raise OSError("C3 offline")
    monkeypatch.setattr(server, "post_report", fail)
    sender, receiver = socket.socketpair()
    jpeg = as_jpeg(synthetic_photo())
    metadata = json.dumps(valid_metadata()).encode()
    try:
        sender.sendall(struct.pack("!4sII", b"PGJ1", len(metadata), len(jpeg)))
        sender.sendall(metadata + jpeg)
        report = server.handle_connection(receiver, ("127.0.0.1", 1234),
                                          "http://test/api", blue_prototype=True)
        assert report is None
        assert sender.recv(1) == b"\x00"
    finally:
        sender.close()
