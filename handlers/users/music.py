from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
import logging

from loader import dp
from states.bot_states import BotStates
from utils.search import search_music
from tasks.bot_tasks import process_music_task
from utils.telegram_helpers import safe_delete_message, safe_edit_text, check_text_length_and_notify
from utils.i18n import get_user_lang, t

router = Router()
logger = logging.getLogger(__name__)

async def show_music_page(chat_id, results, page, lang: str, message_to_edit: Message = None):
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
            text=f"🎵 {res['title'][:30] + '...' if len(res['title']) > 30 else res['title']}", # Smart truncate
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
        nav_buttons.append(InlineKeyboardButton(text=t('music_prev_btn', lang), callback_data=f"music_page:{page-1}"))
    if end < len(results):
        nav_buttons.append(InlineKeyboardButton(text=t('music_next_btn', lang), callback_data=f"music_page:{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Cancel button
    keyboard.append([
        InlineKeyboardButton(text=t("cancel", lang), callback_data="delete_this_msg")
    ])
        
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    text = (
        f"{t('search_results', lang, page=page+1)}"
    )
    
    if message_to_edit:
        await safe_edit_text(message_to_edit, text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

@router.message(Command("my_favorite"))
@router.message(Command("favorites"))
async def cmd_my_favorite(message: Message):
    """Sevimlilar ro'yxatini ko'rsatish"""
    user_id = message.from_user.id
    from loader import redis_client, bot
    lang = await get_user_lang(user_id, redis_client)
    
    if not redis_client:
        await message.answer(t("db_error", lang))
        return

    # Get all likes
    likes = await redis_client.smembers(f"user:{user_id}:likes")
    logger.info(f"Fetching likes for user {user_id}. Found: {len(likes) if likes else 0}")
    
    if not likes:
        await message.answer(t("favorites_empty", lang))
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
    # Sort or just list? Let's list. limiting to 30 to avoid hitting button limits (since we use 2 rows per item)
    for song in decoded_likes[:30]:
        # Row 1: Song Title
        keyboard.append([
            InlineKeyboardButton(
                text=f"🎵 {song['title']}",
                callback_data=f"music:{song['id']}" # Reuse music download handler
            )
        ])
    
    # Add "Clear All" button at the bottom
    keyboard.append([
        InlineKeyboardButton(
            text="🗑 Barchasini tozalash",
            callback_data="del_fav_all"
        )
    ])
        
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    # If called from callback (refresh), edit text. Else answer.
    if isinstance(message, CallbackQuery):
        await safe_edit_text(
            message.message,
            t("favorites_title", lang),
            parse_mode='HTML',
            reply_markup=kb
        )
    else:
        await message.answer(t("favorites_title", lang), parse_mode='HTML', reply_markup=kb)

@router.callback_query(F.data == 'del_fav_all')
async def handle_delete_all_favorites(callback: CallbackQuery):
    """Barcha sevimlilarni o'chirish"""
    user_id = callback.from_user.id
    from loader import redis_client
    lang = await get_user_lang(user_id, redis_client)
    
    if not redis_client:
        await callback.answer(t("db_error", lang), show_alert=True)
        return
        
    # Delete the entire set
    await redis_client.delete(f"user:{user_id}:likes")
    
    await callback.answer(t("favorites_cleared", lang))
    await safe_edit_text(callback.message, t("favorites_empty", lang))

@router.callback_query(F.data.startswith('del_fav:'))
async def handle_delete_favorite(callback: CallbackQuery):
    """Sevimlilardan o'chirish"""
    video_id = callback.data.split(':')[1]
    user_id = callback.from_user.id
    from loader import redis_client
    lang = await get_user_lang(user_id, redis_client)
    
    if not redis_client:
        await callback.answer(t("db_error", lang), show_alert=True)
        return

    # Find the full item to delete (id|title)
    likes = await redis_client.smembers(f"user:{user_id}:likes")
    item_to_delete = None
    
    for item in likes:
        item_str = item.decode() if isinstance(item, bytes) else item
        if item_str.startswith(f"{video_id}|") or item_str == video_id:
            item_to_delete = item
            break
            
    if item_to_delete:
        await redis_client.srem(f"user:{user_id}:likes", item_to_delete)
        await callback.answer("✅ O'chirildi!")
        # Refresh list
        await cmd_my_favorite(callback)
    else:
        await callback.answer("⚠️ Topilmadi", show_alert=True)

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
    
    from loader import redis_client
    lang = await get_user_lang(user_id, redis_client)

    # Redis ga saqlash: "id|title"
    if redis_client:
        try:
            # Add to user's like set
            data = f"{video_id}|{title}"
            added_count = await redis_client.sadd(f"user:{user_id}:likes", data)
            logger.info(f"Added like for user {user_id}: {data} (Result: {added_count})")
            
            if added_count == 0:
                await callback.answer(t("like_exists", lang), show_alert=True)
                return
            else:
                 await callback.answer(t("like_added", lang), show_alert=False)

        except Exception as e:
            logger.error(f"Redis add error: {e}")
            await callback.answer("❌ Xatolik!", show_alert=False)
            return
    # Remove Like button to prevent spamming? Or keep it. Keeping it is fine.

# mode_music function removed

# Legacy state handler removed

async def handle_music_logic(message: Message, state: FSMContext):
    """
    Main Logic that searches for music.
    """
    text = message.text
    
    # Simple check to avoid processing commands if called directly
    if text.startswith("/"):
        return

    await safe_delete_message(message)

    from loader import redis_client
    from loader import bot
    lang = await get_user_lang(message.from_user.id, redis_client)
    
    # Validation: 4-200 characters
    if not await check_text_length_and_notify(text, bot, message.chat.id, lang):
        return

    status_msg = await message.answer(t("searching", lang), parse_mode='HTML')
    
    # 20 ta natija olish (pagination uchun)
    results = await search_music(text) 
    
    if not results:
        await safe_edit_text(status_msg, t("no_results", lang))
        return

    # Cache results in state for pagination
    await state.update_data(search_results=results, search_query=text)
    
    await show_music_page(message.chat.id, results, 0, lang, status_msg)

@router.callback_query(F.data.startswith('music_page:'))
async def handle_music_pagination(callback: CallbackQuery, state: FSMContext):
    from loader import redis_client
    lang = await get_user_lang(callback.from_user.id, redis_client)
    page = int(callback.data.split(':')[1])
    data = await state.get_data()
    results = data.get('search_results', [])
    
    if not results:
        await callback.answer(t("no_results", lang), show_alert=True)
        return

    await show_music_page(callback.message.chat.id, results, page, lang, callback.message)
    await callback.answer()

@router.callback_query(F.data.startswith('music:'))
async def handle_music_callback(callback: CallbackQuery):
    """Musiqa yuklab olish tugmasi bosilganda"""
    video_id = callback.data.split(':')[1]
    
    # Check if this is a video/media message or text message
    is_media = False
    try:
        # If it has video/photo/audio/document attribute populated
        if callback.message.video or callback.message.photo or callback.message.audio or callback.message.document:
            is_media = True
    except:
        pass
        
    from loader import redis_client
    lang = await get_user_lang(callback.from_user.id, redis_client)
    await callback.answer(t("music_button_loading", lang), show_alert=False)
    
    # Celery taskga yuboramiz (parallel bajariladi)
    status_msg = None
    
    try:
        if is_media:
            # Reply to the video message
            status_msg = await callback.message.reply(
                t("music_loading", lang),
                parse_mode='HTML'
            )
        else:
            # Edit text (search result)
            await safe_edit_text(callback.message, t("music_loading", lang), parse_mode='HTML')
    except Exception as e:
        # Fallback
        logger.error(f"Error updating status: {e}")
    
    # process_music_task.delay(
    #     chat_id=callback.message.chat.id,
    #     video_id=video_id,
    #     message_id=callback.message.message_id,
    #     is_media=is_media,
    #     status_message_id=status_msg.message_id if status_msg else None
    # )
    from utils.queue_worker import submit_music_task
    submit_music_task(
        chat_id=callback.message.chat.id,
        video_id=video_id,
        message_id=callback.message.message_id,
        is_media=is_media,
        status_message_id=status_msg.message_id if status_msg else None
    )


@router.callback_query(F.data.startswith('artist:'))
async def handle_artist_songs(callback: CallbackQuery, state: FSMContext):
    """Muallifning boshqa qo'shiqlarini ko'rsatish"""
    video_id = callback.data.split(':')[1]
    from loader import redis_client
    lang = await get_user_lang(callback.from_user.id, redis_client)

    if not redis_client:
        await callback.answer(t("db_error", lang), show_alert=True)
        return

    artist_name = await redis_client.get(f"artist:{video_id}")
    if not artist_name:
        await callback.answer(t("artist_not_found", lang), show_alert=True)
        return

    if isinstance(artist_name, bytes):
        artist_name = artist_name.decode()

    await callback.answer(t("searching", lang), show_alert=False)
    status_msg = await callback.message.reply(
        t("artist_searching", lang, artist=artist_name),
        parse_mode='HTML'
    )

    results = await search_music(artist_name)
    if not results:
        await safe_edit_text(status_msg, t("no_results", lang))
        return

    await state.update_data(search_results=results, search_query=artist_name)
    await show_music_page(callback.message.chat.id, results, 0, lang, status_msg)

@router.callback_query(F.data == 'delete_this_msg')
async def handle_delete_message_callback(callback: CallbackQuery):
    """Xabar o'chirish tugmasi bosilganda"""
    from loader import redis_client
    lang = await get_user_lang(callback.from_user.id, redis_client)
    deleted = await safe_delete_message(callback.message)
    if not deleted:
        await callback.answer(t("delete_failed", lang), show_alert=True)
