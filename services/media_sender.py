from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from core.config import get_settings
from utils.validation import extract_youtube_id, is_youtube_url


def build_video_keyboard(url: str) -> InlineKeyboardMarkup | None:
    if is_youtube_url(url):
        vid_id = extract_youtube_id(url)
        if vid_id:
            return InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🎵", callback_data=f"music:{vid_id}"),
                    InlineKeyboardButton(text="❌", callback_data="delete_this_msg")
                ]
            ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌", callback_data="delete_this_msg")]
    ])


def build_audio_keyboard(video_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎤 Muallif qo'shiqlari", callback_data=f"artist:{video_id}")
        ],
        [
            InlineKeyboardButton(text="❤️", callback_data=f"like:{video_id}"),
            InlineKeyboardButton(text="❌", callback_data="delete_this_msg")
        ]
    ])


async def send_video(
    bot: Bot,
    chat_id: int,
    video_path: str,
    url: str
):
    settings = get_settings()
    # Telegram video preview is best for mp4; for other formats send as document
    if video_path.lower().endswith((".webm", ".mkv")):
        return await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(video_path),
            caption="🤖 " + settings.telegram_nickname,
            reply_markup=build_video_keyboard(url)
        )
    else:
        return await bot.send_video(
            chat_id=chat_id,
            video=FSInputFile(video_path),
            caption="🤖 " + settings.telegram_nickname,
            reply_markup=build_video_keyboard(url)
        )


async def send_audio(
    bot: Bot,
    chat_id: int,
    audio_path: str,
    filename: str,
    video_id: str
):
    settings = get_settings()
    return await bot.send_audio(
        chat_id=chat_id,
        audio=FSInputFile(audio_path, filename=filename),
        caption=f"🎵 {filename.replace('.m4a', '')} \n🤖 " + settings.telegram_nickname,
        title=filename.replace('.m4a', ''),
        reply_markup=build_audio_keyboard(video_id)
    )
