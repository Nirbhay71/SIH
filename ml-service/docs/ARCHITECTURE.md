# Architecture

## Scope and non-goals

This service implements the ML core for SIH PS 26188's four mandated modules (OCR
extraction, document validation, tampering detection, face verification) plus the mandated
risk-scoring fusion layer. It does **not** implement a production dashboard UI, real
government database integration, or the blockchain/hash-chain audit trail — those are
separate, non-ML deliverables. See Section 2 of the build spec and `README.md`.

## Module boundaries and data flow

```
raw bytes
   │
   ▼
src/preprocessing/  (format normalize → boundary detect/crop → deskew → quality gate → region segmentation)
   │  PipelineResult(status="quality_rejected") exits here if blur/glare fails
   ▼
src/ocr/            (MRZ extraction OR free-text field OCR, per document type; normalization; confidence scoring)
   ▼
src/validation/     (checksum, format, logic, cross-zone checks — pure deterministic logic, no ML)
   ▼
src/tampering/      (photo, text, stamp, metadata signals + learned EfficientNet-B3 classifier)
   ▼
src/face/           (liveness → document-vs-live match → identity dedup, only if a live capture was provided)
   ▼
src/fusion/         (Tier 1 hard gates, checked first, always; Tier 2 XGBoost model + SHAP, only if no gate fired)
   ▼
PipelineResult → api/routes.py serializes to the Section 9A JSON contract
```

Every arrow above is a Pydantic-model boundary (`src/schemas.py`) — no raw dict crosses a
module boundary, so a schema drift between two modules fails at the type-checking/test
level rather than silently at runtime.

## Why two tiers in the fusion layer, not one

See Section 9.1 of the build spec for the full reasoning; in short: a hand-weighted linear
formula can't represent signal interactions and is easy to reverse-engineer; a pure trained
model could let several clean-looking signals statistically outvote one deterministic,
near-certain piece of evidence (a failed MRZ checksum), which must never be possible. Tier 1
(`src/fusion/hard_gates.py`) is a pure function with zero ML dependency, checked before Tier
2 can ever run — enforced by `src/pipeline.py`'s control flow and tested directly in
`tests/test_fusion.py`.

## Document-type classification (Section 5.1A)

Implemented as a lightweight heuristic, not a trained classifier, given this build's time
budget: check for an MRZ-like text pattern near the bottom of the page first (separates
MRZ-bearing types from OCI cards/permits), then use the MRZ document-code prefix to
distinguish passport from visa among MRZ-bearing types, then aspect ratio/keyword search for
non-MRZ types. A production system should replace this with a properly trained
document-classification model once labeled data across all target document types exists.
Its accuracy has not been separately measured in this build (see `docs/LIMITATIONS.md`).

## Region segmentation (Section 5.1 step 5)

No suitable pretrained ID-document region/layout detector was sourced and vetted within this
build's time budget. Implemented instead as the spec's own documented fallback: classical
contour/edge-density heuristics combined with ICAO 9303's known relative layout priors (MRZ
near the bottom, photo in the left portion for TD3-format documents). See
`src/preprocessing/region_segmentation.py`.

## Alternatives considered per module (Section 13C)

**OCR:** Tesseract alone was rejected as the sole engine — weaker on non-Latin scripts and
tightly-spaced MRZ text than PaddleOCR, and PassportEye already wraps a Tesseract build
specifically tuned for MRZ. LayoutLMv3/Donut were considered for structured field
extraction and deferred as a future upgrade path rather than the primary path, since they
need fine-tuning or careful zero-shot prompting that adds implementation risk relative to
field-zone-cropped OCR for an initial working system.

**Tampering classifier:** CAT-Net and TruFor are genuinely more capable at pixel-level
forgery localization than an EfficientNet-B3 classifier, but typically assume a PyTorch GPU
setup and heavier dependency management, raising implementation risk for a CPU-runnable
deliverable. Documented here as the correct upgrade path once compute/time allow — attempt
only after the EfficientNet-B3 path is fully working, evaluated, and recorded.

**Forgery classifier weights specifically:** no suitable pretrained SIDTD/MIDV-2020-derived
forgery-detection checkpoint was found and vetted on Hugging Face within this build's time
budget (see `config/model_paths.yaml`). Per the spec's own explicit fallback instruction,
`src/tampering/forgery_classifier.py` uses `timm`'s EfficientNet-B3 pretrained on ImageNet as
a backbone, with a binary head intended to be fine-tuned in `training/train_forgery_head.py`
(not yet run in this build — see `docs/LIMITATIONS.md`).

**Face verification:** DocFace/DocFace+ is measurably more accurate on the ID-document-to-
selfie matching task specifically than generic ArcFace with a recalibrated threshold, per
published research. Not chosen as the primary path because reproducing its training
procedure (dynamic weight imprinting, partially-shared sibling networks) has no guaranteed
pretrained public checkpoint and would require non-trivial reimplementation. ArcFace via
DeepFace with a recalibrated, domain-specific threshold (Section 8.3) captures a substantial
part of the same benefit with far less implementation risk. If a public DocFace+ checkpoint
becomes available, it is a viable upgrade.

**Fusion model:** LightGBM/CatBoost would likely perform comparably at this dataset scale.
XGBoost was chosen for its broader documentation and predictable behavior with the mixed
missing-value feature vector in Section 9.1, not an expected accuracy advantage. An MLP was
rejected outright — a dozen engineered features and a small labeled dataset is exactly the
regime where tree ensembles reliably outperform neural networks, while also providing
SHAP-based per-decision explainability the officer-facing output requires.

## Integration handoff notes for the non-ML system (Section 13F)

1. **The exact API contract in Section 9A (`POST /screen`) is the only interface a separate
   backend, dashboard, or audit-layer team should call.** Do not reach into `src/` directly
   from another service — the Pydantic schemas in `src/schemas.py` are this module's
   internal contract, not a public one.
2. **`RiskAssessment.gate_triggered`, when non-null, is the primary explanation** and should
   be shown to the officer as-is (e.g. "flagged due to MRZ checksum failure"). Use
   `top_contributing_factors` only when `gate_triggered` is null — a hard gate result has an
   empty `top_contributing_factors` list by design (the gate IS the explanation, per Section
   9.5).
3. **The mock watchlist (`src/fusion/hard_gates.py::check_watchlist_hit`, an in-memory
   `set[str]`) and any future mock document-status database are explicit placeholders.**
   Whoever builds the real integration should replace `check_watchlist_hit` specifically —
   it is the single, clearly-named function responsible for that lookup, not logic scattered
   inline elsewhere.
4. **Any change to `src/schemas.py` is a breaking change to this contract.** It must be
   versioned and communicated to downstream consumers, never made silently.

## Logging (Section 9B)

Each module logs through its own named logger (`src.ocr`, `src.validation`, `src.tampering`,
`src.face`, `src.fusion`, `api`) so verbosity can be tuned independently. `api/routes.py`
logs a request ID, document type, total latency, and final risk tier per request, and a
distinct warning-level line whenever a hard gate fires. No raw image bytes, extracted PII, or
face embeddings are ever logged — only structural/diagnostic values (confidence scores, flag
counts, timings).
