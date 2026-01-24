from celery import Celery
from core.config import get_settings

settings = get_settings()
broker_url = settings.celery_broker_url or f"redis://{settings.redis_host}:{settings.redis_port}/0"
result_backend = settings.celery_result_backend or broker_url

celery_app = Celery(
    'downloader_bot',
    broker=broker_url,
    backend=result_backend,
    include=['tasks.bot_tasks']
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
    worker_prefetch_multiplier=2,
    task_acks_late=True,
)
