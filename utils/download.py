import asyncio
import os
import hashlib
import logging
import time
from pathlib import Path
from typing import Tuple, Optional, Callable, Dict, Any
import yt_dlp
import msgpack
from instagram_downloader import download_instagram_direct
from loader import TMP_DIR, redis_client
from utils.validation import is_instagram_url, is_youtube_url

logger = logging.getLogger(__name__)

# --- CONFIG ---
CACHE_TTL = 1800  # 30 minutes

COMMON_OPTS = {
    'quiet': False,
    'cookiefile': '/app/cookies.txt',
    
    'force_ipv4': True, 
    'force_ipv6': False,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',

    'no_warnings': True,
    'ignoreerrors': False,
    'nocheckcertificate': True,
    
    # Aria2c Configuration
    'external_downloader': 'aria2c',
    'external_downloader_args': [
        '--max-connection-per-server=16',
        '--split=16',
        '--min-split-size=1M',
        '--max-overall-download-limit=0',
        '--file-allocation=none',
        # QUYIDAGI 3 TA QATORNI QO'SHING (Time out va ulanish xatolari uchun)
        '--connect-timeout=60',          # Ulanishni uzoqroq kutish
        '--timeout=60',                  # O'qish timeoutni oshirish
        '--retry-wait=5',                # Xato bo'lsa 5 soniya kutib qayta urunish
        '--stream-piece-selector=random',# YouTube cheklovidan qochish uchun bo'laklarni random tanlash
    ],
    
    # HTTP sozlamalari
    'buffersize': 1024 * 1024,   # 1MB buffer (8GB RAM-da bu juda xavfsiz va tezroq)
    'http_chunk_size': 10485760, # 10MB chunk
    
    'retries': 10,               # Qayta urunishlar sonini oshirdik
    'fragment_retries': 20,      # Fragment xatolarida ko'proq urunish
    'socket_timeout': 30,        # 10 soniya juda kam, YouTube ba'zan kechikadi
}

def _map_download_error(err_msg: str, media_type: str) -> Exception:
    if "larger than" in err_msg or "too large" in err_msg:
        if media_type == "audio":
            return Exception("❌ Audio hajmi juda katta (2GB dan ortiq).")
        return Exception("❌ Video hajmi juda katta (2GB dan ortiq). Telegram orqali yuborib bo'lmaydi.")
    if "video unavailable" in err_msg or "private video" in err_msg:
        if media_type == "audio":
            return Exception("❌ Audio/Video topilmadi yoki o'chirilgan.")
        return Exception("❌ Video topilmadi yoki o'chirilgan (Private).")
    if "sign in" in err_msg or "age-gated" in err_msg:
        if media_type == "audio":
            return Exception("❌ Yosh cheklovi yoki login talab qilinadi.")
        return Exception("❌ Bu video yosh cheklovi (18+) yoki login talab qiladi.")
    if "copyright" in err_msg:
        return Exception("❌ Mualliflik huquqi tufayli yuklab bo'lmadi.")
    if "geo-restricted" in err_msg or "available to" in err_msg:
        if media_type == "audio":
            return Exception("❌ Hududiy cheklov tufayli yuklanmaydi.")
        return Exception("❌ Bu video hududiy cheklov tufayli yuklanmaydi.")
    return Exception(err_msg)


def _find_downloaded_file(search_dir: Path, prefix: str) -> Optional[Path]:
    for file in search_dir.glob(f"{prefix}.*"):
        if file.is_file() and not file.name.endswith('.part'):
            return file
    return None

# --- CACHE UTILS ---

async def get_cached_media(url_hash: str) -> Optional[Dict[str, Any]]:
    """
    Redis'dan keshni o'qish. 
    Key format: media_cache:{bucket_id} -> field: {full_hash}
    Value: MessagePack compressed bytes
    """
    if not redis_client:
        return None
        
    bucket = f"media_cache:{url_hash[:4]}"
    try:
        data = await redis_client.hget(bucket, url_hash)
        if data:
            return msgpack.unpackb(data)
    except Exception as e:
        logger.error(f"Cache get error: {e}")
    return None

async def cache_media_result(url_hash: str, data: Dict[str, Any]):
    """
    Natijani Redis'ga siqilgan holda yozish va TTL ni yangilash.
    """
    if not redis_client:
        return
        
    bucket = f"media_cache:{url_hash[:4]}"
    packed = msgpack.packb(data)
    try:
        await redis_client.hset(bucket, url_hash, packed)
        # Butun bucket uchun TTL yangilanadi (oddiy va samarali)
        await redis_client.expire(bucket, CACHE_TTL)
    except Exception as e:
        logger.error(f"Cache set error: {e}")


