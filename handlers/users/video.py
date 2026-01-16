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
from utils.queue_handler import DOWNLOAD_QUEUE
from utils.search import search_music

logger = logging.getLogger(__name__)
router = Router()

@router.message(F.text == "🎬 Video Yuklash")
async def mode_video(message: Message, state: FSMContext):
    await state.set_state(BotStates.video_mode)
    await message.answer("🎬 <b>Video rejimidasiz.</b>\n\nYouTube yoki Instagram link yuboring:", parse_mode='HTML')


@router.callback_query(F.data.startswith('recognize_music:'))
async def handle_recognize_music(callback: CallbackQuery):
    """Videodagi musiqani aniqlash va variantlarni ko'rsatish"""
    video_id = callback.data.split(':')[1]
    await callback.answer("⏳ Musiqa aniqlanmoqda...", show_alert=False)
    
    status_msg = await callback.message.answer("🔍 Musiqa aniqlanmoqda... Biroz kuting.")
    
    temp_audio = None
    try:
        # 1. Audio ni yuklab olish (Recognition uchun)
        temp_audio = Path(TMP_DIR) / f"recog_{video_id}.m4a"
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'outtmpl': str(temp_audio),
            'quiet': True,
            'max_filesize': 10 * 1024 * 1024, # 10MB yetadi
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
            
        if not temp_audio.exists():
            await status_msg.edit_text("❌ Audio yuklab bo'lmadi.")
            return

        # 2. Shazam orqali aniqlash
        shazam = Shazam()
        out = await shazam.recognize(str(temp_audio))
        
        track = out.get('track', {})
        title = track.get('title')
        subtitle = track.get('subtitle')
        
        if not title:
            await status_msg.edit_text("❌ Musiqa aniqlanmadi.")
            return
            
        search_query = f"{title} {subtitle}"
        await status_msg.edit_text(f"✅ Topildi: <b>{search_query}</b>\n\n🔍 Variantlar qidirilmoqda...", parse_mode='HTML')
        
        # 3. YouTube dan variantlarni qidirish
        results = await search_music(search_query)
        
        if not results:
            await status_msg.edit_text(f"❌ '{search_query}' bo'yicha hech narsa topilmadi.")
            return

        # 4. Variantlarni ko'rsatish
        keyboard = []
        for res in results:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"⬇️ {res['title']} ({res['channel']})",
                    callback_data=f"music:{res['id']}" # Bu eski music handlerga tushadi va yuklab beradi
                )
            ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await status_msg.edit_text(
            f"🎵 <b>'{search_query}'</b> bo'yicha natijalar:\nYuklab olish uchun tanlang:",
            parse_mode='HTML',
            reply_markup=kb
        )

    except Exception as e:
        logger.error(f"Recognition error: {e}", exc_info=True)
        await status_msg.edit_text("❌ Xatolik yuz berdi.")
        
    finally:
        if temp_audio and temp_audio.exists():
            try:
                temp_audio.unlink()
            except:
                pass


@router.message(BotStates.video_mode)
async def handle_video_message(message: Message):
    """Video rejimida ishlash"""
    text = message.text
    chat_id = message.chat.id
    
    if text in ["🎬 Video Yuklash", "🎵 Musiqa Qidirish"]:
         # Agar menyu bosilsa
         await message.answer("Rejimni o'zgartirish uchun qaytadan tanlang.", reply_markup=main_menu)
         return

    url = extract_url(text)
    if not url:
        await message.answer("❌ Iltimos, video link yuboring.")
        return

    if not (is_youtube_url(url) or is_instagram_url(url)):
        await message.answer("❌ Faqat YouTube va Instagram videolari qo'llab-quvvatlanadi!")
        return

    status_msg = await message.answer(f"🎬 Yuklab olinmoqda: <b>{url}</b>", parse_mode='HTML')
    
    # Queue ga qo'shish
    position = DOWNLOAD_QUEUE.qsize() + 1
    await status_msg.edit_text(f"⏳ <b>Navbatga qo'shildi...</b>\nSizning navbatingiz: {position}", parse_mode='HTML')
    
    await DOWNLOAD_QUEUE.put(('video', chat_id, url, message))
