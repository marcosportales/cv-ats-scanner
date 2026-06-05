import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.resume import ResumeListItem, ResumeResponse, ResumeUploadResponse
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/upload", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeUploadResponse:
    resume = await ResumeService.upload(db, current_user, file)
    return ResumeUploadResponse(
        id=resume.id, parse_status=resume.parse_status, title=resume.title
    )


@router.get("", response_model=list[ResumeListItem])
async def list_resumes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ResumeListItem]:
    resumes = await ResumeService.list_resumes(db, current_user.id)
    return [ResumeListItem.model_validate(r) for r in resumes]


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeResponse:
    resume = await ResumeService.get_resume(db, current_user.id, resume_id)
    return ResumeResponse.model_validate(resume)


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await ResumeService.delete_resume(db, current_user, resume_id)


@router.post("/{resume_id}/parse", response_model=ResumeResponse)
async def parse_resume(
    resume_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeResponse:
    resume = await ResumeService.trigger_parse(db, current_user.id, resume_id)
    return ResumeResponse.model_validate(resume)
