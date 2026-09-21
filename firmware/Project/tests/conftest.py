import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
C3 = ROOT / "ESP32-C3"
CAM = ROOT / "ESP-CAM"

# Tests import one firmware tree at a time.  C3 comes first because its app
# uses unqualified local imports; CAM modules under test have unique names.
for path in (str(CAM), str(C3)):
    if path not in sys.path:
        sys.path.insert(0, path)

