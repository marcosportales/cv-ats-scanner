import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.user import User
from app.main import app
from app.core.security import hash_password

TEST_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

SAMPLE_JOB_TEXT = """
Senior Backend Developer at TechCo.
Requirements: Python, FastAPI, PostgreSQL, Docker, 5 years experience.
Nice to have: Kubernetes, Redis, Celery.
Responsibilities: Design microservices and mentor juniors.
Remote hybrid Madrid.
"""


@pytest.fixture
async def client_with_user(db_session):
    from app.db.session import get_db
    from app.api.deps import get_current_user

    user = User(
        email="api@test.com",
        password_hash=hash_password("securepass123"),
        full_name="API Test",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    async def override_get_db():
        yield db_session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, user

    app.dependency_overrides.clear()


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_job(client_with_user):
    client, _user = client_with_user
    response = await client.post(
        "/api/v1/jobs",
        json={"title": "Backend Dev", "raw_text": " " * 20 + SAMPLE_JOB_TEXT},
    )
    assert response.status_code == 201
    assert response.json()["parse_status"] in ("queued", "processing", "completed")
