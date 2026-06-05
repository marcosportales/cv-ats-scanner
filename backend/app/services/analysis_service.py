import copy
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.db.models.analysis import Analysis, Recommendation
from app.db.models.user import User
from app.schemas.analysis import AnalysisCreate
from app.services.job_service import JobService
from app.services.resume_service import ResumeService

RECO_DISCLAIMER = (
    "Recomendaciones generadas por IA o plantillas. Revisa manualmente antes de enviar tu CV. "
    "La puntuación es estimada y no garantiza contratación."
)


class AnalysisService:
    @staticmethod
    async def _sync_recommendations_into_result_json(
        db: AsyncSession, analysis: Analysis
    ) -> None:
        """Repara result_json si hay filas en recommendations pero el JSON quedó desincronizado."""
        if not analysis.result_json or analysis.result_json.get("recommendations_available"):
            return

        result = await db.execute(
            select(Recommendation)
            .where(Recommendation.analysis_id == analysis.id)
            .order_by(Recommendation.created_at)
        )
        recs = list(result.scalars().all())
        if not recs:
            return

        bundle = {
            "analysis_id": str(analysis.id),
            "prompt_version": recs[0].prompt_version,
            "items": [r.recommendation_json for r in recs],
            "disclaimer": RECO_DISCLAIMER,
        }
        result_dict = copy.deepcopy(analysis.result_json)
        result_dict["recommendations"] = bundle
        result_dict["recommendations_available"] = True
        analysis.result_json = result_dict
        analysis.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(analysis)

    @staticmethod
    async def create(db: AsyncSession, user: User, data: AnalysisCreate) -> Analysis:
        resume = await ResumeService.get_resume(db, user.id, data.resume_id)
        job = await JobService.get_job(db, user.id, data.job_id)

        if resume.parse_status != "completed":
            raise AppException("RESUME_NOT_PARSED", "El CV aún no está parseado", 400)
        if job.parse_status != "completed":
            raise AppException("JOB_NOT_PARSED", "La oferta aún no está parseada", 400)

        analysis = Analysis(
            user_id=user.id,
            resume_id=resume.id,
            job_id=job.id,
            status="queued",
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)

        from app.workers.dispatch import dispatch_task
        from app.workers.tasks.run_analysis import run_analysis_task

        await dispatch_task(run_analysis_task, str(analysis.id), db, analysis)
        return analysis

    @staticmethod
    async def list_analyses(
        db: AsyncSession, user_id: uuid.UUID, resume_id: uuid.UUID | None = None
    ) -> list[Analysis]:
        query = select(Analysis).where(Analysis.user_id == user_id)
        if resume_id:
            query = query.where(Analysis.resume_id == resume_id)
        query = query.order_by(Analysis.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_analysis(db: AsyncSession, user_id: uuid.UUID, analysis_id: uuid.UUID) -> Analysis:
        result = await db.execute(
            select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user_id)
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            raise AppException("ANALYSIS_NOT_FOUND", "Análisis no encontrado", 404)
        await AnalysisService._sync_recommendations_into_result_json(db, analysis)
        return analysis

    @staticmethod
    async def trigger_recommendations(
        db: AsyncSession, user: User, analysis_id: uuid.UUID
    ) -> Analysis:
        analysis = await AnalysisService.get_analysis(db, user.id, analysis_id)
        if analysis.status != "completed":
            raise AppException("ANALYSIS_NOT_READY", "El análisis no ha terminado", 400)
        if not user.consent_ai_processing:
            raise AppException("CONSENT_REQUIRED", "Debes aceptar el procesamiento con IA", 403)

        from app.workers.dispatch import dispatch_task
        from app.workers.tasks.generate_recommendations import generate_recommendations_task

        await dispatch_task(generate_recommendations_task, str(analysis.id), db, analysis)
        return analysis

    @staticmethod
    async def get_recommendations(db: AsyncSession, user_id: uuid.UUID, analysis_id: uuid.UUID) -> list:
        await AnalysisService.get_analysis(db, user_id, analysis_id)
        result = await db.execute(
            select(Recommendation).where(Recommendation.analysis_id == analysis_id)
        )
        recs = result.scalars().all()
        if recs:
            items = [r.recommendation_json for r in recs]
            return items
        analysis = await AnalysisService.get_analysis(db, user_id, analysis_id)
        if analysis.result_json and analysis.result_json.get("recommendations"):
            return [analysis.result_json["recommendations"]]
        return []

    @staticmethod
    async def export_pdf(db: AsyncSession, user_id: uuid.UUID, analysis_id: uuid.UUID) -> bytes:
        analysis = await AnalysisService.get_analysis(db, user_id, analysis_id)
        if not analysis.result_json:
            raise AppException("NO_REPORT", "Informe no disponible", 404)
        from app.integrations.reports.pdf_export import generate_analysis_pdf

        return generate_analysis_pdf(analysis.result_json)
