"""Best-effort mapping from raw OCR text lines to semantically named fields
(name, date_of_birth, gender, document_number, mobile_number) for non-MRZ
documents (Aadhaar, Voter ID, etc).

This is NOT a trained layout-understanding model — it is keyword/pattern
matching over the lines PaddleOCR returns, so that a value the OCR
genuinely read isn't silently discarded just because this build has no
per-document-type field-position model (see docs/ARCHITECTURE.md).
Confidence on every field produced here is deliberately scaled below the
source line's own OCR confidence, because the *label* (deciding which line
means "date of birth") is this module's guess, not something PaddleOCR
reported.

Input is the ordered {line_0: ..., line_1: ...} dict built in pipeline.py,
in reading order — order matters, since a label and its value are often on
adjacent lines rather than the same one.
"""
import re
from datetime import date

from src.schemas import FieldExtraction

_CONFIDENCE_PENALTY = 0.9  # a semantic-mapping guess is inherently less certain than the raw read

# NOTE on [0-9] rather than \d throughout: Python's \d also matches non-ASCII
# digits, and PaddleOCR's Hindi pass regularly mixes Devanagari numerals into
# otherwise-Latin runs ("8259 7275 950२"). Accepting those produced an Aadhaar
# number with a Devanagari digit in it — not a value any downstream system can
# use — so every numeric pattern here is ASCII-only, and a partially-Devanagari
# read is correctly treated as unreadable rather than silently stored.

_DOB_KEYWORD_RE = re.compile(r"(dob|date\s*of\s*birth|जन्म|જન્મ)", re.IGNORECASE)
_DATE_RE = re.compile(r"([0-9]{1,2}\s*[/\-.]\s*[0-9]{1,2}\s*[/\-.]\s*[0-9]{2,4})")
# A bare digit run where the separators were lost or misread. On these cards
# PaddleOCR frequently reads "/" as "1" ("29/09/2013" -> "2910912013"), so
# 8, 9 and 10-digit runs are all plausible renderings of DD/MM/YYYY.
# Deliberately no \b anchors: OCR routinely glues the label to the value
# ("DOB01122006"), where a leading word boundary never matches. False
# positives are caught by _plausible_date() rather than by the pattern.
_DATE_DIGITS_RE = re.compile(r"([0-9]{8,10})")
_YEAR_ONLY_RE = re.compile(r"(?:year\s*of\s*birth|yob)\D{0,10}([0-9]{4})", re.IGNORECASE)

_MOBILE_KEYWORD_RE = re.compile(r"(mobile|मोबाइल|મોબાઈલ)", re.IGNORECASE)
_MOBILE_DIGITS_RE = re.compile(r"([6-9][0-9]{9})")  # Indian mobile numbers start 6-9

_GENDER_RE = re.compile(r"(female|male|पुरुष|महिला|स्त्री|પુરુષ|સ્ત્રી)", re.IGNORECASE)
_FEMALE_RE = re.compile(r"(female|महिला|स्त्री|સ્ત્રી)", re.IGNORECASE)

# Aadhaar: 12 digits, conventionally printed in three 4-digit groups.
_AADHAAR_RE = re.compile(r"\b([0-9]{4}\s?[0-9]{4}\s?[0-9]{4})\b")
# Voter ID (EPIC): three letters then seven digits.
_EPIC_RE = re.compile(r"\b([A-Z]{3}[0-9]{7})\b")
# A VID is 16 digits and sits right next to the Aadhaar number on the card —
# must never be mistaken for it.
_VID_LINE_RE = re.compile(r"\bvid\b", re.IGNORECASE)

# Printed boilerplate that is NOT the holder's name. Without this the name
# heuristic happily picks "Unique Identification Authority of India", which
# is longer and just as alphabetic as a real name.
_NAME_BLOCKLIST_RE = re.compile(
    r"(government\s+of\s+india|unique\s+identification|authority\s+of\s+india|aadhaar|आधार|आधार|"
    r"भारत\s*सरकार|भारतीय\s*विशिष्ट|election\s+commission|income\s+tax|department|"
    r"permanent\s+account|republic\s+of\s+india|मेरा\s*आधार|मारो\s*आधार|my\s+aadhaar|"
    r"proof\s+of\s+identity|not\s+a\s+proof|help@|www\.|\.gov\.in|address|पता|સરનામું|"
    r"date\s+of\s+issue|issued|details\s+as\s+on|vid|dob|mobile)",
    re.IGNORECASE,
)


