"""Section 9.1, Tier 1 — deterministic hard gates.

Non-negotiable (Section 9.1, 12A): this function must run, and be checked,
before Tier 2's trained model is ever invoked. There must be no code path
that reaches Tier 2 without first passing through here — see
`src/pipeline.py` and `tests/test_fusion.py::test_hard_gate_cannot_be_bypassed`.

A hard gate fires only on near-certain, deterministic evidence: a genuine
MRZ checksum failure (never "inconclusive_low_confidence" — collapsing
that distinction here would reintroduce the exact false-positive failure
mode Section 6.1 exists to prevent), a watchlist hit, or a failed liveness
check.
"""
from src.schemas import FaceVerificationResult, HardGateResult, IdentityDedupResult, ValidationResult

GENUINE_FAILURE = "fail"  # as opposed to "inconclusive_low_confidence", which must never trigger a gate


def check_watchlist_hit(document_number: str | None, watchlist: set[str]) -> bool:
    """Placeholder integration point for the mock watchlist (Section 2, 13F).

    This is the single, clearly-named function a real deployment would
    replace with an authorized government database lookup — see
    docs/ARCHITECTURE.md's integration handoff notes.
    """
    return document_number is not None and document_number in watchlist


def evaluate_hard_gates(
    validation_result: ValidationResult,
    face_result: FaceVerificationResult,
    identity_result: IdentityDedupResult | None,
    watchlist_hit: bool = False,
) -> HardGateResult:
    """Pure function: no side effects, no I/O, no model dependency.

    Checked in this fixed order so the surfaced reason is always the most
    legally/operationally significant one when multiple gates would fire
    simultaneously.
    """
    checksum_fields = (
        validation_result.mrz_checksum_document_number,
        validation_result.mrz_checksum_dob,
        validation_result.mrz_checksum_expiry,
        validation_result.mrz_checksum_composite,
    )
    if any(status == GENUINE_FAILURE for status in checksum_fields):
        return HardGateResult(triggered=True, reason="mrz_checksum_failed")

    if watchlist_hit:
        return HardGateResult(triggered=True, reason="watchlist_hit")

    if face_result.liveness_status == "failed":
        return HardGateResult(triggered=True, reason="liveness_failed")

    return HardGateResult(triggered=False, reason=None)
