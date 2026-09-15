"""Section 7.5 — learned forgery classifier.

Path taken (documented per Section 3/13C): no suitable pretrained SIDTD/
MIDV-2020-fine-tuned forgery-detection checkpoint could be sourced and
vetted from Hugging Face within this build's time budget (see
docs/ARCHITECTURE.md). Per the spec's own documented fallback, this uses
`timm`'s EfficientNet-B3 pretrained on ImageNet as a backbone with a
fine-tuned binary classification head trained in
`training/train_forgery_head.py`. Until that head is trained (see
`docs/model_cards/forgery_classifier.md` for current status), inference
returns a clearly-flagged placeholder score rather than a fabricated
confident one.
"""
import logging
from pathlib import Path

import numpy as np

from src.config import model_paths, thresholds

logger = logging.getLogger("src.tampering")

_MODEL = None
INPUT_SIZE = 300  # EfficientNet-B3's expected input resolution


class ForgeryClassifierUnavailable(Exception):
    """Raised when torch/timm are not installed or no trained head exists.
    Callers (src/pipeline.py) must treat this as a degraded-but-explicit
    outcome, never silently substitute a fabricated probability."""


def _load_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    try:
        import timm
        import torch
    except ImportError as exc:
        raise ForgeryClassifierUnavailable("torch/timm are not installed in this environment.") from exc

    backbone = timm.create_model("efficientnet_b3", pretrained=True, num_classes=1)

    head_path = Path(model_paths()["forgery_classifier"]["fine_tuned_head_path"])
    if head_path.exists():
        state = torch.load(head_path, map_location="cpu")
        backbone.load_state_dict(state)
        logger.info("Loaded fine-tuned forgery classifier head from %s", head_path)
    else:
        logger.warning(
            "No fine-tuned forgery classifier head found at %s — using the ImageNet-pretrained "
            "backbone's untrained head. Probabilities from this model are NOT meaningful until "
            "training/train_forgery_head.py has been run (see docs/model_cards/forgery_classifier.md).",
            head_path,
        )

    backbone.eval()
    _MODEL = backbone
    return backbone


def _preprocess(image: np.ndarray):
    import cv2
    import torch

    resized = cv2.resize(image, (INPUT_SIZE, INPUT_SIZE))
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    normalized = (rgb - mean) / std
    tensor = torch.from_numpy(normalized.transpose(2, 0, 1)).unsqueeze(0).float()
    return tensor


def classify_forgery_probability(image: np.ndarray) -> tuple[float, bool]:
    """Returns (probability, model_is_calibrated).

    `model_is_calibrated` is False whenever the fine-tuned head has not
    been trained yet — the pipeline and API layer must surface this
    honestly (e.g. in a quality/confidence flag) rather than presenting an
    untrained model's output as a real measurement.
    """
    try:
        model = _load_model()
        import torch

        tensor = _preprocess(image)
        with torch.no_grad():
            logit = model(tensor)
            probability = float(torch.sigmoid(logit).item())
        head_path = Path(model_paths()["forgery_classifier"]["fine_tuned_head_path"])
        return probability, head_path.exists()
    except (ForgeryClassifierUnavailable, ImportError) as exc:
        logger.warning("Forgery classifier unavailable: %s", exc)
        return 0.5, False  # maximally uninformative, never a confident-looking fabricated score


def get_threshold() -> float:
    return thresholds()["tampering"]["forgery_classifier_threshold"]
