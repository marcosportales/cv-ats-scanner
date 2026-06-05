from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse


class AuthService:
    @staticmethod
    async def register(db: AsyncSession, data: UserCreate) -> UserResponse:
        existing = await db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise ConflictError("Email already registered")

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return UserResponse.model_validate(user)

    @staticmethod
    async def login(db: AsyncSession, data: UserLogin) -> TokenResponse:
        result = await db.execute(
            select(User).where(
                User.email == data.email,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if user is None or not verify_password(data.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
        )

    @staticmethod
    async def refresh(refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token, expected_type="refresh")
        user_id = payload["sub"]

        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
        )
