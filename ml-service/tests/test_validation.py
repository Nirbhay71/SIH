"""Section 6.6 / 6.5A — hand-verified ICAO 9303 checksum test vectors.

At least 5 valid and 3 deliberately corrupted cases, plus the exact worked
example from Section 6.5A of the build spec, plus the fusion-critical
`inconclusive_low_confidence` distinction from Section 6.1.
"""
from datetime import date

from src.validation.mrz_checksum import (
    compute_check_digit,
    checksum_status,
    composite_check_digit_td3,
)
from src.validation.logic_checks import check_logic_consistency, check_cross_zone_match
from src.validation.format_rules import validate_format


# --- Section 6.5A worked example (literal, from the spec) -------------------

def test_worked_example_document_number_check_digit():
    # "P1234567<4IND..." — document number field is "1234567<", check digit 4.
    assert compute_check_digit("1234567<") == 4


def test_worked_example_document_number_corrupted():
    # Change one digit; the checksum must now disagree with the original digit.
    assert compute_check_digit("1234568<") != 4


# --- 5 hand-verified valid vectors -------------------------------------------

def test_valid_vector_1_dob():
    # DOB 1980-01-01 -> "800101"
    assert compute_check_digit("800101") == 4


def test_valid_vector_2_expiry():
    # Expiry 2030-01-01 -> "300101"
    assert compute_check_digit("300101") == 9


def test_valid_vector_3_all_filler():
    # An all-filler field's check digit must be 0.
    assert compute_check_digit("<<<<<<<<") == 0


def test_valid_vector_4_letters():
    # 'A' = 10 -> weight 7 -> 70 mod 10 = 0
    assert compute_check_digit("A") == 0
    # 'B' = 11 -> weight 7 -> 77 mod 10 = 7
    assert compute_check_digit("B") == 7


def test_valid_vector_5_mixed():
    # "AB2<<<<<" : A=10,B=11,2=2,<=0 x5 ; weights 7,3,1,7,3,1,7,3
    # 10*7 + 11*3 + 2*1 + 0*7 + 0*3 + 0*1 + 0*7 + 0*3 = 70+33+2 = 105 -> 5
    assert compute_check_digit("AB2<<<<<") == 5


# --- 3 deliberately corrupted vectors ----------------------------------------

def test_corrupted_vector_1():
    assert compute_check_digit("800102") != 4  # DOB digit changed


def test_corrupted_vector_2():
    assert compute_check_digit("300102") != 9  # expiry digit changed


def test_corrupted_vector_3():
    assert compute_check_digit("BB2<<<<<") != 5  # letter changed


# --- checksum_status: the non-negotiable low-confidence distinction ---------

def test_checksum_status_pass():
    assert checksum_status("1234567<", "4", field_is_low_confidence=False) == "pass"


def test_checksum_status_fail_when_high_confidence():
    assert checksum_status("1234568<", "4", field_is_low_confidence=False) == "fail"


def test_checksum_status_inconclusive_when_low_confidence():
    # Same mismatch as above, but the source OCR field was low-confidence:
    # must NOT be reported as "fail".
    assert checksum_status("1234568<", "4", field_is_low_confidence=True) == "inconclusive_low_confidence"


def test_checksum_status_not_applicable_when_missing():
    assert checksum_status(None, None, field_is_low_confidence=False) == "not_applicable"


# --- composite check digit over a self-consistent full TD3 line -------------

def test_composite_check_digit_self_consistent_line():
    doc_field = "L898902C"          # 8 chars + check digit below
    doc_check = str(compute_check_digit(doc_field + "3"))  # placeholder, recomputed next line
    # Build a fully self-consistent 44-char TD3 line 2 by construction.
    doc_number_field = "L898902C3"  # 9 chars (8 + filler/check placeholder slot not used here)
    dob_field = "740812"
    dob_check = compute_check_digit(dob_field)
    expiry_field = "120415"
    expiry_check = compute_check_digit(expiry_field)
    personal_number_field = "<" * 14
    personal_check = compute_check_digit(personal_number_field)
    doc_check_digit = compute_check_digit(doc_number_field)

    line2 = (
        doc_number_field + str(doc_check_digit)
        + "UTO"
        + dob_field + str(dob_check)
        + "F"
        + expiry_field + str(expiry_check)
        + personal_number_field + str(personal_check)
    )
    composite = compute_check_digit(line2[0:10] + line2[13:20] + line2[21:43])
    line2 = line2 + str(composite)

    assert len(line2) == 44
    assert composite_check_digit_td3(line2) == composite


def test_composite_check_digit_detects_corruption():
    doc_number_field = "L898902C3"
    dob_field = "740812"
    dob_check = compute_check_digit(dob_field)
    expiry_field = "120415"
    expiry_check = compute_check_digit(expiry_field)
    personal_number_field = "<" * 14
    personal_check = compute_check_digit(personal_number_field)
    doc_check_digit = compute_check_digit(doc_number_field)

    line2 = (
        doc_number_field + str(doc_check_digit)
        + "UTO"
        + dob_field + str(dob_check)
        + "F"
        + expiry_field + str(expiry_check)
        + personal_number_field + str(personal_check)
    )
    composite = compute_check_digit(line2[0:10] + line2[13:20] + line2[21:43])
    wrong_composite = (composite + 1) % 10
    line2 = line2 + str(wrong_composite)

    assert composite_check_digit_td3(line2) != wrong_composite


# --- logic checks -------------------------------------------------------------

def test_logic_check_expiry_before_issue_is_violation():
    ok, violations = check_logic_consistency(date(2030, 1, 1), date(2020, 1, 1), date(1990, 1, 1))
    assert not ok
    assert violations


def test_logic_check_normal_case_passes():
    ok, violations = check_logic_consistency(date(2020, 1, 1), date(2030, 1, 1), date(1990, 1, 1))
    assert ok
    assert not violations


# --- cross-zone match ----------------------------------------------------------

def test_cross_zone_match_none_when_no_mrz():
    assert check_cross_zone_match(None, {"name": "A"}, set()) is None


def test_cross_zone_mismatch_detected():
    mrz = {"name": "JOHN SMITH"}
    visual = {"name": "JOHN SMYTH"}
    assert check_cross_zone_match(mrz, visual, set()) is False


def test_cross_zone_low_confidence_field_excluded_from_mismatch():
    mrz = {"name": "JOHN SMITH"}
    visual = {"name": "JOHN SMYTH"}
    assert check_cross_zone_match(mrz, visual, {"name"}) is True


# --- format validation ---------------------------------------------------------

def test_format_valid_indian_passport():
    ok, violations = validate_format("indian_passport", "P1234567")
    assert ok and not violations


def test_format_invalid_indian_passport():
    ok, violations = validate_format("indian_passport", "1234567")
    assert not ok and violations


def test_format_no_universal_pattern_for_foreign_passport_is_not_a_failure():
    ok, violations = validate_format("foreign_passport", "ANYTHING123")
    assert ok and not violations
