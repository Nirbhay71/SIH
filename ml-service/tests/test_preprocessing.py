"""Section 10.4 — quality-gate behavior on deliberately blurry/glared/
well-formed synthetic sample images.

check_quality() itself only hard-blocks a near-zero-pixel degenerate
image now (see quality_gate.py's module docstring for why blur/glare/
low-resolution no longer block extraction outright) — those are tested
via quality_flags() instead, which is always computed but never blocks."""
import cv2
import numpy as np
import pytest

from src.preprocessing.quality_gate import ABSOLUTE_MIN_DIMENSION_PX, check_quality, quality_flags


def _sharp_document_image() -> np.ndarray:
    img = np.full((600, 900, 3), 220, dtype=np.uint8)
    for i in range(0, 900, 15):
        cv2.line(img, (i, 0), (i, 600), (0, 0, 0), 1)
    for i in range(0, 600, 15):
        cv2.line(img, (0, i), (900, i), (0, 0, 0), 1)
    return img


def _blurry_document_image() -> np.ndarray:
    sharp = _sharp_document_image()
    return cv2.GaussianBlur(sharp, (31, 31), 15)


def _glare_document_image() -> np.ndarray:
    # Sharp grid pattern (keeps blur variance high) with a large near-white
    # glare patch overlaid on part of the frame (pushes glare fraction over
    # threshold without flattening the whole image).
    img = _sharp_document_image()
    cv2.rectangle(img, (0, 0), (900, 250), (255, 255, 255), -1)
    return img


def test_sharp_well_formed_image_passes():
    passed, reason, score = check_quality(_sharp_document_image())
    assert passed
    assert reason is None
    assert quality_flags(_sharp_document_image()) == []


def test_blurry_image_not_hard_blocked_but_flagged():
    passed, reason, score = check_quality(_blurry_document_image())
    assert passed  # no longer hard-blocked — extraction still proceeds
    assert reason is None
    assert "blur" in quality_flags(_blurry_document_image())


def test_glare_image_not_hard_blocked_but_flagged():
    passed, reason, score = check_quality(_glare_document_image())
    assert passed  # no longer hard-blocked — extraction still proceeds
    assert reason is None
    assert "glare" in quality_flags(_glare_document_image())


def test_degenerate_tiny_image_still_hard_blocked():
    tiny = np.full((ABSOLUTE_MIN_DIMENSION_PX - 1, ABSOLUTE_MIN_DIMENSION_PX - 1, 3), 200, dtype=np.uint8)
    passed, reason, score = check_quality(tiny)
    assert not passed
    assert reason == "low_resolution"
    assert score is not None