async def download_audio(video_id: str, chat_id: int) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Music yuklab olish - MP3/M4A
    Returns: (file_path, filename, file_id)
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    url_hash = hashlib.md5(url.encode()).hexdigest()
    
    # 1. Keshni tekshirish
    cached = await get_cached_media(url_hash)
    if cached:
        cached_path = cached.get('path')
        cached_file_id = cached.get('file_id')
        
        # Agar file_id bo'lsa, fayl shart emas (Telegramdan qayta yuboramiz)
        if cached_file_id:
            logger.info(f"Using cached file_id for audio: {video_id}")
            return None, cached.get('filename', 'audio.m4a'), cached_file_id
            
        # Agar fayl diskda bo'lsa
        if cached_path and os.path.exists(cached_path):
            logger.info(f"Using cached file for audio: {video_id}")
            return cached_path, cached.get('filename', 'audio.m4a'), None

    ydl_opts = {
        **COMMON_OPTS,
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': str(Path(TMP_DIR) / f"{video_id}.%(ext)s"),
    }

    title = "Audio"
    author = "Unknown"

    try:
        logger.info(f"Downloading Audio (Fast Mode): {url}")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                if info:
                    title = info.get('title', 'Audio')
                    author = info.get('uploader', 'Unknown')
        except yt_dlp.utils.DownloadError as e:
            raise _map_download_error(str(e).lower(), "audio")

        clean_title = f"{title} - {author}".replace('/', '-').replace('\\', '-')
        
        downloaded_file = _find_downloaded_file(Path(TMP_DIR), video_id)
        
        if downloaded_file:
            filename = f"{clean_title}{downloaded_file.suffix}"
            
            # Keshga yozib qo'yamiz (hozircha fayl ID yo'q, u yuborilgandan keyin queue_worker'da qo'shilishi mumkin, 
            # yoki shunchaki path ni saqlaymiz)
            # Lekin eng muhimi queue_worker da update qilish.
            return str(downloaded_file), filename, None
            
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        raise e 
        
    return None, None, None


async def download_video(
    url: str,
    chat_id: int,
    format_selector: Optional[str] = None,
    output_ext: Optional[str] = None,
    progress_hook: Optional[Callable[[dict], None]] = None
) -> Tuple[Optional[str], Optional[str], Optional[str]]: # Returns (path, file_id, title)
    """Video yuklab olish"""
    
    url_hash = hashlib.md5(url.encode()).hexdigest()
    
    # 1. Keshni tekshirish
    cached = await get_cached_media(url_hash)
    if cached:
        cached_file_id = cached.get('file_id')
        if cached_file_id:
            logger.info(f"Using cached file_id for video: {url}")
            return None, cached_file_id
            
        cached_path = cached.get('path')
        if cached_path and os.path.exists(cached_path):
            logger.info(f"Using cached file for video: {url}")
            return cached_path, None
    
    temp_file = Path(TMP_DIR) / f"{url_hash[:12]}_{chat_id}.mp4"
    
    try:
        if is_instagram_url(url):
            result = await download_instagram_direct(url, temp_file)
            if result and os.path.exists(result):
                return str(result), None

        format_selector = format_selector or "bestvideo*+bestaudio/best"
        merge_ext = output_ext if output_ext in {"mp4", "webm", "mkv"} else "mp4"

        ydl_opts = {
            **COMMON_OPTS,
            'format': f"{format_selector}/best",
            'postprocessors': [{
                'key': 'FFmpegVideoRemuxer',
                'preferedformat': merge_ext,
            }],
            'merge_output_format': merge_ext,
            'outtmpl': str(temp_file).replace('.mp4', '.%(ext)s'),
            'noplaylist': True,
            'cachedir': False,
            'max_filesize': 2 * 1024 * 1024 * 1024,
        }
        if progress_hook:
            ydl_opts['progress_hooks'] = [progress_hook]

        logger.info(f"Downloading Video: {url}")
        video_title = "Video"
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # download=True performs the download and returns info
                info_dict = await asyncio.to_thread(ydl.extract_info, url, download=True)
                if info_dict:
                    video_title = info_dict.get('title', 'Video')
        except yt_dlp.utils.DownloadError as e:
            err_msg = str(e).lower()
            if "requested format is not available" in err_msg:
                fallback_opts = {**ydl_opts, 'format': 'best'}
                try:
                    logger.info(f"Retrying with format 'best' for {url}")
                    with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                        info_dict = await asyncio.to_thread(ydl.extract_info, url, download=True)
                        if info_dict:
                            video_title = info_dict.get('title', 'Video')
                except yt_dlp.utils.DownloadError as e2:
                    raise _map_download_error(str(e2).lower(), "video")
            else:
                raise _map_download_error(err_msg, "video")

        downloaded_file = temp_file if temp_file.exists() else _find_downloaded_file(temp_file.parent, temp_file.stem)

        if not downloaded_file:
            return None, None, None

        return str(downloaded_file), None, video_title

    except Exception as e:
        logger.error(f"Video download error: {e}", exc_info=True)
        raise e

