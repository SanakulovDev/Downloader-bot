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
