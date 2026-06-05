import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.job import JobCreate, JobListItem, JobResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    job = await JobService.create(db, current_user, data)
    return JobResponse.model_validate(job)


@router.get("", response_model=list[JobListItem])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobListItem]:
    jobs = await JobService.list_jobs(db, current_user.id)
    return [JobListItem.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    job = await JobService.get_job(db, current_user.id, job_id)
    return JobResponse.model_validate(job)


@router.post("/{job_id}/parse", response_model=JobResponse)
async def parse_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    job = await JobService.trigger_parse(db, current_user.id, job_id)
    return JobResponse.model_validate(job)
