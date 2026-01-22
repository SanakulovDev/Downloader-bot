from core.config import get_settings
from services.redis_client import get_sync_redis


def acquire_lock(key: str) -> bool:
    client = get_sync_redis()
    if not client:
        return True
    try:
        ttl = get_settings().idempotency_ttl_seconds
        return bool(client.set(key, "1", nx=True, ex=ttl))
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
