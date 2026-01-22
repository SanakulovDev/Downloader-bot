import os

from core.env import load_env
from services.redis_client import get_sync_redis

load_env()

IDEMPOTENCY_TTL_SECONDS = int(os.getenv('IDEMPOTENCY_TTL_SECONDS', '900'))


def acquire_lock(key: str) -> bool:
    client = get_sync_redis()
    if not client:
        return True
    try:
        return bool(client.set(key, "1", nx=True, ex=IDEMPOTENCY_TTL_SECONDS))
    except Exception:
        return True


def release_lock(key: str) -> None:
    client = get_sync_redis()
    if not client:
        return
    try:
        client.delete(key)
    except Exception:
        pass
