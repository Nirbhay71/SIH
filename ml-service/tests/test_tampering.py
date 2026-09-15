"""Section 10.4 — each of the four sub-checks must score a known-tampered
sample higher than a matched genuine sample. Uses only opencv/numpy/PIL,
so this runs without the optional torch/timm forgery-classifier
dependency installed."""
import cv2
import numpy as np

from src.schemas import BoundingBox
from src.tampering.metadata_forensics import analyze_metadata
from src.tampering.photo_boundary_check import photo_tamper_score
from src.tampering.font_spacing_forensics import text_manipulation_score


def _document_with_photo(photo_color, edge_style="smooth") -> np.ndarray:
    img = np.full((400, 600, 3), 230, dtype=np.uint8)
    x, y, w, h = 30, 30, 150, 200
    if edge_style == "smooth":
        for i in range(20):
            alpha = i / 20
            cv2.rectangle(img, (x - i, y - i), (x + w + i, y + h + i), photo_color, 1)
    cv2.rectangle(img, (x, y, ), (x + w, y + h), photo_color, -1)
    if edge_style == "sharp":
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 0), 2)  # hard, high-contrast pasted-looking edge
    return img


def test_photo_tamper_score_higher_for_sharp_pasted_edge():
    genuine = _document_with_photo((150, 140, 130), edge_style="smooth")
    tampered = _document_with_photo((20, 20, 200), edge_style="sharp")  # jarring color + hard edge
    box = BoundingBox(x=30, y=30, width=150, height=200)

    genuine_score = photo_tamper_score(genuine, box)
    tampered_score = photo_tamper_score(tampered, box)

    assert tampered_score >= genuine_score


def test_photo_tamper_score_zero_without_photo_box():
    img = _document_with_photo((150, 140, 130))
    assert photo_tamper_score(img, None) == 0.0


def _uniform_text_field() -> np.ndarray:
    img = np.full((40, 300, 3), 255, dtype=np.uint8)
    for i in range(8):
        x = 10 + i * 30
        cv2.rectangle(img, (x, 10), (x + 15, 30), (0, 0, 0), -1)
    return img


def _irregular_text_field() -> np.ndarray:
    img = np.full((40, 300, 3), 255, dtype=np.uint8)
    positions = [10, 42, 68, 130, 145, 210, 220, 270]
    heights = [20, 8, 25, 12, 22, 6, 24, 14]
    for x, h in zip(positions, heights):
        cv2.rectangle(img, (x, 30 - h), (x + 12, 30), (0, 0, 0), -1)
    return img


def test_text_manipulation_score_higher_for_irregular_field():
    uniform_score = text_manipulation_score(_uniform_text_field())
    irregular_score = text_manipulation_score(_irregular_text_field())
    assert irregular_score >= uniform_score


def test_metadata_flags_known_editing_software():
    # Build a minimal JPEG with a Software EXIF tag via Pillow.
    import io
    from PIL import Image
    import piexif

    img = Image.new("RGB", (100, 100), (255, 255, 255))
    exif_dict = {"0th": {piexif.ImageIFD.Software: "Adobe Photoshop 25.0"}}
    exif_bytes = piexif.dump(exif_dict)
    buf = io.BytesIO()
    img.save(buf, "jpeg", exif=exif_bytes)

    count, flags = analyze_metadata(buf.getvalue())
    assert count >= 1
    assert any("photoshop" in f for f in flags)


def test_metadata_no_flags_when_absent():
    import io
    from PIL import Image

    img = Image.new("RGB", (100, 100), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "png")  # PNG carries no EXIF

    count, flags = analyze_metadata(buf.getvalue())
    assert count == 0
    assert flags == []
