# AI-Based Fake Identity & Document Screening System — ML Service

## 1. What this service does and does not do

This is the **machine-learning core** for SIH PS 26188 (Ministry of Home Affairs / SSB). It
implements the four problem-statement-mandated modules — OCR extraction, document
validation, tampering detection, and face verification — plus a two-tier risk-scoring fusion
layer, behind a single `/screen` REST endpoint.

It does **not** implement a production officer dashboard, real government database
integration (Passport Seva, Interpol, lookout circulars — a mock watchlist stands in), the
blockchain/hash-chain audit trail, or production-grade authentication/rate-limiting beyond a
basic in-memory guard. See `docs/LIMITATIONS.md` for the full, mandatory disclosure of what
is and is not validated in this build — read it before treating any output as more than a
demonstration of the intended architecture.

## 2. Local setup

Requires Python 3.10+.

```bash
cd ml-service
python -m venv venv
./venv/Scripts/pip install -r requirements.txt   # venv/bin/pip on macOS/Linux
```

**Note on install time:** `requirements.txt` includes several large ML libraries
(PaddleOCR/PaddlePaddle, DeepFace + TensorFlow, PyTorch, FAISS, XGBoost, SHAP). In this
build's own environment, these downloads were unreliable/very slow (see
`docs/LIMITATIONS.md`) — on a normal connection, expect the full install to take
10-30 minutes due to sheer download size (PyTorch alone is ~200 MB, TensorFlow-Intel ~380
MB), not because of any dependency conflict.

Every module that depends on one of these libraries degrades gracefully (with a logged
warning and an explicit, non-fabricated output value) if that specific library isn't
installed — so a partial install still runs, with reduced capability. See
`docs/ARCHITECTURE.md`.

## 3. Running the FastAPI test harness

```bash
./venv/Scripts/python -m uvicorn api.main:app --port 8000
```

Sample request:

```bash
curl -X POST http://127.0.0.1:8000/screen \
  -F "document_image=@path/to/document.jpg" \
  -F "live_capture_image=@path/to/selfie.jpg" \
  -F "document_type_hint=indian_passport"
```

`document_type_hint` and `live_capture_image` are both optional — see Section 9A of the
build spec (or `api/routes.py`) for the full request/response contract.

## 4. Running the test suite

```bash
./venv/Scripts/python -m pytest -q
```

49 tests currently pass, covering every module's deterministic logic (checksum validation,
hard-gate ordering, quality gating, tampering forensic sub-checks, the duplicate-identity
dual condition) without requiring the optional heavy ML dependencies to be installed. Tests
that specifically require PaddleOCR/DeepFace/XGBoost etc. are written to be added once those
are installed and a trained model exists (see `docs/LIMITATIONS.md`).

## 5. Reproducing dataset prep, feature extraction, training, and evaluation

In order:

```bash
./venv/Scripts/python -m training.prepare_dataset       # downloads MIDV-2020, generates placeholder forgeries
./venv/Scripts/python -m training.extract_features       # runs the full pipeline over the dataset, writes a feature table
./venv/Scripts/python -m training.train_fusion_model      # trains and versions the XGBoost fusion model
./venv/Scripts/python -m training.calibrate_thresholds    # prints recall-biased threshold recommendations
./venv/Scripts/python -m evaluation.run_evaluation         # produces the full metrics report
```

**Read `docs/LIMITATIONS.md` before running these** — `prepare_dataset.py` can only
automatically fetch MIDV-2020 (freely licensed); SIDTD and FantasyID both require a
human-completed access step (a TC-11 account signup, and an email request to the DeepID
ICCV Challenge organizers, respectively) and are not fetched by this script. Training
without them uses a synthetic placeholder forged class this script generates itself, clearly
labeled as such in every downstream artifact (model manifests, model cards).

## 6. Limitations — read this

**[`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) is the single most important file in this
repository for understanding this system's real-world readiness.** It documents, without
omission: that this pipeline is trained/evaluated on synthetic data only, that no
adversarial robustness testing has been performed, that face-verification demographic
fairness has not been evaluated, that the watchlist and stamp-reference library are mocked,
that no real-checkpoint load testing has been performed, and that human officer oversight is
mandatory. It also documents this specific build's own environment-driven gaps (heavy
dependency installs and two of three research datasets could not be obtained
automatically) — read it before quoting any number from this repository.

## 7. Environment variables

| Variable | Default | Effect |
|---|---|---|
| `ML_SERVICE_PORT` | 8000 | Port the FastAPI harness listens on (when run via the Dockerfile's `CMD`; `uvicorn --port` overrides this when running directly). |
| `ML_SERVICE_LOG_LEVEL` | INFO | Log verbosity for the API and every per-module logger (`src.ocr`, `src.validation`, `src.tampering`, `src.face`, `src.fusion`). |
| `MODEL_ARTIFACT_DIR` | /app/training/artifacts | Where trained model artifacts (fusion model, feature manifest) are read from in the container. |
| `MAX_UPLOAD_SIZE_MB` | 15 | Resource-limit gate (Section 11) — purely a memory/CPU-exposure control, **no accuracy implication**. |
| `MAX_IMAGE_DIMENSION_PX` | 6000 | Same as above — performance/memory only, **no accuracy implication**. Raising it does not improve OCR/tampering/face accuracy on a given image; it only permits larger uploads to be processed. |
| `FAISS_INDEX_PATH` | /app/data/identity_index.faiss | Where the identity-deduplication FAISS index is persisted. |
| `WATCHLIST_MOCK_DB_PATH` | /app/data/mock_watchlist.json | Path to the simulated watchlist data — **not a real government database**, see `docs/LIMITATIONS.md`. |

## 8. Dataset licenses (Section 11A)

- **MIDV-2020**: freely available from the official mirrors
  (ftp://smartengines.com/midv-2020, http://l3i-share.univ-lr.fr), consisting of synthetic
  mock identity documents with artificially generated faces — no real people's data. See its
  `license.txt` at the download mirror for exact terms.
- **SIDTD**: Creative Commons Attribution-ShareAlike 2.5, hosted at
  http://tc11.cvc.uab.es/datasets/SIDTD_1 behind a free account signup. Not fetched
  automatically in this build (see `docs/LIMITATIONS.md`).
- **FantasyID**: CC BY 4.0 (majority of the data), distributed on request via the DeepID
  ICCV Challenge organizers (https://deepid-iccv.github.io/). Not fetched automatically in
  this build.

This project does not use, and must never be extended to use, scraped real passport/ID
images from the internet or social media — see Section 11A of the build spec.

## 9. Multi-language OCR note (Section 5.3)

The pinned PaddleOCR version (2.8.1) requires a separate `PaddleOCR` instance per language
rather than one multilingual instance; `src/ocr/field_ocr.py` runs English and Hindi passes
independently per field crop and keeps the higher-confidence result. Re-verify this against
whatever PaddleOCR version is actually installed if you change the pin.
