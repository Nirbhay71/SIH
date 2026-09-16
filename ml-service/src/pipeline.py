"""Orchestrates all modules end-to-end (Section 3B). A straightforward,
linear sequence of module calls with explicit early-exit points — analysis
logic belongs inside each module, not here.

Fail-closed guarantee (Section 11): any unexpected error partway through
must surface as `status: "processing_error"`, never as a silently
incomplete result a caller could mistake for a low-risk clearance.
"""
import logging
from datetime import date

import cv2
import numpy as np

from src.face.face_verification import FaceVerificationUnavailableError, verify_faces
from src.face.identity_dedup import IdentityIndex, check_duplicate_identity
from src.face.liveness import LivenessUnavailableError, check_liveness
from src.fusion.explain import explain_prediction
from src.fusion.feature_builder import build_feature_vector
from src.fusion.hard_gates import check_watchlist_hit, evaluate_hard_gates
from src.fusion.risk_model import ModelNotAvailableError, run_fusion_model
from src.ocr.field_normalization import normalize_date, normalize_document_number, normalize_name
from src.ocr.field_ocr import ocr_full_document
from src.ocr.mrz_extractor import extract_mrz
from src.ocr.semantic_field_mapper import extract_semantic_fields
from src.preprocessing.boundary_detection import crop_to_boundary, detect_document_boundary
from src.preprocessing.deskew import deskew
from src.preprocessing.format_normalization import normalize_to_array
from src.preprocessing.quality_gate import check_quality, quality_flags
from src.preprocessing.region_segmentation import find_mrz_zone, find_photo_region, find_text_field_zones
from src.schemas import FaceVerificationResult, FieldExtraction, IdentityDedupResult, OCRResult, PipelineResult
from src.tampering.detect import run_tampering_detection
from src.validation.format_rules import validate_format
from src.validation.logic_checks import check_cross_zone_match, check_logic_consistency
from src.validation.mrz_checksum import checksum_status

logger = logging.getLogger("src.pipeline")

_IDENTITY_INDEX = IdentityIndex()
_MOCK_WATCHLIST: set[str] = set()  # Section 2 — simulated, not a real government database


def preprocess(raw_bytes: bytes, filename_hint: str = "") -> dict:
    """Section 5.1 steps 1-5, condensed. Returns a dict rather than a
    Pydantic model here since it is purely internal plumbing consumed
    only by `run_pipeline` in this same file."""
    image = normalize_to_array(raw_bytes, filename_hint)

    quad = detect_document_boundary(image)
    boundary_failed = quad is None
    if not boundary_failed:
        image = crop_to_boundary(image, quad)

    image, deskew_skipped = deskew(image)

    passed, reason, score = check_quality(image)
    if not passed:
        # Only the near-zero-pixel degenerate case reaches here now — see
        # quality_gate.py's module docstring for why ordinary blur/glare/
        # low-but-nonzero-resolution issues no longer block extraction.
        return {"status": "quality_rejected", "reason": reason, "score": score}

    flags = quality_flags(image)

    mrz_box = find_mrz_zone(image)
    photo_box = find_photo_region(image)
    field_boxes = find_text_field_zones(image, exclude=[b for b in (mrz_box, photo_box) if b])

    return {
        "status": "ok",
        "image": image,
        "boundary_detection_failed": boundary_failed,
        "deskew_skipped_large_angle": deskew_skipped,
        "quality_flags": flags,
        "mrz_box": mrz_box,
        "photo_box": photo_box,
        "field_boxes": field_boxes,
    }


