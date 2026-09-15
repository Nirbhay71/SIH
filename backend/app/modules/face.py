"""
Module 4 — Face Verification (mock implementation).

No real face-recognition model is bundled here (kept dependency-free for a
zero-install demo). Embeddings are deterministic hash-derived vectors used
only to demonstrate the *matching logic* (document-vs-live comparison,
watchlist nearest-neighbor, duplicate-check). They do NOT represent real
facial similarity — swap `embed_face` for a real model (e.g. the
`face_recognition` / dlib library, or any embedding API) as a drop-in
replacement; every caller only depends on `embed_face` returning a
fixed-length list[float] and `cosine_similarity` comparing two of them.

Fairness note (Part F.4): face-matching accuracy is known to vary across
ethnicities (NIST studies). The India-Nepal border region is ethnically
diverse, so this is a live concern for any real deployment — mitigations:
use a model benchmarked on diverse datasets, keep a human officer in the
loop for borderline matches, and track false-reject rates by demographic
in production.

Contract:
  embed_face(image_bytes: bytes) -> list[float]
  cosine_similarity(a: list[float], b: list[float]) -> float
  run_liveness(image_bytes: bytes) -> bool
"""
import hashlib
import random

import numpy as np

EMBEDDING_DIM = 64


def embed_face(image_bytes: bytes) -> list[float]:
    digest = hashlib.sha256(image_bytes).digest()
    seed = int.from_bytes(digest[:8], "big")
    rng = np.random.default_rng(seed)
    vec = rng.normal(size=EMBEDDING_DIM)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1e-9
    return float(np.dot(va, vb) / denom)


def run_liveness(image_bytes: bytes) -> bool:
    random.seed(len(image_bytes))
    return random.random() > 0.05


def similarity_between_images(image_a: bytes, image_b: bytes, force_match: bool | None = None) -> float:
    """Convenience used by the mock pipeline: if force_match is set, fabricate
    a plausible high/low score directly (since two demo images of "the same
    person" won't hash-embed as similar under a fake embedding). Otherwise
    fall back to real cosine similarity of the hash-derived embeddings."""
    if force_match is True:
        random.seed(len(image_a) + len(image_b))
        return round(random.uniform(0.88, 0.99), 3)
    if force_match is False:
        random.seed(len(image_a) + len(image_b) + 1)
        return round(random.uniform(0.10, 0.45), 3)
    return round(cosine_similarity(embed_face(image_a), embed_face(image_b)), 3)
