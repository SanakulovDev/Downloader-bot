from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from loader import dp, db
from states.bot_states import BotStates
from keyboards.default_keyboards import main_menu
from utils.db_api.models import User
from sqlalchemy import select

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Start command"""
    try:
        async with db() as session:
            user_id = message.from_user.id
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                await state.set_state(BotStates.waiting_for_name)
                await message.answer("👋 Assalomu alaykum! Botdan foydalanish uchun ismingizni kiriting:")
                return
    except Exception as e:
        print(f"Error checking user: {e}")

    await state.set_state(BotStates.waiting_for_mode)
    await message.answer(
        "👋 Salom! Men universal media botman.\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=main_menu
    )

@router.message(BotStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Handle name input"""
    full_name = message.text
    user_id = message.from_user.id
    username = message.from_user.username

    try:
        async with db() as session:
            new_user = User(id=user_id, full_name=full_name, username=username)
            session.add(new_user)
            await session.commit()
    except Exception as e:
        print(f"Error saving user: {e}")
        await message.answer("Xatolik yuz berdi, iltimos qaytadan urinib ko'ring /start")
        return

    await state.set_state(BotStates.waiting_for_mode)
    await message.answer(
        f"Rahmat, {full_name}! Ro'yxatdan o'tdingiz.\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=main_menu
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Help command"""
    await message.answer(
        "📖 Bot haqida ma'lumot:\n\n"
        "1️⃣ <b>Video yuklash:</b> Link yuboring\n"
        "2️⃣ <b>Musiqa:</b> Qo'shiq nomini yozing (masalan: 'Believer')\n\n"
        "⚡ Bot juda tez ishlaydi!",
        parse_mode='HTML'
    )
