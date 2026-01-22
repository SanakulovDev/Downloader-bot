import asyncio
import logging
import os
from hashlib import sha256
from typing import Optional

import redis
from dotenv import load_dotenv

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from tasks.celery_app import celery_app
from utils.download import download_video, download_audio
from utils.validation import extract_youtube_id, is_youtube_url

load_dotenv('app/.env')

logger = logging.getLogger(__name__)
IDEMPOTENCY_TTL_SECONDS = int(os.getenv('IDEMPOTENCY_TTL_SECONDS', '900'))


def _get_redis():
    host = os.getenv('REDIS_HOST', 'localhost')
    port = int(os.getenv('REDIS_PORT', '6379'))
    try:
        client = redis.Redis(host=host, port=port, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception:
        return None


def _acquire_lock(key: str) -> bool:
    client = _get_redis()
    if not client:
        return True
    try:
        return bool(client.set(key, "1", nx=True, ex=IDEMPOTENCY_TTL_SECONDS))
    except Exception:
        return True


def _release_lock(key: str) -> None:
    client = _get_redis()
    if not client:
        return
    try:
        client.delete(key)
    except Exception:
        pass


async def _with_bot():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    session = AiohttpSession(timeout=1800)
    bot = Bot(token=token, session=session)
    return bot, session


@celery_app.task(name='tasks.process_video_task')
def process_video_task(chat_id: int, url: str, status_message_id: Optional[int] = None) -> None:
    url_hash = sha256(url.encode()).hexdigest()[:16]
    lock_key = f"idempotency:video:{chat_id}:{url_hash}"
    if not _acquire_lock(lock_key):
        if status_message_id:
            asyncio.run(_delete_message_only(chat_id, status_message_id))
        return
    try:
        asyncio.run(_process_video_task_async(chat_id, url, status_message_id))
    finally:
        _release_lock(lock_key)


async def _process_video_task_async(chat_id: int, url: str, status_message_id: Optional[int]) -> None:
    bot, session = await _with_bot()
    try:
        video_path = await download_video(url, chat_id)
        if video_path:
            keyboard = None
            if is_youtube_url(url):
                vid_id = extract_youtube_id(url)
                if vid_id:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="🎵", callback_data=f"music:{vid_id}"),
                            InlineKeyboardButton(text="❌", callback_data="delete_this_msg")
                        ]
                    ])
            else:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌", callback_data="delete_this_msg")]
                ])

            await bot.send_video(
                chat_id=chat_id,
                video=FSInputFile(video_path),
                caption="🤖 " + (os.getenv("TELEGRAM_NICKNAME") or "@InstantAudioBot"),
                reply_markup=keyboard
            )

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
    if not _acquire_lock(lock_key):
        if status_message_id:
            asyncio.run(_delete_message_only(chat_id, status_message_id))
        return
    try:
        asyncio.run(_process_music_task_async(chat_id, video_id, message_id, is_media, status_message_id))
    finally:
        _release_lock(lock_key)


async def _process_music_task_async(
    chat_id: int,
    video_id: str,
    message_id: int,
    is_media: bool,
    status_message_id: Optional[int]
) -> None:
    bot, session = await _with_bot()
    try:
        audio_path, filename = await download_audio(video_id, chat_id)
        if audio_path:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="❤️", callback_data=f"like:{video_id}"),
                    InlineKeyboardButton(text="❌", callback_data="delete_this_msg")
                ]
            ])

            await bot.send_audio(
                chat_id=chat_id,
                audio=FSInputFile(audio_path, filename=filename),
                caption=f"🎵 {filename.replace('.m4a', '')} \n🤖 " + (os.getenv("TELEGRAM_NICKNAME") or "@InstantAudioBot"),
                title=filename.replace('.m4a', ''),
                reply_markup=keyboard
            )

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
        await _edit_or_reply_error(bot, chat_id, message_id, status_message_id, is_media, err_text)
    finally:
        await session.close()


async def _edit_or_reply_error(
    bot: Bot,
    chat_id: int,
    message_id: int,
    status_message_id: Optional[int],
    is_media: bool,
    text: str
) -> None:
    target_message_id = status_message_id if is_media and status_message_id else message_id
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=target_message_id, text=text)
    except Exception:
        await bot.send_message(chat_id=chat_id, text=text)


async def _delete_message_only(chat_id: int, message_id: int) -> None:
    bot, session = await _with_bot()
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass
    finally:
        await session.close()
