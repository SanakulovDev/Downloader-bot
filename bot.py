#!/usr/bin/env python3
"""
⚡ SuperFast Python Telegram Downloader Bot
YouTube va Instagram videolarini juda tez yuklab oladi
"""

import asyncio
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import hashlib

import yt_dlp
import redis.asyncio as redis
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties
from aiohttp import ClientTimeout
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from instagram_downloader import download_instagram_direct
from shazamio import Shazam

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
load_dotenv('app/.env')
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TMP_DIR = os.getenv('TMP_DIR', '/dev/shm/tmp')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
# Document sifatida yuboriladi, shuning uchun 2GB limit (Telegram limiti)
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB Telegram document limit

# Bot va Dispatcher
# Timeout ni oshirish (30 daqiqa)
session = AiohttpSession(timeout=1800)
bot = Bot(token=BOT_TOKEN, session=session)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class BotStates(StatesGroup):
    waiting_for_mode = State()
    video_mode = State()
    music_mode = State()

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🎬 Video Yuklash"), KeyboardButton(text="🎵 Musiqa Qidirish")]
    ],
    resize_keyboard=True
)

# Redis cache (bir URL bir marta yuklab olish)
redis_client = None

# TMP_DIR ni yaratish
Path(TMP_DIR).mkdir(parents=True, exist_ok=True)


def is_youtube_url(url: str) -> bool:
    """YouTube URL ni tekshirish"""
    return 'youtube.com' in url or 'youtu.be' in url


def is_instagram_url(url: str) -> bool:
    """Instagram URL ni tekshirish"""
    return 'instagram.com' in url and ('/p/' in url or '/reel/' in url or '/tv/' in url)


def extract_url(text: str) -> Optional[str]:
    """Matndan URL ni ajratib olish"""
    import re
    match = re.search(r'https?://[^\s]+', text)
    return match.group(0) if match else None


async def search_music(query: str) -> List[Dict]:
    import json
    
    # 1. Check Cache
    cache_key = f"search:{query.lower().strip()}"
    try:
        if redis_client:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                logger.info(f"Returning cached results for '{query}'")
                return json.loads(cached_data)
    except Exception as e:
        logger.error(f"Redis cache error: {e}")

    ydl_opts = {
        'quiet': True,
        'extract_flat': 'in_playlist', # Only extract flat for playlists
        'noplaylist': True,
    }
    
    try:
        # Increase limit to 20 to ensure we have enough after filtering
        search_query = f"ytsearch20:{query}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, search_query, download=False)
            if 'entries' in info:
                entries = list(info['entries'])
                logger.info(f"Search found {len(entries)} results for '{query}'")
                
                results = []
                for entry in entries:
                    if entry is None:
                        continue
                        
                    duration = entry.get('duration', 0)
                    # Filter: 1 min (60s) <= duration <= 5 min (300s)
                    if 60 <= duration <= 300:
                        results.append({
                            'id': entry['id'],
                            'title': entry['title'],
                            'duration': duration,
                            'channel': entry.get('uploader', 'Unknown')
                        })
                
                # 2. Save to Cache
                if results and redis_client:
                    try:
                        # Cache for 24 hours (86400 seconds)
                        await redis_client.setex(cache_key, 86400, json.dumps(results))
                    except Exception as e:
                        logger.error(f"Redis save error: {e}")
                
                return results
            else:
                logger.warning(f"No entries in search result for '{query}': {info.keys()}")
    except Exception as e:
        logger.error(f"Search error for '{query}': {e}", exc_info=True)
    return []


