from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.database import init_db
from app.routers import verification, audit, admin
from app.security import enforce_startup_policy, security_headers_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    enforce_startup_policy()
    await init_db()
    yield


app = FastAPI(title="AI-Based Fake Identity & Document Screening System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.middleware("http")(security_headers_middleware)

app.include_router(verification.router)
app.include_router(audit.router)
app.include_router(admin.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