def extract_ocr(preprocessed: dict, document_type_hint: str | None) -> OCRResult:
    """Sections 5.1A, 5.2, 5.5. Document-type classification here is
    deliberately a light heuristic (Section 5.1A) — see docs/ARCHITECTURE.md."""
    image = preprocessed["image"]
    mrz_box = preprocessed["mrz_box"]

    mrz_result = extract_mrz(image) if mrz_box is not None else None
    document_type = document_type_hint or ("foreign_passport" if mrz_result and mrz_result.found else "oci_card")

    fields: dict[str, FieldExtraction] = {}
    low_confidence_fields: list[str] = []
    confidences: list[float] = []

    if mrz_result and mrz_result.found:
        for key, value in mrz_result.fields.items():
            if value is None:
                continue
            confidence = mrz_result.valid_score if mrz_result.valid_score is not None else 0.9
            fields[key] = FieldExtraction(value=str(value), confidence=confidence)
            confidences.append(confidence)
            if confidence < 0.85:
                low_confidence_fields.append(key)
    else:
        # No MRZ (Aadhaar, Voter ID, ration card, etc. — most of the
        # document types this system's own acceptance_policy.py lists).
        # This used to leave `fields` completely empty for every non-MRZ
        # document, regardless of image quality — a real gap, not a
        # quality issue.
        #
        # Runs PaddleOCR over the whole page rather than over this build's
        # heuristic text-zone crops: PaddleOCR brings its own trained text
        # detector, and feeding it pre-cut crops from the contour/morphology
        # heuristic in region_segmentation.py threw that away in favour of a
        # much cruder one — the visible symptom was characters sliced
        # mid-glyph ("तIENDOB" where the page reads "DOB", "पु! MALE" for
        # "पुरुष/ MALE"). Line labels below are positional (`line_0`,
        # `line_1`, ... in reading order), not semantic; the semantic pass
        # further down is what maps them to name/DOB/etc.
        #
        # Belt-and-suspenders around the whole block, not just per-line:
        # PaddleOCR sharing a process with PyTorch (forgery classifier,
        # timm) can hit a native DLL-load crash on Windows (observed:
        # "[WinError 127] ... torch\lib\shm.dll") that is fixed by importing
        # torch first (see api/main.py) — but low-level DLL failures aren't
        # guaranteed to surface as a normal Python exception field_ocr's own
        # try/except can catch cleanly, and this must never take down
        # document analysis entirely the way it did before.
        try:
            for i, line in enumerate(ocr_full_document(image)[:25]):
                key = f"line_{i}"
                fields[key] = FieldExtraction(value=line.text, confidence=line.confidence)
                confidences.append(line.confidence)
                if line.confidence < 0.85:
                    low_confidence_fields.append(key)
        except Exception:
            logger.exception("Field-level OCR failed for a non-MRZ document; continuing with fields extracted so far.")

        # The raw line_N reads above are genuinely useful (an
        # officer can read them directly), but downstream logic —
        # acceptance_policy.py's age-bracket check in particular — looks
        # for a field literally named "date_of_birth", so a real DOB the
        # OCR actually read was being silently discarded, forcing every
        # non-MRZ document into the "DOB unknown, manual review" fail-
        # closed path even when the text was right there. Best-effort
        # keyword/regex mapping, not a real layout understanding — explicitly
        # lower-confidence than a true field-level read, and does not
        # overwrite an existing key of the same name.
        for key, value in extract_semantic_fields(fields).items():
            if key not in fields:
                fields[key] = value
                confidences.append(value.confidence)
                if value.confidence < 0.85:
                    low_confidence_fields.append(key)

    avg_conf = float(np.mean(confidences)) if confidences else 0.0
    min_conf = float(np.min(confidences)) if confidences else 0.0

    return OCRResult(
        status="ok",
        document_type=document_type,
        document_type_classification_method="hinted" if document_type_hint else "heuristic",
        fields=fields,
        mrz_raw=mrz_result.raw_lines if mrz_result else None,
        mrz_check_digits=mrz_result.check_digits if mrz_result else None,
        mrz_extraction_method=mrz_result.method if mrz_result else "not_applicable",
        mrz_valid_score=mrz_result.valid_score if mrz_result else None,
        ocr_confidence_avg=avg_conf,
        ocr_confidence_min=min_conf,
        low_confidence_fields=low_confidence_fields,
        quality_flags=preprocessed.get("quality_flags", []),
    )


