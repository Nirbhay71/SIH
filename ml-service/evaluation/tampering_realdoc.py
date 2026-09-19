"""Tampering-detector validation against forgeries built from REAL documents.

The repo has no real forged documents, and its synthetic genuine/forged set
was made by the same script that defined what "forged" means — a detector
can score well there by learning the generator, not by detecting tampering.
This builds forgeries from real, genuine documents instead (photo swap, text
overwrite, copy-move, local recompression, blur patch) and asks the honest
question: does the detector separate them from the untouched originals?

Genuine and forged inputs are both decoded and re-saved as lossless PNG
before analysis, so file format / JPEG history can't act as a giveaway.

    python -m evaluation.tampering_realdoc            # print raw scores
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import torch  # noqa: F401,E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from src.pipeline import preprocess  # noqa: E402
from src.preprocessing.format_normalization import normalize_to_array  # noqa: E402
from src.tampering.detect import run_tampering_detection  # noqa: E402

REAL_DIR = Path(__file__).resolve().parent / "real_docs"


def _png_bytes(img: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


def features(img: np.ndarray) -> dict | None:
    raw = _png_bytes(img)
    pre = preprocess(raw, "doc.png")
    if pre["status"] != "ok":
        return None
    image = pre["image"]
    crops = {f"field_{i}": image[b.y:b.y + b.height, b.x:b.x + b.width] for i, b in enumerate(pre["field_boxes"][:10])}
    t = run_tampering_detection(image=image, original_bytes=raw, photo_box=pre["photo_box"],
                                field_crops=crops, stamp_crops=[], reference_stamps=[])
    return {"photo": t.photo_tamper_score, "text": t.text_manipulation_score_max, "meta": float(t.metadata_flag_count)}


def forgeries(img: np.ndarray, seed: int = 0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    pre = preprocess(_png_bytes(img), "doc.png")
    work = pre["image"].copy() if pre["status"] == "ok" else img.copy()
    h, w = work.shape[:2]
    out: dict[str, np.ndarray] = {}

    def region(frac_w=0.3, frac_h=0.08):
        rw, rh = int(w * frac_w), max(int(h * frac_h), 12)
        x, y = int(rng.integers(0, max(w - rw, 1))), int(rng.integers(int(h * 0.1), max(int(h * 0.9) - rh, int(h * 0.1) + 1)))
        return x, y, rw, rh

    # text overwrite: paint out a band, retype digits in a different font
    x, y, rw, rh = region()
    f = work.copy()
    f[y:y + rh, x:x + rw] = np.median(work[y:y + rh, x:x + rw].reshape(-1, 3), axis=0).astype(np.uint8)
    cv2.putText(f, "4839 2017 5526", (x + 4, y + int(rh * 0.75)), cv2.FONT_HERSHEY_SIMPLEX, rh / 32, (20, 20, 20), max(1, rh // 14), cv2.LINE_AA)
    out["text_overwrite"] = f

    # copy-move: duplicate a patch elsewhere on the same document
    x1, y1, rw, rh = region(0.25, 0.12)
    x2, y2, _, _ = region(0.25, 0.12)
    f = work.copy()
    f[y2:y2 + rh, x2:x2 + rw] = work[y1:y1 + rh, x1:x1 + rw]
    out["copy_move"] = f

    # local recompression: a band that was saved at a different JPEG quality
    x, y, rw, rh = region(0.5, 0.15)
    f = work.copy()
    ok, enc = cv2.imencode(".jpg", work[y:y + rh, x:x + rw], [cv2.IMWRITE_JPEG_QUALITY, 22])
    f[y:y + rh, x:x + rw] = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    out["local_recompress"] = f

    # blur patch: smeared region (inpaint-and-rewrite residue)
    x, y, rw, rh = region(0.3, 0.1)
    f = work.copy()
    f[y:y + rh, x:x + rw] = cv2.GaussianBlur(work[y:y + rh, x:x + rw], (0, 0), 3.5)
    out["blur_patch"] = f

    # photo swap: paste unrelated content into the detected photo region
    if pre["status"] == "ok" and pre["photo_box"] is not None:
        b = pre["photo_box"]
        patch = np.tile(np.linspace(60, 200, b.width, dtype=np.uint8), (b.height, 1))
        patch = cv2.merge([patch, np.roll(patch, 9, 1), np.roll(patch, 21, 1)])
        f = work.copy()
        f[b.y:b.y + b.height, b.x:b.x + b.width] = patch
        out["photo_swap"] = f
    return out


def load_real() -> dict[str, np.ndarray]:
    docs = {}
    for p in sorted(REAL_DIR.glob("*")):
        if p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".webp"}:
            docs[p.stem] = normalize_to_array(p.read_bytes(), p.name)
    return docs


if __name__ == "__main__":
    docs = load_real()
    if not docs:
        sys.exit(f"put real genuine documents in {REAL_DIR}")
    print(f"{'document':24} {'kind':18} photo   text    meta")
    for name, img in docs.items():
        g = features(img)
        print(f"{name:24} {'GENUINE':18} " + (f"{g['photo']:.3f}  {g['text']:.3f}  {g['meta']:.0f}" if g else "rejected"))
        for kind, f_img in forgeries(img).items():
            r = features(f_img)
            print(f"{'':24} {kind:18} " + (f"{r['photo']:.3f}  {r['text']:.3f}  {r['meta']:.0f}" if r else "rejected"))
