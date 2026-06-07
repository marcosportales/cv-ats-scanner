from fastapi import Response

from app.config import settings

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


def _base_cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **_base_cookie_kwargs(),
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        **_base_cookie_kwargs(),
    )


def clear_auth_cookies(response: Response) -> None:
    kwargs = _base_cookie_kwargs()
    response.delete_cookie(ACCESS_TOKEN_COOKIE, **kwargs)
    response.delete_cookie(REFRESH_TOKEN_COOKIE, **kwargs)
