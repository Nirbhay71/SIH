"""FastAPI test harness (Section 9A). This is a test/demo harness only —
see Section 2's non-goals and README.md for what a production deployment
would add in front of this (auth, a real API gateway, TLS termination)."""
import logging
import os

# PaddlePaddle (pinned to protobuf<=3.20.2) and TensorFlow (requires
# protobuf>=3.20.3) need incompatible protobuf C-extension versions in this
# environment; forcing the pure-Python protobuf implementation lets both
# coexist in one process at a small deserialization-speed cost. Must be set
# before either library is imported anywhere in the process (both are
# imported lazily per-call in src/ocr/field_ocr.py and src/face/face_verification.py,
# so setting it here at process startup is early enough).
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

# Local Windows dev convenience: the Tesseract OCR binary (a system
# dependency of passporteye/pytesseract, not a pip package) installs here by
# default via winget/UB-Mannheim's installer but isn't added to PATH. Linux
# containers (see Dockerfile) install tesseract via apt, which does put it on
# PATH, so this is a no-op there.
_TESSERACT_WIN_DIR = r"C:\Program Files\Tesseract-OCR"
if os.name == "nt" and os.path.isdir(_TESSERACT_WIN_DIR) and _TESSERACT_WIN_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _TESSERACT_WIN_DIR + os.pathsep + os.environ.get("PATH", "")

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
