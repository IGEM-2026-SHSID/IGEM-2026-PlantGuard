# PlantGuard PC JPEG receiver

The ESP32-CAM sends one frame per TCP connection using this wire format:

`PGJ1` + 4-byte metadata length + 4-byte JPEG length + JSON metadata + JPEG.

Both lengths are unsigned, big-endian integers. The PC validates and decodes
the JPEG, posts the resulting report to the C3, and returns `01` on success or
`00` on failure. The CAM only discards a frame after receiving `01`.

## Run on Windows

1. Connect the computer to the C3 hotspot `PlantGuard` (`plantguard`).
2. Run `ipconfig` and note the Wi-Fi IPv4 address.
3. Set `PC_HOST` in `ESP-CAM/main_pc.py` to that address.
4. Allow inbound TCP port 8765 in Windows Firewall when prompted.
5. Install and start the receiver:

```powershell
py -m pip install -r PC_Server/requirements.txt
py PC_Server/server.py
```

Upload `ESP-CAM/main_pc.py` to the board as `/main.py`, together with
`jpeg_transport.py`, `reporting.py`, `scheduler.py`, and `wifi_manager.py`.
The old `JPEGdecoder.py`, `urequests.py`, `camera_pipeline.py`, and
`http_client.py` are not needed by this entry point.

The receiver currently performs complete RGB decoding and reports dimensions
and pixel count. It deliberately retains `algorithm_not_configured` and a null
`blue_value`, because no blue-region/concentration formula is defined yet.
