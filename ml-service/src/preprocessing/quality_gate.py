"""Section 5.1 step 4 — blur/glare quality gating.

Thresholds live in config/thresholds.yaml (`preprocessing.*`). See
docs/THRESHOLD_JUSTIFICATIONS.md for how they were derived and their
current calibration status — as shipped, both are ILLUSTRATIVE (Section
13E), not yet calibrated against a real labeled sample set.
"""
import cv2
import numpy as np

from src.config import thresholds


def blur_score(image: np.ndarray) -> float:
    """Variance of the Laplacian of the grayscale image. Lower = blurrier."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def glare_score(image: np.ndarray) -> float:
    """Fraction of pixels above a near-white saturation threshold."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    near_white = (hsv[:, :, 1] < 30) & (hsv[:, :, 2] > 240)
    return float(np.count_nonzero(near_white) / near_white.size)


def check_quality(image: np.ndarray) -> tuple[bool, str | None, float | None]:
    """Returns (passed, reason_if_failed, score_if_failed).

    Blur is checked before glare so the more common failure mode (a bad
    camera focus) is reported first when both would fail.
    """
    cfg = thresholds()["preprocessing"]

    blur = blur_score(image)
    if blur < cfg["blur_variance_min"]:
        return False, "blur", blur

    glare = glare_score(image)
    if glare > cfg["glare_pixel_fraction_max"]:
        return False, "glare", glare

    return True, None, None