def _line_items(text_fields: dict[str, FieldExtraction]) -> list[tuple[str, FieldExtraction]]:
    """Dict insertion order is reading order (pipeline.py inserts line_0,
    line_1, ... top-to-bottom), so a plain list() preserves adjacency."""
    return list(text_fields.items())


def _normalize_date(raw: str) -> str:
    return re.sub(r"\s+", "", raw)


def _plausible_date(day: int, month: int, year: int) -> bool:
    """Deliberately strict: a reconstruction that isn't a real calendar date
    is rejected outright rather than stored. A confidently-wrong DOB on a
    border record is worse than an honestly missing one — acceptance_policy
    already fails closed when the DOB is unknown."""
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return False
    if not (1900 <= year <= date.today().year):
        return False
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


def _repair_date_digits(digits: str) -> str | None:
    """Reconstructs DD/MM/YYYY from a separator-less or separator-garbled
    digit run. Tries each split consistent with the run's length — including
    the "/ was read as 1" case these cards produce constantly — and returns
    the first that validates as a real date. Returns None if none do, which
    is the honest outcome for a genuinely corrupted read."""
    candidates: list[tuple[str, str, str]] = []
    if len(digits) == 8:  # DDMMYYYY, separators simply dropped
        candidates.append((digits[0:2], digits[2:4], digits[4:8]))
    elif len(digits) == 9:  # exactly one separator survived as a stray digit
        candidates.append((digits[0:2], digits[3:5], digits[5:9]))
        candidates.append((digits[0:2], digits[2:4], digits[5:9]))
    elif len(digits) == 10:  # both separators misread as digits
        candidates.append((digits[0:2], digits[3:5], digits[6:10]))

    for dd, mm, yyyy in candidates:
        if _plausible_date(int(dd), int(mm), int(yyyy)):
            return f"{dd}/{mm}/{yyyy}"
    return None


_NAME_MIN_WORDS = 2
_NAME_MIN_WORD_LEN = 2


def _longest_name_run(text: str) -> str | None:
    """Longest run of consecutive word-like tokens in `text`, or None if it
    has no run of at least _NAME_MIN_WORDS.

    Scoring whole lines didn't survive real output: PaddleOCR's line grouping
    pulls sideways-printed marginalia into the name's line ("2910912013
    Darshan Niravbhai Buddhdev"), which sank the line's alphabetic ratio and
    got the real name discarded — while a single garbled token ("Ladhaar.",
    a mangled "Aadhaar") sailed through. Requiring consecutive alphabetic
    words, and keeping only that run, handles both.
    """
    best: list[str] = []
    current: list[str] = []
    for token in re.split(r"\s+", text):
        stripped = token.strip(".,:;|/\\()[]")
        is_word = len(stripped) >= _NAME_MIN_WORD_LEN and all(c.isalpha() for c in stripped)
        if is_word:
            current.append(stripped)
            if len(current) > len(best):
                best = list(current)
        else:
            current = []

    return " ".join(best) if len(best) >= _NAME_MIN_WORDS else None


def _find_date_in(text: str) -> str | None:
    """First plausible date in `text`, trying properly-separated dates before
    falling back to repairing bare digit runs.

    Every candidate is tried rather than just the first match: a DOB line on
    these cards routinely carries more than one number (issue date, "details
    as on" date, stray digits from a neighbouring column), so stopping at the
    first regex hit picked the wrong one. Text is searched as-is — an earlier
    version stripped spaces first, which fused adjacent numbers into
    nonexistent 10-digit "dates".
    """
    for match in _DATE_RE.finditer(text):
        normalized = _normalize_date(match.group(1))
        parts = re.split(r"[/\-.]", normalized)
        if len(parts) == 3:
            day, month, year = parts
            if len(year) == 2:
                year = f"20{year}" if int(year) <= date.today().year % 100 else f"19{year}"
            if _plausible_date(int(day), int(month), int(year)):
                return f"{int(day):02d}/{int(month):02d}/{year}"

    for match in _DATE_DIGITS_RE.finditer(text):
        repaired = _repair_date_digits(match.group(1))
        if repaired:
            return repaired

    return None


