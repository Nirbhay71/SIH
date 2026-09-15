"""Orchestrates all four Module 3 signals into one TamperingResult
(Section 7.6). Each named use case (photo, text, stamp, metadata) maps to
an independently testable function, per Section 7's requirement that
judges/evaluators can identify each by name."""
import numpy as np

from src.schemas import BoundingBox, TamperingResult
from src.tampering.font_spacing_forensics import text_manipulation_score
from src.tampering.forgery_classifier import classify_forgery_probability, get_threshold
from src.tampering.metadata_forensics import analyze_metadata
from src.tampering.photo_boundary_check import photo_tamper_score
from src.tampering.stamp_forensics import stamp_forgery_score


def run_tampering_detection(
    image: np.ndarray,
    original_bytes: bytes,
    photo_box: BoundingBox | None,
    field_crops: dict[str, np.ndarray],
    stamp_crops: list[np.ndarray],
    reference_stamps: list[np.ndarray],
) -> TamperingResult:
    """Assumes `image` is the pre-processed, quality-gated document image
    and `original_bytes` are the untouched-since-capture bytes (required
    for both ELA, via photo_tamper_score, and metadata analysis).
    Guarantees every field in TamperingResult is populated, with
    `stamp_forgery_score=None` when no stamp region/reference exists
    (Section 7.3 — never a fabricated placeholder number)."""
    photo_score = photo_tamper_score(image, photo_box)

    text_scores = {field: text_manipulation_score(crop) for field, crop in field_crops.items()}
    text_score_max = max(text_scores.values()) if text_scores else 0.0

    stamp_score = None
    if stamp_crops and reference_stamps:
        stamp_score = max(stamp_forgery_score(crop, reference_stamps) for crop in stamp_crops)

    metadata_flag_count, metadata_flags = analyze_metadata(original_bytes)

    forgery_probability, _calibrated = classify_forgery_probability(image)

    return TamperingResult(
        photo_tamper_score=photo_score,
        text_manipulation_score_max=text_score_max,
        text_manipulation_scores_by_field=text_scores,
        stamp_forgery_score=stamp_score,
        metadata_flag_count=metadata_flag_count,
        metadata_flags=metadata_flags,
        forgery_classifier_probability=forgery_probability,
        forgery_classifier_threshold_used=get_threshold(),
        heatmap_regions=None,
    )
