"""Loads every heavy model once, in the background, at service start.

Why this exists: the first request to touch each model used to pay its full
load time inline — DeepFace's detector, ArcFace and anti-spoofing models alone
took over 60 seconds on a cold start. The backend's request timeout is 60
seconds, so the first face verification after every restart timed out and the
backend silently substituted MOCK face analysis (a fabricated 94-97% "match"
with a passing liveness check). Warming here means the first real request is
as fast as the hundredth.

Runs in a daemon thread so the service accepts connections immediately;
/ready reports which models are loaded so a caller can tell "up" from "warm".
"""
import logging
import threading
import time

import numpy as np

logger = logging.getLogger("api.warmup")

STATE: dict[str, object] = {"started": False, "finished": False, "models": {}, "seconds": None}


def _step(name: str, fn) -> None:
    started = time.time()
    try:
        fn()
        STATE["models"][name] = {"ok": True, "seconds": round(time.time() - started, 1)}
        logger.info("warm-up: %s ready in %.1fs", name, time.time() - started)
    except Exception as exc:  # a model failing to warm must not stop the others, or the service
        STATE["models"][name] = {"ok": False, "error": str(exc)[:200]}
        logger.warning("warm-up: %s failed: %s", name, exc)


# The detector traces a separate compute graph per input size, so warming with
# one tiny image left the FIRST real request (a 640x480 webcam frame, a
# 768x1024 passport page) paying ~40s to build its graph — measured: 63s for
# the first face step vs ~19s for the next. These are the sizes real inputs arrive at.
_WARM_SIZES = ((224, 224), (480, 640), (720, 1280), (1024, 768))


def _face_models() -> None:
    from deepface import DeepFace

    for h, w in _WARM_SIZES:
        blank = np.full((h, w, 3), 127, dtype=np.uint8)
        # enforce_detection=False: there is no face in a blank image; the point
        # is only to force the detector, ArcFace and anti-spoofing to load and
        # trace at this input size.
        DeepFace.represent(blank, model_name="ArcFace", detector_backend="retinaface", enforce_detection=False)
        DeepFace.extract_faces(blank, detector_backend="retinaface", enforce_detection=False, anti_spoofing=True)


def _paddle_models() -> None:
    from src.ocr import field_ocr

    tiny = np.full((64, 256, 3), 255, dtype=np.uint8)
    for lang in ("en", "hi"):
        field_ocr._get_engine(lang).ocr(tiny, cls=True)


def _forgery_backbone() -> None:
    from src.tampering.forgery_classifier import _load_model

    _load_model()


def _run() -> None:
    begin = time.time()
    STATE["started"] = True
    for name, fn in (("face", _face_models), ("ocr", _paddle_models), ("forgery_backbone", _forgery_backbone)):
        _step(name, fn)
    STATE["seconds"] = round(time.time() - begin, 1)
    STATE["finished"] = True
    logger.info("warm-up complete in %.1fs", STATE["seconds"])


def start_in_background() -> None:
    if STATE["started"]:
        return
    threading.Thread(target=_run, name="model-warmup", daemon=True).start()
