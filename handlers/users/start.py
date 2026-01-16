from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from loader import dp
from states.bot_states import BotStates
from keyboards.default_keyboards import main_menu

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Start command"""
    await state.set_state(BotStates.waiting_for_mode)
    await message.answer(
        "👋 Salom! Men universal media botman.\n\n"
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
