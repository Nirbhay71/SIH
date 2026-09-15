# Build Prompt: AI-Based Fake Identity & Document Screening System — ML Component Only

## Executive summary (read this first, then proceed to the full specification below)

You are building the machine-learning core of a border-document-screening system for Smart India Hackathon Problem Statement 26188. The system takes a photo or scan of a travel document (and optionally a live photo of the person presenting it) and outputs a structured risk assessment to help — never replace — a border security officer's decision. It must implement, as four clearly separable modules matching the problem statement's own structure: (1) OCR extraction of document fields, (2) rule-based validation of those fields against official document standards, (3) AI-based tampering detection covering photo replacement, text manipulation, stamp forgery, and metadata analysis, and (4) face verification between the document photo and the presented individual. All four modules' outputs converge into a two-tier risk-scoring layer: deterministic hard gates for near-certain evidence (a failed cryptographic-style checksum, a watchlist hit, a failed liveness check), and a trained, explainable machine-learning model (XGBoost with SHAP) for everything else. Every design decision in this document was made with three things in mind, in this priority order: (1) closing a specific, previously identified failure mode rather than looking sophisticated, (2) being honest about what is and is not validated, tested, or production-ready, and (3) being buildable by one person or a small team within a hackathon timeline using pretrained models wherever a pretrained model exists and reserving actual training effort for the one place it is genuinely needed — the final fusion layer. Keep this priority order in mind whenever this document leaves a judgment call to you.

## How to use this prompt

Paste this entire document into your agentic coding tool (Claude Code, Antigravity, Codex, etc.) as the initial instruction. It describes exactly one deliverable: the **machine learning component** of a border-document-screening system built for Smart India Hackathon Problem Statement ID 26188. Do not build a frontend, a full backend API framework, database persistence layer, blockchain audit trail, or officer dashboard UI unless explicitly instructed elsewhere — those are separate, non-ML deliverables outside this prompt's scope. Your job is to build a correct, well-tested, well-documented Python ML pipeline that can be imported and called by a backend service, with a thin FastAPI wrapper only for local testing/demo purposes.

Read this entire document before writing any code. Follow the module boundaries exactly as specified — do not merge modules, do not skip validation steps, and do not substitute a different model or library than the one specified without first proposing the change and stating the tradeoff. Where a design decision is called out as "non-negotiable," implement it exactly as described even if a simpler alternative seems tempting — these decisions were made deliberately after considering failure modes, and simplifying them re-introduces known problems.

---

## 1. Problem context (do not skip — this determines your success criteria)

This system is being built for Smart India Hackathon Problem Statement ID 26188, titled "AI-Based Fake Identity & Document Screening System," submitted under the Ministry of Home Affairs, Department: Sashastra Seema Bal (SSB), Police II Division, Category: Software, Theme: Blockchain & Cybersecurity.

### Background challenges the system must address
Border checkpoints face: fake passports and visas, altered photographs, modified dates of birth, tampered visa stamps, identity impersonation, multiple identities used by the same person, expired or blacklisted travel documents, and high passenger volume causing delays. Current verification relies heavily on human inspection and basic database lookups, which is slow and misses sophisticated forgeries.

### The four mandated modules (verbatim from the problem statement)
1. **Module 1: OCR Extraction** — automatically extract all relevant information from identity documents (passport, visa, national ID, driving license, permit documents).
2. **Module 2: Document Validation** — verify whether extracted information follows official document standards.
3. **Module 3: Tampering Detection** (explicitly labeled the "Core AI Innovation") — detect digitally or physically altered documents, covering: Photo Replacement, Text Manipulation, Stamp Forgery Detection, Image Metadata Analysis.
4. **Module 4: Face Verification** — ensure the document owner matches the presented individual.

### Mandated output
The system must generate a **risk score** to assist (not replace) border security personnel in making faster, more accurate decisions. This is not optional — it is stated directly in the problem statement.

### Expected impact (your evaluation should map back to these)
Reduce verification time from minutes to seconds; improve detection of forged/tampered documents; standardize screening decisions; enable data-driven risk assessment instead of purely manual inspection; create a digital trail for investigations (this last point is a downstream/non-ML concern, handled by a separate blockchain audit component — your ML output must simply be structured and loggable).

### Scope for Indian border documents specifically
This system screens documents at Indian border checkpoints. Relevant document types: Indian passport, foreign passports (any ICAO 9303-compliant country, since SSB checkpoints see international travelers), Indian visa (sticker or e-visa), OCI/PIO cards, and border permits (Inner Line Permit / Protected Area Permit / Restricted Area Permit), reflecting SSB's actual jurisdiction over Indo-Nepal and Indo-Bhutan border regions. Do not build document-type support for purely domestic ID cards (Aadhaar, PAN, Voter ID) — these are out of scope for a border-checkpoint use case; the PS's "national ID" field refers to documents presented at international border crossings (e.g., OCI cards, foreign national ID cards), not Indian domestic IDs.

### 1A. Glossary of terms used throughout this document

- **MRZ (Machine Readable Zone)**: the two (or three, on some older document types) lines of standardized OCR-B font text at the bottom of a passport or visa's data page, encoding key fields plus check digits, defined by the ICAO 9303 standard.
- **ICAO 9303**: the International Civil Aviation Organization standard defining the physical and machine-readable format of passports and travel documents worldwide, including the exact check-digit algorithm you must implement in Module 2.
- **Check digit**: a single digit mathematically derived from the other characters in a field, printed alongside the field, used to detect data-entry errors or alteration without needing an external lookup.
- **ELA (Error Level Analysis)**: a forensic technique that re-compresses an image and diffs it against the original to reveal regions with an inconsistent compression history, a common indicator of digital editing.
- **PAD (Presentation Attack Detection)**: the standard industry/academic term for detecting fraudulent or manipulated identity documents and biometric spoofing attempts — use this term in any generated documentation, since it is the recognized terminology in this field.
- **TAR / FAR (True Accept Rate / False Accept Rate)**: standard biometric system evaluation metrics, typically reported as a pair (e.g., "97% TAR at 0.1% FAR") since the tradeoff between them, not either number alone, characterizes real system behavior.
- **Hard gate**: a deterministic, non-probabilistic rule in the fusion layer that forces a risk classification regardless of what the trained model would otherwise output, reserved for near-certain facts (checksum failure, watchlist hit, failed liveness).
- **Reality Gap**: the documented phenomenon in current forgery-detection research where models perform well on benchmark/synthetic datasets but degrade meaningfully against real-world or previously unseen data — you must account for this by keeping every accuracy claim scoped explicitly to the dataset it was measured on.
- **OCI/PIO card**: Overseas Citizen of India / Person of Indian Origin card, a distinct document type (not a passport) commonly presented at Indian border checkpoints by diaspora travelers.
- **ILP/PAP/RAP**: Inner Line Permit, Protected Area Permit, Restricted Area Permit — India-specific border-region travel authorizations relevant to SSB's actual jurisdiction over the Indo-Nepal and Indo-Bhutan borders.

### 1B. Indian border document type reference (use this to build `config/document_formats.yaml`)

Build explicit support and format rules for the following, since these are the documents SSB checkpoints actually process, rather than a generic "any country's passport" assumption:

