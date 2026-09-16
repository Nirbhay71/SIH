"""Section 9.3 — trains the Tier 2 XGBoost fusion model.

Procedure (per Section 9.3, 10.6): stratified 80/20 split, k=5 cross-
validation on the training split only for hyperparameter selection
(never the test split), then a final retrain on the full training split
with the selected hyperparameters, evaluated once on the held-out test
split.
"""
import json
import logging
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import roc_auc_score

from src.fusion.feature_builder import FEATURE_ORDER
from training.extract_features import OUTPUT_CSV

logger = logging.getLogger("training.train_fusion_model")

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"

HYPERPARAM_GRID = {
    "max_depth": [2, 3, 4],
    "n_estimators": [100, 150, 200],
    "learning_rate": [0.05, 0.1, 0.15],
}
# On a small synthetic dataset, an unregularized tree can learn an overly
# sharp threshold on a single feature (verified: an earlier training run
# here scored a genuine document as 98% forged because photo_tamper_score
# landed a few hundredths off the exact value the trees split on).
# reg_lambda/min_child_weight/subsample/colsample_bytree all push toward
# smoother, less feature-threshold-brittle splits — a fixed regularization
# choice, not swept in the grid, since the grid already searches depth/
# estimators/learning_rate and adding 4 more dimensions would make this
# combinatorially slow for a 1-day build.
REGULARIZATION = {
    "reg_lambda": 5.0,
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
}


def _cross_validated_auc(X: np.ndarray, y: np.ndarray, params: dict, scale_pos_weight: float) -> float:
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    aucs = []
    for train_idx, val_idx in skf.split(X, y):
        model = xgb.XGBClassifier(
            **params, **REGULARIZATION, scale_pos_weight=scale_pos_weight, eval_metric="auc", use_label_encoder=False,
        )
        model.fit(X[train_idx], y[train_idx])
        preds = model.predict_proba(X[val_idx])[:, 1]
        aucs.append(roc_auc_score(y[val_idx], preds))
    return float(np.mean(aucs))


def train(version: str | None = None) -> Path:
    if not OUTPUT_CSV.exists():
        raise RuntimeError(f"Feature table not found at {OUTPUT_CSV}. Run training/extract_features.py first.")

    df = pd.read_csv(OUTPUT_CSV)
    X_all = df[FEATURE_ORDER].to_numpy(dtype=float)
    y_all = df["label"].to_numpy(dtype=int)

    X_train, X_test, y_train, y_test = train_test_split(
        X_all, y_all, test_size=0.2, stratify=y_all, random_state=42
    )

    genuine_count = int((y_train == 0).sum())
    forged_count = int((y_train == 1).sum())
    scale_pos_weight = (genuine_count / forged_count) if forged_count else 1.0

    best_params, best_auc = None, -1.0
    for max_depth, n_estimators, learning_rate in product(*HYPERPARAM_GRID.values()):
        params = {"max_depth": max_depth, "n_estimators": n_estimators, "learning_rate": learning_rate}
        auc = _cross_validated_auc(X_train, y_train, params, scale_pos_weight)
        logger.info("params=%s mean_cv_auc=%.4f", params, auc)
        if auc > best_auc:
            best_auc, best_params = auc, params

    logger.info("Selected hyperparameters: %s (mean CV AUC=%.4f)", best_params, best_auc)

    final_model = xgb.XGBClassifier(
        **best_params, **REGULARIZATION, scale_pos_weight=scale_pos_weight, eval_metric="auc", use_label_encoder=False,
    )
    final_model.fit(X_train, y_train)

    test_probs = final_model.predict_proba(X_test)[:, 1]
    test_auc = roc_auc_score(y_test, test_probs) if len(set(y_test)) > 1 else float("nan")
    logger.info("Held-out test AUC: %.4f", test_auc)

    version = version or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = ARTIFACT_DIR / f"xgboost_fusion_{version}.json"
    manifest_path = ARTIFACT_DIR / f"feature_manifest_{version}.json"

    final_model.get_booster().save_model(str(model_path))
    manifest = {
        "version": version,
        "feature_order": FEATURE_ORDER,
        "hyperparameters": best_params,
        "scale_pos_weight": scale_pos_weight,
        "cv_auc": best_auc,
        "test_auc": test_auc,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Trained on MIDV-2020 genuine images plus a synthetic PLACEHOLDER forged class "
            "(see training/prepare_dataset.py) because SIDTD/FantasyID require manual, "
            "human-completed access requests not obtainable by an automated script. "
            "See docs/LIMITATIONS.md before treating any metric from this model as real-world accuracy."
        ),
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Saved model to %s and manifest to %s", model_path, manifest_path)
    return model_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    train()
