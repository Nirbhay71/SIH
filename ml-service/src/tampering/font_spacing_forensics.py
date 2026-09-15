"""Section 7.2 — Text Manipulation Detection (per-field character forensics).

Five sub-checks per field, each independently computed, then combined
into one `text_manipulation_score` per field. The aggregate across fields
uses the MAXIMUM, not the average (Section 7.2) — one manipulated field
must not be diluted by several genuine ones.
"""
import cv2
import numpy as np

from src.config import thresholds


def _segment_characters(field_crop: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Connected-component analysis on the thresholded field crop.
    Returns a left-to-right ordered list of (x, y, w, h) boxes."""
    gray = cv2.cvtColor(field_crop, cv2.COLOR_BGR2GRAY) if field_crop.ndim == 3 else field_crop
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w < 2 or h < 5:
            continue
        boxes.append((x, y, w, h))

    return sorted(boxes, key=lambda b: b[0])


def spacing_uniformity_score(boxes: list[tuple[int, int, int, int]]) -> float:
    """Coefficient of variation of inter-character gaps. Higher = less
    uniform spacing = more suspicious."""
    if len(boxes) < 3:
        return 0.0
    gaps = [boxes[i + 1][0] - (boxes[i][0] + boxes[i][2]) for i in range(len(boxes) - 1)]
    gaps = [g for g in gaps if g >= 0]
    if len(gaps) < 2 or np.mean(gaps) == 0:
        return 0.0
    cv = float(np.std(gaps) / np.mean(gaps))
    threshold = thresholds()["tampering"]["font_spacing_cv_max"]
    return float(np.clip(cv / (threshold * 2), 0.0, 1.0))


def baseline_alignment_score(boxes: list[tuple[int, int, int, int]]) -> float:
    """Deviation of each character's bottom edge from a fitted baseline."""
    if len(boxes) < 3:
        return 0.0
    xs = np.array([b[0] + b[2] / 2 for b in boxes])
    bottoms = np.array([b[1] + b[3] for b in boxes])
    coeffs = np.polyfit(xs, bottoms, 1)
    fitted = np.polyval(coeffs, xs)
    deviations = np.abs(bottoms - fitted)

    max_deviation = float(deviations.max())
    threshold_px = thresholds()["tampering"]["baseline_deviation_px_max"]
    return float(np.clip(max_deviation / (threshold_px * 3), 0.0, 1.0))


def font_size_uniformity_score(boxes: list[tuple[int, int, int, int]]) -> float:
    """Z-score of each character's height relative to the field's mean."""
    if len(boxes) < 3:
        return 0.0
    heights = np.array([b[3] for b in boxes])
    std = heights.std() or 1e-6
    z_scores = np.abs((heights - heights.mean()) / std)
    max_z = float(z_scores.max())
    threshold = thresholds()["tampering"]["height_zscore_max"]
    return float(np.clip(max_z / (threshold * 2), 0.0, 1.0))


def edge_sharpness_consistency_score(field_crop: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> float:
    """Per-character Laplacian sharpness compared against the field average."""
    if len(boxes) < 3:
        return 0.0
    gray = cv2.cvtColor(field_crop, cv2.COLOR_BGR2GRAY) if field_crop.ndim == 3 else field_crop

    sharpness_values = []
    for x, y, w, h in boxes:
        char_crop = gray[y : y + h, x : x + w]
        if char_crop.size == 0:
            continue
        sharpness_values.append(float(cv2.Laplacian(char_crop, cv2.CV_64F).var()))

    if len(sharpness_values) < 3:
        return 0.0

    mean_sharpness = np.mean(sharpness_values)
    std_sharpness = np.std(sharpness_values)
    if mean_sharpness == 0:
        return 0.0
    cv = std_sharpness / mean_sharpness
    return float(np.clip(cv, 0.0, 1.0))


def ink_consistency_score(field_crop: np.ndarray, boxes: list[tuple[int, int, int, int]]) -> float:
    """Per-character RGB histogram / local noise variance divergence from
    the field's overall profile."""
    if len(boxes) < 3 or field_crop.ndim != 3:
        return 0.0

    profiles = []
    for x, y, w, h in boxes:
        char_crop = field_crop[y : y + h, x : x + w]
        if char_crop.size == 0:
            continue
        profiles.append(char_crop.reshape(-1, 3).mean(axis=0))

    if len(profiles) < 3:
        return 0.0

    profiles = np.array(profiles)
    overall_mean = profiles.mean(axis=0)
    distances = np.linalg.norm(profiles - overall_mean, axis=1)
    max_distance = float(distances.max())
    return float(np.clip(max_distance / 60.0, 0.0, 1.0))


def text_manipulation_score(field_crop: np.ndarray) -> float:
    """Combines all five sub-checks (simple average, same rationale as
    Section 7.1's combination method) into one score for this field."""
    boxes = _segment_characters(field_crop)
    if len(boxes) < 3:
        return 0.0  # too few characters to assess consistency meaningfully

    scores = [
        spacing_uniformity_score(boxes),
        baseline_alignment_score(boxes),
        font_size_uniformity_score(boxes),
        edge_sharpness_consistency_score(field_crop, boxes),
        ink_consistency_score(field_crop, boxes),
    ]
    return float(np.mean(scores))