- **Indian passport**: ICAO 9303-compliant, two-line MRZ, `P<IND...` document-code prefix. Newer versions include an embedded RFID chip; your ML pipeline should not assume chip access is available and must work from the printed/visual document alone.
- **Foreign passports**: also ICAO 9303-compliant, but the document-code prefix and issuing-country code will vary; your MRZ parser must be country-agnostic and should not hardcode assumptions specific to Indian passports into the MRZ-reading logic itself (only document-specific *format validation*, in Module 2, should vary by country/type).
- **Indian visa**: either a physical sticker/stamp affixed inside a passport (in which case its MRZ, if present, is a distinct MRZ from the passport's own) or an e-Visa printout (a separate paper document, typically without an MRZ, requiring free-text field extraction instead).
- **OCI/PIO card**: no MRZ; free-text field extraction with its own field schema (holder name, date of birth, card number, issuing post).
- **Border permits (ILP/PAP/RAP)**: no MRZ, free-text extraction, and format rules that are explicitly regional/state-dependent rather than nationally uniform — build the config schema to support a per-region rule set rather than a single hardcoded pattern, and treat unmatched/unusual permit formats as lower-confidence rather than outright invalid, since standardization across issuing regions is genuinely inconsistent in the real world.

Do not build support for purely domestic Indian identity documents (Aadhaar, PAN, Voter ID, standard domestic driving licences used for in-country identification) — these are out of scope for a border-checkpoint screening use case and were a scope error identified and corrected earlier in this project's design process; the problem statement's "national ID" and "driving license" input types refer to documents a traveler might present at an international border crossing (e.g., a foreign national's home-country ID card or licence), not Indian domestic-only documents.

---

## 2. Explicit non-goals (do not build these)

- Do not build a production-grade officer dashboard UI. A minimal FastAPI test harness that accepts an image and returns JSON is sufficient for this deliverable.
- Do not implement real government database integration (Passport Seva, Interpol, lookout circulars). Build a mock watchlist using a local JSON file or SQLite table, clearly labeled as simulated in code comments and any generated documentation.
- Do not implement the blockchain/hash-chain audit trail. That is a separate component. Your ML pipeline's output JSON should simply be structured so a downstream service can log it; do not add blockchain logic yourself.
- Do not attempt real-time video processing or multi-frame liveness beyond what DeepFace's built-in anti-spoofing provides.
- Do not train any computer-vision model completely from scratch (i.e., random weight initialization on a CNN backbone). Use pretrained models throughout for CV tasks; the only model you train from scratch is the tabular fusion classifier in Module 3+4's combined risk layer, described in Section 8.
- Do not claim, in code comments, docstrings, or generated reports, that this system is validated for real-world deployment. Every accuracy claim must be qualified as "on synthetic test data" wherever it appears.

---

## 3. Technology stack (use exactly this; do not substitute without stating why)

- **Language:** Python 3.10+
- **Web framework (test harness only):** FastAPI + Uvicorn
- **OCR:** PassportEye (MRZ-bearing documents), PaddleOCR (free-text fields, multi-language `en`+`hi`)
- **Image processing:** OpenCV, Pillow, NumPy
- **Tampering detection classifier:** a pretrained EfficientNet-B3 forgery-detection model (search Hugging Face for a model fine-tuned on SIDTD/MIDV-2020-style ID document forgery data; if unavailable, use `timm`'s EfficientNet-B3 pretrained on ImageNet as a backbone and fine-tune the classification head yourself on the datasets in Section 7 — document which path you took)
- **Face detection/verification:** RetinaFace + ArcFace via the `deepface` library, including its built-in `anti_spoofing` liveness flag
- **Identity deduplication:** FAISS (`faiss-cpu`) for face-embedding similarity search
- **Fusion/risk model:** XGBoost (`xgboost` package)
- **Explainability:** SHAP (`shap` package)
- **Class imbalance handling:** `imbalanced-learn` (for SMOTE) as a fallback if `scale_pos_weight` alone is insufficient
- **Testing:** `pytest`
- **Dependency management:** a single `requirements.txt`, pinned to specific versions you verify work together
- **Containerization:** provide a `Dockerfile` for the ML service so it can be dropped into the larger system's `docker-compose.yml` without modification

Install note: use `pip install --break-system-packages` if working in an externally-managed Python environment. Do not use GPU-only dependencies without a documented CPU fallback path — this must run on a laptop without a dedicated GPU for demo purposes, even if slower.

### 3A. Development milestones (suggested build order and rough effort allocation)

Build in this order; each milestone should leave you with something runnable and testable, not a half-finished cross-cutting change:

1. **Milestone 1 — Skeleton and contracts**: create the full repository structure from Section 4, define every Pydantic schema in `src/schemas.py` up front (even before the logic that populates them exists), and get a trivial FastAPI endpoint returning a hardcoded response. This forces the module boundaries to be concrete before any model integration begins.
2. **Milestone 2 — Module 1 (OCR) end-to-end**: pre-processing, MRZ extraction, free-text extraction, normalization, confidence scoring. Verify against a handful of real sample images (specimen/synthetic only) before moving on.
3. **Milestone 3 — Module 2 (Validation)**: this has no external model dependency and should be fast to build once Module 1's output contract is stable; write the checksum unit tests immediately, since correctness here is fully verifiable by hand-computed test vectors.
4. **Milestone 4 — Module 3 (Tampering)**: build the hand-coded forensic checks first (no external model download needed, fast iteration), then integrate the pretrained forgery classifier, then calibrate its threshold against the dataset from Section 10.
5. **Milestone 5 — Module 4 (Face)**: integrate RetinaFace/ArcFace/liveness, then run the recalibration procedure in Section 8.3 before trusting any threshold.
6. **Milestone 6 — Fusion layer**: implement hard gates first (pure logic, no dependency on the trained model existing yet), then build the feature-extraction pipeline over your training dataset, then train and evaluate the XGBoost model, then wire in SHAP.
7. **Milestone 7 — Evaluation, documentation, and hardening**: run the full evaluation report, write `LIMITATIONS.md` and `THRESHOLD_JUSTIFICATIONS.md`, add the security checks from Section 11, finalize the Dockerfile and README.

Do not attempt to build the fusion layer's trained model before Modules 1-4 produce stable, well-defined output contracts — the feature vector in Section 9.1 depends directly on those contracts, and changing an upstream schema after training would silently invalidate the trained model's feature-order assumptions.

---

## 4. Repository structure (create exactly this layout)

```
ml-service/
├── Dockerfile
├── requirements.txt
├── README.md                          # setup, run, test instructions
├── config/
│   ├── document_formats.yaml          # regex/format rules per document type
│   ├── thresholds.yaml                # every calibrated threshold, with justification comments
│   └── model_paths.yaml               # paths/URLs to pretrained model weights
├── src/
│   ├── __init__.py
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── boundary_detection.py
│   │   ├── deskew.py
│   │   ├── quality_gate.py
│   │   └── region_segmentation.py
│   ├── ocr/
│   │   ├── __init__.py
│   │   ├── mrz_extractor.py
│   │   ├── field_ocr.py
│   │   └── field_normalization.py
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── mrz_checksum.py
│   │   ├── format_rules.py
│   │   └── logic_checks.py
│   ├── tampering/
│   │   ├── __init__.py
│   │   ├── ela.py
│   │   ├── font_spacing_forensics.py
│   │   ├── photo_boundary_check.py
│   │   ├── metadata_forensics.py
│   │   └── forgery_classifier.py
│   ├── face/
│   │   ├── __init__.py
│   │   ├── face_verification.py
│   │   ├── liveness.py
│   │   └── identity_dedup.py
│   ├── fusion/
│   │   ├── __init__.py
│   │   ├── hard_gates.py
│   │   ├── feature_builder.py
│   │   ├── risk_model.py
│   │   ├── train.py
│   │   └── explain.py
│   ├── pipeline.py                    # orchestrates all modules end-to-end
│   └── schemas.py                     # pydantic models for every input/output contract
├── training/
│   ├── prepare_dataset.py             # downloads/prepares MIDV-2020, SIDTD, FantasyID
│   ├── extract_features.py            # runs pipeline over dataset, builds feature table
│   ├── train_fusion_model.py
│   └── calibrate_thresholds.py        # threshold-search scripts for Modules 3 and 4
├── tests/
│   ├── test_preprocessing.py
│   ├── test_ocr.py
│   ├── test_validation.py
│   ├── test_tampering.py
│   ├── test_face.py
│   ├── test_fusion.py
│   └── fixtures/                      # small sample test images (synthetic/placeholder only)
├── evaluation/
│   ├── run_evaluation.py              # produces the metrics report described in Section 9
│   └── reports/                       # generated evaluation output lands here
├── api/
│   ├── main.py                        # FastAPI test harness
│   └── routes.py
└── docs/
    ├── ARCHITECTURE.md
    ├── LIMITATIONS.md                 # mandatory — see Section 12
    └── THRESHOLD_JUSTIFICATIONS.md
```

Every `.py` file must have a module-level docstring explaining its single responsibility. No file should exceed roughly 300 lines — if a module grows past that, split it.

### 4A. Configuration file examples (build these, expand as needed — do not hardcode these values in Python)

`config/document_formats.yaml` (illustrative starting shape — expand with real patterns per Section 1B):
```yaml
indian_passport:
  has_mrz: true
  document_number_pattern: "^[A-Z][0-9]{7}$"
  mrz_document_code_prefix: "P<IND"
indian_visa:
  has_mrz: true
  document_number_pattern: "^[A-Z0-9]{8,10}$"
oci_card:
  has_mrz: false
  fields: [name, dob, card_number, issuing_post]
  document_number_pattern: "^[A-Z0-9]{10,15}$"
foreign_passport:
  has_mrz: true
  document_number_pattern: null   # country-dependent; validate structurally via MRZ length/charset only
border_permit_ilp:
  has_mrz: false
  fields: [holder_name, permit_number, valid_from, valid_to, authorized_region]
  document_number_pattern: null   # region-dependent, see Section 1B
```

`config/thresholds.yaml` (illustrative starting shape — every value must be filled in with a justification comment after calibration, not left as a guess):
```yaml
preprocessing:
  blur_variance_min: 100.0        # justify against Section 5.1 step 4 calibration
  glare_pixel_fraction_max: 0.15
ocr:
  field_confidence_min: 0.85
tampering:
  ela_zscore_threshold: 2.0
  font_spacing_cv_max: 0.4
  baseline_deviation_px_max: 3.0
  height_zscore_max: 2.0
  forgery_classifier_threshold: 0.4   # biased toward recall, see Section 7.5
face:
  match_distance_threshold: null      # MUST be recalibrated per Section 8.3, do not ship the ArcFace default
  borderline_margin: 0.05
fusion:
  risk_tier_low_max: 30
  risk_tier_medium_max: 60
  risk_tier_high_max: 80
```

`config/model_paths.yaml`:
```yaml
forgery_classifier:
  source: "huggingface"
  repo_id: "REPLACE_WITH_ACTUAL_MODEL_REPO"
  expected_sha256: "REPLACE_AFTER_FIRST_DOWNLOAD"
fusion_model:
  path: "training/artifacts/xgboost_fusion_v1.json"
  feature_manifest_path: "training/artifacts/feature_manifest_v1.json"
```

Every threshold must trace back to a written justification in `docs/THRESHOLD_JUSTIFICATIONS.md` — a numeric value in this file with no corresponding explanation is treated as incomplete work.

### 3B. Coding conventions and style

- Use type hints on every function signature. Use Pydantic models (already specified per-module in Sections 5-9) for every data structure that crosses a module boundary — never pass raw dicts between modules, since this removes the type-checking benefit that catches schema drift early.
- Every public function must have a docstring stating: what it does, what it assumes about its input (e.g., "expects a pre-processed, quality-gated image"), and what it guarantees about its output.
- Prefer pure functions wherever the logic allows it (no hidden shared state, no mutation of input arguments) — this makes unit testing dramatically simpler, particularly for Module 2's validation logic and Module 9's hard-gate logic, both of which should be trivially testable with plain input/output assertions.
- Do not catch broad `except Exception` blocks that swallow errors silently. If a step can fail in an expected way (e.g., no MRZ found), that must be an explicit, typed outcome in your Pydantic response model (as already specified with fields like `mrz_extraction_method: "fallback_ocr"`), not a caught-and-ignored exception.
- Configuration values (thresholds, file paths, model identifiers) must never be hardcoded inline in module logic — always load from the YAML config files in Section 4A. This is what makes recalibration (Sections 7.5 and 8.3) something you do by editing a config file, not by hunting through source code.
- Write your orchestration layer (`src/pipeline.py`) as a straightforward, linear sequence of module calls with explicit early-exit points (e.g., after a quality rejection, or after a hard gate fires) — avoid deeply nested conditional branching here. The pipeline's job is orchestration and control flow, not analysis logic, which belongs inside each module.

Example shape for `src/pipeline.py` (illustrative structure, not literal final code):
```python
def run_pipeline(document_image: bytes, live_capture: bytes | None, document_type_hint: str | None) -> PipelineResult:
    preprocessed = preprocess(document_image)
    if preprocessed.status == "quality_rejected":
        return PipelineResult(status="quality_rejected", reason=preprocessed.reason, score=preprocessed.score)

    ocr_result = extract_ocr(preprocessed, document_type_hint)
    validation_result = validate_document(ocr_result)
    tampering_result = detect_tampering(preprocessed, ocr_result)
    face_result = verify_face(preprocessed, live_capture) if live_capture else FaceVerificationResult(face_match_status="not_computed", ...)
    identity_result = check_duplicate_identity(face_result, ocr_result)

    gate_result = evaluate_hard_gates(validation_result, face_result, identity_result)
    if gate_result.triggered:
        risk_assessment = RiskAssessment(risk_score=95, risk_tier="CRITICAL", gate_triggered=gate_result.reason, model_probability=None, top_contributing_factors=[])
    else:
        features = build_feature_vector(ocr_result, validation_result, tampering_result, face_result, identity_result)
        risk_assessment = run_fusion_model(features)

    return PipelineResult(status="ok", ocr_result=ocr_result, validation_result=validation_result,
                           tampering_result=tampering_result, face_result=face_result, risk_assessment=risk_assessment)
```

---

## 5. Module 1: OCR Extraction — full specification

### 5.1 Pre-processing (runs before any OCR call)

Implement, in order, as separate testable functions:

1. **Format normalization**: accept PDF, JPG, JPEG, PNG, HEIC, TIFF. Convert PDFs to images at minimum 300 DPI per page. Convert everything to PNG internally (lossless) — never re-save as JPEG at this stage, since JPEG re-compression at this point will corrupt Module 3's Error Level Analysis later. Keep a reference to the untouched original bytes for Module 3.

2. **Document boundary detection**: use Canny edge detection followed by contour extraction; select the largest plausible quadrilateral contour as the document boundary; crop to it. If no confident boundary is found (e.g., contour area below a sane fraction of total image area), do not crop — pass the full image through and set a flag `boundary_detection_failed: true` in the output so downstream code knows cropping didn't happen.

3. **Deskew**: compute the dominant text/edge angle (via `cv2.minAreaRect` on thresholded content, or Hough line transform as a fallback) and rotate to correct. Cap the correction angle — do not attempt to correct rotations beyond roughly 45 degrees, since that likely indicates a boundary-detection error rather than a genuinely rotated document; flag `deskew_skipped_large_angle: true` in that case instead of guessing.

4. **Quality gating**: compute a blur score using the variance of the Laplacian of the grayscale image, and a glare score as the percentage of pixels above a near-white saturation threshold within the document region. Define both thresholds in `config/thresholds.yaml` with a comment explaining how you derived them (test against a small deliberately blurry/glared sample set and pick a cutoff that separates usable from unusable images). If either check fails, the pipeline must stop here and return a structured rejection: `{"status": "quality_rejected", "reason": "blur"|"glare", "score": <float>}`. Do not proceed to OCR on a document that fails this gate — a low-quality read produces unreliable downstream conclusions across every subsequent module.

5. **Region segmentation**: detect and output bounding boxes for the photo region, the MRZ zone (if the document type has one), each text field zone, and any stamp/seal zones. Use a pretrained ID-document region detector if you can source one (search Hugging Face for an ID-card region/layout detection model); if none is suitable, implement a heuristic fallback using expected relative positions for known document layouts (e.g., ICAO 9303 defines MRZ position relative to the page bottom) combined with contour/text-block detection. Document which approach you used and why.

### 5.1A Document type classification

Before either extraction path (Section 5.2 or 5.3) runs, the pipeline needs to know which document type it is looking at, unless the caller has already supplied `document_type_hint` (Section 9A's API contract). Implement this as a lightweight decision procedure rather than a heavy dedicated deep-learning classifier for this deliverable: check for the presence and expected position of an MRZ-like text pattern (two lines of a roughly fixed character width, dominated by uppercase letters, digits, and `<` filler characters, positioned near the bottom of the document) to distinguish MRZ-bearing document types (passport, visa) from non-MRZ types (OCI card, permits) first; then, among MRZ-bearing types, use the MRZ's own document-code prefix (e.g., `P<` for passport) to distinguish passport from visa; among non-MRZ types, use a combination of aspect ratio, detected layout structure, and any distinctive header text (e.g., "OVERSEAS CITIZEN OF INDIA" or a specific permit title) matched via a simple keyword search on an initial low-cost OCR pass, before committing to full field-level extraction.

Document this heuristic approach explicitly as a design choice in `docs/ARCHITECTURE.md`, and note that a production system would likely replace this with a dedicated, properly trained document-classification model (an image classifier trained on labeled examples of each document type) once sufficient labeled data across all target document types is available — for this deliverable, the heuristic approach is a reasonable, low-risk starting point given time constraints, and its accuracy should still be measured and reported (what fraction of test documents were correctly classified by type) as part of your Module 1 evaluation, not simply assumed to work.

### 5.2 MRZ extraction (passport, visa)

Use PassportEye's `read_mrz` function on the MRZ region. Extract and return, at minimum: document type, full name, surname, given names, document/passport number, nationality, date of birth, sex/gender, expiry date, the two raw MRZ lines, all check digits present in the MRZ (document number check, DOB check, expiry check, composite check), and PassportEye's own internal `valid_score`.

If `read_mrz` returns `None` (no MRZ detected), do not silently fail — fall back to attempting free-text OCR on that region and mark `mrz_extraction_method: "fallback_ocr"` so downstream validation knows checksum validation cannot be performed with full confidence.

### 5.3 Free-text extraction (National ID equivalents, permits — non-MRZ documents)

Run PaddleOCR configured for both English and Hindi (`lang` parameter set to support both, or run two passes and merge, since PaddleOCR's multi-language support may require separate model instances per language depending on the version you install — verify this against the installed version's documentation and note your approach in `README.md`). Run OCR against each field-zone crop from Section 5.1 step 5 individually rather than the whole document at once — field-scoped OCR is measurably more accurate than whole-document OCR because it removes ambiguity about which text belongs to which field.

### 5.4 Field normalization (deterministic, no ML)

- **Dates**: attempt parsing against an ordered list of expected formats (`%d-%m-%Y`, `%d/%m/%Y`, `%d %b %Y`, `%d %B %Y`, `%y%m%d` for MRZ-style compact dates). If none match, set the field to `null` and add `"date_parse_failed"` to a `quality_flags` list rather than guessing or leaving malformed text in a field that downstream code expects to be a valid date.
- **Document/passport numbers**: strip whitespace, uppercase, then validate against the document-type-specific character-set pattern from `config/document_formats.yaml` (e.g., alphanumeric only, expected length). Do not silently correct ambiguous OCR characters (0/O, 1/I, 5/S) by guessing — if the raw OCR output doesn't match the expected pattern after basic cleanup, flag it, don't auto-correct it, since a wrong auto-correction here could mask real tampering or introduce a false checksum failure.
- **Names**: normalize whitespace and capitalization only; do not attempt spelling correction.

### 5.5 Confidence scoring

Every extracted field must carry the OCR engine's own confidence score. Compute and output both `ocr_confidence_avg` (mean across all fields) and `ocr_confidence_min` (minimum across all fields) — the minimum matters because a single badly-read critical field (e.g., date of birth) must not be masked by high confidence on easy fields (e.g., a printed header). Any field below `0.85` confidence (configurable in `thresholds.yaml`) is added to a `low_confidence_fields` list in the output. This list must be passed forward and consulted by Module 2 before any checksum failure is treated as evidence of tampering — this is a non-negotiable design rule described further in Section 6.

### 5.6 Module 1 output contract

```python
class OCRResult(BaseModel):
    status: Literal["ok", "quality_rejected"]
    document_type: str
    fields: dict[str, FieldExtraction]     # each field: {value, confidence, bbox}
    mrz_raw: list[str] | None
    mrz_check_digits: dict[str, str] | None
    ocr_confidence_avg: float
    ocr_confidence_min: float
    low_confidence_fields: list[str]
    quality_flags: list[str]
```

### 5.7 Edge cases you must explicitly handle and test

- Glare or blur specifically on the MRZ zone even when the rest of the document passes the general quality gate — test MRZ-region-specific quality independently of whole-document quality.
- Partial occlusion of the MRZ (finger, fold, physical damage) — `valid_score` from PassportEye should be low; verify your code correctly routes this to a "needs manual review" status rather than proceeding as if extraction succeeded.
- Bilingual documents where a field legitimately contains both Hindi and English text (e.g., permit documents) — verify PaddleOCR's multi-script handling does not silently drop one script's text.
- Old/legacy document formats predating current standards — build the format-rule config to be extensible per issue-year range rather than a single hardcoded rule per document type.
- Documents where the boundary-detection step incorrectly crops out part of the document — verify the `boundary_detection_failed` flag correctly triggers fallback behavior.

---

## 6. Module 2: Document Validation — full specification

This module contains **no machine learning models**. Every check here is deterministic logic. Do not introduce probabilistic scoring or a trained classifier into this module — checksum and format validation must remain 100% auditable, reproducible, and independent of any model's confidence.

### 6.1 MRZ checksum validation (implement exactly this algorithm)

The ICAO 9303 check-digit algorithm: convert each character to a numeric value (digits 0-9 as themselves, `<` as 0, letters A-Z as 10-35 respectively), multiply each position's value by a repeating weight pattern of 7, 3, 1 (cycling), sum the results, and take the result modulo 10. This produces the expected check digit, which must be compared against the actual printed check digit extracted in Module 1.

Apply this to: the passport/document number field, the date-of-birth field, the expiry-date field, and the final composite check digit (which covers a concatenation of multiple fields per the ICAO 9303 specification — implement the exact composite-field concatenation rule as defined in the standard, do not approximate it).

**Non-negotiable rule**: before reporting a checksum failure as `"fail"`, check whether the corresponding source field appears in Module 1's `low_confidence_fields` list. If it does, report the checksum status as `"inconclusive_low_confidence"` rather than `"fail"`. This distinction must be preserved all the way to the fusion layer in Section 8, because Tier 1's hard-gate logic treats `"fail"` (deterministic tampering evidence) very differently from `"inconclusive_low_confidence"` (an OCR problem, not proof of forgery). Getting this wrong — treating an OCR misread as a confirmed forgery — is a real, previously identified failure mode; do not reintroduce it.

### 6.2 Format and pattern validation

Load per-document-type regex/format rules from `config/document_formats.yaml`. At minimum, define rules for: Indian passport number format, Indian visa number format, OCI card number format, and a generic fallback pattern for permit documents (since these vary by issuing state/region and may not have one universal format — document this limitation explicitly rather than forcing an incorrect universal rule).

### 6.3 Logical consistency validation

Check: expiry date is chronologically after issue date (if issue date is available); date of birth implies a plausible age for the document type (flag, do not hard-reject, since edge cases like infant passports are legitimate); for visas, stay duration does not exceed the visa's own validity window; for permits, the validity window is internally consistent (start before end).

### 6.4 Cross-zone consistency validation

For MRZ-bearing documents, compare the MRZ-encoded values (name, DOB, document number) against the same data as OCR'd from the visually printed (non-MRZ) zone of the document. A mismatch here is a meaningful signal, since a forger who edits the visible printed data without correctly re-encoding the MRZ (or vice versa) produces exactly this kind of discrepancy. As with Section 6.1, weight this against OCR confidence on both sides before treating a mismatch as conclusive.

### 6.5 Module 2 output contract

```python
class ValidationResult(BaseModel):
    mrz_checksum_document_number: Literal["pass", "fail", "inconclusive_low_confidence", "not_applicable"]
    mrz_checksum_dob: Literal["pass", "fail", "inconclusive_low_confidence", "not_applicable"]
    mrz_checksum_expiry: Literal["pass", "fail", "inconclusive_low_confidence", "not_applicable"]
    mrz_checksum_composite: Literal["pass", "fail", "inconclusive_low_confidence", "not_applicable"]
    format_valid: bool
    format_violations: list[str]
    logic_consistent: bool
    logic_violations: list[str]
    cross_zone_match: bool | None      # null if document has no MRZ to cross-check against
```

### 6.5A Worked checksum example (use this exact worked-through case as a reference test vector)

Take the illustrative MRZ second line `P1234567<4IND0405121M3405125<<<<<<<<<<<<<<04`. The passport number field is `1234567<` (8 characters, including the filler `<` needed to pad to the fixed field width), followed by its check digit `4`. To verify: map each character to its numeric value (`1`→1, `2`→2, `3`→3, `4`→4, `5`→5, `6`→6, `7`→7, `<`→0), apply the repeating weight sequence 7, 3, 1, 7, 3, 1, 7, 3 to the 8 characters in order, multiply each character's value by its corresponding weight, sum all eight products, and take the sum modulo 10. If your implementation is correct, this computation must produce `4`, matching the printed check digit. Build this exact example (and its date-of-birth and expiry-date counterparts from the same illustrative MRZ line, plus at least two deliberately altered variants where you manually change one digit and confirm the checksum function correctly reports a mismatch) as literal test cases in `tests/test_validation.py` — do not rely only on abstract property-based tests for this function, since a single off-by-one in the weight cycle or a swapped character-to-value mapping would otherwise be easy to miss.

### 6.6 Testing requirement

Write unit tests with hand-verified checksum examples (compute the expected check digit by hand or with an independent reference implementation for at least 5 known-correct MRZ strings, and at least 3 deliberately corrupted ones) to confirm your implementation matches the ICAO 9303 specification exactly — an off-by-one error in the weight cycle or character-value mapping here would silently produce wrong results across the entire system.

---

## 7. Module 3: Tampering Detection — full specification (the "Core AI Innovation")

This module must visibly address all four named use cases from the problem statement. Structure your code so each use case maps to an identifiable, independently testable function — this matters for how the system will be evaluated, since judges/evaluators will look for each of these four by name.

### 7.1 Photo Replacement Detection

Combine three signals:
1. **Boundary artifact check**: apply a Laplacian edge filter specifically within and around the photo region's bounding box (from Module 1's region segmentation). A genuinely embossed/printed photo shows a smooth gradient transition into the surrounding document background; a digitally pasted photo typically shows a sharper, more discontinuous edge. Quantify this as a numeric anomaly score, not a binary flag.
2. **Lighting-direction consistency**: estimate the dominant gradient direction within the photo region versus the dominant gradient direction of the surrounding document background (via Sobel operators), and compute a directional mismatch score.
3. **Localized compression analysis**: run Error Level Analysis (Section 7.2) but specifically isolate its output to the photo bounding box, and compare the photo region's mean error level against the document's non-photo regions' mean error level.

Combine these three into a single `photo_tamper_score` (0-1, normalized), documenting your combination method (simple average is acceptable if you don't have labeled data yet to learn optimal weights; note this as a place calibration could improve results later).

### 7.2 Text Manipulation Detection

Implement Error Level Analysis (ELA): re-save the (untouched, uncompressed-since-capture) working image at a fixed JPEG quality (e.g., 90), compute the pixel-wise absolute difference against the original, and derive a per-region anomaly score using a sliding window (e.g., 32×32 pixels) comparing local mean error level against the global mean plus a standard-deviation-based threshold (flag regions where `local_mean > global_mean + 2 * global_std`).

Additionally, for each text field region identified in Module 1:
- **Character spacing/kerning uniformity**: segment characters via connected-component analysis on the thresholded field crop, measure inter-character gaps, compute the coefficient of variation (std/mean) of those gaps — flag if it exceeds a calibrated threshold (start around 0.4, then tune against your test data; genuine printed text typically stays below roughly 0.25).
- **Baseline alignment**: fit a line through the bottom edge of each character's bounding box within the field, measure each character's deviation from that fitted baseline, flag if any single character deviates beyond a calibrated pixel threshold (start around 3px, scaled appropriately to image resolution).
- **Font size uniformity**: compute a z-score for each character's bounding-box height relative to the field's mean and standard deviation; flag characters with |z| beyond a calibrated threshold (start around 2.0).
- **Edge sharpness/anti-aliasing consistency**: compute a Laplacian-based sharpness measure per character region and compare it against the field's own average — inconsistent sharpness across characters in the same field (some crisper, some blurrier than their neighbors) suggests digital overlay rather than uniform printing.
- **Ink/color consistency**: compute per-character RGB histograms and local noise variance; flag characters whose color/noise profile diverges meaningfully from the field's overall profile.

Combine all of these per-field sub-scores into a single `text_manipulation_score` per field, and an aggregate `text_manipulation_score_max` across all fields (the maximum, not the average, since one manipulated field should not be diluted by several genuine ones).

### 7.3 Stamp Forgery Detection

For each stamp/seal region identified in Module 1's region segmentation: perform template matching against a small reference library of known-genuine stamp geometries you assemble (synthetic/placeholder reference stamps are acceptable for this hackathon deliverable — document clearly that a production system would need an authorized reference library from issuing authorities). Check for: geometric distortion relative to the reference template, ink/color consistency within the stamp region, and duplicate-pattern detection (compare the stamp region's feature descriptor, e.g., via ORB or SIFT keypoints, against other stamps processed in the same session/dataset, to catch a forger reusing one scanned stamp image across multiple documents).

Use ORB (Oriented FAST and Rotated BRIEF) rather than SIFT as your primary keypoint descriptor unless licensing/version constraints in your OpenCV build make SIFT freely available — ORB is patent-unencumbered, faster, and sufficient for the relatively small, well-defined stamp regions you're matching against, whereas SIFT's additional robustness to scale/rotation is more valuable for general-purpose object matching than for a stamp that is already roughly axis-aligned and consistently sized within a cropped document region. Compute a match-quality score (e.g., the proportion of keypoint matches passing Lowe's ratio test, or a normalized Hamming distance for ORB's binary descriptors) rather than a raw keypoint count, since raw counts are not comparable across stamps of different sizes or texture density.

Because your reference stamp library is necessarily incomplete and synthetic for this deliverable, do not let `stamp_forgery_score` be a hard gate or a heavily weighted signal on its own — treat a missing or inconclusive stamp check (no stamp region detected, or no matching reference template available) as a `null`/missing-indicator feature in the fusion layer (Section 9.1), not as evidence of either genuineness or forgery.

### 7.3A Why four independent signals rather than one strong signal for tampering

Do not be tempted to skip the hand-coded forensic checks (7.1, 7.2, 7.3, 7.4) once the learned classifier (7.5) is working, even though the classifier alone may look sufficient on your validation data. Each of these signals has a documented, different failure mode, and running them independently is what makes the overall module robust rather than merely accurate on one benchmark:
- ELA fails silently on a forgery that was carefully re-compressed at a matching quality level, or that was never JPEG-compressed to begin with (e.g., a losslessly edited PNG).
- Font/spacing forensics fail on forgeries that don't touch text at all (a pure photo swap with no altered dates or names).
- The learned classifier, being trained on synthetic forgery generation techniques, may not generalize to a real forger's specific editing tools and workflow — this is the "Reality Gap" referenced throughout this document.
- Metadata analysis fails completely whenever metadata has been stripped, which is trivial for any forger who is even minimally aware of this check.

Because each signal's blind spot is different, a forgery that evades one is likely to still trigger at least one other — this is the entire justification for feeding all four into the fusion layer rather than picking "the best one" and discarding the rest.

### 7.4 Image Metadata Analysis

Extract EXIF metadata where present (not all images will have it, especially after certain uploads strip it — handle the absence gracefully, do not error). Check the `Software` field against a list of known editing tools (Photoshop, GIMP, Paint.NET, and similar); check for inconsistency between `DateTimeOriginal` and `DateTime` (a modification timestamp after the original capture timestamp is suspicious, though not conclusive on its own). Output a `metadata_flag_count` and the specific flags raised. This signal must be weighted lowest of all Module 3 signals in the downstream fusion layer (documented in Section 8), since metadata is trivially stripped or forged and its absence proves nothing about a document's authenticity.

### 7.5 Learned forgery classifier

Load a pretrained EfficientNet-B3-based binary classifier (genuine vs. forged) — search Hugging Face specifically for a model fine-tuned on SIDTD or MIDV-2020-derived identity document forgery data. Run inference on the full pre-processed document image (resized to the model's expected input dimensions), producing a `forgery_classifier_probability` (0-1). If the model architecture supports it (e.g., via Grad-CAM), also produce a heatmap indicating which spatial region most influenced the prediction, and store its coordinates for later visualization by the (separate, non-ML) dashboard component.

**Threshold calibration (mandatory, do not use an arbitrary default):** using your labeled test split (Section 9), run the classifier against known-genuine and known-forged examples, plot the resulting probability distributions separately for each class, and select an operating threshold. Bias this threshold toward **recall over precision** — in a border-security context, a missed forgery (false negative) is a categorically worse outcome than an unnecessary secondary inspection (false positive). Document the exact threshold chosen and the reasoning in `docs/THRESHOLD_JUSTIFICATIONS.md`.

### 7.6 Module 3 output contract

```python
class TamperingResult(BaseModel):
    photo_tamper_score: float
    text_manipulation_score_max: float
    text_manipulation_scores_by_field: dict[str, float]
    stamp_forgery_score: float | None      # null if no stamp regions detected
    metadata_flag_count: int
    metadata_flags: list[str]
    forgery_classifier_probability: float
    forgery_classifier_threshold_used: float
    heatmap_regions: list[BoundingBox] | None
```

### 7.7 Edge cases you must explicitly handle and test

- A genuine document with natural wear (creasing, sun-fading, minor physical damage) must not trigger the same score profile as a digitally edited document — validate that your hand-coded forensic checks (ELA, font/spacing) don't false-positive heavily on worn-but-genuine samples; this is a known weakness of naive ELA-only approaches, and is exactly why the learned classifier runs in parallel rather than as the sole signal.
- A high-quality forgery that specifically evades ELA (clean single-compression, no visible recompression artifact) must still be caught by at least one other signal (font/spacing or the learned classifier) — test this explicitly by constructing or sourcing a test case designed to be ELA-invisible.
- Low-resolution or heavily compressed phone-camera uploads should be caught by Module 1's quality gate before reaching this module at all; verify that quality-rejected images never reach Module 3.
- Face-swap-type forgeries are documented in current research as harder for compression-artifact-based methods to catch, since blending techniques suppress the copy-paste artifacts these methods rely on. Do not claim uniform accuracy across forgery types — report per-forgery-type performance separately in evaluation (Section 9) and be explicit that face-swap-style tampering is a harder case for this pipeline.

---

## 8. Module 4: Face Verification — full specification

### 8.1 Face detection

Use RetinaFace (via the `deepface` library's detector backend option, or the standalone `retina-face` package) to detect and crop the face region from both (a) the document's photo region (from Module 1's region segmentation) and (b) a separately provided live-capture image.

### 8.2 Liveness/anti-spoofing check

Run this **before** attempting any face match. Use DeepFace's `extract_faces` function with `anti_spoofing=True` on the live-capture image only (not the document photo, which is expected to be a static image by definition). If the liveness check fails (indicating a photo-of-a-photo, screen replay, or similar spoofing attempt), set `liveness_status: "failed"` and do not compute or trust a face-match score at all in that case — a failed liveness check should independently and immediately contribute to a high-risk classification in the fusion layer (Section 9), regardless of what a face-match score might otherwise show.

### 8.3 Face matching

Generate embeddings for both cropped faces using ArcFace (via `DeepFace.verify` with `model_name="ArcFace"`), and compute the cosine distance between them.

**Mandatory recalibration (do not use the library's default threshold as-is):** the commonly cited default ArcFace cosine-distance threshold (approximately 0.68) is derived from generic face-verification benchmarks, not document-photo-vs-live-selfie comparisons specifically. Published research on this exact problem (ID document photo to selfie matching) demonstrates that generic face matchers perform substantially worse on this specific pairing than on standard face-to-face verification, because document photos differ systematically from live captures in lighting, compression history, and capture angle. You must:
1. Assemble a set of matched pairs (same identity: a document-style photo and a separate live-style photo of the same synthetic identity — MIDV-2020's video clips are a good source, since they provide multiple frames of the same synthetic identity in different conditions) and mismatched pairs (different identities).
2. Compute the cosine distance for every pair.
3. Plot both distributions and select a threshold that best separates them for this specific pair type, rather than reusing the generic default.
4. Define a "borderline zone" (e.g., within a small margin of your chosen threshold) that is reported as `"needs_officer_review"` rather than a hard match/no-match — do not force a binary decision on genuinely ambiguous cases.

Document your recalibrated threshold and the data used to derive it in `docs/THRESHOLD_JUSTIFICATIONS.md`.

### 8.4 Age-gap tolerance

Since document photos may be years old, do not apply the same strict threshold you might use for same-day photo comparison. Allow a wider tolerance band, and if feasible, flag cases where the estimated age gap (you may use a simple face-based age estimation model, or simply note this as a manual-judgment factor for the officer) is large, so the officer dashboard can display this context rather than the system silently applying a blanket looser threshold with no visibility into why.

### 8.5 Module 4 output contract

```python
class FaceVerificationResult(BaseModel):
    liveness_status: Literal["passed", "failed", "not_applicable"]
    liveness_score: float | None
    face_match_distance: float | None
    face_match_status: Literal["match", "no_match", "needs_officer_review", "not_computed"]
    threshold_used: float
```

### 8.6 Identity deduplication (multiple-identity detection)

Maintain a FAISS index (flat index is sufficient at hackathon/demo scale; document that a production deployment would need a distributed, persistent vector store such as Milvus or Qdrant instead) storing face embeddings of every previously processed document, alongside the associated name/DOB metadata.

For each new document processed: query FAISS for nearest neighbors above a similarity threshold. If a close match is found under a **different** name/DOB combination than the current document, set `duplicate_identity_flag: true`. **Mandatory edge-case handling**: do not flag based on face similarity alone — require both a face-embedding match above threshold AND a differing name/DOB before flagging, since face-similarity-only matching produces false positives on close relatives (siblings, especially twins), which is a documented real-world failure mode for face-based deduplication systems.

### 8.6A Batch processing note

For evaluation runs over the datasets in Section 10 (hundreds of images), do not call `DeepFace.verify` or the RetinaFace detector in a naive per-image Python loop if the underlying library supports batched inference — check the installed version's API for a batch-capable method, since looping one image at a time will make your evaluation run take substantially longer for no accuracy benefit. This is a performance concern for your evaluation/training workflow, not a requirement for the live single-document inference path (which will only ever process one document at a time in practice, so batching there is unnecessary complexity).

### 8.7 Edge cases you must explicitly handle and test

- Photo-of-a-photo or screen-replay spoofing attempts — verify liveness correctly fails and that a failed liveness result overrides any downstream face-match computation.
- Significantly aged document photos (test with MIDV-2020 samples spanning different apparent ages if available, or synthetically age-adjust test images) — verify your recalibrated threshold and tolerance band behave sensibly rather than producing a hard rejection on every older document.
- Poor lighting or extreme angle on the live capture — verify a quality gate (similar in spirit to Module 1's) exists before trusting a match score computed from a degraded live image; a bad-quality live photo should not be silently treated as a confident "no match."
- Twins/close relatives producing high face-similarity — verify the dual-condition (face similarity AND differing identity metadata) correctly avoids a false duplicate-identity flag when the name/DOB actually differ for legitimate reasons (e.g., two siblings crossing separately) versus correctly flagging when they're suspiciously similar in additional ways.

---

## 9. Risk Fusion Layer — the mandated output, and the one place real training happens

This is not a fifth problem-statement module — it is the shared output the PS explicitly requires all four modules to feed into ("generates a risk score to assist border security personnel"). Implement it as a distinct, well-isolated piece of code (`src/fusion/`) since it is architecturally the most important part of the ML system and the part most likely to be scrutinized closely.

### 9.1 Two-tier architecture (non-negotiable — implement both tiers, do not use only one)

**Why two tiers, not a single trained model, and not a single hand-weighted formula:** A pure hand-weighted linear formula cannot represent interactions between signals (two simultaneous red flags should compound risk non-linearly, not just add), and is more easily reverse-engineered by an adversary who can reason about a known, static formula. A pure trained model, on the other hand, could in principle let a small set of clean-looking signals statistically "outvote" a single deterministic, near-certain piece of evidence (like a failed MRZ checksum), which should never be possible — a checksum failure is a mathematical fact, not a probabilistic opinion, and treating it as just one more weighted input creates a genuine security gap (a forger who can keep every other signal clean could dilute a checksum failure's influence on the final score). The two-tier design closes both failure modes: deterministic, near-certain facts bypass the model entirely as hard gates, while every genuinely probabilistic signal is fused by a model trained to learn real interactions from data.

**Tier 1 — deterministic hard gates.** Implement as a pure function, evaluated first, with no ML involved:
```python
def evaluate_hard_gates(validation_result, face_result, identity_result) -> HardGateResult:
    # If MRZ checksum genuinely failed (not "inconclusive_low_confidence") on ANY field,
    # OR a watchlist/blacklist hit is found,
    # OR liveness check failed,
    # -> force risk_tier = "CRITICAL", set gate_triggered to the specific reason,
    #    and skip/override the Tier 2 model score entirely.
    ...
```
The output must clearly indicate whether a hard gate fired and, if so, exactly which one — this must be surfaced in the final output so an officer can see "flagged due to MRZ checksum failure" rather than an opaque score.

**Tier 2 — trained XGBoost fusion model**, applied only when no hard gate fired, over the following feature vector:

```
ocr_confidence_avg, ocr_confidence_min,
format_valid (0/1), logic_consistent (0/1), cross_zone_match (0/1, or missing-indicator if null),
photo_tamper_score, text_manipulation_score_max, stamp_forgery_score (with missing-indicator),
metadata_flag_count, forgery_classifier_probability,
face_match_distance (with missing-indicator if not_computed),
liveness_score,
duplicate_identity_flag (0/1)
```

Use XGBoost's native missing-value handling or explicit missing-indicator features for any signal that may be legitimately absent (e.g., `stamp_forgery_score` when no stamp region was detected on that document type) — do not impute a fabricated numeric value that could be misread as a real measurement.

### 9.2 Training data pipeline

Build `training/prepare_dataset.py` to source and organize:
- **MIDV-2020** — genuine synthetic identity documents (passport-type and ID-card-type subsets specifically), providing your negative (genuine) class and also the matched/mismatched face pairs needed for Module 4's threshold calibration (via its video-clip frames).
- **SIDTD** — labeled synthetic forgeries (crop-and-replace and inpaint-and-rewrite types), providing your positive (forged) class with per-forgery-type labels preserved.
- **FantasyID** — face-swap-type forgeries, specifically included so your evaluation and training data are not blind to this documented harder case.

Build `training/extract_features.py` to run the full Module 1→2→3→4 pipeline over every image in this combined dataset and output one feature row per document, preserving the ground-truth label and the specific forgery type where applicable (needed for the per-forgery-type evaluation breakdown in Section 10).

**Class imbalance handling:** compute `scale_pos_weight` as the ratio of genuine to forged examples in your training split and pass it to XGBoost. If class separation remains poor after this alone, apply SMOTE via `imbalanced-learn` on the training split only (never on the test split, since oversampling the test set would invalidate your evaluation metrics).

### 9.3 Training configuration (`training/train_fusion_model.py`)

- Stratified train/test split (80/20), preserving the genuine/forged ratio and, if feasible, the forgery-type distribution across both splits.
- XGBoost hyperparameters: shallow trees (`max_depth` in the 3-5 range, to avoid overfitting a model with roughly a dozen input features on a comparatively small dataset), `n_estimators` in the 100-200 range, `learning_rate` in the 0.05-0.15 range — perform a small manual or grid search across these ranges, selecting based on cross-validated AUC on the training split (never select based on test-split performance, which would invalidate your final reported metrics).
- Persist the trained model, the exact feature-column order used, and the `scale_pos_weight`/SMOTE configuration together as one versioned artifact (e.g., a directory containing the model file plus a JSON manifest of these settings) — the inference code in `src/fusion/risk_model.py` must load and validate against this manifest, refusing to run if the live feature vector's shape or order doesn't match what the model was trained on.

### 9.4 Explainability (`src/fusion/explain.py`)

Use SHAP's `TreeExplainer` on the trained XGBoost model. For every prediction, compute SHAP values and output the top 3 contributing features with their signed contribution values, converted to human-readable labels (e.g., map `face_match_distance` to a display string like `"Face match distance"`). This output feeds the (separate, non-ML) officer dashboard's "why was this flagged" explanation — your responsibility is to produce this structured explanation data, not to render it visually.

### 9.5 Final combined output contract

```python
class RiskAssessment(BaseModel):
    risk_score: int                      # 0-100
    risk_tier: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    gate_triggered: str | None           # e.g. "mrz_checksum_failed", "watchlist_hit", "liveness_failed", or null
    model_probability: float | None      # raw Tier-2 model output, null if a gate fired
    top_contributing_factors: list[ContributingFactor]  # empty if a gate fired, since the gate IS the explanation
```

Map the model's raw probability (or a fixed high value when a gate fires) to the 0-100 scale and the four-tier bucketing using thresholds defined in `config/thresholds.yaml`, documented with the reasoning behind each cutoff.

### 9.6 Worked example (use this to sanity-check your implementation's behavior, not as literal production logic)

Consider a document where: MRZ checksum passes on all fields, format is valid, `photo_tamper_score = 0.15`, `text_manipulation_score_max = 0.72` (elevated — a font/spacing anomaly was detected on the date-of-birth field), `forgery_classifier_probability = 0.58` (above the calibrated 0.4 threshold from Section 7.5), `face_match_distance` corresponds to a confident match, `liveness_status = "passed"`, and no watchlist hit. No hard gate fires here (the checksum passed, there's no watchlist hit, liveness passed), so this flows into Tier 2. The elevated text-manipulation score and above-threshold forgery-classifier probability should combine, via the trained model's learned interaction, into a meaningfully elevated risk score — likely landing in the HIGH tier rather than LOW or MEDIUM — even though no single signal alone reached a "certain forgery" level. This is precisely the kind of case a hand-weighted linear formula might under-score (if neither individual weight alone crosses a hard-coded cutoff) but a trained model correctly recognizes as a meaningful joint pattern, since real training data would show that this specific combination (text anomaly + moderate forgery-classifier signal, both on the same document) co-occurs with actual forgeries in the labeled dataset far more often than either alone. Use examples like this one, constructed deliberately, as manual sanity checks on your trained model's behavior before trusting its evaluation metrics blindly.

### 9.7 Model versioning and retraining

Every trained fusion model artifact must be saved with a version identifier (e.g., a timestamp or incrementing integer) and its accompanying feature-order manifest, as stated in Section 9.3. Do not overwrite a previous model artifact in place — retraining produces a new versioned artifact, and the inference code should load a specific, explicitly configured version rather than "whatever is newest" by default, so that evaluation results remain reproducible and tied to a known model version. If you retrain after adding a new feature to the vector (for example, if a future iteration adds a new Module 3 sub-check), the feature manifest must change version too, and old evaluation reports should remain clearly labeled with the model version they were computed against — never silently mix metrics from two different model versions in one report.

---

## 9A. API contract for the FastAPI test harness

This section defines the exact request/response shape `api/main.py` must implement. This is the only interface a downstream backend service or a human tester interacts with — it must be stable and fully described here so it can be integrated without needing to read your internal module code.

### Endpoint: `POST /screen`

**Request** (multipart form data):
- `document_image`: required file upload (JPG/PNG/PDF/TIFF/HEIC)
- `live_capture_image`: optional file upload (JPG/PNG); if omitted, Module 4 outputs `face_match_status: "not_computed"` and the fusion layer treats face-related features as missing rather than as a failed match
- `document_type_hint`: optional string (e.g., `"indian_passport"`); if provided, skips Module 1's automatic document-type classification step and uses this directly — useful for testing and for cases where the officer already knows the document type

**Response** (JSON body), example for a genuine, clean document:
```json
{
  "status": "ok",
  "ocr_result": {
    "document_type": "indian_passport",
    "fields": {
      "name": {"value": "DARSHAN BUDDHDEV", "confidence": 0.98},
      "passport_number": {"value": "P1234567", "confidence": 0.97},
      "date_of_birth": {"value": "2004-05-12", "confidence": 0.96},
      "expiry_date": {"value": "2034-05-12", "confidence": 0.97}
    },
    "ocr_confidence_avg": 0.97,
    "ocr_confidence_min": 0.96,
    "low_confidence_fields": []
  },
  "validation_result": {
    "mrz_checksum_document_number": "pass",
    "mrz_checksum_dob": "pass",
    "mrz_checksum_expiry": "pass",
    "mrz_checksum_composite": "pass",
    "format_valid": true,
    "logic_consistent": true,
    "cross_zone_match": true
  },
  "tampering_result": {
    "photo_tamper_score": 0.08,
    "text_manipulation_score_max": 0.11,
    "stamp_forgery_score": null,
    "metadata_flag_count": 0,
    "forgery_classifier_probability": 0.09
  },
  "face_result": {
    "liveness_status": "passed",
    "face_match_distance": 0.22,
    "face_match_status": "match"
  },
  "risk_assessment": {
    "risk_score": 6,
    "risk_tier": "LOW",
    "gate_triggered": null,
    "top_contributing_factors": [
      {"feature": "forgery_classifier_probability", "contribution": -0.04},
      {"feature": "face_match_distance", "contribution": -0.03}
    ]
  }
}
```

**Response**, example for a document that trips a hard gate:
```json
{
  "status": "ok",
  "ocr_result": { "...": "..." },
  "validation_result": {
    "mrz_checksum_document_number": "fail",
    "mrz_checksum_dob": "pass",
    "mrz_checksum_expiry": "pass",
    "mrz_checksum_composite": "fail",
    "format_valid": true,
    "logic_consistent": true,
    "cross_zone_match": false
  },
  "tampering_result": { "...": "..." },
  "face_result": { "...": "..." },
  "risk_assessment": {
    "risk_score": 96,
    "risk_tier": "CRITICAL",
    "gate_triggered": "mrz_checksum_failed",
    "model_probability": null,
    "top_contributing_factors": []
  }
}
```

**Response**, example for a quality-rejected upload (pipeline stops at Module 1):
```json
{
  "status": "quality_rejected",
  "reason": "blur",
  "score": 42.7,
  "message": "Document image is too blurry for reliable analysis. Please re-scan or re-photograph in better lighting with a steady camera."
}
```

Every error path (quality rejection, no MRZ detected on an MRZ-expected document type, missing live-capture image when face verification was requested, malformed upload) must return a clear `status` field and human-readable `message` — never an unhandled exception or a bare 500 error with no explanation, since this endpoint is meant to be tested directly by non-ML engineers integrating the broader system.

## 9B. Logging and monitoring requirements

- Log, at minimum per request: a request ID, the document type processed, total pipeline latency, per-module latency breakdown (Module 1 time, Module 2 time, Module 3 time, Module 4 time, fusion time), and the final risk tier — this is what lets you later diagnose whether a specific module is a throughput bottleneck.
- Do not log raw image bytes, extracted PII field values, or face embeddings, per the security requirement in Section 11.
- Emit a distinct log line whenever a hard gate fires, including which gate, since these are the highest-stakes decisions the system makes and should be the easiest to audit after the fact.
- If you use Python's standard `logging` module, configure a dedicated logger per module (`src.ocr`, `src.validation`, `src.tampering`, `src.face`, `src.fusion`) so log verbosity can be tuned independently per module during debugging.

---

## 10. Accuracy, evaluation, and testing requirements

### 10.1 Metrics — report all of these, never accuracy alone

For the Tier 2 fusion model and for Module 3's forgery classifier independently: report Precision, Recall, F1-score, and AUC-ROC on the held-out test split. Explicitly report and justify **Recall as the headline metric** given the stated cost asymmetry (a missed forgery is worse than an unnecessary secondary inspection in a border-security context) — but still report the others, since Recall alone without context on Precision could hide an unacceptably high false-positive rate.

### 10.2 Per-forgery-type breakdown (mandatory, not optional)

Do not report a single blended accuracy number for Module 3. Break results down by forgery type as labeled in SIDTD (crop-and-replace, inpaint-and-rewrite) and FantasyID (face-swap) separately, since these forgery types are known in current research to have meaningfully different detection difficulty — reporting them separately is more honest and more useful than a single averaged figure that could hide a weak category.

### 10.3 Confusion matrix and error analysis

Produce a confusion matrix for the final fusion output on the test split. For every false negative (a forged document scored as low/medium risk), log which specific module's signal was weakest for that example — this is the diagnostic information needed to know which module to improve first.

### 10.4 Unit test coverage requirements

- `test_validation.py`: hand-verified checksum test vectors (at minimum 5 valid, 3 deliberately invalid), confirming exact ICAO 9303 algorithm correctness.
- `test_preprocessing.py`: quality-gate behavior on deliberately blurry/glared/well-formed sample images.
- `test_tampering.py`: verify each of the four sub-checks (photo, text, stamp, metadata) produces a higher score on a known-tampered sample than on a matched genuine sample.
- `test_face.py`: verify liveness correctly gates face-match computation; verify duplicate-identity flagging requires both conditions (face similarity AND differing metadata).
- `test_fusion.py`: verify hard gates correctly override the Tier-2 model output when triggered; verify the model refuses to run on a malformed/reordered feature vector.

### 10.5 Evaluation report (`evaluation/run_evaluation.py`)

This script must run the full pipeline over the held-out test split and produce a written report (Markdown or JSON, your choice, but human-readable) covering every metric in Sections 10.1-10.3, plus a clear statement of which dataset(s) were used, and the mandatory limitations disclosure from Section 12. This report is a deliverable, not just a debugging tool — it is what demonstrates the system's actual measured performance rather than an assumed one.

### 10.6 Cross-validation and hyperparameter search detail

For the Tier 2 fusion model's hyperparameter search (Section 9.3), use k-fold cross-validation (k=5 is a reasonable default given the likely dataset size) on the training split only, selecting the hyperparameter combination with the best mean cross-validated AUC. Do not use a single train/validation split for hyperparameter selection if your dataset is small enough that a single split would be noisy — cross-validation gives you a more stable estimate with limited data. Once hyperparameters are selected via cross-validation, retrain a final model on the full training split with those chosen hyperparameters, and only then evaluate once on the held-out test split for your final reported metrics. Never iterate on hyperparameters based on test-split performance — doing so silently turns your test split into a second validation split and invalidates the honesty of your final reported numbers, which is a mistake worth explicitly guarding against in code review of your own work.

### 10.7 Regression testing after any threshold or model change

Any time you recalibrate a threshold (Sections 7.5, 8.3) or retrain the fusion model (Section 9.3), re-run the full `evaluation/run_evaluation.py` script and compare the new report against the previous one before considering the change complete. A threshold change that improves Module 3's recall but silently tanks Module 4's face-match precision (for example, if a shared configuration value was accidentally changed) should be caught by this comparison, not discovered later. Keep every evaluation report you generate (timestamped, in `evaluation/reports/`) rather than overwriting the previous one, so this comparison is always possible.

---

## 11. Security requirements for the ML component specifically

Even though full infrastructure security (encryption at rest/in transit, RBAC, network segmentation) belongs to the broader system rather than the ML component alone, the ML code itself must implement the following:

- **Input validation before any model sees the data**: verify uploaded files are genuinely well-formed images/PDFs (correct magic bytes, parseable by the expected library) before passing them to any processing step — malformed or maliciously crafted files should be rejected with a clear error, never passed through to an image-processing library that might have its own parsing vulnerabilities.
- **No arbitrary file paths from user input**: any model-path or config-path loading must come from your own configuration files, never be constructable from request data, to prevent path-traversal issues.
- **Resource limits**: cap maximum accepted image dimensions and file size before processing, to prevent a maliciously oversized input from causing excessive memory/CPU consumption (a basic denial-of-service vector). Enforce this check as the very first step after receiving an upload, before any decoding or format-conversion work happens, since even the act of decoding an oversized or maliciously crafted image can itself be the expensive/exploitable operation you are trying to guard against — check the declared size and, where feasible, basic header dimensions before fully decoding the file into memory.
- **Rate limiting on the test-harness API**: even though this is a test harness rather than a production gateway, implement a basic per-source request rate limit (a simple in-memory or Redis-backed counter is sufficient for this deliverable) so that a misbehaving client or a naive load test cannot trivially overwhelm the service during a demo, and document in `README.md` that a production deployment would place a proper API gateway with more robust rate limiting and authentication in front of this service rather than relying on the ML service itself for these concerns.
- **Fail closed, not open, on any internal error**: if any module raises an unexpected error partway through the pipeline, the overall response must default to a cautious outcome (e.g., a clearly marked `"status": "processing_error"` response prompting manual review) rather than allowing a partially-completed risk assessment to be silently treated as a low-risk clearance. A pipeline that crashes on Module 3 must never allow the caller to interpret the resulting incomplete response as "no tampering detected."
- **Model artifact integrity**: when loading the trained XGBoost model (or any pretrained weights) at inference time, verify a checksum/hash of the model file against a known-good value stored in `config/model_paths.yaml`, and refuse to load if it doesn't match — this guards against a compromised deployment pipeline silently substituting a tampered model.
- **No sensitive data in logs**: ensure logging statements throughout the pipeline never write raw document images, extracted PII fields (name, DOB, document number), or face embeddings to plain-text logs. Log structural/diagnostic information (module timings, confidence scores, flag counts) instead.
- **Deterministic, reproducible inference**: given the same input image and the same model version, the pipeline must produce the same output every time — seed any source of randomness (e.g., if you use stochastic data augmentation anywhere, which should only ever occur during training, never during inference).

Document explicitly in `docs/LIMITATIONS.md` (Section 12) that full production security (encryption, RBAC, DPDP Act compliance, penetration testing, authorized real-database integration) is out of scope for this ML deliverable and belongs to the broader system's infrastructure layer.

### 11A. Dataset licensing and ethical use note

MIDV-2020, SIDTD, and FantasyID are research datasets built specifically to allow identity-document AI research without using real people's real documents — respect the license terms each dataset is published under (check and record each dataset's specific license in `README.md`), and do not attempt to supplement them with scraped real passport/ID images from the internet, social media, or any other uncontrolled source, since doing so would introduce real personal data into your training pipeline without consent or authorization, which is both an ethical problem and a real legal exposure regardless of hackathon context. If you use any publicly available Indian government specimen/sample document images (Section 1B) purely for layout/format validation, confirm they are official specimen images with no real person's data before using them for any purpose, including quick manual testing.

---

## 12. Mandatory limitations disclosure (`docs/LIMITATIONS.md`)

Write this file honestly and explicitly; do not soften or omit any of the following points, since an evaluator reading an inflated claim without this context is a worse outcome than the same evaluator reading an honest, well-reasoned limitations section:

1. This pipeline is trained and evaluated exclusively on synthetic datasets (MIDV-2020, SIDTD, FantasyID). It has not been validated against real border-checkpoint documents, and real-world accuracy is expected to differ from the reported synthetic-data metrics.
2. No adversarial robustness testing has been performed. A determined adversary specifically targeting this system's known detection methods may evade it in ways not represented in the training/test data.
3. Face-verification accuracy has not been evaluated for demographic subgroup disparities (age, gender, or other factors), which is a documented concern in face-recognition research generally. Production deployment would require explicit subgroup-level evaluation before trust in uniform accuracy across all travelers is warranted.
4. The stamp-forgery-detection reference library and the watchlist/blacklist database are both simulated/mocked for this deliverable, not connected to any real authorized data source.
5. This module has not been load-tested at the throughput described in the problem statement ("thousands of documents daily"). Latency and concurrency behavior at real checkpoint volume is unmeasured.
6. Human officer oversight is a required part of any real deployment; this system's risk score is designed to assist, never to autonomously accept or reject a traveler.

---

## 12A. Common pitfalls to avoid (each of these was identified as a real risk during this project's design process — do not reintroduce them)

- **Treating a checksum failure caused by an OCR misread as confirmed tampering.** This is why Section 6.1's `"inconclusive_low_confidence"` status exists as a distinct value from `"fail"` — collapsing these into one "failed" state anywhere in your code (including in the fusion feature vector) reintroduces a known false-positive source.
- **Using the ArcFace library's default face-match threshold unmodified.** This is documented in Section 8.3 as a mandatory recalibration, not an optional refinement — shipping the default threshold means your face verification is measurably worse than a document-photo-specific calibration would be.
- **Letting the fusion model's Tier 2 layer override a Tier 1 hard gate, or structuring the code so a gate can be silently skipped.** The hard-gate check must run and be evaluated before the Tier 2 model is ever invoked, with no code path that reaches Tier 2 without first checking Tier 1. Write a unit test specifically asserting this ordering cannot be bypassed.
- **Reporting a single blended accuracy number for Module 3 instead of a per-forgery-type breakdown.** A high average can hide a near-total failure on one forgery type (face-swap is the documented hardest case) — Section 10.2 requires the breakdown specifically to prevent this from going unnoticed.
- **Evaluating hyperparameters or thresholds against the test split rather than a validation split or cross-validation.** This silently inflates your reported metrics and would misrepresent the system's real performance; Section 10.6 explains the correct procedure.
- **Assuming face-similarity alone is sufficient for multiple-identity detection.** This produces false positives on twins/close relatives; Section 8.6 requires the dual condition (face match AND differing identity metadata) specifically to avoid this.
- **Weighting metadata analysis (Section 7.4) as heavily as the other three tampering sub-checks.** Metadata is the easiest signal for even an unsophisticated forger to defeat (simply strip EXIF data), and should never carry comparable weight to checksum validation, the learned forgery classifier, or face-match distance in the fusion feature vector.
- **Building document-format rules for Indian domestic IDs (Aadhaar, PAN, Voter ID) instead of border-relevant documents.** This was an actual scope correction made during this project's design — reread Section 1B before writing `config/document_formats.yaml` if there is any doubt about which document types are in scope.
- **Claiming or implying production readiness anywhere in generated documentation, code comments, or the evaluation report.** Every accuracy number must be explicitly scoped to "on synthetic test data," and `docs/LIMITATIONS.md` must be complete, not a placeholder — this is a deliverable, not an afterthought.
- **Re-compressing or re-saving the working document image before Module 3's ELA analysis runs.** Any lossy re-encoding between the original capture and the ELA computation destroys the exact signal ELA depends on; keep the pre-processed-but-uncompressed image reference intact through to Module 3.

## 12B. Environment variables and runtime configuration

Define the following as environment variables (with sane defaults in `config/*.yaml` for local development), rather than hardcoding them, so the containerized service can be configured per-deployment without a code change:

```
ML_SERVICE_PORT=8000
ML_SERVICE_LOG_LEVEL=INFO
MODEL_ARTIFACT_DIR=/app/training/artifacts
MAX_UPLOAD_SIZE_MB=15
MAX_IMAGE_DIMENSION_PX=6000
FAISS_INDEX_PATH=/app/data/identity_index.faiss
WATCHLIST_MOCK_DB_PATH=/app/data/mock_watchlist.json
```

Document every one of these in `README.md`, including what happens at each variable's default value versus what changing it affects — do not leave a reader guessing whether raising `MAX_IMAGE_DIMENSION_PX` has any accuracy implication versus a pure performance one (it does not affect accuracy, only memory/CPU use, and this should be stated explicitly).

---

## 13. Deliverables checklist (verify every item before considering this complete)

- [ ] All four modules implemented per their exact specifications in Sections 5-8
- [ ] Two-tier fusion layer implemented per Section 9, with hard gates correctly overriding the model
- [ ] Trained XGBoost model artifact, versioned with its feature-order manifest
- [ ] SHAP explainability wired into the final output
- [ ] Full evaluation report generated per Section 10, including per-forgery-type breakdown
- [ ] Every calibrated threshold documented with reasoning in `docs/THRESHOLD_JUSTIFICATIONS.md`
- [ ] `docs/LIMITATIONS.md` written per Section 12, in full, without omission
- [ ] Unit test suite passing, covering the cases listed in Section 10.4
- [ ] FastAPI test harness (`api/main.py`) allowing a document image (and optional live-capture image) to be submitted and the full JSON risk assessment returned
- [ ] `Dockerfile` builds successfully and the service runs inside the container
- [ ] `README.md` with exact setup, run, and test instructions, including how to reproduce training and evaluation
- [ ] A model card for both the fusion model and the tampering classifier (see Section 13G)

### 13A0. Required `README.md` contents (do not ship a placeholder README)

At minimum, the top-level `README.md` must contain, as clearly separated sections: (1) a one-paragraph description of what this service does and does not do, referencing the non-goals in Section 2; (2) exact local setup instructions (Python version, virtual environment creation, `pip install` command); (3) exact instructions to run the FastAPI test harness locally and a sample `curl` command demonstrating a request against the `/screen` endpoint from Section 9A; (4) exact instructions to run the test suite (`pytest` command, and how to interpret a passing/failing result); (5) exact instructions to reproduce dataset preparation, feature extraction, model training, and evaluation, in that order, referencing the scripts in `training/` and `evaluation/`; (6) a link to `docs/LIMITATIONS.md`, called out explicitly rather than buried, since this is the single most important file for anyone evaluating this system's real-world readiness; (7) the list of environment variables from Section 12B with their defaults and effects.

### 13G. Model cards (standard ML documentation practice — include these)

For both the fusion model and the forgery-detection classifier, produce a short model card (a Markdown file per model, e.g. `docs/model_cards/fusion_model.md` and `docs/model_cards/forgery_classifier.md`) recording: the model architecture and version, the exact dataset(s) and split used for training/evaluation, the headline metrics from Section 10.1 with their values, the per-forgery-type breakdown from Section 10.2 where applicable, the calibrated decision threshold and the reasoning behind it, known weaknesses (e.g., "reduced recall on face-swap-style forgeries, see Section 7.7"), and the intended scope of use (assisting a human officer's decision on synthetic-data-validated signal, not an autonomous accept/reject decision). This is standard practice for any deployed or evaluated ML model and gives any future reviewer — including a future session of the coding agent itself, or a different engineer entirely — a single place to understand a model's real, tested behavior without re-deriving it from source code.

### 13A. Per-module definition of done

Use this as a more granular checklist while working through each milestone from Section 3A — a module is not complete merely because it runs without error; it must satisfy every item below.

**Module 1 (OCR) is done when:**
- It correctly rejects a deliberately blurry and a deliberately glared test image via the quality gate, and correctly accepts a clean one.
- It correctly parses MRZ from at least one genuine Indian-passport-format sample and one non-Indian passport sample, without country-specific logic leaking into the MRZ-reading code itself.
- Every extracted field carries a confidence score, and fields below the configured threshold appear in `low_confidence_fields`.
- Date and document-number normalization correctly handles at least three different raw input formats each, and correctly returns `null` plus a flag for an unparseable value rather than guessing.

**Module 2 (Validation) is done when:**
- The checksum function passes all hand-verified test vectors from Section 6.6, both valid and deliberately corrupted.
- A checksum failure sourced from a field present in `low_confidence_fields` is reported as `"inconclusive_low_confidence"`, verified by a specific unit test constructing exactly this scenario.
- Format and logic validation correctly flag at least one deliberately invalid example per check type (bad format, illogical dates, mismatched cross-zone data).

**Module 3 (Tampering) is done when:**
- Each of the four named sub-checks (photo, text, stamp, metadata) independently produces a demonstrably higher score on a matched tampered/genuine pair of test images than a naive random baseline would.
- The forgery classifier's threshold is calibrated per Section 7.5's procedure, with the calibration data and resulting threshold documented in `docs/THRESHOLD_JUSTIFICATIONS.md`.
- A genuine-but-worn test document does not produce a false-positive tampering flag on the majority of sub-checks (verified against at least one such sample).

**Module 4 (Face) is done when:**
- Liveness correctly fails on a spoofing-style test input (e.g., a photo of a printed photo) and correctly passes on a genuine live-style test input.
- The face-match threshold has been recalibrated per Section 8.3's exact procedure, not left at the library default, with the calibration process and resulting value documented.
- Duplicate-identity detection requires both conditions (Section 8.6) and this is verified by a test where face similarity is high but identity metadata matches (should NOT flag) versus a test where both face similarity and differing metadata are present (SHOULD flag).

**Fusion layer is done when:**
- A unit test confirms that a hard-gate-triggering input (e.g., checksum `"fail"`, not `"inconclusive"`) always produces `risk_tier: "CRITICAL"` regardless of how clean every other input feature is.
- The trained XGBoost model's feature manifest is validated at load time, and a deliberately malformed/reordered feature vector is rejected with a clear error rather than silently producing a wrong prediction.
- SHAP explanations are produced for at least one Tier 2 prediction and manually verified to reference real, correctly-named features.
- The full evaluation report (Section 10.5) has been generated and reviewed, with per-forgery-type breakdown present and Recall reported as the headline metric.

### 13B. Anticipated review questions (prepare code and docs to answer these directly)

A technical reviewer or judge examining this ML component is likely to ask the following; make sure your code, comments, and `docs/` files can answer each without additional explanation from you:

1. "Why does a checksum failure sometimes not result in a high risk score?" — Answer should point to the `"inconclusive_low_confidence"` distinction in Section 6.1.
2. "How do you know your face-match threshold is appropriate, rather than an arbitrary number?" — Answer should point to the recalibration procedure and data in Section 8.3 and `docs/THRESHOLD_JUSTIFICATIONS.md`.
3. "What happens if someone feeds the system a real, sophisticated forgery your training data never saw?" — Answer should point directly to `docs/LIMITATIONS.md` and the Reality Gap discussion, without defensiveness — acknowledging this honestly is the correct answer, not a weakness to hide.
4. "Why XGBoost and not a neural network for the final risk score?" — Answer should reference Section 9's reasoning: a small number of engineered features, limited training data volume, and the need for SHAP-based per-decision explainability, all of which favor a tree-based ensemble over a neural network at this scale.
5. "Could a forger game this system by keeping every individual signal just below its threshold?" — Answer should reference Section 9.1's explanation of why the two-tier architecture (hard gates plus a learned, non-linear fusion model) specifically resists this compared to a hand-weighted linear formula.
6. "Is this validated on real border documents?" — The honest answer is no, and `docs/LIMITATIONS.md` must say so plainly; do not let any other part of the codebase or documentation imply otherwise.

## 13C. Alternatives considered per module (record these in `docs/ARCHITECTURE.md`, adapted to whatever you actually end up choosing if you deviate from Section 3's stack)

Documenting why an alternative was not chosen is as valuable to a reviewer as documenting what you did choose — include a short version of the following reasoning in `docs/ARCHITECTURE.md`, updated to reflect any deviations you make during implementation.

**OCR (Module 1):** Tesseract alone was considered and rejected as the sole OCR engine because its out-of-the-box accuracy on non-Latin scripts and on tightly-spaced MRZ text is weaker than PaddleOCR's, and PassportEye already wraps Tesseract specifically tuned for MRZ, giving the best of both by using each tool where it is strongest. LayoutLMv3/Donut were considered for structured field extraction but deferred to an optional upgrade path (Section 5, end of subsection 5.3) rather than the primary path, since they require either fine-tuning on your specific document layouts or careful zero-shot prompting, both of which add implementation risk relative to the simpler field-zone-cropped-OCR approach for an initial working system.

**Tampering classifier (Module 3):** CAT-Net and TruFor were considered as the primary learned tampering-detection model instead of EfficientNet-B3, and are genuinely more capable at pixel-level forgery localization specifically. They were not chosen as the primary path because they typically assume a PyTorch GPU inference setup and heavier dependency management, which raises implementation risk for a CPU-runnable deliverable; they are documented here as the correct upgrade path if compute resources and implementation time allow, and should be attempted only after the EfficientNet-B3 path is fully working end-to-end, evaluated, and its results recorded, so you always have a working fallback.

**Face verification (Module 4):** DocFace/DocFace+'s domain-specific transfer-learning architecture is, per the published research cited throughout this document, measurably more accurate on the ID-document-to-selfie matching task specifically than a generic ArcFace embedding with a recalibrated threshold. DocFace+ was not chosen as the primary path because reproducing its training procedure (dynamic weight imprinting, partially-shared sibling networks) from the paper requires a non-trivial reimplementation effort with no guaranteed pretrained public checkpoint readily available, whereas ArcFace via DeepFace with a properly recalibrated, domain-specific threshold (Section 8.3) captures a substantial part of the same benefit with far less implementation risk. If a public DocFace+ checkpoint or equivalent becomes available during implementation, document it as a viable upgrade.

**Fusion model:** LightGBM and CatBoost were considered as alternatives to XGBoost, and either would likely perform comparably at this dataset scale — the choice of XGBoost over these alternatives is not based on an expected accuracy advantage, but on XGBoost's slightly broader documentation and more predictable behavior with the mixed missing-value feature vector described in Section 9.1. A small neural network (MLP) was considered and rejected outright for the fusion layer, since a dozen or so engineered features and a comparatively small labeled dataset is exactly the regime where tree-based ensembles reliably outperform neural networks, while also providing the SHAP-based explainability the officer-facing output requires.

## 13D. Test fixture creation guidance

Since real border documents cannot be used for testing (Section 11A), `tests/fixtures/` must contain your own constructed test images. Build these deliberately rather than grabbing arbitrary images from the training datasets, so your unit tests remain fast, small, and independent of the larger dataset download:

- At least one clean, well-formed synthetic document image per document type in Section 1B (can be built from a blank template layout with placeholder text — no real person's data), used as your "genuine" baseline fixture for each module's happy-path tests.
- At least one deliberately blurry and one deliberately glare-affected variant of the same image, for Module 1's quality-gate tests.
- At least one variant with a manually altered date-of-birth field (edited in an image editor, with a mismatched checksum) and one with a manually altered check digit alone (data unchanged, only the printed check digit wrong), to distinguish "text was edited" detection (Module 3) from "checksum doesn't match" detection (Module 2) as separate, independently testable scenarios.
- At least one variant with a swapped/replaced photo region, for Module 3's photo-tampering tests.
- At least one pair of matched (same synthetic identity) and mismatched (different identity) face images, for Module 4's face-matching tests, plus one spoofing-style image (a photo of a printed photo, or a photo displayed on a screen) for liveness testing.

Keep these fixtures small in file size and check them into the repository directly (unlike the full training datasets, which should be downloaded via the `training/prepare_dataset.py` script rather than committed) — fixtures need to be available immediately when `pytest` runs, without requiring a dataset download step first.

---

## 13E. Full threshold/parameter summary (cross-reference while implementing; the authoritative values still live in the YAML configs from Section 4A)

| Parameter | Location | Starting point | Must be recalibrated against real test data before trusting |
|---|---|---|---|
| Blur variance minimum | `config/thresholds.yaml` → `preprocessing.blur_variance_min` | 100.0 (illustrative) | Yes — Section 5.1 step 4 |
| Glare pixel fraction maximum | `preprocessing.glare_pixel_fraction_max` | 0.15 (illustrative) | Yes — Section 5.1 step 4 |
| OCR field confidence minimum | `ocr.field_confidence_min` | 0.85 | Recommended, not mandatory |
| ELA z-score threshold | `tampering.ela_zscore_threshold` | 2.0 | Yes — Section 7.2 |
| Font spacing coefficient-of-variation max | `tampering.font_spacing_cv_max` | 0.4 | Yes — Section 7.2 |
| Baseline deviation max (px) | `tampering.baseline_deviation_px_max` | 3.0 | Yes — Section 7.2, scale to image resolution |
| Character height z-score max | `tampering.height_zscore_max` | 2.0 | Yes — Section 7.2 |
| Forgery classifier decision threshold | `tampering.forgery_classifier_threshold` | 0.4 (recall-biased) | Yes, mandatory — Section 7.5 |
| Face match distance threshold | `face.match_distance_threshold` | none (must not ship default) | Yes, mandatory — Section 8.3 |
| Face match borderline margin | `face.borderline_margin` | 0.05 (illustrative) | Yes — Section 8.3 |
| Risk tier cutoffs (Low/Medium/High) | `fusion.risk_tier_*_max` | 30 / 60 / 80 | Recommended, tune against evaluation results |

Every "Yes" in the rightmost column means: do not ship the illustrative starting value as final without running the calibration procedure referenced and recording the result in `docs/THRESHOLD_JUSTIFICATIONS.md`. A value left at its illustrative default with no calibration record is incomplete work, not a simplification.

## 13F. Integration handoff notes (for whoever builds the non-ML parts of the system)

Although this prompt covers the ML component only, write `docs/ARCHITECTURE.md` so that a separate team or a separate agent session building the backend, dashboard, or blockchain audit layer can integrate against your work without needing to read your internal module code. At minimum, state clearly: (1) the exact API contract from Section 9A is the only interface they should call; (2) the `RiskAssessment` object's `gate_triggered` field, when non-null, should be treated by any downstream UI as the primary explanation, with `top_contributing_factors` used only when `gate_triggered` is null; (3) the mock watchlist and mock document-status database are placeholders they will need to replace with real, authorized integrations before any real deployment, and your code should make this replacement point obvious (a single, clearly-named function or class responsible for the lookup, not scattered inline logic); (4) any change to the Pydantic schemas in `src/schemas.py` is a breaking change to this contract and should be versioned and communicated, not made silently.

## 14. Final instructions to the coding agent

Work through this specification module by module, in the order presented (Section 5 → 6 → 7 → 8 → 9), since later modules depend on earlier modules' output contracts. Write tests alongside each module, not after everything is built. If you find a genuine ambiguity or a case this specification doesn't address, make the most reasonable, security-conscious, recall-favoring decision consistent with the reasoning shown throughout this document, document the decision and your reasoning in code comments, and continue — do not stop and wait for clarification on minor implementation details, but do flag major architectural ambiguities explicitly in your final summary.

As you complete each milestone from Section 3A, produce a short progress note (a few sentences is sufficient) stating what was built, what was tested, what was deliberately deferred or simplified and why, and which configuration values still need real calibration data before they can be trusted. This is not extra bureaucracy — it is what allows anyone picking up this work later (including a future session of yourself) to know exactly how much of this specification has been faithfully implemented versus approximated under time pressure, which matters enormously for a system whose entire premise is that its accuracy claims should be trustworthy and honestly scoped.

Above all, do not weaken any of the sections marked "non-negotiable" for the sake of a simpler implementation; those decisions exist specifically to close known failure modes described earlier in this document. When in doubt about whether a shortcut is acceptable, ask whether it would survive being explained, in plain language, to the SSB evaluator reading `docs/LIMITATIONS.md` — if the honest answer is that the shortcut would need to be hidden or glossed over to pass that scrutiny, it is not an acceptable shortcut, and the correct action is to implement it properly or document it as an explicit, named limitation rather than a silent simplification.
