"""Replaceable pixel-analysis interface.

No blue-region/concentration formula has been approved. This implementation
therefore only validates the streaming integration and counts pixels.
"""


class BlueAnalyzer:
    def __init__(self):
        self.reset()

    def reset(self):
        self.decoded_pixels = 0
        self.selected_pixels = 0

    def consume(self, x, y, rgb):
        """Consume one ``0xRRGGBB`` pixel emitted by JPEGdecoder."""
        self.decoded_pixels += 1

    def result(self):
        return {
            "blue_value": None,
            "status": "algorithm_not_configured",
            "decoded_pixels": self.decoded_pixels,
            "selected_pixels": self.selected_pixels,
        }

