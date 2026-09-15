"""Section 7.5 / 8.3 — threshold-search scripts for Module 3 (forgery
classifier) and Module 4 (face-match distance).

Writes chosen thresholds back into config/thresholds.yaml is intentionally
NOT automated — a human should review the plotted/printed distributions
and the recall/precision tradeoff before a threshold is committed
(Section 7.5's "bias toward recall" instruction is a judgment call, not a
pure optimization target). This script prints its recommendation and the
supporting numbers for docs/THRESHOLD_JUSTIFICATIONS.md; a person copies
the chosen value into the YAML file.
"""
import logging

import numpy as np
import pandas as pd

from training.extract_features import OUTPUT_CSV

logger = logging.getLogger("training.calibrate_thresholds")


def calibrate_forgery_classifier_threshold(recall_floor: float = 0.9) -> dict:
    """Section 7.5: bias toward recall over precision. Picks the highest
    threshold that still achieves at least `recall_floor` recall on the
    labeled set — i.e., the most precision we can get without giving up
    the recall floor, rather than optimizing F1 or accuracy directly."""
    df = pd.read_csv(OUTPUT_CSV)
    scores = df["forgery_classifier_probability"].to_numpy()
    labels = df["label"].to_numpy()

    candidates = np.linspace(0.05, 0.95, 19)
    results = []
    for t in candidates:
        preds = (scores >= t).astype(int)
        tp = int(((preds == 1) & (labels == 1)).sum())
        fn = int(((preds == 0) & (labels == 1)).sum())
        fp = int(((preds == 1) & (labels == 0)).sum())
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        results.append({"threshold": float(t), "recall": recall, "precision": precision})

    eligible = [r for r in results if r["recall"] >= recall_floor]
    chosen = max(eligible, key=lambda r: r["threshold"]) if eligible else min(results, key=lambda r: abs(r["recall"] - recall_floor))

    logger.info("Forgery classifier threshold candidates: %s", results)
    logger.info("Chosen threshold (recall-biased): %s", chosen)
    return {"chosen": chosen, "all_candidates": results}


def calibrate_face_match_threshold(matched_distances: list[float], mismatched_distances: list[float]) -> dict:
    """Section 8.3: select the cosine-distance threshold that best
    separates matched (same-identity) from mismatched-pair distributions,
    using the Youden's-J-maximizing point on a simple ROC sweep.

    Requires real matched/mismatched pairs (e.g. from MIDV-2020 video-clip
    frames of the same synthetic identity) — see docs/THRESHOLD_JUSTIFICATIONS.md
    for this build's current status if this has not yet been run against
    real pair data.
    """
    matched = np.array(matched_distances)
    mismatched = np.array(mismatched_distances)
    candidates = np.linspace(0.0, 1.0, 101)

    best_threshold, best_j = None, -1.0
    for t in candidates:
        tpr = float((matched <= t).mean())  # a matched pair correctly called a match
        fpr = float((mismatched <= t).mean())  # a mismatched pair incorrectly called a match
        j = tpr - fpr
        if j > best_j:
            best_j, best_threshold = j, float(t)

    logger.info("Face match threshold candidates swept 0.0-1.0; chosen=%.3f (Youden's J=%.3f)", best_threshold, best_j)
    return {"threshold": best_threshold, "youdens_j": best_j}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    calibrate_forgery_classifier_threshold()
