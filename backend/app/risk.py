"""Part F.7 — composite risk scoring. Weights are a documented judgment call,
tuned so tampering (the PS's "Core AI Innovation") dominates the score."""

from app.config import FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD

VALIDATION_FAILURE_POINTS = 10
TAMPERING_WEIGHT = 40
FACE_MISMATCH_WEIGHT = 30
WATCHLIST_MATCH_POINTS = 100
DUPLICATE_SUSPICIOUS_DIRECTION_POINTS = 20
IMPOSSIBLE_TRAVEL_POINTS = 25


def compute_risk_score(
    validation_failure_count: int,
    tampering_score: float,
    face_similarity_score: float | None,
    watchlist_match: bool,
    travel_direction_flag: str,
    impossible_travel_flag: bool,
) -> dict:
    breakdown = []
    total = 0

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
