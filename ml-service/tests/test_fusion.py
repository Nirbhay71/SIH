"""Section 10.4 / 13A — the fusion layer's non-negotiable properties:
hard gates always override Tier 2, and Tier 2 refuses a malformed/
reordered feature vector rather than silently mis-predicting."""
import pytest

from src.fusion.feature_builder import FEATURE_ORDER, build_feature_vector
from src.fusion.hard_gates import evaluate_hard_gates
from src.fusion.risk_model import FeatureVectorMismatchError, _validate_feature_vector
from src.schemas import FaceVerificationResult, IdentityDedupResult, OCRResult, TamperingResult, ValidationResult


def _clean_validation():
    return ValidationResult(
        mrz_checksum_document_number="pass",
        mrz_checksum_dob="pass",
        mrz_checksum_expiry="pass",
        mrz_checksum_composite="pass",
        format_valid=True,
        logic_consistent=True,
        cross_zone_match=True,
    )


def _clean_face():
    return FaceVerificationResult(liveness_status="passed", face_match_distance=0.2, face_match_status="match")


def test_hard_gate_fires_on_genuine_checksum_failure_regardless_of_other_signals():
    validation = _clean_validation()
    validation.mrz_checksum_document_number = "fail"  # genuine failure, not inconclusive
    face = _clean_face()

    result = evaluate_hard_gates(validation, face, IdentityDedupResult(), watchlist_hit=False)

    assert result.triggered
    assert result.reason == "mrz_checksum_failed"


def test_hard_gate_does_not_fire_on_inconclusive_low_confidence():
    validation = _clean_validation()
    validation.mrz_checksum_document_number = "inconclusive_low_confidence"
    face = _clean_face()

    result = evaluate_hard_gates(validation, face, IdentityDedupResult(), watchlist_hit=False)

    assert not result.triggered


def test_hard_gate_fires_on_watchlist_hit():
    result = evaluate_hard_gates(_clean_validation(), _clean_face(), IdentityDedupResult(), watchlist_hit=True)
    assert result.triggered
    assert result.reason == "watchlist_hit"


def test_hard_gate_fires_on_liveness_failure():
    face = FaceVerificationResult(liveness_status="failed", face_match_status="not_computed")
    result = evaluate_hard_gates(_clean_validation(), face, IdentityDedupResult(), watchlist_hit=False)
    assert result.triggered
    assert result.reason == "liveness_failed"


def test_hard_gate_clean_case_does_not_trigger():
    result = evaluate_hard_gates(_clean_validation(), _clean_face(), IdentityDedupResult(), watchlist_hit=False)
    assert not result.triggered
    assert result.reason is None


def test_feature_vector_matches_declared_order():
    ocr = OCRResult(status="ok", document_type="indian_passport", ocr_confidence_avg=0.95, ocr_confidence_min=0.9)
    tampering = TamperingResult(
        photo_tamper_score=0.1,
        text_manipulation_score_max=0.1,
        forgery_classifier_probability=0.1,
        forgery_classifier_threshold_used=0.4,
    )
    features = build_feature_vector(ocr, _clean_validation(), tampering, _clean_face(), IdentityDedupResult())
    assert list(features.keys()) == FEATURE_ORDER


def test_risk_model_refuses_malformed_feature_vector():
    manifest = {"feature_order": FEATURE_ORDER}
    reordered = {"ocr_confidence_min": 0.9, "ocr_confidence_avg": 0.95}  # wrong order/keys

    with pytest.raises(FeatureVectorMismatchError):
        _validate_feature_vector(reordered, manifest)
