"""
Module 1 — OCR Extraction (mock implementation).

Real version (teammate's build) would use a document-specific OCR pipeline
(MRZ parsing for passports, layout-aware field extraction for visas/IDs).
This mock returns a fixed realistic field set with small randomized
variation and a per-field confidence score, occasionally simulating a
low-confidence field to demonstrate the "flag for officer review" behavior.

Contract: run_ocr(document_image: bytes, doc_type_hint: str | None) -> dict
"""
import random
from datetime import date, timedelta

NAMES = ["Ramesh Thapa", "Anjali Gurung", "Suresh Rai", "Priya Sharma", "Bikram Lama"]
NATIONALITIES = ["Indian", "Nepali", "Bhutanese"]
DOC_TYPES = ["passport", "visa", "national_id", "driving_license", "permit"]


def _confidence(low: bool = False) -> float:
    if low:
        return round(random.uniform(0.35, 0.55), 2)
    return round(random.uniform(0.88, 0.99), 2)


def run_ocr(document_image: bytes, doc_type_hint: str | None = None, force_tampered: bool = False) -> dict:
    random.seed(len(document_image) + (1 if force_tampered else 0))

    doc_type = doc_type_hint or random.choice(DOC_TYPES)
    name = random.choice(NAMES)
    nationality = random.choice(NATIONALITIES)

    issue_date = date.today() - timedelta(days=random.randint(200, 1500))
    expiry_date = issue_date + timedelta(days=3650)
    if force_tampered:
        # Simulate an inconsistent/altered expiry so Module 2 has something to flag.
        expiry_date = issue_date - timedelta(days=30)

    dob = date.today() - timedelta(days=random.randint(365 * 18, 365 * 55))

    low_conf_field = random.random() < 0.15
    low_conf_choice = random.choice(["name", "dob", "doc_number"]) if low_conf_field else None

    fields = {
        "name": {"value": name, "confidence": _confidence(low_conf_choice == "name")},
        "document_number": {
            "value": f"{nationality[:1].upper()}{random.randint(1000000, 9999999)}",
            "confidence": _confidence(low_conf_choice == "doc_number"),
        },
        "nationality": {"value": nationality, "confidence": _confidence()},
        "date_of_birth": {"value": dob.isoformat(), "confidence": _confidence(low_conf_choice == "dob")},
        "date_of_issue": {"value": issue_date.isoformat(), "confidence": _confidence()},
        "date_of_expiry": {"value": expiry_date.isoformat(), "confidence": _confidence()},
        "gender": {"value": random.choice(["M", "F"]), "confidence": _confidence()},
    }

    if doc_type == "visa":
        fields["visa_number"] = {"value": f"V{random.randint(100000, 999999)}", "confidence": _confidence()}
        fields["visa_type"] = {"value": random.choice(["Tourist", "Business", "Transit"]), "confidence": _confidence()}
        fields["entry_validity"] = {"value": "Multiple", "confidence": _confidence()}
        fields["stay_duration"] = {"value": "90 days", "confidence": _confidence()}

    low_confidence_fields = [k for k, v in fields.items() if v["confidence"] < 0.6]

    return {
        "doc_type": doc_type,
        "fields": fields,
        "low_confidence_fields": low_confidence_fields,
        "face_crop": "placeholder_face_crop",
    }
