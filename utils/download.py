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

# Umumiy sozlamalar (Audio va Video uchun ham kerak)
COMMON_OPTS = {
    'cookiefile': '/app/cookies.txt',  # Docker ichidagi manzil
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'], # Bloklarni aylanib o'tish kaliti
        }
    },
    'nocheckcertificate': True,
    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'http_chunk_size': 10485760, # 10MB chunk
}

async def download_audio(video_id: str, chat_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Music yuklab olish - MP3 formatda"""
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    temp_filename = f"{video_id}" # Kengaytmani yt-dlp o'zi qo'shadi
    
    # Biz kutyapmizki, yakuniy fayl .mp3 bo'ladi
    final_path = Path(TMP_DIR) / f"{video_id}.mp3"
    
    # 1. Cache tekshirish
    if final_path.exists() and final_path.stat().st_size > 0:
        return str(final_path), f"Audio_{video_id}.mp3"

    # 2. Sozlamalar
    ydl_opts = {
        **COMMON_OPTS, # Yuqoridagi umumiy sozlamalarni qo'shamiz
        'format': 'bestaudio/best',
        'outtmpl': str(Path(TMP_DIR) / f"{video_id}.%(ext)s"),
        
        # MP3 ga aylantirish
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    title = "Audio"
    author = "Unknown"

    try:
        # Info va Download bitta joyda (bloklanishni kamaytirish uchun)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            if info:
                title = info.get('title', 'Audio')
                author = info.get('uploader', 'Unknown')
            
        # Fayl nomini chiroyli qilish
        clean_title = f"{title} - {author}".replace('/', '-').replace('\\', '-')
        
        # Tekshirish
        if final_path.exists() and final_path.stat().st_size > 0:
            return str(final_path), f"{clean_title}.mp3"
            
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        
    return None, None


async def download_video(url: str, chat_id: int) -> Optional[str]:
    """Video yuklab olish (YouTube + Android Client fix)"""
    
    temp_file = None
    try:
        # URL hash (cache uchun)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        temp_file = Path(TMP_DIR) / f"{url_hash}_{chat_id}.mp4"
        
        # 1. Redis cache tekshirish
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
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")
        
        # 2. Instagram (alohida mantiq)
        if is_instagram_url(url):
            result = await download_instagram_direct(url, temp_file)
            if result and os.path.exists(result):
                return result
            # Agar direct o'xshamasa, pastda yt-dlp ga tushadi

        # 3. YouTube va boshqalar uchun yt-dlp sozlamalari
        ydl_opts = {
            **COMMON_OPTS, # Cookie va Android client shu yerda!
            
            # Format: MP4 bo'lsin, H264 kodek (Telegram o'qishi uchun), 
            # 1080p yoki 720p gacha (juda katta bo'lmasligi uchun)
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            
            'outtmpl': str(temp_file).replace('.mp4', '.%(ext)s'),
            'merge_output_format': 'mp4',
            'max_filesize': 2 * 1024 * 1024 * 1024,  # 2GB limit
        }

        # Download
        logger.info(f"Downloading {url}...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])

        # Faylni qidirish (chunki yt-dlp ba'zan formatni o'zgartiradi)
        downloaded_file = None
        for file in temp_file.parent.glob(f"{temp_file.stem}.*"):
            if file.suffix in ['.mp4', '.webm', '.mkv'] and file.exists():
                if not file.name.endswith('.part'):
                    downloaded_file = file
                    break
        
        if not downloaded_file:
            # Agar topilmasa, temp_file o'zini tekshiramiz
            if temp_file.exists():
                downloaded_file = temp_file
            else:
                logger.error("Video fayl topilmadi!")
                return None

        # Hajm tekshiruvi
        file_size = downloaded_file.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size > 2 * 1024 * 1024 * 1024: # 2GB
            logger.warning(f"File too large: {file_size_mb:.2f}MB")
            downloaded_file.unlink()
            raise ValueError(f"FILE_TOO_LARGE:{file_size_mb:.1f}MB")

        logger.info(f"Success: {downloaded_file} ({file_size_mb:.2f}MB)")
        
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