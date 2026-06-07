from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import ACCESS_TOKEN_COOKIE
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.db.models.user import User
from app.db.session import get_db

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    access_token_cookie: Annotated[str | None, Cookie(alias=ACCESS_TOKEN_COOKIE)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = access_token_cookie or (credentials.credentials if credentials else None)
    if token is None:
        raise UnauthorizedError()

    payload = decode_token(token, expected_type="access")
    user_id = UUID(payload["sub"])

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True), User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedError()

    return user
