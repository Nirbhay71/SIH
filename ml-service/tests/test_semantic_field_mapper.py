"""Semantic field mapping for non-MRZ documents (Aadhaar, Voter ID, ...).

Fixtures are real-shaped OCR line sequences — including the boilerplate and
adjacent-value layouts that previously caused mis-picks — not idealized
"NAME: X" pairs, since the whole point of this module is coping with what
PaddleOCR actually returns for these cards.
"""
from src.ocr.semantic_field_mapper import extract_semantic_fields
from src.schemas import FieldExtraction


def _fields(*lines: str, confidence: float = 0.95) -> dict[str, FieldExtraction]:
    return {f"line_{i}": FieldExtraction(value=text, confidence=confidence) for i, text in enumerate(lines)}


AADHAAR_LINES = (
    "भारत सरकार",
    "GOVERNMENT OF INDIA",
    "दर्शन नीरवभाई बुद्धदेव",
    "Darshan Niravbhai Buddhdev",
    "जन्म तारीख/DOB: 01/12/2006",
    "पुरुष/ MALE",
    "Mobile No: 9426986139",
    "8269 7276 9502",
    "Unique Identification Authority of India",
    "VID : 9174 7742 0712 8083",
)


def test_aadhaar_fields_are_mapped():
    result = extract_semantic_fields(_fields(*AADHAAR_LINES))
    assert result["date_of_birth"].value == "01/12/2006"
    assert result["gender"].value == "M"
    assert result["mobile_number"].value == "9426986139"
    assert result["name"].value == "Darshan Niravbhai Buddhdev"


def test_document_number_prefers_aadhaar_over_vid():
    """The 16-digit VID sits right next to the 12-digit Aadhaar number on
    the card; picking the VID would put a wrong ID on the audit record."""
    result = extract_semantic_fields(_fields(*AADHAAR_LINES))
    assert result["document_number"].value == "826972769502"


def test_printed_boilerplate_is_not_mistaken_for_the_name():
    """"Unique Identification Authority of India" is longer and just as
    alphabetic as a real name — the blocklist is what keeps it out."""
    result = extract_semantic_fields(_fields(*AADHAAR_LINES))
    assert "Authority" not in result["name"].value
    assert "GOVERNMENT" not in result["name"].value.upper()


def test_dob_value_on_the_following_line_is_still_found():
    result = extract_semantic_fields(_fields("Date of Birth", "15/08/1991", "MALE"))
    assert result["date_of_birth"].value == "15/08/1991"


def test_voter_id_epic_number_is_mapped():
    result = extract_semantic_fields(_fields("ELECTION COMMISSION OF INDIA", "ABC1234567", "Ramesh Kumar"))
    assert result["document_number"].value == "ABC1234567"


def test_semantic_confidence_is_below_the_source_line_confidence():
    """The label is this module's guess, not PaddleOCR's — that uncertainty
    has to show up in the reported confidence."""
    result = extract_semantic_fields(_fields("DOB: 01/12/2006", confidence=0.9))
    assert result["date_of_birth"].confidence < 0.9


def test_no_text_yields_no_fields():
    assert extract_semantic_fields({}) == {}


def test_dob_with_slashes_misread_as_digits_is_reconstructed():
    """PaddleOCR reads "/" as "1" on these cards constantly:
    "01/12/2006" comes back as "0111212006"."""
    result = extract_semantic_fields(_fields("DOB: 0111212006"))
    assert result["date_of_birth"].value == "01/12/2006"


def test_dob_with_separators_dropped_is_reconstructed():
    result = extract_semantic_fields(_fields("DOB 01122006"))
    assert result["date_of_birth"].value == "01/12/2006"


def test_impossible_date_is_rejected_rather_than_stored():
    """A wrong DOB on a border record is worse than a missing one —
    acceptance_policy already fails closed on an unknown DOB."""
    result = extract_semantic_fields(_fields("DOB: 99999999"))
    assert "date_of_birth" not in result


# Verbatim PaddleOCR output for a real Aadhaar photo — messy on purpose.
# Every earlier version of this module mis-handled at least one of these
# lines, so they are kept exactly as the engine produced them.
REAL_MESSY_OCR_LINES = (
    "Aaoha?",
    "श न२ाछ कुखव",
    "2910912013 Darshan Niravbhai Buddhdev",  # sideways-printed issue date pulled into the name's line
    "Yभ त2NDOB: 011212006 30/111202?",        # DOB label garbled, "/" read as "1", extra dates alongside
    "पुष MALE",
    "Mobile No: 9425985139 पपठ",
    "Ladhaar.",                                 # garbled "Aadhaar" — a single token, not a name
    "8259 7275 950२",                          # Devanagari digit inside the Aadhaar number
    "VID ९174 774२ 071२ 808३",
)


def test_real_messy_ocr_still_yields_the_right_fields():
    result = extract_semantic_fields(_fields(*REAL_MESSY_OCR_LINES))
    assert result["date_of_birth"].value == "01/12/2006"
    assert result["gender"].value == "M"
    assert result["mobile_number"].value == "9425985139"
    assert result["name"].value == "Darshan Niravbhai Buddhdev"


def test_name_survives_marginalia_glued_onto_its_line():
    """Line grouping pulls sideways-printed text in; the name run has to be
    recovered from inside the line rather than the line being discarded."""
    result = extract_semantic_fields(_fields(*REAL_MESSY_OCR_LINES))
    assert not result["name"].value.startswith("29")


def test_single_garbled_token_is_not_taken_as_a_name():
    result = extract_semantic_fields(_fields(*REAL_MESSY_OCR_LINES))
    assert result["name"].value != "Ladhaar."


def test_devanagari_digits_make_a_number_unreadable_rather_than_wrong():
    """"8259 7275 950२" must not become an Aadhaar number — a corrupted ID
    on an audit record is worse than an absent one."""
    result = extract_semantic_fields(_fields(*REAL_MESSY_OCR_LINES))
    assert "document_number" not in result
