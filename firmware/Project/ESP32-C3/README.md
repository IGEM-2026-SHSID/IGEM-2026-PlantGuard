# PlantGuard ESP32-C3

Copy the top-level `.py` files to an ESP32-C3 running MicroPython, adjust
`config.py`, then boot `main.py`. Tests run on desktop Python with:

    python -m unittest discover ESP32-C3/tests -v

The access point is intentionally unauthenticated at the API layer. The Wi-Fi
password only limits association; camera reports are not cryptographically
authenticated.
