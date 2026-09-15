import math
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    STORAGE_DIR,
    DUPLICATE_FACE_SIMILARITY_THRESHOLD,
    DUPLICATE_WINDOW_HOURS,
    IMPOSSIBLE_TRAVEL_MAX_KMH,
    WATCHLIST_MATCH_THRESHOLD,
)
from app.database import get_db
from app.hashchain import compute_hash
from app.models import VerificationRecord, WatchlistFace
from app.modules.ocr import run_ocr
from app.modules.validation import run_validation
from app.modules.tampering import run_tampering
from app.modules.face import embed_face, cosine_similarity, run_liveness, similarity_between_images
from app.risk import compute_risk_score
from app.schemas import StartVerificationRequest, DecisionRequest
from app.ws_manager import manager

router = APIRouter(prefix="/api/verification", tags=["verification"])


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


@router.post("/{session_id}/document")
async def upload_document(session_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    record = await _get_record(db, session_id)
    image_bytes = await file.read()
    force_tampered = "tampered" in (file.filename or "").lower()

    doc_path = STORAGE_DIR / "documents" / f"{session_id}_{file.filename}"
    doc_path.write_bytes(image_bytes)
    record.document_image_path = str(doc_path)

    # --- OCR ---
    await manager.emit(session_id, "ocr", "started", "Detecting document type...")
    ocr_result = run_ocr(image_bytes, force_tampered=force_tampered)
    await manager.emit(session_id, "ocr", "progress", f"Document type: {ocr_result['doc_type'].replace('_', ' ').title()}")
    await manager.emit(session_id, "ocr", "progress", "Locating MRZ / field zones...")
    await manager.emit(session_id, "ocr", "progress", "Extracting fields...")
    if ocr_result["low_confidence_fields"]:
        await manager.emit(session_id, "ocr", "progress", f"Low confidence on: {', '.join(ocr_result['low_confidence_fields'])} (flagged for officer review).")
    await manager.emit(session_id, "ocr", "done", "Field confidence check complete.", {"ocr": ocr_result})

    record.doc_type = ocr_result["doc_type"]
    record.doc_number = ocr_result["fields"]["document_number"]["value"]
    record.name = ocr_result["fields"]["name"]["value"]
    record.dob = ocr_result["fields"]["date_of_birth"]["value"]
    record.nationality = ocr_result["fields"]["nationality"]["value"]
    record.expiry_date = ocr_result["fields"]["date_of_expiry"]["value"]
    record.ocr_raw_json = ocr_result

    # --- Validation ---
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
    record.validation_result_json = validation_result

    # --- Tampering ---
    await manager.emit(session_id, "tampering", "started", "Running error-level analysis...")
    tampering_result = run_tampering(image_bytes, force_tampered=force_tampered)
    await manager.emit(session_id, "tampering", "progress", "Checking sensor noise consistency across regions...")
    await manager.emit(session_id, "tampering", "progress", "Scanning for font/spacing anomalies...")
    await manager.emit(session_id, "tampering", "progress", "Comparing stamps against reference templates...")

    heatmap_path = STORAGE_DIR / "heatmaps" / f"{session_id}.png"
    heatmap_path.write_bytes(tampering_result["heatmap_bytes"])
    record.tampering_heatmap_path = str(heatmap_path)
    record.tampering_score = tampering_result["tampering_score"]
    record.tampering_result_json = {"flagged_regions": tampering_result["flagged_regions"]}

    label = "high" if tampering_result["tampering_score"] > 0.5 else "low"
    await manager.emit(
        session_id, "tampering", "done",
        f"Tampering score: {tampering_result['tampering_score']:.2f} ({label}).",
        {"tampering_score": tampering_result["tampering_score"], "flagged_regions": tampering_result["flagged_regions"]},
    )

    await db.commit()
    return {"ocr": ocr_result, "validation": validation_result, "tampering_score": tampering_result["tampering_score"]}


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

    liveness_passed = run_liveness(live_face_bytes)
    await manager.emit(session_id, "face", "progress", f"Liveness check: {'passed' if liveness_passed else 'FAILED'}.")

    document_bytes = None
    if record.document_image_path:
        from pathlib import Path
        document_bytes = Path(record.document_image_path).read_bytes()

    similarity = similarity_between_images(
        document_bytes or b"", live_face_bytes, force_match=not simulate_mismatch
    )
    live_embedding = embed_face(live_face_bytes)

    await manager.emit(session_id, "face", "done", f"Match: {similarity * 100:.1f}%.", {"similarity": similarity, "liveness_passed": liveness_passed})

    record.face_match_score = similarity
    record.liveness_passed = liveness_passed
    record.live_face_embedding = live_embedding

    # --- Watchlist check ---
    await manager.emit(session_id, "watchlist", "started", "Comparing against watchlist database...")
    wl_result = await db.execute(select(WatchlistFace))
    watchlist_entries = wl_result.scalars().all()
    await manager.emit(session_id, "watchlist", "progress", f"Comparing against watchlist database ({len(watchlist_entries)} entries)...", delay=0.2)

    watchlist_match = False
    watchlist_ref = None
    best_score = 0.0
    for entry in watchlist_entries:
        score = cosine_similarity(live_embedding, entry.embedding)
        if score > best_score:
            best_score = score
        if score >= WATCHLIST_MATCH_THRESHOLD:
            watchlist_match = True
            watchlist_ref = entry.reference_label
            break

    record.watchlist_match = watchlist_match
    record.watchlist_match_ref = watchlist_ref

    if watchlist_match:
        await manager.emit(session_id, "watchlist", "error", f"⚠️ Match found: {watchlist_ref}.", {"match": True, "ref": watchlist_ref})
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
    for candidate in candidates:
        sim = cosine_similarity(live_embedding, candidate.live_face_embedding)
        if sim >= DUPLICATE_FACE_SIMILARITY_THRESHOLD:
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
    )
    record.risk_score = risk["risk_score"]
    record.risk_level = risk["risk_level"]
    record.risk_breakdown_json = risk["risk_breakdown"]

    await manager.emit(session_id, "risk_score", "done", f"Final risk score: {risk['risk_score']} ({risk['risk_level'].title()}).", {"risk": risk})

    await db.commit()
    return {"face_match_score": similarity, "watchlist_match": watchlist_match, "risk": risk}


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

    prev_result = await db.execute(
        select(VerificationRecord)
        .where(VerificationRecord.record_hash.is_not(None))
        .order_by(VerificationRecord.decided_at.desc())
        .limit(1)
    )
    prev = prev_result.scalar_one_or_none()
    prev_hash = prev.record_hash if prev else ""
    record.prev_hash = prev_hash
    record.record_hash = compute_hash(_serialize(record), prev_hash)

    await db.commit()
    return _serialize(record)


def _serialize(record: VerificationRecord) -> dict:
    return {
        "id": record.id,
        "session_id": record.session_id,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "doc_type": record.doc_type,
        "doc_number": record.doc_number,
        "name": record.name,
        "dob": record.dob,
        "nationality": record.nationality,
        "expiry_date": record.expiry_date,
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
