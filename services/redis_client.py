import os

import redis
from core.env import load_env

load_env()


def get_sync_redis() -> redis.Redis | None:
    host = os.getenv('REDIS_HOST', 'localhost')
    port = int(os.getenv('REDIS_PORT', '6379'))
    try:
        client = redis.Redis(host=host, port=port, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception:
        return None
