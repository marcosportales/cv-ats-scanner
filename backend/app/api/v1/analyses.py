import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisListItem,
    AnalysisResponse,
    RecommendationBundleResponse,
)
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisResponse, status_code=202)
async def create_analysis(
    data: AnalysisCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalysisResponse:
    analysis = await AnalysisService.create(db, current_user, data)
    return AnalysisResponse.model_validate(analysis)


@router.get("", response_model=list[AnalysisListItem])
async def list_analyses(
    resume_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AnalysisListItem]:
    analyses = await AnalysisService.list_analyses(db, current_user.id, resume_id)
    return [AnalysisListItem.model_validate(a) for a in analyses]


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalysisResponse:
    analysis = await AnalysisService.get_analysis(db, current_user.id, analysis_id)
    return AnalysisResponse.model_validate(analysis)


@router.get("/{analysis_id}/report")
async def get_report(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    analysis = await AnalysisService.get_analysis(db, current_user.id, analysis_id)
    return analysis.result_json or {}


@router.post("/{analysis_id}/recommendations", status_code=202)
async def request_recommendations(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await AnalysisService.trigger_recommendations(db, current_user, analysis_id)
    return {"status": "queued", "analysis_id": str(analysis_id)}


@router.get("/{analysis_id}/recommendations", response_model=RecommendationBundleResponse | dict)
async def get_recommendations(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = await AnalysisService.get_analysis(db, current_user.id, analysis_id)
    recs = await AnalysisService.get_recommendations(db, current_user.id, analysis_id)
    if analysis.result_json and analysis.result_json.get("recommendations"):
        bundle = analysis.result_json["recommendations"]
        return RecommendationBundleResponse(
            analysis_id=analysis_id,
            prompt_version=bundle.get("prompt_version", "reco-v1"),
            items=bundle.get("items", []),
            disclaimer=bundle.get("disclaimer", ""),
        )
    return {"items": recs}


@router.get("/{analysis_id}/export/pdf")
async def export_pdf(
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    pdf_bytes = await AnalysisService.export_pdf(db, current_user.id, analysis_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="informe-{analysis_id}.pdf"'},
    )
