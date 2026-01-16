from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
import logging

from loader import dp
from states.bot_states import BotStates
from utils.search import search_music
from utils.queue_handler import DOWNLOAD_QUEUE

router = Router()
logger = logging.getLogger(__name__)

async def show_music_page(chat_id, results, page, message_to_edit: Message = None):
    # This requires `bot` instance. We can import it from loader
    from loader import bot
    ITEMS_PER_PAGE = 10
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_items = results[start:end]
    
    keyboard = []
    row = []
    for i, res in enumerate(current_items):
        button = InlineKeyboardButton(
            text=f"🎵 {res['title'][:30]}...", # Shorten title for 2 columns
            callback_data=f"music:{res['id']}"
        )
        row.append(button)
        # 2 columns per row
        if len(row) == 2:
            keyboard.append(row)
            row = []
    
    # Add remaining
    if row:
        keyboard.append(row)
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"music_page:{page-1}"))
    if end < len(results):
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"music_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
        
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    text = f"🎵 Natijalar (Sahifa {page+1}):"
    
    if message_to_edit:
        await message_to_edit.edit_text(text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

@router.callback_query(F.data.startswith('like:'))
async def handle_like(callback: CallbackQuery):
    """Like bosilganda"""
    video_id = callback.data.split(':')[1]
    user_id = callback.from_user.id
    
    # Extract title from audio or caption
    title = "Unknown Song"
    if callback.message.audio:
        title = callback.message.audio.title or callback.message.caption or "Song"
    elif callback.message.caption:
        title = callback.message.caption.split('\n')[0].replace('🎵 ', '')
    
    # Redis ga saqlash: "id|title"
    from loader import redis_client
    if redis_client:
        try:
            # Add to user's like set
            data = f"{video_id}|{title}"
            await redis_client.sadd(f"user:{user_id}:likes", data)
        except:
            pass
            
    await callback.answer("❤️ Sevimlilarga qo'shildi!", show_alert=False)
    # Remove Like button to prevent spamming? Or keep it. Keeping it is fine.

@router.message(F.text == "🎵 Musiqa Qidirish")
@router.message(Command("music"))
async def mode_music(message: Message, state: FSMContext):
    await state.set_state(BotStates.music_mode)
    await message.answer("🎵 <b>Musiqa rejimidasiz.</b>\n\nQo'shiq yoki artist nomini yozing:", parse_mode='HTML')

@router.message(BotStates.music_mode)
async def handle_music_message(message: Message, state: FSMContext):
    """Musiqa rejimida ishlash"""
    text = message.text
    
    if text in ["🎬 Video Yuklash", "🎵 Musiqa Qidirish"]:
         return

    status_msg = await message.answer(f"🔍 Qidirilmoqda: <b>{text}</b>...", parse_mode='HTML')
    
    # 20 ta natija olish (pagination uchun)
    results = await search_music(text) 
    
    if not results:
        await status_msg.edit_text("❌ Hech narsa topilmadi.")
        return

    # Cache results in state for pagination
    await state.update_data(search_results=results, search_query=text)
    
    await show_music_page(message.chat.id, results, 0, status_msg)

@router.callback_query(F.data.startswith('music_page:'))
async def handle_music_pagination(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(':')[1])
    data = await state.get_data()
    results = data.get('search_results', [])
    
    if not results:
        await callback.answer("❌ Qidiruv natijalari eskirgan.", show_alert=True)
        return

    await show_music_page(callback.message.chat.id, results, page, callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith('music:'))
async def handle_music_callback(callback: CallbackQuery):
    """Musiqa yuklab olish tugmasi bosilganda"""
    video_id = callback.data.split(':')[1]
    await callback.answer("⏳ Musiqa yuklanmoqda...", show_alert=False)
    
    # Queue ga qo'shish
    position = DOWNLOAD_QUEUE.qsize() + 1
    await callback.message.edit_text(f"⏳ <b>Navbatga qo'shildi...</b>\nSizning navbatingiz: {position}", parse_mode='HTML')
    
    await DOWNLOAD_QUEUE.put(('music', callback.message.chat.id, video_id, callback))


@router.message(Command("my_favorite"))
@router.message(Command("favorites"))
async def cmd_my_favorite(message: Message):
    """Sevimlilar ro'yxatini ko'rsatish"""
    user_id = message.from_user.id
    from loader import redis_client, bot
    
    if not redis_client:
        await message.answer("❌ Kechirasiz, bu funksiya hozir ishlamayapti (Database offline).")
        return

    # Get all likes
    likes = await redis_client.smembers(f"user:{user_id}:likes")
    if not likes:
        await message.answer("🤷‍♂️ Sizda hali sevimli musiqalar yo'q.")
        return
        
    # Parse likes (id|title)
    # Handle old format (just id) gracefully if any
    keyboard = []
    decoded_likes = []
    
    for item in likes:
        try:
            item_str = item.decode() if isinstance(item, bytes) else item
            if '|' in item_str:
                vid, title = item_str.split('|', 1)
                decoded_likes.append({'id': vid, 'title': title})
            else:
                # Fallback for old data
                decoded_likes.append({'id': item_str, 'title': "Unknown Song"})
        except:
            pass
            
    # Sort or just list? Let's list. limiting to 50 maybe?
    for song in decoded_likes[:50]:
        keyboard.append([
            InlineKeyboardButton(
                text=f"🎵 {song['title']}",
                callback_data=f"music:{song['id']}" # Reuse music download handler
            )
        ])
        
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("❤️ <b>Sizning sevimli musiqalaringiz:</b>", parse_mode='HTML', reply_markup=kb)
