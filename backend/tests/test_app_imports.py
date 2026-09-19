"""Guards against the class of bug that unit tests of individual modules miss:
a module deleting/renaming something another module imports. Importing the
FastAPI app exercises every router's imports, so an ImportError shows up here
instead of as a backend that won't start."""


def test_the_fastapi_app_and_all_routers_import():
    from app.main import app
    paths = {r.path for r in app.routes}
    for expected in ("/api/verification/start", "/api/verification/{session_id}/document",
                     "/api/verification/{session_id}/face", "/api/verification/{session_id}/family",
                     "/api/audit/verify-chain", "/api/health"):
        assert expected in paths, expected


def test_adapt_face_inverts_distance_to_similarity():
    from app.ml_adapter import adapt_face
    score, live = adapt_face({"face_match_distance": 0.25, "liveness_status": "passed"})
    assert round(score, 2) == 0.75 and live is True
    assert adapt_face({"liveness_status": "failed"}) == (None, False)


def _record(**kw):
    from app.models import VerificationRecord
    r = VerificationRecord(session_id="s", risk_level=kw.pop("risk_level", "low"))
    for k, v in kw.items():
        setattr(r, k, v)
    return r


def test_crosscheck_is_informational_when_it_leans_on_the_untrained_classifier():
    from app.routers.verification import _model_crosscheck
    ml = {"risk_tier": "HIGH", "risk_score": 78,
          "top_contributing_factors": [{"feature": "forgery_classifier_probability", "display_name": "x", "contribution": 1.0}]}
    out = _model_crosscheck(_record(ml_risk_json=ml, tampering_result_json={"forgery_classifier_calibrated": False}))
    assert out["informational_only"] is True
    assert out["agrees_with_displayed_score"] is None  # never raised as a disagreement


def test_crosscheck_flags_a_full_band_disagreement_when_the_model_is_credible():
    from app.routers.verification import _model_crosscheck
    ml = {"risk_tier": "HIGH", "risk_score": 80, "top_contributing_factors": [{"feature": "face_match_distance", "display_name": "x", "contribution": 1.0}]}
    out = _model_crosscheck(_record(ml_risk_json=ml, risk_level="low", tampering_result_json={}))
    assert out["informational_only"] is False
    assert out["agrees_with_displayed_score"] is False


def test_the_result_serializer_exposes_the_face_incomplete_state():
    """Regression: these fields once landed in the wrong endpoint's response
    (a search-and-replace hit the first "group_id" in the file) and the result
    API silently lacked them."""
    from app.routers.verification import _serialize
    out = _serialize(_record(face_embedding_source="unavailable", face_unavailable_reason="timeout"))
    assert out["face_check_incomplete"] is True
    assert out["face_unavailable_reason"] == "timeout"
    assert out["watchlist_checked"] is False
    ok = _serialize(_record(face_embedding_source="ml_service"))
    assert ok["face_check_incomplete"] is False and ok["watchlist_checked"] is True


def test_a_timeout_produces_a_readable_reason_not_an_empty_string():
    import asyncio
    import httpx
    from app import ml_client

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k): raise httpx.ReadTimeout("")

    real = ml_client.httpx.AsyncClient
    ml_client.httpx.AsyncClient = _Client
    try:
        try:
            asyncio.run(ml_client._post_with_connect_retry("http://x", timeout=7))
        except ml_client.MLServiceUnavailableError as exc:
            assert "7s" in str(exc) and "ReadTimeout" in str(exc)
        else:
            raise AssertionError("expected MLServiceUnavailableError")
    finally:
        ml_client.httpx.AsyncClient = real
