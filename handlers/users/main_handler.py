from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from utils.validation import is_youtube_url, is_instagram_url, extract_url
from handlers.users.video import handle_video_logic
from handlers.users.music import handle_music_logic
from utils.i18n import get_user_lang, t

router = Router()

@router.message(StateFilter(None))
async def main_message_handler(message: Message, state: FSMContext):
    """
    Main handler that auto-detects content type:
    - URL -> Video
    - Text -> Music
    """
    text = message.text
    
    # 1. Check for commands or specific reserved words (optional, if router ordering is correct these won't trigger)
    if text.startswith("/"):
        return

    # 2. Check for URL
    url = extract_url(text)
    if url and (is_youtube_url(url) or is_instagram_url(url)):
        # Route to Video Logic
        await handle_video_logic(message, url)
    else:
        # Route to Music Logic
        # If it looks like a URL but not supported, maybe warn? 
        # For now, treat everything else as music search term.
        if url:
            from loader import redis_client
            lang = await get_user_lang(message.from_user.id, redis_client)
            await message.answer(t("unsupported_url", lang))
            return
            
        await handle_music_logic(message, state)
