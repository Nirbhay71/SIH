"""Part F.7 — composite risk scoring.

Two-tier design, mirroring ml-service's own src/fusion/hard_gates.py
concept (a real, existing pattern in this codebase, not invented here):

1. HARD GATES — watchlist_match and document_not_accepted. These force
   risk_score=100/HIGH outright, bypassing the weighted model below. This
   is deliberate, not a shortcut: a naive weighted-sum-to-100 model would
   cap a confirmed watchlist match's contribution at its own weight (e.g.
   15/100), which could let a genuine wanted-list hit score as LOW risk
   if nothing else about the crossing looked suspicious — unacceptable
   for what this system is actually for. A hard gate can never be diluted
   by an otherwise-clean document.

2. WEIGHTED FACTORS — everything else. Each factor's WEIGHT is its
   maximum possible point contribution; the six weights below sum to
   exactly 100 by construction, and each factor contributes
   weight * severity_fraction (severity_fraction always in [0, 1]), so
   the total is mathematically guaranteed to land in [0, 100] without
   needing a min(total, 100) clamp to paper over an already-broken sum.
   Tampering carries the largest weight per the project brief's "Core AI
   Innovation" framing; the rest are a documented judgment call, not a
   calibrated-against-real-outcomes model (this system has no historical
   ground-truth labels to calibrate against — see ml-service's own
   THRESHOLD_JUSTIFICATIONS.md for the same caveat applied there).
"""

from app.config import FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD

# --- Hard gates: bypass weighting entirely, force HIGH/100 ---
HARD_GATE_SCORE = 100

# --- Weighted factors: weights sum to exactly 100 ---
WEIGHT_TAMPERING = 35
WEIGHT_FACE_MISMATCH = 30
WEIGHT_LIVENESS_FAILED = 15
WEIGHT_VALIDATION_FAILURES = 10
WEIGHT_SUSPICIOUS_TRAVEL_DIRECTION = 5
WEIGHT_IMPOSSIBLE_TRAVEL = 5

assert (
    WEIGHT_TAMPERING
    + WEIGHT_FACE_MISMATCH
    + WEIGHT_LIVENESS_FAILED
    + WEIGHT_VALIDATION_FAILURES
    + WEIGHT_SUSPICIOUS_TRAVEL_DIRECTION
    + WEIGHT_IMPOSSIBLE_TRAVEL
    == 100
), "Weighted risk factors must sum to exactly 100 — see module docstring."

# A face similarity just under FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD (e.g. a
# slightly bad camera angle) is treated as a soft, partial signal — severity
# scales linearly from 0 at the threshold to 1.0 at zero similarity. Below
# this second, lower threshold, the mismatch is no longer "marginal", it's
# almost certainly two different people, so severity is pinned to the
# factor's full weight rather than continuing to scale down with similarity.
FACE_CONFIRMED_MISMATCH_THRESHOLD = 0.5

# 3+ simultaneous validation failures is treated as maximally severe for
# this factor's weight; severity scales linearly below that.
VALIDATION_FAILURE_SEVERITY_CAP = 3


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _hard_gate_result(factor: str, reason: str) -> dict:
    return {
        "risk_score": HARD_GATE_SCORE,
        "risk_level": "high",
        "scoring_model": "hard_gate",
        "risk_breakdown": [{
            "factor": factor,
            "points": HARD_GATE_SCORE,
            "weight": HARD_GATE_SCORE,
            "severity": 1.0,
            "hard_gate": True,
            "reason": reason + " This is a hard gate: it forces maximum risk on its own, bypassing the weighted model.",
        }],
    }


