import asyncio
import os
import hashlib
import logging
from pathlib import Path
from typing import Tuple, Optional
import yt_dlp
from instagram_downloader import download_instagram_direct
from loader import TMP_DIR, redis_client
from utils.validation import is_instagram_url, is_youtube_url

logger = logging.getLogger(__name__)

# --- YANGILANGAN SOZLAMALAR (IPv6) ---
COMMON_OPTS = {
    # 1. Cookies faylni QAYTARAMIZ
    # (Login qilingan sessiya baribir ishonchliroq)
    'cookiefile': '/app/cookies.txt',
    
    # 2. IPv6 ni majburlash (IP blokni aylanib o'tish uchun)
    'force_ipv4': False, 
    'force_ipv6': True,

    # 3. iOS Mijozi (Androiddan ko'ra ishonchliroq)
    'extractor_args': {
        'youtube': {
            'player_client': ['ios'],
        }
    },
    
    # 4. OAuth ni O'CHIRAMIZ (Chunki u xato beryapti)
    # 'username': 'oauth2', <-- KERAK EMAS
    # 'password': '',       <-- KERAK EMAS
    
    # Qo'shimcha
    'nocheckcertificate': True,
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'http_chunk_size': 10485760,
}
# -------------------------------------

async def download_audio(video_id: str, chat_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Music yuklab olish - MP3"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    final_path = Path(TMP_DIR) / f"{video_id}.mp3"
    
    if final_path.exists() and final_path.stat().st_size > 0:
        return str(final_path), f"Audio_{video_id}.mp3"

    ydl_opts = {
        **COMMON_OPTS, # Yuqoridagi IPv6 sozlamalarini qo'shadi
        'format': 'bestaudio/best',
        'outtmpl': str(Path(TMP_DIR) / f"{video_id}.%(ext)s"),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    title = "Audio"
    author = "Unknown"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            if info:
                title = info.get('title', 'Audio')
                author = info.get('uploader', 'Unknown')
            
        clean_title = f"{title} - {author}".replace('/', '-').replace('\\', '-')
        
        if final_path.exists() and final_path.stat().st_size > 0:
            return str(final_path), f"{clean_title}.mp3"
            
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        
    return None, None


async def download_video(url: str, chat_id: int) -> Optional[str]:
    """Video yuklab olish (IPv6 bilan)"""
    temp_file = None
    try:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        temp_file = Path(TMP_DIR) / f"{url_hash}_{chat_id}.mp4"
        
        # Redis cache...
        if redis_client:
            try:
                cache_key = f"video:{url_hash}"
                cached_path = await redis_client.get(cache_key)
                if cached_path:
                    cached_path_str = cached_path.decode() if isinstance(cached_path, bytes) else cached_path
                    if os.path.exists(cached_path_str):
                        logger.info(f"Using cached video: {cached_path_str}")
                        import shutil
                        shutil.copy2(cached_path_str, temp_file)
                        return str(temp_file)
            except:
                pass
        
        # Instagram check...
        if is_instagram_url(url):
            result = await download_instagram_direct(url, temp_file)
            if result and os.path.exists(result):
                return result

        # YOUTUBE yuklash
        ydl_opts = {
            **COMMON_OPTS, # IPv6 settings
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(temp_file).replace('.mp4', '.%(ext)s'),
            'merge_output_format': 'mp4',
            'max_filesize': 2 * 1024 * 1024 * 1024,
        }

        logger.info(f"Downloading {url} via IPv6...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])

        # Faylni topish
        downloaded_file = None
        for file in temp_file.parent.glob(f"{temp_file.stem}.*"):
            if file.suffix in ['.mp4', '.webm', '.mkv'] and file.exists():
                if not file.name.endswith('.part'):
                    downloaded_file = file
                    break
        
        if not downloaded_file and temp_file.exists():
            downloaded_file = temp_file

        if not downloaded_file:
            return None

        # Check size limit
        if downloaded_file.stat().st_size > 2 * 1024 * 1024 * 1024:
            downloaded_file.unlink()
            raise ValueError("FILE_TOO_LARGE")

        # Save to Redis
        if redis_client:
            try:
                await redis_client.setex(f"video:{url_hash}", 3600, str(downloaded_file).encode())
            except:
                pass
        
        return str(downloaded_file)

    except Exception as e:
        logger.error(f"Video download error: {e}", exc_info=True)
        return None