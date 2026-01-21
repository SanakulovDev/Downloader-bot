import asyncio
import logging
from ytmusicapi import YTMusic
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class YouTubeMusicService:
    def __init__(self):
        """
        YTMusic mijozini ishga tushirish. 
        Headers-siz qidiruv (public) ishlaydi.
        """
        try:
            self.ytmusic = YTMusic()
        except Exception as e:
            logger.error(f"YTMusic init error: {e}")
            self.ytmusic = None

    async def search_track(self, query: str) -> Optional[Dict]:
        """
        Qo'shiqni qidirish va eng mos keladigan natijani qaytarish.
        Sinxron kodni asinxron threadga o'tkazamiz.
        """
        if not self.ytmusic:
            return None

        try:
            # 'songs' filtri videolarni emas, audio treklarni qidirishni ta'minlaydi
            search_results = await asyncio.to_thread(
                self.ytmusic.search, query, filter="songs"
            )

            if not search_results:
                logger.warning(f"No YTMusic results for query: {query}")
                return None

            # Birinchi natija odatda eng to'g'risi bo'ladi
            track = search_results[0]
            
            # Kerakli ma'lumotlarni yig'amiz
            return {
                "video_id": track.get('videoId'),
                "title": track.get('title'),
                "artist": ", ".join([a['name'] for a in track.get('artists', [])]),
                "duration": track.get('duration', '0:00'),
                "thumbnail": track.get('thumbnails', [{}])[-1].get('url') if track.get('thumbnails') else None
            }
        except Exception as e:
            logger.error(f"YTMusic search error for '{query}': {e}")
            return None

    async def search_songs(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Qo'shiqni qidirish (massiv qaytaradi)
        """
        if not self.ytmusic:
            return []

        try:
            # 'songs' filtri videolarni emas, audio treklarni qidirishni ta'minlaydi
            search_results = await asyncio.to_thread(
                self.ytmusic.search, query, filter="songs", limit=limit
            )

            if not search_results:
                logger.warning(f"No YTMusic results for query: {query}")
                return []

            results = []
            for track in search_results:
                if 'videoId' not in track:
                    continue
                    
                # Parse duration (e.g., "3:45" or "1:20:30")
                duration = track.get('duration', '0:00')
                duration_seconds = 0
                try:
                    parts = list(map(int, duration.split(':')))
                    if len(parts) == 2:
                        duration_seconds = parts[0] * 60 + parts[1]
                    elif len(parts) == 3:
                        duration_seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
                except:
                    pass

                results.append({
                    "id": track.get('videoId'),
                    "title": track.get('title'),
                    "artist": ", ".join([a['name'] for a in track.get('artists', [])]),
                    "album": track.get('album', {}).get('name') if track.get('album') else None,
                    "duration": duration_seconds,
                    "thumbnail": track.get('thumbnails', [{}])[-1].get('url') if track.get('thumbnails') else None
                })
            
            return results

        except Exception as e:
            logger.error(f"YTMusic search error for '{query}': {e}")
            return []

    async def get_track_info(self, video_id: str) -> Optional[Dict]:
        """Video ID orqali trek haqida batafsil ma'lumot olish"""
        try:
            track = await asyncio.to_thread(self.ytmusic.get_song, video_id)
            return track
        except Exception as e:
            logger.error(f"YTMusic get_song error: {e}")
            return None

# Singleton obyekt yaratish
yt_music_service = YouTubeMusicService()