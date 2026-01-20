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

# --- SOZLAMALAR ---
COMMON_OPTS = {
    # 1. Siz olgan "oltin" cookie fayli
    'cookiefile': '/app/cookies.txt',
    
    # 2. IPv6 (SSH tunnelda ham IPv6 ishlatgan bo'lsangiz kerak, bu turaversin)
    'force_ipv4': False, 
    'force_ipv6': True,

    # 3. Web Client (Cookie bilan shu eng yaxshi ishlaydi)
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
    """Music yuklab olish - MP3"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    final_path = Path(TMP_DIR) / f"{video_id}.mp3"
    
    if final_path.exists() and final_path.stat().st_size > 0:
        return str(final_path), f"Audio_{video_id}.mp3"

    ydl_opts = {
        **COMMON_OPTS,
        # O'ZGARISH: [ext=m4a] ni olib tashladik. Borini oladi.
        'format': 'bestaudio/best',
        'outtmpl': str(Path(TMP_DIR) / f"{video_id}.%(ext)s"),
        
        # FFmpeg baribir buni MP3 qiladi
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
    """Video yuklab olish (Universal Format)"""
    temp_file = None
    try:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        temp_file = Path(TMP_DIR) / f"{url_hash}_{chat_id}.mp4"
        
        # Redis cache
        if redis_client:
            try:
                cache_key = f"video:{url_hash}"
                cached_path = await redis_client.get(cache_key)
                if cached_path and os.path.exists(cached_path.decode()):
                    return cached_path.decode()
            except:
                pass
        
        # Instagram
        if is_instagram_url(url):
            result = await download_instagram_direct(url, temp_file)
            if result and os.path.exists(result):
                return result

        # YOUTUBE
        ydl_opts = {
            **COMMON_OPTS,
            
            # --- O'ZGARISH (MUHIM) ---
            # Biz "ext=mp4" deb cheklamaymiz. Webm kelsa ham olaveramiz.
            # 'merge_output_format': 'mp4' buyrug'i yakuniy faylni MP4 qilib beradi.
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'merge_output_format': 'mp4',
            
            'outtmpl': str(temp_file).replace('.mp4', '.%(ext)s'),
            'max_filesize': 2 * 1024 * 1024 * 1024,
        }

        logger.info(f"Downloading {url}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])

        # Faylni topish (mp4 bo'lishi shart emas, lekin merge_output_format mp4 qiladi)
        downloaded_file = None
        # Avval aynan biz kutgan nomni tekshiramiz
        if temp_file.exists():
             downloaded_file = temp_file
        else:
            # Agar topilmasa, atrofni qidiramiz
            for file in temp_file.parent.glob(f"{temp_file.stem}.*"):
                if file.exists() and not file.name.endswith('.part'):
                    downloaded_file = file
                    break

        if not downloaded_file:
            return None

        # Redisga saqlash
        if redis_client:
            try:
                await redis_client.setex(f"video:{url_hash}", 3600, str(downloaded_file).encode())
            except:
                pass
        
        return str(downloaded_file)

    except Exception as e:
        logger.error(f"Video download error: {e}", exc_info=True)
        return None