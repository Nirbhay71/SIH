"""Loads YAML configuration (Section 4A). No threshold, path, or format rule
may be hardcoded in module logic — everything reachable from here."""
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@lru_cache(maxsize=None)
def _load(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def thresholds() -> dict:
    return _load("thresholds.yaml")


def document_formats() -> dict:
    return _load("document_formats.yaml")


def model_paths() -> dict:
    return _load("model_paths.yaml")
