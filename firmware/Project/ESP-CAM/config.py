"""PlantGuard ESP32-CAM configuration.

Change credentials before deploying. Keeping settings here avoids scattering
board-specific constants through the capture pipeline.
"""

DEVICE_ID = "plantguard-cam-01"

WIFI_SSID = "PlantGuard"
WIFI_PASSWORD = "plantguard"
WIFI_CONNECT_TIMEOUT_MS = 15_000
WIFI_RETRY_INTERVAL_MS = 5_000

UPLOAD_URL = "http://192.168.4.1/api/v1/camera/readings"
HTTP_TIMEOUT_SECONDS = 10

CAPTURE_INTERVAL_MS = 300_000
TRIGGER_PIN = 13
TRIGGER_DEBOUNCE_MS = 250

FRAME_SIZE = "QQVGA"  # 160 x 120
EXPECTED_WIDTH = 160
EXPECTED_HEIGHT = 120
JPEG_QUALITY = 8  # Decoder quality, valid range: 1..8.
CAMERA_JPEG_QUALITY = 12  # Firmware encoder setting when supported.

LOOP_SLEEP_MS = 20

