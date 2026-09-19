from app.hashchain import compute_hash
from app.ml_adapter import adapt_tampering
from app.risk import (
    WEIGHT_FACE_MISMATCH, WEIGHT_IMPOSSIBLE_TRAVEL, WEIGHT_LIVENESS_FAILED,
    WEIGHT_SUSPICIOUS_TRAVEL_DIRECTION, WEIGHT_TAMPERING, WEIGHT_VALIDATION_FAILURES,
    compute_risk_score,
)


def _score(**kw):
    base = dict(validation_failure_count=0, tampering_score=0.0, face_similarity_score=0.9, watchlist_match=False,
                travel_direction_flag="ok", impossible_travel_flag=False, liveness_passed=True)
    base.update(kw)
    return compute_risk_score(**base)


def test_weights_sum_to_exactly_100():
    assert (WEIGHT_TAMPERING + WEIGHT_FACE_MISMATCH + WEIGHT_LIVENESS_FAILED + WEIGHT_VALIDATION_FAILURES
            + WEIGHT_SUSPICIOUS_TRAVEL_DIRECTION + WEIGHT_IMPOSSIBLE_TRAVEL) == 100


def test_worst_case_weighted_score_cannot_exceed_100():
    r = _score(validation_failure_count=9, tampering_score=1.0, face_similarity_score=0.0,
               travel_direction_flag="suspicious", impossible_travel_flag=True, liveness_passed=False)
    assert r["risk_score"] == 100 and r["scoring_model"] == "weighted"


def test_clean_case_scores_zero():
    assert _score()["risk_score"] == 0


def test_watchlist_match_is_a_hard_gate_regardless_of_everything_else():
    r = _score(watchlist_match=True, watchlist_match_source="document_photo")
    assert r["risk_score"] == 100 and r["scoring_model"] == "hard_gate"
    assert "document's printed photo" in r["risk_breakdown"][0]["reason"]


def test_rejected_document_is_a_hard_gate():
    assert _score(document_not_accepted=True)["risk_level"] == "high"


def test_every_factor_is_reported_even_when_it_scored_zero():
    assert len(_score()["risk_breakdown"]) == 6


def test_visual_tamper_heuristics_are_not_scored():
    """Measured to be identical on genuine and forged real documents."""
    assert adapt_tampering({"photo_tamper_score": 0.24, "text_manipulation_score_max": 0.9, "metadata_flag_count": 0}) == 0.0


def test_editing_software_metadata_is_scored():
    assert adapt_tampering({"metadata_flag_count": 1}) == 0.6
    assert adapt_tampering({"metadata_flag_count": 2}) > adapt_tampering({"metadata_flag_count": 1})


def test_untrained_classifier_probability_is_ignored():
    assert adapt_tampering({"forgery_classifier_probability": 0.99, "forgery_classifier_calibrated": False}) == 0.0


def test_hash_changes_when_any_hashed_field_changes():
    rec = {"id": "1", "session_id": "s", "name": "A", "risk_score": 10, "officer_decision": "approved"}
    assert compute_hash(rec, "prev") != compute_hash({**rec, "risk_score": 11}, "prev")
    assert compute_hash(rec, "prev") != compute_hash(rec, "other")


def test_mrz_dates_are_shown_as_real_dates_with_the_right_century():
    from app.ml_adapter import adapt_ocr
    fields = {
        "date_of_birth": {"value": "711204", "confidence": 0.99},   # 1971, not 2071
        "expiry_date": {"value": "270830", "confidence": 0.99},     # 2027, an expiry is always this century
        "name": {"value": "ROHIT MAHAJAN", "confidence": 0.8},
    }
    out = adapt_ocr({"document_type": "P", "fields": fields})["fields"]
    assert out["date_of_birth"]["value"] == "04/12/1971"
    assert out["expiry_date"]["value"] == "30/08/2027"
    assert out["name"]["value"] == "ROHIT MAHAJAN"


def test_an_impossible_mrz_date_is_left_as_read_not_invented():
    from app.ml_adapter import adapt_ocr
    out = adapt_ocr({"fields": {"date_of_birth": {"value": "711304", "confidence": 0.5}}})["fields"]
    assert out["date_of_birth"]["value"] == "711304"


def test_the_formatted_dob_still_feeds_the_acceptance_age_check():
    from datetime import date
    from app.acceptance_policy import parse_dob
    assert parse_dob("04/12/1971") == date(1971, 12, 4)


def test_incomplete_face_check_floors_risk_at_medium_and_says_why():
    r = compute_risk_score(
        validation_failure_count=0, tampering_score=0.0, face_similarity_score=None, watchlist_match=False,
        travel_direction_flag="ok", impossible_travel_flag=False, liveness_passed=None, face_check_incomplete=True,
    )
    assert r["risk_score"] >= 31 and r["risk_level"] == "medium"
    assert any(b["factor"] == "Face verification incomplete" for b in r["risk_breakdown"])
