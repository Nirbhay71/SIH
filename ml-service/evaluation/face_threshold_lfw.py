"""Calibrates / validates the face-match threshold on REAL faces.

The shipped threshold (face.match_distance_threshold: 0.58) was documented as
"recalibrated on synthetic placeholder pairs" — coloured blobs with no faces in
them, so it measured nothing about faces. LFW (Labeled Faces in the Wild) is
the standard public benchmark of real face pairs (same person / different
person), so this measures the production embedding function against it.

Uses ml-service's own get_embedding (ArcFace via DeepFace, RetinaFace detector)
so the number describes the real pipeline, not a stand-in. Pairs where either
face isn't detected are counted and reported, not silently dropped.

    python -m evaluation.face_threshold_lfw [--pairs-per-class 150]

Writes evaluation/reports/face_threshold_lfw.json.
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
# Deliberately NOT importing torch here (unlike api/main.py, which needs it
# before PaddleOCR): this script only uses TensorFlow via DeepFace, and loading
# a second OpenMP runtime next to TensorFlow's hung a 300-pair run at 75 pairs
# with zero CPU use. Passive waiting stops idle threads busy-spinning.
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")
os.environ.setdefault("KMP_BLOCKTIME", "0")

import numpy as np  # noqa: E402

REPORTS = Path(__file__).resolve().parent / "reports"


def cosine_distance(a, b) -> float:
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    return float(1.0 - np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main(pairs_per_class: int) -> dict:
    from sklearn.datasets import fetch_lfw_pairs
    from sklearn.metrics import roc_auc_score, roc_curve

    from src.face.face_verification import get_embedding

    data = fetch_lfw_pairs(subset="test", color=True, resize=1.0, slice_=None, download_if_missing=True)
    pairs, labels = data.pairs, data.target
    pos = np.where(labels == 1)[0][:pairs_per_class]
    neg = np.where(labels == 0)[0][:pairs_per_class]
    chosen = np.concatenate([pos, neg])

    def to_bgr(img):
        arr = img if img.max() > 1.5 else img * 255.0
        return np.ascontiguousarray(arr[..., ::-1].astype(np.uint8))

    distances, y, skipped = [], [], 0
    start = time.time()
    for n, idx in enumerate(chosen):
        e1, e2 = get_embedding(to_bgr(pairs[idx][0])), get_embedding(to_bgr(pairs[idx][1]))
        if e1 is None or e2 is None:
            skipped += 1
            continue
        distances.append(cosine_distance(e1, e2))
        y.append(int(labels[idx]))
        if n % 10 == 0:
            print(f"{n}/{len(chosen)}  ({time.time() - start:.0f}s)", flush=True)
            REPORTS.mkdir(exist_ok=True)
            (REPORTS / "face_threshold_lfw.partial.json").write_text(
                json.dumps({"done": n, "of": len(chosen), "distances": distances, "labels": y}), encoding="utf-8")

    d, y = np.array(distances), np.array(y)
    # y=1 means SAME person; a smaller distance should mean "same", so score = -distance.
    auc = float(roc_auc_score(y, -d))
    fpr, tpr, thr = roc_curve(y, -d)
    fnr = 1 - tpr
    eer_i = int(np.nanargmin(np.abs(fnr - fpr)))
    eer, eer_threshold = float((fpr[eer_i] + fnr[eer_i]) / 2), float(-thr[eer_i])

    def at_far(target):
        ok = np.where(fpr <= target)[0]
        i = ok[-1] if len(ok) else 0
        return {"far": float(fpr[i]), "tar": float(tpr[i]), "distance_threshold": float(-thr[i])}

    current = 0.58
    pred_same = d <= current
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "LFW pairs (test split), first %d same + first %d different" % (pairs_per_class, pairs_per_class),
        "pairs_evaluated": int(len(y)),
        "pairs_skipped_no_face_detected": int(skipped),
        "auc": auc,
        "equal_error_rate": eer,
        "eer_distance_threshold": eer_threshold,
        "at_far_1pct": at_far(0.01),
        "at_far_0_1pct": at_far(0.001),
        "currently_shipped_threshold": current,
        "shipped_threshold_false_accept_rate": float(pred_same[y == 0].mean()),
        "shipped_threshold_false_reject_rate": float((~pred_same[y == 1]).mean()),
        "same_person_distance_mean": float(d[y == 1].mean()),
        "different_person_distance_mean": float(d[y == 0].mean()),
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "face_threshold_lfw.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs-per-class", type=int, default=150)
    main(ap.parse_args().pairs_per_class)
