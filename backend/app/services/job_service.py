import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.db.models.job import JobDescription
from app.db.models.user import User
from app.schemas.job import JobCreate


class JobService:
    @staticmethod
    async def create(db: AsyncSession, user: User, data: JobCreate) -> JobDescription:
        job = JobDescription(
            user_id=user.id,
            title=data.title,
            raw_text=data.raw_text,
            parse_status="queued",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        from app.workers.dispatch import dispatch_task
        from app.workers.tasks.parse_job import parse_job_task

        await dispatch_task(parse_job_task, str(job.id), db, job)
        return job

    @staticmethod
    async def list_jobs(db: AsyncSession, user_id: uuid.UUID) -> list[JobDescription]:
        result = await db.execute(
            select(JobDescription)
            .where(JobDescription.user_id == user_id, JobDescription.deleted_at.is_(None))
            .order_by(JobDescription.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_job(db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> JobDescription:
        result = await db.execute(
            select(JobDescription).where(
                JobDescription.id == job_id,
                JobDescription.user_id == user_id,
                JobDescription.deleted_at.is_(None),
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            raise AppException("JOB_NOT_FOUND", "Oferta no encontrada", 404)
        return job

    @staticmethod
    async def trigger_parse(db: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> JobDescription:
        job = await JobService.get_job(db, user_id, job_id)
        job.parse_status = "queued"
        await db.commit()
        from app.workers.dispatch import dispatch_task
        from app.workers.tasks.parse_job import parse_job_task

        await dispatch_task(parse_job_task, str(job.id), db, job)
        return job
