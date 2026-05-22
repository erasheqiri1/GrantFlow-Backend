from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "grantflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.email", "app.tasks.ai_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Tirane",
    enable_utc=True,
    broker_connection_retry_on_startup=False,
)
