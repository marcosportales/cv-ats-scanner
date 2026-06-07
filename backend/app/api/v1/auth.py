from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.cookies import (
    REFRESH_TOKEN_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
)
from app.core.exceptions import UnauthorizedError
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    AuthSuccessResponse,
    RefreshTokenRequest,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)) -> UserResponse:
    return await AuthService.register(db, data)


@router.post("/login", response_model=AuthSuccessResponse)
async def login(
    data: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSuccessResponse:
    tokens = await AuthService.login(db, data)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return AuthSuccessResponse()


@router.post("/refresh", response_model=AuthSuccessResponse)
async def refresh_token(
    response: Response,
    refresh_token_cookie: Annotated[str | None, Cookie(alias=REFRESH_TOKEN_COOKIE)] = None,
    data: RefreshTokenRequest | None = None,
) -> AuthSuccessResponse:
    refresh_token = refresh_token_cookie or (data.refresh_token if data else None)
    if not refresh_token:
        raise UnauthorizedError()

    tokens = await AuthService.refresh(refresh_token)
    set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return AuthSuccessResponse()


@router.post("/logout", response_model=AuthSuccessResponse)
async def logout(response: Response) -> AuthSuccessResponse:
    clear_auth_cookies(response)
    return AuthSuccessResponse(authenticated=False)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
