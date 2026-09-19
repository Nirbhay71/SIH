"""Repairs OCR character confusions in an MRZ field using its own check digit.

An MRZ document number is alphanumeric, so OCR can't tell from the characters
alone whether a leading "2" is really a "Z" (the classic confusion:
Z/2, O/0, I/1, S/5, B/8, G/6). But the MRZ prints an ICAO 9303 check digit
for the field, and a wrong character almost always breaks it — so the check
digit can arbitrate. Candidate substitutions are tried, and one is accepted
only if it makes the check digit validate AND it is the only candidate at that
edit distance that does.

The uniqueness rule is what keeps this honest. A check digit is one decimal
digit, so a random wrong candidate validates ~10% of the time; if two
candidates both validate the checksum cannot tell them apart, and picking one
would be a coin flip presented as a correction. In that case the field is
left exactly as read.
"""
import re
from itertools import combinations

from src.validation.mrz_checksum import compute_check_digit

# Confusable pairs, in both directions.
_CONFUSIONS = {
    "0": "O", "O": "0",
    "1": "I", "I": "1",
    "2": "Z", "Z": "2",
    "5": "S", "S": "5",
    "8": "B", "B": "8",
    "6": "G", "G": "6",
}
_MAX_SUBSTITUTIONS = 2
_FIELD_WIDTH = 9  # ICAO TD3 document-number field, right-padded with '<'


def _check_matches(value: str, printed_check_digit: str) -> bool:
    padded = value.ljust(_FIELD_WIDTH, "<")
    try:
        return str(compute_check_digit(padded)) == str(printed_check_digit).strip()
    except ValueError:
        return False


def repair_document_number(
    value: str | None, printed_check_digit: str | None, format_pattern: str | None = None
) -> tuple[str | None, bool]:
    """Returns (value, was_repaired). Never returns a different value unless
    the substitution is validated by the check digit and unambiguous.

    `format_pattern` (the document type's number format, e.g. an Indian
    passport's letter + 7 digits) is a second, independent constraint: a
    candidate that cannot be a valid number for this document type is not
    considered at all. That is what disambiguates the common case where
    several substitutions happen to satisfy the one-digit check — without it
    those cases would (correctly) be refused as ambiguous."""
    if not value or printed_check_digit is None or not str(printed_check_digit).strip().isdigit():
        return value, False
    if _check_matches(value, printed_check_digit):
        return value, False  # already consistent — nothing to fix

    confusable_positions = [i for i, ch in enumerate(value) if ch in _CONFUSIONS]
    for n_subs in range(1, _MAX_SUBSTITUTIONS + 1):
        valid: list[str] = []
        for positions in combinations(confusable_positions, n_subs):
            # each chosen position is swapped to its confusable twin
            chars = list(value)
            for pos in positions:
                chars[pos] = _CONFUSIONS[chars[pos]]
            candidate = "".join(chars)
            if format_pattern and not re.fullmatch(format_pattern, candidate):
                continue
            if _check_matches(candidate, printed_check_digit):
                valid.append(candidate)
        unique = sorted(set(valid))
        if len(unique) == 1:
            return unique[0], True
        if len(unique) > 1:
            return value, False  # ambiguous: the check digit can't choose, so don't guess
    return value, False
