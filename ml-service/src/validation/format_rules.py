"""Section 6.2 — format/pattern validation against config/document_formats.yaml.

No document-format rule for a domestic Indian ID (Aadhaar/PAN/Voter ID) may
ever be added here — see Section 1B of the build spec; this system screens
border-checkpoint documents only.
"""
import re

from src.config import document_formats


def validate_format(document_type: str, document_number: str | None) -> tuple[bool, list[str]]:
    """Checks `document_number` against the pattern configured for
    `document_type`. Returns (is_valid, violations).

    A document type with `document_number_pattern: null` (e.g. foreign
    passports, region-dependent permits) is treated as "no universal
    pattern exists" rather than an automatic failure — this is a
    documented, deliberate limitation (Section 6.2), not a bug.
    """
    rules = document_formats().get(document_type)
    if rules is None:
        return False, [f"Unknown document type '{document_type}' — no format rules configured."]

    pattern = rules.get("document_number_pattern")
    if pattern is None:
        return True, []  # no universal format to check against for this type

    if document_number is None:
        return False, ["document_number is missing; cannot validate format."]

    if not re.match(pattern, document_number):
        return False, [f"document_number '{document_number}' does not match expected pattern for {document_type}."]

    return True, []
