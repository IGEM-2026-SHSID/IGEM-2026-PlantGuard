"""Standalone ESP-CAM PGJ1 receiver and C3 JSON reporter."""
import argparse
import json
import logging
from pathlib import Path
import socket
import struct
import time
import urllib.parse
import urllib.request

try:
    from .analysis import BlueAnalyzer, Settings, make_preview
    from .records import DEFAULT_RECORDS_FILE, fetch_sensor, save_record
except ImportError:
    from analysis import BlueAnalyzer, Settings, make_preview
    from records import DEFAULT_RECORDS_FILE, fetch_sensor, save_record

LOG = logging.getLogger("center_blue")
DEFAULT_C3_URL = "http://192.168.4.1/api/v1/camera/readings"


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
    magic, meta_size, jpeg_size = struct.unpack("!4sII", recv_exact(conn, 12))
    if magic != b"PGJ1":
        raise ValueError("invalid PGJ1 magic")
    if not (0 < meta_size <= 4096 and 0 < jpeg_size <= 1048576):
        raise ValueError("frame exceeds protocol size limit")
    metadata = json.loads(recv_exact(conn, meta_size).decode("utf-8"))
    validate_metadata(metadata)
    return metadata, recv_exact(conn, jpeg_size)


def validate_metadata(metadata):
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a JSON object")
    if not isinstance(metadata.get("device_id"), str) or not metadata["device_id"]:
        raise ValueError("device_id must be a non-empty string")
    for field in ("sequence", "capture_uptime_ms"):
        value = metadata.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(field + " must be a non-negative integer")
    if metadata.get("trigger") not in ("timer", "gpio"):
        raise ValueError("trigger must be timer or gpio")


def analyze_report(metadata, jpeg, analyzer):
    validate_metadata(metadata)
    started = time.monotonic()
    metrics, image, mask = analyzer.analyze(jpeg)
    # Send only the camera contract and compact diagnostics, not arbitrary input.
    report = {key: metadata[key] for key in
              ("device_id", "sequence", "capture_uptime_ms", "trigger")}
    report.update(metrics)
    report["timing_ms"] = {"pc_analysis": round((time.monotonic() - started) * 1000)}
    return report, image, mask


def post_report(url, report):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("C3 URL must be an HTTP(S) URL")
    body = json.dumps(report, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(body) > 2048:
        raise ValueError("report exceeds C3's 2048-byte body limit")
    request = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
    # Local device traffic should not be routed through system HTTP proxies.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=5) as response:
        if response.status not in (200, 201):
            raise OSError("C3 returned HTTP %d" % response.status)


def record_with_sensor(c3_url, report, records_file):
    try:
        sensor, age = fetch_sensor(c3_url)
        error = None
    except (OSError, ValueError, UnicodeError) as exc:
        sensor, age = None, None
        error = "%s: %s" % (type(exc).__name__, exc)
        LOG.warning("C3 sensor snapshot unavailable: %s", error)
    return save_record(records_file, report, sensor, age, error)


def process_connection(conn, c3_url, analyzer, viewer=None, records_file=DEFAULT_RECORDS_FILE):
    """ACK only once C3 accepts the report and a local record is written."""
    try:
        metadata, jpeg = receive_frame(conn)
        report, image, mask = analyze_report(metadata, jpeg, analyzer)
        post_report(c3_url, report)
        record_with_sensor(c3_url, report, records_file)
        conn.sendall(b"\x01")
    except Exception as exc:
        try:
            conn.sendall(b"\x00")
        except OSError:
            pass
        LOG.warning("Frame rejected: %s", exc)
        return None
    LOG.info("Frame %s: blue=%s, pixels=%s, status=%s", report["sequence"],
             report["blue_value"], report["selected_pixels"], report["analysis_status"])
    if viewer is not None:
        try:
            viewer.show(make_preview(report, image, mask))
        except Exception as exc:
            LOG.warning("Preview failed: %s", exc)
    return report


class Viewer:
    def __init__(self):
        import tkinter as tk
        from PIL import ImageTk
        self.image_tk = ImageTk
        self.root = tk.Tk()
        self.root.title("PlantGuard Central Blue")
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)
        self.label = tk.Label(self.root)
        self.label.pack()
        self.photo = None

    def show(self, image):
        from PIL import Image
        image.thumbnail((1200, 800), Image.Resampling.LANCZOS)
        self.photo = self.image_tk.PhotoImage(image, master=self.root)
        self.label.configure(image=self.photo)
        self.root.deiconify()
        self.poll()

    def poll(self):
        self.root.update_idletasks()
        self.root.update()

    def close(self):
        self.root.destroy()


def serve(host, port, c3_url, analyzer, show=False, records_file=DEFAULT_RECORDS_FILE):
    viewer = Viewer() if show else None
    try:
        with socket.create_server((host, port)) as listener:
            listener.settimeout(0.1)
            LOG.info("Listening on %s:%d; C3: %s", host, port, c3_url)
            while True:
                if viewer:
                    viewer.poll()
                try:
                    conn, address = listener.accept()
                except socket.timeout:
                    continue
                with conn:
                    conn.settimeout(10)
                    LOG.info("Receiving from %s", address[0])
                    process_connection(conn, c3_url, analyzer, viewer, records_file)
    finally:
        if viewer:
            viewer.close()


def main():
    parser = argparse.ArgumentParser(description="Extract central blue region and report to C3")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--c3-url", default=DEFAULT_C3_URL)
    parser.add_argument("--records-file", type=Path, default=DEFAULT_RECORDS_FILE,
                        help="append one JSONL row per analyzed photo")
    parser.add_argument("--roi-ratio", type=float, default=0.6)
    parser.add_argument("--hue-min", type=float, default=190)
    parser.add_argument("--hue-max", type=float, default=260)
    parser.add_argument("--saturation-min", type=float, default=0.25)
    parser.add_argument("--brightness-min", type=float, default=0.15)
    parser.add_argument("--min-pixels", type=int, default=9)
    parser.add_argument("--show", action="store_true", help="open live image preview")
    parser.add_argument("--image", type=Path, help="analyze a local image instead of listening")
    parser.add_argument("--preview", type=Path, help="save local-image preview as PNG")
    parser.add_argument("--post", action="store_true", help="also post local-image result to C3")
    args = parser.parse_args()
    if (args.preview or args.post) and args.image is None:
        parser.error("--preview and --post require --image")
    try:
        analyzer = BlueAnalyzer(Settings(args.roi_ratio, args.hue_min, args.hue_max,
                                        args.saturation_min, args.brightness_min, args.min_pixels))
    except ValueError as exc:
        parser.error(str(exc))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.image:
        metadata = {"device_id": "pc-local", "sequence": 0,
                    "capture_uptime_ms": 0, "trigger": "gpio"}
        report, image, mask = analyze_report(metadata, args.image.read_bytes(), analyzer)
        if args.preview:
            make_preview(report, image, mask).save(args.preview, format="PNG")
        if args.post:
            post_report(args.c3_url, report)
            record_with_sensor(args.c3_url, report, args.records_file)
        print(json.dumps(report, indent=2, allow_nan=False))
    else:
        try:
            serve(args.host, args.port, args.c3_url, analyzer, args.show, args.records_file)
        except KeyboardInterrupt:
            LOG.info("Stopped")


if __name__ == "__main__":
    main()
