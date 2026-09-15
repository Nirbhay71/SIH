"""Part C.4 — hash-chain audit log. Implements the tamper-evident data
structure at the core of a blockchain (previous_hash + SHA-256 of canonical
record data), without a distributed-consensus layer — appropriate for a
single-authority (SSB) ledger where multi-node consensus adds no value."""
import hashlib
import json


def canonical_payload(record: dict) -> str:
    keys = [
        "id", "session_id", "doc_type", "doc_number", "name", "dob",
        "tampering_score", "face_match_score", "watchlist_match",
        "risk_score", "risk_level", "officer_decision",
    ]
    payload = {k: record.get(k) for k in keys}
    return json.dumps(payload, sort_keys=True, default=str)


def compute_hash(record: dict, prev_hash: str) -> str:
    data = canonical_payload(record) + "|" + (prev_hash or "")
    return hashlib.sha256(data.encode()).hexdigest()
