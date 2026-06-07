import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.cookies import ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE
from app.db.base import Base
from app.main import app

TEST_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session):
    from app.db.session import get_db

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_register_and_login(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "securepass123",
            "full_name": "Test User",
        },
    )
    assert register_response.status_code == 201
    user = register_response.json()
    assert user["email"] == "test@example.com"
    assert user["full_name"] == "Test User"
    assert "id" in user

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    assert login_response.status_code == 200
    assert login_response.json() == {"authenticated": True}
    assert ACCESS_TOKEN_COOKIE in login_response.cookies
    assert REFRESH_TOKEN_COOKIE in login_response.cookies

    me_response = await client.get(
        "/api/v1/auth/me",
        cookies=login_response.cookies,
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_refresh_with_cookie(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@example.com", "password": "securepass123"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "securepass123"},
    )
    assert login_response.status_code == 200

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        cookies=login_response.cookies,
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json() == {"authenticated": True}
    assert ACCESS_TOKEN_COOKIE in refresh_response.cookies


@pytest.mark.asyncio
async def test_logout_clears_cookies(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "logout@example.com", "password": "securepass123"},
    )
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "securepass123"},
    )

    logout_response = await client.post(
        "/api/v1/auth/logout",
        cookies=login_response.cookies,
    )
    assert logout_response.status_code == 200
    assert logout_response.json() == {"authenticated": False}

    me_response = await client.get("/api/v1/auth/me")
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "securepass123",
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
