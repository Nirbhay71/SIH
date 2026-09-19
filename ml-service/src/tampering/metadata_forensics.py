"""Section 7.4 — Image Metadata (EXIF) Analysis.

Weighted lowest of all Module 3 signals downstream (Section 8, feature
builder) — metadata is trivially stripped by even an unsophisticated
forger, and its absence proves nothing about authenticity (Section 12A).
"""
import io
from datetime import datetime

from PIL import Image
from PIL.ExifTags import TAGS

KNOWN_EDITING_SOFTWARE = ["photoshop", "gimp", "paint.net", "affinity photo", "pixlr", "canva", "snapseed", "picsart", "coreldraw", "lightroom"]


def extract_exif(raw_bytes: bytes) -> dict[str, str]:
    """Returns a flat dict of decoded EXIF tags. Returns an empty dict
    (never raises) when metadata is absent or unreadable — this is an
    expected, common case (Section 7.4), not an error."""
    try:
        image = Image.open(io.BytesIO(raw_bytes))
        raw_exif = image.getexif()
    except Exception:
        return {}

    if not raw_exif:
        return {}

    decoded = {}
    for tag_id, value in raw_exif.items():
        tag_name = TAGS.get(tag_id, str(tag_id))
        decoded[tag_name] = str(value)
    return decoded


def analyze_metadata(raw_bytes: bytes) -> tuple[int, list[str]]:
    """Returns (flag_count, flags)."""
    exif = extract_exif(raw_bytes)
    flags: list[str] = []

    software = exif.get("Software", "").lower()
    if any(tool in software for tool in KNOWN_EDITING_SOFTWARE):
        flags.append(f"known_editing_software:{software}")

    original = exif.get("DateTimeOriginal")
    modified = exif.get("DateTime")
    if original and modified:
        try:
            fmt = "%Y:%m:%d %H:%M:%S"
            if datetime.strptime(modified, fmt) > datetime.strptime(original, fmt):
                flags.append("modification_after_capture")
        except ValueError:
            pass  # unparseable EXIF timestamps are not, on their own, evidence of anything

    return len(flags), flags
