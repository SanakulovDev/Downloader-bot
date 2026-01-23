from aiogram.types import Message


async def safe_delete_message(message: Message) -> bool:
    try:
        await message.delete()
        return True
    except Exception:
        return False


async def safe_edit_text(message: Message, text: str, **kwargs) -> None:
    try:
        await message.edit_text(text, **kwargs)
    except Exception:
        pass


async def check_text_length_and_notify(text: str, bot, chat_id: int, lang: str, min_len: int = 4, max_len: int = 200) -> bool:
    """
    Tekst uzunligini tekshiradi va agar mos kelmasa xabar yuboradi.
    Returns:
        True - agar valid bo'lsa
        False - agar invalid bo'lsa (xabar yuboriladi)
    """
    if not (min_len <= len(text) <= max_len):
        from utils.i18n import t
        await bot.send_message(chat_id, t("no_results", lang))
        return False
    return True
