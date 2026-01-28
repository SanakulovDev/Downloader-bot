import asyncio
import os
import hashlib
import logging
import time
from pathlib import Path
from typing import Tuple, Optional, Callable, Dict, Any, Union
import yt_dlp
import msgpack
from instagram_downloader import download_instagram_direct
from loader import TMP_DIR, redis_client
from utils.validation import is_instagram_url, is_youtube_url

logger = logging.getLogger(__name__)

# --- CONFIG ---
CACHE_TTL = 1800  # 30 minutes
YTDLP_DOWNLOAD_TIMEOUT = 900  # seconds

class _YtDlpLogger:
    def debug(self, msg):
        if not msg.startswith('[debug] '):
            logger.debug(f"[yt-dlp] {msg}")

    def info(self, msg):
        logger.info(f"[yt-dlp] {msg}")

    def warning(self, msg):
        if "Requested format is not available" in str(msg):
            return
        logger.warning(f"[yt-dlp] {msg}")

    def error(self, msg):
        if "Requested format is not available" in str(msg):
            return
        logger.error(f"[yt-dlp] {msg}")

_COOKIE_FILE = os.getenv("YTDLP_COOKIE_FILE")

COMMON_OPTS = {
    'quiet': False,
    **({'cookiefile': _COOKIE_FILE} if _COOKIE_FILE else {}),
    'force_ipv4': True,
    'force_ipv6': False,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'no_warnings': True,
    'ignoreerrors': False,
    'nocheckcertificate': True,
    'remote_components': ['ejs:github'],
    # Aria2c Configuration
    'external_downloader': 'aria2c',
    'external_downloader_args': [
        '--max-connection-per-server=16',
        '--split=16',
        '--min-split-size=1M',
        '--max-overall-download-limit=0',
        '--file-allocation=none',
        # QUYIDAGI 3 TA QATORNI QO'SHING (Time out va ulanish xatolari uchun)
        '--connect-timeout=60', # Ulanishni uzoqroq kutish
        '--timeout=60', # O'qish timeoutni oshirish
        '--retry-wait=5', # Xato bo'lsa 5 soniya kutib qayta urunish
        '--stream-piece-selector=random',# YouTube cheklovidan qochish uchun bo'laklarni random tanlash
    ],
    # HTTP sozlamalari
    'buffersize': 1024 * 1024, # 1MB buffer (8GB RAM-da bu juda xavfsiz va tezroq)
    'http_chunk_size': 10485760, # 10MB chunk
    'retries': 10, # Qayta urunishlar sonini oshirdik
    'fragment_retries': 20, # Fragment xatolarida ko'proq urunish
    'socket_timeout': 30, # 10 soniya juda kam, YouTube ba'zan kechikadi

}

TARGET_HEIGHTS = {144, 240, 360, 480, 720, 1080, 1440, 2160}
MAX_FORMAT_SIZE_BYTES = 900 * 1024 * 1024  # 900MB
VIDEO_CODEC_PRIORITY = {
    "avc1": 3,
    "vp9": 2,
    "av01": 1,
}


def _video_codec_rank(vcodec: str | None) -> int:
    if not vcodec:
        return 0
    for prefix, rank in VIDEO_CODEC_PRIORITY.items():
        if vcodec.startswith(prefix):
            return rank
    return 0


def _estimate_format_size_bytes(fmt: dict, duration: int | None) -> int | None:
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    if size:
        return int(size)
    tbr = fmt.get("tbr")  # kbps
    if tbr and duration:
        return int(tbr * 1000 / 8 * duration)
    return None


def _is_storyboard(fmt: dict) -> bool:
    return fmt.get("ext") == "mhtml" or (fmt.get("format_id") or "").startswith("sb")


def _pick_better_format(current: dict | None, candidate: dict) -> dict:
    if not current:
        return candidate
    current_rank = _video_codec_rank(current.get("vcodec"))
    candidate_rank = _video_codec_rank(candidate.get("vcodec"))
    if candidate_rank != current_rank:
        return candidate if candidate_rank > current_rank else current
    if (candidate.get("tbr") or 0) > (current.get("tbr") or 0):
        return candidate
    return current