def extract_semantic_fields(text_fields: dict[str, FieldExtraction]) -> dict[str, FieldExtraction]:
    """Returns semantically named fields inferred from `text_fields`.
    Callers should only add keys not already present, never overwrite."""
    items = _line_items(text_fields)
    semantic: dict[str, FieldExtraction] = {}
    consumed: set[str] = set()

    for index, (key, fe) in enumerate(items):
        text = (fe.value or "").strip()
        if not text:
            continue

        # --- Date of birth: label and value are often on the same line,
        # but on several real cards the value wraps to the next one. ---
        if "date_of_birth" not in semantic and _DOB_KEYWORD_RE.search(text):
            # The value is usually on the label's own line, but on several
            # real cards it wraps to the next one — and PaddleOCR's word-level
            # boxes can push it there even when the print does not.
            searched = [(text, fe)]
            if index + 1 < len(items):
                searched.append((items[index + 1][1].value or "", items[index + 1][1]))

            for candidate_text, source in searched:
                value = _find_date_in(candidate_text)
                if value:
                    semantic["date_of_birth"] = FieldExtraction(
                        value=value, confidence=source.confidence * _CONFIDENCE_PENALTY
                    )
                    consumed.add(key)
                    break
            if "date_of_birth" in semantic:
                continue

        if "date_of_birth" not in semantic:
            year_match = _YEAR_ONLY_RE.search(text)
            if year_match:
                # Year-of-birth-only cards (common on older Aadhaar prints).
                # Stored as a bare year — acceptance_policy.parse_dob will
                # reject it rather than invent a day/month, which is correct:
                # a guessed DOB is worse than an honestly unknown one.
                semantic["date_of_birth"] = FieldExtraction(
                    value=year_match.group(1), confidence=fe.confidence * _CONFIDENCE_PENALTY
                )
                consumed.add(key)
                continue

        # --- Mobile number ---
        if "mobile_number" not in semantic and _MOBILE_KEYWORD_RE.search(text):
            match = _MOBILE_DIGITS_RE.search(text.replace(" ", ""))
            if match:
                semantic["mobile_number"] = FieldExtraction(
                    value=match.group(1), confidence=fe.confidence * _CONFIDENCE_PENALTY
                )
                consumed.add(key)
                continue

        # --- Gender ---
        if "gender" not in semantic and _GENDER_RE.search(text):
            semantic["gender"] = FieldExtraction(
                value="F" if _FEMALE_RE.search(text) else "M",
                confidence=fe.confidence * _CONFIDENCE_PENALTY,
            )
            consumed.add(key)
            continue

        # --- Document number (Aadhaar 12-digit / EPIC) ---
        if "document_number" not in semantic and not _VID_LINE_RE.search(text):
            epic = _EPIC_RE.search(text.replace(" ", ""))
            if epic:
                semantic["document_number"] = FieldExtraction(
                    value=epic.group(1), confidence=fe.confidence * _CONFIDENCE_PENALTY
                )
                consumed.add(key)
                continue
            aadhaar = _AADHAAR_RE.search(text)
            if aadhaar:
                semantic["document_number"] = FieldExtraction(
                    value=re.sub(r"\s+", "", aadhaar.group(1)),
                    confidence=fe.confidence * _CONFIDENCE_PENALTY,
                )
                consumed.add(key)
                continue

    # --- Name: the strongest run of consecutive alphabetic words on any
    # line that isn't printed boilerplate and wasn't consumed above. ---
    best_value, best_confidence, best_score = None, 0.0, -1.0
    for key, fe in items:
        if key in consumed:
            continue
        text = (fe.value or "").strip()
        if _NAME_BLOCKLIST_RE.search(text):
            continue
        candidate = _longest_name_run(text)
        if not candidate:
            continue
        latin = sum(1 for c in candidate if "a" <= c.lower() <= "z")
        score = len(candidate) * (1.0 + latin / max(len(candidate), 1))
        if score > best_score:
            best_value, best_confidence, best_score = candidate, fe.confidence, score

    if best_value is not None:
        semantic["name"] = FieldExtraction(
            value=best_value, confidence=best_confidence * _CONFIDENCE_PENALTY
        )

    return semantic
