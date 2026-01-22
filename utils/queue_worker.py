import threading
import queue
import asyncio
import logging
import time
from hashlib import sha256
from typing import Optional, Dict, Any

from utils.download import download_video, download_audio
from services.artist_cache import cache_artist_name
from services.bot_client import create_bot_session
from services.idempotency import acquire_lock, release_lock
from services.media_sender import send_audio, send_video
from services.message_utils import edit_or_reply_error, delete_message_only
from utils.i18n import get_user_lang_sync, translate_error, t

logger = logging.getLogger(__name__)

# Global Task Queue
task_queue = queue.Queue()

def start_worker():
    """Starts the background worker thread."""
    thread = threading.Thread(target=_worker_loop, daemon=True)
    thread.start()
    logger.info("Background worker thread started.")

def submit_video_task(chat_id: int, url: str, status_message_id: Optional[int] = None, format_selector: Optional[str] = None, output_ext: Optional[str] = None):
    task = {
        'type': 'video',
        'chat_id': chat_id,
        'url': url,
        'status_message_id': status_message_id,
        'format_selector': format_selector,
        'output_ext': output_ext
    }
    task_queue.put(task)
    logger.info(f"Video task submitted for chat {chat_id}")

def submit_music_task(chat_id: int, video_id: str, message_id: int, is_media: bool, status_message_id: Optional[int] = None):
    task = {
        'type': 'music',
        'chat_id': chat_id,
        'video_id': video_id,
        'message_id': message_id,
        'is_media': is_media,
        'status_message_id': status_message_id
    }
    task_queue.put(task)
    logger.info(f"Music task submitted for chat {chat_id}")

def _worker_loop():
    """Main loop for the worker thread."""
    while True:
        try:
            task = task_queue.get()
            if task is None:
                break
            
            logger.info(f"Processing task: {task['type']}")
            try:
                # Run async task in a fresh event loop for this thread
                asyncio.run(_process_task(task))
            except Exception as e:
                logger.error(f"Error processing task: {e}", exc_info=True)
            finally:
                task_queue.task_done()
        except Exception as e:
            logger.error(f"Worker loop fatal error: {e}", exc_info=True)
            time.sleep(1)

async def _process_task(task: Dict[str, Any]):
    if task['type'] == 'video':
        await _process_video_task_async(
            task['chat_id'], 
            task['url'], 
            task['status_message_id'], 
            task['format_selector'], 
            task['output_ext']
        )
    elif task['type'] == 'music':
        await _process_music_task_async(
            task['chat_id'], 
            task['video_id'], 
            task['message_id'], 
            task['is_media'], 
            task['status_message_id']
        )

# --- Logic adapted from tasks/bot_tasks.py ---

async def _process_video_task_async(chat_id: int, url: str, status_message_id: Optional[int], format_selector: Optional[str], output_ext: Optional[str]):
    # Idempotency check
    url_hash = sha256(url.encode()).hexdigest()[:16]
    lock_key = f"idempotency:video:{chat_id}:{url_hash}"
    # Note: acquire_lock uses Redis. If Redis is down/removed, we might want to skip or handle gracefully.
    # Assuming Redis container is still kept as per plan.
    if not acquire_lock(lock_key):
        if status_message_id:
            await _delete_message_only(chat_id, status_message_id)
        return

    try:
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
                
                # We need to run this on the main thread loop or ensure thread safety.
                # Since we are in asyncio.run(), we have OUR loop.
                # NOTE: create_bot_session creates a bot instance.
                # Calling bot methods is async, can be awaited directly in this loop.
                asyncio.run_coroutine_threadsafe(
                    _edit_progress_message(bot, chat_id, status_message_id, text),
                    loop
                )
                last_update = now

            video_path = await download_video(
                url,
                chat_id,
                format_selector=format_selector,
                output_ext=output_ext,
                progress_hook=progress_hook
            )
            if video_path:
                await send_video(bot, chat_id, video_path, url)

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
    finally:
        release_lock(lock_key)

async def _process_music_task_async(chat_id: int, video_id: str, message_id: int, is_media: bool, status_message_id: Optional[int]):
    lock_key = f"idempotency:music:{chat_id}:{video_id}"
    if not acquire_lock(lock_key):
        if status_message_id:
            await _delete_message_only(chat_id, status_message_id)
        return

    try:
        bot, session = create_bot_session()
        lang = get_user_lang_sync(chat_id)
        try:
            audio_path, filename = await download_audio(video_id, chat_id)
            if audio_path:
                artist_name = "Unknown"
                if " - " in filename:
                    artist_name = filename.rsplit(" - ", 1)[1].replace(".m4a", "")
                cache_artist_name(video_id, artist_name)

                await send_audio(bot, chat_id, audio_path, filename, video_id)

                if not is_media:
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=message_id)
                    except Exception:
                        pass

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
    finally:
        release_lock(lock_key)

async def _edit_progress_message(bot, chat_id: int, message_id: int, text: str) -> None:
    try:
        await bot.edit_message_caption(chat_id=chat_id, message_id=message_id, caption=text, parse_mode='HTML')
    except Exception:
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, parse_mode='HTML')
        except Exception:
            pass

async def _edit_or_reply_error(bot, chat_id: int, message_id: int, status_message_id: Optional[int], is_media: bool, text: str) -> None:
    await edit_or_reply_error(bot, chat_id, message_id, status_message_id, is_media, text)

async def _delete_message_only(chat_id: int, message_id: int) -> None:
    bot, session = create_bot_session()
    try:
        await delete_message_only(bot, chat_id, message_id)
    finally:
        await session.close()
