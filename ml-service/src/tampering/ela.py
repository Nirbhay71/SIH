"""Section 7.2 — Error Level Analysis (ELA).

Critical precondition (Section 12A): the `image` passed here must be the
untouched-since-capture working image, never re-saved as JPEG since
Module 1's format normalization step. Any lossy re-encoding in between
destroys the exact signal ELA depends on.
"""
import io

import cv2
import numpy as np
from PIL import Image

from src.config import thresholds
from src.schemas import BoundingBox

ELA_JPEG_QUALITY = 90
WINDOW_SIZE = 32


def compute_ela_map(image: np.ndarray) -> np.ndarray:
    """Re-saves `image` at ELA_JPEG_QUALITY and returns the per-pixel
    grayscale absolute difference against the original."""
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb)

    buf = io.BytesIO()
    pil_image.save(buf, "JPEG", quality=ELA_JPEG_QUALITY)
    buf.seek(0)
    recompressed = np.array(Image.open(buf).convert("RGB"))

    diff = cv2.absdiff(rgb, recompressed)
    return cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY).astype(np.float64)


def find_anomalous_regions(ela_map: np.ndarray, window: int = WINDOW_SIZE) -> list[tuple[BoundingBox, float]]:
    """Sliding-window scan: flags windows where the local mean error level
    exceeds global_mean + z * global_std (Section 7.2)."""
    z = thresholds()["tampering"]["ela_zscore_threshold"]
    global_mean = float(ela_map.mean())
    global_std = float(ela_map.std()) or 1e-6
    threshold = global_mean + z * global_std

    h, w = ela_map.shape
    anomalies = []
    for y in range(0, h - window, window):
        for x in range(0, w - window, window):
            local_mean = float(ela_map[y : y + window, x : x + window].mean())
            if local_mean > threshold:
                anomalies.append((BoundingBox(x=x, y=y, width=window, height=window), local_mean))

    return anomalies


def region_mean_error(ela_map: np.ndarray, box: BoundingBox) -> float:
    """Mean ELA error within a bounding box, used to compare a specific
    region (e.g. the photo) against the rest of the document (Section 7.1
    signal 3)."""
    crop = ela_map[box.y : box.y + box.height, box.x : box.x + box.width]
    if crop.size == 0:
        return 0.0
    return float(crop.mean())
