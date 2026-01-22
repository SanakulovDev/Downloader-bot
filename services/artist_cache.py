from core.config import get_settings
from services.redis_client import get_sync_redis


def cache_artist_name(video_id: str, artist_name: str) -> None:
    if not artist_name:
        return
    client = get_sync_redis()
    if not client:
        return
    try:
        ttl = get_settings().artist_cache_ttl_seconds
        client.setex(f"artist:{video_id}", ttl, artist_name)
    except Exception:
        pass
