import asyncio
import copy
import uuid
from datetime import datetime, timezone

from app.db.sync_session import get_sync_db
from app.domain.recommendations.generator import (
    build_llm_messages,
    generate_template_recommendations,
)
from app.integrations.llm.factory import complete_json
from app.schemas.parsed import AnalysisResult, ParsedJob, ParsedResume
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.generate_recommendations.generate_recommendations_task")
def generate_recommendations_task(analysis_id: str) -> None:
    with get_sync_db() as db:
        from app.db.models.analysis import Analysis, Recommendation
        from app.db.models.job import JobDescription
        from app.db.models.resume import Resume

        analysis = db.get(Analysis, uuid.UUID(analysis_id))
        if not analysis or not analysis.result_json:
            return

        resume = db.get(Resume, analysis.resume_id)
        job = db.get(JobDescription, analysis.job_id)
        if not resume or not job:
            return

        cv_data = {k: v for k, v in resume.parsed_json.items() if not k.startswith("_")}
        parsed_cv = ParsedResume.model_validate(cv_data)
        parsed_job = ParsedJob.model_validate(job.parsed_json)
        result = AnalysisResult.model_validate(analysis.result_json)

        bundle = generate_template_recommendations(parsed_cv, parsed_job, result)

        try:
            messages = build_llm_messages(parsed_cv, parsed_job, result)
            llm_result = asyncio.run(complete_json(messages))
            if llm_result and "items" in llm_result:
                bundle["items"] = llm_result["items"]
                if llm_result.get("ats_risks_highlighted"):
                    bundle["ats_risks_highlighted"] = llm_result["ats_risks_highlighted"]
        except Exception:
            pass

        bundle["analysis_id"] = str(analysis.id)
        # Copia explícita: SQLAlchemy no detecta mutaciones in-place en columnas JSON.
        result_dict = copy.deepcopy(analysis.result_json)
        result_dict["recommendations"] = bundle
        result_dict["recommendations_available"] = True
        analysis.result_json = result_dict

        db.query(Recommendation).filter(Recommendation.analysis_id == analysis.id).delete()
        for item in bundle.get("items", []):
            rec = Recommendation(
                analysis_id=analysis.id,
                section=item.get("section", "general"),
                priority=item.get("priority", "medium"),
                recommendation_json=item,
                llm_model="template+optional_llm",
                prompt_version=bundle.get("prompt_version", "reco-v1"),
            )
            db.add(rec)

        analysis.updated_at = datetime.now(timezone.utc)
        db.commit()
