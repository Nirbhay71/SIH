r"""
Generates a labeled batch of synthetic genuine/forged documents for
training the fusion model, using the same generator design already
verified (this session) to actually pass the real quality gate — textured
scan-noise background (a flat fill gets rejected as glare), a clean backing
panel behind printed text (raw text-on-noise reads as per-character
inconsistency to font_spacing_forensics.py), and a monospace field font
(matches real ID data-zone typography, minimizing that same false signal).

Complements — does not replace — the existing 70+70 genuine/forged set
(from this session's first training run). Writes with a distinct filename
prefix so nothing is overwritten.

Usage:
    cd ml-service
    .\venv\Scripts\python.exe training\generate_labeled_batch.py
"""
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DATA_DIR = Path(__file__).resolve().parent / "data"
GENUINE_DIR = DATA_DIR / "midv2020" / "scan_upright"
FORGED_DIR = DATA_DIR / "synthetic_forged"
GENUINE_DIR.mkdir(parents=True, exist_ok=True)
FORGED_DIR.mkdir(parents=True, exist_ok=True)

try:
    FONT = ImageFont.truetype("consola.ttf", 20)
except Exception:
    FONT = ImageFont.load_default()

FIRST_NAMES_MALE = [
    "Ramesh", "Suresh", "Deepak", "Arun", "Rajesh", "Ganesh", "Hari", "Binod",
    "Mohan", "Rajan", "Vikram", "Santosh", "Manoj", "Gopal", "Bhim", "Dorje",
    "Tenzin", "Karma", "Pema", "Dawa", "Mingma", "Nabin", "Devendra", "Rakesh",
]
FIRST_NAMES_FEMALE = [
    "Anjali", "Priya", "Sita", "Nisha", "Lakshmi", "Meena", "Pooja", "Neha",
    "Kavita", "Sunita", "Dolma", "Dipa", "Kamala", "Radha", "Sarita", "Gita",
]
LAST_NAMES = [
    "Thapa", "Gurung", "Rai", "Sharma", "Magar", "Tamang", "Kumar", "Devi",
    "Wangchuk", "Adhikari", "Verma", "Dorji", "Prasad", "Kumari", "Chaudhary",
    "Mishra", "Lama", "Tshering", "Karki", "Sah", "Yadav", "Bhandari",
]
NATIONALITIES = ["IND", "NPL", "BTN"]
DOC_TYPES = ["passport", "visa", "national_id", "driving_license", "permit"]


def _random_name():
    first = random.choice(FIRST_NAMES_MALE if random.random() < 0.5 else FIRST_NAMES_FEMALE)
    return f"{first} {random.choice(LAST_NAMES)}"


