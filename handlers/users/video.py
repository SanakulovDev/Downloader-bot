from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from pathlib import Path
from shazamio import Shazam
import logging
import asyncio
import yt_dlp

from loader import dp, TMP_DIR
from states.bot_states import BotStates
from keyboards.default_keyboards import main_menu
from utils.validation import is_youtube_url, is_instagram_url, extract_url
from tasks.bot_tasks import process_video_task
from utils.search import search_music
from utils.telegram_helpers import safe_delete_message, safe_edit_text
from utils.i18n import get_user_lang, t

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data.startswith('recognize_music:'))
async def handle_recognize_music(callback: CallbackQuery):
    """Videodagi musiqani aniqlash va variantlarni ko'rsatish"""
    video_id = callback.data.split(':')[1]
    from loader import redis_client
    lang = await get_user_lang(callback.from_user.id, redis_client)
    
    # Userga javob qaytarish (loading...)
    await callback.answer(t("recognize_start", lang), show_alert=False)
    status_msg = await callback.message.answer(t("audio_part_loading", lang))
    
    # Biz yakuniy fayl .mp3 bo'lishini kutyapmiz
    temp_audio = Path(TMP_DIR) / f"recog_{video_id}.mp3"
    
    try:
        # 1. Audio ni yuklab olish (Cookiesiz, Android Client bilan)
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            # Fayl nomini shablon orqali beramiz, yt-dlp o'zi .mp3 qiladi
            'outtmpl': str(Path(TMP_DIR) / f"recog_{video_id}.%(ext)s"),
            
            # --- IP BLOKNI AYLANIB O'TISH ---
            # Cookie ISHLATMAYMIZ (IP mojarosi bo'lmasligi uchun)
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            },
            # --------------------------------
            
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            
            # Majburan MP3 ga o'tkazish (Shazam uchun qulay)
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        await safe_edit_text(status_msg, t("audio_loading_youtube", lang))
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
            
        if not temp_audio.exists():
            # Ba'zan yt-dlp formatni o'zgartirib yuborishi mumkin, tekshiramiz
            found = False
            for f in Path(TMP_DIR).glob(f"recog_{video_id}.*"):
                if f.exists():
                    temp_audio = f
                    found = True
                    break
            if not found:
                await safe_edit_text(status_msg, t("audio_download_failed", lang))
                return

        # 2. Shazam orqali aniqlash
        await safe_edit_text(status_msg, t("shazam_listening", lang))
        shazam = Shazam()
        out = await shazam.recognize(str(temp_audio))
        
        track = out.get('track', {})
        title = track.get('title')
        subtitle = track.get('subtitle')
        
        if not title:
            await safe_edit_text(status_msg, t("shazam_not_found", lang))
            return
            
        search_query = f"{title} {subtitle}"
        await safe_edit_text(
            status_msg,
            t("shazam_found", lang, query=search_query),
            parse_mode='HTML'
        )
        
        # 3. YouTube dan variantlarni qidirish (Bot ichidan yuklab berish uchun)
        results = await search_music(search_query)
        
        if not results:
            await safe_edit_text(
                status_msg,
                t("shazam_no_results", lang, query=search_query)
            )
            return

        # 4. Variantlarni ko'rsatish
        keyboard = []
        for res in results[:5]: # Maksimum 5 ta variant
            keyboard.append([
                InlineKeyboardButton(
                    text=f"⬇️ {res['title'][:30]}...",
                    callback_data=f"music:{res['id']}" 
                )
            ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await safe_edit_text(
            status_msg,
            t("choose_variant", lang, query=search_query),
            parse_mode='HTML',
            reply_markup=kb
        )

    except Exception as e:
        logger.error(f"Recognition error: {e}", exc_info=True)
        await safe_edit_text(status_msg, t("system_error", lang))
        
    finally:
        # Faylni tozalash
        if temp_audio and temp_audio.exists():
            try:
                temp_audio.unlink()
            except:
                pass

async def handle_video_logic(message: Message, url: str):
    """
    Asosiy Video yuklash logikasi (Navbatga qo'shadi)
    Mijoz link yuborsa, uning xabarini o'chirib, keyin status xabarini yuboradi
    """
    chat_id = message.chat.id
    
    # Mijozning link xabarini o'chirish (preview ko'rsatilmasligi uchun)
    deleted = await safe_delete_message(message)
    if not deleted:
        logger.warning("Xabarni o'chirib bo'lmadi.")
    
    # Status xabarini yuborish
    from loader import bot
    from loader import redis_client
    lang = await get_user_lang(message.from_user.id, redis_client)
    status_msg = await bot.send_message(
        chat_id=chat_id,
        text=t("video_loading", lang),
        parse_mode='HTML',
        disable_web_page_preview=True
    )
    
    # Celery taskga yuboramiz (parallel bajariladi)
    process_video_task.delay(
        chat_id=chat_id,
        url=url,
        status_message_id=status_msg.message_id
    )

@router.callback_query(F.data == 'delete_this_msg')
async def handle_delete_message_callback(callback: CallbackQuery):
    """Xabar o'chirish tugmasi bosilganda"""
    from loader import redis_client
    lang = await get_user_lang(callback.from_user.id, redis_client)
    deleted = await safe_delete_message(callback.message)
    if deleted:
        await callback.answer(t("delete_ok", lang), show_alert=False)
    else:
        await callback.answer(t("delete_failed", lang), show_alert=True)
