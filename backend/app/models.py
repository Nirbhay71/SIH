import uuid
from datetime import datetime

from sqlalchemy import String, Float, Boolean, DateTime, Date, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(String, index=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    doc_type: Mapped[str | None] = mapped_column(String, nullable=True)
    doc_number: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    dob: Mapped[str | None] = mapped_column(String, nullable=True)
    nationality: Mapped[str | None] = mapped_column(String, nullable=True)
    expiry_date: Mapped[str | None] = mapped_column(String, nullable=True)

    document_image_path: Mapped[str | None] = mapped_column(String, nullable=True)
    ocr_raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    tampering_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tampering_result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tampering_heatmap_path: Mapped[str | None] = mapped_column(String, nullable=True)

    face_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    liveness_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    live_face_embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    live_face_image_path: Mapped[str | None] = mapped_column(String, nullable=True)

    watchlist_match: Mapped[bool] = mapped_column(Boolean, default=False)
    watchlist_match_ref: Mapped[str | None] = mapped_column(String, nullable=True)

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    travel_direction: Mapped[str | None] = mapped_column(String, nullable=True)

    duplicate_of_record_id: Mapped[str | None] = mapped_column(String, ForeignKey("verification_records.id"), nullable=True)
    travel_direction_flag: Mapped[str] = mapped_column(String, default="not_applicable")
    impossible_travel_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    impossible_travel_detail_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_breakdown_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    officer_decision: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    record_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    prev_hash: Mapped[str | None] = mapped_column(String, nullable=True)


class WatchlistFace(Base):
    __tablename__ = "watchlist_faces"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    reference_label: Mapped[str] = mapped_column(String)
    embedding: Mapped[list] = mapped_column(JSON)
    photo_path: Mapped[str] = mapped_column(String)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    uploaded_by: Mapped[str] = mapped_column(String, default="admin")
