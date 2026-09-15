"""Section 6.3 (logical consistency) and 6.4 (cross-zone consistency)."""
from datetime import date

MIN_PLAUSIBLE_AGE_YEARS = 0  # infants can legitimately hold passports — flag, never hard-reject (Section 6.3)
MAX_PLAUSIBLE_AGE_YEARS = 120


def _years_between(d1: date, d2: date) -> float:
    return (d2 - d1).days / 365.25


def check_logic_consistency(
    issue_date: date | None,
    expiry_date: date | None,
    date_of_birth: date | None,
    today: date | None = None,
) -> tuple[bool, list[str]]:
    """Section 6.3. Flags rather than hard-rejects implausible-but-possible
    cases (e.g. an infant's passport) — only genuinely contradictory data
    (expiry before issue) is a hard violation."""
    today = today or date.today()
    violations = []

    if issue_date and expiry_date and issue_date >= expiry_date:
        violations.append("expiry_date is not after issue_date.")

    if date_of_birth:
        age_years = _years_between(date_of_birth, today)
        if age_years < MIN_PLAUSIBLE_AGE_YEARS or age_years > MAX_PLAUSIBLE_AGE_YEARS:
            violations.append(f"date_of_birth implies an implausible age ({age_years:.1f} years).")

    return len(violations) == 0, violations


def check_visa_stay_within_validity(entry_validity_days: int | None, stay_duration_days: int | None) -> tuple[bool, list[str]]:
    if entry_validity_days is None or stay_duration_days is None:
        return True, []
    if stay_duration_days > entry_validity_days:
        return False, ["stay_duration exceeds the visa's own validity window."]
    return True, []


def check_permit_validity_window(valid_from: date | None, valid_to: date | None) -> tuple[bool, list[str]]:
    if valid_from is None or valid_to is None:
        return True, []
    if valid_from >= valid_to:
        return False, ["permit valid_from is not before valid_to."]
    return True, []


def check_cross_zone_match(
    mrz_fields: dict[str, str | None] | None,
    visual_fields: dict[str, str | None] | None,
    low_confidence_fields: set[str],
) -> bool | None:
    """Section 6.4. Compares MRZ-encoded values against the same fields as
    OCR'd from the visually printed zone. Returns None if there is no MRZ
    to cross-check against (non-MRZ document types).

    Fields present in `low_confidence_fields` on either side are excluded
    from the comparison rather than being allowed to produce a false
    mismatch driven purely by an OCR misread.
    """
    if not mrz_fields:
        return None

    for key, mrz_value in mrz_fields.items():
        if key in low_confidence_fields:
            continue
        visual_value = (visual_fields or {}).get(key)
        if visual_value is None:
            continue
        if str(mrz_value).strip().upper() != str(visual_value).strip().upper():
            return False

    return True
