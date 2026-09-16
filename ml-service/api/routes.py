"""Section 9A — the `/screen` endpoint. This is the only interface a
downstream backend or human tester should call (Section 13F)."""
import logging
import time
import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from src.face.face_verification import get_embedding
from src.pipeline import run_pipeline
from src.preprocessing.format_normalization import normalize_to_array

logger = logging.getLogger("api")
router = APIRouter()

MAX_UPLOAD_SIZE_MB = 15
MAX_IMAGE_DIMENSION_PX = 6000  # informational here; enforced where the image is actually decoded (src/preprocessing)
RATE_LIMIT_REQUESTS_PER_MINUTE = 30

_KNOWN_MAGIC_BYTES = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"II*\x00": "tiff",
    b"MM\x00*": "tiff",
    b"%PDF": "pdf",
}

# WebP's magic bytes aren't a fixed prefix like the formats above — it's a
# RIFF container ("RIFF" + 4-byte size + "WEBP"), so it needs its own check
# rather than a dict entry. Missing this rejected every real-world image
# saved from a browser image search (Google Images serves WebP by default),
# which silently fell back to mock analysis data with a confusing generic
# "unrecognized magic bytes" error — genuinely common real-world input, not
# an edge case.
def _is_webp(raw_bytes: bytes) -> bool:
    return len(raw_bytes) >= 12 and raw_bytes[0:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP"

_request_log: dict[str, deque] = defaultdict(deque)


def _rate_limit_check(client_id: str) -> None:
    """Basic in-memory per-source rate limit (Section 11). A production
    deployment would place a proper API gateway in front of this service
    instead of relying on the ML service itself — documented in README.md."""
    now = time.time()
    window = _request_log[client_id]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_REQUESTS_PER_MINUTE:
        raise HTTPException(429, "Rate limit exceeded. Try again shortly.")
    window.append(now)


def _validate_upload(raw_bytes: bytes, filename: str) -> None:
    """Section 11: verify well-formed magic bytes and size BEFORE any
    decoding happens — the resource-limit check runs first since even
    decoding a maliciously oversized file can be the expensive operation
    being guarded against."""
    size_mb = len(raw_bytes) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(413, f"Upload exceeds the {MAX_UPLOAD_SIZE_MB} MB limit.")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in ("heic", "heif"):
        return  # HEIC magic-byte sniffing is not implemented; format support itself is optional (see README.md)

    if not any(raw_bytes.startswith(magic) for magic in _KNOWN_MAGIC_BYTES) and not _is_webp(raw_bytes):
        raise HTTPException(400, "Uploaded file does not have recognizable image/PDF magic bytes.")


@router.post("/screen")
async def screen_document(
    request: Request,
    document_image: UploadFile = File(...),
    live_capture_image: UploadFile | None = File(None),
    document_type_hint: str | None = Form(None),
):
    client_id = request.client.host if request.client else "unknown"
    _rate_limit_check(client_id)

    request_id = str(uuid.uuid4())
    start = time.time()

    document_bytes = await document_image.read()
    _validate_upload(document_bytes, document_image.filename or "")

    live_bytes = None
    if live_capture_image is not None:
        live_bytes = await live_capture_image.read()
        _validate_upload(live_bytes, live_capture_image.filename or "")

    try:
        result = run_pipeline(
            document_image=document_bytes,
            live_capture=live_bytes,
            document_type_hint=document_type_hint,
            document_filename=document_image.filename or "",
        )
    except Exception as exc:  # Section 11: fail closed, never a bare 500 with no explanation
        logger.exception("request_id=%s unhandled error in /screen", request_id)
        return JSONResponse(
            status_code=200,
            content={
                "status": "processing_error",
                "message": "An internal error occurred. This document requires manual review.",
            },
        )

    latency_ms = (time.time() - start) * 1000
    doc_type = result.ocr_result.document_type if result.ocr_result else None
    risk_tier = result.risk_assessment.risk_tier if result.risk_assessment else None
    gate = result.risk_assessment.gate_triggered if result.risk_assessment else None

    logger.info(
        "request_id=%s document_type=%s latency_ms=%.1f risk_tier=%s",
        request_id, doc_type, latency_ms, risk_tier,
    )
    if gate:
        logger.warning("request_id=%s HARD GATE FIRED: %s", request_id, gate)

    if result.status == "quality_rejected":
        return {
            "status": "quality_rejected",
            "reason": result.reason,
            "score": result.score,
            "message": f"Document image is too {result.reason} for reliable analysis. Please re-scan or re-photograph in better lighting with a steady camera.",
        }

    if result.status == "processing_error":
        return {"status": "processing_error", "message": result.message}

    return {
        "status": "ok",
        "ocr_result": result.ocr_result.model_dump() if result.ocr_result else None,
        "validation_result": result.validation_result.model_dump() if result.validation_result else None,
        "tampering_result": result.tampering_result.model_dump() if result.tampering_result else None,
        "face_result": result.face_result.model_dump() if result.face_result else None,
        "risk_assessment": result.risk_assessment.model_dump() if result.risk_assessment else None,
    }


@router.post("/embed")
async def embed_face(request: Request, image: UploadFile = File(...)):
    """Not part of the problem-statement-mandated `/screen` contract (Section
    9A) — a narrow extra endpoint so a caller who needs a raw face embedding
    directly (e.g. enrolling a watchlist reference photo, or storing a
    duplicate-identity-check vector) can get one in the same ArcFace vector
    space `/screen`'s internal face matching uses, without re-deriving it
    from a face-match distance. Never exposes embeddings for two uploaded
    images to be compared client-side against each other in a way that
    bypasses the liveness-gated logic in `/screen` — this only returns a
    single image's embedding."""
    client_id = request.client.host if request.client else "unknown"
    _rate_limit_check(client_id)

    raw_bytes = await image.read()
    _validate_upload(raw_bytes, image.filename or "")

    try:
        array = normalize_to_array(raw_bytes, image.filename or "")
        embedding = get_embedding(array)
    except ImportError:
        return {"embedding": None, "reason": "face_embedding_unavailable"}
    except Exception:
        logger.exception("unhandled error in /embed")
        return {"embedding": None, "reason": "processing_error"}

    if embedding is None:
        return {"embedding": None, "reason": "no_face_detected"}
    return {"embedding": embedding, "reason": None}