def _select_best_formats(info: dict) -> list[dict]:
    formats = info.get("formats") or []
    duration = info.get("duration")
    best_progressive: dict[int, dict] = {}
    best_dash: dict[int, dict] = {}

    for fmt in formats:
        height = fmt.get("height")
        if not height or height not in TARGET_HEIGHTS:
            continue
        if _is_storyboard(fmt):
            continue

        vcodec = fmt.get("vcodec")
        if not vcodec or vcodec == "none":
            continue

        size = _estimate_format_size_bytes(fmt, duration)
        if size and size > MAX_FORMAT_SIZE_BYTES:
            continue

        acodec = fmt.get("acodec")
        has_audio = acodec and acodec != "none"
        if has_audio:
            best_progressive[height] = _pick_better_format(best_progressive.get(height), fmt)
        else:
            best_dash[height] = _pick_better_format(best_dash.get(height), fmt)

    items: list[dict] = []
    for height in sorted(TARGET_HEIGHTS):
        fmt = best_progressive.get(height) or best_dash.get(height)
        if not fmt:
            continue
        size_bytes = _estimate_format_size_bytes(fmt, duration) or 0
        is_merge = 0 if (fmt.get("acodec") and fmt.get("acodec") != "none") else 1
        note = "progressive" if is_merge == 0 else "dash_video_only_merge_audio"
        ext = fmt.get("ext") or "mp4"
        items.append({
            "height": height,
            "format_id": fmt.get("format_id"),
            "is_merge": is_merge,
            "ext": ext,
            "size_bytes": size_bytes,
            "size_mb_est": round(size_bytes / (1024 * 1024), 1) if size_bytes else 0.0,
            "note": note,
        })

    if not items:
        for fmt in formats:
            if fmt.get("format_id") == "18":
                size_bytes = _estimate_format_size_bytes(fmt, duration) or 0
                items.append({
                    "height": 360,
                    "format_id": "18",
                    "is_merge": 0,
                    "ext": fmt.get("ext") or "mp4",
                    "size_bytes": size_bytes,
                    "size_mb_est": round(size_bytes / (1024 * 1024), 1) if size_bytes else 0.0,
                    "note": "progressive",
                })
                break

    return items


def _yt_info_opts(include_manifests: bool, extractor_args: dict | None = None) -> dict:
    user_agent = COMMON_OPTS.get("user_agent") or COMMON_OPTS.get("user-agent")
    return {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'skip_download': True,
        'noplaylist': True,
        'socket_timeout': 10,
        'retries': 2,
        'extractor_retries': 2,
        'youtube_include_dash_manifest': include_manifests,
        'youtube_include_hls_manifest': include_manifests,
        'user_agent': user_agent,
        'http_headers': {
            'User-Agent': user_agent,
        },
        'extractor_args': extractor_args or {},
    }


def _extract_info_fast(url: str, opts: dict) -> dict | None:
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


async def fetch_youtube_formats_fast(url: str) -> dict | None:
    """
    Fast YouTube format detection with yt-dlp metadata only.
    Returns schema:
    {
      "id": "", "title": "", "uploader": "", "thumbnail": "", "duration": 0,
      "items": [ ... ]
    }
    """
    info = None
    try:
        fast_opts = _yt_info_opts(include_manifests=False)
        info = await asyncio.wait_for(
            asyncio.to_thread(_extract_info_fast, url, fast_opts),
            timeout=15
        )
    except yt_dlp.utils.DownloadError as e:
        err = str(e).lower()
        if "403" not in err and "forbidden" not in err:
            info = None
    except Exception:
        info = None

    if not info or not info.get("formats"):
        try:
            fallback_opts = _yt_info_opts(
                include_manifests=True,
                extractor_args={
                    "youtube": {
                        "player_client": ["android", "web"],
                    }
                }
            )
            info = await asyncio.wait_for(
                asyncio.to_thread(_extract_info_fast, url, fallback_opts),
                timeout=20
            )
        except Exception:
            info = None

    if not info:
        return None

    items = _select_best_formats(info)
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration") or 0,
        "items": items,
    }


# --- YOUTUBE CONFIG & HELPERS ---
TARGET_HEIGHTS = {144, 240, 360, 480, 720, 1080, 1440, 2160}
MAX_FORMAT_SIZE_BYTES = 900 * 1024 * 1024  # 900MB
VIDEO_CODEC_PRIORITY = {
    "av01": 3,
    "vp9": 2,
    "avc1": 1,
}

