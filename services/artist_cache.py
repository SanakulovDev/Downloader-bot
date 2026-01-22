import os

from core.env import load_env
from services.redis_client import get_sync_redis

load_env()

ARTIST_CACHE_TTL_SECONDS = int(os.getenv('ARTIST_CACHE_TTL_SECONDS', '3600'))


def cache_artist_name(video_id: str, artist_name: str) -> None:
    if not artist_name:
        return
    client = get_sync_redis()
    if not client:
        return
    try:
        client.setex(f"artist:{video_id}", ARTIST_CACHE_TTL_SECONDS, artist_name)
    except Exception:
        pass
