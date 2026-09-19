"""MRZ cleanup, using strings taken verbatim from real/observed passport reads."""
from src.ocr.mrz_cleanup import clean_document_type, clean_mrz_name, mrz_field_confidences


def test_real_passport_name_is_cleaned():
    """The exact string a user saw in the UI."""
    assert clean_mrz_name("ROHIT MAHAJANKXKX     KK KKKKKKKKKKKK") == "ROHIT MAHAJAN"


def test_sample_document_trailing_filler_is_cleaned():
    assert clean_mrz_name("SHARMA RAVI KUMAR         K KKKKKKKKKK") == "SHARMA RAVI KUMAR"


def test_names_containing_k_x_c_are_left_alone():
    for name in ("RAVI KUMAR", "ANKIT KHAN", "ALEX MAX", "MARK DAKOTA", "NIKKI ROCK", "FELIX COX"):
        assert clean_mrz_name(name) == name, name


def test_a_lone_k_initial_is_not_dropped():
    assert clean_mrz_name("RAVI K") == "RAVI K"


def test_never_reduces_a_name_to_nothing():
    assert clean_mrz_name("KKKK") == "KKKK"
    assert clean_mrz_name(None) is None and clean_mrz_name("") == ""


def test_document_type_filler_is_removed():
    assert clean_document_type("P<") == "P"
    assert clean_document_type("PD") == "PD"


def _fields():
    return {"document_number": "Z3797156", "date_of_birth": "711204", "expiry_date": "270830",
            "nationality": "IND", "sex": "M", "name": "ROHIT MAHAJAN", "document_type": "P", "country": "IND"}


def test_verified_check_digits_give_high_confidence_not_a_flat_61_percent():
    checks = {"document_number": "9", "date_of_birth": "1", "expiry_date": "0"}
    conf = mrz_field_confidences(_fields(), checks, base_confidence=0.61)
    assert conf["document_number"] == conf["date_of_birth"] == conf["expiry_date"] == 0.99
    assert conf["nationality"] == conf["sex"] == 0.95
    assert conf["name"] == 0.80   # nothing verifies line 1, so it is not flattered


def test_a_failed_check_digit_lowers_only_that_field_and_stops_flattering_others():
    checks = {"document_number": "9", "date_of_birth": "7", "expiry_date": "0"}  # DOB digit wrong
    conf = mrz_field_confidences(_fields(), checks, base_confidence=0.61)
    assert conf["date_of_birth"] < 0.5
    assert conf["document_number"] == 0.99
    assert conf["nationality"] == 0.61 and conf["name"] == 0.61   # fall back to the whole-MRZ score


def test_missing_check_digits_fall_back_to_the_base_score():
    conf = mrz_field_confidences(_fields(), {}, base_confidence=0.61)
    assert set(conf.values()) == {0.61}
