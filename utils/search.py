import yt_dlp
import asyncio
import json
import logging
import os
from loader import redis_client

logger = logging.getLogger(__name__)

async def search_music(query: str):
    from loader import redis_client
    from utils.yt_music import yt_music_service
    
    # 1. Check Cache
    cache_key = f"search:music:v3:{query.lower().strip()}" # Changed key prefix to separate from old video search if needed, or keep same. Let's use new key to avoid conflicts.
    try:
        if redis_client:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached results for '{query}'")
                return json.loads(cached_data)
    except Exception as e:
        logger.error(f"Redis cache error: {e}")

    try:
        # Search via YTMusic
        results = await yt_music_service.search_songs(query, limit=20)
        
        final_results = []
        for r in results:
            # Format title as "Title - Artist" for better visibility in buttons
            display_title = f"{r['title']} - {r['artist']}"
            
            final_results.append({
                'id': r['id'],
                'title': display_title,
                'duration': r['duration'],
                'channel': r['artist']
            })
            
        if final_results and redis_client:
            try:
                # Cache for 24 hours
                await redis_client.setex(cache_key, 86400, json.dumps(final_results))
            except Exception as e:
                logger.error(f"Redis save error: {e}")
                
        return final_results

    except Exception as e:
        logger.error(f"Search error for '{query}': {e}", exc_info=True)
    return []
