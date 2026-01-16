#!/usr/bin/env python3
"""
Webhook server - ngrok bilan ishlash uchun
"""

import asyncio
import os
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from dotenv import load_dotenv

load_dotenv('app/.env')

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_PATH = "/webhook"
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')
BASE_WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot va Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Bot kodini import qilish - handlers ni qayta yozish
from bot import (
    is_youtube_url, is_instagram_url, extract_url, download_video
)
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

# Handlers ni qo'shish
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Salom! Men YouTube va Instagram videolarini yuklab oluvchi botman.\n\n"
        "📹 Video linkini yuboring va men uni sizga yuboraman!\n\n"
        "✅ Qo'llab-quvvatlanadigan linklar:\n"
        "• YouTube: https://www.youtube.com/watch?v=...\n"
        "• Instagram: https://www.instagram.com/reel/..."
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 Bot haqida ma'lumot:\n\n"
        "1️⃣ YouTube yoki Instagram video linkini yuboring\n"
        "2️⃣ Bot video ni yuklab oladi\n"
        "3️⃣ Video sizga yuboriladi\n\n"
        "⚡ Bot juda tez ishlaydi!"
    )

@dp.message(F.text)
async def handle_message(message: Message):
    """Xabarlarni qayta ishlash"""
    text = message.text
    chat_id = message.chat.id

    # URL ni topish
    url = extract_url(text)
    
    if not url:
        await message.answer(
            "❌ Iltimos, YouTube yoki Instagram video linkini yuboring.\n\n"
            "Masalan:\n"
            "• https://www.youtube.com/watch?v=...\n"
            "• https://www.instagram.com/reel/..."
        )
        return

    # URL ni tekshirish
    if not (is_youtube_url(url) or is_instagram_url(url)):
        await message.answer("❌ Faqat YouTube va Instagram videolari qo'llab-quvvatlanadi!")
        return

    # Yuklab olishni boshlash
    status_msg = await message.answer(f"🎬 Yuklab olinmoqda:", parse_mode='HTML')
    
    # Video ni yuklab olish
    video_path = await download_video(url, chat_id)

    if not video_path:
        await status_msg.edit_text("❌ Yuklab olishda xatolik yuz berdi!")
        return

    try:
        # Video ni yuborish
        await bot.send_video(
            chat_id=chat_id,
            video=types.FSInputFile(video_path),
            caption="✅ Yuklab olindi! 🎉"
        )
        
        # Status xabarni o'chirish
        await status_msg.delete()
        
        logger.info(f"Video sent to {chat_id}: {url}")

    except Exception as e:
        logger.error(f"Send video error: {e}")
        await status_msg.edit_text("❌ Video yuborishda xatolik yuz berdi!")
    
    finally:
        # Temp faylni o'chirish
        import os
        if os.path.exists(video_path):
            os.remove(video_path)


async def on_startup(bot: Bot) -> None:
    """Webhook ni o'rnatish"""
    if BASE_WEBHOOK_URL:
        webhook_url = f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(
            webhook_url,
            secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None
        )
        logger.info(f"Webhook set to: {webhook_url}")


async def on_shutdown(bot: Bot) -> None:
    """Webhook ni o'chirish"""
    await bot.session.close()


def main():
    """Webhook server ni ishga tushirish"""
    app = web.Application()
    
    # Webhook handler
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    # Startup va shutdown
    setup_application(app, dp, bot=bot)
    
    # Startup handler
    app.on_startup.append(lambda _: on_startup(bot))
    app.on_shutdown.append(lambda _: on_shutdown(bot))
    
    # Server ni ishga tushirish
    web.run_app(app, host="0.0.0.0", port=8080)


if __name__ == '__main__':
    main()

