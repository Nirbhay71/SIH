"""Section 5.1 step 4 — blur/glare/resolution quality signals.

Thresholds live in config/thresholds.yaml (`preprocessing.*`). See
docs/THRESHOLD_JUSTIFICATIONS.md for how they were derived and their
current calibration status — as shipped, all are ILLUSTRATIVE (Section
13E), not yet calibrated against a real labeled sample set.

Design note (changed after real-world testing): this used to hard-reject
the whole upload on the first failing check, before OCR ever ran. That
repeatedly produced false positives on real, legible photos — a
composite/multi-page image (a real, distinct problem) and an ordinary
photo with some blank white page background pushing the glare fraction
over threshold (not actually a problem — the document text itself was
perfectly readable) both got the same hard "rejected, try again" wall,
even though the second case's data was extractable. Officers reviewing
flagged real-world documents need to see what OCR *could* extract, with
quality concerns as a visible warning, not have extraction refused
outright — a human in the loop should decide whether a poor-quality
result is usable, not a heuristic threshold no one has calibrated yet.
So: only a genuinely unusable image (near-zero pixels — would crash or
produce meaningless output no matter what) is still hard-rejected.
Everything else always proceeds to OCR/tampering/validation, with any
quality concerns attached as non-blocking `quality_flags`.
"""
import cv2
import numpy as np

from src.config import thresholds

# True hard floor — below this, most OpenCV/OCR calls either crash or
# produce meaningless output; there's no informative extraction to attempt.
# Deliberately much lower than the old "reject if <400px" heuristic, which
# was rejecting perfectly attempt-able (if imperfect) real-world photos.
ABSOLUTE_MIN_DIMENSION_PX = 40


def blur_score(image: np.ndarray) -> float:
    """Variance of the Laplacian of the grayscale image. Lower = blurrier."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def glare_score(image: np.ndarray) -> float:
    """Fraction of pixels above a near-white saturation threshold."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    near_white = (hsv[:, :, 1] < 30) & (hsv[:, :, 2] > 240)
    return float(np.count_nonzero(near_white) / near_white.size)


def aspect_ratio(image: np.ndarray) -> float:
    h, w = image.shape[:2]
    return w / h if h else 0.0


def check_quality(image: np.ndarray) -> tuple[bool, str | None, float | None]:
    """Returns (hard_blocked, reason_if_blocked, score_if_blocked).

    `hard_blocked=True` only for the near-zero-pixel degenerate case (see
    module docstring) — everything else returns (True, None, None) and
    relies on `quality_flags()` below for non-blocking warnings instead.
    """
    h, w = image.shape[:2]
    if min(h, w) < ABSOLUTE_MIN_DIMENSION_PX:
        return False, "low_resolution", float(min(h, w))
    return True, None, None


def quality_flags(image: np.ndarray) -> list[str]:
    """Non-blocking quality warnings (e.g. "low_resolution", "blur",
    "glare"). Always computed and attached to the OCR result rather than
    gating extraction — see module docstring."""
    cfg = thresholds()["preprocessing"]
    flags = []

    h, w = image.shape[:2]
    if min(h, w) < cfg["min_dimension_px"]:
        flags.append("low_resolution")

    if blur_score(image) < cfg["blur_variance_min"]:
        flags.append("blur")

    if glare_score(image) > cfg["glare_pixel_fraction_max"]:
        flags.append("glare")

    return flags
