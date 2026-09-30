"""PlantGuard practice/demo: synthetic pictures + optional fully local protocol simulation.

No camera, experimental photos, C3 device, or internet connection is needed.
This creates illustrative colors ONLY. The outputs do not predict drought.

Windows PowerShell (from the PC_Server folder):
    py simulate_without_photos.py
    py simulate_without_photos.py --mock-network

Output goes to PC_Server/synthetic_results/ by default.
"""

import argparse
import csv
import io
import json
from pathlib import Path
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from PIL import Image, ImageDraw

import server
from blue_analysis import analyze_blue

IMAGE_SIZE = (160, 120)
# Synthetic setup: central region only, excluding a distracting blue label.
# These numbers are for GENERATED images; do not reuse blindly with real photos.
DEMO_ROI = (0.30, 0.25, 0.85, 0.85)

SCENES = {
    "strong_blue": (30, 55, 220),
    "medium_blue": (70, 100, 190),
    "pale_blue": (160, 174, 200),
    "purple": (168, 95, 178),
    "not_blue": (197, 166, 137),
    "blue_label_only": None,
}


def make_scene(name):
    """Create a fake 'bead' on a soil-like background and blue label outside ROI.

    RGB values are illustrative, not measured from PlantGuard indicators.
    No bead is drawn for 'blue_label_only'.
    """
    if name not in SCENES:
        raise ValueError("Unknown scene: " + name)
    image = Image.new("RGB", IMAGE_SIZE, (113, 90, 68))
    draw = ImageDraw.Draw(image)
    # Deliberately blue distraction present in EVERY synthetic image.
    draw.rectangle((7, 8, 46, 23), fill=(16, 32, 224))
    # A pale visual frame for clarity; it is outside the analysis ROI.
    draw.rectangle((5, 6, 48, 25), outline=(230, 222, 205), width=1)
    if SCENES[name] is not None:
        draw.ellipse((78, 50, 110, 82), fill=SCENES[name],
                     outline=(85, 82, 79), width=1)
    return image


def as_jpeg(image):
    """Use the same JPEG type that the real camera is designed to send."""
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=97, subsampling=0)
    return buf.getvalue()


def generate_samples(output_dir):
    """Generate test JPEGs, segmentation masks, and JSON/CSV summaries."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    print("\nSYNTHETIC IMAGE TEST (ROI excludes the blue label)")
    print("%-19s %-18s %7s %10s" %
          ("image", "status", "regions", "blue_value"))

    for name in SCENES:
        jpg_path = output_dir / (name + ".jpg")
        jpg_path.write_bytes(as_jpeg(make_scene(name)))
        # Measure the JPEG after compression, not the original RGB drawing.
        with Image.open(jpg_path) as image:
            result, mask = analyze_blue(image, roi=DEMO_ROI,
                                        return_mask=True)
        mask.save(output_dir / (name + "_mask.png"))
        record = {"name": name, **result}
        records.append(record)
        print("%-19s %-18s %7d %10s" %
              (name, result["analysis_status"],
               result["blue_region_count"], str(result["blue_value"])))

    # Explicit false-positive control: analyze the label-only scene without ROI.
    with Image.open(output_dir / "blue_label_only.jpg") as image:
        full, full_mask = analyze_blue(image, return_mask=True)
    full_mask.save(output_dir / "blue_label_only_full_frame_mask.png")
    (output_dir / "results.json").write_text(
        json.dumps({"note": "Synthetic test only; not biological/drought results",
                    "synthetic_roi": DEMO_ROI, "scenes": records,
                    "label_only_without_roi": full}, indent=2), encoding="utf-8")
    with (output_dir / "results.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "analysis_status",
                                              "blue_region_count", "selected_pixels",
                                              "blue_area_fraction", "blue_value"])
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field) for field in writer.fieldnames})
    print("\nLabel-only WITHOUT ROI: %d false region(s)" % full["blue_region_count"])
    print("Label-only WITH    ROI: 0 regions expected")
    print("Generated images, masks, results.csv, results.json in:")
    print(output_dir.resolve())
    return records


def run_mock_network(output_dir):
    """Simulate camera -> real PC handler -> LOCAL mock C3 -> camera ACK.

    Uses localhost only. Does NOT connect to or change any hardware.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    received_reports = []

    class MockC3(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/api/v1/camera/readings":
                self.send_error(404)
                return
            count = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(count)
            received_reports.append(json.loads(data.decode("utf-8")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"accepted":true}')

        def log_message(self, format_string, *args):
            return  # Keep console output beginner-friendly.

    httpd = HTTPServer(("127.0.0.1", 0), MockC3)
    http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    http_thread.start()
    try:
        c3_url = "http://127.0.0.1:%d/api/v1/camera/readings" % httpd.server_port
        jpeg = as_jpeg(make_scene("strong_blue"))
        metadata = {"device_id": "synthetic-camera", "sequence": 1,
                    "capture_uptime_ms": 123, "trigger": "timer",
                    "timing_ms": {"capture": 1}}
        meta_bytes = json.dumps(metadata).encode("utf-8")
        packet = struct.pack("!4sII", server.MAGIC, len(meta_bytes), len(jpeg))
        packet += meta_bytes + jpeg

        # A genuine local TCP socket models the fake camera -> PC link.
        # No camera or C3 devices are involved.
        with socket.create_server(("127.0.0.1", 0)) as listener:
            listener.settimeout(5)
            with socket.create_connection(listener.getsockname(), timeout=5) as cam:
                cam.settimeout(5)
                pc_conn, pc_address = listener.accept()
                cam.sendall(packet)
                pc_report = server.handle_connection(
                    pc_conn, pc_address, c3_url, blue_prototype=True,
                    roi=DEMO_ROI)
                acknowledgement = cam.recv(1)

        if acknowledgement != b"\x01" or pc_report is None:
            raise RuntimeError("Local demo failed: PC did not acknowledge fake camera")
        if len(received_reports) != 1 or received_reports[0] != pc_report:
            raise RuntimeError("Local demo failed: mock C3 received an unexpected report")
        (output_dir / "mock_c3_report.json").write_text(
            json.dumps(pc_report, indent=2), encoding="utf-8")
        print("\nLOCAL SIMULATION PASSED")
        print("Fake camera: sent a PGJ1 packet containing synthetic JPEG")
        print("Real PC code: received JPEG and analyzed blue region")
        print("Mock C3 at 127.0.0.1: received report by HTTP POST")
        print("Fake camera: got success acknowledgement (01)")
        print("Report saved to:", (output_dir / "mock_c3_report.json").resolve())
        return pc_report
    finally:
        httpd.shutdown()
        httpd.server_close()
        http_thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description="PlantGuard offline coding demo")
    parser.add_argument("--output", default=str(Path(__file__).parent / "synthetic_results"))
    parser.add_argument("--mock-network", action="store_true",
                        help="also run fake camera -> PC -> localhost-only mock C3")
    args = parser.parse_args()
    generate_samples(args.output)
    if args.mock_network:
        run_mock_network(args.output)
    print("\nIMPORTANT: No actual bead concentration or drought result is measured.")


if __name__ == "__main__":
    main()
