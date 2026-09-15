"""Section 5.2 — MRZ extraction for passport/visa document types.

Uses PassportEye's `read_mrz`. Country-agnostic by design (Section 1B):
this module must never branch on issuing country — only document-type
*format validation* (Module 2) is allowed to vary by country.
"""
import logging
import tempfile
from pathlib import Path

import numpy as np

logger = logging.getLogger("src.ocr")


class MRZExtractionResult:
    def __init__(
        self,
        found: bool,
        raw_lines: list[str] | None = None,
        fields: dict[str, str] | None = None,
        check_digits: dict[str, str] | None = None,
        valid_score: float | None = None,
        method: str = "not_applicable",
    ):
        self.found = found
        self.raw_lines = raw_lines
        self.fields = fields or {}
        self.check_digits = check_digits or {}
        self.valid_score = valid_score
        self.method = method


def extract_mrz(image: np.ndarray) -> MRZExtractionResult:
    """Runs PassportEye's read_mrz on `image` (a full document image or a
    tightly-cropped MRZ region). Returns found=False (never raises) if no
    MRZ is detected — Section 5.2 requires this to be an explicit,
    typed outcome, not a caught exception, so downstream code can fall
    back to free-text OCR and mark `mrz_extraction_method: "fallback_ocr"`.
    """
    try:
        from passporteye import read_mrz
    except ImportError:
        logger.warning("passporteye is not installed; MRZ extraction unavailable in this environment.")
        return MRZExtractionResult(found=False, method="not_applicable")

    import cv2

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "mrz_input.png"
        cv2.imwrite(str(tmp_path), image)
        mrz = read_mrz(str(tmp_path))

    if mrz is None:
        return MRZExtractionResult(found=False, method="fallback_ocr")

    data = mrz.to_dict()
    raw_lines = [data.get("raw_text", "")] if "raw_text" in data else None
    if hasattr(mrz, "aux") and "text" in getattr(mrz, "aux", {}):
        raw_lines = mrz.aux["text"]

    fields = {
        "document_type": data.get("type"),
        "name": f"{data.get('surname', '')} {data.get('names', '')}".strip(),
        "surname": data.get("surname"),
        "given_names": data.get("names"),
        "document_number": data.get("number"),
        "nationality": data.get("nationality"),
        "date_of_birth": data.get("date_of_birth"),
        "sex": data.get("sex"),
        "expiry_date": data.get("expiration_date"),
        "country": data.get("country"),
    }

    check_digits = {
        "document_number": data.get("check_number"),
        "date_of_birth": data.get("check_date_of_birth"),
        "expiry_date": data.get("check_expiration_date"),
        "composite": data.get("check_composite"),
        "personal_number": data.get("check_personal_number"),
    }

    return MRZExtractionResult(
        found=True,
        raw_lines=raw_lines,
        fields=fields,
        check_digits=check_digits,
        valid_score=float(data.get("valid_score", 0.0)) / 100.0 if "valid_score" in data else None,
        method="passporteye",
    )
