import asyncio
import os
import hashlib
import logging
from pathlib import Path
from typing import Tuple, Optional, Callable
import yt_dlp
from instagram_downloader import download_instagram_direct
from loader import TMP_DIR, redis_client
from utils.validation import is_instagram_url, is_youtube_url

logger = logging.getLogger(__name__)

# --- FIX: LIST FORMAT FOR REMOTE COMPONENTS ---
COMMON_OPTS = {
    'quiet': True,
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
    
    # 4. REMOTE COMPONENTS
    'remote_components': ['ejs:github'],

    # 5. User Agent
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',

    'no_warnings': True,
    'ignoreerrors': True,
    'nocheckcertificate': True,
    'http_chunk_size': 10485760,
    'retries': 5,
    'fragment_retries': 5,
    'socket_timeout': 15,
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
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.to_thread(ydl.extract_info, url, download=True)
                if info:
                    title = info.get('title', 'Audio')
                    author = info.get('uploader', 'Unknown')
        except yt_dlp.utils.DownloadError as e:
            raise _map_download_error(str(e).lower(), "audio")

        clean_title = f"{title} - {author}".replace('/', '-').replace('\\', '-')
        
        # Faylni qidiramiz (chunki u .m4a, .webm va hokazo bo'lishi mumkin)
        # video_id.* bo'yicha glob qilamiz
        downloaded_file = _find_downloaded_file(Path(TMP_DIR), video_id)
        
        if downloaded_file:
            return str(downloaded_file), f"{clean_title}{downloaded_file.suffix}"
            
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        # Re-raise specific errors or return None?
        # Let's return None for now as queue handler handles generic "None" as error, 
        # but better to raise to show message.
        # However, to avoid breaking changes let's try to map it if possible or just log.
        # But user wants SPECIFIC message. So we SHOULD raise.
        raise e 
        
    return None, None


async def download_video(
    url: str,
    chat_id: int,
    format_selector: Optional[str] = None,
    output_ext: Optional[str] = None,
    progress_hook: Optional[Callable[[dict], None]] = None
) -> Optional[str]:
    """Video yuklab olish"""
    logger.info(f"DEBUG: download_video called for {url}")
    logger.info(f"DEBUG: COMMON_OPTS ipv6={COMMON_OPTS.get('force_ipv6')}, client={COMMON_OPTS.get('extractor_args', {}).get('youtube', {}).get('player_client')}")
    
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

        format_selector = format_selector or "bestvideo*+bestaudio/best"
        merge_ext = output_ext if output_ext in {"mp4", "webm", "mkv"} else "mp4"

        # YOUTUBE formatini Shorts va har xil sifatlarga moslab yangilash
        ydl_opts = {
            **COMMON_OPTS,
            # Hech qanday formatni "majbur" qilmaymiz: mavjud bo'lgan eng yaxshi video+audio (yoki best) ni olamiz.
            'format': f"{format_selector}/best",
            # Telegram uchun kerakli konteynerga remux (re-encode emas).
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
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await asyncio.to_thread(ydl.download, [url])
        except yt_dlp.utils.DownloadError as e:
            err_msg = str(e).lower()
            if "requested format is not available" in err_msg:
                # 1-urinish: bestvideo+bestaudio fail bo'lsa -> best (bitta fayl, masalan format 18)
                fallback_opts = {**ydl_opts, 'format': 'best'}
                try:
                    logger.info(f"Retrying with format 'best' for {url}")
                    with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                        await asyncio.to_thread(ydl.download, [url])
                except yt_dlp.utils.DownloadError as e2:
                    # Agar yana o'xshamasa -> error qaytarish
                    raise _map_download_error(str(e2).lower(), "video")
            else:
                raise _map_download_error(err_msg, "video")

        downloaded_file = temp_file if temp_file.exists() else _find_downloaded_file(temp_file.parent, temp_file.stem)

        if not downloaded_file:
            return None

        if redis_client:
            try:
                await redis_client.setex(f"video:{url_hash}", 86400, str(downloaded_file).encode())
            except:
                pass
        
        return str(downloaded_file)

    except Exception as e:
        logger.error(f"Video download error: {e}", exc_info=True)
        raise e # Re-raise to be caught by queue handler
