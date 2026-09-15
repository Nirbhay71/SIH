"""Pydantic contracts for every module boundary in the pipeline.

Per Section 3B of the build spec: raw dicts never cross a module boundary.
Every model here is what one module returns and the next module (or the
API layer) consumes. A change to any of these is a breaking change to the
contract described in `docs/ARCHITECTURE.md` and Section 9A of the spec.
"""
from typing import Literal

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class FieldExtraction(BaseModel):
    value: str | None
    confidence: float
    bbox: BoundingBox | None = None


class PreprocessResult(BaseModel):
    status: Literal["ok", "quality_rejected"]
    reason: Literal["blur", "glare"] | None = None
    score: float | None = None
    image_path: str | None = None
    original_bytes_path: str | None = None
    boundary_detection_failed: bool = False
    deskew_skipped_large_angle: bool = False
    photo_bbox: BoundingBox | None = None
    mrz_bbox: BoundingBox | None = None
    field_bboxes: dict[str, BoundingBox] = Field(default_factory=dict)
    stamp_bboxes: list[BoundingBox] = Field(default_factory=list)
    region_segmentation_method: str | None = None


ChecksumStatus = Literal["pass", "fail", "inconclusive_low_confidence", "not_applicable"]


class OCRResult(BaseModel):
    status: Literal["ok", "quality_rejected", "needs_manual_review"]
    document_type: str
    document_type_classification_method: Literal["hinted", "heuristic"] = "heuristic"
    fields: dict[str, FieldExtraction] = Field(default_factory=dict)
    mrz_raw: list[str] | None = None
    mrz_check_digits: dict[str, str] | None = None
    mrz_extraction_method: Literal["passporteye", "fallback_ocr", "not_applicable"] = "not_applicable"
    mrz_valid_score: float | None = None
    ocr_confidence_avg: float = 0.0
    ocr_confidence_min: float = 0.0
    low_confidence_fields: list[str] = Field(default_factory=list)
    quality_flags: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    mrz_checksum_document_number: ChecksumStatus = "not_applicable"
    mrz_checksum_dob: ChecksumStatus = "not_applicable"
    mrz_checksum_expiry: ChecksumStatus = "not_applicable"
    mrz_checksum_composite: ChecksumStatus = "not_applicable"
    format_valid: bool = True
    format_violations: list[str] = Field(default_factory=list)
    logic_consistent: bool = True
    logic_violations: list[str] = Field(default_factory=list)
    cross_zone_match: bool | None = None


class TamperingResult(BaseModel):
    photo_tamper_score: float
    text_manipulation_score_max: float
    text_manipulation_scores_by_field: dict[str, float] = Field(default_factory=dict)
    stamp_forgery_score: float | None = None
    metadata_flag_count: int = 0
    metadata_flags: list[str] = Field(default_factory=list)
    forgery_classifier_probability: float
    forgery_classifier_threshold_used: float
    heatmap_regions: list[BoundingBox] | None = None


class FaceVerificationResult(BaseModel):
    liveness_status: Literal["passed", "failed", "not_applicable"] = "not_applicable"
    liveness_score: float | None = None
    face_match_distance: float | None = None
    face_match_status: Literal["match", "no_match", "needs_officer_review", "not_computed"] = "not_computed"
    threshold_used: float | None = None
    estimated_age_gap_flag: bool = False


class IdentityDedupResult(BaseModel):
    duplicate_identity_flag: bool = False
    matched_record_id: str | None = None
    face_similarity: float | None = None


class HardGateResult(BaseModel):
    triggered: bool
    reason: str | None = None


class ContributingFactor(BaseModel):
    feature: str
    display_name: str
    contribution: float


class RiskAssessment(BaseModel):
    risk_score: int
    risk_tier: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    gate_triggered: str | None = None
    model_probability: float | None = None
    top_contributing_factors: list[ContributingFactor] = Field(default_factory=list)
    model_version: str | None = None


class PipelineResult(BaseModel):
    status: Literal["ok", "quality_rejected", "processing_error"]
    reason: str | None = None
    score: float | None = None
    message: str | None = None
    ocr_result: OCRResult | None = None
    validation_result: ValidationResult | None = None
    tampering_result: TamperingResult | None = None
    face_result: FaceVerificationResult | None = None
    identity_result: IdentityDedupResult | None = None
    risk_assessment: RiskAssessment | None = None
