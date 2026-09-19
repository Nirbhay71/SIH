"""Detects likely photocopies / monochrome reproductions of a document.

The India-Nepal rules require an *original* document — "any photocopy or
digital/PDF copy" is not accepted — and this system only ever sees images, so
it cannot know whether an image is a photo of an original or of a copy. What
it CAN detect is the physical signature of a monochrome reproduction, which
is stable and measurable:

  - a colour original (passport data page, Voter ID, ...) has real chroma;
    a black-and-white photocopy has none, and
  - a photocopier/threshold output is bi-level: nearly every pixel sits at a
    tonal extreme with almost no mid-tones, whereas an original carries a
    photo and gradients.

Measured on real documents (colour originals vs the same documents
binarised): originals kept mean saturation >= 5 and always retained
mid-tones; a binarised copy read chroma 0.0 with 100% of pixels at the
extremes. Thresholds sit in that gap, deliberately near the copy side, so a
merely pale or washed-out original is not accused of being a copy.

This is a heuristic for an officer's attention, not a verdict: a genuine
monochrome document, or a colour photocopy, will not be caught / will be
misjudged. It is therefore surfaced as a flag + validation failure, never as
an automatic rejection.
"""
import cv2
import numpy as np

# Colour is judged over "ink" pixels only (not near-black), so dark borders
# don't drag the mean down.
_MONOCHROME_MAX_CHROMA = 1.5
_MONOCHROME_MAX_COLOURFUL_FRACTION = 0.003
_BILEVEL_MIN_EXTREME_FRACTION = 0.985
_BILEVEL_MAX_MIDTONE_FRACTION = 0.01


def reproduction_flags(image_bgr: np.ndarray) -> list[str]:
    if image_bgr is None or image_bgr.size == 0 or image_bgr.ndim != 3:
        return []

    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    ink = hsv[..., 2] > 40
    chroma = float(hsv[..., 1][ink].mean()) if ink.any() else 0.0
    colourful = float(((hsv[..., 1] > 45) & (hsv[..., 2] > 60)).mean())

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    hist = np.bincount(gray.ravel(), minlength=256) / gray.size
    extreme = float(hist[:40].sum() + hist[215:].sum())
    midtone = float(hist[80:180].sum())

    flags = []
    if chroma <= _MONOCHROME_MAX_CHROMA and colourful <= _MONOCHROME_MAX_COLOURFUL_FRACTION:
        flags.append("monochrome_reproduction")
    if extreme >= _BILEVEL_MIN_EXTREME_FRACTION and midtone <= _BILEVEL_MAX_MIDTONE_FRACTION:
        flags.append("bilevel_reproduction")
    return flags
