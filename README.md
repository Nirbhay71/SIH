# AI-Based Fake Identity & Document Screening System

SIH 2026 · Problem Statement 26188 · India–Nepal border (SSB checkpoints)

An officer-facing web app that screens a traveller's identity document and live face at a checkpoint, then gives an explainable risk decision (LOW / MEDIUM / HIGH) with the reasons behind it.

## Architecture

```
React + Vite frontend (:5173)  ──►  FastAPI backend (:8000)  ──►  ML service (:8001)
   camera, i18n (en/hi/ne)           SQLite, auth, risk model,        MRZ, OCR, face match,
   results, admin, WebSocket         acceptance policy, audit chain   liveness, forensics
```

| Folder | What it is |
|---|---|
| `frontend/` | React 18 + Vite 5 UI. Camera-only face capture, live pipeline progress, result page, admin dashboard. English, Hindi, Nepali. |
| `backend/` | FastAPI + async SQLAlchemy + SQLite (`backend/app.db`). Orchestrates the flow, applies the risk model and acceptance policy, keeps the audit log. |
| `ml-service/` | Machine-learning core: passporteye MRZ, PaddleOCR (en/hi), DeepFace ArcFace + RetinaFace, anti-spoofing, EfficientNet-B3 forgery backbone, XGBoost fusion with SHAP. Has its own [README](ml-service/README.md). |
| `deploy/` | Caddyfile (TLS reverse proxy) and an optional Postgres compose file. Not yet tested end to end. |

## What it does

- **Document analysis**: MRZ parsing with check-digit-driven repair of OCR errors and per-field confidence; full-page OCR for non-MRZ documents (Aadhaar with Verhoeff check, PAN, driving licence, voter ID).
- **Face verification**: live camera capture matched against the document photo, with liveness / anti-spoofing.
- **Acceptance policy (India–Nepal)**: documents accepted depend on age bracket; a family provision handles children travelling with a parent. Aadhaar is deliberately not accepted for adults. Photocopies are flagged as a validation failure.
- **Watchlist**: checks both the live face and the document photo.
- **Risk score**: hard gates (watchlist match, document not accepted → 100 / HIGH) plus weighted factors summing to 100: tampering 35, face mismatch 30, liveness 15, validation 10, suspicious direction 5, impossible travel 5. LOW ≤ 30, MEDIUM ≤ 65, otherwise HIGH. The ML fusion score is shown only as an informational cross-check.
- **Audit**: SHA-256 hash-chained log of decisions.
- **Fail-closed face step**: if the face service fails, no match result is invented. The record is flagged incomplete, the risk is floored at 31, and the officer can retry. If the document step falls back to mock data, the UI shows a "Demo Data" banner.

## Prerequisites

- Python 3.10
- Node.js 18+ (developed on v24)
- Tesseract OCR (Windows: `C:\Program Files\Tesseract-OCR`; the ML service adds it to PATH automatically)
- Several GB of disk for the ML dependencies and model downloads

## Running (three terminals)

**1. ML service** (first start takes about 60–100 s to warm up; check `GET /ready`)
```powershell
cd ml-service
.\venv\Scripts\python.exe -m uvicorn api.main:app --port 8001
```

**2. Backend**
```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

**3. Frontend**
```powershell
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. Setup for each service's virtualenv is in `ml-service/README.md` and `backend/requirements.txt`.

Optional demo data: `python seed_demo_data.py` from `backend/`.

Without the ML service, document analysis falls back to labelled mock data. The face step will not.

## Configuration

Backend environment variables (see `backend/.env.example`):

`APP_ENV`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `CORS_ORIGINS`, `BEHIND_TLS_PROXY`, `ML_SERVICE_URL`, `ML_SERVICE_TIMEOUT_SECONDS`, `ML_SERVICE_FACE_TIMEOUT_SECONDS`, `DATABASE_URL`, `AUTH_RATE_LIMIT_PER_MINUTE`.

ML service: `ML_SERVICE_WARMUP` (default true), `ML_SERVICE_LOG_LEVEL`.

**Development admin credentials are for local use only.** Set `APP_ENV=production` with your own `ADMIN_USERNAME` / `ADMIN_PASSWORD` and serve behind HTTPS (see `deploy/Caddyfile`) for anything beyond a demo.

## Tests

```powershell
cd backend;    .\venv\Scripts\python.exe -m pytest
cd ml-service; .\venv\Scripts\python.exe -m pytest
```

`ml-service/evaluation/` holds measurement scripts (OCR robustness, tampering on real documents, LFW face-threshold evaluation). Failed experiments are recorded in `ml-service/docs/LIMITATIONS.md`.

## Known limitations

- Tampering detection is **not validated**: the forgery classifier head is untrained, and the heuristics tried did not discriminate. Its output is evidence only, and it is not a reliable signal.
- The face threshold (0.58 cosine distance) was set on synthetic pairs. An LFW evaluation exists but its results have not been reviewed yet.
- Aadhaar number extraction is not reliable on every card.
- OCR quality drops on heavily noisy or low-resolution images.
- Bundled sample documents are synthetic and contain no real face.
- HTTPS and Postgres deployment files are untested.
- Not production-hardened or certified for real border use.

## Privacy

Never commit real identity documents, `backend/app.db`, uploaded files, or logs. Evaluation documents belong in a git-ignored folder.
