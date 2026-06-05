import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResumeUploadResponse(BaseModel):
    id: uuid.UUID
    parse_status: str
    title: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ResumeResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    parse_status: str
    extraction_method: str | None
    language_detected: str | None
    parsed_json: dict | None
    parse_errors: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeListItem(BaseModel):
    id: uuid.UUID
    title: str | None
    parse_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
