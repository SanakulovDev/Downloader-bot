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

async def download_audio(video_id: str, chat_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Music yuklab olish - filename va speed fix"""
    
    # 1. Info olish (nomini bilish uchun)
    title = "Audio"
    author = "Unknown"
    
    try:
        ydl_opts_info = {'quiet': True, 'noplaylist': True}
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            title = info.get('title', 'Audio')
            author = info.get('uploader', 'Unknown')
    except:
        pass

    # Clean filename
    clean_title = f"{title} - {author}".replace('/', '-').replace('\\', '-')
    
    temp_file = Path(TMP_DIR) / f"{video_id}.m4a"
    
    # Cache check
    if temp_file.exists() and temp_file.stat().st_size > 0:
        return str(temp_file), f"{clean_title}.m4a"

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio',
        'outtmpl': str(temp_file),
        'quiet': True,
        # 'cookiefile': '/app/app/cookies.txt',
        'no_warnings': True,
        # Speed optimizations
        'concurrent_fragment_downloads': 5,
        'http_chunk_size': 10485760, # 10MB
        'username': os.getenv('YT_USERNAME', 'oauth2'), 
    'password': os.getenv('YT_PASSWORD', ''),
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
            
        if temp_file.exists() and temp_file.stat().st_size > 0:
            return str(temp_file), f"{clean_title}.m4a"
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        
    return None, None


async def download_video(url: str, chat_id: int) -> Optional[str]:
    """
    Video ni yuklab olish - async va tez
    Professional optimizatsiya bilan
    """
    from loader import redis_client # Deferred import

    temp_file = None
    try:
        # URL hash (cache uchun)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        temp_file = Path(TMP_DIR) / f"{url_hash}_{chat_id}.mp4"
        
        # Redis cache tekshirish (bir URL bir marta yuklab olish)
        if redis_client:
            try:
                cache_key = f"video:{url_hash}"
                cached_path = await redis_client.get(cache_key)
                if cached_path:
                    cached_path_str = cached_path.decode() if isinstance(cached_path, bytes) else cached_path
                    if os.path.exists(cached_path_str):
                        logger.info(f"Using cached video: {cached_path_str}")
                        # Cached faylni nusxalash
                        import shutil
                        shutil.copy2(cached_path_str, temp_file)
                        return str(temp_file)
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")
        
        # Platformani aniqlash
        format_selector = None
        
        if is_instagram_url(url):
            # Instagram uchun direct JSON API (20x tezroq)
            result = await download_instagram_direct(url, temp_file)
            if result and os.path.exists(result):
                # Cache ga saqlash
                if redis_client:
                    try:
                        await redis_client.setex(f"video:{url_hash}", 3600, result.encode())  # 1 soat
                    except:
                        pass
                return result
            # Agar direct download ishlamasa, yt-dlp ga o'tamiz
            format_selector = 'best'
        elif is_youtube_url(url):
            # YouTube uchun (ffmpeg bor, shuning uchun maksimal sifat, lekin H264 compatibilty)
            # bestvideo[ext=mp4][vcodec^=avc] -> H.264 formatini tanlash (qora ekran bo'lmasligi uchun)
            format_selector = 'bestvideo[height<=480][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]'
        else:
            return None
        
        if not format_selector:
            return None
        
        # yt-dlp options - FIXED FOR NO FFMPEG/ARIA2C
        ydl_opts = {
            'format': format_selector,
            'outtmpl': str(temp_file).replace('.mp4', '.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extract_flat': False,
            # Document sifatida yuboriladi, shuning uchun 2GB limit
            'max_filesize': 2 * 1024 * 1024 * 1024,  # 2GB
            'merge_output_format': 'mp4', # Ensure merged output is mp4
        }

        # Download qilish
        logger.info(f"Downloading {url} to {temp_file}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])

        # Fayl mavjudligini tekshirish (ext o'zgarishi mumkin)
        downloaded_file = None
        
        # Avval barcha mumkin bo'lgan fayllarni tekshiramiz
        for file in temp_file.parent.glob(f"{temp_file.stem}.*"):
            if file.suffix in ['.mp4', '.webm', '.mkv'] and file.exists():
                # .part fayllarni o'tkazib yuboramiz
                if not file.name.endswith('.part'):
                    downloaded_file = file
                    logger.info(f"Found downloaded file: {downloaded_file}")
                    break
        
        # Agar fayl topilmasa, temp_file ni tekshiramiz
        if not downloaded_file and temp_file.exists():
            downloaded_file = temp_file
            logger.info(f"Using temp_file: {downloaded_file}")
        
        if not downloaded_file or not downloaded_file.exists():
            logger.error(f"Downloaded file not found. Searched for: {temp_file}")
            return None

        # Fayl hajmini tekshirish
        file_size = downloaded_file.stat().st_size
        if file_size == 0:
            logger.error(f"Downloaded file is empty: {downloaded_file}")
            downloaded_file.unlink()
            return None
        
        # Fayl hajmini MB da hisoblash
        file_size_mb = file_size / (1024 * 1024)
        
        # Document sifatida yuboriladi, shuning uchun 2GB limit (Telegram limiti)
        telegram_max_size = 2 * 1024 * 1024 * 1024  # 2GB
            
        if file_size > telegram_max_size:
            logger.warning(f"File too large: {file_size_mb:.2f}MB (Telegram limit: 2GB)")
            downloaded_file.unlink()
            # Maxsus xatolik kodi qaytarish
            raise ValueError(f"FILE_TOO_LARGE:{file_size_mb:.1f}MB")

        logger.info(f"Successfully downloaded: {downloaded_file} ({file_size_mb:.2f}MB)")
        
        # Cache ga saqlash (bir URL bir marta yuklab olish)
        if redis_client:
            try:
                await redis_client.setex(f"video:{url_hash}", 3600, str(downloaded_file).encode())  # 1 soat
            except:
                pass
        
        return str(downloaded_file)

    except ValueError as e:
        # Fayl hajmi uchun maxsus xatolik
        error_msg = str(e)
        if error_msg.startswith("FILE_TOO_LARGE:"):
            size = error_msg.split(":")[1]
            logger.warning(f"File too large: {size}")
            raise ValueError(f"FILE_TOO_LARGE:{size}")
        raise
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp Download error: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        return None
