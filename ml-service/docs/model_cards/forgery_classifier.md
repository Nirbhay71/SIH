# Model Card: Module 3 Learned Forgery Classifier

## Status

**Not fine-tuned in this build.** `torch`/`timm` could not be installed in this build's
environment (see `docs/LIMITATIONS.md`), so `src/tampering/forgery_classifier.py` has never
actually run inference. When the dependencies or the fine-tuned head are unavailable,
`classify_forgery_probability` returns a fixed, clearly-flagged uninformative probability
(0.5) with `model_is_calibrated=False`, rather than a fabricated confident score — this
degraded path is what the `/screen` endpoint exercised during this build's live testing (it
was reached; the pipeline itself failed closed later, at the fusion layer, for the separate
reason that no trained fusion model exists either).

## Architecture and path taken

No suitable pretrained SIDTD/MIDV-2020-fine-tuned forgery-detection checkpoint was found and
vetted on Hugging Face within this build's time budget. Per the spec's own explicit fallback
instruction (Section 3), this uses `timm`'s `efficientnet_b3` pretrained on ImageNet as a
backbone with a binary classification head, intended to be fine-tuned by a (not yet written
in full, and not yet run) `training/train_forgery_head.py` script against the labeled
feature-extraction dataset from `training/extract_features.py`.

## Training data (once fine-tuned)

Same caveat as the fusion model: only MIDV-2020 (genuine) plus this build's own synthetic
placeholder forged images (`training/prepare_dataset.py::generate_synthetic_forgeries`) are
available — SIDTD and FantasyID both require a human-completed access step not obtainable
autonomously (see `docs/LIMITATIONS.md`).

## Headline metrics

Not available — no fine-tuning run has been completed.

## Threshold

`config/thresholds.yaml`'s `tampering.forgery_classifier_threshold` (0.4, recall-biased per
Section 7.5) is the spec's own suggested starting value, not a calibrated one —
`training/calibrate_thresholds.py::calibrate_forgery_classifier_threshold` implements the
required recall-biased sweep but has not been run (see `docs/THRESHOLD_JUSTIFICATIONS.md`).

## Per-forgery-type breakdown

Not available (see the fusion model card — same root cause).

## Known weaknesses

- Untrained head as shipped — its raw probability output should not be treated as
  meaningful until `training/train_forgery_head.py` has been run.
- Once trained, only on synthetic placeholder data, not SIDTD/FantasyID — see
  `docs/LIMITATIONS.md`'s Reality Gap discussion.
- Face-swap-style forgeries are documented in the literature as a harder case for
  compression-artifact-based and CNN classifiers generally; this build has no data to
  confirm or refute that for this specific model.

## Intended scope of use

One of four independent Module 3 signals (alongside photo-boundary, text-manipulation, and
stamp forensics), feeding the Tier 2 fusion model — never used alone as a tampering
determination. See Section 7.3A of the build spec for why relying on this signal alone would
reintroduce a known failure mode.
