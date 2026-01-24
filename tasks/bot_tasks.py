import asyncio
import logging
import os
import time
from hashlib import sha256
from typing import Optional

from tasks.celery_app import celery_app
from utils.download import download_video, download_audio, cache_media_result
from services.artist_cache import cache_artist_name
from services.bot_client import create_bot_session
from services.idempotency import acquire_lock, release_lock
from services.media_sender import send_audio, send_video
from services.message_utils import edit_or_reply_error, delete_message_only
from utils.i18n import get_user_lang_sync, translate_error, t

logger = logging.getLogger(__name__)


@celery_app.task(name='tasks.process_video_task')
def process_video_task(
    chat_id: int,
    url: str,
    status_message_id: Optional[int] = None,
    format_selector: Optional[str] = None,
    output_ext: Optional[str] = None
) -> None:
    url_hash = sha256(url.encode()).hexdigest()[:16]
    lock_key = f"idempotency:video:{chat_id}:{url_hash}"
    if not acquire_lock(lock_key):
        if status_message_id:
            asyncio.run(_delete_message_only(chat_id, status_message_id))
        return
    try:
        asyncio.run(_process_video_task_async(chat_id, url, status_message_id, format_selector, output_ext))
    finally:
        release_lock(lock_key)


async def _process_video_task_async(
    chat_id: int,
    url: str,
    status_message_id: Optional[int],
    format_selector: Optional[str],
    output_ext: Optional[str]
) -> None:
    bot, session = create_bot_session()
    lang = get_user_lang_sync(chat_id)
    try:
        loop = asyncio.get_running_loop()
        last_update = 0.0

        def progress_hook(data: dict) -> None:
            nonlocal last_update
            if data.get("status") != "downloading" or not status_message_id:
                return
            now = time.monotonic()
            if now - last_update < 2.0:
                return
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes")
            percent = ""
            if total and downloaded:
                percent = f"{downloaded * 100 / total:.0f}%"
            text = t("video_progress", lang, percent=percent)
            asyncio.run_coroutine_threadsafe(
                _edit_progress_message(bot, chat_id, status_message_id, text),
                loop
            )
            last_update = now

        video_path, existing_file_id, video_title = await download_video(
            url,
            chat_id,
            format_selector=format_selector,
            output_ext=output_ext,
            progress_hook=progress_hook
        )
        
        sent_message = None
        if existing_file_id:
            sent_message = await send_video(bot, chat_id, video_path=None, url=url, file_id=existing_file_id, title=video_title)
        elif video_path:
            sent_message = await send_video(bot, chat_id, video_path=video_path, url=url, title=video_title)
             
             # Cache the file_id if sending was successful
            if sent_message and sent_message.video:
                url_hash = sha256(url.encode()).hexdigest()
                await cache_media_result(url_hash, {'file_id': sent_message.video.file_id})
            
            # Remove file from RAM/Disk (ALWAYS)
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
            except Exception as e:
                logger.error(f"Failed to remove video file: {e}")

        if sent_message:
            if status_message_id:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=status_message_id)
                except Exception:
                    pass
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=t("video_download_failed", lang),
                disable_web_page_preview=True
            )
            if status_message_id:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=status_message_id)
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Video task error: {e}")
        err_text = translate_error(str(e), lang)
        if "❌" not in err_text:
            err_text = t("download_error_generic", lang)
        await bot.send_message(chat_id=chat_id, text=err_text, disable_web_page_preview=True)
        if status_message_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=status_message_id)
            except Exception:
                pass
    finally:
        await session.close()


async def _edit_progress_message(bot, chat_id: int, message_id: int, text: str) -> None:
    try:
        await bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, parse_mode='HTML')
    except Exception:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode='HTML')
        except Exception:
            pass


@celery_app.task(name='tasks.process_music_task')
def process_music_task(
    chat_id: int,
    video_id: str,
    message_id: int,
    is_media: bool,
    status_message_id: Optional[int] = None
) -> None:
    lock_key = f"idempotency:music:{chat_id}:{video_id}"
    if not acquire_lock(lock_key):
        if status_message_id:
            asyncio.run(_delete_message_only(chat_id, status_message_id))
        return
    try:
        asyncio.run(_process_music_task_async(chat_id, video_id, message_id, is_media, status_message_id))
    finally:
        release_lock(lock_key)


async def _process_music_task_async(
    chat_id: int,
    video_id: str,
    message_id: int,
    is_media: bool,
    status_message_id: Optional[int]
) -> None:
    bot, session = create_bot_session()
    lang = get_user_lang_sync(chat_id)
    try:
        audio_path, filename, file_id = await download_audio(video_id, chat_id)
        
        sent_message = None
        if file_id:
             # Reuse cached file_id
             sent_message = await send_audio(bot, chat_id, file_id, filename, video_id)
        elif audio_path:
            artist_name = "Unknown"
            if " - " in filename:
                artist_name = filename.rsplit(" - ", 1)[1].replace(".m4a", "")
            cache_artist_name(video_id, artist_name)

            sent_message = await send_audio(bot, chat_id, audio_path, filename, video_id)
        
        if sent_message:
            # Capture file_id and Cache
            new_file_id = None
            if sent_message.audio:
                new_file_id = sent_message.audio.file_id
            
            if new_file_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
                url_hash = sha256(url.encode()).hexdigest()
                cache_data = {
                    'path': audio_path if audio_path else "",
                    'file_id': new_file_id,
                    'filename': filename,
                    'ts': int(time.time()),
                    'type': 'audio'
                }
                await cache_media_result(url_hash, cache_data)

            if not is_media:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    pass

            # Cleanup audio file
            try:
                if audio_path and os.path.exists(audio_path):
                     os.remove(audio_path)
            except Exception as e:
                logger.error(f"Failed to remove audio file: {e}")

            if status_message_id:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=status_message_id)
                except Exception:
                    pass
        else:
            await _edit_or_reply_error(
                bot,
                chat_id,
                message_id,
                status_message_id,
                is_media,
                t("music_download_failed", lang)
            )
    except Exception as e:
        logger.error(f"Music task error: {e}")
        err_text = translate_error(str(e), lang)
        if "❌" not in err_text:
            err_text = t("send_error_generic", lang)
        await edit_or_reply_error(bot, chat_id, message_id, status_message_id, is_media, err_text)
    finally:
        await session.close()

async def _edit_or_reply_error(
    bot,
    chat_id: int,
    message_id: int,
    status_message_id: Optional[int],
    is_media: bool,
    text: str
) -> None:
    await edit_or_reply_error(bot, chat_id, message_id, status_message_id, is_media, text)


async def _delete_message_only(chat_id: int, message_id: int) -> None:
    bot, session = create_bot_session()
    try:
        await delete_message_only(bot, chat_id, message_id)
    finally:
        await session.close()
