"""Extract the nearest blue component inside a central region."""
from dataclasses import dataclass
import io
import math

from PIL import Image, ImageDraw


def pixel_data(image):
    # Pillow 12.1 renamed getdata; retain compatibility with Pillow 10/11.
    if hasattr(image, "get_flattened_data"):
        return image.get_flattened_data()
    return image.getdata()


@dataclass(frozen=True)
class Settings:
    roi_ratio: float = 0.6
    hue_min: float = 190
    hue_max: float = 260
    saturation_min: float = 0.25
    brightness_min: float = 0.15
    min_pixels: int = 9

    def __post_init__(self):
        if not (0 < self.roi_ratio <= 1 and
                0 <= self.hue_min < self.hue_max <= 360 and
                0 <= self.saturation_min <= 1 and
                0 <= self.brightness_min <= 1):
            raise ValueError("invalid ROI or HSV thresholds")
        if isinstance(self.min_pixels, bool) or not isinstance(self.min_pixels, int) or self.min_pixels < 1:
            raise ValueError("min_pixels must be a positive integer")


class BlueAnalyzer:
    def __init__(self, settings=None):
        self.settings = settings or Settings()

    def analyze(self, data):
        with Image.open(io.BytesIO(data)) as source:
            width, height = source.size
            if width * height > 4_000_000:
                raise ValueError("image exceeds 4 million pixels")
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            image = source.convert("RGB")
        cfg = self.settings
        rw, rh = max(1, round(width * cfg.roi_ratio)), max(1, round(height * cfg.roi_ratio))
        left, top = (width - rw) // 2, (height - rh) // 2
        roi = (left, top, left + rw, top + rh)
        crop = image.crop(roi)
        rgb = list(pixel_data(crop))
        candidates = bytearray(rw * rh)
        for i, (h, s, v) in enumerate(pixel_data(crop.convert("HSV"))):
            r, g, b = rgb[i]
            candidates[i] = (cfg.hue_min <= h * 360 / 255 <= cfg.hue_max and
                             s / 255 >= cfg.saturation_min and
                             v / 255 >= cfg.brightness_min and b > max(r, g))

        # Four-connected components. Nearest actual pixel wins; size breaks ties.
        cx, cy = (width - 1) / 2 - left, (height - 1) / 2 - top
        selected, best_key = [], (math.inf, 0)
        for seed in range(len(candidates)):
            if not candidates[seed]:
                continue
            candidates[seed] = 0
            stack, component, distance = [seed], [], math.inf
            while stack:
                index = stack.pop()
                component.append(index)
                x, y = index % rw, index // rw
                distance = min(distance, (x - cx) ** 2 + (y - cy) ** 2)
                neighbors = []
                if x: neighbors.append(index - 1)
                if x + 1 < rw: neighbors.append(index + 1)
                if y: neighbors.append(index - rw)
                if y + 1 < rh: neighbors.append(index + rw)
                for neighbor in neighbors:
                    if candidates[neighbor]:
                        candidates[neighbor] = 0
                        stack.append(neighbor)
            key = (distance, -len(component))
            if len(component) >= cfg.min_pixels and key < best_key:
                selected, best_key = component, key

        metrics = {
            "width": width, "height": height, "decoded_pixels": width * height,
            "selected_pixels": len(selected), "blue_value": None,
            "analysis_status": "no_blue_region", "error": "no_blue_region",
            "roi": list(roi), "region_bbox": None,
            "blue_method": "mean_blue_dominance_percent_v1",
        }
        mask_data = bytearray(rw * rh)
        if selected:
            values = [(rgb[i][2] - max(rgb[i][0], rgb[i][1])) / rgb[i][2]
                      for i in selected]
            xs, ys = [i % rw for i in selected], [i // rw for i in selected]
            metrics.update(
                blue_value=round(100 * math.fsum(values) / len(values), 4),
                analysis_status="ok", error=None,
                region_bbox=[left + min(xs), top + min(ys),
                             left + max(xs) + 1, top + max(ys) + 1],
            )
            for i in selected:
                mask_data[i] = 255
        mask = Image.new("L", image.size)
        mask.paste(Image.frombytes("L", (rw, rh), bytes(mask_data)), (left, top))
        return metrics, image, mask


def make_preview(metrics, image, mask):
    """Original with ROI / region bounds alongside the extracted blue pixels."""
    original = image.copy()
    draw = ImageDraw.Draw(original)
    x0, y0, x1, y1 = metrics["roi"]
    draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline="yellow", width=2)
    if metrics["region_bbox"]:
        x0, y0, x1, y1 = metrics["region_bbox"]
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline="lime", width=2)
    extracted = Image.new("RGB", image.size, "black")
    extracted.paste(image, mask=mask)
    width, height = image.size
    preview = Image.new("RGB", (width * 2, height + 32), "#202020")
    preview.paste(original, (0, 32))
    preview.paste(extracted, (width, 32))
    draw = ImageDraw.Draw(preview)
    draw.text((6, 8), "Original / central ROI", fill="white")
    draw.text((width + 6, 8), "Blue: %s / pixels: %d" % (
        metrics["blue_value"], metrics["selected_pixels"]), fill="white")
    return preview
