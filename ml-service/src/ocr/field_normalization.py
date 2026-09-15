"""Section 5.4 — deterministic field normalization. No ML, no guessing:
an unparseable value becomes null plus a quality flag, never a silent
best-effort correction (Section 12A — auto-correcting ambiguous OCR
characters like 0/O could mask real tampering or fabricate a checksum
failure)."""
import re
from datetime import date, datetime

DATE_FORMATS = ["%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%y%m%d"]


def normalize_date(raw: str | None) -> tuple[date | None, bool]:
    """Returns (parsed_date_or_None, parse_failed)."""
    if not raw or not raw.strip():
        return None, True

    cleaned = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date(), False
        except ValueError:
            continue

    return None, True


def normalize_document_number(raw: str | None, pattern: str | None) -> tuple[str | None, bool]:
    """Strips whitespace, uppercases, then checks against `pattern`.

    Returns (value, format_flagged). Never auto-corrects ambiguous
    characters (0/O, 1/I, 5/S) — a mismatch is flagged for the officer,
    not silently "fixed."
    """
    if raw is None:
        return None, True

    cleaned = re.sub(r"\s+", "", raw).upper()
    if pattern and not re.match(pattern, cleaned):
        return cleaned, True

    return cleaned, False


def normalize_name(raw: str | None) -> str | None:
    """Whitespace/capitalization normalization only — never spelling
    correction (Section 5.4)."""
    if raw is None:
        return None
    return re.sub(r"\s+", " ", raw.strip()).upper()
