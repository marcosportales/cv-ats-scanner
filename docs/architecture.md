# CV ATS Scanner — Architecture

See the project README for setup. Core pipeline:

1. Upload CV → S3 → Celery `parse_resume_task`
2. Create job → Celery `parse_job_task`
3. Create analysis → Celery `run_analysis_task` (rules + matching + scoring)
4. Optional → Celery `generate_recommendations_task` (template + LLM)
5. Export PDF via WeasyPrint

Domain logic lives in `backend/app/domain/` (no FastAPI imports).
