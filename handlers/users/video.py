from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from pathlib import Path
from shazamio import Shazam
import logging
import asyncio
import yt_dlp
import aiohttp

from loader import dp, TMP_DIR
from states.bot_states import BotStates
from keyboards.default_keyboards import main_menu
from utils.validation import is_youtube_url, is_instagram_url, extract_url, extract_youtube_id
from tasks.bot_tasks import process_video_task
from utils.search import search_music
from utils.download import fetch_youtube_formats_fast, get_format_selector
from utils.telegram_helpers import safe_delete_message, safe_edit_text, check_text_length_and_notify
from utils.i18n import get_user_lang, t

logger = logging.getLogger(__name__)
router = Router()
YTDLP_INFO_TIMEOUT = 60

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
    
    from loader import bot
    from loader import redis_client
    lang = await get_user_lang(message.from_user.id, redis_client)

    # 1. Xabarni darhol o'chirish
    deleted = await safe_delete_message(message)
    if not deleted:
        logger.warning("Xabarni o'chirib bo'lmadi.")

    # 2. Uzunlikni tekshirish (4-200)
    text = message.text or ""
    if not await check_text_length_and_notify(text, bot, chat_id, lang):
        return

    if is_youtube_url(url):
        initial_msg = await _send_fast_preview(bot, chat_id, url, lang)
        info = await _fetch_video_info(url)
        if not info:
            if initial_msg:
                await safe_edit_text(initial_msg, t("no_formats", lang))
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=t("no_formats", lang),
                    disable_web_page_preview=True
                )
            return

        caption, keyboard = _build_format_message(info, lang)
        if not keyboard:
            if initial_msg:
                await safe_edit_text(initial_msg, t("no_formats", lang))
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=t("no_formats", lang),
                    disable_web_page_preview=True
                )
            return

        if initial_msg:
            await _edit_preview_with_formats(bot, initial_msg, caption, keyboard)
        else:
            thumb = info.get("thumbnail")
            if thumb:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=thumb,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=caption,
                    parse_mode='HTML',
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
        return

    # Instagram va boshqa holatlar uchun eski oqim

    # Instagram va boshqa holatlar uchun eski oqim
    status_msg = await bot.send_message(
        chat_id=chat_id,
        text=t("video_loading", lang),
        parse_mode='HTML',
        disable_web_page_preview=True
    )
    # process_video_task.delay(
    #     chat_id=chat_id,
    #     url=url,
    #     status_message_id=status_msg.message_id
    # )
    from tasks.bot_tasks import process_video_task
    process_video_task.delay(
        chat_id=chat_id,
        url=url,
        status_message_id=status_msg.message_id
    )


def _build_format_message(info: dict, lang: str) -> tuple[str, InlineKeyboardMarkup | None]:
    items = info.get("items") or []
    if not items:
        logger.error("No suitable formats found at all")
        return "", None

    format_lines = []
    buttons = []
    row = []
    
    for item in items:
        height = item.get("height")
        format_id = item.get("format_id")
        is_merge = str(item.get("is_merge", 0))
        size_bytes = item.get("size_bytes") or 0
        ext = item.get("ext") or "mp4"
        label = _format_quality_label(height)
        size_mb = "?"
        if size_bytes:
            size_mb = t("size_mb", lang, mb=round(size_bytes / (1024 * 1024), 1))
        
        format_lines.append(t("format_line", lang, height=label, size=size_mb))

        # Pattern: vf:{video_id}:{fmt_id}:{is_merge}:{ext}
        vid = info.get('id')
        
        row.append(
            InlineKeyboardButton(
                text=label, 
                callback_data=f"vf:{vid}:{format_id}:{is_merge}:{ext}"
            )
        )
        if len(row) == 3: # 3 tadan tugma bir qatorda
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # Pastki boshqaruv tugmalari
    buttons.append([
        InlineKeyboardButton(text="🎵 MP3", callback_data=f"music:{info.get('id')}"),
        InlineKeyboardButton(text="❌", callback_data="delete_this_msg")
    ])

    caption = t(
        "formats_header",
        lang,
        title=info.get("title") or "Video",
        uploader=info.get("uploader") or "",
        formats="\n".join(format_lines)
    )
    return caption, InlineKeyboardMarkup(inline_keyboard=buttons)


def _format_quality_label(height: int | None) -> str:
    if height == 2160:
        return "4K"
    if height == 1440:
        return "2K"
    if height == 1080:
        return "HD"
    if height:
        return f"{height}p"
    return "N/A"


def _render_progress_bar(percent: int) -> str:
    width = 12
    pct = max(0, min(100, percent))
    filled = int(width * pct / 100)
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


