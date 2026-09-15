"""Section 9.1 Tier 2 + Section 9.3 — trained XGBoost fusion model inference.

Loads a versioned model artifact and its feature-order manifest together
(Section 9.3, 9.7). Refuses to run if the live feature vector doesn't
match what the model was trained on (Section 9.3) — this is fail-closed
behavior per Section 11, not an optional safety check.
"""
import json
from pathlib import Path

from src.config import model_paths, thresholds
from src.fusion.feature_builder import FEATURE_ORDER
from src.schemas import RiskAssessment

ARTIFACT_DIR = Path(__file__).resolve().parent.parent.parent / "training" / "artifacts"


class ModelNotAvailableError(Exception):
    """Raised when the trained fusion model artifact cannot be loaded.

    The pipeline (src/pipeline.py) must treat this as a processing error
    requiring manual review (Section 11: fail closed, not open) — never as
    an implicit low-risk clearance.
    """


class FeatureVectorMismatchError(Exception):
    """Raised when a live feature vector's keys/order don't match the
    manifest the model was trained on (Section 9.3)."""


def manifest_path_config() -> Path:
    return Path(model_paths()["fusion_model"]["feature_manifest_path"])


def model_artifact_path() -> Path:
    return Path(model_paths()["fusion_model"]["path"])


def load_manifest() -> dict:
    path = manifest_path_config()
    if not path.exists():
        raise ModelNotAvailableError(f"Feature manifest not found at {path}. Train the fusion model first (training/train_fusion_model.py).")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _validate_feature_vector(feature_dict: dict[str, float], manifest: dict) -> list[float]:
    expected_order = manifest["feature_order"]
    if list(feature_dict.keys()) != expected_order:
        raise FeatureVectorMismatchError(
            f"Feature vector keys {list(feature_dict.keys())} do not match the trained model's "
            f"feature order {expected_order}. Refusing to run inference on a mismatched vector."
        )
    return [feature_dict[k] for k in expected_order]


def _score_to_tier(score: int) -> str:
    cfg = thresholds()["fusion"]
    if score <= cfg["risk_tier_low_max"]:
        return "LOW"
    if score <= cfg["risk_tier_medium_max"]:
        return "MEDIUM"
    if score <= cfg["risk_tier_high_max"]:
        return "HIGH"
    return "CRITICAL"


def run_fusion_model(feature_dict: dict[str, float]) -> RiskAssessment:
    """Runs Tier 2 inference. Callers must have already confirmed no Tier 1
    hard gate fired (src/fusion/hard_gates.py) — see the non-negotiable
    ordering rule documented there and tested in tests/test_fusion.py."""
    try:
        import xgboost as xgb
    except ImportError as exc:
        raise ModelNotAvailableError("xgboost is not installed in this environment.") from exc

    manifest = load_manifest()
    model_file = model_artifact_path()
    if not model_file.exists():
        raise ModelNotAvailableError(f"Trained model artifact not found at {model_file}. Run training/train_fusion_model.py first.")

    ordered_values = _validate_feature_vector(feature_dict, manifest)

    booster = xgb.Booster()
    booster.load_model(str(model_file))
    dmatrix = xgb.DMatrix([ordered_values], feature_names=manifest["feature_order"], missing=float("nan"))
    probability = float(booster.predict(dmatrix)[0])

    score = int(round(probability * 100))
    return RiskAssessment(
        risk_score=score,
        risk_tier=_score_to_tier(score),
        gate_triggered=None,
        model_probability=probability,
        top_contributing_factors=[],
        model_version=manifest.get("version"),
    )
