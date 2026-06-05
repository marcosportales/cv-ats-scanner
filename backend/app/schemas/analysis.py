import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalysisCreate(BaseModel):
    resume_id: uuid.UUID
    job_id: uuid.UUID


class AnalysisResponse(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    total_score: float | None
    ats_score: float | None
    job_match_score: float | None
    result_json: dict | None
    scoring_version: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisListItem(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    total_score: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecommendationBundleResponse(BaseModel):
    analysis_id: uuid.UUID
    prompt_version: str
    items: list[dict]
    disclaimer: str
