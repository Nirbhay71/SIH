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


def _enhance_clahe(image: np.ndarray) -> np.ndarray:
    """Local contrast + mild sharpening — the fix for washed-out and slightly
    soft photos, where the recognizer's problem is faint strokes, not noise."""
    import cv2

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(l)
    boosted = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    blurred = cv2.GaussianBlur(boosted, (0, 0), 1.6)
    return cv2.addWeighted(boosted, 1.6, blurred, -0.6, 0)


def _enhance_denoise(image: np.ndarray) -> np.ndarray:
    """Denoise first, then contrast — for sensor-noise / heavy-JPEG photos,
    where sharpening alone would amplify the noise into false strokes."""
    import cv2

    return _enhance_clahe(cv2.fastNlMeansDenoisingColored(image, None, 7, 7, 7, 21))


def _enhance_binarize(image: np.ndarray) -> np.ndarray:
    """Adaptive threshold — for uneven lighting, shadows and photocopy-grey
    backgrounds, where a single global brightness makes text vanish."""
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


# Tried in order, cheapest-to-most-aggressive. "base" is always first.
_VARIANTS: tuple[tuple[str, object], ...] = (
    ("base", lambda img: img),
    ("clahe", _enhance_clahe),
    ("denoise", _enhance_denoise),
    ("binarize", _enhance_binarize),
)


def _ocr_pass(image: np.ndarray, languages: tuple[str, ...]) -> tuple[list[OCRLine], str | None]:
    """One PaddleOCR pass per language over `image`; returns the language
    pass that read the most text confidently, and which language that was."""
    best_lines: list[OCRLine] = []
    best_score = -1.0
    best_lang = None
    for lang in languages:
        try:
            result = _get_engine(lang).ocr(image, cls=True)
        except Exception as exc:
            logger.warning("PaddleOCR pass failed for lang=%s: %s", lang, exc)
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

        # A pass that finds 12 lines at 0.9 beats one finding 2 at 0.95.
        score = float(np.mean([l.confidence for l in lines])) * min(len(lines), 20)
        if score > best_score:
            best_score, best_lines, best_lang = score, lines, lang
    return best_lines, best_lang


def ocr_document_candidates(
    image: np.ndarray,
    languages: tuple[str, ...] = ("en", "hi"),
    good_enough=None,
) -> list[tuple[str, list[OCRLine]]]:
    """Every enhancement variant's OCR read, as [(variant_name, lines)].

    Callers vote across these rather than trusting any single one: on a
    poor photo each enhancement fixes some characters and breaks others, and
    which is which is unknowable per-image — but a value that several
    independently processed reads agree on is far more likely correct than
    one that appeared once. `good_enough(lines)` stops early after a variant
    that already reads cleanly, so a clean photo still pays for one pass.
    """
    try:
        import paddleocr  # noqa: F401
    except ImportError:
        logger.warning("paddleocr is not installed; full-document OCR unavailable in this environment.")
        return []

    prepared = _upscale_for_ocr(image)
    candidates: list[tuple[str, list[OCRLine]]] = []
    winning_lang: str | None = None

    for name, transform in _VARIANTS:
        try:
            variant_image = transform(prepared)
        except Exception as exc:
            logger.warning("OCR enhancement %r failed, skipping it: %s", name, exc)
            continue

        langs = languages if winning_lang is None else (winning_lang,)
        raw_lines, lang = _ocr_pass(variant_image, langs)
        if not raw_lines:
            continue
        if winning_lang is None:
            winning_lang = lang

        grouped = _group_into_lines(raw_lines)
        candidates.append((name, grouped))
        if good_enough is not None and good_enough(grouped):
            break

    return candidates


def ocr_full_document(
    image: np.ndarray,
    languages: tuple[str, ...] = ("en", "hi"),
    score_fn=None,
    good_enough=None,
) -> list[OCRLine]:
    """Runs PaddleOCR over the WHOLE document image and returns every text
    line it detects, in reading order.

    Poor-quality photos are handled by trying progressively more aggressive
    image enhancements (contrast/sharpen, denoise, adaptive threshold) and
    keeping whichever variant reads best — rather than one fixed pipeline
    that is wrong for half the ways a photo can be bad. The choice is
    driven by `score_fn(lines)` (the caller knows what "reads well" means:
    pipeline.py scores by how many real fields the lines yield, not just by
    OCR confidence, which is high even on confidently-wrong text).
    `good_enough(lines)` lets the caller stop early: a clean photo pays for
    exactly one pass, and only a poor one pays for the rest.

    PaddleOCR brings its own trained text detector, which locates lines far
    more accurately than the heuristic zone-finder in
    src/preprocessing/region_segmentation.py — hence whole-page, not crops.

    Returns [] (never raises) if PaddleOCR is unavailable or nothing is
    detected — an empty result is a valid outcome, not an error.
    """
    try:
        import paddleocr  # noqa: F401
    except ImportError:
        logger.warning("paddleocr is not installed; full-document OCR unavailable in this environment.")
        return []

    score_fn = score_fn or (lambda lines: float(np.mean([l.confidence for l in lines])) * min(len(lines), 20))

    prepared = _upscale_for_ocr(image)
    best_lines: list[OCRLine] = []
    best_score = float("-inf")
    winning_lang: str | None = None

    for name, transform in _VARIANTS:
        try:
            variant_image = transform(prepared)
        except Exception as exc:
            logger.warning("OCR enhancement %r failed, skipping it: %s", name, exc)
            continue

        # After the first pass, only the language that already won is worth
        # re-running — the others cost a full pass each for no new signal.
        langs = languages if winning_lang is None else (winning_lang,)
        raw_lines, lang = _ocr_pass(variant_image, langs)
        if not raw_lines:
            continue
        if winning_lang is None:
            winning_lang = lang

        grouped = _group_into_lines(raw_lines)
        score = score_fn(grouped)
        logger.info("OCR variant=%s lines=%d score=%.2f", name, len(grouped), score)
        if score > best_score:
            best_score, best_lines = score, grouped
        if good_enough is not None and good_enough(grouped):
            break

    return best_lines


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
