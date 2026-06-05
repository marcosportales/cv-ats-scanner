import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import JSONType
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class JobDescription(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "job_descriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="paste", nullable=False)
    parsed_json: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    parse_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="job_descriptions")
    chunks = relationship("JobChunk", back_populates="job", cascade="all, delete-orphan")
    analyses = relationship("Analysis", back_populates="job")
