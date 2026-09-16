"""Thin async client for the real ml-service (../ml-service). Every function
here can fail — connection refused, timeout, or a non-2xx response — and
callers (app/routers/verification.py, app/routers/admin.py) are expected to
catch MLServiceUnavailableError and fall back to the mock modules in
app/modules/, so the demo never hard-depends on the heavy ML stack being up.
"""
import asyncio

import httpx

from app.config import ML_SERVICE_TIMEOUT_SECONDS, ML_SERVICE_URL


class MLServiceUnavailableError(Exception):
    pass


# ml-service can be briefly unreachable — mid-restart, or still loading its
# (large, slow-to-import) ML models on cold start — without actually being
# "down" for the purposes of this demo. A bare ConnectError on the first
# attempt used to fall back to mock data immediately, which is misleading
# (a real request would have succeeded seconds later). Retrying only on
# ConnectError/ConnectTimeout, never on a slow-but-connected response or an
# HTTP error status, keeps this from masking genuine failures — those still
# raise immediately, same as before.
_CONNECT_RETRY_ATTEMPTS = 3
_CONNECT_RETRY_DELAY_SECONDS = 2.0


async def _post_with_connect_retry(url: str, **kwargs) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(_CONNECT_RETRY_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=ML_SERVICE_TIMEOUT_SECONDS) as client:
                resp = await client.post(url, **kwargs)
                resp.raise_for_status()
                return resp
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            last_exc = exc
            if attempt < _CONNECT_RETRY_ATTEMPTS - 1:
                await asyncio.sleep(_CONNECT_RETRY_DELAY_SECONDS)
        except httpx.HTTPStatusError as exc:
            # str(exc) alone is just "Client error '400 Bad Request' for
            # url ..." — the actual reason (e.g. "exceeds 15 MB limit", or
            # "unrecognized magic bytes") is in the response body, which
            # ml-service always populates with a real detail message
            # (api/routes.py's _validate_upload). Without this, every
            # validation rejection looked identical and undiagnosable.
            try:
                detail = exc.response.json().get("detail")
            except Exception:
                detail = exc.response.text[:300] if exc.response is not None else None
            message = f"{exc} — {detail}" if detail else str(exc)
            raise MLServiceUnavailableError(message) from exc
        except httpx.TimeoutException as exc:
            raise MLServiceUnavailableError(str(exc)) from exc
    raise MLServiceUnavailableError(str(last_exc))


async def screen_document(
    document_bytes: bytes,
    document_filename: str,
    live_bytes: bytes | None = None,
    live_filename: str | None = None,
    document_type_hint: str | None = None,
) -> dict:
    """Calls ml-service's POST /screen. Returns its JSON body as-is (status
    "ok" | "quality_rejected" | "processing_error" — callers must check
    `status` themselves, same as ml-service's own contract)."""
    files = {"document_image": (document_filename or "document", document_bytes, "application/octet-stream")}
    if live_bytes is not None:
        files["live_capture_image"] = (live_filename or "live.jpg", live_bytes, "application/octet-stream")
    data = {}
    if document_type_hint:
        data["document_type_hint"] = document_type_hint

    resp = await _post_with_connect_retry(f"{ML_SERVICE_URL}/screen", files=files, data=data)
    return resp.json()


async def embed_face(image_bytes: bytes, filename: str = "face.jpg") -> list[float] | None:
    """Calls ml-service's POST /embed. Returns None if no face was detected
    (a valid, expected outcome) — raises MLServiceUnavailableError only if
    the service itself couldn't be reached."""
    files = {"image": (filename, image_bytes, "application/octet-stream")}
    resp = await _post_with_connect_retry(f"{ML_SERVICE_URL}/embed", files=files)
    return resp.json().get("embedding")


async def is_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{ML_SERVICE_URL}/health")
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False
