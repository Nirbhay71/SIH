"""Generates the two demo sample documents referenced in Part I (Demo Script)
and Part F.3: a 'genuine' sample and a 'tampered' sample.

Written to be readable by the REAL ml-service pipeline, not just the mock
modules: real quality-gate checks (src/preprocessing/quality_gate.py) reject
flat/textureless images as glare, and real MRZ extraction (passporteye)
needs an actual ICAO-format two-line MRZ block to read — a solid-fill
placeholder with plain field labels (this script's previous version) passed
neither. Filenames still matter for the mock fallback path: the upload
endpoint uses the substring 'tampered' as the demo hint to force the mock
tampering/validation modules into their high-risk branch (Part F.3) when
ml-service is unreachable.

Run once: python generate_samples.py — writes to both backend/sample_documents/
(this script's traditional output dir) and frontend/public/samples/ (what the
frontend's "Use Genuine/Tampered Sample" buttons actually fetch from).
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BACKEND_OUT_DIR = Path(__file__).parent / "sample_documents"
FRONTEND_OUT_DIR = Path(__file__).parent.parent / "frontend" / "public" / "samples"
BACKEND_OUT_DIR.mkdir(exist_ok=True)
FRONTEND_OUT_DIR.mkdir(parents=True, exist_ok=True)

try:
    # Real ID/passport data zones are printed in a monospace/OCR-friendly
    # font specifically because it has near-zero per-character width and
    # spacing variance — a proportional font like Arial has natural kerning
    # variance that the real tampering module's font/spacing forensics
    # (src/tampering/font_spacing_forensics.py) reads as suspicious, which
    # isn't representative of what these checks are meant to catch.
    FONT = ImageFont.truetype("consola.ttf", 20)
except Exception:
    FONT = ImageFont.load_default()

NAME = "SHARMA RAVI KUMAR"
SURNAME, GIVEN = "SHARMA", "RAVI KUMAR"
COUNTRY = "IND"
DOC_NUMBER = "N1234567"


def _base_canvas(seed: int) -> Image.Image:
    """A textured (not flat-fill) background — real-camera-scan-like noise
    so the real quality gate's blur/glare checks don't reject it outright."""
    rng = np.random.default_rng(seed)
    img = np.full((600, 900, 3), 212, dtype=np.uint8)
    noise = rng.integers(-16, 16, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(img)


def _draw_common_fields(draw: ImageDraw.ImageDraw) -> None:
    # The base canvas's per-pixel scan-noise texture (added so the real
    # quality gate doesn't reject a flat image as glare) bleeds into glyph
    # edges when text is drawn directly over it, which the tampering
    # module's edge-sharpness/ink-consistency forensics read as
    # per-character inconsistency — a real ID's printed data panel is
    # cleaner than its surrounding card stock anyway, so give the field
    # text a clean backing panel instead of drawing straight onto the noise.
    draw.rectangle([295, 35, 890, 285], fill=(238, 238, 235))
    lines = [
        f"REPUBLIC OF {COUNTRY}",
        f"Name: {NAME}",
        "Date of Birth: 15 JAN 1990",
        f"Nationality: {COUNTRY}",
        f"Passport No: {DOC_NUMBER}",
        "Date of Expiry: 20 MAR 2032",
    ]
    y = 40
    for line in lines:
        draw.text((300, y), line, fill=(10, 10, 10), font=FONT)
        y += 35


def _draw_mrz(draw: ImageDraw.ImageDraw) -> None:
    mrz1 = f"P<{COUNTRY}{SURNAME}<<{GIVEN.replace(' ', '<')}" + "<" * 40
    mrz1 = mrz1[:44]
    mrz2 = f"{DOC_NUMBER}<4{COUNTRY}9001156M3203201<<<<<<<<<<<<<<02"
    mrz2 = (mrz2 + "<" * 44)[:44]
    draw.rectangle([20, 520, 880, 580], fill=(230, 230, 230))
    draw.text((30, 525), mrz1, fill=(0, 0, 0), font=FONT)
    draw.text((30, 550), mrz2, fill=(0, 0, 0), font=FONT)


def make_genuine() -> Image.Image:
    im = _base_canvas(seed=42)
    draw = ImageDraw.Draw(im)
    draw.rectangle([40, 40, 260, 320], fill=(120, 100, 90))
    draw.ellipse([90, 90, 210, 210], fill=(200, 170, 150))
    _draw_common_fields(draw)
    _draw_mrz(draw)
    return im


def make_tampered() -> Image.Image:
    """Same document, but with an actual pasted-texture photo-region splice
    and a redrawn (mismatched-sharpness) DOB field — the same forgery
    simulation training/prepare_dataset.py uses — so the real tampering
    module's photo_tamper_score / text_manipulation_score genuinely differ
    from the genuine sample, not just the filename hint."""
    im = _base_canvas(seed=99)
    draw = ImageDraw.Draw(im)
    _draw_common_fields(draw)

    rng = np.random.default_rng(7)
    arr = np.array(im)
    # Spliced photo region: mismatched noise patch, not the smooth gradient
    # the rest of the "photo" box would have.
    noise_patch = rng.integers(0, 255, (280, 220, 3), dtype=np.uint8)
    arr[40:320, 40:260] = noise_patch
    im = Image.fromarray(arr)
    draw = ImageDraw.Draw(im)

    # Redrawn DOB field at a different (sharper, mismatched) rendering.
    draw.rectangle([420, 108, 620, 132], fill=(255, 255, 255))
    draw.text((422, 108), "Date of Birth: 01 JAN 1999", fill=(0, 0, 0), font=FONT)

    _draw_mrz(draw)
    return im


def main():
    genuine = make_genuine()
    tampered = make_tampered()

    for out_dir in (BACKEND_OUT_DIR, FRONTEND_OUT_DIR):
        genuine.save(out_dir / "sample_genuine.png")
        tampered.save(out_dir / "sample_tampered_document.png")

    print(f"Wrote sample documents to {BACKEND_OUT_DIR} and {FRONTEND_OUT_DIR}")


if __name__ == "__main__":
    main()
