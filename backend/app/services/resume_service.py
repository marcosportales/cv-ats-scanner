import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.db.models.file import File
from app.db.models.resume import Resume
from app.db.models.user import User
from app.integrations.storage import s3_client

ALLOWED_MIMES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


class ResumeService:
    @staticmethod
    async def upload(db: AsyncSession, user: User, file: UploadFile) -> Resume:
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise AppException("FILE_TOO_LARGE", "El archivo supera 5MB", 400)

        mime = file.content_type or ""
        if mime not in ALLOWED_MIMES:
            raise AppException("INVALID_FILE_TYPE", "Solo PDF y DOCX", 400)

        storage_key, checksum = s3_client.upload_file(
            user.id, file.filename or "resume.pdf", content, mime
        )

        file_record = File(
            user_id=user.id,
            storage_key=storage_key,
            original_filename=file.filename or "resume",
            mime_type=mime,
            size_bytes=len(content),
            checksum_sha256=checksum,
            virus_scan_status="skipped",
        )
        db.add(file_record)
        await db.flush()

        resume = Resume(
            user_id=user.id,
            file_id=file_record.id,
            title=file.filename,
            parse_status="queued",
        )
        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        from app.workers.dispatch import dispatch_task
        from app.workers.tasks.parse_resume import parse_resume_task

        await dispatch_task(parse_resume_task, str(resume.id), db, resume)
        return resume

    @staticmethod
    async def list_resumes(db: AsyncSession, user_id: uuid.UUID) -> list[Resume]:
        result = await db.execute(
            select(Resume)
            .where(Resume.user_id == user_id, Resume.deleted_at.is_(None))
            .order_by(Resume.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_resume(db: AsyncSession, user_id: uuid.UUID, resume_id: uuid.UUID) -> Resume:
        result = await db.execute(
            select(Resume).where(
                Resume.id == resume_id,
                Resume.user_id == user_id,
                Resume.deleted_at.is_(None),
            )
        )
        resume = result.scalar_one_or_none()
        if not resume:
            raise AppException("RESUME_NOT_FOUND", "CV no encontrado", 404)
        return resume

    @staticmethod
    async def delete_resume(db: AsyncSession, user: User, resume_id: uuid.UUID) -> None:
        resume = await ResumeService.get_resume(db, user.id, resume_id)
        from datetime import datetime, timezone

        resume.deleted_at = datetime.now(timezone.utc)
        if resume.file_id:
            file_result = await db.execute(select(File).where(File.id == resume.file_id))
            f = file_result.scalar_one_or_none()
            if f:
                try:
                    s3_client.delete_file(f.storage_key)
                except Exception:
                    pass
                f.deleted_at = resume.deleted_at
        await db.commit()

    @staticmethod
    async def trigger_parse(db: AsyncSession, user_id: uuid.UUID, resume_id: uuid.UUID) -> Resume:
        resume = await ResumeService.get_resume(db, user_id, resume_id)
        resume.parse_status = "queued"
        await db.commit()
        from app.workers.dispatch import dispatch_task
        from app.workers.tasks.parse_resume import parse_resume_task

        await dispatch_task(parse_resume_task, str(resume.id), db, resume)
        return resume
