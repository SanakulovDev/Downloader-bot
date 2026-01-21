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

# --- FIX: LIST FORMAT FOR REMOTE COMPONENTS ---
COMMON_OPTS = {
    # 1. Cookie fayli
    'cookiefile': '/app/cookies.txt',
    
    # 2. IPv6
    'force_ipv4': False, 
    'force_ipv6': True,

    # 3. MIJOZ: WEB
    'extractor_args': {
        'youtube': {
            'player_client': ['web'],
        }
    },
    
    # 4. REMOTE COMPONENTS (TUZATILDI: LIST FORMATI)
    # Oldingi xato: {'ejs': 'github'} (Dict)
    # To'g'ri variant: ['ejs:github'] (List)
    'remote_components': ['ejs:github'],

    # 5. User Agent
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',

    'quiet': True,
    'no_warnings': True,
    'ignoreerrors': True,
    'nocheckcertificate': True,
    'http_chunk_size': 10485760,
}

async def download_audio(video_id: str, chat_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Music yuklab olish - MP3"""
    url = f"https://www.youtube.com/watch?v={video_id}"
    # Oldingi .mp3 tekshiruvini olib tashlaymiz
    # final_path = Path(TMP_DIR) / f"{video_id}.mp3" 
    
    # 1. Keshni (hozircha mp3 ga) tekshirish (agar oldin yuklangan bo'lsa)
    # Agar biz dinamik formatga o'tsak, keshlash mantig'ini ham o'zgartirish kerak.
    # Hozircha oddiy qoldiramiz: Har doim yangisini yuklayversin yoki faylni qidirsin.

    ydl_opts = {
        **COMMON_OPTS,
        # 'bestaudio[ext=m4a]' -> M4A ni majburlash (Telegram uchun eng yaxshisi)
        # Agar bo'lmasa oddiy bestaudio
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        
        'outtmpl': str(Path(TMP_DIR) / f"{video_id}.%(ext)s"),
        
        # Postprocessor (FFmpeg) O'CHIRILDI -> Tezlik 10x oshadi
    }

    title = "Audio"
    author = "Unknown"

    try:
        logger.info(f"Downloading Audio (Fast Mode): {url}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            if info:
                title = info.get('title', 'Audio')
                author = info.get('uploader', 'Unknown')
            
        clean_title = f"{title} - {author}".replace('/', '-').replace('\\', '-')
        
        # Faylni qidiramiz (chunki u .m4a, .webm va hokazo bo'lishi mumkin)
        # video_id.* bo'yicha glob qilamiz
        downloaded_file = None
        for file in Path(TMP_DIR).glob(f"{video_id}.*"):
            if file.is_file() and not file.name.endswith('.part'):
                downloaded_file = file
                break
        
        if downloaded_file:
            return str(downloaded_file), f"{clean_title}{downloaded_file.suffix}"
            
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
            'format': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
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