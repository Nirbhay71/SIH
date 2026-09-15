"""ICAO 9303 MRZ check-digit algorithm (Section 6.1 of the build spec).

Character values: digits 0-9 as themselves, '<' as 0, letters A-Z as 10-35.
Weights cycle 7, 3, 1 starting fresh (at 7) for every field. The check
digit is the weighted sum modulo 10.

Non-negotiable rule (Section 6.1): a checksum computed from a field that
Module 1 flagged as low-confidence must never be reported as a definite
"fail" — see `checksum_status` below, which is what the fusion layer
(Section 9.1) relies on to distinguish an OCR problem from real evidence
of tampering.
"""
from typing import Literal

ChecksumStatus = Literal["pass", "fail", "inconclusive_low_confidence", "not_applicable"]

_WEIGHTS = (7, 3, 1)


def _char_value(ch: str) -> int:
    if ch.isdigit():
        return int(ch)
    if ch == "<":
        return 0
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    raise ValueError(f"Character '{ch}' is not valid in an MRZ field (expected A-Z, 0-9, or '<').")


def compute_check_digit(data: str) -> int:
    """Computes the ICAO 9303 check digit for `data`.

    Assumes `data` contains only uppercase letters, digits, and '<' filler
    characters (raw MRZ alphabet). Guarantees a single digit 0-9.
    """
    total = 0
    for i, ch in enumerate(data):
        total += _char_value(ch) * _WEIGHTS[i % 3]
    return total % 10


def checksum_status(
    field_data: str | None,
    printed_check_digit: str | None,
    *,
    field_is_low_confidence: bool,
    field_present: bool = True,
) -> ChecksumStatus:
    """Compares a computed check digit against the printed one.

    Non-negotiable: if `field_is_low_confidence` is True, a mismatch is
    reported as "inconclusive_low_confidence", never "fail" — an OCR
    misread must not be reported as confirmed tampering evidence.
    """
    if not field_present or field_data is None or printed_check_digit is None:
        return "not_applicable"

    try:
        computed = compute_check_digit(field_data)
        matches = str(computed) == str(printed_check_digit).strip()
    except ValueError:
        matches = False

    if matches:
        return "pass"
    return "inconclusive_low_confidence" if field_is_low_confidence else "fail"


def composite_check_digit_td3(line2: str) -> int:
    """ICAO 9303 TD3 (passport) composite check digit.

    Covers, per the standard: document-number field + its check digit
    (positions 1-10, 1-indexed), date-of-birth field + its check digit
    (positions 14-20), and expiry-date field + its check digit + the
    personal-number field + its check digit (positions 22-43), all
    concatenated, over a standard 44-character TD3 line 2.
    """
    if len(line2) != 44:
        raise ValueError(f"TD3 MRZ line 2 must be 44 characters, got {len(line2)}.")
    composite_input = line2[0:10] + line2[13:20] + line2[21:43]
    return compute_check_digit(composite_input)
