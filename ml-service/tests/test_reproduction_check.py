"""Photocopy / monochrome-reproduction detection. Fixtures model the two
signatures the check keys on: absent chroma, and bi-level tones."""
import cv2
import numpy as np

from src.preprocessing.reproduction_check import reproduction_flags


def _colour_original() -> np.ndarray:
    rng = np.random.default_rng(0)
    img = np.full((500, 800, 3), (200, 215, 225), dtype=np.uint8)          # warm paper
    img[40:200, 40:220] = (150, 110, 90)                                   # a coloured photo block
    img[60:90, 300:700] = (60, 60, 160)                                    # coloured header band
    for y in range(230, 460, 34):
        cv2.putText(img, "SAMPLE FIELD 1234567", (300, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 30, 30), 2)
    noise = rng.normal(0, 6, img.shape)
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def _binarised_copy(img: np.ndarray) -> np.ndarray:
    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (0, 0), 0.8)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 14)
    return cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)


def test_colour_original_is_not_flagged():
    assert reproduction_flags(_colour_original()) == []


def test_binarised_photocopy_is_flagged_both_ways():
    flags = reproduction_flags(_binarised_copy(_colour_original()))
    assert "monochrome_reproduction" in flags
    assert "bilevel_reproduction" in flags


def test_greyscale_scan_is_monochrome_but_not_bilevel():
    """A greyscale scan keeps its mid-tones (the photo), so it is a
    monochrome reproduction but not a photocopier-style threshold output."""
    grey = cv2.cvtColor(cv2.cvtColor(_colour_original(), cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    flags = reproduction_flags(grey)
    assert "monochrome_reproduction" in flags
    assert "bilevel_reproduction" not in flags


def test_pale_washed_out_original_is_not_accused():
    """Low contrast is not the same as no colour: a faded original still has
    chroma and must not be called a copy."""
    faded = cv2.convertScaleAbs(_colour_original(), alpha=0.6, beta=80)
    assert reproduction_flags(faded) == []


def test_degenerate_input_never_raises():
    assert reproduction_flags(np.zeros((0, 0, 3), dtype=np.uint8)) == []
