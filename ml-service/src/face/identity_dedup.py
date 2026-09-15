"""Section 8.6 — identity deduplication (multiple-identity detection) via
FAISS nearest-neighbor search over face embeddings.

Mandatory dual condition (Section 8.6, 12A): a duplicate-identity flag
requires BOTH a face-embedding match above threshold AND a differing
name/DOB combination. Face similarity alone produces false positives on
twins/close relatives — a documented real-world failure mode this
function exists specifically to avoid.

Hackathon-scale note (Section 8.6): a flat FAISS index is sufficient here;
a production deployment would need a distributed, persistent vector store
(e.g. Milvus, Qdrant) instead.
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.schemas import IdentityDedupResult

logger = logging.getLogger("src.face")

FACE_MATCH_SIMILARITY_THRESHOLD = 0.90  # cosine similarity; distinct from Module 4's document-vs-live threshold


@dataclass
class IdentityRecord:
    record_id: str
    embedding: list[float]
    name: str | None
    date_of_birth: str | None


class IdentityIndex:
    """Thin wrapper around a FAISS flat index plus a parallel metadata
    store. Persisted to disk as (index_file, metadata_file) pairs so the
    demo can retain state across API restarts."""

    def __init__(self, dim: int = 512):
        self.dim = dim
        self._records: list[IdentityRecord] = []
        self._index = None

    def _ensure_index(self):
        if self._index is not None:
            return
        try:
            import faiss
        except ImportError as exc:
            raise RuntimeError("faiss-cpu is not installed in this environment.") from exc
        self._index = faiss.IndexFlatIP(self.dim)  # inner product on L2-normalized vectors == cosine similarity

    @staticmethod
    def _normalize(vec: list[float]) -> np.ndarray:
        arr = np.array(vec, dtype=np.float32)
        norm = np.linalg.norm(arr) or 1e-9
        return arr / norm

    def add(self, record: IdentityRecord) -> None:
        self._ensure_index()
        self._index.add(np.expand_dims(self._normalize(record.embedding), 0))
        self._records.append(record)

    def query(self, embedding: list[float], k: int = 5) -> list[tuple[IdentityRecord, float]]:
        self._ensure_index()
        if self._index.ntotal == 0:
            return []
        query_vec = np.expand_dims(self._normalize(embedding), 0)
        k = min(k, self._index.ntotal)
        similarities, indices = self._index.search(query_vec, k)
        return [(self._records[i], float(similarities[0][rank])) for rank, i in enumerate(indices[0]) if i >= 0]

    def save(self, index_path: Path, metadata_path: Path) -> None:
        import faiss

        self._ensure_index()
        faiss.write_index(self._index, str(index_path))
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump([r.__dict__ for r in self._records], f)

    @classmethod
    def load(cls, index_path: Path, metadata_path: Path, dim: int = 512) -> "IdentityIndex":
        instance = cls(dim=dim)
        if not index_path.exists() or not metadata_path.exists():
            return instance
        import faiss

        instance._index = faiss.read_index(str(index_path))
        with open(metadata_path, encoding="utf-8") as f:
            instance._records = [IdentityRecord(**r) for r in json.load(f)]
        return instance


def check_duplicate_identity(
    index: IdentityIndex,
    embedding: list[float],
    name: str | None,
    date_of_birth: str | None,
) -> IdentityDedupResult:
    """Section 8.6's non-negotiable dual condition: flags only when a close
    face match AND a differing name/DOB are both present."""
    matches = index.query(embedding, k=5)

    for record, similarity in matches:
        if similarity < FACE_MATCH_SIMILARITY_THRESHOLD:
            continue

        same_identity = (record.name == name) and (record.date_of_birth == date_of_birth)
        if same_identity:
            continue  # same person re-scanned under the same declared identity — not a duplicate-identity case

        return IdentityDedupResult(duplicate_identity_flag=True, matched_record_id=record.record_id, face_similarity=similarity)

    return IdentityDedupResult(duplicate_identity_flag=False)
