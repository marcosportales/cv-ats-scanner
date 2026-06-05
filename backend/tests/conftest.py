import os
from pathlib import Path

_test_db = Path(__file__).resolve().parent / ".pytest.db"
if _test_db.exists():
    _test_db.unlink()

os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_test_db}")
os.environ.setdefault("SYNC_TASKS", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-32chars")


def pytest_sessionstart(session):
    from app.db.base import Base
    from app.db.sync_session import sync_engine

    Base.metadata.create_all(sync_engine)
