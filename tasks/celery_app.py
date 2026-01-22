import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv('app/.env')

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')

broker_url = os.getenv('CELERY_BROKER_URL', f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
result_backend = os.getenv('CELERY_RESULT_BACKEND', broker_url)

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
    enable_utc=True
)
