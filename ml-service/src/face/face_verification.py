"""Section 8.1, 8.3, 8.4 — face detection, matching, and age-gap tolerance.

Mandatory (Section 8.3, 12A): never use DeepFace/ArcFace's generic default
cosine-distance threshold (~0.68) as-is. That default is derived from
generic face-to-face benchmarks, not document-photo-vs-live-selfie
matching specifically, which published research shows performs
measurably worse under the generic threshold. The recalibrated threshold
lives in config/thresholds.yaml (`face.match_distance_threshold`) —
see docs/THRESHOLD_JUSTIFICATIONS.md and `training/calibrate_thresholds.py`
for how it was derived (or, in this build, why it is still a placeholder
pending real matched/mismatched pair data — see that doc for current
status).
"""
import logging

import numpy as np

from src.config import thresholds
from src.schemas import FaceVerificationResult

logger = logging.getLogger("src.face")


class FaceVerificationUnavailableError(Exception):
    pass


def _get_embedding(image: np.ndarray) -> list[float] | None:
    from deepface import DeepFace

    try:
        result = DeepFace.represent(
            image, model_name="ArcFace", detector_backend="retinaface", enforce_detection=True
        )
    except ValueError:
        return None  # no face detected — an expected, typed outcome, not an error

    if not result:
        return None
    return result[0]["embedding"]


def cosine_distance(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1e-9
    similarity = float(np.dot(va, vb) / denom)
    return 1.0 - similarity


def verify_faces(document_photo: np.ndarray, live_capture: np.ndarray, liveness_status: str) -> FaceVerificationResult:
    """Assumes `liveness_status` has already been computed by
    src/face/liveness.py — Section 8.2 requires liveness to run first and
    a failed liveness check to bypass face-match computation entirely."""
    if liveness_status == "failed":
        return FaceVerificationResult(
            liveness_status="failed",
            face_match_status="not_computed",
            threshold_used=thresholds()["face"]["match_distance_threshold"],
        )

    try:
        doc_embedding = _get_embedding(document_photo)
        live_embedding = _get_embedding(live_capture)
    except ImportError as exc:
        raise FaceVerificationUnavailableError("deepface is not installed in this environment.") from exc

    face_cfg = thresholds()["face"]
    threshold = face_cfg["match_distance_threshold"]
    margin = face_cfg["borderline_margin"]

    if doc_embedding is None or live_embedding is None:
        return FaceVerificationResult(
            liveness_status=liveness_status,
            face_match_status="not_computed",
            threshold_used=threshold,
        )

    distance = cosine_distance(doc_embedding, live_embedding)

    if abs(distance - threshold) <= margin:
        status = "needs_officer_review"
    elif distance <= threshold:
        status = "match"
    else:
        status = "no_match"

    return FaceVerificationResult(
        liveness_status=liveness_status,
        face_match_distance=distance,
        face_match_status=status,
        threshold_used=threshold,
    )
