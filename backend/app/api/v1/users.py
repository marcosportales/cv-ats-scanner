from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.user import ConsentResponse, ConsentUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/consent", response_model=ConsentResponse)
async def get_consent(current_user: User = Depends(get_current_user)) -> ConsentResponse:
    return ConsentResponse(
        consent_ai_processing=current_user.consent_ai_processing,
        consent_retention_at=(
            current_user.consent_retention_at.isoformat()
            if current_user.consent_retention_at
            else None
        ),
    )


@router.patch("/me/consent", response_model=ConsentResponse)
async def update_consent(
    data: ConsentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsentResponse:
    user = await UserService.update_consent(db, current_user, data)
    return ConsentResponse(
        consent_ai_processing=user.consent_ai_processing,
        consent_retention_at=(
            user.consent_retention_at.isoformat() if user.consent_retention_at else None
        ),
    )


@router.delete("/me", status_code=204)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await UserService.delete_account(db, current_user)
