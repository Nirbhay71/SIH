"""Section 5.1 step 3 — deskew via minAreaRect, with Hough-line fallback."""
import cv2
import numpy as np

MAX_CORRECTION_ANGLE_DEG = 45.0


def estimate_skew_angle(image: np.ndarray) -> float:
    """Estimates the dominant skew angle in degrees using cv2.minAreaRect on
    thresholded content, falling back to a Hough line transform if no
    usable contour is found. Returns 0.0 if no signal is detectable."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(thresh)

    if coords is not None and len(coords) > 50:
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        if angle < -45:
            angle = 90 + angle
        return float(angle)

    return _hough_fallback_angle(gray)


def _hough_fallback_angle(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=150)
    if lines is None:
        return 0.0

    angles = []
    for line in lines[:50]:
        _, theta = line[0]
        angle_deg = (theta * 180 / np.pi) - 90
        angles.append(angle_deg)

    return float(np.median(angles)) if angles else 0.0


def deskew(image: np.ndarray) -> tuple[np.ndarray, bool]:
    """Returns (corrected_image, skipped_large_angle).

    A detected angle beyond MAX_CORRECTION_ANGLE_DEG likely indicates a
    boundary-detection error rather than a genuinely rotated document
    (Section 5.1 step 3) — in that case the original image is returned
    unmodified and `skipped_large_angle` is True.
    """
    angle = estimate_skew_angle(image)
    if abs(angle) > MAX_CORRECTION_ANGLE_DEG:
        return image, True

    if abs(angle) < 0.1:
        return image, False

    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated, False
