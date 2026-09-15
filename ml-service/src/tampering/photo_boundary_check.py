"""Section 7.1 — Photo Replacement Detection.

Combines three signals into a single `photo_tamper_score` (0-1): boundary
artifact sharpness, lighting-direction mismatch, and localized ELA. Simple
average is used to combine them (Section 7.1 explicitly allows this
absent labeled data to learn optimal weights) — noted here as a place
calibration could improve results once real labeled data is available.
"""
import cv2
import numpy as np

from src.schemas import BoundingBox
from src.tampering.ela import compute_ela_map, region_mean_error


def boundary_artifact_score(image: np.ndarray, photo_box: BoundingBox, margin: int = 15) -> float:
    """Laplacian edge-discontinuity score along the photo boundary. A
    genuinely embossed/printed photo shows a smooth gradient transition;
    a pasted photo shows a sharper, more discontinuous edge. Normalized
    to roughly [0, 1] via a fixed empirical scale (Section 7.1 signal 1)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    x0, y0 = max(photo_box.x - margin, 0), max(photo_box.y - margin, 0)
    x1 = min(photo_box.x + photo_box.width + margin, gray.shape[1])
    y1 = min(photo_box.y + photo_box.height + margin, gray.shape[0])
    border_ring = gray[y0:y1, x0:x1].copy()

    inner_x0, inner_y0 = photo_box.x - x0, photo_box.y - y0
    border_ring[inner_y0 : inner_y0 + photo_box.height, inner_x0 : inner_x0 + photo_box.width] = 0

    laplacian = cv2.Laplacian(border_ring, cv2.CV_64F)
    raw_score = float(np.abs(laplacian).mean())
    return float(np.clip(raw_score / 50.0, 0.0, 1.0))


def lighting_direction_mismatch(image: np.ndarray, photo_box: BoundingBox) -> float:
    """Sobel-gradient dominant-direction mismatch between the photo region
    and the surrounding document background (Section 7.1 signal 2)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    photo_crop = gray[photo_box.y : photo_box.y + photo_box.height, photo_box.x : photo_box.x + photo_box.width]
    background = gray.copy()
    background[photo_box.y : photo_box.y + photo_box.height, photo_box.x : photo_box.x + photo_box.width] = 0

    photo_angle = _dominant_gradient_angle(photo_crop)
    background_angle = _dominant_gradient_angle(background)

    if photo_angle is None or background_angle is None:
        return 0.0

    diff = abs(photo_angle - background_angle)
    diff = min(diff, 360 - diff)
    return float(np.clip(diff / 180.0, 0.0, 1.0))


def _dominant_gradient_angle(gray_region: np.ndarray) -> float | None:
    if gray_region.size == 0:
        return None
    sobel_x = cv2.Sobel(gray_region, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray_region, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = np.hypot(sobel_x, sobel_y)
    if magnitude.sum() < 1e-6:
        return None
    angles = np.arctan2(sobel_y, sobel_x) * 180 / np.pi
    weighted_angle = float(np.average(angles, weights=magnitude))
    return weighted_angle % 360


def photo_tamper_score(image: np.ndarray, photo_box: BoundingBox | None) -> float:
    """Section 7.1 combined score. Returns 0.0 (no evidence, not "genuine
    proven") if no photo region was detected — a missing photo region is a
    Module 1 limitation, not tampering evidence."""
    if photo_box is None:
        return 0.0

    boundary = boundary_artifact_score(image, photo_box)
    lighting = lighting_direction_mismatch(image, photo_box)

    ela_map = compute_ela_map(image)
    photo_error = region_mean_error(ela_map, photo_box)
    full_box = BoundingBox(x=0, y=0, width=image.shape[1], height=image.shape[0])
    document_error = region_mean_error(ela_map, full_box)
    ela_ratio = float(np.clip((photo_error - document_error) / 20.0 + 0.5, 0.0, 1.0)) if document_error else 0.0

    return float(np.clip((boundary + lighting + ela_ratio) / 3.0, 0.0, 1.0))
