import io
import json
import socket
import struct

from PIL import Image

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
