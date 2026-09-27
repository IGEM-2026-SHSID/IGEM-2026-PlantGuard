"""PlantGuard PC JPEG receiver and C3 report forwarder."""
import argparse
import io
import json
import socket
import struct
import time
import urllib.request

from PIL import Image

MAGIC = b"PGJ1"
MAX_METADATA = 4096
MAX_JPEG = 1024 * 1024


def recv_exact(conn, size):
    chunks = []
    while size:
        chunk = conn.recv(min(size, 65536))
        if not chunk:
            raise ConnectionError("connection closed before frame completed")
        chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks)


def receive_frame(conn):
    magic, metadata_size, jpeg_size = struct.unpack("!4sII", recv_exact(conn, 12))
    if magic != MAGIC:
        raise ValueError("invalid protocol magic")
    if not 0 < metadata_size <= MAX_METADATA or not 0 < jpeg_size <= MAX_JPEG:
        raise ValueError("frame exceeds configured size limit")
    metadata = json.loads(recv_exact(conn, metadata_size).decode("utf-8"))
    return metadata, recv_exact(conn, jpeg_size)


def decode_report(metadata, jpeg_data):
    started = time.monotonic()
    with Image.open(io.BytesIO(jpeg_data)) as image:
        image.verify()
    with Image.open(io.BytesIO(jpeg_data)) as image:
        width, height = image.size
        image.convert("RGB").load()
    report = dict(metadata)
    report.update({"width": width, "height": height,
                   "decoded_pixels": width * height, "selected_pixels": 0,
                   "blue_value": None, "analysis_status": "algorithm_not_configured",
                   "error": None})
    report.setdefault("timing_ms", {})["pc_decode"] = round(
        (time.monotonic() - started) * 1000)
    return report


def post_report(url, report):
    body = json.dumps(report, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(url, body,
        {"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status not in (200, 201):
            raise OSError("C3 returned HTTP %d" % response.status)


def serve(host, port, c3_url):
    with socket.create_server((host, port)) as server:
        print("Listening for ESP-CAM on %s:%d" % (host, port))
        while True:
            conn, address = server.accept()
            with conn:
                conn.settimeout(20)
                try:
                    metadata, jpeg = receive_frame(conn)
                    report = decode_report(metadata, jpeg)
                    post_report(c3_url, report)
                    conn.sendall(b"\x01")
                    print("Frame %s from %s: %dx%d, %d bytes" %
                          (report.get("sequence"), address[0], report["width"],
                           report["height"], len(jpeg)))
                except Exception as exc:
                    try:
                        conn.sendall(b"\x00")
                    except OSError:
                        pass
                    print("Rejected connection from %s: %s" % (address[0], exc))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PlantGuard JPEG receiver")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--c3-url", default="http://192.168.4.1/api/v1/camera/readings")
    args = parser.parse_args()
    serve(args.host, args.port, args.c3_url)
