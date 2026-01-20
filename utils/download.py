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

# --- ENG KUCHLI SOZLAMALAR ---
COMMON_OPTS = {
    # 1. Cookie fayli (SSH Tunnel orqali olingan)
    'cookiefile': '/app/cookies.txt',
    
    # 2. IPv6 majburiy
    'force_ipv4': False, 
    'force_ipv6': True,

    # 3. Web Client
    'extractor_args': {
        'youtube': {
            'player_client': ['web'],
        }
    },
    
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'nocheckcertificate': True,
    'http_chunk_size': 10485760,
}

async def download_audio(video_id: str, chat_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Music yuklab olish - MP3 (ENG UNIVERSAL USUL)"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    final_path = Path(TMP_DIR) / f"{video_id}.mp3"
    
    if final_path.exists() and final_path.stat().st_size > 0:
        return str(final_path), f"Audio_{video_id}.mp3"

    ydl_opts = {
        **COMMON_OPTS,
        
        # --- "ATOM BOMBASI" FORMATI (Hech qachon xato bermaydi) ---
        # 1. bestaudio: Toza audio qidir.
        # 2. bestvideo+bestaudio: Agar yo'q bo'lsa, video+audio ol.
        # 3. best: Agar u ham bo'lmasa, shunchaki borini ol.
        'format': 'bestaudio/bestvideo+bestaudio/best',
        
        'outtmpl': str(Path(TMP_DIR) / f"{video_id}.%(ext)s"),
        
        # Nima yuklansa ham baribir MP3 ga aylantirib beradi
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    title = "Audio"
    author = "Unknown"

    try:
        logger.info(f"Downloading Audio (Aggressive): {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            if info:
                title = info.get('title', 'Audio')
                author = info.get('uploader', 'Unknown')
            
        clean_title = f"{title} - {author}".replace('/', '-').replace('\\', '-')
        
        # Yakuniy MP3 faylni tekshiramiz
        if final_path.exists() and final_path.stat().st_size > 0:
            return str(final_path), f"{clean_title}.mp3"
            
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        
    return None, None


async def download_video(url: str, chat_id: int) -> Optional[str]:
    """Video yuklab olish"""
    temp_file = None
    try:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        temp_file = Path(TMP_DIR) / f"{url_hash}_{chat_id}.mp4"
        
        if redis_client:
            try:
                cache_key = f"video:{url_hash}"
                cached_path = await redis_client.get(cache_key)
                if cached_path:
                    cached_path_str = cached_path.decode() if isinstance(cached_path, bytes) else cached_path
                    if os.path.exists(cached_path_str):
                        return cached_path_str
            except:
                pass
        
        if is_instagram_url(url):
            result = await download_instagram_direct(url, temp_file)
            if result and os.path.exists(result):
                return result

        # YOUTUBE
        ydl_opts = {
            **COMMON_OPTS,
            # Videoga ham xuddi shunday "borini ol" sharti
            'format': 'best/bestvideo+bestaudio',
            'merge_output_format': 'mp4',
            'outtmpl': str(temp_file).replace('.mp4', '.%(ext)s'),
            'max_filesize': 2 * 1024 * 1024 * 1024,
        }

        logger.info(f"Downloading Video: {url}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])

        downloaded_file = None
        if temp_file.exists():
             downloaded_file = temp_file
        else:
            for file in temp_file.parent.glob(f"{temp_file.stem}.*"):
                if file.exists() and not file.name.endswith('.part'):
                    downloaded_file = file
                    break

        if not downloaded_file:
            return None

        if redis_client:
            try:
                await redis_client.setex(f"video:{url_hash}", 3600, str(downloaded_file).encode())
            except:
                pass
        
        return str(downloaded_file)

    except Exception as e:
        logger.error(f"Video download error: {e}", exc_info=True)
        return None