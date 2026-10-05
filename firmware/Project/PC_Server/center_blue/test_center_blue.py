import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from center_blue.analysis import BlueAnalyzer, Settings, make_preview
from center_blue import server
from center_blue.records import state_url


def encoded(image, fmt="PNG"):
    output = io.BytesIO()
    image.save(output, fmt)
    return output.getvalue()


def metadata():
    return {"device_id": "cam", "sequence": 1, "capture_uptime_ms": 123,
            "trigger": "timer", "error": {"old": "ignored"}}


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = BlueAnalyzer()

    def test_pure_blue_and_preview(self):
        metrics, image, mask = self.analyzer.analyze(encoded(Image.new("RGB", (100, 100), "blue")))
        self.assertEqual(metrics["roi"], [20, 20, 80, 80])
        self.assertEqual(metrics["selected_pixels"], 3600)
        self.assertEqual(metrics["blue_value"], 100)
        self.assertEqual(mask.getpixel((50, 50)), 255)
        self.assertEqual(mask.getpixel((0, 0)), 0)
        self.assertEqual(make_preview(metrics, image, mask).size, (200, 132))

    def test_white_gray_red_and_dark_are_not_blue(self):
        for color in ("white", "gray", "red", "black", (0, 0, 20)):
            with self.subTest(color=color):
                metrics, _, _ = self.analyzer.analyze(encoded(Image.new("RGB", (40, 40), color)))
                self.assertIsNone(metrics["blue_value"])
                self.assertEqual(metrics["selected_pixels"], 0)
                self.assertEqual(metrics["analysis_status"], "no_blue_region")

    def test_nearest_component_beats_larger_component(self):
        image = Image.new("RGB", (100, 100), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 35, 70), fill="blue")
        draw.rectangle((48, 48, 52, 52), fill=(50, 100, 200))
        metrics, _, _ = self.analyzer.analyze(encoded(image))
        self.assertEqual(metrics["region_bbox"], [48, 48, 53, 53])
        self.assertEqual(metrics["selected_pixels"], 25)
        self.assertEqual(metrics["blue_value"], 50)

    def test_edges_and_small_noise_are_excluded(self):
        image = Image.new("RGB", (100, 100), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 19, 99), fill="blue")
        draw.rectangle((49, 49, 50, 50), fill="blue")
        metrics, _, _ = self.analyzer.analyze(encoded(image))
        self.assertIsNone(metrics["blue_value"])

    def test_border_rows_do_not_wrap_components(self):
        image = Image.new("RGB", (10, 10), "white")
        image.putpixel((9, 4), (0, 0, 255))
        image.putpixel((0, 5), (0, 0, 255))
        metrics, _, _ = BlueAnalyzer(Settings(roi_ratio=1, min_pixels=2)).analyze(encoded(image))
        self.assertEqual(metrics["selected_pixels"], 0)

    def test_small_image_and_jpeg(self):
        metrics, _, _ = BlueAnalyzer(Settings(min_pixels=1)).analyze(
            encoded(Image.new("RGB", (1, 1), "blue"), "JPEG"))
        self.assertEqual(metrics["selected_pixels"], 1)
        self.assertGreater(metrics["blue_value"], 99)

    def test_bad_images_and_settings(self):
        with self.assertRaises(Exception):
            self.analyzer.analyze(b"not an image")
        for kwargs in ({"roi_ratio": 0}, {"roi_ratio": 2}, {"min_pixels": 0},
                       {"hue_min": 270}, {"saturation_min": -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Settings(**kwargs)


class TransportTests(unittest.TestCase):
    def packet(self, color="blue"):
        jpeg = encoded(Image.new("RGB", (20, 20), color), "JPEG")
        meta = json.dumps(metadata()).encode()
        return struct.pack("!4sII", b"PGJ1", len(meta), len(jpeg)) + meta + jpeg

    def test_fragmented_stream(self):
        packet = self.packet()

        class Fragmented:
            def recv(self, count):
                nonlocal packet
                result, packet = packet[:min(count, 3)], packet[min(count, 3):]
                return result

        meta, jpeg = server.receive_frame(Fragmented())
        self.assertEqual(meta["sequence"], 1)
        report, _, _ = server.analyze_report(meta, jpeg, BlueAnalyzer())
        self.assertEqual(report["analysis_status"], "ok")
        self.assertIsNone(report["error"])

    def test_bad_header_and_incomplete_stream(self):
        for packet in (struct.pack("!4sII", b"BAD!", 1, 1),
                       struct.pack("!4sII", b"PGJ1", 4097, 1), b"PGJ1"):
            sender, receiver = socket.socketpair()
            with sender, receiver:
                sender.sendall(packet)
                sender.shutdown(socket.SHUT_WR)
                with self.assertRaises((ValueError, ConnectionError)):
                    server.receive_frame(receiver)

    def test_invalid_metadata(self):
        for value in ([], {}, {**metadata(), "sequence": True},
                      {**metadata(), "trigger": "unknown"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                server.validate_metadata(value)

    def test_upload_failure_returns_negative_ack(self):
        sender, receiver = socket.socketpair()
        with sender, receiver:
            sender.sendall(self.packet())
            with patch.object(server, "post_report", side_effect=OSError("offline")):
                with self.assertLogs("center_blue", level="WARNING"):
                    self.assertIsNone(server.process_connection(receiver, "http://localhost", BlueAnalyzer()))
            self.assertEqual(sender.recv(1), b"\x00")

    def test_state_url_and_invalid_state(self):
        self.assertEqual(state_url("http://127.0.0.1:8765/custom/path?x=1"),
                         "http://127.0.0.1:8765/api/v1/state")
        with self.assertRaises(ValueError):
            state_url("invalid")

    def test_sensor_read_failure_still_records_photo(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "readings.jsonl"
            sender, receiver = socket.socketpair()
            with sender, receiver:
                sender.sendall(self.packet())
                with patch.object(server, "post_report") as post, \
                        patch.object(server, "fetch_sensor", side_effect=OSError("offline")), \
                        self.assertLogs("center_blue", level="WARNING"):
                    report = server.process_connection(
                        receiver, "http://127.0.0.1", BlueAnalyzer(), records_file=path)
                post.assert_called_once()
                self.assertEqual(sender.recv(1), b"\x01")
            row = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(row["camera"]["blue_value"], report["blue_value"])
            self.assertIsNone(row["sensor"])
            self.assertIn("offline", row["sensor_error"])

    def test_write_failure_returns_negative_ack(self):
        sender, receiver = socket.socketpair()
        with sender, receiver:
            sender.sendall(self.packet())
            with patch.object(server, "post_report"), \
                    patch.object(server, "fetch_sensor", return_value=(None, None)), \
                    patch.object(server, "save_record", side_effect=OSError("disk full")), \
                    self.assertLogs("center_blue", level="WARNING"):
                self.assertIsNone(server.process_connection(receiver, "http://127.0.0.1", BlueAnalyzer()))
            self.assertEqual(sender.recv(1), b"\x00")

    def test_actual_c3_contract_over_http_and_ack_order(self):
        # Exercise the repository's real C3 route behind a local HTTP listener.
        c3_path = str(Path(__file__).resolve().parents[2] / "ESP32-C3")
        sys.path.insert(0, c3_path)
        try:
            from app import Application
            from history import RingHistory
            app = Application(RingHistory(4), RingHistory(4))
        finally:
            sys.path.remove(c3_path)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status, content_type, response = app.route("GET", self.path)
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                self.server.test.assertLessEqual(len(body), 2048)
                status, content_type, response = app.route("POST", self.path, body)
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, *args):
                pass

        httpd = HTTPServer(("127.0.0.1", 0), Handler)
        httpd.test = self
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            url = "http://127.0.0.1:%d/api/v1/camera/readings" % httpd.server_port
            app.sensors.append({"uptime_ms": app.clock(), "temperature_c": 26,
                                "air_humidity_pct": 60, "lux": 123,
                                "full_spectrum": 100, "infrared": 30,
                                "visible": 70, "dht_status": "ok",
                                "tsl2591_status": "ok", "errors": {}})
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "readings.jsonl"
                for color in ("blue", "white"):
                    sender, receiver = socket.socketpair()
                    with sender, receiver:
                        sender.settimeout(2)
                        sender.sendall(self.packet(color))
                        report = server.process_connection(receiver, url, BlueAnalyzer(), records_file=path)
                        self.assertIsNotNone(report)
                        self.assertEqual(app.cameras.latest()["blue_value"], report["blue_value"])
                        self.assertEqual(sender.recv(1), b"\x01")
                records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(records), 2)
                self.assertEqual([row["camera"]["blue_value"] for row in records], [100, None])
                self.assertEqual([row["sensor"]["lux"] for row in records], [123, 123])
                self.assertTrue(all(row["sensor_age_ms"] >= 0 for row in records))
                self.assertTrue(all(row["recorded_at"] for row in records))
                self.assertTrue(all(row["sensor_error"] is None for row in records))
            self.assertEqual(len(app.cameras), 2)
            self.assertIsNone(app.state()["camera"]["blue_value"])
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)

    def test_local_cli_writes_preview_without_posting(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.jpg"
            preview_path = Path(directory) / "preview.png"
            Image.new("RGB", (40, 40), "blue").save(image_path)
            result = subprocess.run([sys.executable, str(Path(server.__file__)),
                                     "--image", str(image_path), "--preview", str(preview_path)],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)["analysis_status"], "ok")
            with Image.open(preview_path) as preview:
                self.assertEqual(preview.size, (80, 72))


if __name__ == "__main__":
    unittest.main()
