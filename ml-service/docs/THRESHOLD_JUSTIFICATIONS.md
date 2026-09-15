# Threshold Justifications

Every threshold in `config/thresholds.yaml` is listed here with its status. Per Section
13E of the build spec, a value marked "Yes" for recalibration and left at its illustrative
default with no calibration record is incomplete work, not an acceptable simplification —
so this document says exactly that, plainly, wherever it applies, rather than glossing over
it.

| Parameter | Value shipped | Status |
|---|---|---|
| `preprocessing.blur_variance_min` | 100.0 | **ILLUSTRATIVE, not calibrated.** Chosen as a round number in the range typically cited for Laplacian-variance blur detection on document-scale images; `tests/test_preprocessing.py` confirms it separates a hand-constructed sharp image from a Gaussian-blurred (σ=15) copy of the same image, which is the only validation performed. |
| `preprocessing.glare_pixel_fraction_max` | 0.15 | **ILLUSTRATIVE, not calibrated.** Same status as above — validated only against a constructed test fixture, not a real sample sweep. |
| `ocr.field_confidence_min` | 0.85 | Matches the spec's own recommended (not mandatory) starting value; not recalibrated, but the spec does not require this one to be. |
| `tampering.ela_zscore_threshold` | 2.0 | **ILLUSTRATIVE, not calibrated.** Requires a labeled genuine/forged set at real ELA-relevant scale (JPEG-compressed originals) to calibrate properly; only MIDV-2020 (genuine) plus this build's own synthetic placeholder forgeries were available (see LIMITATIONS.md), which are not a faithful stand-in for real re-compression forensics since the synthetic forgeries were never JPEG-recompressed. |
| `tampering.font_spacing_cv_max` | 0.4 | **ILLUSTRATIVE, not calibrated.** Spec's own suggested starting point; not tuned against real data for the same reason as above. |
| `tampering.baseline_deviation_px_max` | 3.0 | **ILLUSTRATIVE, not calibrated.** Spec's own suggested starting point, scaled to a 300 DPI reference. |
| `tampering.height_zscore_max` | 2.0 | **ILLUSTRATIVE, not calibrated.** Spec's own suggested starting point. |
| `tampering.forgery_classifier_threshold` | 0.4 | **Mandatory recalibration not completed.** `training/calibrate_thresholds.py::calibrate_forgery_classifier_threshold` implements the required recall-biased sweep procedure (Section 7.5) and was written and is ready to run, but could not be executed in this build: it requires both (a) XGBoost/the forgery classifier's dependencies (torch/timm) installed, and (b) `training/extract_features.py` to have produced a feature table — neither completed in this build's environment (see LIMITATIONS.md's dependency-install note). The value shipped is the spec's own suggested recall-biased starting point, explicitly not a calibrated value. |
| `face.match_distance_threshold` | 0.58 | **Mandatory recalibration not completed.** `training/calibrate_thresholds.py::calibrate_face_match_threshold` implements the required Youden's-J sweep over matched/mismatched cosine-distance distributions (Section 8.3), but no real matched/mismatched document-photo-vs-live-selfie pairs were available to run it against (would need MIDV-2020 video-clip frames plus DeepFace/ArcFace installed, neither available in this build's environment — see LIMITATIONS.md). The value shipped is a placeholder chosen to sit below the commonly-cited generic ArcFace default (~0.68), reflecting the spec's stated expectation that the document-photo-vs-selfie task is harder than generic face-to-face verification and needs a tighter (lower) distance threshold — but this is a reasoned placeholder, not a calibrated value, and must not be presented as one. |
| `face.borderline_margin` | 0.05 | ILLUSTRATIVE, per spec's own suggested value. |
| `face.liveness_score_min` | 0.5 | ILLUSTRATIVE — DeepFace's anti-spoofing model was not installed in this build (see LIMITATIONS.md), so this has not been exercised against any real spoofing attempt. |
| `fusion.risk_tier_low_max` / `_medium_max` / `_high_max` | 30 / 60 / 80 | Match the spec's own suggested starting cutoffs (Section 4A); the spec marks these "recommended, tune against evaluation results" rather than mandatory — no evaluation report exists yet to tune against (see LIMITATIONS.md), so they remain at the suggested defaults. |
| `security.max_upload_size_mb` | 15 | Matches Section 12B's documented default. Purely a resource-limit control; changing it has no accuracy implication, only memory/CPU exposure. |
| `security.max_image_dimension_px` | 6000 | Matches Section 12B's documented default. Same as above — performance/memory only, no accuracy implication. |

## What would need to happen to complete calibration

1. Successfully install `xgboost`, `torch`, `timm`, `deepface`, `retina-face`, `tf-keras`,
   `paddlepaddle`, `paddleocr`, `faiss-cpu` (all specified in `requirements.txt`, all pinned
   to versions verified to resolve together, but not installable in this build's network
   environment — see `docs/LIMITATIONS.md`).
2. Obtain SIDTD and/or FantasyID (both require a human-completed access step — see
   `training/prepare_dataset.py`'s manual-instructions functions) for real labeled forgery
   data, or at minimum run `training/extract_features.py` against MIDV-2020 plus the
   synthetic placeholder forgeries this build already generates, to unblock the forgery-
   classifier threshold sweep specifically.
3. Extract MIDV-2020 video-clip frames of the same synthetic identity to build matched
   pairs, plus frames from different identities for mismatched pairs, and run
   `training/calibrate_thresholds.py::calibrate_face_match_threshold` against them.
4. Re-run `evaluation/run_evaluation.py` after each change per Section 10.7's regression-
   testing requirement, and update this document with the new values and supporting numbers
   — never silently overwrite a threshold without updating its justification here.
