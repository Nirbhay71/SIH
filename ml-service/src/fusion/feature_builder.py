"""Section 9.1 — builds the fixed-order Tier 2 feature vector.

Feature order is authoritative and must match `FEATURE_ORDER` exactly, in
both training (`training/extract_features.py`) and inference
(`src/fusion/risk_model.py`) — the trained model's feature manifest
(Section 9.3) is validated against this list at load time.

Missing signals (e.g. `stamp_forgery_score` when no stamp region was
found) are represented as NaN plus an explicit `<feature>_missing`
indicator column, never as a fabricated numeric value that could be
misread as a real measurement (Section 9.1).
"""
import math

from src.schemas import FaceVerificationResult, IdentityDedupResult, OCRResult, TamperingResult, ValidationResult

BASE_FEATURES = [
    "ocr_confidence_avg",
    "ocr_confidence_min",
    "format_valid",
    "logic_consistent",
    "cross_zone_match",
    "photo_tamper_score",
    "text_manipulation_score_max",
    "stamp_forgery_score",
    "metadata_flag_count",
    "forgery_classifier_probability",
    "face_match_distance",
    "liveness_score",
    "duplicate_identity_flag",
]

MISSING_INDICATOR_FEATURES = ["cross_zone_match", "stamp_forgery_score", "face_match_distance", "liveness_score"]

FEATURE_ORDER = BASE_FEATURES + [f"{f}_missing" for f in MISSING_INDICATOR_FEATURES]


def _bool_to_float(value: bool | None) -> float:
    if value is None:
        return math.nan
    return 1.0 if value else 0.0


def build_feature_vector(
    ocr_result: OCRResult,
    validation_result: ValidationResult,
    tampering_result: TamperingResult,
    face_result: FaceVerificationResult,
    identity_result: IdentityDedupResult | None,
) -> dict[str, float]:
    """Returns a dict keyed exactly by FEATURE_ORDER. Every caller (training
    and inference) must serialize this dict in FEATURE_ORDER, never in
    dict-iteration order, to guarantee column alignment."""
    identity_result = identity_result or IdentityDedupResult()

    values: dict[str, float] = {
        "ocr_confidence_avg": ocr_result.ocr_confidence_avg,
        "ocr_confidence_min": ocr_result.ocr_confidence_min,
        "format_valid": _bool_to_float(validation_result.format_valid),
        "logic_consistent": _bool_to_float(validation_result.logic_consistent),
        "cross_zone_match": _bool_to_float(validation_result.cross_zone_match),
        "photo_tamper_score": tampering_result.photo_tamper_score,
        "text_manipulation_score_max": tampering_result.text_manipulation_score_max,
        "stamp_forgery_score": tampering_result.stamp_forgery_score
        if tampering_result.stamp_forgery_score is not None
        else math.nan,
        "metadata_flag_count": float(tampering_result.metadata_flag_count),
        "forgery_classifier_probability": tampering_result.forgery_classifier_probability,
        "face_match_distance": face_result.face_match_distance if face_result.face_match_distance is not None else math.nan,
        "liveness_score": face_result.liveness_score if face_result.liveness_score is not None else math.nan,
        "duplicate_identity_flag": _bool_to_float(identity_result.duplicate_identity_flag),
    }

    for feature in MISSING_INDICATOR_FEATURES:
        values[f"{feature}_missing"] = 1.0 if math.isnan(values[feature]) else 0.0

    return {k: values[k] for k in FEATURE_ORDER}
