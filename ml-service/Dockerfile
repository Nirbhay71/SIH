FROM python:3.11-slim

WORKDIR /app

# System libraries required by opencv-python and paddleocr at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV ML_SERVICE_PORT=8000 \
    ML_SERVICE_LOG_LEVEL=INFO \
    MODEL_ARTIFACT_DIR=/app/training/artifacts \
    MAX_UPLOAD_SIZE_MB=15 \
    MAX_IMAGE_DIMENSION_PX=6000 \
    FAISS_INDEX_PATH=/app/data/identity_index.faiss \
    WATCHLIST_MOCK_DB_PATH=/app/data/mock_watchlist.json

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
