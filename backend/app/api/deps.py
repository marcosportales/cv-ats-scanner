from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_db

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError()

    payload = decode_token(credentials.credentials, expected_type="access")
    user_id = UUID(payload["sub"])

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedError()

    return user
