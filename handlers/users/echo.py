from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from handlers.users.start import cmd_start

router = Router()

@router.message(F.text)
async def handle_any_text(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await cmd_start(message, state)
