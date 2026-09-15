"""Runs Module 1->2->3->4 over the prepared dataset and writes one feature
row per document (Section 9.2), preserving the ground-truth label and
forgery type where applicable (needed for Section 10.2's per-forgery-type
breakdown).

HONEST STATUS: with only MIDV-2020 (genuine) and the synthetic placeholder
forged set available in this environment (see prepare_dataset.py), the
"forgery_type" column here is limited to {"none", "synthetic_placeholder"}
— it does NOT include SIDTD's crop-and-replace/inpaint-and-rewrite labels
or FantasyID's face-swap label, since neither dataset could be obtained
automatically. Re-run this script after manually placing SIDTD/FantasyID
data (see prepare_dataset.py's manual-instructions functions) to get a
real per-forgery-type breakdown.
"""
import csv
import logging
from pathlib import Path

from src.fusion.feature_builder import FEATURE_ORDER, build_feature_vector
from src.pipeline import extract_ocr, preprocess, validate_document
from src.schemas import FaceVerificationResult, IdentityDedupResult
from src.tampering.detect import run_tampering_detection
from training.prepare_dataset import MIDV2020_DIR, SYNTHETIC_FORGED_DIR

logger = logging.getLogger("training.extract_features")

OUTPUT_CSV = Path(__file__).resolve().parent / "artifacts" / "feature_table.csv"


def _extract_one(image_path: Path) -> dict | None:
    raw_bytes = image_path.read_bytes()
    preprocessed = preprocess(raw_bytes, image_path.name)
    if preprocessed["status"] != "ok":
        logger.warning("Skipping %s: quality-rejected during preprocessing (%s)", image_path, preprocessed.get("reason"))
        return None

    ocr_result = extract_ocr(preprocessed, document_type_hint=None)
    validation_result = validate_document(ocr_result)

    image = preprocessed["image"]
    field_crops = {
        f"field_{i}": image[b.y : b.y + b.height, b.x : b.x + b.width]
        for i, b in enumerate(preprocessed["field_boxes"][:10])
    }
    tampering_result = run_tampering_detection(
        image=image,
        original_bytes=raw_bytes,
        photo_box=preprocessed["photo_box"],
        field_crops=field_crops,
        stamp_crops=[],
        reference_stamps=[],
    )

    face_result = FaceVerificationResult(face_match_status="not_computed")
    identity_result = IdentityDedupResult()

    return build_feature_vector(ocr_result, validation_result, tampering_result, face_result, identity_result)


def build_feature_table() -> Path:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    genuine_images = list((MIDV2020_DIR / "scan_upright").rglob("*.jpg")) if (MIDV2020_DIR / "scan_upright").exists() else []
    forged_images = list(SYNTHETIC_FORGED_DIR.glob("*.png")) if SYNTHETIC_FORGED_DIR.exists() else []

    for path in genuine_images:
        features = _extract_one(path)
        if features is None:
            continue
        rows.append({**features, "label": 0, "forgery_type": "none", "source_path": str(path)})

    for path in forged_images:
        features = _extract_one(path)
        if features is None:
            continue
        rows.append({**features, "label": 1, "forgery_type": "synthetic_placeholder", "source_path": str(path)})

    if not rows:
        raise RuntimeError(
            "No images available to extract features from. Run training/prepare_dataset.py first, "
            "and see docs/LIMITATIONS.md for why SIDTD/FantasyID may still be missing."
        )

    fieldnames = FEATURE_ORDER + ["label", "forgery_type", "source_path"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Wrote %d feature rows to %s (%d genuine, %d forged)", len(rows), OUTPUT_CSV, len(genuine_images), len(forged_images))
    return OUTPUT_CSV


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_feature_table()
