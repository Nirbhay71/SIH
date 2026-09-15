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

# Thresholds — documented here so they're easy to tune (Part F.7 / F.5 / F.6)
FACE_MATCH_HIGH_CONFIDENCE_THRESHOLD = 0.75
WATCHLIST_MATCH_THRESHOLD = 0.85
DUPLICATE_FACE_SIMILARITY_THRESHOLD = 0.80
DUPLICATE_WINDOW_HOURS = 2
IMPOSSIBLE_TRAVEL_MAX_KMH = 900.0

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