def compute_risk_score(
    validation_failure_count: int,
    tampering_score: float,
    face_similarity_score: float | None,
    watchlist_match: bool,
    travel_direction_flag: str,
    impossible_travel_flag: bool,
    document_not_accepted: bool = False,
    document_not_accepted_reason: str | None = None,
    liveness_passed: bool | None = None,
    watchlist_match_source: str | None = None,
    face_check_incomplete: bool = False,
) -> dict:
    # --- Hard gates first — short-circuit the weighted model entirely ---
    if watchlist_match:
        # Watchlist screening checks both the live camera face and the
        # document's own printed photo (app/routers/verification.py) — the
        # reason text must say which one actually fired, not always assume
        # it was the live face, or an officer reviewing a match caught via
        # the document photo alone would be told something that didn't happen.
        source_desc = {
            "live_face": "Live camera face matched a watchlist entry.",
            "document_photo": "The document's printed photo matched a watchlist entry.",
        }.get(watchlist_match_source, "A captured face matched a watchlist entry.")
        return _hard_gate_result("Watchlist match", source_desc)

    if document_not_accepted:
        return _hard_gate_result(
            "Document not accepted",
            document_not_accepted_reason or "This document type is not accepted proof of citizenship for this crossing.",
        )

    # --- Weighted factors: each contributes weight * severity_fraction ---
    # Every factor is emitted, including ones scoring zero, so the officer
    # can see the whole 100-point model and why a factor did *not* fire —
    # an explainability requirement (Part F.7), not decoration.
    tampering_severity = _clamp01(tampering_score)

    if face_similarity_score is None:
        face_severity = 0.0
        face_detail = "No live face captured for comparison."
    elif face_similarity_score >= FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD:
        face_severity = 0.0
        face_detail = f"Face similarity {face_similarity_score:.2f} is above the match threshold."
    elif face_similarity_score < FACE_CONFIRMED_MISMATCH_THRESHOLD:
        face_severity = 1.0
        face_detail = (
            f"Face similarity {face_similarity_score:.2f} is well below the match threshold — "
            "document photo and live capture likely show different people."
        )
    else:
        face_severity = _clamp01(
            (FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD - face_similarity_score) / FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD
        )
        face_detail = f"Face similarity {face_similarity_score:.2f} is below the confidence threshold."

    validation_severity = _clamp01(validation_failure_count / VALIDATION_FAILURE_SEVERITY_CAP)

    factors = [
        (
            "Tampering",
            WEIGHT_TAMPERING,
            tampering_severity,
            f"Tampering evidence score {tampering_score:.2f}."
            if tampering_score > 0
            else "No tampering evidence found by the scored checks (metadata, trained classifier). "
            "This is absence of evidence, not proof of authenticity — visual heuristics are experimental and not scored.",
        ),
        ("Face mismatch", WEIGHT_FACE_MISMATCH, face_severity, face_detail),
        (
            "Liveness check failed",
            WEIGHT_LIVENESS_FAILED,
            1.0 if liveness_passed is False else 0.0,
            "The live face capture could not be confirmed as genuine."
            if liveness_passed is False
            else "Liveness check passed." if liveness_passed else "Liveness not assessed.",
        ),
        (
            "Validation failures",
            WEIGHT_VALIDATION_FAILURES,
            validation_severity,
            f"{validation_failure_count} rule(s) failed."
            if validation_failure_count
            else "All document validation rules passed.",
        ),
        (
            "Suspicious travel direction",
            WEIGHT_SUSPICIOUS_TRAVEL_DIRECTION,
            1.0 if travel_direction_flag == "suspicious" else 0.0,
            "Same direction recorded twice with no opposite leg."
            if travel_direction_flag == "suspicious"
            else "Travel direction consistent with prior records.",
        ),
        (
            "Impossible travel",
            WEIGHT_IMPOSSIBLE_TRAVEL,
            1.0 if impossible_travel_flag else 0.0,
            "Required speed between records exceeds plausible travel."
            if impossible_travel_flag
            else "No implausible travel speed detected.",
        ),
    ]

    breakdown = []
    total = 0.0
    for name, weight, severity, detail in factors:
        points = weight * severity
        total += points
        breakdown.append({
            "factor": name,
            "points": round(points, 1),
            "weight": weight,
            "severity": round(severity, 3),
            "hard_gate": False,
            "reason": detail,
        })

    # No min(total, 100) needed — every term above is weight * fraction_in_[0,1]
    # and the weights sum to 100, so total is mathematically bounded to
    # [0, 100] already. Rounding only at the very end avoids compounding
    # rounding error across factors.
    score = round(total)

    # A crossing whose face check never ran must not come out LOW just because
    # the missing factor contributed zero points: absence of a check is not a
    # pass. Floor at the bottom of MEDIUM and say why, so the officer completes
    # the check by hand.
    if face_check_incomplete:
        breakdown.append({
            "factor": "Face verification incomplete",
            "points": 0,
            "weight": 0,
            "severity": 1.0,
            "hard_gate": False,
            "reason": "The ML service could not complete face verification, so face match, liveness and the "
                      "watchlist check did not run. Risk is floored at MEDIUM until an officer verifies the face manually.",
        })
        score = max(score, 31)

    if score <= 30:
        level = "low"
    elif score <= 65:
        level = "medium"
    else:
        level = "high"

    return {
        "risk_score": score,
        "risk_level": level,
        "scoring_model": "weighted",
        "risk_breakdown": breakdown,
    }
