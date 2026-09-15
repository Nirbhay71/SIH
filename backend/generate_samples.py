"""Generates the two demo sample documents referenced in Part I (Demo Script)
and Part F.3: a 'genuine' sample and a 'tampered' sample. Filenames matter —
the upload endpoint uses the substring 'tampered' as the demo hint to force
the mock tampering/validation modules into their high-risk branch (Part F.3).
Run once: python generate_samples.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).parent / "sample_documents"
OUT_DIR.mkdir(exist_ok=True)


def draw_document(title: str) -> Image.Image:
    img = Image.new("RGB", (900, 560), (245, 245, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 889, 549], outline=(30, 60, 120), width=4)
    try:
        font_big = ImageFont.truetype("arial.ttf", 28)
        font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        font_big = ImageFont.load_default()
        font = ImageFont.load_default()

    draw.text((40, 30), f"REPUBLIC OF DEMOSTAN — {title}", fill=(30, 60, 120), font=font_big)
    draw.rectangle([40, 90, 260, 340], fill=(210, 210, 210), outline=(0, 0, 0))
    draw.text((70, 200), "PHOTO", fill=(90, 90, 90), font=font)

    fields = [
        ("Name", "Bikram Lama"),
        ("Document No.", "N2086907"),
        ("Nationality", "Nepali"),
        ("Date of Birth", "04 JUN 1975"),
        ("Date of Issue", "03 FEB 2023"),
        ("Date of Expiry", "31 JAN 2033"),
        ("Gender", "M"),
    ]
    y = 100
    for label, value in fields:
        draw.text((300, y), f"{label}:", fill=(30, 30, 30), font=font)
        draw.text((520, y), value, fill=(0, 0, 0), font=font)
        y += 40

    return img


def main():
    genuine = draw_document("NATIONAL PERMIT (GENUINE SAMPLE)")
    genuine.save(OUT_DIR / "sample_genuine.png")

    tampered = draw_document("NATIONAL PERMIT (DEMO SAMPLE)")
    draw = ImageDraw.Draw(tampered, "RGBA")
    # Visibly redraw the photo box and DOB row to represent a swapped photo
    # and an altered DOB field for the live demo narration.
    draw.rectangle([40, 90, 260, 340], fill=(180, 140, 140, 255), outline=(200, 0, 0), width=3)
    draw.text((70, 200), "SWAPPED", fill=(120, 0, 0))
    draw.rectangle([510, 178, 700, 202], outline=(200, 0, 0), width=2)
    tampered.save(OUT_DIR / "sample_tampered_document.png")

    print(f"Wrote sample documents to {OUT_DIR}")


if __name__ == "__main__":
    main()
