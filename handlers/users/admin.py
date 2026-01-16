from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from filters.admin import IsAdmin
from loader import db
from utils.db_api.models import User
from sqlalchemy import select

router = Router()
router.message.filter(IsAdmin())

class AdminStates(StatesGroup):
    waiting_for_broadcast_message = State()

@router.message(Command("admin"))
async def admin_start(message: Message):
    await message.answer(
        "👨‍💼 Admin paneliga xush kelibsiz!\n\n"
        "/broadcast - Barcha foydalanuvchilarga xabar yuborish\n"
        "/count - Foydalanuvchilar soni"
    )

@router.message(Command("count"))
async def count_users(message: Message):
    try:
        async with db() as session:
            # We can use func.count but fetching all is fine for small scale
            result = await session.execute(select(User))
            users = result.scalars().all()
            users_count = len(users)
        await message.answer(f"📊 Jami foydalanuvchilar: {users_count}")
    except Exception as e:
        await message.answer(f"Error: {e}")

@router.message(Command("broadcast"))
async def start_broadcast(message: Message, state: FSMContext):
    await message.answer("Xabarni yuboring (matn, rasm, video, va h.k):")
    await state.set_state(AdminStates.waiting_for_broadcast_message)

@router.message(AdminStates.waiting_for_broadcast_message)
async def broadcast_message(message: Message, state: FSMContext):
    # Get all users
    try:
        async with db() as session:
            result = await session.execute(select(User.id))
            user_ids = result.scalars().all()
        
        count = 0
        await message.answer(f"📨 Xabar yuborish boshlandi... Jami: {len(user_ids)}")
        
        for user_id in user_ids:
            try:
                await message.copy_to(chat_id=user_id)
                count += 1
            except Exception:
                pass
                
        await message.answer(f"✅ Xabar {count} ta foydalanuvchiga yuborildi.")
    except Exception as e:
        await message.answer(f"Error during broadcast: {e}")
        
    await state.clear()
