import uuid
from datetime import datetime, timezone

from app.db.sync_session import get_sync_db
from app.domain.parsing.job_parser import parse_job
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.parse_job.parse_job_task")
def parse_job_task(job_id: str) -> None:
    with get_sync_db() as db:
        from app.db.models.job import JobDescription

        job = db.get(JobDescription, uuid.UUID(job_id))
        if not job:
            return

        job.parse_status = "processing"
        db.commit()

        try:
            parsed = parse_job(job.raw_text, job.title)
            job.parsed_json = parsed.model_dump()
            job.parse_status = "completed"
            job.parse_errors = None
        except Exception as exc:
            job.parse_status = "failed"
            job.parse_errors = {"error": str(exc)}
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
