"""India-Nepal border document acceptance policy for Indian citizens, per
Embassy of India, Kathmandu (as provided in the project brief).

This is a distinct check from app/modules/validation.py's per-document-type
FORMAT validation: a document can be a perfectly genuine, well-formatted
Aadhaar card and still not be valid proof of citizenship for this specific
crossing. Both checks run independently and both surface as failures in
the same validation_result_json.failures list the frontend already
displays — see app/routers/verification.py's use of evaluate_acceptance().

Scope, explicitly: Indian citizens only (nationality "Indian"/"IND"). The
project brief did not specify Nepali-citizen-side rules for this crossing,
so non-Indian nationalities are NOT covered here — evaluate_acceptance()
returns applies=False for them, and callers must not treat that as either
an acceptance or a rejection.

Two provisions of the brief are handled outside evaluate_acceptance():
  - "Families traveling together": evaluate_family_provision() below, driven
    by the group/relationship fields on VerificationRecord (see the
    /api/verification/{id}/family endpoint). It only ever *upgrades* a
    document that failed this policy, and only when every condition is met.
  - "Only original, no photocopies or digital images": not decidable from an
    image in general (every submission is a digital image), so it is not part
    of this policy. What IS detectable is the physical signature of a
    monochrome photocopy of a colour-issued document; that is raised as a
    validation failure for the officer (see ml-service
    reproduction_check.py and ORIGINAL_REQUIRED_DOC_TYPES in the verification
    router), never as an automatic rejection.
"""
from datetime import date, datetime

# Adult (18-65), standard rule. Both "indian_passport" and "foreign_passport"
# are accepted here — they're the two doc_type keys the rest of the system
# (frontend's document-type dropdown, ml-service's document_formats.yaml)
# actually uses for a passport; a bare "passport" key here would silently
# reject every real passport submission (verified: this was exactly the
# case before this fix — a genuine Indian passport was flagged as an
# unrecognized, unaccepted document type).
STANDARD_ACCEPTED = {
    "indian_passport", "foreign_passport",
    "passport",  # app/modules/ocr.py's mock module's own generic key when no document_type_hint is supplied
    "voter_id", "emergency_certificate", "identity_certificate",
}

# Above 65 or below 15: exempted from the standard list, broader photo-ID set allowed.
AGE_EXEMPT_ACCEPTED = STANDARD_ACCEPTED | {"aadhaar", "driving_license", "ration_card", "cghs_card"}

# Ages 15-18: standard list plus a school-issued identity certificate.
MINOR_15_18_ACCEPTED = STANDARD_ACCEPTED | {"school_identity_certificate"}

# Explicitly called out in the brief as NOT accepted for the standard
# 18-65 bracket, despite being valid ID within India generally — named
# separately from "just not in the accepted set" so the rejection message
# can be specific about why.
EXPLICITLY_REJECTED_FOR_STANDARD_ADULT = {"aadhaar", "pan_card", "driving_license"}


def parse_dob(raw: str | None) -> date | None:
    """The two OCR sources this backend consumes store DOB differently: the
    mock module writes ISO (YYYY-MM-DD); real MRZ extraction (passporteye,
    via ml-service) leaves the raw 6-digit MRZ field (YYMMDD) unconverted.
    Tries both, plus one common printed format, before giving up — an
    unparseable DOB must fail closed via evaluate_acceptance's dob=None
    path, never silently skip the age check."""
    if not raw:
        return None
    raw = raw.strip()

    try:
        return date.fromisoformat(raw)
    except ValueError:
        pass

    if len(raw) == 6 and raw.isdigit():
        yy, mm, dd = int(raw[0:2]), int(raw[2:4]), int(raw[4:6])
        # ICAO 9303 convention: no century digit in the MRZ, so infer it —
        # a YY greater than the current two-digit year is assumed 19xx,
        # otherwise 20xx (this is the standard passport-MRZ heuristic, not
        # a guess specific to this codebase).
        current_yy = datetime.now().year % 100
        century = 1900 if yy > current_yy else 2000
        try:
            return date(century + yy, mm, dd)
        except ValueError:
            return None

    for fmt in ("%d %b %Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    # ml-service's semantic_field_mapper.py (non-MRZ documents — Aadhaar,
    # Voter ID, etc.) reads a DOB line via free-text OCR, and separators
    # ("/", "-") are sometimes lost in that read even when the digits
    # themselves are correct — an 8-digit DDMMYYYY run with no separator.
    # A wrong-length digit run (anything but exactly 8) is genuinely
    # corrupted OCR, not just missing separators, and must NOT be guessed
    # at — falls through to the fail-closed None below, same as always.
    if len(raw) == 8 and raw.isdigit():
        dd, mm, yyyy = int(raw[0:2]), int(raw[2:4]), int(raw[4:8])
        try:
            return date(yyyy, mm, dd)
        except ValueError:
            return None

    return None


# These document types are, by definition, only ever issued to Indian
# citizens/residents — so nationality can be correctly inferred from the
# document type alone. This matters because ml-service's real OCR pipeline
# currently only extracts fields from documents with an MRZ (Section 5.1A);
# none of these do, so their "nationality" OCR field is reliably empty —
# see src/pipeline.py's extract_ocr(), which never calls the field_ocr.py
# module that exists for exactly this case (a real, separately-disclosed
# gap, not something this inference works around silently: it only ever
# sets nationality, never fabricates a DOB, so evaluate_acceptance still
# correctly fails closed when DOB is genuinely unknown).
INDIA_ONLY_DOCUMENT_TYPES = {
    "voter_id", "aadhaar", "pan_card", "driving_license", "ration_card",
    "cghs_card", "emergency_certificate", "identity_certificate",
    "school_identity_certificate",
}


def infer_nationality(doc_type: str | None, ocr_nationality: str | None) -> str | None:
    if ocr_nationality:
        return ocr_nationality
    if doc_type and doc_type.strip().lower().replace(" ", "_") in INDIA_ONLY_DOCUMENT_TYPES:
        return "Indian"
    return None


def _age_at(dob: date, on: date | None = None) -> int:
    on = on or date.today()
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))


