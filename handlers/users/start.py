from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext

from loader import dp, db
from states.bot_states import BotStates
from utils.db_api.models import User
from sqlalchemy import select
from utils.i18n import get_user_lang, set_user_lang, t

LANG_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text=t("lang_uz", "uz"), callback_data="lang:uz"),
        InlineKeyboardButton(text=t("lang_ru", "ru"), callback_data="lang:ru")
    ]
])

router = Router()

async def _send_welcome_or_name_prompt(message: Message, state: FSMContext, lang: str) -> None:
    try:
        async with db() as session:
            user_id = message.from_user.id
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                await state.set_state(BotStates.waiting_for_name)
                await message.answer(t("ask_name", lang))
                return
    except Exception as e:
        print(f"Error checking user: {e}")

    await state.clear()
    await message.answer(t("start_welcome", lang), parse_mode='HTML')


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Start command"""
    from loader import redis_client
    if redis_client:
        raw_lang = await redis_client.get(f"user:lang:{message.from_user.id}")
        if not raw_lang:
            await message.answer(t("choose_language", "uz"), reply_markup=LANG_KB)
            return
    lang = await get_user_lang(message.from_user.id, redis_client)
    await _send_welcome_or_name_prompt(message, state, lang)

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
        from loader import redis_client
        lang = await get_user_lang(user_id, redis_client)
        await message.answer(t("generic_error_retry", lang))
        return

    await state.clear()
    from loader import redis_client
    lang = await get_user_lang(user_id, redis_client)
    await message.answer(t("registration_thanks", lang, name=full_name), parse_mode='HTML')


@router.message(Command("language"))
async def cmd_language(message: Message):
    """Change language command"""
    from loader import redis_client
    lang = await get_user_lang(message.from_user.id, redis_client)
    await message.answer(t("choose_language", lang), reply_markup=LANG_KB)


@router.callback_query(F.data.startswith("lang:"))
async def handle_language_choice(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split(":", 1)[1]
    from loader import redis_client
    await set_user_lang(callback.from_user.id, lang, redis_client)
    if lang == "ru":
        await callback.message.edit_text(t("language_changed_ru", "ru"))
    else:
        await callback.message.edit_text(t("language_changed_uz", "uz"))
    try:
        async with db() as session:
            result = await session.execute(select(User).where(User.id == callback.from_user.id))
            user = result.scalar_one_or_none()
            if not user:
                await _send_welcome_or_name_prompt(callback.message, state, lang)
    except Exception:
        await _send_welcome_or_name_prompt(callback.message, state, lang)
