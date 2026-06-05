import uuid
from datetime import datetime, timezone

from app.config import settings
from app.db.sync_session import get_sync_db
from app.domain.ats.rules_engine import AtsIssue, run_ats_rules
from app.domain.matching.keyword_matcher import match_cv_to_job
from app.domain.scoring.engine import compute_scores
from app.schemas.parsed import ParsedJob, ParsedResume
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.run_analysis.run_analysis_task")
def run_analysis_task(analysis_id: str) -> None:
    with get_sync_db() as db:
        from app.db.models.analysis import Analysis, AnalysisEvent
        from app.db.models.job import JobDescription
        from app.db.models.resume import Resume

        analysis = db.get(Analysis, uuid.UUID(analysis_id))
        if not analysis:
            return

        analysis.status = "processing"
        analysis.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            resume = db.get(Resume, analysis.resume_id)
            job = db.get(JobDescription, analysis.job_id)
            if not resume or not job or not resume.parsed_json or not job.parsed_json:
                raise ValueError("Resume or job not parsed")

            cv_data = {k: v for k, v in resume.parsed_json.items() if not k.startswith("_")}
            meta = resume.parsed_json.get("_extraction_meta", {})
            parsed_cv = ParsedResume.model_validate(cv_data)
            parsed_job = ParsedJob.model_validate(job.parsed_json)

            match = match_cv_to_job(parsed_cv, parsed_job)
            if resume.raw_text:
                issues = run_ats_rules(
                    resume.raw_text,
                    parsed_cv,
                    needs_ocr=meta.get("needs_ocr", False),
                    image_count=meta.get("image_count", 0),
                    chars_per_page=meta.get("chars_per_page", 500),
                )
            else:
                issues_data = resume.parsed_json.get("_ats_issues", [])
                issues = [
                    AtsIssue(
                        id=i["id"],
                        severity=i["severity"],
                        penalty=i["penalty"],
                        message=i["message"],
                        fix_hint=i.get("fix_hint"),
                        confidence=i.get("confidence", "high"),
                        evidence=i.get("evidence"),
                    )
                    for i in issues_data
                ]

            result = compute_scores(
                parsed_cv,
                parsed_job,
                match,
                issues,
                needs_ocr=meta.get("needs_ocr", False),
                chars_per_page=meta.get("chars_per_page", 500),
                text_length=meta.get("text_length", len(resume.raw_text or "")),
                scoring_version=settings.scoring_version,
            )

            analysis.total_score = result.total_score
            analysis.ats_score = result.ats_score
            analysis.job_match_score = result.job_match_score
            analysis.result_json = result.model_dump()
            analysis.status = "completed"
            analysis.completed_at = datetime.now(timezone.utc)
            analysis.error_message = None

            event = AnalysisEvent(
                analysis_id=analysis.id,
                event_type="scoring_completed",
                payload={"total_score": result.total_score, "level": result.level},
            )
            db.add(event)
        except Exception as exc:
            analysis.status = "failed"
            analysis.error_message = str(exc)
            analysis.completed_at = datetime.now(timezone.utc)
        analysis.updated_at = datetime.now(timezone.utc)
        db.commit()