def evaluate_acceptance(nationality: str | None, doc_type: str | None, dob: date | None) -> dict:
    """Returns {"applies": bool, "accepted": bool, "reason": str | None, "age": int | None}.

    `applies=False` means this policy doesn't cover the case (non-Indian
    nationality, or doc_type/dob missing/unparseable) — the caller must
    treat that as "no opinion", never as an implicit pass or fail.
    """
    if not nationality or nationality.strip().lower() not in ("indian", "ind"):
        return {"applies": False, "accepted": True, "reason": None, "age": None}

    if not doc_type:
        return {"applies": False, "accepted": True, "reason": None, "age": None}

    doc_key = doc_type.strip().lower().replace(" ", "_")

    if dob is None:
        # Fail closed (Section 11 pattern used throughout this codebase):
        # without a DOB we cannot apply the age-based exception, so this
        # must not silently fall through to adult rules.
        return {
            "applies": True,
            "accepted": False,
            "age": None,
            "reason": "Date of birth could not be determined from the document — cannot verify document acceptance without it. Manual review required.",
        }

    age = _age_at(dob)

    if age < 15 or age > 65:
        accepted_set, bracket = AGE_EXEMPT_ACCEPTED, "under 15 or over 65 (age-exempt)"
    elif age < 18:
        accepted_set, bracket = MINOR_15_18_ACCEPTED, "15-18"
    else:
        accepted_set, bracket = STANDARD_ACCEPTED, "18-65 (standard adult)"

    if doc_key in accepted_set:
        return {"applies": True, "accepted": True, "reason": None, "age": age}

    if doc_key in EXPLICITLY_REJECTED_FOR_STANDARD_ADULT:
        return {
            "applies": True,
            "accepted": False,
            "age": age,
            "reason": (
                f"{doc_type.replace('_', ' ').title()} is not accepted as proof of Indian citizenship for this "
                f"crossing (per Embassy of India, Kathmandu) for travelers in the {bracket} bracket — a valid "
                f"Indian passport or original Voter ID card is required."
            ),
        }

    return {
        "applies": True,
        "accepted": False,
        "age": age,
        "reason": (
            f"'{doc_type}' is not a recognized accepted document type for Indian citizens at this crossing "
            f"(age bracket: {bracket})."
        ),
    }


# "Families traveling together: if one adult carries an approved document
# (passport/voter ID), other family members can travel with lesser proof of
# identity plus proof of the family relationship." The brief does not enumerate
# "lesser proof"; it is taken here as any recognised photo-ID from the age-
# exempt list plus PAN and a school identity certificate, i.e. an identity
# document that is real but not, on its own, accepted citizenship proof.
FAMILY_LESSER_PROOF = AGE_EXEMPT_ACCEPTED | {"pan_card", "school_identity_certificate"}

FAMILY_RELATIONSHIPS = {"spouse", "child", "parent", "sibling", "other_relative"}


def evaluate_family_provision(
    member_doc_type: str | None,
    relationship: str | None,
    relationship_proof_presented: bool,
    anchor_name: str | None,
    anchor_doc_type: str | None,
) -> dict:
    """Decides whether a member whose own document was NOT accepted may
    travel under the family provision. Returns {"accepted": bool, "reason": str}.

    Every condition of the provision is checked and named in the reason, so
    an officer can see exactly which one is unmet rather than just "no"."""
    anchor_key = (anchor_doc_type or "").strip().lower()
    anchor_ok = anchor_key in STANDARD_ACCEPTED
    doc_key = (member_doc_type or "").strip().lower().replace(" ", "_")
    lesser_ok = doc_key in FAMILY_LESSER_PROOF
    rel_ok = (relationship or "") in FAMILY_RELATIONSHIPS

    missing = []
    if not anchor_ok:
        missing.append("no adult in the group carries an approved document (passport / original Voter ID / embassy certificate)")
    if not lesser_ok:
        missing.append(f"'{member_doc_type}' is not a recognised identity document for the family provision")
    if not rel_ok:
        missing.append("no family relationship was declared")
    if not relationship_proof_presented:
        missing.append("proof of the family relationship was not presented")

    if missing:
        return {"accepted": False, "reason": "Family provision not met: " + "; ".join(missing) + "."}

    who = anchor_name or "the group's adult"
    return {
        "accepted": True,
        "reason": (
            f"Accepted under the family provision: {relationship.replace('_', ' ')} of {who}, "
            f"who carries an approved document ({anchor_key.replace('_', ' ')}), with proof of relationship presented."
        ),
    }
