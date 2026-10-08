"""PlantGuard PC JPEG receiver and C3 report forwarder.

The blue detector is an optional, unvalidated prototype and is OFF by default.
"""
import argparse
import io
import json
import socket
import struct
import time
import urllib.request

from PIL import Image

from blue_analysis import analyze_blue, parse_roi

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
    if not isinstance(metadata, dict):
        raise ValueError("frame metadata must be a JSON object")
    return metadata, recv_exact(conn, jpeg_size)


def decode_report(metadata, jpeg_data, *, blue_prototype=False,
                  roi=(0.0, 0.0, 1.0, 1.0), min_region_pixels=16):
    started = time.monotonic()
    with Image.open(io.BytesIO(jpeg_data)) as image:
        image.verify()
    with Image.open(io.BytesIO(jpeg_data)) as image:
        rgb = image.convert("RGB")
        rgb.load()
        width, height = rgb.size
        # Preserve the repository's original behavior until the team has
        # agreed on a scientifically meaningful extraction/calibration method.
        results = {"selected_pixels": 0, "blue_value": None,
                   "analysis_status": "algorithm_not_configured"}
        if blue_prototype:
            results = analyze_blue(rgb, roi=roi,
                                   min_region_pixels=min_region_pixels)
    report = dict(metadata)
    report.update({"width": width, "height": height,
                   "decoded_pixels": width * height, "error": None})
    report.update(results)
    if report.get("timing_ms") is None:
        report["timing_ms"] = {}
    if not isinstance(report["timing_ms"], dict):
        raise ValueError("timing_ms must be an object if provided")
    report["timing_ms"]["pc_decode"] = round(
        (time.monotonic() - started) * 1000)
    return report


def post_report(url, report):
    body = json.dumps(report, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(url, body,
        {"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        if response.status not in (200, 201):
            raise OSError("C3 returned HTTP %d" % response.status)


def handle_connection(conn, address, c3_url, *, blue_prototype=False,
                      roi=(0.0, 0.0, 1.0, 1.0), min_region_pixels=16):
    """Process one frame; acknowledge CAM ONLY after C3 accepts the report."""
    with conn:
        conn.settimeout(20)
        try:
            metadata, jpeg = receive_frame(conn)
            report = decode_report(metadata, jpeg, blue_prototype=blue_prototype,
                                   roi=roi, min_region_pixels=min_region_pixels)
            post_report(c3_url, report)
            conn.sendall(b"\x01")
            print("Frame %s from %s: %dx%d, %d bytes; analysis=%s; blue=%s" %
                  (report.get("sequence"), address[0], report["width"],
                   report["height"], len(jpeg), report["analysis_status"],
                   report["blue_value"]))
            return report
        except Exception as exc:
            try:
                conn.sendall(b"\x00")
            except OSError:
                pass
            print("Rejected connection from %s: %s" % (address[0], exc))
            return None


def serve(host, port, c3_url, *, blue_prototype=False,
          roi=(0.0, 0.0, 1.0, 1.0), min_region_pixels=16):
    with socket.create_server((host, port)) as server:
        print("Listening for ESP-CAM on %s:%d" % (host, port))
        if blue_prototype:
            print("EXPERIMENTAL blue detector active (NOT a concentration measurement)")
        while True:
            conn, address = server.accept()
            handle_connection(conn, address, c3_url, blue_prototype=blue_prototype,
                              roi=roi, min_region_pixels=min_region_pixels)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PlantGuard JPEG receiver")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--c3-url", default="http://192.168.4.1/api/v1/camera/readings")
    parser.add_argument("--blue-prototype", action="store_true",
                        help="Enable UNVALIDATED HSV/connected-region blue indicator")
    parser.add_argument("--roi", type=parse_roi, default=(0.0, 0.0, 1.0, 1.0),
                        help="Normalized region x0,y0,x1,y1; limit to bead area")
    parser.add_argument("--min-region-pixels", type=int, default=16)
    args = parser.parse_args()
    if args.min_region_pixels < 1:
        parser.error("--min-region-pixels must be positive")
    serve(args.host, args.port, args.c3_url,
          blue_prototype=args.blue_prototype, roi=args.roi,
          min_region_pixels=args.min_region_pixels)
