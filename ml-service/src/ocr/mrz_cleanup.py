"""Turns raw MRZ OCR output into values an officer can read and trust.

Three defects showed up on a real Indian passport (verified against the
committed session data, not synthetic input):

1. The name came out as "ROHIT MAHAJANKXKX     KK KKKKKKKKKKKK". An MRZ pads
   the rest of a name field with "<" filler, and OCR reads that filler as
   K / X / C — glued onto the last name and as trailing junk tokens.
2. The document type came out as "P<" (the "<" is filler, not part of it).
3. Every field carried the same 61% confidence — passporteye's single
   whole-MRZ score — even though the document number, date of birth and
   expiry each have their own ICAO check digit that *verified*. A field whose
   check digit passes is about as certain as OCR gets; reporting it at 61%
   told the officer the wrong thing, and made the validator treat verified
   checksums as "inconclusive".
"""
import re

from src.validation.mrz_checksum import compute_check_digit

# Letters OCR most often produces for the "<" filler character.
_FILLER_LOOKALIKES = set("KXC")
# Only long trailing runs are treated as glued filler: a single trailing K/X/C
# is a normal letter ("MARK", "ALEX", "ROCK"), a run of three is not.
_GLUED_FILLER_MIN_RUN = 3


def clean_mrz_name(raw: str | None) -> str | None:
    """Removes filler-lookalike junk from an MRZ name; never invents or
    alters real letters. Returns the input unchanged if it has nothing to clean."""
    if not raw:
        return raw
    tokens = raw.split()
    if not tokens:
        return raw

    # 1. Trailing tokens made only of filler lookalikes. A lone "K" is kept
    #    unless it follows already-dropped junk (it could be a real initial).
    dropped_any = False
    while len(tokens) > 1:
        last = tokens[-1]
        if set(last) <= _FILLER_LOOKALIKES and (len(last) >= 2 or dropped_any):
            tokens.pop()
            dropped_any = True
        else:
            break

    # 2. A run of filler lookalikes glued to the end of the final real token
    #    ("MAHAJAN" + "KXKX"), only when a real name remains after removing it.
    tail = re.search(r"[KXC]{%d,}$" % _GLUED_FILLER_MIN_RUN, tokens[-1])
    if tail and len(tokens[-1]) - len(tail.group(0)) >= 2:
        tokens[-1] = tokens[-1][: tail.start()]

    return " ".join(tokens)


def clean_document_type(raw: str | None) -> str | None:
    """"P<" -> "P". The "<" is MRZ filler, not part of the document type."""
    if not raw:
        return raw
    return raw.replace("<", "").strip() or raw


# Line-1 fields carry no check digit of their own; line-2 nationality and sex
# sit between check-digit-verified fields but are not covered by them.
LINE1_FIELDS = ("document_type", "country", "name", "surname", "given_names")
LINE2_UNCHECKED_FIELDS = ("nationality", "sex")
_CHECKED = {  # field -> (width of the checked span, key in check_digits)
    "document_number": (9, "document_number"),
    "date_of_birth": (6, "date_of_birth"),
    "expiry_date": (6, "expiry_date"),
}
_PASS_CONFIDENCE = 0.99
_FAIL_CONFIDENCE = 0.35   # low on purpose: a failed check on an OCR read is more
                          # likely a misread than tampering, so it must not be
                          # promoted to a confident "fail" (mrz_checksum.py rule)
_LINE1_CONFIDENCE = 0.80  # unverified by any checksum
_LINE2_ALIGNED_CONFIDENCE = 0.95


def mrz_field_confidences(
    fields: dict[str, str | None], check_digits: dict[str, str | None], base_confidence: float
) -> dict[str, float]:
    """Per-field confidence from what each field's own check digit says.

    Checked fields: pass -> very high, fail -> low. If all three verify, the
    second MRZ line was read cleanly, so its unchecked fields (nationality,
    sex) are given high confidence too, and the name line a moderate one
    (nothing verifies it). If any check fails or is missing, everything
    unverified falls back to the whole-MRZ score rather than being flattered."""
    statuses: dict[str, bool | None] = {}
    for key, (width, digit_key) in _CHECKED.items():
        value, printed = fields.get(key), (check_digits or {}).get(digit_key)
        if value is None or printed is None or not str(printed).strip().isdigit():
            statuses[key] = None
            continue
        try:
            statuses[key] = str(compute_check_digit(value.ljust(width, "<"))) == str(printed).strip()
        except ValueError:
            statuses[key] = None

    out: dict[str, float] = {}
    for key, ok in statuses.items():
        if ok is True:
            out[key] = _PASS_CONFIDENCE
        elif ok is False:
            out[key] = _FAIL_CONFIDENCE

    all_verified = all(v is True for v in statuses.values())
    for key in fields:
        if key in out:
            continue
        if all_verified and key in LINE2_UNCHECKED_FIELDS:
            out[key] = _LINE2_ALIGNED_CONFIDENCE
        elif all_verified and key in LINE1_FIELDS:
            out[key] = _LINE1_CONFIDENCE
        else:
            out[key] = base_confidence
    return out
