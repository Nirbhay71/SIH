"""Part F.7 — composite risk scoring. Weights are a documented judgment call,
tuned so tampering (the PS's "Core AI Innovation") dominates the score."""

from app.config import FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD

VALIDATION_FAILURE_POINTS = 10
TAMPERING_WEIGHT = 40
FACE_MISMATCH_WEIGHT = 30
WATCHLIST_MATCH_POINTS = 100
DUPLICATE_SUSPICIOUS_DIRECTION_POINTS = 20
IMPOSSIBLE_TRAVEL_POINTS = 25

# A face similarity just under FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD (e.g. a
# slightly bad camera angle) is a soft signal and gets only the scaled
# FACE_MISMATCH_WEIGHT penalty above. But this system's entire purpose is
# catching document-vs-holder identity fraud — a similarity this low is not
# an unlucky selfie, it's two different people — so a confirmed mismatch
# must not stay capped in "low" risk territory alongside genuinely marginal
# cases. This threshold and its added points are a separate, harder gate on
# top of the scaled penalty, not a replacement for it.
FACE_CONFIRMED_MISMATCH_THRESHOLD = 0.5
FACE_CONFIRMED_MISMATCH_POINTS = 50

# A document type that isn't accepted proof of citizenship for this crossing
# (app/acceptance_policy.py — e.g. an Aadhaar card presented as travel proof)
# is an eligibility problem, not a data-quality one, so it's scored
# separately from ordinary VALIDATION_FAILURE_POINTS and weighted heavily
# enough (70) to cross into "high" risk on its own, regardless of how clean
# everything else about the document is.
DOCUMENT_NOT_ACCEPTED_POINTS = 70

# A failed liveness check means the live capture could not be confirmed as a
# real, live face (e.g. a photo-of-a-photo/screen-replay spoof, or simply no
# face detected at all) — this was previously computed by
# app/modules/face.py / ml_adapter.py and stored on the record
# (liveness_passed) but never fed into the risk score, so a spoofed or
# undetectable "live" capture silently scored identically to a clean one.
# Weighted just under DOCUMENT_NOT_ACCEPTED_POINTS: liveness failure is a
# strong spoof signal but, unlike a rejected document type, can also stem
# from an honest capture problem (bad lighting, camera angle), so it is not
# given quite the same certainty.
LIVENESS_FAILED_POINTS = 60


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
) -> dict:
    breakdown = []
    total = 0

    if liveness_passed is False:
        total += LIVENESS_FAILED_POINTS
        breakdown.append({
            "factor": "Liveness check failed",
            "points": LIVENESS_FAILED_POINTS,
            "reason": "The live face capture could not be confirmed as a genuine live face (no face detected, or a possible spoof/replay).",
        })

    if document_not_accepted:
        total += DOCUMENT_NOT_ACCEPTED_POINTS
        breakdown.append({
            "factor": "Document not accepted",
            "points": DOCUMENT_NOT_ACCEPTED_POINTS,
            "reason": document_not_accepted_reason or "This document type is not accepted proof of citizenship for this crossing.",
        })

    if validation_failure_count:
        pts = validation_failure_count * VALIDATION_FAILURE_POINTS
        total += pts
        breakdown.append({"factor": "Validation failures", "points": pts, "reason": f"{validation_failure_count} rule(s) failed."})

    tampering_pts = round(tampering_score * TAMPERING_WEIGHT)
    total += tampering_pts
    breakdown.append({"factor": "Tampering", "points": tampering_pts, "reason": f"Tampering score {tampering_score:.2f}."})

    if face_similarity_score is not None and face_similarity_score < FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD:
        face_pts = round((1 - face_similarity_score) * FACE_MISMATCH_WEIGHT)
        total += face_pts
        breakdown.append({"factor": "Face mismatch", "points": face_pts, "reason": f"Face similarity {face_similarity_score:.2f} below confidence threshold."})

        if face_similarity_score < FACE_CONFIRMED_MISMATCH_THRESHOLD:
            total += FACE_CONFIRMED_MISMATCH_POINTS
            breakdown.append({
                "factor": "Face identity mismatch",
                "points": FACE_CONFIRMED_MISMATCH_POINTS,
                "reason": f"Face similarity {face_similarity_score:.2f} is well below the match threshold — document photo and live capture likely show different people.",
            })

    if watchlist_match:
        total += WATCHLIST_MATCH_POINTS
        breakdown.append({"factor": "Watchlist match", "points": WATCHLIST_MATCH_POINTS, "reason": "Live face matched a watchlist entry."})

    if travel_direction_flag == "suspicious":
        total += DUPLICATE_SUSPICIOUS_DIRECTION_POINTS
        breakdown.append({"factor": "Suspicious travel direction", "points": DUPLICATE_SUSPICIOUS_DIRECTION_POINTS, "reason": "Same direction recorded twice with no opposite leg."})

    if impossible_travel_flag:
        total += IMPOSSIBLE_TRAVEL_POINTS
        breakdown.append({"factor": "Impossible travel", "points": IMPOSSIBLE_TRAVEL_POINTS, "reason": "Required speed between records exceeds plausible travel."})

    score = min(total, 100)
    if score <= 30:
        level = "low"
    elif score <= 65:
        level = "medium"
    else:
        level = "high"

    return {"risk_score": score, "risk_level": level, "risk_breakdown": breakdown}
