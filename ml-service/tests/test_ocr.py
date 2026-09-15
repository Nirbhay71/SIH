"""Section 10.4 — deterministic parts of Module 1 (normalization) tested
without requiring the optional OCR engine dependencies to be installed."""
from datetime import date

from src.ocr.field_normalization import normalize_date, normalize_document_number, normalize_name


def test_normalize_date_dmy_dash():
    d, failed = normalize_date("12-05-2004")
    assert d == date(2004, 5, 12)
    assert not failed


def test_normalize_date_dmy_slash():
    d, failed = normalize_date("12/05/2004")
    assert d == date(2004, 5, 12)
    assert not failed


def test_normalize_date_mrz_compact():
    d, failed = normalize_date("040512")
    assert d == date(2004, 5, 12)
    assert not failed


def test_normalize_date_unparseable_returns_null_and_flag():
    d, failed = normalize_date("not-a-date")
    assert d is None
    assert failed


def test_normalize_document_number_strips_and_uppercases():
    value, flagged = normalize_document_number(" p1234567 ", r"^[A-Z][0-9]{7}$")
    assert value == "P1234567"
    assert not flagged


def test_normalize_document_number_flags_mismatch_without_autocorrecting():
    value, flagged = normalize_document_number("P123456O", r"^[A-Z][0-9]{7}$")  # trailing char is letter O, not digit
    assert value == "P123456O"  # returned as-is, never auto-corrected to a digit
    assert flagged


def test_normalize_name_whitespace_and_case_only():
    assert normalize_name("  john   smith ") == "JOHN SMITH"
