"""Section 5.3 — free-text field extraction (non-MRZ documents: OCI cards,
border permits, e-Visa printouts) via PaddleOCR.

Run per field-zone crop (Section 5.1 step 5), never on the whole document
at once — field-scoped OCR measurably outperforms whole-document OCR
because it removes ambiguity about which text belongs to which field.

Multi-language note (Section 5.3): the installed PaddleOCR version
(2.8.1, pinned in requirements.txt) requires a separate `PaddleOCR`
instance per language rather than a single multi-lingual instance, so we
run English and Hindi passes independently per crop and keep whichever
result has higher mean confidence. This is documented here and in
README.md rather than assumed — different PaddleOCR versions handle this
differently.
"""
import logging

import numpy as np

logger = logging.getLogger("src.ocr")

_ENGINES: dict[str, object] = {}


def _get_engine(lang: str):
    if lang not in _ENGINES:
        from paddleocr import PaddleOCR

        _ENGINES[lang] = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
    return _ENGINES[lang]


class FieldOCRResult:
    def __init__(self, text: str | None, confidence: float):
        self.text = text
        self.confidence = confidence


def ocr_field_crop(crop: np.ndarray, languages: tuple[str, ...] = ("en", "hi")) -> FieldOCRResult:
    """Runs OCR on a single field-zone crop, trying each language in
    `languages` and keeping the highest-confidence result. Returns
    confidence=0.0 (never raises) if PaddleOCR is unavailable or no text
    is detected — an empty/low-confidence result is a valid, expected
    outcome, not an error."""
    try:
        import paddleocr  # noqa: F401
    except ImportError:
        logger.warning("paddleocr is not installed; free-text field OCR unavailable in this environment.")
        return FieldOCRResult(text=None, confidence=0.0)

    best = FieldOCRResult(text=None, confidence=0.0)
    for lang in languages:
        try:
            engine = _get_engine(lang)
            result = engine.ocr(crop, cls=True)
        except Exception as exc:  # PaddleOCR's own runtime errors on a degenerate crop
            logger.warning("PaddleOCR failed for lang=%s: %s", lang, exc)
            continue

        if not result or not result[0]:
            continue

        lines = result[0]
        texts = [line[1][0] for line in lines]
        confidences = [line[1][1] for line in lines]
        if not texts:
            continue

        combined_text = " ".join(texts)
        mean_confidence = float(np.mean(confidences))
        if mean_confidence > best.confidence:
            best = FieldOCRResult(text=combined_text, confidence=mean_confidence)

    return best
