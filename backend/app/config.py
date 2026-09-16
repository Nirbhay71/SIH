"""
Central configuration. Uses SQLite by default so the project runs with zero
external services (no Postgres install required for the demo). Set
DATABASE_URL to a Postgres+asyncpg URL in production; pgvector is not
required — embeddings are stored as JSON float arrays and compared with
cosine similarity in Python (see Part C.3 of the master spec, which
explicitly allows this fallback at demo scale).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(exist_ok=True)
(STORAGE_DIR / "documents").mkdir(exist_ok=True)
(STORAGE_DIR / "faces").mkdir(exist_ok=True)
(STORAGE_DIR / "heatmaps").mkdir(exist_ok=True)
(STORAGE_DIR / "watchlist").mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'app.db'}")

# Real ML service (see ../ml-service). When reachable, the verification
# pipeline uses its real OCR/tampering/face models instead of the mock
# modules in app/modules/ — see app/ml_client.py. Falls back to the mocks
# automatically (with a logged/emitted warning) if this URL is unreachable,
# so the demo never hard-depends on the heavy ML stack being up.
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://127.0.0.1:8001")
ML_SERVICE_TIMEOUT_SECONDS = float(os.getenv("ML_SERVICE_TIMEOUT_SECONDS", "60"))

# Thresholds — documented here so they're easy to tune (Part F.7 / F.5 / F.6)
FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD = 0.75
DUPLICATE_WINDOW_HOURS = 2
IMPOSSIBLE_TRAVEL_MAX_KMH = 900.0

# Mock module embeddings (app/modules/face.py) and ml-service's real ArcFace
# embeddings occupy different cosine-similarity ranges, so each embedding
# source needs its own threshold. Every stored embedding is tagged with
# which source produced it (VerificationRecord.face_embedding_source /
# WatchlistFace.embedding_source); comparisons across mismatched sources are
# skipped rather than compared under the wrong threshold.
MOCK_WATCHLIST_MATCH_THRESHOLD = 0.85
MOCK_DUPLICATE_FACE_SIMILARITY_THRESHOLD = 0.80
# Derived from ml-service's calibrated face.match_distance_threshold (0.58,
# see ml-service/config/thresholds.yaml) via similarity = 1 - distance.
ML_WATCHLIST_MATCH_THRESHOLD = 0.42
ML_DUPLICATE_FACE_SIMILARITY_THRESHOLD = 0.42

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
