"""Blue-channel threshold analysis and in-window photo display."""
import io
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk


class BlueDegreeAnalyzer:
    """Apply three high-pass thresholds to the blue channel."""

    def __init__(self, thresholds=(64, 128, 192)):
        if (len(thresholds) != 3 or tuple(sorted(thresholds)) != thresholds
                or any(not 0 <= threshold <= 255 for threshold in thresholds)):
            raise ValueError("thresholds must be three ascending values from 0 to 255")
        self.thresholds = thresholds

    def analyze(self, image_data):
        with Image.open(io.BytesIO(image_data)) as source:
            blue = source.convert("RGB").getchannel("B")

        width, height = blue.size
        pixel_count = width * height
        result_image = Image.new("RGB", (width * len(self.thresholds), height + 32))
        draw = ImageDraw.Draw(result_image)
        levels = []
        black = Image.new("L", blue.size, 0)

        for index, threshold in enumerate(self.thresholds):
            mask = blue.point(lambda value: 0 if value >= threshold else 255)
            panel = Image.merge("RGB", (black, black, mask))
            x_offset = index * width
            result_image.paste(panel, (x_offset, 32))
            draw.text((x_offset + 8, 9), "Blue >= %d" % threshold, fill="white")
            selected_pixels = mask.histogram()[255]
            levels.append({
                "threshold": threshold,
                "selected_pixels": selected_pixels,
                "ratio": selected_pixels / pixel_count,
            })

        return {"image": result_image, "levels": levels}


class PILPhotoViewer:
    """Display each analyzed frame in one reusable Pillow-backed window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PlantGuard Blue Analysis")
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)
        self.label = tk.Label(self.root)
        self.label.pack()
        self.photo = None
        self.root.withdraw()

    def show(self, image):
        self.photo = ImageTk.PhotoImage(image=image, master=self.root)
        self.label.configure(image=self.photo)
        self.root.deiconify()
        self.root.update_idletasks()
        self.root.update()
"""Blue-channel threshold analysis and a reusable Pillow image window."""
import io
import tkinter as tk

from PIL import Image, ImageTk

DEFAULT_BLUE_THRESHOLDS = (64, 128, 192)


class BlueLevelAnalyzer:
    def __init__(self, thresholds=DEFAULT_BLUE_THRESHOLDS):
        if (len(thresholds) != 3 or
                any(not 0 < threshold <= 255 for threshold in thresholds) or
                tuple(sorted(set(thresholds))) != tuple(thresholds)):
            raise ValueError("thresholds must be three increasing values in 1..255")
        self.thresholds = tuple(thresholds)

    def analyze(self, image_data):
        with Image.open(io.BytesIO(image_data)) as source:
            original = source.convert("RGB")
            blue_channel = original.getchannel("B")

        width, height = blue_channel.size
        result = Image.new("RGB", (width * (len(self.thresholds) + 1), height + 32))
        draw = ImageDraw.Draw(result)
        result.paste(original, (0, 32))
        draw.text((8, 9), "Original", fill="white")
        for index, threshold in enumerate(self.thresholds):
            mask = blue_channel.point(
                lambda value, cutoff=threshold: 0 if value >= cutoff else 255)
            panel = Image.merge("RGB", (mask, mask, mask))
            x_offset = (index + 1) * width
            result.paste(panel, (x_offset, 32))
            draw.text((x_offset + 8, 9), "Blue >= %d" % threshold, fill="white")
        return result


class BluePhotoWindow:
    def __init__(self, analyzer=None):
        self.analyzer = analyzer or BlueLevelAnalyzer()
        self.root = tk.Tk()
        self.root.title("PlantGuard Blue Levels")
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)
        self.image_label = tk.Label(self.root)
        self.image_label.pack()
        self.photo = None
        self.root.withdraw()

    def show(self, image_data):
        preview = self.analyzer.analyze(image_data)
        preview.thumbnail((1200, 800), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(preview)
        self.image_label.configure(image=self.photo)
        self.root.deiconify()
        self.process_events()

    def process_events(self):
        self.root.update_idletasks()
        self.root.update()