async def _get_cached_format_info(video_id: str, format_id: str) -> dict:
    from loader import redis_client
    if not redis_client:
        return {}
    try:
        import hashlib
        import json
        url = f"https://www.youtube.com/watch?v={video_id}"
        url_key = f"yt_info:{hashlib.md5(url.encode()).hexdigest()}"
        cached = await redis_client.get(url_key)
        if not cached:
            return {}
        info = json.loads(cached)
        for item in info.get("items") or []:
            if item.get("format_id") == format_id:
                return {
                    "title": info.get("title"),
                    "uploader": info.get("uploader"),
                    "height": item.get("height"),
                }
    except Exception:
        return {}
    return {}

async def _fetch_video_info(url: str) -> dict | None:
    from loader import redis_client
    url_key = None
    if redis_client:
        try:
            import hashlib
            url_key = f"yt_info:{hashlib.md5(url.encode()).hexdigest()}"
            cached = await redis_client.get(url_key)
            if cached:
                import json
                cached_info = json.loads(cached)
                if cached_info and cached_info.get("items"):
                    return cached_info
        except Exception:
            pass

    try:
        info = await asyncio.wait_for(fetch_youtube_formats_fast(url), timeout=YTDLP_INFO_TIMEOUT)

        if info and redis_client and url_key:
            try:
                import json
                await redis_client.setex(url_key, 300, json.dumps(info))
            except Exception:
                pass
        if info:
            return info
        return None
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None


async def _send_fast_preview(bot, chat_id: int, url: str, lang: str):
    video_id = extract_youtube_id(url)
    if not video_id:
        return None
    oembed = await _fetch_oembed(url)
    title = oembed.get("title") if oembed else None
    author = oembed.get("author_name") if oembed else None
    thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    caption = t("preview_header", lang, title=title or "Video", uploader=author or "")
    caption = f"{caption}\n\n{t('formats_loading', lang)}"
    try:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=thumb,
            caption=caption,
            parse_mode='HTML'
        )
    except Exception:
        return await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode='HTML',
            disable_web_page_preview=True
        )


async def _fetch_oembed(url: str) -> dict:
    oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(oembed_url, timeout=2) as resp:
                if resp.status != 200:
                    return {}
                return await resp.json()
    except Exception:
        return {}


async def _edit_preview_with_formats(bot, message: Message, caption: str, keyboard: InlineKeyboardMarkup):
    try:
        # Eng ishonchli usul: Caption va Markupni birga yangilash
        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            parse_mode='HTML',
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Edit preview error: {e}")
        # Agar rasm o'rniga oddiy text bo'lib qolgan bo'lsa yoki boshqa xato:
        await safe_edit_text(message, caption, reply_markup=keyboard, parse_mode='HTML')


@router.callback_query(F.data.startswith('vf:'))
async def handle_video_format(callback: CallbackQuery):
    # vf:{vid}:{fid}:{m}:{ext}
    data = callback.data.split(':')
    if len(data) < 5:
        return
        
    video_id = data[1]
    format_id = data[2]
    is_merge = data[3]
    output_ext = data[4]

    format_selector = get_format_selector(format_id, is_merge)
    from loader import redis_client
    lang = await get_user_lang(callback.from_user.id, redis_client)

    await callback.answer(t("video_loading", lang), show_alert=False)
    status_message_id = callback.message.message_id

    cached_info = await _get_cached_format_info(video_id, format_id)
    format_label = _format_quality_label(cached_info.get("height")) if cached_info else ""
    title = cached_info.get("title") or ""
    uploader = cached_info.get("uploader") or ""
    if not title or not uploader:
        try:
            oembed = await _fetch_oembed(f"https://www.youtube.com/watch?v={video_id}")
            title = title or (oembed.get("title") if oembed else "") or "Video"
            uploader = uploader or (oembed.get("author_name") if oembed else "") or ""
        except Exception:
            title = title or "Video"
    format_line = t("format_label", lang, label=format_label) if format_label else ""
    initial_caption = t(
        "video_progress_caption",
        lang,
        title=title,
        uploader=uploader,
        format=format_line,
        percent="0%",
        bar=_render_progress_bar(0),
    )

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        await callback.message.edit_caption(initial_caption, parse_mode='HTML')
    except Exception:
        await safe_edit_text(callback.message, initial_caption, parse_mode='HTML')

    url = f"https://www.youtube.com/watch?v={video_id}"
    # process_video_task.delay(
    #     chat_id=callback.message.chat.id,
    #     url=url,
    #     status_message_id=callback.message.message_id,
    #     format_selector=format_selector,
    #     output_ext=output_ext
    # )
    from tasks.bot_tasks import process_video_task
    process_video_task.delay(
        chat_id=callback.message.chat.id,
        url=url,
        status_message_id=status_message_id,
        format_selector=format_selector,
        output_ext=output_ext,
        format_label=format_label,
        title=title,
        uploader=uploader,
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
