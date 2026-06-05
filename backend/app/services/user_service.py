from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.analysis import Analysis
from app.db.models.file import File
from app.db.models.job import JobDescription
from app.db.models.resume import Resume
from app.db.models.user import User
from app.integrations.storage import s3_client
from app.schemas.user import ConsentUpdate


class UserService:
    @staticmethod
    async def update_consent(db: AsyncSession, user: User, data: ConsentUpdate) -> User:
        user.consent_ai_processing = data.consent_ai_processing
        if data.consent_ai_processing:
            user.consent_retention_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def delete_account(db: AsyncSession, user: User) -> None:
        now = datetime.now(timezone.utc)
        user.deleted_at = now
        user.is_active = False

        files = await db.execute(select(File).where(File.user_id == user.id))
        for f in files.scalars().all():
            try:
                s3_client.delete_file(f.storage_key)
            except Exception:
                pass
            f.deleted_at = now

        for model in (Resume, JobDescription, Analysis):
            rows = await db.execute(select(model).where(model.user_id == user.id))
            for row in rows.scalars().all():
                if hasattr(row, "deleted_at"):
                    row.deleted_at = now

        await db.commit()