def validate_document(ocr_result: OCRResult):
    from src.schemas import ValidationResult

    low_conf = set(ocr_result.low_confidence_fields)
    check_digits = ocr_result.mrz_check_digits or {}
    fields = ocr_result.fields

    def field_value(name: str) -> str | None:
        return fields[name].value if name in fields else None

    doc_num_status = checksum_status(
        field_value("document_number"), check_digits.get("document_number"),
        field_is_low_confidence="document_number" in low_conf,
        field_present=bool(field_value("document_number")),
    )
    dob_status = checksum_status(
        field_value("date_of_birth"), check_digits.get("date_of_birth"),
        field_is_low_confidence="date_of_birth" in low_conf,
        field_present=bool(field_value("date_of_birth")),
    )
    expiry_status = checksum_status(
        field_value("expiry_date"), check_digits.get("expiry_date"),
        field_is_low_confidence="expiry_date" in low_conf,
        field_present=bool(field_value("expiry_date")),
    )
    composite_status = checksum_status(
        None, check_digits.get("composite"), field_is_low_confidence=False, field_present=False,
    )  # composite recomputation over full MRZ line is not wired in this build; see LIMITATIONS.md

    format_valid, format_violations = validate_format(ocr_result.document_type, field_value("document_number"))

    dob_date, _ = normalize_date(field_value("date_of_birth"))
    expiry_dt, _ = normalize_date(field_value("expiry_date"))
    logic_consistent, logic_violations = check_logic_consistency(None, expiry_dt, dob_date)

    cross_zone = check_cross_zone_match(None, None, low_conf)  # no separate visual-zone OCR pass wired in this build

    return ValidationResult(
        mrz_checksum_document_number=doc_num_status,
        mrz_checksum_dob=dob_status,
        mrz_checksum_expiry=expiry_status,
        mrz_checksum_composite=composite_status,
        format_valid=format_valid,
        format_violations=format_violations,
        logic_consistent=logic_consistent,
        logic_violations=logic_violations,
        cross_zone_match=cross_zone,
    )


def run_pipeline(
    document_image: bytes,
    live_capture: bytes | None,
    document_type_hint: str | None = None,
    document_filename: str = "",
) -> PipelineResult:
    try:
        preprocessed = preprocess(document_image, document_filename)
        if preprocessed["status"] == "quality_rejected":
            return PipelineResult(status="quality_rejected", reason=preprocessed["reason"], score=preprocessed["score"])

        ocr_result = extract_ocr(preprocessed, document_type_hint)
        validation_result = validate_document(ocr_result)

        field_crops = {}
        image = preprocessed["image"]
        for i, box in enumerate(preprocessed["field_boxes"][:10]):
            field_crops[f"field_{i}"] = image[box.y : box.y + box.height, box.x : box.x + box.width]

        tampering_result = run_tampering_detection(
            image=image,
            original_bytes=document_image,
            photo_box=preprocessed["photo_box"],
            field_crops=field_crops,
            stamp_crops=[],
            reference_stamps=[],
        )

        face_result = FaceVerificationResult(face_match_status="not_computed")
        identity_result = IdentityDedupResult()

        if live_capture is not None and preprocessed["photo_box"] is not None:
            live_image = normalize_to_array(live_capture)
            box = preprocessed["photo_box"]
            doc_photo_crop = image[box.y : box.y + box.height, box.x : box.x + box.width]
            try:
                liveness_status, liveness_score = check_liveness(live_image)
                face_result = verify_faces(doc_photo_crop, live_image, liveness_status)
                face_result.liveness_score = liveness_score
            except (LivenessUnavailableError, FaceVerificationUnavailableError) as exc:
                logger.warning("Face verification unavailable: %s", exc)
                face_result = FaceVerificationResult(liveness_status="not_applicable", face_match_status="not_computed")

        watchlist_hit = check_watchlist_hit(
            ocr_result.fields.get("document_number").value if "document_number" in ocr_result.fields else None,
            _MOCK_WATCHLIST,
        )

        gate_result = evaluate_hard_gates(validation_result, face_result, identity_result, watchlist_hit)

        if gate_result.triggered:
            from src.schemas import RiskAssessment

            risk_assessment = RiskAssessment(risk_score=96, risk_tier="CRITICAL", gate_triggered=gate_result.reason)
        else:
            try:
                features = build_feature_vector(ocr_result, validation_result, tampering_result, face_result, identity_result)
                risk_assessment = run_fusion_model(features)
                risk_assessment.top_contributing_factors = explain_prediction(features)
            except ModelNotAvailableError as exc:
                logger.error("Fusion model unavailable, failing closed: %s", exc)
                return PipelineResult(
                    status="processing_error",
                    message="Risk model unavailable — this document requires manual review and cannot be auto-scored.",
                )

        return PipelineResult(
            status="ok",
            ocr_result=ocr_result,
            validation_result=validation_result,
            tampering_result=tampering_result,
            face_result=face_result,
            identity_result=identity_result,
            risk_assessment=risk_assessment,
        )

    except Exception as exc:  # fail closed (Section 11) — never let an unexpected error look like a clean pass
        logger.exception("Unexpected pipeline error")
        return PipelineResult(status="processing_error", message=f"Internal processing error: {exc}")
