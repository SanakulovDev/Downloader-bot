from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import json
import subprocess

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
    video_path: str = None,
    url: str = None,
    file_id: str = None,  # Add file_id
    title: str = "Video",
    caption_suffix: str | None = None
):
    settings = get_settings()
    if caption_suffix:
        caption_text = f"📹 {title}\n{caption_suffix}\n\n🤖 {settings.telegram_nickname}"
    else:
        caption_text = f"📹 {title}\n\n🤖 {settings.telegram_nickname}"
    
    if file_id:
        return await bot.send_video(
            chat_id=chat_id,
            video=file_id,
            caption=caption_text,
            reply_markup=build_video_keyboard(url)
        )

    # Telegram video preview is best for mp4; for other formats send as document
    if video_path and video_path.lower().endswith((".webm", ".mkv")):
        return await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(video_path),
            caption=caption_text,
            reply_markup=build_video_keyboard(url)
        )
    elif video_path:
        video_meta = await _probe_video_meta(video_path)
        return await bot.send_video(
            chat_id=chat_id,
            video=FSInputFile(video_path),
            caption=caption_text,
            reply_markup=build_video_keyboard(url),
            supports_streaming=True,
            width=video_meta.get("width"),
            height=video_meta.get("height"),
            duration=video_meta.get("duration"),
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
        caption=f"🎵 {filename.replace('.m4a', '')} \n\n🤖 " + settings.telegram_nickname,
        title=filename.replace('.m4a', ''),
        reply_markup=build_audio_keyboard(video_id)
    )


async def _probe_video_meta(path: str) -> dict:
    def _run_probe() -> dict:
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-print_format",
                    "json",
                    "-show_streams",
                    "-show_format",
                    path,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return {}
            data = json.loads(result.stdout or "{}")
            streams = data.get("streams") or []
            video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
            if not video_stream:
                return {}
            width = int(video_stream.get("width") or 0) or None
            height = int(video_stream.get("height") or 0) or None
            duration = video_stream.get("duration") or (data.get("format") or {}).get("duration")
            duration = int(float(duration)) if duration else None
            return {"width": width, "height": height, "duration": duration}
        except Exception:
            return {}

    return await asyncio.to_thread(_run_probe)
