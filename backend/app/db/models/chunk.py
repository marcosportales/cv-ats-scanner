import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONType, TimestampMixin, UUIDMixin

EMBEDDING_DIM = 384


class ResumeChunk(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "resume_chunks"

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), index=True
    )
    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict | None] = mapped_column("metadata", JSONType, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    resume = relationship("Resume", back_populates="chunks")


class JobChunk(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "job_chunks"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_descriptions.id", ondelete="CASCADE"), index=True
    )
    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict | None] = mapped_column("metadata", JSONType, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    job = relationship("JobDescription", back_populates="chunks")
