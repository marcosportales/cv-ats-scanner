from celery import Celery

from app.config import settings

celery_app = Celery(
    "cv_ats_scanner",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    task_routes={
        "app.workers.tasks.*": {"queue": "default"},
    },
    task_always_eager=settings.sync_tasks,
    task_eager_propagates=settings.sync_tasks,
)

celery_app.autodiscover_tasks(["app.workers.tasks"])
