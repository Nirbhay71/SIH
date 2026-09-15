"""
Module 3 — Tampering Detection ("Core AI Innovation" per the PS) — mock implementation.

The real version (teammate's build) would run: Error Level Analysis (ELA),
sensor-noise/PRNU consistency checks, font/spacing anomaly detection (CNN),
stamp/seal template matching, copy-move forgery detection (SIFT/ORB), and
EXIF/metadata analysis. See Part F.3 of the master spec for the full list —
this mock stands in for all of that and returns the same output shape a
real pipeline would.

Contract: run_tampering(document_image: bytes, force_tampered: bool) -> dict
"""
import io
import random

from PIL import Image, ImageDraw

REASONS = [
    "Compression-artifact discontinuity (ELA) around this region.",
    "Sensor noise fingerprint differs from the rest of the document (possible splice).",
    "Font/spacing anomaly consistent with digitally altered characters.",
    "Stamp does not match reference template shape/color.",
]


def run_tampering(document_image: bytes, force_tampered: bool = False) -> dict:
    random.seed(len(document_image) + (99 if force_tampered else 0))

    try:
        img = Image.open(io.BytesIO(document_image)).convert("RGB")
    except Exception:
        img = Image.new("RGB", (800, 500), color=(230, 230, 230))

    width, height = img.size
    flagged_regions = []

    if force_tampered:
        score = round(random.uniform(0.72, 0.95), 2)
        # Flag the photo region and the DOB field region.
        photo_box = (int(width * 0.05), int(height * 0.15), int(width * 0.30), int(height * 0.65))
        dob_box = (int(width * 0.40), int(height * 0.55), int(width * 0.75), int(height * 0.65))
        flagged_regions = [
            {"box": list(photo_box), "reason": REASONS[0]},
            {"box": list(dob_box), "reason": REASONS[2]},
        ]
    else:
        score = round(random.uniform(0.02, 0.15), 2)

    overlay = img.copy()
    draw = ImageDraw.Draw(overlay, "RGBA")
    for region in flagged_regions:
        draw.rectangle(region["box"], fill=(255, 0, 0, 90), outline=(255, 0, 0, 255), width=3)

    buf = io.BytesIO()
    overlay.save(buf, format="PNG")
    heatmap_bytes = buf.getvalue()

    return {
        "tampering_score": score,
        "flagged_regions": flagged_regions,
        "heatmap_bytes": heatmap_bytes,
    }
