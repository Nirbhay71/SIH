"""Section 7.3 — Stamp Forgery Detection.

Uses ORB (patent-unencumbered, faster, sufficient for small axis-aligned
stamp regions) rather than SIFT, per Section 7.3's explicit reasoning.

Because the reference stamp library here is necessarily small and
synthetic (a production system would need an authorized reference library
from issuing authorities — documented in docs/LIMITATIONS.md), a missing
or inconclusive stamp check must be a `None`/missing-indicator feature in
the fusion layer, never a hard gate or heavily-weighted signal on its own
(Section 7.3, enforced by `stamp_forgery_score: float | None` in
TamperingResult and the `_missing` indicator in the feature builder).
"""
import cv2
import numpy as np

from src.schemas import BoundingBox

LOWE_RATIO = 0.75


def _orb_descriptors(image: np.ndarray):
    orb = cv2.ORB_create(nfeatures=500)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    return keypoints, descriptors


def match_quality(image_a: np.ndarray, image_b: np.ndarray) -> float:
    """Proportion of ORB keypoint matches passing Lowe's ratio test,
    normalized to [0, 1]. Used both for genuine/forged geometric-distortion
    comparison against a reference stamp, and for duplicate-pattern
    detection across stamps in the same session."""
    _, desc_a = _orb_descriptors(image_a)
    _, desc_b = _orb_descriptors(image_b)

    if desc_a is None or desc_b is None or len(desc_a) < 2 or len(desc_b) < 2:
        return 0.0

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    matches = bf.knnMatch(desc_a, desc_b, k=2)

    good_matches = 0
    for pair in matches:
        if len(pair) < 2:
            continue
        m, n = pair
        if m.distance < LOWE_RATIO * n.distance:
            good_matches += 1

    total_possible = min(len(desc_a), len(desc_b))
    return float(good_matches / total_possible) if total_possible else 0.0


def stamp_forgery_score(
    stamp_crop: np.ndarray,
    reference_stamps: list[np.ndarray],
    other_session_stamps: list[np.ndarray] | None = None,
) -> float:
    """Combines: (1) best geometric/ink match quality against a small
    reference library (higher match = more genuine-looking, so we invert
    it into a "distortion" signal), and (2) duplicate-pattern detection
    against other stamps processed in the same session (Section 7.3) — a
    forger reusing one scanned stamp image across documents produces an
    unusually HIGH match here, which is itself suspicious.

    Callers must treat the return value as missing (None) rather than
    calling this function at all when no reference library or no other-
    session stamps exist to compare against (Section 7.3) — this function
    only computes a score given at least one comparison target.
    """
    other_session_stamps = other_session_stamps or []

    best_reference_match = max((match_quality(stamp_crop, ref) for ref in reference_stamps), default=0.0)
    distortion_score = 1.0 - best_reference_match

    duplicate_score = max((match_quality(stamp_crop, other) for other in other_session_stamps), default=0.0)

    return float(np.clip(max(distortion_score, duplicate_score), 0.0, 1.0))
