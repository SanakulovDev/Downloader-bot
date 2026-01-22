from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
import os
from utils.i18n import get_user_lang, t

router = Router()

@router.message(Command("help"))
async def bot_help(message: Message):
    web_app_url = os.getenv("WEB_APP_URL")
    from loader import redis_client
    lang = await get_user_lang(message.from_user.id, redis_client)
    
    # Needs to be a full URL like https://xyz.ngrok.io/admin/support
    if not web_app_url:
        await message.answer(t("help_no_url", lang))
        return
        
    support_url = f"{web_app_url}/support"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t("help_button", lang), 
                web_app=WebAppInfo(url=support_url)
            )
        ]
    ])
    
    await message.answer(t("help_text", lang), reply_markup=kb, parse_mode="HTML")