def _video_codec_rank(vcodec: str | None) -> int:
    if not vcodec:
        return 0
    for prefix, rank in VIDEO_CODEC_PRIORITY.items():
        if vcodec.startswith(prefix):
            return rank
    return 0

def _estimate_format_size_bytes(fmt: dict, duration: int | None) -> int | None:
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    if size:
        return int(size)
    tbr = fmt.get("tbr")  # kbps
    if tbr and duration:
        return int(tbr * 1000 / 8 * duration)
    return None

def _is_storyboard(fmt: dict) -> bool:
    return fmt.get("ext") == "mhtml" or (fmt.get("format_id") or "").startswith("sb")

def _pick_better_format(current: dict | None, candidate: dict) -> dict:
    if not current:
        return candidate
    current_rank = _video_codec_rank(current.get("vcodec"))
    candidate_rank = _video_codec_rank(candidate.get("vcodec"))
    if candidate_rank != current_rank:
        return candidate if candidate_rank > current_rank else current
    if (candidate.get("tbr") or 0) > (current.get("tbr") or 0):
        return candidate
    return current

def _select_best_formats(info: dict) -> list[dict]:
    formats = info.get("formats") or []
    duration = info.get("duration")
    best_progressive: dict[int, dict] = {}
    best_dash: dict[int, dict] = {}

    for fmt in formats:
        height = fmt.get("height")
        if not height or height not in TARGET_HEIGHTS:
            continue
        if _is_storyboard(fmt):
            continue

        vcodec = fmt.get("vcodec")
        if not vcodec or vcodec == "none":
            continue

        size = _estimate_format_size_bytes(fmt, duration)
        if size and size > MAX_FORMAT_SIZE_BYTES:
            continue

        acodec = fmt.get("acodec")
        has_audio = acodec and acodec != "none"
        if has_audio:
            best_progressive[height] = _pick_better_format(best_progressive.get(height), fmt)
        else:
            best_dash[height] = _pick_better_format(best_dash.get(height), fmt)

    items: list[dict] = []
    for height in sorted(TARGET_HEIGHTS):
        prog = best_progressive.get(height)
        dash = best_dash.get(height)
        
        # Priority: Progressive > DASH (if prog exists)
        # Requirement: "If progressive... prefer this".
        # Note: If high quality is only DASH, we take DASH.
        # But if 360p is both, we take Progressive.
        
        final_fmt = None
        is_merge = 0
        note = ""

        if prog:
            final_fmt = prog
            is_merge = 0
            note = "progressive"
        elif dash:
            final_fmt = dash
            is_merge = 1
            note = "dash_video_only_merge_audio"
        
        if not final_fmt:
            continue

        size_bytes = _estimate_format_size_bytes(final_fmt, duration) or 0
        ext = final_fmt.get("ext") or "mp4"
        items.append({
            "height": height,
            "format_id": final_fmt.get("format_id"),
            "is_merge": is_merge,
            "ext": ext,
            "size_bytes": size_bytes,
            "size_mb_est": round(size_bytes / (1024 * 1024), 1) if size_bytes else 0.0,
            "note": note,
        })

    if not items:
        # Fallback 18
        for fmt in formats:
            if fmt.get("format_id") == "18":
                size_bytes = _estimate_format_size_bytes(fmt, duration) or 0
                items.append({
                    "height": 360,
                    "format_id": "18",
                    "is_merge": 0,
                    "ext": fmt.get("ext") or "mp4",
                    "size_bytes": size_bytes,
                    "size_mb_est": round(size_bytes / (1024 * 1024), 1) if size_bytes else 0.0,
                    "note": "progressive",
                })
                break
    return items

def _yt_info_opts(include_manifests: bool, extractor_args: dict | None = None) -> dict:
    user_agent = COMMON_OPTS.get("user_agent")
    return {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'skip_download': True,
        'noplaylist': True,
        'socket_timeout': 10,
        'retries': 2,
        'extractor_retries': 2,
        'youtube_include_dash_manifest': include_manifests,
        'youtube_include_hls_manifest': include_manifests,
        'user_agent': user_agent,
        'http_headers': {
            'User-Agent': user_agent,
        },
        'extractor_args': extractor_args or {},
    }

