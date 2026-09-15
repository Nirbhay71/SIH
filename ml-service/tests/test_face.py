"""Section 10.4 — liveness gating and the mandatory dual-condition for
duplicate-identity detection (Section 8.6). Uses a fake FAISS-like index
so these specific logic tests don't require faiss-cpu to be installed."""
import numpy as np
import pytest

from src.face.face_verification import verify_faces
from src.face.identity_dedup import IdentityRecord, check_duplicate_identity
from src.schemas import FaceVerificationResult


class _FakeIndex:
    """Minimal stand-in for IdentityIndex.query, used only to test the
    dual-condition logic in check_duplicate_identity in isolation."""

    def __init__(self, matches):
        self._matches = matches

    def query(self, embedding, k=5):
        return self._matches


def test_liveness_failed_short_circuits_face_match():
    doc_photo = np.zeros((10, 10, 3), dtype=np.uint8)
    live_capture = np.zeros((10, 10, 3), dtype=np.uint8)

    result = verify_faces(doc_photo, live_capture, liveness_status="failed")

    assert result.liveness_status == "failed"
    assert result.face_match_status == "not_computed"
    assert result.face_match_distance is None


def test_duplicate_flag_requires_both_face_match_and_differing_identity():
    record = IdentityRecord(record_id="r1", embedding=[0.1] * 512, name="JOHN SMITH", date_of_birth="1990-01-01")
    index = _FakeIndex(matches=[(record, 0.95)])  # high similarity

    # Case 1: same name/DOB as the matched record -> must NOT flag.
    result_same_identity = check_duplicate_identity(index, [0.1] * 512, name="JOHN SMITH", date_of_birth="1990-01-01")
    assert not result_same_identity.duplicate_identity_flag

    # Case 2: differing name/DOB with the same high-similarity match -> SHOULD flag.
    result_diff_identity = check_duplicate_identity(index, [0.1] * 512, name="JANE DOE", date_of_birth="1985-05-05")
    assert result_diff_identity.duplicate_identity_flag
    assert result_diff_identity.matched_record_id == "r1"


def test_no_flag_when_similarity_below_threshold_even_with_differing_identity():
    record = IdentityRecord(record_id="r1", embedding=[0.1] * 512, name="JOHN SMITH", date_of_birth="1990-01-01")
    index = _FakeIndex(matches=[(record, 0.40)])  # low similarity

    result = check_duplicate_identity(index, [0.1] * 512, name="JANE DOE", date_of_birth="1985-05-05")
    assert not result.duplicate_identity_flag
