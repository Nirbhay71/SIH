"""Startup checks, security headers and a small rate limiter.

Nothing here changes what the app does in development — it makes the
insecure demo defaults *visible* and, in production, *impossible to ship*.
"""
import logging
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.config import (
    AUTH_RATE_LIMIT_PER_MINUTE,
    BEHIND_TLS_PROXY,
    CORS_ORIGINS,
    IS_PRODUCTION,
    USING_DEFAULT_ADMIN_PASSWORD,
)

logger = logging.getLogger("app.security")


def enforce_startup_policy() -> None:
    problems = []
    if USING_DEFAULT_ADMIN_PASSWORD:
        problems.append("ADMIN_PASSWORD is the built-in demo default")
    if "*" in CORS_ORIGINS:
        problems.append("CORS_ORIGINS contains a wildcard")

    if not problems:
        return
    if IS_PRODUCTION:
        raise RuntimeError(
            "Refusing to start with APP_ENV=production: " + "; ".join(problems) + ". Set the corresponding env vars."
        )
    for problem in problems:
        logger.warning("INSECURE DEFAULT (allowed only because APP_ENV != production): %s", problem)


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # camera is needed by the capture pages; nothing else is.
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=(self)")
    if BEHIND_TLS_PROXY:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    """FastAPI dependency. Sliding one-minute window per client address."""
    client = request.client.host if request.client else "unknown"
    now = time.time()
    window = _hits[client]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= AUTH_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(429, "Too many requests. Try again shortly.")
    window.append(now)
