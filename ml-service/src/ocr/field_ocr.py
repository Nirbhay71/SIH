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


class OCRLine:
    def __init__(self, text: str, confidence: float, y_center: float, x_left: float, height: float = 0.0):
        self.text = text
        self.confidence = confidence
        self.y_center = y_center
        self.x_left = x_left
        self.height = height


# Two detections belong to the same printed line if their vertical centres
# are closer than this fraction of typical glyph height. PaddleOCR's
# detector often splits a single printed line into separate word boxes
# ("Darshan" / "Niravbhai" / "Buddhdev"), and those boxes' y-centres wobble
# by a few pixels — sorting purely by y then scrambles word order and, worse,
# separates a label from its value ("DOB:" ending up nowhere near the date),
# which is exactly what the semantic mapper needs to see together.
_SAME_LINE_Y_TOLERANCE = 0.6


def _group_into_lines(boxes: list[OCRLine]) -> list[OCRLine]:
    if not boxes:
        return []

    heights = [b.height for b in boxes if b.height > 0]
    median_height = sorted(heights)[len(heights) // 2] if heights else 10.0
    tolerance = max(median_height * _SAME_LINE_Y_TOLERANCE, 1.0)

    grouped: list[list[OCRLine]] = []
    for box in sorted(boxes, key=lambda b: b.y_center):
        if grouped and abs(box.y_center - grouped[-1][0].y_center) <= tolerance:
            grouped[-1].append(box)
        else:
            grouped.append([box])

    lines: list[OCRLine] = []
    for group in grouped:
        group.sort(key=lambda b: b.x_left)
        lines.append(OCRLine(
            text=" ".join(b.text for b in group),
            confidence=float(np.mean([b.confidence for b in group])),
            y_center=float(np.mean([b.y_center for b in group])),
            x_left=min(b.x_left for b in group),
            height=float(np.mean([b.height for b in group])),
        ))
    return lines


# PaddleOCR's recognition head wants roughly 32px-tall text to work well.
# On a phone photo of an ID card the printed fields are often 10-15px tall,
# which is where the garbled reads come from ("तIENDOB" for "DOB", etc.) —
# upscaling first measurably improves recognition, and costs nothing on
# images that are already large. Capped so a genuinely large scan isn't
# blown up into a multi-second OCR pass for no accuracy gain.
_UPSCALE_TARGET_SHORT_SIDE_PX = 1400
_UPSCALE_MAX_FACTOR = 4.0


def _upscale_for_ocr(image: np.ndarray) -> np.ndarray:
    import cv2

    h, w = image.shape[:2]
    short_side = min(h, w)
    if short_side <= 0 or short_side >= _UPSCALE_TARGET_SHORT_SIDE_PX:
        return image
    factor = min(_UPSCALE_TARGET_SHORT_SIDE_PX / short_side, _UPSCALE_MAX_FACTOR)
    # INTER_CUBIC over INTER_LINEAR: preserves glyph edges better at the
    # 2-4x factors this hits in practice, which is what the recognizer needs.
    return cv2.resize(image, (int(w * factor), int(h * factor)), interpolation=cv2.INTER_CUBIC)


def ocr_full_document(image: np.ndarray, languages: tuple[str, ...] = ("en", "hi")) -> list[OCRLine]:
    """Runs PaddleOCR over the WHOLE document image and returns every text
    line it detects, in reading order (top-to-bottom, then left-to-right).

    This is the preferred path for non-MRZ documents, replacing the older
    per-crop approach (`ocr_field_crop` below, kept for callers that
    already have a tight crop). Reason: PaddleOCR ships its own trained
    text *detector*, which locates text lines far more accurately than
    this build's heuristic contour/morphology zone-finder in
    src/preprocessing/region_segmentation.py. Feeding that heuristic's
    crops to PaddleOCR threw away the good detector and kept the crude
    one, which is what produced characters sliced mid-glyph.

    Returns [] (never raises) if PaddleOCR is unavailable or nothing is
    detected — an empty result is a valid outcome, not an error.
    """
    try:
        import paddleocr  # noqa: F401
    except ImportError:
        logger.warning("paddleocr is not installed; full-document OCR unavailable in this environment.")
        return []

    prepared = _upscale_for_ocr(image)

    best_lines: list[OCRLine] = []
    best_mean_confidence = -1.0
    for lang in languages:
        try:
            engine = _get_engine(lang)
            result = engine.ocr(prepared, cls=True)
        except Exception as exc:
            logger.warning("PaddleOCR full-document pass failed for lang=%s: %s", lang, exc)
            continue

        if not result or not result[0]:
            continue

        lines: list[OCRLine] = []
        for entry in result[0]:
            box, (text, confidence) = entry[0], entry[1]
            if not text or not text.strip():
                continue
            ys = [point[1] for point in box]
            xs = [point[0] for point in box]
            lines.append(OCRLine(
                text=text.strip(),
                confidence=float(confidence),
                y_center=float(sum(ys) / len(ys)),
                x_left=float(min(xs)),
                height=float(max(ys) - min(ys)),
            ))

        if not lines:
            continue

        mean_confidence = float(np.mean([line.confidence for line in lines]))
        # Prefer the language pass that read the most text confidently —
        # a pass that finds 12 lines at 0.9 beats one finding 2 at 0.95.
        score = mean_confidence * min(len(lines), 20)
        if score > best_mean_confidence:
            best_mean_confidence = score
            best_lines = lines

    return _group_into_lines(best_lines)


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
