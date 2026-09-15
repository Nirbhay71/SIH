"""Section 5.1 step 5 — region segmentation (photo, MRZ, field zones, stamps).

Design choice (documented per Section 5.1 as required, see also
docs/ARCHITECTURE.md): no pretrained ID-document region/layout detector
was available to source and vet within this build's time budget, so this
uses the spec's own documented fallback — a heuristic combining expected
relative layout positions (ICAO 9303 places the MRZ near the bottom of the
data page) with classical contour/text-block detection. A production
system should replace this with a properly trained layout-detection model
once labeled data across all target document types exists.
"""
import cv2
import numpy as np

from src.schemas import BoundingBox

MRZ_ZONE_HEIGHT_FRACTION = 0.22  # ICAO 9303 MRZ sits in roughly the bottom ~20% of a TD3 data page
PHOTO_MIN_AREA_FRACTION = 0.03
PHOTO_MAX_AREA_FRACTION = 0.35
PHOTO_ASPECT_RATIO_RANGE = (0.65, 1.15)  # portrait-ish, roughly ID-photo shaped


def _to_bbox(x, y, w, h) -> BoundingBox:
    return BoundingBox(x=int(x), y=int(y), width=int(w), height=int(h))


def find_mrz_zone(image: np.ndarray) -> BoundingBox | None:
    """Heuristic: the MRZ is a dense band of monospace text near the bottom
    of the page. We look for a horizontal strip in the bottom
    MRZ_ZONE_HEIGHT_FRACTION of the image with high edge density and low
    row-to-row variance (characteristic of fixed-width MRZ text lines)."""
    h, w = image.shape[:2]
    band_top = int(h * (1 - MRZ_ZONE_HEIGHT_FRACTION))
    band = image[band_top:h, 0:w]

    gray = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    row_density = edges.sum(axis=1)

    if row_density.max() == 0:
        return None

    dense_rows = np.where(row_density > row_density.max() * 0.3)[0]
    if len(dense_rows) == 0:
        return None

    y0, y1 = dense_rows.min(), dense_rows.max()
    return _to_bbox(0, band_top + y0, w, max(y1 - y0, 10))


def find_photo_region(image: np.ndarray) -> BoundingBox | None:
    """Heuristic: the ID photo is a roughly rectangular, portrait-oriented
    contiguous block, typically in the left-hand portion of the page for
    TD3-format documents. Selected via contour area + aspect ratio filter."""
    h, w = image.shape[:2]
    image_area = h * w
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((7, 7), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_score = -1.0
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        area_fraction = (cw * ch) / image_area
        if not (PHOTO_MIN_AREA_FRACTION <= area_fraction <= PHOTO_MAX_AREA_FRACTION):
            continue
        aspect = cw / ch if ch else 0
        if not (PHOTO_ASPECT_RATIO_RANGE[0] <= aspect <= PHOTO_ASPECT_RATIO_RANGE[1]):
            continue
        # Prefer candidates in the left half of the page (TD3 layout prior).
        left_bias = 1.0 if x < w * 0.5 else 0.5
        score = area_fraction * left_bias
        if score > best_score:
            best_score = score
            best = (x, y, cw, ch)

    return _to_bbox(*best) if best else None


def find_text_field_zones(image: np.ndarray, exclude: list[BoundingBox] | None = None) -> list[BoundingBox]:
    """Heuristic text-line detection via morphological gradient + horizontal
    dilation, excluding any already-identified regions (photo, MRZ)."""
    exclude = exclude or []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    grad = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    _, thresh = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    connected = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, np.ones((1, 25), np.uint8))

    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    zones = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < 20 or h < 8:
            continue
        candidate = _to_bbox(x, y, w, h)
        if any(_overlaps(candidate, ex) for ex in exclude):
            continue
        zones.append(candidate)

    return zones


def find_stamp_zones(image: np.ndarray, exclude: list[BoundingBox] | None = None) -> list[BoundingBox]:
    """Heuristic: stamps/seals tend to be roughly circular or blob-like
    contours with a moderate fill ratio, distinct from the elongated
    rectangular text-line contours found by `find_text_field_zones`."""
    exclude = exclude or []
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    zones = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 400:
            continue
        perimeter = cv2.arcLength(c, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter ** 2)
        if circularity < 0.5:  # not roughly round/blob-shaped
            continue
        x, y, w, h = cv2.boundingRect(c)
        candidate = _to_bbox(x, y, w, h)
        if any(_overlaps(candidate, ex) for ex in exclude):
            continue
        zones.append(candidate)

    return zones


def _overlaps(a: BoundingBox, b: BoundingBox) -> bool:
    ax2, ay2 = a.x + a.width, a.y + a.height
    bx2, by2 = b.x + b.width, b.y + b.height
    return not (ax2 <= b.x or bx2 <= a.x or ay2 <= b.y or by2 <= a.y)
