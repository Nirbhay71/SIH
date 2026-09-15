"""Section 8.2 — liveness/anti-spoofing check.

Runs BEFORE any face match is attempted, on the live-capture image only
(never the document photo, which is expected to be a static image by
definition). A failed liveness check must independently and immediately
push the fusion layer's hard gate (Section 9.1) — see
src/fusion/hard_gates.py — regardless of what a face-match score would
otherwise show.
"""
import logging

import numpy as np

from src.config import thresholds

logger = logging.getLogger("src.face")


class LivenessUnavailableError(Exception):
    """Raised when DeepFace's anti-spoofing model is not installed. Callers
    must treat this as `liveness_status: "not_applicable"`, never as a
    silent pass (Section 11: fail closed, not open)."""


def check_liveness(live_capture: np.ndarray) -> tuple[str, float | None]:
    """Returns (status, score) where status is "passed", "failed", or
    raises LivenessUnavailableError if the dependency is missing."""
    try:
        from deepface import DeepFace
    except ImportError as exc:
        raise LivenessUnavailableError("deepface is not installed in this environment.") from exc

    try:
        faces = DeepFace.extract_faces(live_capture, anti_spoofing=True, enforce_detection=True)
    except ValueError as exc:
        # DeepFace raises ValueError when no face is detected at all.
        logger.warning("No face detected in live capture during liveness check: %s", exc)
        return "failed", 0.0

    if not faces:
        return "failed", 0.0

    face = faces[0]
    is_real = face.get("is_real", False)
    score = float(face.get("antispoof_score", 0.0))

    threshold = thresholds()["face"]["liveness_score_min"]
    passed = bool(is_real) and score >= threshold
    return ("passed" if passed else "failed"), score
