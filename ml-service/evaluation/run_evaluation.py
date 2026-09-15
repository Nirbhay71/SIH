"""Section 10.5 — the full evaluation report. A deliverable, not just a
debugging tool: this is what demonstrates measured performance rather
than assumed performance.

Section 10.1: reports Precision, Recall, F1, AUC-ROC — Recall is the
headline metric given the stated cost asymmetry (a missed forgery is
worse than an unnecessary secondary inspection), but the others are
always reported alongside it, never omitted.

Section 10.2: per-forgery-type breakdown is mandatory, never a single
blended number.

Section 10.7: every run is timestamped and kept (never overwritten), so a
threshold/model change can be compared against the prior report.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix

from training.extract_features import OUTPUT_CSV

logger = logging.getLogger("evaluation.run_evaluation")
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def _binary_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray) -> dict:
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "auc_roc": float(roc_auc_score(y_true, y_score)) if len(set(y_true)) > 1 else None,
    }


def run_evaluation() -> Path:
    if not OUTPUT_CSV.exists():
        raise RuntimeError(f"Feature table not found at {OUTPUT_CSV}. Run training/extract_features.py first.")

    df = pd.read_csv(OUTPUT_CSV)
    y_true = df["label"].to_numpy(dtype=int)
    y_score = df["forgery_classifier_probability"].to_numpy(dtype=float)
    threshold = 0.4  # config/thresholds.yaml tampering.forgery_classifier_threshold
    y_pred = (y_score >= threshold).astype(int)

    overall = _binary_metrics(y_true, y_pred, y_score)

    per_type = {}
    for forgery_type, group in df.groupby("forgery_type"):
        if forgery_type == "none":
            continue
        combined = pd.concat([df[df["forgery_type"] == "none"], group])
        yt = combined["label"].to_numpy(dtype=int)
        ys = combined["forgery_classifier_probability"].to_numpy(dtype=float)
        yp = (ys >= threshold).astype(int)
        per_type[forgery_type] = _binary_metrics(yt, yp, ys)

    cm = confusion_matrix(y_true, y_pred).tolist()

    false_negatives = df[(y_true == 1) & (y_pred == 0)]
    weak_signal_notes = []
    for _, row in false_negatives.iterrows():
        signals = {
            "photo_tamper_score": row["photo_tamper_score"],
            "text_manipulation_score_max": row["text_manipulation_score_max"],
            "forgery_classifier_probability": row["forgery_classifier_probability"],
        }
        weakest = min(signals, key=signals.get)
        weak_signal_notes.append({"source_path": row["source_path"], "weakest_signal": weakest, "values": signals})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_disclosure": (
            "Evaluated on MIDV-2020 genuine images plus a SYNTHETIC PLACEHOLDER forged class "
            "(training/prepare_dataset.py::generate_synthetic_forgeries). SIDTD and FantasyID "
            "were NOT obtainable automatically in this build (see docs/LIMITATIONS.md) — these "
            "metrics say nothing about real-world or SIDTD/FantasyID-style forgery detection."
        ),
        "headline_metric": "recall",
        "headline_metric_rationale": "A missed forgery (false negative) is a categorically worse outcome than an unnecessary secondary inspection (false positive) in a border-security context.",
        "overall_metrics_on_synthetic_test_data": overall,
        "per_forgery_type_breakdown_on_synthetic_test_data": per_type,
        "confusion_matrix": {"matrix": cm, "labels": ["genuine", "forged"]},
        "false_negative_weak_signal_analysis": weak_signal_notes,
        "n_samples": len(df),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORTS_DIR / f"evaluation_{timestamp}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("Evaluation report written to %s", report_path)
    return report_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_evaluation()
