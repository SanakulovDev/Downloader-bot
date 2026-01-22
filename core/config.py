from dataclasses import dataclass
import os

from core.env import load_env

load_env()


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    redis_host: str = os.getenv('REDIS_HOST', 'localhost')
    redis_port: int = int(os.getenv('REDIS_PORT', '6379'))
    tmp_dir: str = os.getenv('TMP_DIR', '/dev/shm/tmp')
    telegram_nickname: str = os.getenv('TELEGRAM_NICKNAME', '@InstantAudioBot')
    idempotency_ttl_seconds: int = int(os.getenv('IDEMPOTENCY_TTL_SECONDS', '900'))
    artist_cache_ttl_seconds: int = int(os.getenv('ARTIST_CACHE_TTL_SECONDS', '3600'))
    celery_broker_url: str = os.getenv('CELERY_BROKER_URL', '')
    celery_result_backend: str = os.getenv('CELERY_RESULT_BACKEND', '')


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
