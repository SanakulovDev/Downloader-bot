import asyncio
import logging
from hashlib import sha256
from typing import Optional

from tasks.celery_app import celery_app
from utils.download import download_video, download_audio
from services.artist_cache import cache_artist_name
from services.bot_client import create_bot_session
from services.idempotency import acquire_lock, release_lock
from services.media_sender import send_audio, send_video
from services.message_utils import edit_or_reply_error, delete_message_only

logger = logging.getLogger(__name__)


@celery_app.task(name='tasks.process_video_task')
def process_video_task(chat_id: int, url: str, status_message_id: Optional[int] = None) -> None:
    url_hash = sha256(url.encode()).hexdigest()[:16]
    lock_key = f"idempotency:video:{chat_id}:{url_hash}"
    if not acquire_lock(lock_key):
        if status_message_id:
            asyncio.run(_delete_message_only(chat_id, status_message_id))
        return
    try:
        asyncio.run(_process_video_task_async(chat_id, url, status_message_id))
    finally:
        release_lock(lock_key)


async def _process_video_task_async(chat_id: int, url: str, status_message_id: Optional[int]) -> None:
    bot, session = create_bot_session()
    try:
        video_path = await download_video(url, chat_id)
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
                text="❌ Video yuklab bo'lmadi.",
                disable_web_page_preview=True
            )
            if status_message_id:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=status_message_id)
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Video task error: {e}")
        err_text = str(e)
        if "❌" not in err_text:
            err_text = "❌ Yuklashda xatolik yuz berdi! (Keyinroq urinib ko'ring)"
        await bot.send_message(chat_id=chat_id, text=err_text, disable_web_page_preview=True)
        if status_message_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=status_message_id)
            except Exception:
                pass
    finally:
        await session.close()


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
                "❌ Musiqa yuklashda xatolik bo'ldi."
            )
    except Exception as e:
        logger.error(f"Music task error: {e}")
        err_text = str(e)
        if "❌" not in err_text:
            err_text = "❌ Yuborishda xatolik yuz berdi!"
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
