from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings


async def dispatch_task(
    task: Callable[[str], Any],
    entity_id: str,
    db: AsyncSession,
    entity: Any,
) -> None:
    """Run Celery task inline when SYNC_TASKS=true, else enqueue for worker."""
    if settings.sync_tasks:
        task(entity_id)
        await db.refresh(entity)
    else:
        task.delay(entity_id)
