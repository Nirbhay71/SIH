"""Adapts ml-service's real-pipeline response shapes (see
../ml-service/src/schemas.py) into the shapes app/modules/*.py's mocks
already produce and app/routers/verification.py, _serialize(), and the
frontend (frontend/src/pages/Result.jsx) already expect. Keeping this
mapping in one place means neither the router nor the frontend needs to
know whether a given record was scored by the mocks or the real service.
"""


from datetime import datetime


def _format_mrz_date(raw: str, *, is_expiry: bool) -> str:
    """MRZ dates are YYMMDD with no century. Shown as DD/MM/YYYY, because
    "711204" reads as nonsense to an officer and "date of birth 270830" looks
    like an extraction error.

    Century: an expiry date is always this century (passports are valid for at
    most ~10 years). A date of birth is this century only if that would not
    put the holder in the future — otherwise last century (ICAO 9303 leaves
    this to the reader; this is the standard rule). Unparseable input is
    returned as read, never guessed at."""
    if not (len(raw) == 6 and raw.isascii() and raw.isdigit()):
        return raw
    yy, mm, dd = int(raw[0:2]), int(raw[2:4]), int(raw[4:6])
    year = 2000 + yy if (is_expiry or yy <= datetime.now().year % 100) else 1900 + yy
    try:
        datetime(year, mm, dd)
    except ValueError:
        return raw
    return f"{dd:02d}/{mm:02d}/{year}"


def _display_fields(fields: dict) -> dict:
    out = {}
    for key, fe in fields.items():
        if key in ("date_of_birth", "expiry_date") and isinstance(fe, dict) and isinstance(fe.get("value"), str):
            fe = {**fe, "value": _format_mrz_date(fe["value"], is_expiry=key == "expiry_date")}
        out[key] = fe
    return out


def adapt_ocr(ml_ocr: dict) -> dict:
    """ml_ocr is an OCRResult.model_dump() from ml-service. Its `fields`
    dict is already {key: {value, confidence, bbox}} — the same shape
    app/modules/ocr.py's mock produces (minus bbox, which the frontend
    ignores) — so it's passed through, just relabeled at the top level to
    match the mock's `doc_type`/`low_confidence_fields` keys."""
    return {
        "doc_type": ml_ocr.get("document_type"),
        "fields": _display_fields(ml_ocr.get("fields", {})),
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
    """Collapses ml-service's tampering output into the single 0..1 scalar
    app/risk.py and the frontend display expect — using ONLY evidence-grade
    signals.

    Measured, not assumed (ml-service/evaluation/tampering_realdoc.py): the
    visual heuristics (photo_tamper_score, text_manipulation_score_max) scored
    the untouched real originals and every forgery built from them
    identically (~0.85-0.9 on both), i.e. they respond to the document, not to
    an edit. Feeding them into the risk score made every real document look
    moderately tampered and told an officer nothing. They are still returned
    by ml-service and stored in tampering_result_json for inspection; they
    are just not scored.

    Scored: metadata forensics (an explicit editing-software tag, or a
    modified-after-capture timestamp), and the learned forgery classifier
    only if its head is trained (forgery_classifier_calibrated) — and a
    stamp-forensics result when a reference library exists. Absence of a
    metadata flag proves nothing (metadata is trivially stripped), so a
    clean result here means "no tampering evidence found", not "verified
    genuine" — the UI says so."""
    candidates: list[float] = []

    flag_count = ml_tampering.get("metadata_flag_count") or 0
    if flag_count:
        # One explicit editor tag is strong evidence; two independent flags
        # are stronger. Bounded well below 1.0: metadata alone is trivially
        # forged, so it shouldn't single-handedly max the factor.
        candidates.append(min(0.6 + 0.25 * (flag_count - 1), 0.9))

    if ml_tampering.get("stamp_forgery_score") is not None:
        candidates.append(ml_tampering["stamp_forgery_score"])
    if ml_tampering.get("forgery_classifier_calibrated") and ml_tampering.get("forgery_classifier_probability") is not None:
        candidates.append(ml_tampering["forgery_classifier_probability"])

    return max(candidates) if candidates else 0.0


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
