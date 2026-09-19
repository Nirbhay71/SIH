"""Measures non-MRZ OCR accuracy across deliberately degraded copies of one
real card image, so "improved OCR on poor photos" is a number, not a claim.

Usage (from ml-service/):
    python -m evaluation.ocr_robustness <card_image> [--baseline]

Ground truth below is for the specific card image this was developed against;
pass a different image plus --truth-json to evaluate another card. --baseline
runs the single-pass (no enhancement) path so before/after can be compared on
identical inputs.
"""
import argparse
import json
import os
import sys

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import torch  # noqa: F401,E402  — must import before paddle (see api/main.py)

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from src.ocr import field_ocr  # noqa: E402
from src.ocr.semantic_field_mapper import extract_semantic_fields  # noqa: E402
from src.pipeline import _lines_good_enough, _semantic_yield, _vote_fields  # noqa: E402

DEFAULT_TRUTH = {
    "name": "Darshan Niravbhai Buddhdev",
    "date_of_birth": "01/12/2006",
    "gender": "M",
    "mobile_number": "9425985139",
}


def degradations(img: np.ndarray) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(0)
    out = {"clean": img}
    out["blur"] = cv2.GaussianBlur(img, (0, 0), 1.8)
    out["noise"] = np.clip(img.astype(np.int16) + rng.normal(0, 22, img.shape), 0, 255).astype(np.uint8)
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 18])
    out["heavy_jpeg"] = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    out["low_contrast"] = cv2.convertScaleAbs(img, alpha=0.45, beta=90)
    h, w = img.shape[:2]
    out["half_res"] = cv2.resize(cv2.resize(img, (w // 2, h // 2)), (w, h))
    shade = np.tile(np.linspace(0.35, 1.0, w, dtype=np.float32), (h, 1))[..., None]
    out["uneven_light"] = np.clip(img.astype(np.float32) * shade, 0, 255).astype(np.uint8)
    return out


def _similar(a: str, b: str) -> bool:
    import difflib
    return difflib.SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio() >= 0.9


def score(fields: dict, truth: dict) -> tuple[int, int, dict]:
    """exact = identical value; close = >=90% similar (one garbled character).
    Both are reported: exact is what an automated check would need, close is
    what an officer can still work with — but they must not be conflated."""
    hits = {}
    exact = close = 0
    for key, expected in truth.items():
        got = fields[key].value if key in fields else None
        e = got is not None and got.strip().lower() == expected.strip().lower()
        c = e or (got is not None and _similar(got, expected))
        hits[key] = "exact" if e else ("close" if c else ("WRONG" if got else "missing"))
        exact += e
        close += c
    return exact, close, hits


def run(image_path: str, truth: dict, baseline: bool) -> dict:
    img = cv2.imread(image_path)
    if img is None:
        sys.exit(f"cannot read {image_path}")
    from src.schemas import FieldExtraction
    results = {}
    for name, variant in degradations(img).items():
        if baseline:
            original = field_ocr._VARIANTS
            field_ocr._VARIANTS = (original[0],)  # one pass, no enhancement: the pre-change behaviour
            try:
                candidates = field_ocr.ocr_document_candidates(variant)
            finally:
                field_ocr._VARIANTS = original
        else:
            candidates = field_ocr.ocr_document_candidates(variant, good_enough=_lines_good_enough)
        fields = _vote_fields(candidates) if candidates else {}
        exact, close, hits = score(fields, truth)
        results[name] = {"exact": exact, "close": close, "of": len(truth), "hits": hits}
        print(f"{name:14} exact {exact}/{len(truth)}  close {close}/{len(truth)}  {hits}", flush=True)
    ex = sum(r["exact"] for r in results.values())
    cl = sum(r["close"] for r in results.values())
    possible = sum(r["of"] for r in results.values())
    wrong = sum(1 for r in results.values() for v in r["hits"].values() if v == "WRONG")
    print(f"\nTOTAL exact {ex}/{possible} ({100*ex/possible:.0f}%)  close {cl}/{possible} ({100*cl/possible:.0f}%)  "
          f"confidently-WRONG {wrong}  mode={'baseline' if baseline else 'enhanced'}")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--truth-json")
    a = ap.parse_args()
    truth = json.load(open(a.truth_json, encoding="utf-8")) if a.truth_json else DEFAULT_TRUTH
    run(a.image, truth, a.baseline)
