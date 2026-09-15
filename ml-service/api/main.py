"""FastAPI test harness (Section 9A). This is a test/demo harness only —
see Section 2's non-goals and README.md for what a production deployment
would add in front of this (auth, a real API gateway, TLS termination)."""
import logging
import os

from fastapi import FastAPI

from api.routes import router

logging.basicConfig(level=os.getenv("ML_SERVICE_LOG_LEVEL", "INFO"))
for module in ("src.ocr", "src.validation", "src.tampering", "src.face", "src.fusion"):
    logging.getLogger(module).setLevel(os.getenv("ML_SERVICE_LOG_LEVEL", "INFO"))

app = FastAPI(
    title="AI-Based Fake Identity & Document Screening System — ML Service",
    description="Machine-learning core for SIH PS 26188. See docs/LIMITATIONS.md before treating any output as production-validated.",
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
