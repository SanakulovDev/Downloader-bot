from typing import Optional

from aiogram import Bot


async def edit_or_reply_error(
    bot: Bot,
    chat_id: int,
    message_id: int,
    status_message_id: Optional[int],
    is_media: bool,
    text: str
) -> None:
    target_message_id = status_message_id if is_media and status_message_id else message_id
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=target_message_id, text=text)
    except Exception:
        await bot.send_message(chat_id=chat_id, text=text)


async def delete_message_only(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass
