import yt_dlp
import asyncio
import json
import logging
import os
from loader import redis_client

logger = logging.getLogger(__name__)

async def search_music(query: str):
    from loader import redis_client # Deferred import to avoid circular dependency issues if any, but loader is safe
    
    # 1. Check Cache
    cache_key = f"search:{query.lower().strip()}"
    try:
        if redis_client:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached results for '{query}'")
                return json.loads(cached_data)
    except Exception as e:
        logger.error(f"Redis cache error: {e}")

    ydl_opts = {
        'quiet': True,
        # 'cookiefile': '/app/app/cookies.txt',
        'extract_flat': 'in_playlist', # Only extract flat for playlists
        'noplaylist': True,
    }
    
    try:
        # Increase limit to 20 to ensure we have enough after filtering
        search_query = f"ytsearch20:{query}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, search_query, download=False)
            if 'entries' in info:
                entries = list(info['entries'])
                logger.info(f"Search found {len(entries)} results for '{query}'")
                
                results = []
                for entry in entries:
                    if entry is None:
                        continue
                        
                    duration = entry.get('duration') or 0
                    # Filter: 1 min (60s) <= duration <= 5 min (300s)
                    if 60 <= duration <= 300:
                        results.append({
                            'id': entry['id'],
                            'title': entry['title'],
                            'duration': duration,
                            'channel': entry.get('uploader', 'Unknown')
                        })
                
                # 2. Save to Cache
                if results and redis_client:
                    try:
                        # Cache for 24 hours (86400 seconds)
                        await redis_client.setex(cache_key, 86400, json.dumps(results))
                    except Exception as e:
                        logger.error(f"Redis save error: {e}")
                
                return results
            else:
                logger.warning(f"No entries in search result for '{query}': {info.keys()}")
    except Exception as e:
        logger.error(f"Search error for '{query}': {e}", exc_info=True)
    return []
