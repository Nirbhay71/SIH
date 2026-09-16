"""Adapts ml-service's real-pipeline response shapes (see
../ml-service/src/schemas.py) into the shapes app/modules/*.py's mocks
already produce and app/routers/verification.py, _serialize(), and the
frontend (frontend/src/pages/Result.jsx) already expect. Keeping this
mapping in one place means neither the router nor the frontend needs to
know whether a given record was scored by the mocks or the real service.
"""


def adapt_ocr(ml_ocr: dict) -> dict:
    """ml_ocr is an OCRResult.model_dump() from ml-service. Its `fields`
    dict is already {key: {value, confidence, bbox}} — the same shape
    app/modules/ocr.py's mock produces (minus bbox, which the frontend
    ignores) — so it's passed through, just relabeled at the top level to
    match the mock's `doc_type`/`low_confidence_fields` keys."""
    return {
        "doc_type": ml_ocr.get("document_type"),
        "fields": ml_ocr.get("fields", {}),
        "low_confidence_fields": ml_ocr.get("low_confidence_fields", []),
        "ml_detail": ml_ocr,
    }


def field_value(adapted_ocr: dict, key: str) -> str | None:
    field = adapted_ocr["fields"].get(key)
    return field.get("value") if field else None


def adapt_validation(ml_validation: dict) -> dict:
    """ml_validation is a ValidationResult.model_dump(). It reports
    checksum/format/logic checks separately; the mock's (and the frontend's)
    contract is a single passed/failures/failure_count summary, so this
    flattens all three violation sources into one failures list."""
    failures = []
    for reason in ml_validation.get("format_violations") or []:
        failures.append({"rule": "format", "reason": reason})
    for reason in ml_validation.get("logic_violations") or []:
        failures.append({"rule": "logic", "reason": reason})
    for check_name in ("document_number", "dob", "expiry", "composite"):
        status = ml_validation.get(f"mrz_checksum_{check_name}")
        if status == "failed":
            failures.append({"rule": f"mrz_checksum_{check_name}", "reason": f"MRZ checksum for {check_name} failed."})

    passed = bool(ml_validation.get("format_valid")) and bool(ml_validation.get("logic_consistent")) and not any(
        f["rule"].startswith("mrz_checksum") for f in failures
    )

    return {
        "passed": passed,
        "failures": failures,
        "failure_count": len(failures),
        "ml_detail": ml_validation,
    }


def adapt_tampering(ml_tampering: dict) -> float:
    """Collapses ml-service's several tampering sub-scores (photo splice,
    text-manipulation, stamp forgery, the learned forgery-classifier
    probability) into the single 0..1 scalar app/risk.py and the frontend's
    tampering-score display expect. Uses the max across whichever
    sub-checks actually ran (some are None when their optional dependency —
    e.g. a stamp reference library — isn't available) rather than an
    average, so one strongly-flagged sub-check isn't diluted by others that
    found nothing.

    forgery_classifier_probability is excluded unless
    forgery_classifier_calibrated is True: until ml-service's fine-tuned
    head is trained, that probability comes from an untrained model head
    and is explicitly documented (src/tampering/forgery_classifier.py) as
    not meaningful — including it here would let noise silently drive the
    displayed tampering score and the risk calculation built on it."""
    candidates = [
        ml_tampering.get("photo_tamper_score"),
        ml_tampering.get("text_manipulation_score_max"),
        ml_tampering.get("stamp_forgery_score"),
    ]
    if ml_tampering.get("forgery_classifier_calibrated"):
        candidates.append(ml_tampering.get("forgery_classifier_probability"))

    present = [c for c in candidates if c is not None]
    return max(present) if present else 0.0


_LIVENESS_STATUS_TO_PASSED = {"passed": True, "failed": False, "not_applicable": None}


def adapt_face(ml_face: dict) -> tuple[float | None, bool | None]:
    """ml_face is a FaceVerificationResult.model_dump(). Returns
    (face_match_score, liveness_passed) in the mock's similarity-based
    (higher-is-better) shape — ml-service reports a cosine *distance*
    (lower-is-better) instead, so this inverts it."""
    distance = ml_face.get("face_match_distance")
    face_match_score = None
    if distance is not None:
        face_match_score = max(0.0, min(1.0, 1.0 - distance))

    liveness_passed = _LIVENESS_STATUS_TO_PASSED.get(ml_face.get("liveness_status"), None)
    return face_match_score, liveness_passed
