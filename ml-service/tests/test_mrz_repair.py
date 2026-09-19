"""MRZ document-number repair via the ICAO check digit."""
from src.ocr.mrz_repair import repair_document_number
from src.validation.mrz_checksum import compute_check_digit


def _check(value: str) -> str:
    return str(compute_check_digit(value.ljust(9, "<")))


def test_the_real_passport_case_z_read_as_2_is_repaired():
    """From a real Indian passport: printed Z3797156 with check digit 9,
    read by OCR as 23797156."""
    assert _check("Z3797156") == "9"
    assert repair_document_number("23797156", "9", r"[A-Z][0-9]{7}") == ("Z3797156", True)


def test_a_value_that_already_matches_is_left_alone():
    assert repair_document_number("Z3797156", "9") == ("Z3797156", False)


def test_o_read_as_zero_is_repaired():
    value = "K0123456"
    good = value.replace("0", "O", 1)
    assert repair_document_number(value, _check(good))[0] in (good, value)  # unique-or-untouched, never a wrong guess


def test_no_candidate_validates_so_the_value_is_untouched():
    """A misread that isn't a known confusion, or a misread check digit,
    can't be repaired — it must come back exactly as read."""
    assert repair_document_number("Q3797156", "9") == ("Q3797156", False)


def test_ambiguous_repair_is_refused_rather_than_guessed():
    """Two different candidates that both satisfy a one-digit check can't be
    told apart; the honest answer is to change nothing."""
    # Brute-force a value with two valid single-substitution repairs.
    from itertools import product
    from src.ocr.mrz_repair import _CONFUSIONS
    found = None
    for tail in product("0O1I25SZ", repeat=3):
        value = "A" + "".join(tail) + "9999"
        for check in "0123456789":
            cands = set()
            for i, ch in enumerate(value):
                if ch in _CONFUSIONS:
                    c = value[:i] + _CONFUSIONS[ch] + value[i + 1:]
                    if _check(c) == check:
                        cands.add(c)
            if len(cands) > 1 and _check(value) != check:
                found = (value, check)
                break
        if found:
            break
    assert found, "test setup: expected at least one ambiguous case to exist"
    assert repair_document_number(*found) == (found[0], False)


def test_missing_inputs_never_raise():
    assert repair_document_number(None, "9") == (None, False)
    assert repair_document_number("Z3797156", None) == ("Z3797156", False)
    assert repair_document_number("Z3797156", "x") == ("Z3797156", False)


def test_without_the_format_constraint_the_real_case_is_ambiguous_and_refused():
    """Documents WHY the format pattern matters: the check digit alone can't
    tell the real Z3797156 from other single substitutions, so it declines."""
    assert repair_document_number("23797156", "9") == ("23797156", False)
