"""Section 10.4 — quality-gate behavior on deliberately blurry/glared/
well-formed synthetic sample images."""
import cv2
import numpy as np
import pytest

from src.preprocessing.quality_gate import check_quality


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


def test_blurry_image_rejected():
    passed, reason, score = check_quality(_blurry_document_image())
    assert not passed
    assert reason == "blur"
    assert score is not None


def test_glare_image_rejected():
    passed, reason, score = check_quality(_glare_document_image())
    assert not passed
    assert reason == "glare"
    assert score is not None