def _extract_info_fast(url: str, opts: dict) -> dict | None:
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None

async def fetch_youtube_formats_fast(url: str) -> dict | None:
    """
    Fast YouTube format detection with yt-dlp metadata only.
    """
    info = None
    try:
        fast_opts = _yt_info_opts(include_manifests=False)
        info = await asyncio.wait_for(
            asyncio.to_thread(_extract_info_fast, url, fast_opts),
            timeout=15
        )
    except Exception:
        pass

    if not info or not info.get("formats"):
        try:
            fallback_opts = _yt_info_opts(
                include_manifests=True,
                extractor_args={
                    "youtube": {
                        "player_client": ["android", "web"],
                    }
                }
            )
            info = await asyncio.wait_for(
                asyncio.to_thread(_extract_info_fast, url, fallback_opts),
                timeout=20
            )
        except Exception:
            pass

    if not info:
        return None

    items = _select_best_formats(info)
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration") or 0,
        "items": items,
    }

def get_format_selector(format_id: str, is_merge: int) -> str:
    if str(is_merge) == "1":
        return f"{format_id}+bestaudio[ext=m4a][acodec!=none]/bestaudio[acodec!=none]/bestaudio"
    else:
        return format_id

async def _path_exists(path: Union[str, os.PathLike]) -> bool:
    return await asyncio.to_thread(os.path.exists, path)

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
        if cached_path and await _path_exists(cached_path):
            logger.info(f"Using cached file for audio: {video_id}")
            return cached_path, cached.get('filename', 'audio.m4a'), None

    ydl_opts = {
        **COMMON_OPTS,
        'quiet': False,
        'logger': _YtDlpLogger(),
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': str(Path(TMP_DIR) / f"{video_id}.%(ext)s"),
    }

    title = "Audio"
    author = "Unknown"

    try:
        logger.info(f"Downloading Audio (Fast Mode): {url}")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await asyncio.wait_for(
                    asyncio.to_thread(ydl.extract_info, url, download=True),
                    timeout=YTDLP_DOWNLOAD_TIMEOUT
                )
                if info:
                    title = info.get('title', 'Audio')
                    author = info.get('uploader', 'Unknown')
        except asyncio.TimeoutError:
            raise Exception("❌ Yuklash vaqti tugadi. Keyinroq urinib ko'ring.")
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
        if cached_path and await _path_exists(cached_path):
            logger.info(f"Using cached file for video: {url}")
            return cached_path, None
    
    temp_file = Path(TMP_DIR) / f"{url_hash[:12]}_{chat_id}.mp4"
    
    try:
        if is_instagram_url(url):
            result = await download_instagram_direct(url, temp_file)
            if result and await _path_exists(result):
                return str(result), None

            # Fallback to yt-dlp for Instagram when direct JSON fails
            format_selector = "best"
            merge_ext = output_ext if output_ext in {"mp4", "webm", "mkv"} else "mp4"
            ig_cookie = os.getenv("INSTAGRAM_COOKIE_FILE")
            ig_proxy = os.getenv("INSTAGRAM_PROXY", "").strip() or None
            ydl_opts = {
                **COMMON_OPTS,
                **({'cookiefile': ig_cookie} if ig_cookie else {}),
                **({'proxy': ig_proxy} if ig_proxy else {}),
                'quiet': False,
                'logger': _YtDlpLogger(),
                'format': format_selector,
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
            # Avoid external downloader for IG to reduce failures
            ydl_opts.pop("external_downloader", None)
            ydl_opts.pop("external_downloader_args", None)
            if progress_hook:
                ydl_opts['progress_hooks'] = [progress_hook]

            logger.info(f"Downloading Instagram via yt-dlp: {url}")
            video_title = "Video"
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = await asyncio.wait_for(
                        asyncio.to_thread(ydl.extract_info, url, download=True),
                        timeout=YTDLP_DOWNLOAD_TIMEOUT
                    )
                    if info_dict:
                        video_title = info_dict.get('title', 'Video')
            except asyncio.TimeoutError:
                raise Exception("❌ Yuklash vaqti tugadi. Keyinroq urinib ko'ring.")
            except yt_dlp.utils.DownloadError as e:
                raise _map_download_error(str(e).lower(), "video")

            downloaded_file = temp_file if temp_file.exists() else _find_downloaded_file(temp_file.parent, temp_file.stem)
            if not downloaded_file:
                return None, None, None
            return str(downloaded_file), None, video_title

        format_selector = format_selector or "bestvideo*+bestaudio/best"
        merge_ext = output_ext if output_ext in {"mp4", "webm", "mkv"} else "mp4"

        ydl_opts = {
            **COMMON_OPTS,
            'quiet': False,
            'logger': _YtDlpLogger(),
            'format': format_selector,
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
                info_dict = await asyncio.wait_for(
                    asyncio.to_thread(ydl.extract_info, url, download=True),
                    timeout=YTDLP_DOWNLOAD_TIMEOUT
                )
                if info_dict:
                    video_title = info_dict.get('title', 'Video')
        except asyncio.TimeoutError:
            raise Exception("❌ Yuklash vaqti tugadi. Keyinroq urinib ko'ring.")
        except yt_dlp.utils.DownloadError as e:
            err_msg = str(e).lower()
            if "aria2c exited with code" in err_msg:
                logger.warning("aria2c failed, retrying with internal downloader")
                no_aria_opts = {**ydl_opts}
                no_aria_opts.pop("external_downloader", None)
                no_aria_opts.pop("external_downloader_args", None)
                try:
                    with yt_dlp.YoutubeDL(no_aria_opts) as ydl:
                        info_dict = await asyncio.wait_for(
                            asyncio.to_thread(ydl.extract_info, url, download=True),
                            timeout=YTDLP_DOWNLOAD_TIMEOUT
                        )
                        if info_dict:
                            video_title = info_dict.get('title', 'Video')
                    err_msg = ""
                except asyncio.TimeoutError:
                    raise Exception("❌ Yuklash vaqti tugadi. Keyinroq urinib ko'ring.")
                except yt_dlp.utils.DownloadError as e_noaria:
                    err_msg = str(e_noaria).lower()
            if "requested format is not available" in err_msg:
                try:
                    # 1. Fallback: Request qilingan formatni cookiesiz urinib ko'rish
                    logger.info(f"Retrying with original format without cookies for {url}")
                    fallback_opts_1 = {**ydl_opts}
                    if 'cookiefile' in fallback_opts_1:
                        del fallback_opts_1['cookiefile']
                    fallback_opts_1.pop("external_downloader", None)
                    fallback_opts_1.pop("external_downloader_args", None)
                    
                    with yt_dlp.YoutubeDL(fallback_opts_1) as ydl:
                        info_dict = await asyncio.wait_for(
                            asyncio.to_thread(ydl.extract_info, url, download=True),
                            timeout=YTDLP_DOWNLOAD_TIMEOUT
                        )
                        if info_dict:
                            video_title = info_dict.get('title', 'Video')

                except asyncio.TimeoutError:
                    raise Exception("❌ Yuklash vaqti tugadi. Keyinroq urinib ko'ring.")
                except yt_dlp.utils.DownloadError as e_opt:
                     # 2. Fallback: Agar o'xshamasa, 'best' formatni cookiesiz urinib ko'rish
                    logger.warning(f"Original format retry failed: {e_opt}. Trying 'best' format...")
                    
                    fallback_opts_2 = {**ydl_opts, 'format': 'bestvideo*+bestaudio/best'}
                    if 'cookiefile' in fallback_opts_2:
                        del fallback_opts_2['cookiefile']
                    fallback_opts_2.pop("external_downloader", None)
                    fallback_opts_2.pop("external_downloader_args", None)
                    
                    try:
                        with yt_dlp.YoutubeDL(fallback_opts_2) as ydl:
                            info_dict = await asyncio.wait_for(
                                asyncio.to_thread(ydl.extract_info, url, download=True),
                                timeout=YTDLP_DOWNLOAD_TIMEOUT
                            )
                            if info_dict:
                                video_title = info_dict.get('title', 'Video')
                    except asyncio.TimeoutError:
                        raise Exception("❌ Yuklash vaqti tugadi. Keyinroq urinib ko'ring.")
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

