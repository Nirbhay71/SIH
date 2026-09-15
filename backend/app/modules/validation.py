"""
Module 2 — Document Validation (mock/rule-based implementation).

This is a rules layer, not fraud detection: it checks that OCR-extracted
data is well-formed and internally consistent for the stated document type.
See Part F.2 of the master spec.

Contract: run_validation(ocr_result: dict) -> dict
"""
import re
from datetime import date

MIN_LICENSE_AGE_YEARS = 18
DOC_NUMBER_RE = re.compile(r"^[A-Z][0-9]{6,8}$")


def _years_between(d1: date, d2: date) -> float:
    return (d2 - d1).days / 365.25


def run_validation(ocr_result: dict) -> dict:
    fields = ocr_result["fields"]
    doc_type = ocr_result["doc_type"]
    failures = []

    today = date.today()

    expiry = date.fromisoformat(fields["date_of_expiry"]["value"])
    issue = date.fromisoformat(fields["date_of_issue"]["value"])
    dob = date.fromisoformat(fields["date_of_birth"]["value"])

    if expiry < today:
        failures.append({"rule": "expiry_not_past", "reason": "Document expiry date is in the past (expired document)."})

    if issue >= expiry:
        failures.append({"rule": "issue_before_expiry", "reason": "Issue date is not before expiry date."})

    if doc_type == "driving_license" and _years_between(dob, issue) < MIN_LICENSE_AGE_YEARS:
        failures.append({"rule": "minimum_age", "reason": f"Holder was under {MIN_LICENSE_AGE_YEARS} at time of issue."})

    doc_number = fields["document_number"]["value"]
    if not DOC_NUMBER_RE.match(doc_number):
        failures.append({"rule": "doc_number_format", "reason": f"Document number '{doc_number}' does not match expected format."})

    if fields["gender"]["value"] not in ("M", "F", "X"):
        failures.append({"rule": "gender_enum", "reason": "Gender field is not a recognized value."})

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "failure_count": len(failures),
    }
