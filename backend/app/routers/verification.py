import logging
import math
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.acceptance_policy import evaluate_acceptance, infer_nationality, parse_dob
from app.config import (
    STORAGE_DIR,
    DUPLICATE_WINDOW_HOURS,
    IMPOSSIBLE_TRAVEL_MAX_KMH,
    ML_DUPLICATE_FACE_SIMILARITY_THRESHOLD,
    ML_WATCHLIST_MATCH_THRESHOLD,
    MOCK_DUPLICATE_FACE_SIMILARITY_THRESHOLD,
    MOCK_WATCHLIST_MATCH_THRESHOLD,
)
from app.database import get_db
from app.hashchain import compute_hash
from app import ml_client
from app.ml_adapter import adapt_face, adapt_ocr, adapt_tampering, adapt_validation, field_value
from app.models import VerificationRecord, WatchlistFace
from app.modules.ocr import run_ocr
from app.modules.validation import run_validation
from app.modules.tampering import run_tampering
from app.modules.face import embed_face, cosine_similarity, run_liveness, similarity_between_images
from app.risk import compute_risk_score
from app.schemas import StartVerificationRequest, DecisionRequest
from app.ws_manager import manager

router = APIRouter(prefix="/api/verification", tags=["verification"])
logger = logging.getLogger("app.verification")


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


@router.post("/start")
async def start_verification(body: StartVerificationRequest, db: AsyncSession = Depends(get_db)):
    session_id = str(uuid.uuid4())
    record = VerificationRecord(
        session_id=session_id,
        travel_direction=body.travel_direction,
        latitude=body.latitude,
        longitude=body.longitude,
    )
    db.add(record)
    await db.commit()
    return {"session_id": session_id}


@router.websocket("/{session_id}/stream")
async def verification_stream(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id)


