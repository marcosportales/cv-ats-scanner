import uuid

from app.config import settings
from app.db.sync_session import get_sync_db
from app.integrations.embeddings.local import embed_text
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.index_embeddings.index_resume_embeddings_task")
def index_resume_embeddings_task(resume_id: str) -> None:
    if not settings.enable_semantic_match:
        return

    with get_sync_db() as db:
        from app.db.models.chunk import ResumeChunk
        from app.db.models.resume import Resume

        resume = db.get(Resume, uuid.UUID(resume_id))
        if not resume or not resume.parsed_json:
            return

        db.query(ResumeChunk).filter(ResumeChunk.resume_id == resume.id).delete()

        for exp in resume.parsed_json.get("experience", []):
            for bullet in exp.get("bullets", []):
                chunk = ResumeChunk(
                    resume_id=resume.id,
                    chunk_type="experience",
                    content=bullet,
                    chunk_metadata={"role": exp.get("role")},
                    embedding=embed_text(bullet),
                )
                db.add(chunk)
        db.commit()
