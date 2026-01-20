from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
import os

router = Router()

@router.message(Command("help"))
async def bot_help(message: Message):
    web_app_url = os.getenv("WEB_APP_URL")
    
    # Needs to be a full URL like https://xyz.ngrok.io/admin/support
    if not web_app_url:
        await message.answer("⚠️ Bot sozlanmagan (WEB_APP_URL yo'q).")
        return
        
    support_url = f"{web_app_url}/support"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📝 Murojaat qoldirish", 
                web_app=WebAppInfo(url=support_url)
            )
        ]
    ])
    
    text = (
        "📖 <b>Bot haqida ma'lumot:</b>\n\n"
        "1️⃣ <b>Video yuklash:</b> Link yuboring\n"
        "2️⃣ <b>Musiqa:</b> Qo'shiq nomini yozing (masalan: 'Believer')\n\n"
        "⚡ <b>Bot juda tez ishlaydi!</b>"
    )
    
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
