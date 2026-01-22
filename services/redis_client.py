import redis
from core.config import get_settings


def get_sync_redis() -> redis.Redis | None:
    settings = get_settings()
    host = settings.redis_host
    port = settings.redis_port
    try:
        client = redis.Redis(host=host, port=port, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception:
        return None
