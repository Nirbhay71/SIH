"""Section 9.4 — SHAP explainability for Tier 2 predictions."""
from pathlib import Path

from src.config import model_paths
from src.fusion.risk_model import model_artifact_path
from src.schemas import ContributingFactor

DISPLAY_NAMES = {
    "ocr_confidence_avg": "OCR confidence (average)",
    "ocr_confidence_min": "OCR confidence (weakest field)",
    "format_valid": "Document format validity",
    "logic_consistent": "Logical date/field consistency",
    "cross_zone_match": "MRZ vs. visual-zone match",
    "photo_tamper_score": "Photo tampering signal",
    "text_manipulation_score_max": "Text manipulation signal",
    "stamp_forgery_score": "Stamp forgery signal",
    "metadata_flag_count": "Metadata anomaly count",
    "forgery_classifier_probability": "Learned forgery classifier score",
    "face_match_distance": "Face match distance",
    "liveness_score": "Liveness score",
    "duplicate_identity_flag": "Duplicate identity flag",
}


def _display_name(feature: str) -> str:
    base = feature[: -len("_missing")] if feature.endswith("_missing") else feature
    label = DISPLAY_NAMES.get(base, base.replace("_", " "))
    return f"{label} (missing)" if feature.endswith("_missing") else label


def explain_prediction(feature_dict: dict[str, float], top_k: int = 3) -> list[ContributingFactor]:
    """Computes SHAP values for one prediction and returns the top_k
    contributing features with signed contributions, human-readable.

    Requires `shap` and the same trained model used for the prediction
    (Section 9.4). Returns an empty list (never raises into the pipeline)
    if SHAP or the model artifact is unavailable — the risk score itself
    still stands; only the explanation is degraded, and this is logged by
    the caller, not silently hidden (Section 11).
    """
    try:
        import shap
        import xgboost as xgb
    except ImportError:
        return []

    model_file = model_artifact_path()
    if not Path(model_file).exists():
        return []

    booster = xgb.Booster()
    booster.load_model(str(model_file))

    feature_names = list(feature_dict.keys())
    explainer = shap.TreeExplainer(booster)
    shap_values = explainer.shap_values([list(feature_dict.values())])[0]

    ranked = sorted(zip(feature_names, shap_values), key=lambda pair: abs(pair[1]), reverse=True)
    return [
        ContributingFactor(feature=name, display_name=_display_name(name), contribution=float(value))
        for name, value in ranked[:top_k]
    ]
