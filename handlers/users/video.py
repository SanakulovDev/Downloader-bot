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

@router.callback_query(F.data.startswith('recognize_music:'))
async def handle_recognize_music(callback: CallbackQuery):
    """Videodagi musiqani aniqlash va variantlarni ko'rsatish"""
    video_id = callback.data.split(':')[1]
    
    # Userga javob qaytarish (loading...)
    await callback.answer("⏳ Musiqa aniqlanmoqda...", show_alert=False)
    status_msg = await callback.message.answer("🔍 Audio qismi yuklanmoqda... 0%")
    
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
        
        await status_msg.edit_text("🔍 Audio yuklanmoqda... (Youtube)")
        
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
                await status_msg.edit_text("❌ Audio yuklab bo'lmadi (Youtube blokladi).")
                return

        # 2. Shazam orqali aniqlash
        await status_msg.edit_text("🎧 Shazam orqali eshitilmoqda...")
        shazam = Shazam()
        out = await shazam.recognize(str(temp_audio))
        
        track = out.get('track', {})
        title = track.get('title')
        subtitle = track.get('subtitle')
        
        if not title:
            await status_msg.edit_text("❌ Afsuski, bu musiqani aniqlab bo'lmadi.")
            return
            
        search_query = f"{title} {subtitle}"
        await status_msg.edit_text(f"✅ Topildi: <b>{search_query}</b>\n\n🔍 Botdan qidirilmoqda...", parse_mode='HTML')
        
        # 3. YouTube dan variantlarni qidirish (Bot ichidan yuklab berish uchun)
        results = await search_music(search_query)
        
        if not results:
            await status_msg.edit_text(f"❌ '{search_query}' Shazamda topildi, lekin Youtubedan topa olmadim.")
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
        await status_msg.edit_text(
            f"🎵 <b>'{search_query}'</b>\n\nQaysi birini yuklab beray?",
            parse_mode='HTML',
            reply_markup=kb
        )

    except Exception as e:
        logger.error(f"Recognition error: {e}", exc_info=True)
        await status_msg.edit_text("❌ Tizimda xatolik yuz berdi.")
        
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
    try:
        await message.delete()
    except Exception as e:
        # Agar xabarni o'chirib bo'lmasa (masalan, xabar juda eski yoki bot admin emas)
        logger.warning(f"Xabarni o'chirib bo'lmadi: {e}")
    
    # Status xabarini yuborish
    from loader import bot
    status_msg = await bot.send_message(
        chat_id=chat_id,
        text="⏳ <b>Video yuklanmoqda...</b>",
        parse_mode='HTML',
        disable_web_page_preview=True
    )
    
    # Queue ga qo'shish
    # position = DOWNLOAD_QUEUE.qsize() + 1
    # await status_msg.edit_text(f"⏳ <b>Navbatga qo'shildi!</b>\nSizning o'rningiz: {position}", parse_mode='HTML')
    
    # Queue handler o'zi `utils/download.py` dagi funksiyani chaqiradi
    # user_msg o'rniga None yuboramiz, chunki xabar o'chirilgan
    await DOWNLOAD_QUEUE.put(('video', chat_id, url, {'user_msg': None, 'status_msg': status_msg, 'original_chat_id': chat_id}))

@router.callback_query(F.data == 'delete_this_msg')
async def handle_delete_message_callback(callback: CallbackQuery):
    """Xabar o'chirish tugmasi bosilganda"""
    try:
        await callback.message.delete()
        await callback.answer("✅ Xabar o'chirildi", show_alert=False)
    except Exception as e:
        await callback.answer("❌ O'chirib bo'lmadi", show_alert=True)