def _base_canvas(seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    img = np.full((600, 900, 3), int(rng.integers(195, 225)), dtype=np.uint8)
    noise = rng.integers(-16, 16, img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(img)


def _draw_fields(draw: ImageDraw.ImageDraw, name: str, country: str, doc_number: str, dob: str, expiry: str) -> None:
    draw.rectangle([295, 35, 890, 285], fill=(238, 238, 235))
    lines = [
        f"REPUBLIC OF {country}",
        f"Name: {name}",
        f"Date of Birth: {dob}",
        f"Nationality: {country}",
        f"Passport No: {doc_number}",
        f"Date of Expiry: {expiry}",
    ]
    y = 40
    for line in lines:
        draw.text((300, y), line, fill=(10, 10, 10), font=FONT)
        y += 35


def _draw_mrz(draw: ImageDraw.ImageDraw, country: str, surname: str, given: str, doc_number: str) -> None:
    mrz1 = (f"P<{country}{surname}<<{given.replace(' ', '<')}" + "<" * 40)[:44]
    mrz2 = (f"{doc_number}<4{country}9001156M3203201<<<<<<<<<<<<<<02" + "<" * 44)[:44]
    draw.rectangle([20, 520, 880, 580], fill=(230, 230, 230))
    draw.text((30, 525), mrz1, fill=(0, 0, 0), font=FONT)
    draw.text((30, 550), mrz2, fill=(0, 0, 0), font=FONT)


def make_genuine(seed: int) -> Image.Image:
    random.seed(seed)
    name = _random_name()
    surname, given = name.split(" ", 1)
    country = random.choice(NATIONALITIES)
    doc_number = f"{country[0]}{random.randint(1000000, 9999999)}"
    dob = f"{random.randint(1,28):02d} JAN {random.randint(1965,2002)}"
    expiry = f"{random.randint(1,28):02d} MAR {random.randint(2027,2034)}"

    im = _base_canvas(seed=seed)
    draw = ImageDraw.Draw(im)
    # Real (unforged) ID photos still vary — print/scan quality, lighting,
    # lamination glare — so a fixed, identical photo-region rendering across
    # every "genuine" example taught the model to treat ANY deviation from
    # that one exact baseline as forgery (verified: this collapsed a real
    # genuine document's low-but-nonzero photo_tamper_score into a 98%
    # forgery classification — see train_fusion_model.py's REGULARIZATION
    # comment). Jittering color and adding mild legitimate per-photo noise
    # here — a different, gentler pattern than make_forged's harsh
    # full-region random-noise splice — gives the genuine class realistic
    # internal spread instead of one brittle point value.
    rng = np.random.default_rng(seed + 300000)
    skin = tuple(int(np.clip(c + rng.integers(-15, 15), 0, 255)) for c in (200, 170, 150))
    backdrop = tuple(int(np.clip(c + rng.integers(-15, 15), 0, 255)) for c in (120, 100, 90))
    draw.rectangle([40, 40, 260, 320], fill=backdrop)
    draw.ellipse([90, 90, 210, 210], fill=skin)
    if rng.random() < 0.5:
        arr = np.array(im)
        box = arr[40:320, 40:260]
        mild_noise = rng.integers(-10, 10, box.shape, dtype=np.int16)
        arr[40:320, 40:260] = np.clip(box.astype(np.int16) + mild_noise, 0, 255).astype(np.uint8)
        im = Image.fromarray(arr)
        draw = ImageDraw.Draw(im)
    _draw_fields(draw, name, country, doc_number, dob, expiry)
    _draw_mrz(draw, country, surname, given, doc_number)
    return im


def make_forged(seed: int) -> Image.Image:
    """Same construction as make_genuine, but with an actual pasted-texture
    photo-region splice and a redrawn (mismatched-sharpness) DOB field —
    the forgery this build's real tampering module (photo_tamper_score,
    font_spacing forensics) is designed to catch, not just a filename hint."""
    random.seed(seed + 100000)
    name = _random_name()
    surname, given = name.split(" ", 1)
    country = random.choice(NATIONALITIES)
    doc_number = f"{country[0]}{random.randint(1000000, 9999999)}"
    dob = f"{random.randint(1,28):02d} JAN {random.randint(1965,2002)}"
    expiry = f"{random.randint(1,28):02d} MAR {random.randint(2027,2034)}"

    im = _base_canvas(seed=seed + 100000)
    draw = ImageDraw.Draw(im)
    _draw_fields(draw, name, country, doc_number, dob, expiry)

    rng = np.random.default_rng(seed + 200000)
    arr = np.array(im)
    noise_patch = rng.integers(0, 255, (280, 220, 3), dtype=np.uint8)
    arr[40:320, 40:260] = noise_patch
    im = Image.fromarray(arr)
    draw = ImageDraw.Draw(im)

    draw.rectangle([420, 108, 620, 132], fill=(255, 255, 255))
    draw.text((422, 108), f"Date of Birth: {random.randint(1,28):02d} JAN {random.randint(1965,2002)}", fill=(0, 0, 0), font=FONT)

    _draw_mrz(draw, country, surname, given, doc_number)
    return im


def main(count: int = 175):
    for i in range(count):
        make_genuine(seed=i).save(GENUINE_DIR / f"seed_genuine_{i:04d}.jpg", quality=88)
    for i in range(count):
        make_forged(seed=i).save(FORGED_DIR / f"seed_forged_{i:04d}.png")
    print(f"Wrote {count} genuine to {GENUINE_DIR} and {count} forged to {FORGED_DIR}")


if __name__ == "__main__":
    main()
