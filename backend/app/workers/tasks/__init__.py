from app.workers.tasks.generate_recommendations import generate_recommendations_task
from app.workers.tasks.index_embeddings import index_resume_embeddings_task
from app.workers.tasks.parse_job import parse_job_task
from app.workers.tasks.parse_resume import parse_resume_task
from app.workers.tasks.run_analysis import run_analysis_task

__all__ = [
    "parse_resume_task",
    "parse_job_task",
    "run_analysis_task",
    "generate_recommendations_task",
    "index_resume_embeddings_task",
]
