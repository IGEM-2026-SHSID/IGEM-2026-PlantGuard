"""Length-prefixed JPEG upload with bounded metadata."""
import socket
import struct
try:
    import ujson as json
except ImportError:
    import json


def send_jpeg(host, port, image, report, timeout=15):
    metadata = json.dumps(report).encode("utf-8")
    if len(metadata) > 4096 or not 0 < len(image) <= 1048576:
        raise ValueError("metadata or JPEG exceeds protocol limit")
    sock = socket.socket()
    try:
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(struct.pack("!4sII", b"PGJ1", len(metadata), len(image)))
        view = memoryview(image)
        sock.sendall(metadata)
        for offset in range(0, len(view), 1024):
            sock.sendall(view[offset:offset + 1024])
        if sock.recv(1) != b"\x01":
            raise OSError("PC receiver did not acknowledge frame")
    finally:
        sock.close()
