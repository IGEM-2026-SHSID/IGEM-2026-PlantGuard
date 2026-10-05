import io
import json
import socket
import struct

from PIL import Image

from blue_analysis import BlueLevelAnalyzer
import server


def test_protocol_round_trip_and_decode():
    output = io.BytesIO()
    Image.new("RGB", (3, 2), "blue").save(output, "JPEG")
    jpeg = output.getvalue()
    metadata = json.dumps({"device_id": "cam", "sequence": 1}).encode()
    sender, receiver = socket.socketpair()
    try:
        sender.sendall(struct.pack("!4sII", b"PGJ1", len(metadata), len(jpeg)))
        sender.sendall(metadata + jpeg)
        received_metadata, received_jpeg = server.receive_frame(receiver)
    finally:
        sender.close()
        receiver.close()
    report = server.decode_report(received_metadata, received_jpeg)
    assert (report["width"], report["height"]) == (3, 2)
    assert report["decoded_pixels"] == 6


def test_blue_level_analyzer_applies_three_high_pass_thresholds():
    output = io.BytesIO()
    source = Image.new("RGB", (4, 1))
    source.putdata([(0, 0, value) for value in (32, 80, 144, 224)])
    source.save(output, "PNG")

    result = BlueLevelAnalyzer().analyze(output.getvalue())

    assert result.size == (16, 33)
    assert [result.getpixel((x, 32)) for x in range(4)] == [
        (0, 0, 32), (0, 0, 80), (0, 0, 144), (0, 0, 224),
    ]
    assert [result.getpixel((x, 32)) for x in range(4, 16)] == [
        (255, 255, 255), (0, 0, 0), (0, 0, 0), (0, 0, 0),
        (255, 255, 255), (255, 255, 255), (0, 0, 0), (0, 0, 0),
        (255, 255, 255), (255, 255, 255), (255, 255, 255), (0, 0, 0),
    ]
