"""Optional EXPERIMENTAL blue-region detector for PlantGuard PC.

IMPORTANT: This is NOT a validated bead-concentration or drought algorithm.
Its 'blue_value' is the mean relative RGB blue dominance of selected pixels.
Only enable after testing on the team's own photographs and calibration targets.
No packages beyond the repository's existing Pillow dependency are needed.
"""

import argparse
from collections import deque
import json

from PIL import Image

# Pillow hue is 0..255. About 205..275 degrees includes strong blue.
DEFAULT_HUE_MIN = 145
DEFAULT_HUE_MAX = 195
DEFAULT_SATURATION_MIN = 80
DEFAULT_BRIGHTNESS_MIN = 40
DEFAULT_BLUE_ADVANTAGE = 30


def parse_roi(value):
    """Parse normalized ROI x0,y0,x1,y1 (top-left to bottom-right)."""
    try:
        roi = tuple(float(part) for part in value.split(","))
    except (ValueError, AttributeError) as exc:
        raise ValueError("ROI must be x0,y0,x1,y1 in normalized 0..1 units") from exc
    if len(roi) != 4 or not (0 <= roi[0] < roi[2] <= 1 and
                              0 <= roi[1] < roi[3] <= 1):
        raise ValueError("ROI must satisfy 0<=x0<x1<=1 and 0<=y0<y1<=1")
    return roi


def analyze_blue(image, *, roi=(0.0, 0.0, 1.0, 1.0), min_region_pixels=16,
                 return_mask=False):
    """Segment blue-looking connected regions; return EXPERIMENTAL measurements.

    Blue candidates must pass HSV hue/saturation/brightness thresholds and
    exceed red AND green by >=30 on the 0..255 RGB scale. Only 4-connected
    components with >=min_region_pixels are counted (JPEG speckles are ignored).

    blue_value = mean((B - max(R, G)) / 255) over selected pixels in [0, 1].
    This is a camera-dependent image metric, NOT pigment concentration.
    Use an ROI to exclude blue objects unrelated to the indicator beads.
    """
    if not isinstance(min_region_pixels, int) or isinstance(min_region_pixels, bool) or min_region_pixels < 1:
        raise ValueError("min_region_pixels must be a positive integer")
    if len(roi) != 4 or not (0 <= roi[0] < roi[2] <= 1 and
                              0 <= roi[1] < roi[3] <= 1):
        raise ValueError("invalid normalized ROI")
    rgb = image.convert("RGB")
    hsv = rgb.convert("HSV")
    width, height = rgb.size
    if width < 1 or height < 1:
        raise ValueError("empty image")

    # Normalized ROI in source-image coordinates. For small images, ceil the
    # right/bottom edges so nonempty ROIs remain meaningful.
    import math
    x0 = min(width - 1, int(roi[0] * width))
    y0 = min(height - 1, int(roi[1] * height))
    x1 = min(width, max(x0 + 1, int(math.ceil(roi[2] * width))))
    y1 = min(height, max(y0 + 1, int(math.ceil(roi[3] * height))))
    pixels, hsv_pixels = rgb.load(), hsv.load()
    candidates = bytearray(width * height)
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = pixels[x, y]
            h, s, v = hsv_pixels[x, y]
            if (DEFAULT_HUE_MIN <= h <= DEFAULT_HUE_MAX and
                    s >= DEFAULT_SATURATION_MIN and
                    v >= DEFAULT_BRIGHTNESS_MIN and
                    b >= max(r, g) + DEFAULT_BLUE_ADVANTAGE):
                candidates[y * width + x] = 1

    # Filter tiny blue speckles and keep independent blue regions. Pure Python
    # is sufficient for the 160x120 camera resolution in this prototype.
    visited = bytearray(width * height)
    kept = bytearray(width * height)
    kept_count = 0
    total_dominance = 0
    region_count = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            start = y * width + x
            if not candidates[start] or visited[start]:
                continue
            queue = deque([start])
            visited[start] = 1
            component = []
            while queue:
                index = queue.popleft()
                component.append(index)
                cy, cx = divmod(index, width)
                for nx, ny in ((cx - 1, cy), (cx + 1, cy),
                               (cx, cy - 1), (cx, cy + 1)):
                    if x0 <= nx < x1 and y0 <= ny < y1:
                        nxt = ny * width + nx
                        if candidates[nxt] and not visited[nxt]:
                            visited[nxt] = 1
                            queue.append(nxt)
            if len(component) < min_region_pixels:
                continue
            region_count += 1
            for index in component:
                cy, cx = divmod(index, width)
                r, g, b = pixels[cx, cy]
                total_dominance += (b - max(r, g)) / 255.0
                kept[index] = 255
            kept_count += len(component)
    area = (x1 - x0) * (y1 - y0)
    result = {
        "blue_value": round(total_dominance / kept_count, 4) if kept_count else None,
        "selected_pixels": kept_count,
        "blue_area_fraction": round(kept_count / area, 4),
        "blue_region_count": region_count,
        "analysis_status": "experimental_unvalidated" if kept_count else "no_blue_region",
        "analysis_roi": [x0, y0, x1, y1],
    }
    if return_mask:
        mask = Image.frombytes("L", (width, height), bytes(kept))
        return result, mask
    return result


def main():
    parser = argparse.ArgumentParser(description="Preview PlantGuard experimental blue detection")
    parser.add_argument("--image", required=True, help="Local photo/JPEG path")
    parser.add_argument("--roi", type=parse_roi, default=(0, 0, 1, 1),
                        help="Normalized x0,y0,x1,y1; e.g. 0.2,0.2,0.8,0.8")
    parser.add_argument("--min-region-pixels", type=int, default=16)
    parser.add_argument("--mask", help="Optional black/white PNG output for visual inspection")
    args = parser.parse_args()
    with Image.open(args.image) as image:
        result, mask = analyze_blue(image, roi=args.roi,
                                    min_region_pixels=args.min_region_pixels,
                                    return_mask=True)
    print(json.dumps(result, indent=2))
    if args.mask:
        mask.save(args.mask)
        print("Mask saved to %s (white=selected blue pixels)" % args.mask)


if __name__ == "__main__":
    main()