async def download_audio(video_id: str, chat_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Music yuklab olish - filename va speed fix"""
    
    # 1. Info olish (nomini bilish uchun)
    title = "Audio"
    author = "Unknown"
    
    try:
        ydl_opts_info = {'quiet': True, 'noplaylist': True}
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            title = info.get('title', 'Audio')
            author = info.get('uploader', 'Unknown')
    except:
        pass

    # Clean filename
    clean_title = f"{title} - {author}".replace('/', '-').replace('\\', '-')
    
    temp_file = Path(TMP_DIR) / f"{video_id}.m4a"
    
    # Cache check
    if temp_file.exists() and temp_file.stat().st_size > 0:
        return str(temp_file), f"{clean_title}.m4a"

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio',
        'outtmpl': str(temp_file),
        'quiet': True,
        'no_warnings': True,
        # Speed optimizations
        'concurrent_fragment_downloads': 5,
        'http_chunk_size': 10485760, # 10MB
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
            
        if temp_file.exists() and temp_file.stat().st_size > 0:
            return str(temp_file), f"{clean_title}.m4a"
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        
    return None, None


async def download_video(url: str, chat_id: int) -> Optional[str]:
    """
    Video ni yuklab olish - async va tez
    Professional optimizatsiya bilan
    """
    temp_file = None
    try:
        # URL hash (cache uchun)
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        temp_file = Path(TMP_DIR) / f"{url_hash}_{chat_id}.mp4"
        
        # Redis cache tekshirish (bir URL bir marta yuklab olish)
        global redis_client
        if redis_client:
            try:
                cache_key = f"video:{url_hash}"
                cached_path = await redis_client.get(cache_key)
                if cached_path:
                    cached_path_str = cached_path.decode() if isinstance(cached_path, bytes) else cached_path
                    if os.path.exists(cached_path_str):
                        logger.info(f"Using cached video: {cached_path_str}")
                        # Cached faylni nusxalash
                        import shutil
                        shutil.copy2(cached_path_str, temp_file)
                        return str(temp_file)
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")
        
        # Platformani aniqlash
        format_selector = None
        
        if is_instagram_url(url):
            # Instagram uchun direct JSON API (20x tezroq)
            result = await download_instagram_direct(url, temp_file)
            if result and os.path.exists(result):
                # Cache ga saqlash
                if redis_client:
                    try:
                        await redis_client.setex(f"video:{url_hash}", 3600, result.encode())  # 1 soat
                    except:
                        pass
                return result
            # Agar direct download ishlamasa, yt-dlp ga o'tamiz
            format_selector = 'best'
        elif is_youtube_url(url):
            # YouTube uchun (ffmpeg bor, shuning uchun maksimal sifat)
            format_selector = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        else:
            return None
        
        if not format_selector:
            return None
        
        # yt-dlp options - FIXED FOR NO FFMPEG/ARIA2C
        ydl_opts = {
            'format': format_selector,
            'outtmpl': str(temp_file).replace('.mp4', '.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extract_flat': False,
            # Document sifatida yuboriladi, shuning uchun 2GB limit
            'max_filesize': 2 * 1024 * 1024 * 1024,  # 2GB
        }

        # Download qilish
        logger.info(f"Downloading {url} to {temp_file}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])

        # Fayl mavjudligini tekshirish (ext o'zgarishi mumkin)
        downloaded_file = None
        
        # Avval barcha mumkin bo'lgan fayllarni tekshiramiz
        for file in temp_file.parent.glob(f"{temp_file.stem}.*"):
            if file.suffix in ['.mp4', '.webm', '.mkv'] and file.exists():
                # .part fayllarni o'tkazib yuboramiz
                if not file.name.endswith('.part'):
                    downloaded_file = file
                    logger.info(f"Found downloaded file: {downloaded_file}")
                    break
        
        # Agar fayl topilmasa, temp_file ni tekshiramiz
        if not downloaded_file and temp_file.exists():
            downloaded_file = temp_file
            logger.info(f"Using temp_file: {downloaded_file}")
        
        if not downloaded_file or not downloaded_file.exists():
            logger.error(f"Downloaded file not found. Searched for: {temp_file}")
            return None

        # Fayl hajmini tekshirish
        file_size = downloaded_file.stat().st_size
        if file_size == 0:
            logger.error(f"Downloaded file is empty: {downloaded_file}")
            downloaded_file.unlink()
            return None
        
        # Fayl hajmini MB da hisoblash
        file_size_mb = file_size / (1024 * 1024)
        
        # Document sifatida yuboriladi, shuning uchun 2GB limit (Telegram limiti)
        telegram_max_size = 2 * 1024 * 1024 * 1024  # 2GB
            
        if file_size > telegram_max_size:
            logger.warning(f"File too large: {file_size_mb:.2f}MB (Telegram limit: 2GB)")
            downloaded_file.unlink()
            # Maxsus xatolik kodi qaytarish
            raise ValueError(f"FILE_TOO_LARGE:{file_size_mb:.1f}MB")

        logger.info(f"Successfully downloaded: {downloaded_file} ({file_size_mb:.2f}MB)")
        
        # Cache ga saqlash (bir URL bir marta yuklab olish)
        if redis_client:
            try:
                await redis_client.setex(f"video:{url_hash}", 3600, str(downloaded_file).encode())  # 1 soat
            except:
                pass
        
        return str(downloaded_file)

    except ValueError as e:
        # Fayl hajmi uchun maxsus xatolik
        error_msg = str(e)
        if error_msg.startswith("FILE_TOO_LARGE:"):
            size = error_msg.split(":")[1]
            logger.warning(f"File too large: {size}")
            raise ValueError(f"FILE_TOO_LARGE:{size}")
        raise
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp Download error: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        return None


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Start command"""
    await state.set_state(BotStates.waiting_for_mode)
    await message.answer(
        "👋 Salom! Men universal media botman.\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=main_menu
    )

@dp.message(F.text == "🎬 Video Yuklash")
async def mode_video(message: Message, state: FSMContext):
    await state.set_state(BotStates.video_mode)
    await message.answer("� <b>Video rejimidasiz.</b>\n\nYouTube yoki Instagram link yuboring:", parse_mode='HTML')

@dp.message(F.text == "🎵 Musiqa Qidirish")
async def mode_music(message: Message, state: FSMContext):
    await state.set_state(BotStates.music_mode)
    await message.answer("🎵 <b>Musiqa rejimidasiz.</b>\n\nQo'shiq yoki artist nomini yozing:", parse_mode='HTML')


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Help command"""
    await message.answer(
        "📖 Bot haqida ma'lumot:\n\n"
        "1️⃣ <b>Video yuklash:</b> Link yuboring\n"
        "2️⃣ <b>Musiqa:</b> Qo'shiq nomini yozing (masalan: 'Believer')\n\n"
        "⚡ Bot juda tez ishlaydi!",
        parse_mode='HTML'
    )


@dp.callback_query(F.data.startswith('recognize_music:'))
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


@dp.callback_query(F.data.startswith('music:'))
async def handle_music_callback(callback: CallbackQuery):
    """Musiqa yuklab olish tugmasi bosilganda"""
    video_id = callback.data.split(':')[1]
    await callback.answer("⏳ Musiqa yuklanmoqda...", show_alert=False)
    
    # Queue ga qo'shish
    position = DOWNLOAD_QUEUE.qsize() + 1
    await callback.message.edit_text(f"⏳ <b>Navbatga qo'shildi...</b>\nSizning navbatingiz: {position}", parse_mode='HTML')
    
    await DOWNLOAD_QUEUE.put(('music', callback.message.chat.id, video_id, callback))


@dp.message(BotStates.video_mode)
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


@dp.message(BotStates.music_mode)
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

async def show_music_page(chat_id, results, page, message_to_edit: Message = None):
    ITEMS_PER_PAGE = 5
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_items = results[start:end]
    
    keyboard = []
    for res in current_items:
        keyboard.append([
            InlineKeyboardButton(
                text=f"🎵 {res['title']} ({res['channel']})",
                callback_data=f"music:{res['id']}"
            )
        ])
    
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

@dp.callback_query(F.data.startswith('music_page:'))
async def handle_music_pagination(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(':')[1])
    data = await state.get_data()
    results = data.get('search_results', [])
    
    if not results:
        await callback.answer("❌ Qidiruv natijalari eskirgan.", show_alert=True)
        return

    await show_music_page(callback.message.chat.id, results, page, callback.message)
    await callback.answer()

# Generic handler for text if no state (fallback)
@dp.message(F.text)
async def handle_any_text(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await cmd_start(message, state)



# Queue settings
DOWNLOAD_QUEUE = asyncio.Queue()
MAX_CONCURRENT_DOWNLOADS = 2

async def download_worker(worker_id: int):
    logger.info(f"Worker {worker_id} started")
    while True:
        try:
            # Task format: (type, chat_id, data, message/callback)
            task = await DOWNLOAD_QUEUE.get()
            task_type, chat_id, data, msg_obj = task
            
            queue_size = DOWNLOAD_QUEUE.qsize()
            logger.info(f"Worker {worker_id} processing task. Queue size: {queue_size}")
            
            try:
                if task_type == 'video':
                    await process_video_task(chat_id, data, msg_obj)
                elif task_type == 'music':
                    await process_music_task(chat_id, data, msg_obj)
            except Exception as e:
                logger.error(f"Error processing task in worker {worker_id}: {e}")
                try:
                    target = msg_obj.message if isinstance(msg_obj, CallbackQuery) else msg_obj
                    await target.answer("❌ Xatolik yuz berdi.")
                except:
                    pass
            finally:
                DOWNLOAD_QUEUE.task_done()
                
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Worker {worker_id} error: {e}")
            await asyncio.sleep(1)

async def process_video_task(chat_id, url, message: Message):
    status_msg = await message.answer("⏳ <b>Navbat keldi, yuklab olinmoqda...</b>", parse_mode='HTML')
    video_path = await download_video(url, chat_id)
    
    if video_path:
        try:
            await message.answer_video(
                FSInputFile(video_path),
                caption="🤖 @qishloqlik_devbot"
            )
            await status_msg.delete()
            try:
                os.remove(video_path)
            except:
                pass
        except Exception as e:
            logger.error(f"Send video error: {e}")
            await status_msg.edit_text("❌ Yuborishda xatolik yuz berdi!")
    else:
        await status_msg.edit_text("❌ Video yuklab bo'lmadi.")

async def process_music_task(chat_id, video_id, callback: CallbackQuery):
    try:
        # Edit message to show processing started
        await callback.message.edit_text("⏳ <b>Navbat keldi, yuklab olinmoqda...</b>", parse_mode='HTML')
    except:
        pass

    audio_path, filename = await download_audio(video_id, chat_id)
    
    if audio_path:
        try:
            await callback.message.answer_audio(
                FSInputFile(audio_path, filename=filename),
                caption=f"🎵 {filename.replace('.m4a', '')} \n🤖 @qishloqlik_devbot",
                title=filename.replace('.m4a', '')
            )
            try:
                await callback.message.delete()
            except:
                pass
            
            try:
                os.remove(audio_path)
            except:
                pass
        except Exception as e:
            logger.error(f"Send audio error: {e}")
            await callback.message.answer("❌ Yuborishda xatolik yuz berdi!")
    else:
        await callback.message.edit_text("❌ Musiqa yuklashda xatolik bo'ldi.")


async def main():
    """Bot ni ishga tushirish"""
    logger.info("🚀 Bot ishga tushmoqda...")
    
    # Redis ni ulash (cache uchun)
    global redis_client
    try:
        redis_client = await redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=False,
            socket_connect_timeout=2
        )
        await redis_client.ping()
        logger.info("✅ Redis connected (cache enabled)")
    except Exception as e:
        logger.warning(f"Redis not available: {e} (cache disabled)")
        redis_client = None

    # Start Workers
    workers = []
    for i in range(MAX_CONCURRENT_DOWNLOADS):
        w = asyncio.create_task(download_worker(i+1))
        workers.append(w)
    
    # Webhook ni o'chirish (polling uchun)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Polling ni boshlash
    try:
        await dp.start_polling(bot)
    finally:
        # Cancel workers on exit
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
    
    # Redis ni yopish
    if redis_client:
        await redis_client.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi")
