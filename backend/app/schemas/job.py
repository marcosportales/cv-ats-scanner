import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    title: str | None = None
    raw_text: str = Field(..., min_length=50)


class JobResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    parse_status: str
    parsed_json: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobListItem(BaseModel):
    id: uuid.UUID
    title: str | None
    parse_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
