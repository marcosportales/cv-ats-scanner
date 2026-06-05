from pydantic import BaseModel


class ConsentUpdate(BaseModel):
    consent_ai_processing: bool


class ConsentResponse(BaseModel):
    consent_ai_processing: bool
    consent_retention_at: str | None
