import os

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from core.env import load_env

load_env()


def create_bot_session(timeout: int = 1800) -> tuple[Bot, AiohttpSession]:
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    session = AiohttpSession(timeout=timeout)
    bot = Bot(token=token, session=session)
    return bot, session