async def _get_record(db: AsyncSession, session_id: str) -> VerificationRecord:
    result = await db.execute(select(VerificationRecord).where(VerificationRecord.session_id == session_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(404, "Session not found")
    return record


async def _run_document_analysis_ml(session_id: str, image_bytes: bytes, filename: str, document_type_hint: str | None = None) -> dict:
    """Calls ml-service's /screen (document only — no live capture yet) and
    adapts its response into the mock modules' shapes. Raises
    ml_client.MLServiceUnavailableError if ml-service can't be reached;
    callers must catch that and fall back to _run_document_analysis_mock."""
    ml_result = await ml_client.screen_document(image_bytes, filename, document_type_hint=document_type_hint)

    if ml_result["status"] == "quality_rejected":
        reason = ml_result.get("reason", "quality issue")
        reason_messages = {
            "blur": "the image is too blurry",
            "glare": "glare/reflection is obscuring the document",
            "low_resolution": "the image resolution is too low to read reliably",
        }
        reason_message = reason_messages.get(reason, "a quality issue was detected")
        await manager.emit(
            session_id, "ocr", "error",
            f"Document rejected by quality gate — {reason_message}. Please retake: capture only the document's photo/data page, filling the frame, in good lighting. Flagged for manual review.",
        )
        empty_ocr = {"doc_type": None, "fields": {}, "low_confidence_fields": [], "ml_detail": ml_result}
        forced_validation = {
            "passed": False,
            "failures": [{"rule": "quality_gate", "reason": f"Document image quality rejected — {reason_message}."}],
            "failure_count": 1,
        }
        await manager.emit(session_id, "validation", "error", "Skipped — document failed quality gate.", {"validation": forced_validation})
        await manager.emit(session_id, "tampering", "done", "Skipped — document failed quality gate.", {"tampering_score": 1.0})
        return {"ocr": empty_ocr, "validation": forced_validation, "tampering_score": 1.0, "tampering_detail": {}}

    if ml_result["status"] == "processing_error":
        raise ml_client.MLServiceUnavailableError(ml_result.get("message", "ml-service processing_error"))

    adapted_ocr = adapt_ocr(ml_result["ocr_result"])
    await manager.emit(session_id, "ocr", "progress", f"Document type: {(adapted_ocr['doc_type'] or 'unknown').replace('_', ' ').title()}")
    await manager.emit(session_id, "ocr", "progress", "Locating MRZ / field zones (real OCR)...")
    if adapted_ocr["low_confidence_fields"]:
        await manager.emit(session_id, "ocr", "progress", f"Low confidence on: {', '.join(adapted_ocr['low_confidence_fields'])} (flagged for officer review).")
    await manager.emit(session_id, "ocr", "done", "Field confidence check complete.", {"ocr": adapted_ocr})

    adapted_validation = adapt_validation(ml_result["validation_result"])
    status = "done" if adapted_validation["passed"] else "error"
    await manager.emit(
        session_id, "validation", status,
        f"Validation complete: {adapted_validation['failure_count']} failure(s).",
        {"validation": adapted_validation},
    )

    tampering_score = adapt_tampering(ml_result["tampering_result"])
    label = "high" if tampering_score > 0.5 else "low"
    await manager.emit(
        session_id, "tampering", "done",
        f"Tampering score: {tampering_score:.2f} ({label}).",
        {"tampering_score": tampering_score},
    )

    return {
        "ocr": adapted_ocr,
        "validation": adapted_validation,
        "tampering_score": tampering_score,
        "tampering_detail": ml_result["tampering_result"],
    }


async def _run_document_analysis_mock(session_id: str, image_bytes: bytes, filename: str, document_type_hint: str | None = None) -> dict:
    force_tampered = "tampered" in (filename or "").lower()

    await manager.emit(session_id, "ocr", "started", "Detecting document type... (mock — ML service unavailable)")
    ocr_result = run_ocr(image_bytes, doc_type_hint=document_type_hint, force_tampered=force_tampered)
    await manager.emit(session_id, "ocr", "progress", f"Document type: {ocr_result['doc_type'].replace('_', ' ').title()}")
    await manager.emit(session_id, "ocr", "progress", "Locating MRZ / field zones...")
    await manager.emit(session_id, "ocr", "progress", "Extracting fields...")
    if ocr_result["low_confidence_fields"]:
        await manager.emit(session_id, "ocr", "progress", f"Low confidence on: {', '.join(ocr_result['low_confidence_fields'])} (flagged for officer review).")
    await manager.emit(session_id, "ocr", "done", "Field confidence check complete.", {"ocr": ocr_result})

    await manager.emit(session_id, "validation", "started", "Verifying document number format...")
    validation_result = run_validation(ocr_result)
    await manager.emit(session_id, "validation", "progress", "Checking expiry date...")
    await manager.emit(session_id, "validation", "progress", "Cross-checking DOB against document type...")
    status = "done" if validation_result["passed"] else "error"
    await manager.emit(
        session_id, "validation", status,
        f"Validation complete: {validation_result['failure_count']} failure(s).",
        {"validation": validation_result},
    )

    await manager.emit(session_id, "tampering", "started", "Running error-level analysis...")
    tampering_result = run_tampering(image_bytes, force_tampered=force_tampered)
    await manager.emit(session_id, "tampering", "progress", "Checking sensor noise consistency across regions...")
    await manager.emit(session_id, "tampering", "progress", "Scanning for font/spacing anomalies...")
    await manager.emit(session_id, "tampering", "progress", "Comparing stamps against reference templates...")

    heatmap_path = STORAGE_DIR / "heatmaps" / f"{session_id}.png"
    heatmap_path.write_bytes(tampering_result["heatmap_bytes"])

    label = "high" if tampering_result["tampering_score"] > 0.5 else "low"
    await manager.emit(
        session_id, "tampering", "done",
        f"Tampering score: {tampering_result['tampering_score']:.2f} ({label}).",
        {"tampering_score": tampering_result["tampering_score"], "flagged_regions": tampering_result["flagged_regions"]},
    )

    return {
        "ocr": ocr_result,
        "validation": validation_result,
        "tampering_score": tampering_result["tampering_score"],
        "tampering_detail": {"flagged_regions": tampering_result["flagged_regions"]},
        "heatmap_path": str(heatmap_path),
    }


@router.post("/{session_id}/document")
async def upload_document(
    session_id: str,
    file: UploadFile = File(...),
    document_type_hint: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    record = await _get_record(db, session_id)
    image_bytes = await file.read()
    filename = file.filename or "document"

    doc_path = STORAGE_DIR / "documents" / f"{session_id}_{filename}"
    doc_path.write_bytes(image_bytes)
    record.document_image_path = str(doc_path)

    try:
        analysis = await _run_document_analysis_ml(session_id, image_bytes, filename, document_type_hint)
        record.analysis_source = "ml_service"
    except ml_client.MLServiceUnavailableError as exc:
        # The exact failure reason used to be discarded here, which made
        # every mock-data fallback undiagnosable after the fact (frontend,
        # DB, and logs all just said "mock" with no clue why) — logged now,
        # and the reason is also stored on the record so it can be shown
        # to the officer instead of a generic "unavailable" message.
        logger.warning("ml-service unavailable for document analysis (session=%s): %s", session_id, exc)
        record.ml_fallback_reason = str(exc)[:500]
        await manager.emit(session_id, "ocr", "progress", f"ML service unavailable ({exc}) — falling back to mock analysis.")
        analysis = await _run_document_analysis_mock(session_id, image_bytes, filename, document_type_hint)
        record.analysis_source = "mock"

    record.doc_type = analysis["ocr"]["doc_type"]
    fields = analysis["ocr"]["fields"]
    record.doc_number = fields.get("document_number", {}).get("value")
    record.name = fields.get("name", {}).get("value")
    record.dob = fields.get("date_of_birth", {}).get("value")
    record.nationality = fields.get("nationality", {}).get("value")
    record.expiry_date = fields.get("expiry_date", {}).get("value") or fields.get("date_of_expiry", {}).get("value")
    record.ocr_raw_json = analysis["ocr"]
    validation_result = analysis["validation"]
    record.tampering_score = analysis["tampering_score"]
    record.tampering_result_json = analysis["tampering_detail"]
    if analysis.get("heatmap_path"):
        record.tampering_heatmap_path = analysis["heatmap_path"]

    # India-Nepal crossing document-acceptance policy (app/acceptance_policy.py)
    # — a distinct check from format validation above: a well-formatted
    # Aadhaar card is still not valid citizenship proof for this crossing.
    acceptance_nationality = infer_nationality(record.doc_type, record.nationality)
    acceptance = evaluate_acceptance(acceptance_nationality, record.doc_type, parse_dob(record.dob))
    if acceptance["applies"]:
        record.document_accepted = acceptance["accepted"]
        record.document_acceptance_reason = acceptance["reason"]
        if not acceptance["accepted"]:
            validation_result = {
                **validation_result,
                "passed": False,
                "failures": [
                    *validation_result["failures"],
                    {"rule": "document_not_accepted", "reason": acceptance["reason"]},
                ],
                "failure_count": validation_result["failure_count"] + 1,
            }
            await manager.emit(
                session_id, "validation", "error",
                f"⚠️ Document not accepted: {acceptance['reason']}",
                {"document_accepted": False, "reason": acceptance["reason"]},
            )
    else:
        record.document_accepted = None
        record.document_acceptance_reason = None

    record.validation_result_json = validation_result

    await db.commit()
    return {"ocr": analysis["ocr"], "validation": validation_result, "tampering_score": analysis["tampering_score"]}


@router.post("/{session_id}/face")
async def upload_face(
    session_id: str,
    file: UploadFile = File(...),
    simulate_mismatch: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    record = await _get_record(db, session_id)
    live_face_bytes = await file.read()

    face_path = STORAGE_DIR / "faces" / f"{session_id}_{file.filename}"
    face_path.write_bytes(live_face_bytes)
    record.live_face_image_path = str(face_path)

    await manager.emit(session_id, "face", "started", "Detecting face region in document...")
    await manager.emit(session_id, "face", "progress", "Capturing live face...")

    from pathlib import Path
    document_bytes = Path(record.document_image_path).read_bytes() if record.document_image_path else b""

    live_embedding: list[float] | None = None
    document_embedding: list[float] | None = None
    face_embedding_source = "mock"

    if record.analysis_source == "ml_service":
        try:
            ml_result = await ml_client.screen_document(
                document_bytes, "document", live_bytes=live_face_bytes, live_filename=file.filename or "live.jpg",
            )
            if ml_result["status"] != "ok":
                raise ml_client.MLServiceUnavailableError(ml_result.get("message", ml_result["status"]))

            face_match_score, liveness_passed = adapt_face(ml_result["face_result"])
            await manager.emit(session_id, "face", "progress", f"Liveness check: {'passed' if liveness_passed else 'FAILED' if liveness_passed is False else 'unavailable'}.")

            live_embedding = await ml_client.embed_face(live_face_bytes, file.filename or "live.jpg")
            # Watchlist screening must also catch a watchlisted person's own
            # document photo (genuine or forged) — see model comment on
            # document_face_embedding — so this is computed here too, not
            # just the live capture. document_bytes is the whole scanned
            # page, not a pre-cropped face, but /embed runs its own face
            # detector over the full image and simply finds nothing (None)
            # on a document type with no photo — never raises.
            if document_bytes:
                document_embedding = await ml_client.embed_face(document_bytes, "document.jpg")
            face_embedding_source = "ml_service"

            gate = (ml_result.get("risk_assessment") or {}).get("gate_triggered")
            if gate:
                await manager.emit(session_id, "face", "progress", f"ML service hard gate: {gate}.")
        except ml_client.MLServiceUnavailableError:
            await manager.emit(session_id, "face", "progress", "ML service unavailable — falling back to mock face analysis.")
            liveness_passed = run_liveness(live_face_bytes)
            face_match_score = similarity_between_images(document_bytes, live_face_bytes, force_match=not simulate_mismatch)
            live_embedding = embed_face(live_face_bytes)
            document_embedding = embed_face(document_bytes) if document_bytes else None
            face_embedding_source = "mock"
    else:
        liveness_passed = run_liveness(live_face_bytes)
        await manager.emit(session_id, "face", "progress", f"Liveness check: {'passed' if liveness_passed else 'FAILED'}.")
        face_match_score = similarity_between_images(document_bytes, live_face_bytes, force_match=not simulate_mismatch)
        live_embedding = embed_face(live_face_bytes)
        document_embedding = embed_face(document_bytes) if document_bytes else None
        face_embedding_source = "mock"

    match_label = f"{face_match_score * 100:.1f}%" if face_match_score is not None else "not computed"
    await manager.emit(session_id, "face", "done", f"Match: {match_label}.", {"similarity": face_match_score, "liveness_passed": liveness_passed})

    record.face_match_score = face_match_score
    record.liveness_passed = liveness_passed
    record.live_face_embedding = live_embedding
    record.document_face_embedding = document_embedding
    record.face_embedding_source = face_embedding_source

    watchlist_threshold = ML_WATCHLIST_MATCH_THRESHOLD if face_embedding_source == "ml_service" else MOCK_WATCHLIST_MATCH_THRESHOLD
    duplicate_threshold = ML_DUPLICATE_FACE_SIMILARITY_THRESHOLD if face_embedding_source == "ml_service" else MOCK_DUPLICATE_FACE_SIMILARITY_THRESHOLD

    # --- Watchlist check ---
    # Checks BOTH the live camera capture and the document's own printed
    # photo against every watchlist entry — not live-only. A watchlisted
    # person presenting a genuine document still has their real photo on
    # it, and a forged document built from a watchlisted person's real
    # photo should be caught too; restricting this to the live face missed
    # both cases. Either source matching is enough to flag it, and the
    # result records which one fired so an officer isn't left guessing.
    await manager.emit(session_id, "watchlist", "started", "Comparing against watchlist database...")
    wl_result = await db.execute(select(WatchlistFace))
    watchlist_entries = wl_result.scalars().all()
    await manager.emit(session_id, "watchlist", "progress", f"Comparing against watchlist database ({len(watchlist_entries)} entries)...", delay=0.2)

    watchlist_match = False
    watchlist_ref = None
    watchlist_source = None
    candidates = [("live_face", live_embedding), ("document_photo", document_embedding)]
    for source_label, embedding in candidates:
        if embedding is None or watchlist_match:
            continue
        for entry in watchlist_entries:
            if entry.embedding_source != face_embedding_source:
                continue  # different embedding spaces — not comparable
            score = cosine_similarity(embedding, entry.embedding)
            if score >= watchlist_threshold:
                watchlist_match = True
                watchlist_ref = entry.reference_label
                watchlist_source = source_label
                break

    record.watchlist_match = watchlist_match
    record.watchlist_match_ref = watchlist_ref
    record.watchlist_match_source = watchlist_source

    if watchlist_match:
        source_desc = "live camera face" if watchlist_source == "live_face" else "document photo"
        await manager.emit(
            session_id, "watchlist", "error",
            f"⚠️ Match found: {watchlist_ref} (matched via {source_desc}).",
            {"match": True, "ref": watchlist_ref, "source": watchlist_source},
        )
    else:
        await manager.emit(session_id, "watchlist", "done", "No match found.", {"match": False})

    # --- Duplicate check ---
    await manager.emit(session_id, "duplicate_check", "started", "Searching verification records from the last 2 hours...")
    window_start = datetime.utcnow() - timedelta(hours=DUPLICATE_WINDOW_HOURS)
    dup_result = await db.execute(
        select(VerificationRecord).where(
            VerificationRecord.doc_number == record.doc_number,
            VerificationRecord.created_at >= window_start,
            VerificationRecord.id != record.id,
            VerificationRecord.live_face_embedding.is_not(None),
        )
    )
    candidates = dup_result.scalars().all()

    duplicate_record = None
    if live_embedding is not None:
        for candidate in candidates:
            if candidate.face_embedding_source != face_embedding_source:
                continue  # different embedding spaces — not comparable
            sim = cosine_similarity(live_embedding, candidate.live_face_embedding)
            if sim >= duplicate_threshold:
                duplicate_record = candidate
                break

    travel_direction_flag = "not_applicable"
    impossible_travel_flag = False
    impossible_detail = None

    if duplicate_record:
        record.duplicate_of_record_id = duplicate_record.id
        await manager.emit(session_id, "duplicate_check", "progress", f"Duplicate found: matches record from {duplicate_record.created_at.isoformat()}.")

        if duplicate_record.travel_direction == record.travel_direction:
            travel_direction_flag = "suspicious"
        else:
            travel_direction_flag = "consistent"

        if (
            record.latitude is not None and record.longitude is not None
            and duplicate_record.latitude is not None and duplicate_record.longitude is not None
        ):
            distance_km = haversine_km(record.latitude, record.longitude, duplicate_record.latitude, duplicate_record.longitude)
            elapsed_hours = max((record.created_at - duplicate_record.created_at).total_seconds() / 3600.0, 1e-6)
            required_speed = distance_km / elapsed_hours
            impossible_detail = {
                "distance_km": round(distance_km, 2),
                "time_elapsed_minutes": round(elapsed_hours * 60, 1),
                "required_speed_kmh": round(required_speed, 1),
            }
            if required_speed > IMPOSSIBLE_TRAVEL_MAX_KMH:
                impossible_travel_flag = True

        await manager.emit(
            session_id, "duplicate_check", "done",
            f"Travel direction: {travel_direction_flag}." + (" Impossible travel detected." if impossible_travel_flag else ""),
            {"duplicate": True, "travel_direction_flag": travel_direction_flag, "impossible_travel": impossible_travel_flag, "detail": impossible_detail},
        )
    else:
        await manager.emit(session_id, "duplicate_check", "done", "No prior record found — first scan for this traveler.", {"duplicate": False})

    record.travel_direction_flag = travel_direction_flag
    record.impossible_travel_flag = impossible_travel_flag
    record.impossible_travel_detail_json = impossible_detail

    # --- Risk scoring ---
    await manager.emit(session_id, "risk_score", "started", "Aggregating module outputs...")
    validation_failures = (record.validation_result_json or {}).get("failure_count", 0)
    risk = compute_risk_score(
        validation_failure_count=validation_failures,
        tampering_score=record.tampering_score or 0.0,
        face_similarity_score=record.face_match_score,
        watchlist_match=record.watchlist_match,
        travel_direction_flag=travel_direction_flag,
        impossible_travel_flag=impossible_travel_flag,
        document_not_accepted=record.document_accepted is False,
        document_not_accepted_reason=record.document_acceptance_reason,
        liveness_passed=record.liveness_passed,
        watchlist_match_source=record.watchlist_match_source,
    )
    record.risk_score = risk["risk_score"]
    record.risk_level = risk["risk_level"]
    record.risk_breakdown_json = risk["risk_breakdown"]

    await manager.emit(session_id, "risk_score", "done", f"Final risk score: {risk['risk_score']} ({risk['risk_level'].title()}).", {"risk": risk})

    await db.commit()
    return {"face_match_score": face_match_score, "watchlist_match": watchlist_match, "risk": risk}


@router.get("/{session_id}/heatmap")
async def get_heatmap(session_id: str, db: AsyncSession = Depends(get_db)):
    record = await _get_record(db, session_id)
    if not record.tampering_heatmap_path:
        raise HTTPException(404, "No heatmap available")
    return FileResponse(record.tampering_heatmap_path)


@router.get("/{session_id}/document-image")
async def get_document_image(session_id: str, db: AsyncSession = Depends(get_db)):
    record = await _get_record(db, session_id)
    if not record.document_image_path:
        raise HTTPException(404, "No document image available")
    return FileResponse(record.document_image_path)


@router.get("/{session_id}/result")
async def get_result(session_id: str, db: AsyncSession = Depends(get_db)):
    record = await _get_record(db, session_id)
    return _serialize(record)


@router.post("/{session_id}/decision")
async def decide(session_id: str, body: DecisionRequest, db: AsyncSession = Depends(get_db)):
    record = await _get_record(db, session_id)
    record.officer_decision = body.decision
    record.decided_at = datetime.utcnow()

    # Chain position must come from chain_sequence, never a business
    # timestamp like decided_at — decided_at values can tie or invert
    # between close-together decisions (verified at scale with seeded data;
    # see app/routers/audit.py), which would corrupt the very chain this is
    # meant to make tamper-evident.
    prev_result = await db.execute(
        select(VerificationRecord)
        .where(VerificationRecord.record_hash.is_not(None))
        .order_by(VerificationRecord.chain_sequence.desc())
        .limit(1)
    )
    prev = prev_result.scalar_one_or_none()
    prev_hash = prev.record_hash if prev else ""
    record.chain_sequence = (prev.chain_sequence + 1) if prev else 0
    record.prev_hash = prev_hash
    record.record_hash = compute_hash(_serialize(record), prev_hash)

    await db.commit()
    return _serialize(record)


def _serialize(record: VerificationRecord) -> dict:
    return {
        "id": record.id,
        "session_id": record.session_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "analysis_source": record.analysis_source,
        "ml_fallback_reason": record.ml_fallback_reason,
        "doc_type": record.doc_type,
        "doc_number": record.doc_number,
        "name": record.name,
        "dob": record.dob,
        "nationality": record.nationality,
        "expiry_date": record.expiry_date,
        "document_accepted": record.document_accepted,
        "document_acceptance_reason": record.document_acceptance_reason,
        "ocr_raw_json": record.ocr_raw_json,
        "validation_result_json": record.validation_result_json,
        "tampering_score": record.tampering_score,
        "tampering_result_json": record.tampering_result_json,
        "tampering_heatmap_path": f"/api/verification/{record.session_id}/heatmap" if record.tampering_heatmap_path else None,
        "document_image_url": f"/api/verification/{record.session_id}/document-image" if record.document_image_path else None,
        "face_match_score": record.face_match_score,
        "liveness_passed": record.liveness_passed,
        "watchlist_match": record.watchlist_match,
        "watchlist_match_ref": record.watchlist_match_ref,
        "watchlist_match_source": record.watchlist_match_source,
        "latitude": record.latitude,
        "longitude": record.longitude,
        "travel_direction": record.travel_direction,
        "duplicate_of_record_id": record.duplicate_of_record_id,
        "travel_direction_flag": record.travel_direction_flag,
        "impossible_travel_flag": record.impossible_travel_flag,
        "impossible_travel_detail_json": record.impossible_travel_detail_json,
        "risk_score": record.risk_score,
        "risk_level": record.risk_level,
        "risk_breakdown_json": record.risk_breakdown_json,
        "officer_decision": record.officer_decision,
        "decided_at": record.decided_at.isoformat() if record.decided_at else None,
        "record_hash": record.record_hash,
        "prev_hash": record.prev_hash,
    }
