from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from core.config import get_settings


def create_bot_session(timeout: int = 1800) -> tuple[Bot, AiohttpSession]:
    settings = get_settings()
    token = settings.bot_token
    session = AiohttpSession(timeout=timeout)
    bot = Bot(token=token, session=session)
    return bot, session
